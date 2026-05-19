"""Build a federated client-assertion JWT for the OAuth authorization-code flow.

## Why this module exists

The interactive OAuth login flow (``/api/v1/auth/azure/callback``) does
a server-side authorization-code -> token exchange. Microsoft Entra
requires the confidential client to authenticate during that exchange.
The two supported methods are:

1. **client_secret** — a static string. This is what the codebase used
   pre-OIDC-migration. It expires (see ct-jxe: 20-day silent outage),
   leaks in logs, requires rotation tooling, etc.
2. **client_assertion** — a JWT signed by either:
    a. A certificate the app reg trusts (still a static credential to rotate)
    b. A **federated** identity provider the app reg trusts (zero static
       credentials — the assertion is minted on demand by the Managed
       Identity / Workload Identity).

This module implements option **2b**: federated client assertion via the
App Service Managed Identity. The MI hands us an OIDC assertion JWT for
the audience ``api://AzureADTokenExchange``; we include that JWT in the
token-exchange POST as ``client_assertion``, with
``client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer``.

End result: **no client_secret anywhere in the runtime**.

## How the Azure portal must be configured

The app registration needs a **federated credential** that trusts the
Managed Identity. Specifically:

- Issuer:  https://login.microsoftonline.com/<tenant-id>/v2.0
- Subject: the MI's object ID (or api://AzureADTokenExchange/<MI-client-id>,
  depending on portal version)
- Audience: api://AzureADTokenExchange

See ``docs/runbooks/migrate-to-oidc-federation.md`` for the click-through.

## Caching

We do NOT cache the assertion here. The azure-identity
``ManagedIdentityCredential`` already caches its tokens by audience, so
calling ``get_token("api://AzureADTokenExchange")`` repeatedly is cheap
(< 1ms when warm). Adding a second layer of caching in this module
would just be one more invalidation bug waiting to happen — the Zen of
Python is loud on this one ("There should be one — and preferably only
one — obvious way to do it.").
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


#: The audience expected by Microsoft Entra when the assertion is being
#: exchanged for an access token. This is a constant — it's not the
#: target tenant's audience, it's the assertion's audience.
ASSERTION_AUDIENCE: str = "api://AzureADTokenExchange"

#: The grant_type extension that tells the token endpoint to treat the
#: ``client_assertion`` field as the client credential. RFC 7521.
CLIENT_ASSERTION_TYPE: str = (
    "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
)


class FederatedAssertionError(RuntimeError):
    """Raised when we can't mint a federated assertion JWT.

    This is a real configuration / infrastructure error — either:
        * The Managed Identity isn't bound to the App Service (deploy bug)
        * The MI doesn't have permission to mint the assertion (RBAC bug)
        * The IMDS endpoint is unreachable (Azure-side outage)

    The OAuth callback maps this to HTTP 503 with a message that
    distinguishes the OIDC failure mode from a generic Azure AD failure.
    Distinguishing these is critical at incident time — "refresh the
    federated credential on the app reg" is a very different runbook
    from "rotate the client secret".
    """


def get_federated_client_assertion() -> str:
    """Mint a fresh client_assertion JWT from the App Service Managed Identity.

    This is what we include as ``client_assertion`` in the
    authorization-code -> token exchange POST when ``use_oidc_federation``
    is enabled.

    Returns:
        The raw JWT assertion string. NOT a bearer token — it's only
        useful as a credential during the token exchange.

    Raises:
        FederatedAssertionError: If the MI is unreachable or returns no token.
    """
    # Lazy import so that test environments without azure-identity installed
    # (or without an MI endpoint) can still load this module.
    from app.core.oidc_credential import get_oidc_provider

    provider = get_oidc_provider()
    try:
        # The provider's MI credential is what we want directly here. We
        # could go through ``get_credential_for_tenant()`` but that would
        # build a ``ClientAssertionCredential`` around the MI — overkill
        # when all we need is the raw assertion JWT.
        mi_credential = provider._get_mi_credential()
        token = mi_credential.get_token(ASSERTION_AUDIENCE)
    except Exception as exc:
        # The azure-identity SDK throws ClientAuthenticationError here when
        # the MI isn't bound. We catch broadly to also handle ImportError /
        # network blips / etc, then re-raise our own typed exception so the
        # OAuth callback can distinguish "OIDC broken" from "Azure AD
        # rejected our creds" in its 5xx response.
        logger.error(
            "Failed to acquire federated assertion from Managed Identity",
            extra={"audience": ASSERTION_AUDIENCE, "exception_class": type(exc).__name__},
        )
        raise FederatedAssertionError(
            f"Could not mint federated client assertion ({type(exc).__name__}): {exc}"
        ) from exc

    if not token or not token.token:
        # Defensive: shouldn't happen with a healthy MI, but the SDK has
        # been known to return AccessToken instances with empty .token
        # strings during quota-throttle events. Better to fail loud here
        # than to send an empty client_assertion to Entra.
        raise FederatedAssertionError(
            "Managed Identity returned an empty assertion token"
        )

    return token.token


def build_token_exchange_credentials(
    *,
    client_id: str,
    client_secret: str | None,
    use_oidc_federation: bool,
) -> dict[str, Any]:
    """Return the credential fields for an OAuth token-exchange POST body.

    Centralises the "secret vs federated assertion" choice so the OAuth
    callback and the on-behalf-of flow (and any future server-side
    token-exchange flow) all go through ONE place. DRY against the
    branching that would otherwise be duplicated at every call site.

    Args:
        client_id: The app reg's client ID.
        client_secret: The static secret. Used only when use_oidc_federation
            is False. May be None in OIDC mode.
        use_oidc_federation: When True, mint a federated assertion via the
            Managed Identity and include it as ``client_assertion``.
            When False, fall back to ``client_secret``.

    Returns:
        A dict of fields to merge into the token-exchange POST body.

    Raises:
        FederatedAssertionError: If OIDC mode is on but we can't mint the
            assertion (MI not bound, etc.).
        ValueError: If secret mode is on but client_secret is None.
    """
    if use_oidc_federation:
        assertion = get_federated_client_assertion()
        return {
            "client_id": client_id,
            "client_assertion_type": CLIENT_ASSERTION_TYPE,
            "client_assertion": assertion,
        }
    if not client_secret:
        raise ValueError(
            "build_token_exchange_credentials called in secret mode but "
            "client_secret is None. Either set USE_OIDC_FEDERATION=true or "
            "populate AZURE_AD_CLIENT_SECRET."
        )
    return {
        "client_id": client_id,
        "client_secret": client_secret,
    }

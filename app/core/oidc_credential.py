"""OIDC Workload Identity Federation credential provider.

Replaces ClientSecretCredential with ClientAssertionCredential backed by
the App Service Managed Identity. No secrets required at runtime.

CREDENTIAL RESOLUTION ORDER:
1. Azure App Service (prod/staging): ClientAssertionCredential + ManagedIdentityCredential
2. Workload Identity (CI/K8s): WorkloadIdentityCredential via AZURE_FEDERATED_TOKEN_FILE
3. Local development fallback: DefaultAzureCredential (az login, VS Code, CLI)
"""

import logging
import os

from azure.core.credentials import TokenCredential
from azure.identity import (
    ClientAssertionCredential,
    DefaultAzureCredential,
    ManagedIdentityCredential,
    WorkloadIdentityCredential,
)

logger = logging.getLogger(__name__)


class OIDCCredentialProvider:
    """Provides per-tenant TokenCredential instances via OIDC Workload Identity Federation.

    In production (App Service), uses ManagedIdentityCredential to obtain an OIDC
    assertion token, then exchanges it for a per-tenant access token via
    ClientAssertionCredential — zero secrets involved.
    """

    def __init__(self, managed_identity_client_id: str | None = None) -> None:
        """Initialise the provider.

        Args:
            managed_identity_client_id: Client ID of a user-assigned managed identity.
                Leave ``None`` to use the system-assigned managed identity.
        """
        self._managed_identity_client_id = managed_identity_client_id
        self._mi_credential: ManagedIdentityCredential | None = None

    # ------------------------------------------------------------------
    # Environment detection
    # ------------------------------------------------------------------

    def _is_app_service(self) -> bool:
        """Return True when running inside Azure App Service."""
        return bool(os.environ.get("WEBSITE_SITE_NAME"))

    def _is_workload_identity(self) -> bool:
        """Return True when a federated token file is present (CI / K8s)."""
        return bool(os.environ.get("AZURE_FEDERATED_TOKEN_FILE"))

    # ------------------------------------------------------------------
    # MI assertion factory
    # ------------------------------------------------------------------

    def _get_mi_credential(self) -> ManagedIdentityCredential:
        """Lazy-initialise the ManagedIdentityCredential (singleton per provider)."""
        if self._mi_credential is None:
            if self._managed_identity_client_id:
                self._mi_credential = ManagedIdentityCredential(
                    client_id=self._managed_identity_client_id
                )
            else:
                self._mi_credential = ManagedIdentityCredential()
        return self._mi_credential

    def _get_mi_assertion(self) -> str:
        """Obtain an OIDC assertion token from the Managed Identity.

        Called by ClientAssertionCredential on every token refresh — the SDK
        handles caching so this is not called on every API request.

        Returns:
            The raw JWT assertion string from the MI token endpoint.

        Raises:
            azure.core.exceptions.ClientAuthenticationError: If the MI endpoint
                is unreachable or the identity is not configured.
        """
        token = self._get_mi_credential().get_token("api://AzureADTokenExchange")
        return token.token

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_credential_for_tenant(self, tenant_id: str, client_id: str) -> TokenCredential:
        """Return a TokenCredential scoped to the given tenant.

        Credential selection follows the documented resolution order:
        1. App Service  → ClientAssertionCredential (MI-backed, no secrets)
        2. Workload ID  → WorkloadIdentityCredential (file-based token)
        3. Dev fallback → DefaultAzureCredential (az login / VS Code)

        Args:
            tenant_id: Target Azure AD tenant ID.
            client_id: App registration client ID in that tenant.

        Returns:
            A TokenCredential ready to authenticate against the target tenant.
        """
        if self._is_app_service():
            logger.debug(
                "OIDC: App Service path → ClientAssertionCredential (tenant=%s, client=%s)",
                tenant_id,
                client_id,
            )
            return ClientAssertionCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                func=self._get_mi_assertion,
            )

        if self._is_workload_identity():
            logger.debug(
                "OIDC: Workload Identity path → WorkloadIdentityCredential (tenant=%s, client=%s)",
                tenant_id,
                client_id,
            )
            return WorkloadIdentityCredential(
                tenant_id=tenant_id,
                client_id=client_id,
            )

        # Development fallback — guarded by explicit opt-in.
        # In production, a missing WEBSITE_SITE_NAME means a misconfigured App Service;
        # fail loud rather than silently using the wrong identity.
        from app.core.config import get_settings  # lazy — avoids circular at import time

        _settings = get_settings()
        if not _settings.oidc_allow_dev_fallback:
            raise RuntimeError(
                f"OIDC: Neither App Service (WEBSITE_SITE_NAME) nor Workload Identity "
                f"(AZURE_FEDERATED_TOKEN_FILE) environment detected for tenant={tenant_id}. "
                f"Set OIDC_ALLOW_DEV_FALLBACK=true for local development. "
                f"In production, ensure WEBSITE_SITE_NAME is set on the App Service."
            )
        logger.warning(
            "OIDC: Dev fallback active for tenant=%s (OIDC_ALLOW_DEV_FALLBACK=true). "
            "This credential does not scope to the target tenant. "
            "Do NOT use in production.",
            tenant_id,
        )
        return DefaultAzureCredential()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_provider: OIDCCredentialProvider | None = None


def get_oidc_provider() -> OIDCCredentialProvider:
    """Return the module-level OIDCCredentialProvider singleton.

    Reads ``AZURE_MANAGED_IDENTITY_CLIENT_ID`` from settings on first call.
    """
    global _provider
    if _provider is None:
        from app.core.config import get_settings

        settings = get_settings()
        _provider = OIDCCredentialProvider(
            managed_identity_client_id=settings.azure_managed_identity_client_id
        )
    return _provider

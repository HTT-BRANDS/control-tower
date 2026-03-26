"""Smoke tests for OIDC Workload Identity Federation — real Azure calls.

These tests require running in an environment that has OIDC credentials available:
  - Azure App Service with Managed Identity (WEBSITE_SITE_NAME set), OR
  - Workload Identity via token file (AZURE_FEDERATED_TOKEN_FILE set), OR
  - USE_OIDC_FEDERATION=true AND either AZURE_CLIENT_ID or AZURE_MANAGED_IDENTITY_CLIENT_ID

The entire module is skipped when none of those conditions are met, so CI runs
without Azure credentials will not see failures here.

Run manually with:
    uv run pytest tests/smoke/test_oidc_connectivity.py -v -m smoke

Requirements on the Azure side (per tenant app registration):
    - Federated Identity Credential configured with the Managed Identity as subject
    - Issuer: https://login.microsoftonline.com/{managing_tenant_id}/v2.0
    - Audience: api://AzureADTokenExchange
"""

from __future__ import annotations

import os

import pytest

# ---------------------------------------------------------------------------
# Skip the entire module when OIDC environment isn't present.
# This is evaluated at collection time — no import-time Azure calls.
# ---------------------------------------------------------------------------

_HAS_OIDC_ENV = bool(
    os.environ.get("WEBSITE_SITE_NAME")
    or os.environ.get("AZURE_FEDERATED_TOKEN_FILE")
    or (
        os.environ.get("USE_OIDC_FEDERATION", "").lower() == "true"
        and (
            os.environ.get("AZURE_MANAGED_IDENTITY_CLIENT_ID") or os.environ.get("AZURE_CLIENT_ID")
        )
    )
)

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.azure_creds_required,
    pytest.mark.skipif(
        not _HAS_OIDC_ENV,
        reason=(
            "OIDC environment not detected. "
            "Set WEBSITE_SITE_NAME, AZURE_FEDERATED_TOKEN_FILE, "
            "or USE_OIDC_FEDERATION=true to run these tests."
        ),
    ),
]

# ---------------------------------------------------------------------------
# Riverside tenant constants (source of truth: app/core/tenants_config.py)
# ---------------------------------------------------------------------------

HTT_TENANT_ID = "0c0e35dc-188a-4eb3-b8ba-61752154b407"
HTT_APP_ID = "1e3e8417-49f1-4d08-b7be-47045d8a12e9"

BCC_TENANT_ID = "b5380912-79ec-452d-a6ca-6d897b19b294"
BCC_APP_ID = "4861906b-2079-4335-923f-a55cc0e44d64"

FN_TENANT_ID = "98723287-044b-4bbb-9294-19857d4128a0"
FN_APP_ID = "7648d04d-ccc4-43ac-bace-da1b68bf11b4"

TLL_TENANT_ID = "3c7d2bf3-b597-4766-b5cb-2b489c2904d6"
TLL_APP_ID = "52531a02-78fd-44ba-9ab9-b29675767955"

ACTIVE_TENANTS = [
    ("HTT", HTT_TENANT_ID, HTT_APP_ID),
    ("BCC", BCC_TENANT_ID, BCC_APP_ID),
    ("FN", FN_TENANT_ID, FN_APP_ID),
    ("TLL", TLL_TENANT_ID, TLL_APP_ID),
]

AZURE_MANAGEMENT_SCOPE = "https://management.azure.com/.default"
GRAPH_SCOPE = "https://graph.microsoft.com/.default"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def oidc_provider():
    """Module-scoped OIDCCredentialProvider instance.

    Uses the real provider (system or user-assigned MI depending on env).
    """
    from app.core.oidc_credential import OIDCCredentialProvider

    mi_client_id = os.environ.get("AZURE_MANAGED_IDENTITY_CLIENT_ID") or None
    return OIDCCredentialProvider(managed_identity_client_id=mi_client_id)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_oidc_provider_initializes(oidc_provider):
    """OIDCCredentialProvider can be instantiated without error."""
    from app.core.oidc_credential import OIDCCredentialProvider

    assert isinstance(oidc_provider, OIDCCredentialProvider)


def test_credential_for_htt_tenant(oidc_provider):
    """get_credential_for_tenant(HTT) returns a credential object without raising."""
    from azure.core.credentials import TokenCredential

    cred = oidc_provider.get_credential_for_tenant(HTT_TENANT_ID, HTT_APP_ID)
    assert isinstance(cred, TokenCredential), f"Expected TokenCredential, got {type(cred).__name__}"


@pytest.mark.parametrize("code,tenant_id,app_id", ACTIVE_TENANTS)
def test_credential_for_all_active_tenants(oidc_provider, code: str, tenant_id: str, app_id: str):
    """Each of the 4 active Riverside tenants produces a valid credential object."""
    from azure.core.credentials import TokenCredential

    cred = oidc_provider.get_credential_for_tenant(tenant_id, app_id)
    assert isinstance(cred, TokenCredential), (
        f"Tenant {code}: expected TokenCredential, got {type(cred).__name__}"
    )


def test_token_acquisition_htt(oidc_provider):
    """Actually acquires a management-scope token for HTT.

    Proves the federated credential on the HTT app registration is configured
    correctly to trust the managing-tenant Managed Identity.
    """
    cred = oidc_provider.get_credential_for_tenant(HTT_TENANT_ID, HTT_APP_ID)
    token = cred.get_token(AZURE_MANAGEMENT_SCOPE)

    assert token is not None
    assert isinstance(token.token, str)
    assert len(token.token) > 50, "Token looks suspiciously short"
    assert token.expires_on > 0, "Token has no expiration"


def test_graph_token_htt(oidc_provider):
    """Acquires a Graph-scope token for HTT.

    Proves Graph API admin consent was granted for the app registration.
    """
    cred = oidc_provider.get_credential_for_tenant(HTT_TENANT_ID, HTT_APP_ID)
    token = cred.get_token(GRAPH_SCOPE)

    assert token is not None
    assert isinstance(token.token, str)
    assert len(token.token) > 50


def test_azure_client_manager_oidc_mode():
    """AzureClientManager.get_credential(HTT_TENANT_ID) succeeds with OIDC enabled.

    Patches USE_OIDC_FEDERATION into settings via env, which exercises the full
    production call chain without needing a real .env file.
    """
    from unittest.mock import patch

    # Force settings to see use_oidc_federation=True for this test
    from app.core.config import Settings

    oidc_settings = Settings(
        use_oidc_federation=True,
        azure_managed_identity_client_id=os.environ.get("AZURE_MANAGED_IDENTITY_CLIENT_ID"),
        _env_file=None,
    )

    with patch("app.api.services.azure_client.settings", oidc_settings):
        with patch("app.api.services.azure_client.get_settings", return_value=oidc_settings):
            # Reset any cached providers
            import app.core.oidc_credential as oidc_mod
            from app.api.services.azure_client import AzureClientManager

            oidc_mod._provider = None

            manager = AzureClientManager()
            cred = manager.get_credential(HTT_TENANT_ID)

            assert cred is not None
            # If we got a credential without ValueError, the OIDC path worked

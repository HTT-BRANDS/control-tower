"""Tests for sync tenant eligibility helpers."""

from unittest.mock import MagicMock, patch

from app.core.sync.utils import (
    build_sync_eligibility_decision,
    get_sync_eligible_tenants,
    tenant_is_sync_eligible,
)


def _tenant(**overrides):
    tenant = MagicMock()
    tenant.is_active = True
    tenant.tenant_id = "tenant-123"
    tenant.client_id = None
    tenant.client_secret_ref = None
    for key, value in overrides.items():
        setattr(tenant, key, value)
    return tenant


class TestTenantIsSyncEligible:
    def test_inactive_tenant_is_not_eligible(self):
        with patch("app.core.sync.utils.settings") as settings:
            settings.use_uami_auth = False
            settings.use_oidc_federation = False
            settings.key_vault_url = None
            settings.azure_client_id = "shared-client"
            settings.azure_client_secret = (
                "shared-credential-placeholder"  # pragma: allowlist secret
            )

            assert tenant_is_sync_eligible(_tenant(is_active=False)) is False

    def test_secret_mode_without_keyvault_uses_shared_credentials(self):
        with patch("app.core.sync.utils.settings") as settings:
            settings.use_uami_auth = False
            settings.use_oidc_federation = False
            settings.key_vault_url = None
            settings.azure_client_id = "shared-client"
            settings.azure_client_secret = (
                "shared-credential-placeholder"  # pragma: allowlist secret
            )

            assert tenant_is_sync_eligible(_tenant()) is True

    def test_keyvault_mode_rejects_tenant_without_real_secret_path(self):
        with patch("app.core.sync.utils.settings") as settings:
            settings.use_uami_auth = False
            settings.use_oidc_federation = False
            settings.key_vault_url = "https://vault.example"
            settings.azure_client_id = "shared-client"
            settings.azure_client_secret = (
                "shared-credential-placeholder"  # pragma: allowlist secret
            )

            assert tenant_is_sync_eligible(_tenant()) is False

    def test_keyvault_mode_allows_explicit_per_tenant_secret_ref(self):
        with patch("app.core.sync.utils.settings") as settings:
            settings.use_uami_auth = False
            settings.use_oidc_federation = False
            settings.key_vault_url = "https://vault.example"
            settings.azure_client_id = "shared-client"
            settings.azure_client_secret = (
                "shared-credential-placeholder"  # pragma: allowlist secret
            )

            assert (
                tenant_is_sync_eligible(
                    _tenant(
                        client_id="tenant-app-id",
                        client_secret_ref="tenant-client-secret",  # pragma: allowlist secret
                    )
                )
                is True
            )

    def test_oidc_mode_requires_resolvable_app_id(self):
        with patch("app.core.sync.utils.settings") as settings:
            settings.use_uami_auth = False
            settings.use_oidc_federation = True
            settings.key_vault_url = None
            settings.azure_client_id = None
            settings.azure_client_secret = None
            with patch("app.core.sync.utils.get_app_id_for_tenant", return_value=None):
                assert tenant_is_sync_eligible(_tenant()) is False
            with patch("app.core.sync.utils.get_app_id_for_tenant", return_value="app-123"):
                assert tenant_is_sync_eligible(_tenant()) is True


class TestBuildSyncEligibilityDecision:
    def test_keyvault_mode_reports_missing_db_declared_secret_path(self):
        decision = build_sync_eligibility_decision(
            tenant_is_active=True,
            tenant_id="tenant-123",
            tenant_client_id=None,
            tenant_client_secret_ref=None,
            use_uami_auth=False,
            use_oidc_federation=False,
            key_vault_url="https://vault.example",
            azure_client_id="shared-client",
            azure_client_secret="shared-credential",  # pragma: allowlist secret
            resolved_app_id=None,
        )

        assert decision.eligible is False
        assert decision.auth_mode == "key_vault_secret"
        assert decision.reason == "missing_db_declared_secret_path"

    def test_oidc_mode_prefers_resolved_app_id(self):
        decision = build_sync_eligibility_decision(
            tenant_is_active=True,
            tenant_id="tenant-123",
            tenant_client_id=None,
            tenant_client_secret_ref=None,
            use_uami_auth=False,
            use_oidc_federation=True,
            key_vault_url=None,
            azure_client_id=None,
            azure_client_secret=None,
            resolved_app_id="app-123",
        )

        assert decision.eligible is True
        assert decision.auth_mode == "oidc"
        assert decision.reason == "oidc_app_id_resolved"
        assert decision.resolved_app_id == "app-123"


class TestGetSyncEligibleTenants:
    def test_filters_ineligible_tenants(self):
        tenants = [
            _tenant(
                tenant_id="good-1",
                client_id="first-app-id",
                client_secret_ref="first-secret-ref",  # pragma: allowlist secret
            ),
            _tenant(
                tenant_id="good-2",
                client_id="tenant-app-id",
                client_secret_ref="secret-ref",  # pragma: allowlist secret
            ),
            _tenant(tenant_id="bad-1"),
        ]
        with patch("app.core.sync.utils.settings") as settings:
            settings.use_uami_auth = False
            settings.use_oidc_federation = False
            settings.key_vault_url = "https://vault.example"
            settings.azure_client_id = "shared-client"
            settings.azure_client_secret = (
                "shared-credential-placeholder"  # pragma: allowlist secret
            )
            eligible = get_sync_eligible_tenants(tenants)

        assert [tenant.tenant_id for tenant in eligible] == ["good-1", "good-2"]

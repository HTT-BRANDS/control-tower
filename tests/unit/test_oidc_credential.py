"""Unit tests for OIDC Workload Identity Federation credential provider.

Tests cover:
- OIDCCredentialProvider.get_credential_for_tenant() all 3 resolution paths
- ManagedIdentityCredential assertion callback behaviour
- Singleton lazy-init (_get_mi_credential caching)
- AzureClientManager OIDC path (get_credential with use_oidc_federation=True)
- GraphClient OIDC path (_get_credential with use_oidc_federation=True)
- Preflight azure_checks OIDC bypass (_get_credential guard)
- tenants_config helpers (get_app_id_for_tenant, validate_tenant_config, key vault)
"""

import os
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_oidc_provider_singleton():
    """Reset the module-level _provider between tests to prevent cross-test leakage."""
    import app.core.oidc_credential as mod

    mod._provider = None
    yield
    mod._provider = None


def _make_provider(managed_identity_client_id: str | None = None):
    """Construct a fresh OIDCCredentialProvider with no module-level side-effects."""
    from app.core.oidc_credential import OIDCCredentialProvider

    return OIDCCredentialProvider(managed_identity_client_id=managed_identity_client_id)


# ===========================================================================
# Section 1: Environment detection
# ===========================================================================


class TestEnvironmentDetection:
    """_is_app_service() and _is_workload_identity() env-var detection."""

    def test_is_app_service_true_when_website_site_name_set(self):
        with patch.dict(os.environ, {"WEBSITE_SITE_NAME": "my-app-service"}):
            provider = _make_provider()
            assert provider._is_app_service() is True

    def test_is_app_service_false_when_env_var_absent(self):
        env = {k: v for k, v in os.environ.items() if k != "WEBSITE_SITE_NAME"}
        with patch.dict(os.environ, env, clear=True):
            provider = _make_provider()
            assert provider._is_app_service() is False

    def test_is_workload_identity_true_when_token_file_set(self):
        with patch.dict(os.environ, {"AZURE_FEDERATED_TOKEN_FILE": "/var/run/secrets/token"}):
            provider = _make_provider()
            assert provider._is_workload_identity() is True

    def test_is_workload_identity_false_when_env_var_absent(self):
        env = {k: v for k, v in os.environ.items() if k != "AZURE_FEDERATED_TOKEN_FILE"}
        with patch.dict(os.environ, env, clear=True):
            provider = _make_provider()
            assert provider._is_workload_identity() is False


# ===========================================================================
# Section 2: App Service path — ClientAssertionCredential
# ===========================================================================


class TestAppServicePath:
    """When WEBSITE_SITE_NAME is present, get_credential_for_tenant uses
    ClientAssertionCredential backed by the Managed Identity."""

    def test_returns_client_assertion_credential_on_app_service(self):
        with patch.dict(os.environ, {"WEBSITE_SITE_NAME": "governance-app"}):
            with patch("app.core.oidc_credential.ClientAssertionCredential") as mock_cac:
                mock_cac.return_value = MagicMock()
                provider = _make_provider()
                cred = provider.get_credential_for_tenant("tenant-aaa", "client-bbb")

                mock_cac.assert_called_once_with(
                    tenant_id="tenant-aaa",
                    client_id="client-bbb",
                    func=provider._get_mi_assertion,
                )
                assert cred is mock_cac.return_value

    def test_assertion_callback_calls_mi_get_token_with_oidc_audience(self):
        """The func callback must request the AzureADTokenExchange audience."""
        mock_token = MagicMock()
        mock_token.token = "eyJhbGciOiJSUzI1NiJ9.fake_jwt"

        mock_mi = MagicMock()
        mock_mi.get_token.return_value = mock_token

        with patch("app.core.oidc_credential.ManagedIdentityCredential", return_value=mock_mi):
            provider = _make_provider()
            result = provider._get_mi_assertion()

            mock_mi.get_token.assert_called_once_with("api://AzureADTokenExchange")
            assert result == "eyJhbGciOiJSUzI1NiJ9.fake_jwt"

    def test_system_assigned_mi_constructed_without_client_id(self):
        """When no managed_identity_client_id given, ManagedIdentityCredential() with no args."""
        with patch("app.core.oidc_credential.ManagedIdentityCredential") as mock_mi_cls:
            mock_mi_cls.return_value = MagicMock()
            provider = _make_provider(managed_identity_client_id=None)
            provider._get_mi_credential()

            mock_mi_cls.assert_called_once_with()

    def test_user_assigned_mi_constructed_with_client_id(self):
        """When managed_identity_client_id is given, ManagedIdentityCredential(client_id=...) used."""
        with patch("app.core.oidc_credential.ManagedIdentityCredential") as mock_mi_cls:
            mock_mi_cls.return_value = MagicMock()
            provider = _make_provider(managed_identity_client_id="mi-client-uuid")
            provider._get_mi_credential()

            mock_mi_cls.assert_called_once_with(client_id="mi-client-uuid")

    def test_mi_credential_is_lazily_cached_on_provider(self):
        """_get_mi_credential() returns the same object on repeated calls (singleton)."""
        with patch("app.core.oidc_credential.ManagedIdentityCredential") as mock_mi_cls:
            mock_mi_cls.return_value = MagicMock()
            provider = _make_provider()

            cred1 = provider._get_mi_credential()
            cred2 = provider._get_mi_credential()

            assert cred1 is cred2
            mock_mi_cls.assert_called_once()  # constructed exactly once

    def test_different_tenant_client_pairs_produce_independent_credentials(self):
        """Two calls with different (tenant_id, client_id) must NOT share credentials."""
        with patch.dict(os.environ, {"WEBSITE_SITE_NAME": "governance-app"}):
            with patch("app.core.oidc_credential.ClientAssertionCredential") as mock_cac:
                mock_cac.side_effect = lambda **kw: MagicMock(name=f"cac-{kw['tenant_id']}")
                provider = _make_provider()

                cred_a = provider.get_credential_for_tenant("tenant-aaa", "client-111")
                cred_b = provider.get_credential_for_tenant("tenant-bbb", "client-222")

                assert cred_a is not cred_b
                assert mock_cac.call_count == 2


# ===========================================================================
# Section 3: Workload Identity path
# ===========================================================================


class TestWorkloadIdentityPath:
    """When AZURE_FEDERATED_TOKEN_FILE is set (and App Service is NOT), returns
    WorkloadIdentityCredential."""

    def test_returns_workload_identity_credential(self):
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in {"WEBSITE_SITE_NAME", "AZURE_FEDERATED_TOKEN_FILE"}
        }
        env["AZURE_FEDERATED_TOKEN_FILE"] = "/var/run/secrets/token"

        with patch.dict(os.environ, env, clear=True):
            with patch("app.core.oidc_credential.WorkloadIdentityCredential") as mock_wic:
                mock_wic.return_value = MagicMock()
                provider = _make_provider()
                cred = provider.get_credential_for_tenant("tenant-xyz", "client-xyz")

                mock_wic.assert_called_once_with(
                    tenant_id="tenant-xyz",
                    client_id="client-xyz",
                )
                assert cred is mock_wic.return_value

    def test_app_service_takes_priority_over_workload_identity(self):
        """If both WEBSITE_SITE_NAME and AZURE_FEDERATED_TOKEN_FILE are set,
        App Service path wins (it's checked first)."""
        env_override = {
            "WEBSITE_SITE_NAME": "governance-app",
            "AZURE_FEDERATED_TOKEN_FILE": "/var/run/secrets/token",
        }
        with patch.dict(os.environ, env_override):
            with patch("app.core.oidc_credential.ClientAssertionCredential") as mock_cac:
                with patch("app.core.oidc_credential.WorkloadIdentityCredential") as mock_wic:
                    mock_cac.return_value = MagicMock()
                    provider = _make_provider()
                    provider.get_credential_for_tenant("t", "c")

                    mock_cac.assert_called_once()
                    mock_wic.assert_not_called()


# ===========================================================================
# Section 4: Dev fallback path
# ===========================================================================


class TestDevFallbackPath:
    """When neither App Service nor Workload Identity env vars are present,
    DefaultAzureCredential is returned with a WARNING log."""

    def _clean_env(self):
        return {
            k: v
            for k, v in os.environ.items()
            if k not in {"WEBSITE_SITE_NAME", "AZURE_FEDERATED_TOKEN_FILE"}
        }

    def test_returns_default_azure_credential(self):
        mock_settings = MagicMock()
        mock_settings.oidc_allow_dev_fallback = True
        with patch.dict(os.environ, self._clean_env(), clear=True):
            with patch("app.core.oidc_credential.DefaultAzureCredential") as mock_dac:
                with patch("app.core.config.get_settings", return_value=mock_settings):
                    mock_dac.return_value = MagicMock()
                    provider = _make_provider()
                    cred = provider.get_credential_for_tenant("tenant-dev", "client-dev")

                    mock_dac.assert_called_once_with()
                    assert cred is mock_dac.return_value

    def test_dev_fallback_emits_warning_log(self):
        mock_settings = MagicMock()
        mock_settings.oidc_allow_dev_fallback = True
        with patch.dict(os.environ, self._clean_env(), clear=True):
            with patch("app.core.oidc_credential.DefaultAzureCredential"):
                with patch("app.core.config.get_settings", return_value=mock_settings):
                    with patch("app.core.oidc_credential.logger") as mock_logger:
                        provider = _make_provider()
                        provider.get_credential_for_tenant("tenant-dev", "client-dev")

                        mock_logger.warning.assert_called_once()
                        warning_msg = mock_logger.warning.call_args[0][0]
                        assert "OIDC_ALLOW_DEV_FALLBACK" in warning_msg

    def test_dev_fallback_raises_when_not_allowed(self):
        """Kill switch: RuntimeError when OIDC_ALLOW_DEV_FALLBACK is False (the default)."""
        mock_settings = MagicMock()
        mock_settings.oidc_allow_dev_fallback = False
        with patch.dict(os.environ, self._clean_env(), clear=True):
            with patch("app.core.config.get_settings", return_value=mock_settings):
                provider = _make_provider()
                with pytest.raises(RuntimeError) as exc_info:
                    provider.get_credential_for_tenant("fake-tenant", "fake-client")

                msg = str(exc_info.value)
                assert "WEBSITE_SITE_NAME" in msg
                assert "AZURE_FEDERATED_TOKEN_FILE" in msg
                assert "OIDC_ALLOW_DEV_FALLBACK" in msg
                assert "fake-tenant" in msg

    def test_dev_fallback_allowed_explicitly(self):
        """When OIDC_ALLOW_DEV_FALLBACK=True, DefaultAzureCredential is returned."""
        mock_settings = MagicMock()
        mock_settings.oidc_allow_dev_fallback = True
        with patch.dict(os.environ, self._clean_env(), clear=True):
            with patch("app.core.oidc_credential.DefaultAzureCredential") as mock_dac:
                with patch("app.core.config.get_settings", return_value=mock_settings):
                    mock_dac.return_value = MagicMock()
                    provider = _make_provider()
                    cred = provider.get_credential_for_tenant("tenant-x", "client-x")

                    assert cred is mock_dac.return_value


# ===========================================================================
# Section 5: get_oidc_provider() singleton
# ===========================================================================


class TestGetOidcProviderSingleton:
    """Module-level singleton returned by get_oidc_provider()."""

    def test_returns_oidc_credential_provider_instance(self):
        from app.core.oidc_credential import OIDCCredentialProvider, get_oidc_provider

        mock_settings = MagicMock()
        mock_settings.azure_managed_identity_client_id = None

        with patch("app.core.config.get_settings", return_value=mock_settings):
            provider = get_oidc_provider()
            assert isinstance(provider, OIDCCredentialProvider)

    def test_returns_same_instance_on_repeated_calls(self):
        from app.core.oidc_credential import get_oidc_provider

        mock_settings = MagicMock()
        mock_settings.azure_managed_identity_client_id = None

        with patch("app.core.config.get_settings", return_value=mock_settings):
            p1 = get_oidc_provider()
            p2 = get_oidc_provider()
            assert p1 is p2

    def test_passes_managed_identity_client_id_from_settings(self):
        from app.core.oidc_credential import OIDCCredentialProvider, get_oidc_provider

        mock_settings = MagicMock()
        mock_settings.azure_managed_identity_client_id = "user-assigned-mi-uuid"

        with patch("app.core.config.get_settings", return_value=mock_settings):
            provider = get_oidc_provider()
            assert isinstance(provider, OIDCCredentialProvider)
            assert provider._managed_identity_client_id == "user-assigned-mi-uuid"

    def test_reads_settings_only_on_first_call(self):
        """get_settings() must be called exactly once regardless of provider calls."""
        from app.core.oidc_credential import get_oidc_provider

        mock_settings = MagicMock()
        mock_settings.azure_managed_identity_client_id = None

        with patch("app.core.config.get_settings", return_value=mock_settings) as mock_gs:
            get_oidc_provider()
            get_oidc_provider()
            get_oidc_provider()

            mock_gs.assert_called_once()


# ===========================================================================
# Section 6: AzureClientManager OIDC path
# ===========================================================================


class TestAzureClientManagerOidcPath:
    """AzureClientManager.get_credential() branches on use_oidc_federation."""

    @pytest.fixture(autouse=True)
    def _mock_settings(self):
        self.mock_settings = MagicMock()
        self.mock_settings.azure_client_id = "base-client-id"
        self.mock_settings.azure_client_secret = "base-secret"
        self.mock_settings.azure_tenant_id = "base-tenant-id"
        self.mock_settings.key_vault_url = None

    def test_oidc_path_resolves_client_id_from_tenants_config(self):
        self.mock_settings.use_oidc_federation = True
        self.mock_settings.use_uami_auth = False

        mock_cred = MagicMock()
        mock_provider = MagicMock()
        mock_provider.get_credential_for_tenant.return_value = mock_cred

        with patch("app.api.services.azure_client.get_settings", return_value=self.mock_settings):
            with patch("app.api.services.azure_client.settings", self.mock_settings):
                with patch(
                    "app.api.services.azure_client.get_app_id_for_tenant",
                    return_value="tenant-config-client-id",
                ):
                    with patch(
                        "app.core.oidc_credential.get_oidc_provider",
                        return_value=mock_provider,
                    ):
                        from app.api.services.azure_client import AzureClientManager

                        manager = AzureClientManager()
                        cred = manager.get_credential("htt-tenant-id")

                        mock_provider.get_credential_for_tenant.assert_called_once_with(
                            "htt-tenant-id", "tenant-config-client-id"
                        )
                        assert cred is mock_cred

    def test_oidc_path_falls_back_to_db_client_id(self):
        """When tenants_config returns None, fall back to the DB tenant record."""
        self.mock_settings.use_oidc_federation = True
        self.mock_settings.use_uami_auth = False

        mock_cred = MagicMock()
        mock_provider = MagicMock()
        mock_provider.get_credential_for_tenant.return_value = mock_cred

        mock_tenant_record = MagicMock()
        mock_tenant_record.client_id = "db-client-id"

        with patch("app.api.services.azure_client.get_settings", return_value=self.mock_settings):
            with patch("app.api.services.azure_client.settings", self.mock_settings):
                with patch(
                    "app.api.services.azure_client.get_app_id_for_tenant", return_value=None
                ):
                    with patch(
                        "app.core.oidc_credential.get_oidc_provider",
                        return_value=mock_provider,
                    ):
                        from app.api.services.azure_client import AzureClientManager

                        manager = AzureClientManager()
                        with patch.object(
                            manager, "_get_tenant_from_db", return_value=mock_tenant_record
                        ):
                            cred = manager.get_credential("unknown-tenant-id")

                        mock_provider.get_credential_for_tenant.assert_called_once_with(
                            "unknown-tenant-id", "db-client-id"
                        )
                        assert cred is mock_cred

    def test_oidc_path_raises_value_error_when_no_client_id_found(self):
        """ValueError is raised when neither tenants_config nor DB can supply a client_id."""
        self.mock_settings.use_oidc_federation = True
        self.mock_settings.use_uami_auth = False

        with patch("app.api.services.azure_client.get_settings", return_value=self.mock_settings):
            with patch("app.api.services.azure_client.settings", self.mock_settings):
                with patch(
                    "app.api.services.azure_client.get_app_id_for_tenant", return_value=None
                ):
                    from app.api.services.azure_client import AzureClientManager

                    manager = AzureClientManager()
                    with patch.object(manager, "_get_tenant_from_db", return_value=None):
                        with pytest.raises(ValueError, match="OIDC mode"):
                            manager.get_credential("unknown-tenant-id")

    def test_secret_path_used_when_oidc_disabled(self):
        """When use_oidc_federation=False, original ClientSecretCredential path is taken."""
        self.mock_settings.use_oidc_federation = False
        self.mock_settings.use_uami_auth = False

        with patch("app.api.services.azure_client.get_settings", return_value=self.mock_settings):
            with patch("app.api.services.azure_client.settings", self.mock_settings):
                with patch("app.api.services.azure_client.ClientSecretCredential") as mock_csc:
                    mock_csc.return_value = MagicMock()

                    from app.api.services.azure_client import AzureClientManager

                    manager = AzureClientManager()
                    manager.get_credential("some-tenant-id")

                    mock_csc.assert_called_once()
                    call_kwargs = mock_csc.call_args[1]
                    assert call_kwargs["connection_timeout"] == 10


# ===========================================================================
# Section 7: GraphClient OIDC path
# ===========================================================================


class TestGraphClientOidcPath:
    """GraphClient._get_credential() branches on use_oidc_federation.

    After HIGH-3 fix: OIDC path delegates to azure_client_manager singleton
    so clear_cache() takes effect and TTL caching is shared.
    """

    def test_oidc_path_returned_when_oidc_enabled(self):
        mock_settings = MagicMock()
        mock_settings.use_oidc_federation = True
        mock_settings.use_uami_auth = False

        mock_cred = MagicMock()

        with patch("app.api.services.graph_client.settings", mock_settings):
            with patch("app.api.services.azure_client.azure_client_manager") as mock_manager:
                mock_manager.get_credential.return_value = mock_cred

                from app.api.services.graph_client import GraphClient

                client = GraphClient("gc-tenant-id")
                cred = client._get_credential()

                mock_manager.get_credential.assert_called_once_with("gc-tenant-id")
                assert cred is mock_cred

    def test_secret_path_used_when_oidc_disabled(self):
        mock_settings = MagicMock()
        mock_settings.azure_client_id = "gc-client-id"
        mock_settings.azure_client_secret = "gc-secret"
        mock_settings.azure_tenant_id = "gc-tenant-id"
        mock_settings.use_oidc_federation = False
        mock_settings.use_uami_auth = False

        with patch("app.api.services.graph_client.settings", mock_settings):
            with patch("app.api.services.graph_client.ClientSecretCredential") as mock_csc:
                with patch("app.api.services.azure_client.AzureClientManager") as mock_mgr:
                    mock_mgr.return_value._resolve_credentials.return_value = (
                        "client-id",
                        "secret",
                        None,
                    )
                    mock_csc.return_value = MagicMock()

                    from app.api.services.graph_client import GraphClient

                    client = GraphClient("gc-tenant-id")
                    client._get_credential()

                    mock_csc.assert_called_once()
                    call_kwargs = mock_csc.call_args[1]
                    assert call_kwargs["connection_timeout"] == 10

    def test_oidc_credential_is_cached_on_graph_client(self):
        """Once _get_credential() resolves, same object returned on subsequent calls."""
        mock_settings = MagicMock()
        mock_settings.use_oidc_federation = True
        mock_settings.use_uami_auth = False

        mock_cred = MagicMock()

        with patch("app.api.services.graph_client.settings", mock_settings):
            with patch("app.api.services.azure_client.azure_client_manager") as mock_manager:
                mock_manager.get_credential.return_value = mock_cred

                from app.api.services.graph_client import GraphClient

                client = GraphClient("tenant-xyz")
                cred1 = client._get_credential()
                cred2 = client._get_credential()

                assert cred1 is cred2
                # get_credential() on the manager called once (cached on GraphClient instance)
                mock_manager.get_credential.assert_called_once_with("tenant-xyz")


# ===========================================================================
# Section 8: Preflight azure_checks OIDC bypass
# ===========================================================================


class TestAzureCheckGetCredentialOidcBypass:
    """_get_credential() in azure_checks.py bypasses the secret guard in OIDC mode."""

    def test_oidc_mode_bypasses_secret_check_and_delegates_to_manager(self):
        mock_settings = MagicMock()
        mock_settings.use_oidc_federation = True
        mock_settings.use_uami_auth = False
        mock_settings.azure_client_id = None  # no secret configured
        mock_settings.azure_client_secret = None

        mock_cred = MagicMock()
        mock_manager = MagicMock()
        mock_manager.get_credential.return_value = mock_cred

        with patch("app.preflight.azure.base.settings", mock_settings):
            with patch("app.preflight.azure.base.azure_client_manager", mock_manager):
                from app.preflight.azure.base import _get_credential

                cred = _get_credential("tenant-oidc")

                mock_manager.get_credential.assert_called_once_with("tenant-oidc")
                assert cred is mock_cred

    def test_secret_mode_raises_azure_check_error_when_creds_missing(self):
        mock_settings = MagicMock()
        mock_settings.use_oidc_federation = False
        mock_settings.use_uami_auth = False
        mock_settings.azure_client_id = None
        mock_settings.azure_client_secret = None

        with patch("app.preflight.azure.base.settings", mock_settings):
            from app.preflight.azure.base import AzureCheckError, _get_credential

            with pytest.raises(AzureCheckError) as exc_info:
                _get_credential("tenant-secret")

            assert exc_info.value.error_code == "credentials_not_configured"
            assert exc_info.value.details["azure_client_id_set"] is False

    def test_secret_mode_succeeds_when_creds_present(self):
        mock_settings = MagicMock()
        mock_settings.use_oidc_federation = False
        mock_settings.use_uami_auth = False
        mock_settings.azure_client_id = "real-client-id"
        mock_settings.azure_client_secret = "real-client-secret"

        mock_csc = MagicMock()
        with patch("app.preflight.azure.base.settings", mock_settings):
            with patch("azure.identity.ClientSecretCredential", return_value=mock_csc) as mock_cls:
                from app.preflight.azure.base import _get_credential

                cred = _get_credential("tenant-with-secret")
                mock_cls.assert_called_once_with(
                    tenant_id="tenant-with-secret",
                    client_id="real-client-id",
                    client_secret="real-client-secret",
                )
                assert cred is mock_csc


# ===========================================================================
# Section 9: tenants_config helpers
# ===========================================================================


# Build the parametrized list dynamically from the tenant config — no hardcoded IDs.
from app.core.tenants_config import RIVERSIDE_TENANTS as _RT

ALL_FIVE_TENANTS = [(code, cfg.tenant_id, cfg.app_id) for code, cfg in _RT.items()]


class TestTenantsConfigHelpers:
    """get_app_id_for_tenant, validate_tenant_config, get_key_vault_secret_name."""

    @pytest.mark.parametrize("code,tenant_id,expected_app_id", ALL_FIVE_TENANTS)
    def test_get_app_id_for_tenant_returns_correct_app_id(
        self, code: str, tenant_id: str, expected_app_id: str
    ):
        from app.core.tenants_config import get_app_id_for_tenant

        result = get_app_id_for_tenant(tenant_id)
        assert result == expected_app_id, (
            f"Tenant {code}: expected app_id {expected_app_id!r}, got {result!r}"
        )

    def test_get_app_id_for_tenant_returns_none_for_unknown(self):
        from app.core.tenants_config import get_app_id_for_tenant

        assert get_app_id_for_tenant("00000000-0000-0000-0000-000000000000") is None

    def test_validate_tenant_config_passes_for_all_oidc_tenants(self):
        """All 5 Riverside tenants have oidc_enabled=True and valid IDs → no issues."""
        from app.core.tenants_config import validate_tenant_config

        issues = validate_tenant_config()
        assert issues == [], f"Unexpected validation issues: {issues}"

    def test_get_key_vault_secret_name_returns_none_when_oidc_enabled(self):
        """When oidc_enabled=True, secret name is not needed → returns None."""
        from app.core.tenants_config import get_key_vault_secret_name

        for code, _, _ in ALL_FIVE_TENANTS:
            result = get_key_vault_secret_name(code)
            assert result is None, f"{code}: expected None (OIDC), got {result!r}"

    def test_get_key_vault_secret_name_raises_for_unknown_code(self):
        from app.core.tenants_config import get_key_vault_secret_name

        with pytest.raises(ValueError, match="Unknown tenant code"):
            get_key_vault_secret_name("NOPE")

    def test_all_five_tenants_have_oidc_enabled_true(self):
        from app.core.tenants_config import RIVERSIDE_TENANTS

        for code, config in RIVERSIDE_TENANTS.items():
            assert config.oidc_enabled is True, f"{code}.oidc_enabled should be True"

    def test_all_five_tenants_have_no_key_vault_secret_name(self):
        from app.core.tenants_config import RIVERSIDE_TENANTS

        for code, config in RIVERSIDE_TENANTS.items():
            assert config.key_vault_secret_name is None, (
                f"{code}.key_vault_secret_name should be None (OIDC mode)"
            )

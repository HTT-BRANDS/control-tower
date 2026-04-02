"""Unit tests for Phase C UAMI (User-Assigned Managed Identity) authentication.

Tests the UAMI credential provider, token caching, environment detection,
and integration with the multi-tenant app via Federated Identity Credentials.

Phase C: Zero-secrets authentication using User-Assigned Managed Identity
- Uses UAMI with OIDC federation instead of client secrets
- Eliminates all secrets from configuration
- Backward compatible with Phase B (can rollback)
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.core.uami_credential import (
    CachedToken,
    UAMICredentialError,
    UAMICredentialProvider,
    get_uami_provider,
    reset_provider,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_uami_config():
    """Create sample UAMI configuration."""
    return {
        "uami_client_id": "00000000-0000-0000-0000-000000000001",
        "uami_principal_id": "00000000-0000-0000-0000-000000000002",
        "fic_id": "github-actions-federation",
        "multi_tenant_app_id": "00000000-0000-0000-0000-000000000003",
        "tenant_id": "00000000-0000-0000-0000-000000000004",
    }


@pytest.fixture
def provider(sample_uami_config):
    """Create a UAMI credential provider with test configuration."""
    return UAMICredentialProvider(
        uami_client_id=sample_uami_config["uami_client_id"],
        fic_id=sample_uami_config["fic_id"],
    )


@pytest.fixture
def mock_token():
    """Create a mock OIDC token."""
    # Simulated JWT structure (not a real token, just for testing)
    return (
        "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsIng1dCI6IjdkRC1nZWNOZ1gx"
        "WmViTlhmTVhEYl9hVkhNaWxoVSIsImtpZCI6IjdkRC1nZWNOZ1gxWmViTlhm"
        "TVhEYl9hVkhNaWxoVSJ9.eyJpc3MiOiJodHRwczovL2xvZ2luLm1pY3Jvc29m"
        "dG9ubGluZS5jb20vY29tbW9uL3YyLjAiLCJpYXQiOjE3MDQwNjcyMDAsImV4"
        "cCI6MTcwNDA3MDgwMCwic3ViIjoiMDAwMDAwMDAtMDAwMC0wMDAwLTAwMDAt"
        "MDAwMDAwMDAwMDAxIn0.mock_signature"
    )


# ============================================================================
# Test CachedToken
# ============================================================================


class TestCachedToken:
    """Test the CachedToken dataclass."""

    def test_creation(self):
        """Should create a cached token with correct values."""
        import time

        now = time.time()
        token = "test_token"
        expires = now + 3600

        cached = CachedToken(token=token, created_at=now, expires_at=expires)

        assert cached.token == token
        assert cached.created_at == now
        assert cached.expires_at == expires

    def test_is_expired_true(self):
        """Should return True when token is expired."""
        import time

        now = time.time()
        cached = CachedToken(token="test", created_at=now - 7200, expires_at=now - 3600)

        assert cached.is_expired() is True

    def test_is_expired_false(self):
        """Should return False when token is not expired."""
        import time

        now = time.time()
        cached = CachedToken(token="test", created_at=now, expires_at=now + 3600)

        assert cached.is_expired() is False

    def test_should_refresh_true(self):
        """Should return True when within refresh buffer."""
        import time

        now = time.time()
        # Token expires in 4 minutes (within 5 minute default buffer)
        cached = CachedToken(token="test", created_at=now, expires_at=now + 240)

        assert cached.should_refresh() is True

    def test_should_refresh_false(self):
        """Should return False when outside refresh buffer."""
        import time

        now = time.time()
        # Token expires in 10 minutes (outside 5 minute default buffer)
        cached = CachedToken(token="test", created_at=now, expires_at=now + 600)

        assert cached.should_refresh() is False


# ============================================================================
# Test UAMICredentialProvider Initialization
# ============================================================================


class TestUAMICredentialProviderInit:
    """Test UAMI credential provider initialization."""

    def test_init_with_explicit_values(self, sample_uami_config):
        """Should accept explicit configuration values."""
        provider = UAMICredentialProvider(
            uami_client_id=sample_uami_config["uami_client_id"],
            fic_id=sample_uami_config["fic_id"],
            token_ttl_seconds=7200,
        )

        assert provider._uami_client_id == sample_uami_config["uami_client_id"]
        assert provider._fic_id == sample_uami_config["fic_id"]
        assert provider._token_ttl == 7200

    def test_init_from_environment(self, monkeypatch):
        """Should read configuration from environment variables."""
        monkeypatch.setenv("UAMI_CLIENT_ID", "env-uami-client-id")
        monkeypatch.setenv("FEDERATED_IDENTITY_CREDENTIAL_ID", "env-fic-id")

        provider = UAMICredentialProvider()

        assert provider._uami_client_id == "env-uami-client-id"
        assert provider._fic_id == "env-fic-id"

    def test_init_defaults(self):
        """Should use sensible defaults when no configuration provided."""
        provider = UAMICredentialProvider()

        assert provider._uami_client_id is None
        assert provider._fic_id == "github-actions-federation"
        assert provider._token_ttl == 3600

    def test_init_warnings_when_no_uami(self, caplog):
        """Should log warning when UAMI client ID not configured."""
        import logging

        with caplog.at_level(logging.WARNING):
            UAMICredentialProvider()

        assert "UAMI client ID not provided" in caplog.text


# ============================================================================
# Test Environment Detection
# ============================================================================


class TestEnvironmentDetection:
    """Test environment detection methods."""

    def test_is_app_service_true(self, monkeypatch):
        """Should detect App Service when WEBSITE_SITE_NAME is set."""
        monkeypatch.setenv("WEBSITE_SITE_NAME", "my-app")
        provider = UAMICredentialProvider()

        assert provider._is_app_service() is True

    def test_is_app_service_false(self, monkeypatch):
        """Should not detect App Service when WEBSITE_SITE_NAME is not set."""
        monkeypatch.delenv("WEBSITE_SITE_NAME", raising=False)
        provider = UAMICredentialProvider()

        assert provider._is_app_service() is False

    def test_is_github_actions_true(self, monkeypatch):
        """Should detect GitHub Actions when both env vars are set."""
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.setenv("AZURE_FEDERATED_TOKEN_FILE", "/tmp/token")
        provider = UAMICredentialProvider()

        assert provider._is_github_actions() is True

    def test_is_github_actions_false_no_github_actions(self, monkeypatch):
        """Should not detect GitHub Actions when GITHUB_ACTIONS not set."""
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
        monkeypatch.setenv("AZURE_FEDERATED_TOKEN_FILE", "/tmp/token")
        provider = UAMICredentialProvider()

        assert provider._is_github_actions() is False

    def test_is_github_actions_false_no_token_file(self, monkeypatch):
        """Should not detect GitHub Actions when token file not set."""
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.delenv("AZURE_FEDERATED_TOKEN_FILE", raising=False)
        provider = UAMICredentialProvider()

        assert provider._is_github_actions() is False

    def test_is_local_development_true(self, monkeypatch):
        """Should detect local development when not in cloud environment."""
        monkeypatch.delenv("WEBSITE_SITE_NAME", raising=False)
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
        provider = UAMICredentialProvider()

        assert provider._is_local_development() is True

    def test_is_local_development_false_in_app_service(self, monkeypatch):
        """Should not detect local development when in App Service."""
        monkeypatch.setenv("WEBSITE_SITE_NAME", "my-app")
        provider = UAMICredentialProvider()

        assert provider._is_local_development() is False

    def test_can_use_uami_in_app_service_with_uami(self, monkeypatch):
        """Should be able to use UAMI in App Service when UAMI is configured."""
        monkeypatch.setenv("WEBSITE_SITE_NAME", "my-app")
        provider = UAMICredentialProvider(uami_client_id="00000000-0000-0000-0000-000000000001")

        assert provider._can_use_uami() is True

    def test_can_use_uami_in_app_service_without_uami(self, monkeypatch):
        """Should not be able to use UAMI in App Service without UAMI client ID."""
        monkeypatch.setenv("WEBSITE_SITE_NAME", "my-app")
        provider = UAMICredentialProvider()  # No UAMI client ID

        assert provider._can_use_uami() is False

    def test_can_use_uami_in_github_actions(self, monkeypatch):
        """Should be able to use UAMI in GitHub Actions with token file."""
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.setenv("AZURE_FEDERATED_TOKEN_FILE", "/tmp/token")
        provider = UAMICredentialProvider()

        assert provider._can_use_uami() is True


# ============================================================================
# Test Token Caching
# ============================================================================


class TestTokenCaching:
    """Test token caching functionality."""

    def test_cache_key_generation(self, provider):
        """Should generate consistent cache keys."""
        key1 = provider._get_cache_key("tenant-1", "client-1")
        key2 = provider._get_cache_key("tenant-1", "client-1")

        assert key1 == key2
        assert key1 == "tenant-1:client-1"

    def test_cache_key_uniqueness(self, provider):
        """Should generate unique cache keys for different tenants/clients."""
        key1 = provider._get_cache_key("tenant-1", "client-1")
        key2 = provider._get_cache_key("tenant-1", "client-2")
        key3 = provider._get_cache_key("tenant-2", "client-1")

        assert key1 != key2
        assert key1 != key3
        assert key2 != key3

    def test_store_and_retrieve_cached_token(self, provider):
        """Should store and retrieve cached tokens."""
        provider._cache_token("tenant-1", "client-1", "token-123")

        retrieved = provider._get_cached_token("tenant-1", "client-1")

        assert retrieved == "token-123"

    def test_retrieve_nonexistent_token(self, provider):
        """Should return None for non-existent cached token."""
        retrieved = provider._get_cached_token("tenant-1", "client-1")

        assert retrieved is None

    def test_expired_token_removed_from_cache(self, provider):
        """Should remove expired tokens from cache."""
        import time

        # Manually insert an expired token
        provider._token_cache["tenant-1:client-1"] = CachedToken(
            token="expired-token",
            created_at=time.time() - 7200,
            expires_at=time.time() - 3600,
        )

        # Should return None and remove from cache
        retrieved = provider._get_cached_token("tenant-1", "client-1")

        assert retrieved is None
        assert "tenant-1:client-1" not in provider._token_cache

    def test_clear_all_cache(self, provider):
        """Should clear all cached tokens when tenant_id is None."""
        provider._cache_token("tenant-1", "client-1", "token-1")
        provider._cache_token("tenant-2", "client-2", "token-2")

        stats = provider.clear_cache()

        assert stats["tokens_cleared"] == 2
        assert len(provider._token_cache) == 0

    def test_clear_specific_tenant_cache(self, provider):
        """Should clear only specified tenant's cached tokens."""
        provider._cache_token("tenant-1", "client-1", "token-1")
        provider._cache_token("tenant-1", "client-2", "token-2")
        provider._cache_token("tenant-2", "client-1", "token-3")

        stats = provider.clear_cache(tenant_id="tenant-1")

        assert stats["tokens_cleared"] == 2
        assert len(provider._token_cache) == 1
        assert provider._get_cached_token("tenant-2", "client-1") == "token-3"

    def test_cache_stats(self, provider):
        """Should return accurate cache statistics."""
        import time

        # Add valid token
        provider._cache_token("tenant-1", "client-1", "token-1")

        # Add expired token
        provider._token_cache["tenant-2:client-1"] = CachedToken(
            token="expired",
            created_at=time.time() - 7200,
            expires_at=time.time() - 3600,
        )

        # Add expiring soon token (4 minutes left)
        provider._token_cache["tenant-3:client-1"] = CachedToken(
            token="expiring",
            created_at=time.time(),
            expires_at=time.time() + 240,
        )

        stats = provider.get_cache_stats()

        assert stats["token_cache_size"] == 3
        assert stats["token_ttl_seconds"] == 3600
        assert stats["expired_tokens"] == 1
        assert stats["expiring_soon"] == 1


# ============================================================================
# Test Credential Creation
# ============================================================================


class TestCredentialCreation:
    """Test credential creation and token acquisition."""

    @patch("app.core.uami_credential.ManagedIdentityCredential")
    def test_get_credential_for_tenant_success(self, mock_mi_class, provider, monkeypatch):
        """Should successfully create ClientAssertionCredential for tenant."""
        monkeypatch.setenv("WEBSITE_SITE_NAME", "my-app")

        mock_mi = MagicMock()
        mock_token = MagicMock()
        mock_token.token = "mock_oidc_token"
        mock_mi.get_token.return_value = mock_token
        mock_mi_class.return_value = mock_mi

        # Patch ClientAssertionCredential to avoid actual Azure calls
        with patch("app.core.uami_credential.ClientAssertionCredential") as mock_credential_class:
            mock_credential = MagicMock()
            mock_credential_class.return_value = mock_credential

            credential = provider.get_credential_for_tenant(
                tenant_id="00000000-0000-0000-0000-000000000001",
                client_id="00000000-0000-0000-0000-000000000002",
            )

            assert credential is mock_credential
            mock_credential_class.assert_called_once()
            call_kwargs = mock_credential_class.call_args.kwargs
            assert call_kwargs["tenant_id"] == "00000000-0000-0000-0000-000000000001"
            assert call_kwargs["client_id"] == "00000000-0000-0000-0000-000000000002"

    def test_get_credential_raises_when_uami_unavailable(self):
        """Should raise UAMICredentialError when UAMI cannot be used."""
        # Create provider without UAMI client_id to simulate unavailable UAMI
        provider_without_uami = UAMICredentialProvider(uami_client_id="")

        with pytest.raises(UAMICredentialError) as exc_info:
            provider_without_uami.get_credential_for_tenant(
                tenant_id="00000000-0000-0000-0000-000000000001",
                client_id="00000000-0000-0000-0000-000000000002",
            )

        assert "UAMI authentication is not available" in str(exc_info.value)

    @patch("app.core.uami_credential.ManagedIdentityCredential")
    def test_get_credential_with_force_refresh(self, mock_mi_class, provider, monkeypatch):
        """Should clear cache and create new credential when force_refresh is True."""
        monkeypatch.setenv("WEBSITE_SITE_NAME", "my-app")

        mock_mi = MagicMock()
        mock_token = MagicMock()
        mock_token.token = "mock_oidc_token"
        mock_mi.get_token.return_value = mock_token
        mock_mi_class.return_value = mock_mi

        # Pre-populate cache
        provider._cache_token("tenant-1", "client-1", "old-token")

        with patch("app.core.uami_credential.ClientAssertionCredential"):
            provider.get_credential_for_tenant(
                tenant_id="tenant-1",
                client_id="client-1",
                force_refresh=True,
            )

            # Cache should be cleared
            assert provider._get_cached_token("tenant-1", "client-1") is None


# ============================================================================
# Test OIDC Assertion
# ============================================================================


class TestOIDCAssertion:
    """Test OIDC assertion token acquisition."""

    @patch("app.core.uami_credential.ManagedIdentityCredential")
    def test_get_uami_oidc_assertion_success(self, mock_mi_class, provider):
        """Should successfully obtain OIDC assertion from UAMI."""
        mock_mi = MagicMock()
        mock_token = MagicMock()
        mock_token.token = "test_oidc_token_123"
        mock_mi.get_token.return_value = mock_token
        mock_mi_class.return_value = mock_mi

        # Set up the MI credential
        provider._mi_credential = mock_mi

        token = provider._get_uami_oidc_assertion()

        assert token == "test_oidc_token_123"
        mock_mi.get_token.assert_called_once_with("api://AzureADTokenExchange")

    @patch("app.core.uami_credential.ManagedIdentityCredential")
    def test_get_uami_oidc_assertion_failure(self, mock_mi_class, provider):
        """Should raise UAMICredentialError when assertion fails."""
        mock_mi = MagicMock()
        mock_mi.get_token.side_effect = Exception("Token endpoint error")
        mock_mi_class.return_value = mock_mi

        provider._mi_credential = mock_mi

        with pytest.raises(UAMICredentialError) as exc_info:
            provider._get_uami_oidc_assertion()

        assert "Failed to obtain UAMI OIDC assertion" in str(exc_info.value)


# ============================================================================
# Test Module-Level Functions
# ============================================================================


class TestModuleLevelFunctions:
    """Test module-level singleton and helper functions."""

    def test_get_uami_provider_returns_singleton(self):
        """Should return the same provider instance on multiple calls."""
        reset_provider()  # Ensure clean state

        provider1 = get_uami_provider()
        provider2 = get_uami_provider()

        assert provider1 is provider2

    def test_get_uami_provider_uses_settings(self, monkeypatch):
        """Should read configuration from settings."""
        reset_provider()

        # Mock settings - patch where it's defined, not where it's imported
        mock_settings = MagicMock()
        mock_settings.uami_client_id = "settings-uami-id"
        mock_settings.federated_identity_credential_id = "settings-fic-id"

        with patch("app.core.config.get_settings", return_value=mock_settings):
            provider = get_uami_provider()

            assert provider._uami_client_id == "settings-uami-id"
            assert provider._fic_id == "settings-fic-id"

    def test_reset_provider_clears_singleton(self):
        """Should clear the provider singleton for testing."""
        reset_provider()

        provider1 = get_uami_provider()
        reset_provider()
        provider2 = get_uami_provider()

        assert provider1 is not provider2


# ============================================================================
# Test Public Interface
# ============================================================================


class TestPublicInterface:
    """Test public methods and properties."""

    def test_is_available_returns_true_when_configured(self, monkeypatch):
        """is_available should return True when UAMI is configured."""
        monkeypatch.setenv("WEBSITE_SITE_NAME", "my-app")
        provider = UAMICredentialProvider(uami_client_id="00000000-0000-0000-0000-000000000001")

        assert provider.is_available() is True

    def test_is_available_returns_false_when_not_configured(self):
        """is_available should return False when UAMI is not configured."""
        provider = UAMICredentialProvider()

        assert provider.is_available() is False

    def test_get_environment_info_in_app_service(self, monkeypatch):
        """Should return accurate environment info in App Service."""
        monkeypatch.setenv("WEBSITE_SITE_NAME", "my-app")
        provider = UAMICredentialProvider(uami_client_id="00000000-0000-0000-0000-000000000001")

        info = provider.get_environment_info()

        assert info["is_app_service"] is True
        assert info["is_github_actions"] is False
        assert info["is_local_development"] is False
        assert info["uami_configured"] is True
        assert info["can_use_uami"] is True

    def test_get_environment_info_in_github_actions(self, monkeypatch):
        """Should return accurate environment info in GitHub Actions."""
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.setenv("AZURE_FEDERATED_TOKEN_FILE", "/tmp/token")
        provider = UAMICredentialProvider()

        info = provider.get_environment_info()

        assert info["is_app_service"] is False
        assert info["is_github_actions"] is True
        assert info["is_local_development"] is False
        assert info["uami_configured"] is False
        assert info["can_use_uami"] is True

    def test_get_environment_info_in_local_development(self, monkeypatch):
        """Should return accurate environment info in local development."""
        monkeypatch.delenv("WEBSITE_SITE_NAME", raising=False)
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
        provider = UAMICredentialProvider()

        info = provider.get_environment_info()

        assert info["is_app_service"] is False
        assert info["is_github_actions"] is False
        assert info["is_local_development"] is True

    @patch("app.core.uami_credential.ManagedIdentityCredential")
    def test_get_token_for_tenant(self, mock_mi_class, provider, monkeypatch):
        """Should get token directly for tenant."""
        monkeypatch.setenv("WEBSITE_SITE_NAME", "my-app")

        # Mock MI
        mock_mi = MagicMock()
        mock_oidc = MagicMock()
        mock_oidc.token = "oidc_token"
        mock_mi.get_token.return_value = mock_oidc
        mock_mi_class.return_value = mock_mi
        provider._mi_credential = mock_mi

        # Mock ClientAssertionCredential and token
        mock_credential = MagicMock()
        mock_access_token = MagicMock()
        mock_access_token.token = "final_access_token"
        mock_credential.get_token.return_value = mock_access_token

        with patch(
            "app.core.uami_credential.ClientAssertionCredential",
            return_value=mock_credential,
        ):
            token = provider.get_token_for_tenant(
                tenant_id="tenant-1",
                client_id="client-1",
                scope="https://graph.microsoft.com/.default",
            )

            assert token == "final_access_token"


# ============================================================================
# Test Integration with Configuration
# ============================================================================


class TestConfigurationIntegration:
    """Test integration with application configuration."""

    def test_provider_uses_configured_ttl(self):
        """Should use configured token TTL."""
        provider = UAMICredentialProvider(token_ttl_seconds=7200)

        assert provider._token_ttl == 7200

    def test_cache_respects_ttl(self):
        """Cached tokens should respect TTL."""
        import time

        provider = UAMICredentialProvider(token_ttl_seconds=1)  # 1 second TTL
        provider._cache_token("tenant-1", "client-1", "token-1")

        # Should be available immediately
        assert provider._get_cached_token("tenant-1", "client-1") == "token-1"

        # Wait for expiration
        time.sleep(1.5)

        # Should be expired now
        assert provider._get_cached_token("tenant-1", "client-1") is None


# ============================================================================
# Test Edge Cases
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_uami_client_id_treated_as_none(self):
        """Empty string UAMI client ID should be treated as not configured (None)."""
        provider = UAMICredentialProvider(uami_client_id="")

        assert provider._uami_client_id is None
        assert not provider._uami_client_id  # Falsy

    def test_fic_id_defaults_when_not_set(self):
        """FIC ID should default to 'github-actions-federation'."""
        provider = UAMICredentialProvider()

        assert provider._fic_id == "github-actions-federation"

    def test_valid_uuid_in_cache_key(self, provider):
        """Cache key should work with valid UUIDs."""
        tenant_id = str(uuid.uuid4())
        client_id = str(uuid.uuid4())

        provider._cache_token(tenant_id, client_id, "token")
        retrieved = provider._get_cached_token(tenant_id, client_id)

        assert retrieved == "token"

    def test_clear_cache_empty(self, provider):
        """Clearing empty cache should not error."""
        stats = provider.clear_cache()

        assert stats["tokens_cleared"] == 0

    def test_clear_nonexistent_tenant_cache(self, provider):
        """Clearing cache for non-existent tenant should not error."""
        provider._cache_token("tenant-1", "client-1", "token-1")

        stats = provider.clear_cache(tenant_id="nonexistent-tenant")

        assert stats["tokens_cleared"] == 0
        assert provider._get_cached_token("tenant-1", "client-1") == "token-1"


# ============================================================================
# Test Backward Compatibility
# ============================================================================


class TestBackwardCompatibility:
    """Ensure Phase C can fall back to Phase B."""

    def test_can_detect_when_uami_not_available(self):
        """Should correctly detect when UAMI is not available."""
        provider = UAMICredentialProvider()  # No configuration

        assert provider.is_available() is False

    def test_error_message_when_uami_unavailable(self):
        """Should provide helpful error message when UAMI unavailable."""
        provider = UAMICredentialProvider()

        with pytest.raises(UAMICredentialError) as exc_info:
            provider.get_credential_for_tenant("tenant-1", "client-1")

        error_msg = str(exc_info.value)
        assert "UAMI_CLIENT_ID" in error_msg
        assert "AZURE_FEDERATED_TOKEN_FILE" in error_msg

    def test_uami_client_id_prefix_in_env_info(self, monkeypatch):
        """Should include masked UAMI client ID in environment info."""
        monkeypatch.setenv("WEBSITE_SITE_NAME", "my-app")
        provider = UAMICredentialProvider(uami_client_id="12345678-1234-1234-1234-123456789abc")

        info = provider.get_environment_info()

        assert info["uami_client_id_prefix"] == "12345678..."

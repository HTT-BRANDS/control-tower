"""Unit tests for AzureClientManager.

Tests the AzureClientManager class which manages Azure SDK clients per tenant
with support for both Azure Lighthouse and Key Vault-based multi-tenant credentials.

Coverage:
- Initialization and default configuration
- Client creation per tenant (Lighthouse mode)
- Client creation per tenant (Key Vault mode)
- Credential caching and TTL management
- Auto-refresh before expiry
- Error handling for invalid/missing tenant configs
- Key Vault integration and secret caching
- Cache clearing and bulk operations
"""

import time
from unittest.mock import MagicMock, patch

import pytest


class TestAzureClientManagerInitialization:
    """Test suite for AzureClientManager initialization."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Set up mocks before each test."""
        self.mock_settings = MagicMock()
        self.mock_settings.azure_client_id = "test-client-id"
        self.mock_settings.azure_client_secret = "test-client-secret"
        self.mock_settings.azure_tenant_id = "test-tenant-id"
        self.mock_settings.key_vault_url = None

        with patch("app.api.services.azure_client.get_settings", return_value=self.mock_settings):
            with patch("app.api.services.azure_client.settings", self.mock_settings):
                yield

    def test_initialization_default_ttl(self):
        """Test AzureClientManager initializes with default credential TTL."""
        from app.api.services.azure_client import AzureClientManager

        manager = AzureClientManager()

        assert manager._credential_ttl == AzureClientManager.DEFAULT_CREDENTIAL_TTL_SECONDS
        assert manager._credentials == {}
        assert manager._key_vault_cache == {}
        assert manager._default_credential is None
        assert manager._key_vault_client is None

    def test_initialization_custom_ttl(self):
        """Test AzureClientManager initializes with custom credential TTL."""
        from app.api.services.azure_client import AzureClientManager

        custom_ttl = 7200  # 2 hours
        manager = AzureClientManager(credential_ttl_seconds=custom_ttl)

        assert manager._credential_ttl == custom_ttl

    def test_initialization_no_keyvault_available(self):
        """Test initialization when azure-keyvault-secrets package not installed."""
        from app.api.services.azure_client import AzureClientManager

        with patch("app.api.services.azure_client.KEYVAULT_AVAILABLE", False):
            manager = AzureClientManager()
            kv_client = manager._get_key_vault_client()

            assert kv_client is None


class TestCredentialResolution:
    """Test suite for credential resolution logic."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Set up mocks before each test."""
        self.mock_settings = MagicMock()
        self.mock_settings.azure_client_id = "lighthouse-client-id"
        self.mock_settings.azure_client_secret = "lighthouse-client-secret"
        self.mock_settings.azure_tenant_id = "lighthouse-tenant-id"
        self.mock_settings.key_vault_url = None

        with patch("app.api.services.azure_client.get_settings", return_value=self.mock_settings):
            with patch("app.api.services.azure_client.settings", self.mock_settings):
                yield

    def test_lighthouse_mode_no_keyvault(self):
        """Test credential resolution in Lighthouse mode (no Key Vault configured)."""
        from app.api.services.azure_client import AzureClientManager

        manager = AzureClientManager()
        tenant_id = "tenant-123"

        client_id, client_secret, tenant = manager._resolve_credentials(tenant_id)

        assert client_id == "lighthouse-client-id"
        assert client_secret == "lighthouse-client-secret"
        assert tenant is None

    def test_lighthouse_mode_missing_credentials_raises_error(self):
        """Test error when Lighthouse mode but credentials not configured."""
        from app.api.services.azure_client import AzureClientManager

        self.mock_settings.azure_client_id = None
        self.mock_settings.azure_client_secret = None

        manager = AzureClientManager()
        tenant_id = "tenant-123"

        with pytest.raises(ValueError, match="Could not resolve credentials"):
            manager._resolve_credentials(tenant_id)

    def test_tenant_with_use_lighthouse_flag(self):
        """Test credential resolution when tenant has use_lighthouse=True."""
        from app.api.services.azure_client import AzureClientManager

        self.mock_settings.key_vault_url = "https://test-kv.vault.azure.net/"

        # Mock tenant with use_lighthouse=True
        mock_tenant = MagicMock()
        mock_tenant.tenant_id = "tenant-123"
        mock_tenant.use_lighthouse = True
        mock_tenant.client_id = None
        mock_tenant.client_secret_ref = None

        with patch("app.api.services.azure_client.KEYVAULT_AVAILABLE", True):
            manager = AzureClientManager()
            with patch.object(manager, "_get_tenant_from_db", return_value=mock_tenant):
                client_id, client_secret, tenant = manager._resolve_credentials("tenant-123")

                assert client_id == "lighthouse-client-id"
                assert client_secret == "lighthouse-client-secret"
                assert tenant == mock_tenant

    def test_tenant_with_custom_app_registration(self):
        """Test credential resolution with custom client_id and client_secret_ref."""
        from app.api.services.azure_client import AzureClientManager

        self.mock_settings.key_vault_url = "https://test-kv.vault.azure.net/"

        # Mock tenant with custom app registration
        mock_tenant = MagicMock()
        mock_tenant.tenant_id = "tenant-123"
        mock_tenant.use_lighthouse = False
        mock_tenant.client_id = "custom-client-id"
        mock_tenant.client_secret_ref = "custom-secret-ref"

        with patch("app.api.services.azure_client.KEYVAULT_AVAILABLE", True):
            manager = AzureClientManager()
            with patch.object(manager, "_get_tenant_from_db", return_value=mock_tenant):
                with patch.object(
                    manager, "_fetch_key_vault_secret", return_value="custom-secret-value"
                ) as mock_fetch:
                    client_id, client_secret, tenant = manager._resolve_credentials("tenant-123")

                    assert client_id == "custom-client-id"
                    assert client_secret == "custom-secret-value"
                    assert tenant == mock_tenant
                    mock_fetch.assert_called_once_with("custom-secret-ref", "tenant-123")

    def test_keyvault_standard_secret_format(self):
        """Test credential resolution using standard Key Vault secret format."""
        from app.api.services.azure_client import AzureClientManager

        self.mock_settings.key_vault_url = "https://test-kv.vault.azure.net/"

        # Mock tenant without custom credentials
        mock_tenant = MagicMock()
        mock_tenant.tenant_id = "tenant-123"
        mock_tenant.use_lighthouse = False
        mock_tenant.client_id = None
        mock_tenant.client_secret_ref = None

        with patch("app.api.services.azure_client.KEYVAULT_AVAILABLE", True):
            manager = AzureClientManager()
            with patch.object(manager, "_get_tenant_from_db", return_value=mock_tenant):

                def mock_fetch_secret(secret_name, tenant_id):
                    if secret_name == "tenant-123-client-id":
                        return "kv-client-id"
                    elif secret_name == "tenant-123-client-secret":
                        return "kv-client-secret"
                    return None

                with patch.object(
                    manager, "_fetch_key_vault_secret", side_effect=mock_fetch_secret
                ):
                    client_id, client_secret, tenant = manager._resolve_credentials("tenant-123")

                    assert client_id == "kv-client-id"
                    assert client_secret == "kv-client-secret"
                    assert tenant == mock_tenant

    def test_keyvault_fallback_to_settings(self):
        """Test fallback to settings credentials when Key Vault secrets not found."""
        from app.api.services.azure_client import AzureClientManager

        self.mock_settings.key_vault_url = "https://test-kv.vault.azure.net/"

        mock_tenant = MagicMock()
        mock_tenant.tenant_id = "tenant-123"
        mock_tenant.use_lighthouse = False
        mock_tenant.client_id = None
        mock_tenant.client_secret_ref = None

        with patch("app.api.services.azure_client.KEYVAULT_AVAILABLE", True):
            manager = AzureClientManager()
            with patch.object(manager, "_get_tenant_from_db", return_value=mock_tenant):
                with patch.object(manager, "_fetch_key_vault_secret", return_value=None):
                    client_id, client_secret, tenant = manager._resolve_credentials("tenant-123")

                    # Should fallback to lighthouse credentials
                    assert client_id == "lighthouse-client-id"
                    assert client_secret == "lighthouse-client-secret"

    def test_no_credentials_available_raises_error(self):
        """Test error when no credentials can be resolved."""
        from app.api.services.azure_client import AzureClientManager

        self.mock_settings.key_vault_url = "https://test-kv.vault.azure.net/"
        self.mock_settings.azure_client_id = None
        self.mock_settings.azure_client_secret = None

        mock_tenant = MagicMock()
        mock_tenant.tenant_id = "tenant-123"
        mock_tenant.use_lighthouse = False
        mock_tenant.client_id = None
        mock_tenant.client_secret_ref = None

        with patch("app.api.services.azure_client.KEYVAULT_AVAILABLE", True):
            manager = AzureClientManager()
            with patch.object(manager, "_get_tenant_from_db", return_value=mock_tenant):
                with patch.object(manager, "_fetch_key_vault_secret", return_value=None):
                    with pytest.raises(ValueError, match="Could not resolve credentials"):
                        manager._resolve_credentials("tenant-123")


class TestCredentialCaching:
    """Test suite for credential caching and TTL management."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Set up mocks before each test."""
        self.mock_settings = MagicMock()
        self.mock_settings.azure_client_id = "test-client-id"
        self.mock_settings.azure_client_secret = "test-client-secret"
        self.mock_settings.azure_tenant_id = "test-tenant-id"
        self.mock_settings.key_vault_url = None
        self.mock_settings.use_oidc_federation = False  # secret mode under test
        self.mock_settings.use_uami_auth = False

        with patch("app.api.services.azure_client.get_settings", return_value=self.mock_settings):
            with patch("app.api.services.azure_client.settings", self.mock_settings):
                with patch(
                    "app.api.services.azure_client.ClientSecretCredential"
                ) as self.mock_cred:
                    self.mock_cred_instance = MagicMock()
                    self.mock_cred.return_value = self.mock_cred_instance
                    yield

    def test_credential_cached_on_first_call(self):
        """Test that credentials are cached after first retrieval."""
        from app.api.services.azure_client import AzureClientManager

        manager = AzureClientManager(credential_ttl_seconds=3600)
        tenant_id = "tenant-123"

        # First call should create and cache credential
        cred1 = manager.get_credential(tenant_id)
        assert tenant_id in manager._credentials
        assert cred1 == self.mock_cred_instance

        # Second call should return cached credential
        cred2 = manager.get_credential(tenant_id)
        assert cred2 == cred1
        assert self.mock_cred.call_count == 1  # Only created once

    def test_credential_not_expired_returns_cached(self):
        """Test that non-expired credentials are returned from cache."""
        from app.api.services.azure_client import AzureClientManager, CachedCredential

        manager = AzureClientManager(credential_ttl_seconds=3600)
        tenant_id = "tenant-123"

        # Manually create a fresh cached credential
        now = time.time()
        manager._credentials[tenant_id] = CachedCredential(
            credential=self.mock_cred_instance,
            created_at=now,
            expires_at=now + 3600,
        )

        cred = manager.get_credential(tenant_id)
        assert cred == self.mock_cred_instance
        assert self.mock_cred.call_count == 0  # No new credential created

    def test_expired_credential_refreshed(self):
        """Test that expired credentials are refreshed automatically."""
        from app.api.services.azure_client import AzureClientManager, CachedCredential

        manager = AzureClientManager(credential_ttl_seconds=3600)
        tenant_id = "tenant-123"

        # Create an expired credential
        now = time.time()
        old_cred = MagicMock()
        manager._credentials[tenant_id] = CachedCredential(
            credential=old_cred,
            created_at=now - 4000,
            expires_at=now - 400,  # Expired 400 seconds ago
        )

        cred = manager.get_credential(tenant_id)
        assert cred == self.mock_cred_instance  # New credential
        assert cred != old_cred
        assert self.mock_cred.call_count == 1

    def test_credential_approaching_expiry_refreshed(self):
        """Test that credentials approaching expiry are refreshed."""
        from app.api.services.azure_client import AzureClientManager, CachedCredential

        manager = AzureClientManager(credential_ttl_seconds=3600)
        tenant_id = "tenant-123"

        # Create a credential expiring in 200 seconds (within refresh buffer of 300s)
        now = time.time()
        old_cred = MagicMock()
        manager._credentials[tenant_id] = CachedCredential(
            credential=old_cred,
            created_at=now - 3400,
            expires_at=now + 200,  # Expires in 200 seconds
        )

        cred = manager.get_credential(tenant_id)
        assert cred == self.mock_cred_instance  # Refreshed
        assert self.mock_cred.call_count == 1

    def test_force_refresh_ignores_cache(self):
        """Test force_refresh parameter bypasses cache."""
        from app.api.services.azure_client import AzureClientManager, CachedCredential

        manager = AzureClientManager(credential_ttl_seconds=3600)
        tenant_id = "tenant-123"

        # Create a fresh cached credential
        now = time.time()
        old_cred = MagicMock()
        manager._credentials[tenant_id] = CachedCredential(
            credential=old_cred,
            created_at=now,
            expires_at=now + 3600,
        )

        cred = manager.get_credential(tenant_id, force_refresh=True)
        assert cred == self.mock_cred_instance
        assert cred != old_cred
        assert self.mock_cred.call_count == 1

    def test_cached_credential_ttl_applied(self):
        """Test that cached credentials use configured TTL."""
        from app.api.services.azure_client import AzureClientManager

        custom_ttl = 1800  # 30 minutes
        manager = AzureClientManager(credential_ttl_seconds=custom_ttl)
        tenant_id = "tenant-123"

        before = time.time()
        manager.get_credential(tenant_id)
        after = time.time()

        cached = manager._credentials[tenant_id]
        expected_expiry = cached.created_at + custom_ttl

        assert abs(cached.expires_at - expected_expiry) < 1  # Within 1 second
        assert cached.created_at >= before
        assert cached.created_at <= after


class TestKeyVaultIntegration:
    """Test suite for Key Vault secret fetching and caching."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Set up mocks before each test."""
        self.mock_settings = MagicMock()
        self.mock_settings.azure_client_id = "test-client-id"
        self.mock_settings.azure_client_secret = "test-client-secret"
        self.mock_settings.key_vault_url = "https://test-kv.vault.azure.net/"

        with patch("app.api.services.azure_client.get_settings", return_value=self.mock_settings):
            with patch("app.api.services.azure_client.settings", self.mock_settings):
                yield

    def test_key_vault_secret_fetched_and_cached(self):
        """Test that Key Vault secrets are fetched and cached."""
        from app.api.services.azure_client import AzureClientManager

        mock_secret = MagicMock()
        mock_secret.value = "secret-value-123"

        mock_kv_client = MagicMock()
        mock_kv_client.get_secret.return_value = mock_secret

        with patch("app.api.services.azure_client.KEYVAULT_AVAILABLE", True):
            manager = AzureClientManager()
            with patch.object(manager, "_get_key_vault_client", return_value=mock_kv_client):
                secret1 = manager._fetch_key_vault_secret("test-secret", "tenant-123")
                secret2 = manager._fetch_key_vault_secret("test-secret", "tenant-123")

                assert secret1 == "secret-value-123"
                assert secret2 == "secret-value-123"
                # Should only fetch from Key Vault once due to caching
                assert mock_kv_client.get_secret.call_count == 1

    def test_key_vault_secret_cache_expires(self):
        """Test that cached Key Vault secrets expire after TTL."""
        from app.api.services.azure_client import AzureClientManager

        mock_secret = MagicMock()
        mock_secret.value = "secret-value-123"

        mock_kv_client = MagicMock()
        mock_kv_client.get_secret.return_value = mock_secret

        with patch("app.api.services.azure_client.KEYVAULT_AVAILABLE", True):
            manager = AzureClientManager()

            # Manually add an expired cache entry
            cache_key = "tenant-123:test-secret"
            manager._key_vault_cache[cache_key] = ("old-value", time.time() - 100)

            with patch.object(manager, "_get_key_vault_client", return_value=mock_kv_client):
                secret = manager._fetch_key_vault_secret("test-secret", "tenant-123")

                assert secret == "secret-value-123"  # New value
                assert (
                    cache_key not in manager._key_vault_cache
                    or manager._key_vault_cache[cache_key][0] == "secret-value-123"
                )
                mock_kv_client.get_secret.assert_called_once()

    def test_key_vault_secret_fetch_error_returns_none(self):
        """Test that Key Vault errors return None gracefully."""
        from app.api.services.azure_client import AzureClientManager

        mock_kv_client = MagicMock()
        mock_kv_client.get_secret.side_effect = Exception("Key Vault error")

        with patch("app.api.services.azure_client.KEYVAULT_AVAILABLE", True):
            manager = AzureClientManager()
            with patch.object(manager, "_get_key_vault_client", return_value=mock_kv_client):
                secret = manager._fetch_key_vault_secret("test-secret", "tenant-123")

                assert secret is None

    def test_key_vault_not_configured_returns_none(self):
        """Test that Key Vault client returns None when not configured."""
        from app.api.services.azure_client import AzureClientManager

        self.mock_settings.key_vault_url = None

        manager = AzureClientManager()
        kv_client = manager._get_key_vault_client()

        assert kv_client is None


class TestClientCreation:
    """Test suite for Azure SDK client creation per tenant."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Set up mocks before each test."""
        self.mock_settings = MagicMock()
        self.mock_settings.azure_client_id = "test-client-id"
        self.mock_settings.azure_client_secret = "test-client-secret"
        self.mock_settings.key_vault_url = None
        self.mock_settings.use_oidc_federation = False  # secret mode under test
        self.mock_settings.use_uami_auth = False

        with patch("app.api.services.azure_client.get_settings", return_value=self.mock_settings):
            with patch("app.api.services.azure_client.settings", self.mock_settings):
                with patch("app.api.services.azure_client.ClientSecretCredential"):
                    yield

    def test_get_subscription_client(self):
        """Test creating SubscriptionClient for a tenant."""
        from app.api.services.azure_client import AzureClientManager

        with patch("app.api.services.azure_client.SubscriptionClient") as mock_sub_client:
            manager = AzureClientManager()
            client = manager.get_subscription_client("tenant-123")

            mock_sub_client.assert_called_once()
            assert client is not None

    def test_get_resource_client(self):
        """Test creating ResourceManagementClient for a tenant."""
        from app.api.services.azure_client import AzureClientManager

        with patch(
            "app.api.services.azure_client.ResourceManagementClient"
        ) as mock_resource_client:
            manager = AzureClientManager()
            manager.get_resource_client("tenant-123", "sub-456")

            mock_resource_client.assert_called_once()
            args = mock_resource_client.call_args[0]
            assert args[1] == "sub-456"

    def test_get_cost_client(self):
        """Test creating CostManagementClient for a tenant."""
        from app.api.services.azure_client import AzureClientManager

        with patch("app.api.services.azure_client.CostManagementClient") as mock_cost_client:
            manager = AzureClientManager()
            manager.get_cost_client("tenant-123", "sub-456")

            mock_cost_client.assert_called_once()
            args = mock_cost_client.call_args[0]
            # CostManagementClient only takes credential, not subscription_id
            assert len(args) == 1

    def test_get_policy_client(self):
        """Test creating PolicyInsightsClient for a tenant."""
        from app.api.services.azure_client import AzureClientManager

        with patch("app.api.services.azure_client.PolicyInsightsClient") as mock_policy_client:
            manager = AzureClientManager()
            manager.get_policy_client("tenant-123", "sub-456")

            mock_policy_client.assert_called_once()
            args = mock_policy_client.call_args[0]
            assert args[1] == "sub-456"

    def test_get_security_client(self):
        """Test creating SecurityCenter client for a tenant."""
        from app.api.services.azure_client import AzureClientManager

        with patch("app.api.services.azure_client.SecurityCenter") as mock_security_client:
            manager = AzureClientManager()
            manager.get_security_client("tenant-123", "sub-456")

            mock_security_client.assert_called_once()
            args = mock_security_client.call_args[0]
            assert args[1] == "sub-456"

    def test_get_default_credential(self):
        """Test getting DefaultAzureCredential for Lighthouse scenarios."""
        from app.api.services.azure_client import AzureClientManager

        with patch("app.api.services.azure_client.DefaultAzureCredential") as mock_default_cred:
            mock_default_instance = MagicMock()
            mock_default_cred.return_value = mock_default_instance

            manager = AzureClientManager()
            cred1 = manager.get_default_credential()
            cred2 = manager.get_default_credential()

            # Should create only once and cache
            assert cred1 == mock_default_instance
            assert cred2 == mock_default_instance
            mock_default_cred.assert_called_once()


class TestCacheManagement:
    """Test suite for cache clearing and bulk operations."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Set up mocks before each test."""
        self.mock_settings = MagicMock()
        self.mock_settings.azure_client_id = "test-client-id"
        self.mock_settings.azure_client_secret = "test-client-secret"
        self.mock_settings.key_vault_url = None
        self.mock_settings.use_oidc_federation = False  # secret mode under test
        self.mock_settings.use_uami_auth = False

        with patch("app.api.services.azure_client.get_settings", return_value=self.mock_settings):
            with patch("app.api.services.azure_client.settings", self.mock_settings):
                with patch("app.api.services.azure_client.ClientSecretCredential"):
                    yield

    def test_clear_cache_specific_tenant(self):
        """Test clearing cache for a specific tenant."""
        from app.api.services.azure_client import AzureClientManager, CachedCredential

        manager = AzureClientManager()
        now = time.time()

        # Add cached credentials for multiple tenants
        manager._credentials["tenant-1"] = CachedCredential(
            credential=MagicMock(),
            created_at=now,
            expires_at=now + 3600,
        )
        manager._credentials["tenant-2"] = CachedCredential(
            credential=MagicMock(),
            created_at=now,
            expires_at=now + 3600,
        )

        # Add Key Vault cache entries
        manager._key_vault_cache["tenant-1:secret-1"] = ("value1", now + 300)
        manager._key_vault_cache["tenant-1:secret-2"] = ("value2", now + 300)
        manager._key_vault_cache["tenant-2:secret-1"] = ("value3", now + 300)

        stats = manager.clear_cache(tenant_id="tenant-1")

        assert stats["credentials_cleared"] == 1
        assert stats["secrets_cleared"] == 2
        assert "tenant-1" not in manager._credentials
        assert "tenant-2" in manager._credentials
        assert "tenant-1:secret-1" not in manager._key_vault_cache
        assert "tenant-2:secret-1" in manager._key_vault_cache

    def test_clear_all_caches(self):
        """Test clearing all caches."""
        from app.api.services.azure_client import AzureClientManager, CachedCredential

        manager = AzureClientManager()
        now = time.time()

        # Add multiple cached items
        manager._credentials["tenant-1"] = CachedCredential(
            credential=MagicMock(),
            created_at=now,
            expires_at=now + 3600,
        )
        manager._credentials["tenant-2"] = CachedCredential(
            credential=MagicMock(),
            created_at=now,
            expires_at=now + 3600,
        )
        manager._key_vault_cache["tenant-1:secret"] = ("value", now + 300)

        stats = manager.clear_cache()

        assert stats["credentials_cleared"] == 2
        assert stats["secrets_cleared"] == 1
        assert len(manager._credentials) == 0
        assert len(manager._key_vault_cache) == 0

    def test_get_cache_stats(self):
        """Test retrieving cache statistics."""
        from app.api.services.azure_client import AzureClientManager, CachedCredential

        manager = AzureClientManager(credential_ttl_seconds=3600)
        now = time.time()

        # Add various cached credentials
        # Fresh credential
        manager._credentials["tenant-1"] = CachedCredential(
            credential=MagicMock(),
            created_at=now,
            expires_at=now + 3600,
        )
        # Expiring soon (within 300s buffer)
        manager._credentials["tenant-2"] = CachedCredential(
            credential=MagicMock(),
            created_at=now - 3400,
            expires_at=now + 200,
        )
        # Expired
        manager._credentials["tenant-3"] = CachedCredential(
            credential=MagicMock(),
            created_at=now - 4000,
            expires_at=now - 400,
        )

        manager._key_vault_cache["tenant-1:secret"] = ("value", now + 300)

        stats = manager.get_cache_stats()

        assert stats["credential_cache_size"] == 3
        assert stats["secret_cache_size"] == 1
        assert stats["credential_ttl_seconds"] == 3600
        assert stats["expired_credentials"] == 1
        assert stats["expiring_soon"] == 1

    def test_refresh_all_credentials(self):
        """Test bulk credential refresh."""
        from app.api.services.azure_client import AzureClientManager, CachedCredential

        manager = AzureClientManager()
        now = time.time()

        # Add cached credentials
        manager._credentials["tenant-1"] = CachedCredential(
            credential=MagicMock(),
            created_at=now,
            expires_at=now + 3600,
        )
        manager._credentials["tenant-2"] = CachedCredential(
            credential=MagicMock(),
            created_at=now,
            expires_at=now + 3600,
        )

        with patch.object(manager, "get_credential") as mock_get_cred:
            stats = manager.refresh_all_credentials()

            assert stats["refreshed"] == 2
            assert stats["failed"] == 0
            assert mock_get_cred.call_count == 2
            # Verify force_refresh was used
            for call in mock_get_cred.call_args_list:
                assert call.kwargs.get("force_refresh") is True

    def test_refresh_all_credentials_with_failures(self):
        """Test bulk credential refresh handles failures gracefully."""
        from app.api.services.azure_client import AzureClientManager, CachedCredential

        manager = AzureClientManager()
        now = time.time()

        # Add cached credentials
        manager._credentials["tenant-1"] = CachedCredential(
            credential=MagicMock(),
            created_at=now,
            expires_at=now + 3600,
        )
        manager._credentials["tenant-2"] = CachedCredential(
            credential=MagicMock(),
            created_at=now,
            expires_at=now + 3600,
        )

        def mock_get_cred(tenant_id, force_refresh=False):
            if tenant_id == "tenant-2":
                raise ValueError("Credential error")
            return MagicMock()

        with patch.object(manager, "get_credential", side_effect=mock_get_cred):
            stats = manager.refresh_all_credentials()

            assert stats["refreshed"] == 1
            assert stats["failed"] == 1


class TestErrorHandling:
    """Test suite for error handling and edge cases."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Set up mocks before each test."""
        self.mock_settings = MagicMock()
        self.mock_settings.azure_client_id = "test-client-id"
        self.mock_settings.azure_client_secret = "test-client-secret"
        self.mock_settings.key_vault_url = None
        self.mock_settings.use_oidc_federation = False  # secret mode under test
        self.mock_settings.use_uami_auth = False

        with patch("app.api.services.azure_client.get_settings", return_value=self.mock_settings):
            with patch("app.api.services.azure_client.settings", self.mock_settings):
                yield

    def test_invalid_tenant_config_raises_error(self):
        """Test error handling for invalid tenant configuration."""
        from app.api.services.azure_client import AzureClientManager

        # No credentials configured anywhere
        self.mock_settings.azure_client_id = None
        self.mock_settings.azure_client_secret = None
        self.mock_settings.key_vault_url = None

        manager = AzureClientManager()

        with pytest.raises(ValueError, match="Could not resolve credentials"):
            manager.get_credential("tenant-123")

    def test_tenant_db_lookup_failure_handled(self):
        """Test graceful handling when tenant DB lookup fails."""
        from app.api.services.azure_client import AzureClientManager

        self.mock_settings.key_vault_url = "https://test-kv.vault.azure.net/"

        with patch("app.api.services.azure_client.KEYVAULT_AVAILABLE", True):
            manager = AzureClientManager()

            # Mock DB lookup to return None (simulates failure)
            with patch.object(manager, "_get_tenant_from_db", return_value=None):
                # Should fallback to Key Vault lookup
                with patch.object(
                    manager,
                    "_fetch_key_vault_secret",
                    side_effect=lambda name, tid: (
                        "secret-value" if "secret" in name else "client-id"
                    ),
                ):
                    client_id, client_secret, tenant = manager._resolve_credentials("tenant-123")
                    assert client_id == "client-id"
                    assert client_secret == "secret-value"
                    assert tenant is None

    def test_keyvault_initialization_failure(self):
        """Test handling when Key Vault client initialization fails."""
        from app.api.services.azure_client import AzureClientManager

        self.mock_settings.key_vault_url = "https://test-kv.vault.azure.net/"

        with patch("app.api.services.azure_client.KEYVAULT_AVAILABLE", True):
            with patch(
                "app.api.services.azure_client.DefaultAzureCredential",
                side_effect=Exception("Auth error"),
            ):
                manager = AzureClientManager()
                kv_client = manager._get_key_vault_client()

                assert kv_client is None

    @pytest.mark.asyncio
    async def test_list_subscriptions_error_propagates(self):
        """Test that subscription listing errors are properly raised."""
        from app.api.services.azure_client import AzureClientManager

        with patch("app.api.services.azure_client.ClientSecretCredential"):
            with patch("app.api.services.azure_client.SubscriptionClient") as mock_sub_client:
                mock_client = MagicMock()
                mock_client.subscriptions.list.side_effect = Exception("API error")
                mock_sub_client.return_value = mock_client

                manager = AzureClientManager()

                with pytest.raises(Exception, match="API error"):
                    await manager.list_subscriptions("tenant-123")

    @pytest.mark.asyncio
    async def test_list_subscriptions_success(self):
        """Test successful subscription listing."""
        from app.api.services.azure_client import AzureClientManager

        mock_sub1 = MagicMock()
        mock_sub1.subscription_id = "sub-1"
        mock_sub1.display_name = "Sub 1"
        mock_sub1.state = "Enabled"

        mock_sub2 = MagicMock()
        mock_sub2.subscription_id = "sub-2"
        mock_sub2.display_name = "Sub 2"
        mock_sub2.state = "Disabled"

        with patch("app.api.services.azure_client.ClientSecretCredential"):
            with patch("app.api.services.azure_client.SubscriptionClient") as mock_sub_client:
                mock_client = MagicMock()
                mock_client.subscriptions.list.return_value = [mock_sub1, mock_sub2]
                mock_sub_client.return_value = mock_client

                manager = AzureClientManager()
                result = await manager.list_subscriptions("tenant-123")

                assert len(result) == 2
                assert result[0]["subscription_id"] == "sub-1"
                assert result[0]["display_name"] == "Sub 1"
                assert result[0]["state"] == "Enabled"
                assert result[1]["subscription_id"] == "sub-2"

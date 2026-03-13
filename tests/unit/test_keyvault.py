"""Tests for Key Vault integration."""

from app.core.keyvault import KeyVaultClient, get_keyvault_client


class TestKeyVaultClient:
    """Tests for KeyVaultClient."""

    def test_fallback_to_env_var(self, monkeypatch):
        """When no Key Vault URL, falls back to env vars."""
        monkeypatch.setenv("HTT_CLIENT_SECRET", "test-secret-123")  # pragma: allowlist secret
        client = KeyVaultClient(vault_url=None)
        assert (
            client.get_secret("htt-client-secret") == "test-secret-123"
        )  # pragma: allowlist secret

    def test_env_var_not_found(self):
        """Returns None when secret not in env vars and no Key Vault."""
        client = KeyVaultClient(vault_url=None)
        result = client.get_secret("nonexistent-secret")
        assert result is None

    def test_secret_caching(self, monkeypatch):
        """Secrets are cached after first retrieval."""
        monkeypatch.setenv("MY_SECRET", "cached-value")
        client = KeyVaultClient(vault_url=None)

        # First call
        assert client.get_secret("my-secret") == "cached-value"

        # Remove env var - should still return cached value
        monkeypatch.delenv("MY_SECRET")
        assert client.get_secret("my-secret") == "cached-value"

        # Clear cache
        client.clear_cache()
        assert client.get_secret("my-secret") is None

    def test_keyvault_import_fallback(self, monkeypatch):
        """Gracefully handles missing azure-identity package."""
        monkeypatch.setenv("MY_SECRET", "fallback-value")
        # Even with a vault URL, if azure packages fail to connect, falls back
        client = KeyVaultClient(vault_url="https://test.vault.azure.net/")
        # Client should still work via env var fallback
        assert client.get_secret("my-secret") == "fallback-value"

    def test_clear_cache(self, monkeypatch):
        """clear_cache empties the cache."""
        monkeypatch.setenv("TEST_SECRET", "value")
        client = KeyVaultClient(vault_url=None)
        client.get_secret("test-secret")
        assert "test-secret" in client._cache
        client.clear_cache()
        assert len(client._cache) == 0

    def test_get_keyvault_client_returns_instance(self):
        """get_keyvault_client returns a KeyVaultClient."""
        get_keyvault_client.cache_clear()
        client = get_keyvault_client()
        assert isinstance(client, KeyVaultClient)

    def test_get_keyvault_client_is_cached(self):
        """get_keyvault_client returns the same instance."""
        get_keyvault_client.cache_clear()
        client1 = get_keyvault_client()
        client2 = get_keyvault_client()
        assert client1 is client2

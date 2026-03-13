"""Azure Key Vault integration with environment variable fallback.

Retrieves secrets from Azure Key Vault when configured (production),
falls back to environment variables for development.
"""

import logging
import os
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)


class KeyVaultClient:
    """Azure Key Vault secret retrieval with env var fallback.

    In production with KEY_VAULT_URL configured:
      - Uses DefaultAzureCredential (Managed Identity, CLI, etc.)
      - Retrieves secrets from Key Vault

    In development or without Key Vault:
      - Falls back to environment variables
      - Maps secret names to env vars (e.g., "htt-client-secret" -> "HTT_CLIENT_SECRET")
    """

    def __init__(self, vault_url: str | None = None) -> None:
        self._vault_url = vault_url
        self._client: Any = None
        self._cache: dict[str, str] = {}

        if vault_url:
            self._init_client()

    def _init_client(self) -> None:
        """Initialize Azure Key Vault SecretClient."""
        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient

            credential = DefaultAzureCredential()
            self._client = SecretClient(
                vault_url=self._vault_url,
                credential=credential,
            )
            logger.info("Key Vault client initialized: %s", self._vault_url)
        except ImportError:
            logger.warning(
                "azure-identity or azure-keyvault-secrets not installed. "
                "Falling back to environment variables for secrets."
            )
        except Exception as e:
            logger.warning("Key Vault initialization failed: %s. Falling back to env vars.", e)

    def get_secret(self, secret_name: str) -> str | None:
        """Retrieve a secret by name.

        Tries Key Vault first (if configured), then falls back to env var.
        Secret name is converted to env var format:
            "htt-client-secret" -> "HTT_CLIENT_SECRET"

        Args:
            secret_name: Key Vault secret name (e.g., "htt-client-secret")

        Returns:
            Secret value or None if not found
        """
        # Check cache first
        if secret_name in self._cache:
            return self._cache[secret_name]

        # Try Key Vault
        if self._client:
            try:
                secret = self._client.get_secret(secret_name)
                value = secret.value
                if value:
                    self._cache[secret_name] = value
                    return value
            except Exception as e:
                logger.warning("Key Vault retrieval failed for '%s': %s", secret_name, e)

        # Fallback to environment variable
        env_key = secret_name.upper().replace("-", "_")
        value = os.getenv(env_key)
        if value:
            self._cache[secret_name] = value
        return value

    def clear_cache(self) -> None:
        """Clear the secret cache."""
        self._cache.clear()


@lru_cache
def get_keyvault_client() -> KeyVaultClient:
    """Get cached Key Vault client instance."""
    from app.core.config import get_settings

    settings = get_settings()
    return KeyVaultClient(vault_url=settings.key_vault_url)

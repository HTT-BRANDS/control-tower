"""Azure SDK client wrapper for multi-tenant access with Key Vault support.

Supports two credential modes:
1. Single managing tenant (Azure Lighthouse): Uses settings.azure_* values
2. Multi-tenant with per-tenant credentials: Fetches from Azure Key Vault

Key Vault mode is activated when settings.key_vault_url is configured.
In this mode, tenant-specific credentials are stored as secrets named:
- {tenant-id}-client-id
- {tenant-id}-client-secret

The Tenant model determines credential mode per tenant:
- use_lighthouse=True: Use managing tenant credentials (settings.azure_*)
- use_lighthouse=False: Fetch per-tenant credentials from Key Vault
- client_id + client_secret_ref: Custom app registration for the tenant

SECURITY FEATURES:
- TTL-based credential caching (1 hour default)
- Auto-refresh before expiry
- Manual cache clearing capability
"""

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from azure.identity import ClientSecretCredential, DefaultAzureCredential
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.policyinsights import PolicyInsightsClient
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.security import SecurityCenter
from azure.mgmt.subscription import SubscriptionClient

from app.core.config import get_settings

# Optional Key Vault import with graceful handling
try:
    from azure.keyvault.secrets import SecretClient

    KEYVAULT_AVAILABLE = True
except ImportError:
    KEYVAULT_AVAILABLE = False
    SecretClient = None

# Import database for tenant lookups
from app.core.database import SessionLocal

if TYPE_CHECKING:
    from app.models.tenant import Tenant
else:
    from app.models.tenant import Tenant

logger = logging.getLogger(__name__)
settings = get_settings()


class KeyVaultError(Exception):
    """Raised when Key Vault operations fail."""

    pass


@dataclass
class CachedCredential:
    """Cached credential with expiration tracking."""

    credential: ClientSecretCredential
    created_at: float
    expires_at: float

    def is_expired(self) -> bool:
        """Check if credential has expired."""
        return time.time() > self.expires_at

    def should_refresh(self, refresh_buffer_seconds: int = 300) -> bool:
        """Check if credential should be refreshed before expiry.

        Args:
            refresh_buffer_seconds: Refresh this many seconds before expiry

        Returns:
            True if credential should be refreshed
        """
        return time.time() > (self.expires_at - refresh_buffer_seconds)


class AzureClientManager:
    """Manages Azure SDK clients for multiple tenants with Key Vault integration.

    Credential Resolution Order:
    1. If Key Vault not configured: Use settings.azure_* (Lighthouse mode)
    2. If Key Vault configured:
       a) Check tenant.use_lighthouse - if True, use settings.azure_*
       b) If tenant has client_id + client_secret_ref, use those
       c) Otherwise, fetch {tenant-id}-client-id and {tenant-id}-client-secret

    SECURITY FEATURES:
    - Credentials cached with TTL (default 1 hour)
    - Auto-refresh before expiry
    - Manual cache clearing for security rotations
    """

    DEFAULT_CREDENTIAL_TTL_SECONDS = 3600  # 1 hour

    def __init__(self, credential_ttl_seconds: int | None = None) -> None:
        self._credentials: dict[str, CachedCredential] = {}
        self._default_credential: DefaultAzureCredential | None = None
        self._key_vault_client: SecretClient | None = None
        self._key_vault_cache: dict[str, tuple[str, float]] = {}  # (value, expires_at)
        self._settings = get_settings()
        self._credential_ttl = credential_ttl_seconds or self.DEFAULT_CREDENTIAL_TTL_SECONDS
        logger.debug(f"AzureClientManager initialized with credential TTL: {self._credential_ttl}s")
    def _get_key_vault_client(self) -> "SecretClient | None":
        """Get or create Key Vault client using DefaultAzureCredential.

        Returns None if Key Vault is not configured or package not installed.
        """
        if not settings.key_vault_url:
            return None

        if not KEYVAULT_AVAILABLE:
            logger.warning(
                "Key Vault URL is configured but azure-keyvault-secrets package "
                "is not installed. Run: pip install azure-keyvault-secrets"
            )
            return None

        if self._key_vault_client is None:
            try:
                credential = DefaultAzureCredential()
                self._key_vault_client = SecretClient(
                    vault_url=str(settings.key_vault_url),
                    credential=credential,
                )
                logger.debug(f"Key Vault client initialized: {settings.key_vault_url}")
            except Exception as e:
                logger.error(f"Failed to initialize Key Vault client: {e}")
                return None

        return self._key_vault_client

    def _get_tenant_from_db(self, tenant_id: str) -> Tenant | None:
        """Fetch tenant record from database.

        Args:
            tenant_id: The Azure tenant ID

        Returns:
            Tenant model instance or None if not found
        """
        try:
            from app.models.tenant import Tenant

            with SessionLocal() as db:
                return db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
        except Exception as e:
            logger.warning(f"Failed to fetch tenant {tenant_id} from database: {e}")
            return None

    def _fetch_key_vault_secret(
        self, secret_name: str, tenant_id: str
    ) -> str | None:
        """Fetch a secret from Key Vault with TTL-based caching.

        SECURITY: Secrets are cached for 5 minutes to balance performance and security.

        Args:
            secret_name: Name of the secret in Key Vault
            tenant_id: Azure tenant ID (for error context)

        Returns:
            Secret value or None if not found/error
        """
        cache_key = f"{tenant_id}:{secret_name}"
        now = time.time()

        # Check cache first with TTL validation
        if cache_key in self._key_vault_cache:
            value, expires_at = self._key_vault_cache[cache_key]
            if now < expires_at:
                logger.debug(f"Using cached secret '{secret_name}' for tenant {tenant_id}")
                return value
            else:
                logger.debug(f"Secret '{secret_name}' cache expired, refreshing")
                del self._key_vault_cache[cache_key]

        kv_client = self._get_key_vault_client()
        if not kv_client:
            return None

        try:
            secret = kv_client.get_secret(secret_name)
            value = secret.value
            # Cache secrets for 5 minutes (300 seconds)
            secret_ttl = 300
            self._key_vault_cache[cache_key] = (str(value), now + secret_ttl)
            logger.debug(f"Fetched secret '{secret_name}' from Key Vault for tenant {tenant_id}")
            return str(value)
        except Exception as e:
            logger.error(
                f"Failed to fetch secret '{secret_name}' from Key Vault for tenant {tenant_id}: {e}"
            )
            return None

    def _resolve_credentials(
        self, tenant_id: str
    ) -> tuple[str, str, Tenant | None]:
        """Resolve client_id and client_secret for a tenant.

        Resolution order:
        1. If no Key Vault URL: Use settings.azure_* (Lighthouse mode)
        2. If tenant.use_lighthouse=True: Use settings.azure_*
        3. If tenant has client_id + client_secret_ref: Use custom values from Key Vault
        4. Otherwise: Fetch {tenant-id}-client-id and {tenant-id}-client-secret from Key Vault

        Args:
            tenant_id: The Azure tenant ID

        Returns:
            Tuple of (client_id, client_secret, tenant_model)

        Raises:
            ValueError: If credentials cannot be resolved
        """
        # Check if Key Vault is configured
        if not settings.key_vault_url or not KEYVAULT_AVAILABLE:
            # Lighthouse mode - use settings credentials
            if not settings.azure_client_id or not settings.azure_client_secret:
                raise ValueError(
                    f"No Key Vault configured and settings.azure_client_id/"
                    f"azure_client_secret are not set for tenant {tenant_id}"
                )
            return (
                str(settings.azure_client_id),
                str(settings.azure_client_secret),
                None,
            )

        # Key Vault mode - fetch tenant to determine credential mode
        tenant = self._get_tenant_from_db(tenant_id)

        if tenant and tenant.use_lighthouse:
            # Tenant explicitly wants Lighthouse mode
            if not settings.azure_client_id or not settings.azure_client_secret:
                raise ValueError(
                    f"Tenant {tenant_id} configured for Lighthouse but "
                    f"settings.azure_client_id/azure_client_secret are not set"
                )
            logger.debug(f"Using Lighthouse credentials for tenant {tenant_id}")
            return (
                str(settings.azure_client_id),
                str(settings.azure_client_secret),
                tenant,
            )

        # Try custom client_id + client_secret_ref first
        if tenant and tenant.client_id and tenant.client_secret_ref:
            client_secret = self._fetch_key_vault_secret(
                tenant.client_secret_ref, tenant_id
            )
            if client_secret:
                logger.debug(
                    f"Using custom app registration for tenant {tenant_id} "
                    f"(client_id: {tenant.client_id[:8]}...)"
                )
                return (tenant.client_id, client_secret, tenant)
            else:
                logger.warning(
                    f"Failed to fetch client_secret_ref '{tenant.client_secret_ref}' "
                    f"for tenant {tenant_id}, falling back to default"
                )

        # Fetch standard Key Vault secrets
        client_id = self._fetch_key_vault_secret(f"{tenant_id}-client-id", tenant_id)
        client_secret = self._fetch_key_vault_secret(
            f"{tenant_id}-client-secret", tenant_id
        )

        if client_id and client_secret:
            logger.debug(f"Using Key Vault credentials for tenant {tenant_id}")
            return (client_id, client_secret, tenant)

        # Fallback to settings if Key Vault lookup failed
        if settings.azure_client_id and settings.azure_client_secret:
            logger.warning(
                f"Key Vault credentials not found for tenant {tenant_id}, "
                f"falling back to settings credentials"
            )
            return (
                str(settings.azure_client_id),
                str(settings.azure_client_secret),
                tenant,
            )

        raise ValueError(
            f"Could not resolve credentials for tenant {tenant_id}. "
            f"Tried Key Vault secrets and settings fallback."
        )

    def get_credential(self, tenant_id: str, force_refresh: bool = False) -> ClientSecretCredential:
        """Get or create credential for a tenant with TTL-based caching.

        SECURITY: Credentials are cached with TTL and auto-refreshed before expiry.

        Args:
            tenant_id: The Azure tenant ID
            force_refresh: If True, ignore cache and create new credential

        Returns:
            ClientSecretCredential for the tenant

        Raises:
            ValueError: If credentials cannot be resolved
        """
        now = time.time()
        cached = self._credentials.get(tenant_id)

        # Check if we can use cached credential
        if not force_refresh and cached:
            if not cached.is_expired():
                if not cached.should_refresh():
                    # Credential is valid and doesn't need refresh yet
                    return cached.credential
                else:
                    # Credential is valid but approaching expiry - refresh in background
                    logger.debug(f"Credential for tenant {tenant_id} approaching expiry, refreshing")
            else:
                logger.debug(f"Credential for tenant {tenant_id} expired, refreshing")
        elif force_refresh:
            logger.debug(f"Force refreshing credential for tenant {tenant_id}")

        # Create new credential
        client_id, client_secret, _ = self._resolve_credentials(tenant_id)
        new_credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
            connection_timeout=10,
        )

        # Cache with expiration
        self._credentials[tenant_id] = CachedCredential(
            credential=new_credential,
            created_at=now,
            expires_at=now + self._credential_ttl,
        )

        logger.debug(f"Created new credential for tenant {tenant_id}, expires in {self._credential_ttl}s")
        return new_credential

    def get_default_credential(self) -> DefaultAzureCredential:
        """Get default credential for Lighthouse scenarios."""
        if not self._default_credential:
            self._default_credential = DefaultAzureCredential()
        return self._default_credential

    def get_subscription_client(self, tenant_id: str) -> SubscriptionClient:
        """Get subscription client for a tenant."""
        credential = self.get_credential(tenant_id)
        return SubscriptionClient(credential)

    def get_resource_client(
        self, tenant_id: str, subscription_id: str
    ) -> ResourceManagementClient:
        """Get resource management client."""
        credential = self.get_credential(tenant_id)
        return ResourceManagementClient(credential, subscription_id)

    def get_cost_client(
        self, tenant_id: str, subscription_id: str
    ) -> CostManagementClient:
        """Get cost management client.

        Note: CostManagementClient does NOT take subscription_id in its
        constructor (unlike other ARM clients). The subscription scope
        is passed to individual query calls instead.
        """
        credential = self.get_credential(tenant_id)
        return CostManagementClient(credential)

    def get_policy_client(
        self, tenant_id: str, subscription_id: str
    ) -> PolicyInsightsClient:
        """Get policy insights client."""
        credential = self.get_credential(tenant_id)
        return PolicyInsightsClient(credential, subscription_id)

    def get_security_client(
        self, tenant_id: str, subscription_id: str
    ) -> SecurityCenter:
        """Get security center client."""
        credential = self.get_credential(tenant_id)
        return SecurityCenter(credential, subscription_id)

    async def list_subscriptions(self, tenant_id: str) -> list[dict[str, str]]:
        """List all subscriptions in a tenant."""
        try:
            client = self.get_subscription_client(tenant_id)
            subscriptions = []
            for sub in client.subscriptions.list():
                subscriptions.append({
                    "subscription_id": sub.subscription_id,
                    "display_name": sub.display_name,
                    "state": str(sub.state) if sub.state else "Unknown",
                })
            return subscriptions
        except Exception as e:
            logger.error(f"Failed to list subscriptions for tenant {tenant_id}: {e}")
            raise

    def clear_cache(self, tenant_id: str | None = None) -> dict[str, int]:
        """Clear credential cache.

        SECURITY: Use this method to force credential refresh after security rotations
        or when secrets are updated.

        Args:
            tenant_id: If provided, clear only that tenant's cache.
                      If None, clear all caches.

        Returns:
            Dict with cache clear statistics
        """
        stats = {"credentials_cleared": 0, "secrets_cleared": 0}

        if tenant_id:
            # Clear specific tenant
            if tenant_id in self._credentials:
                del self._credentials[tenant_id]
                stats["credentials_cleared"] = 1

            # Clear Key Vault cache entries for this tenant
            keys_to_remove = [
                k for k in self._key_vault_cache if k.startswith(f"{tenant_id}:")
            ]
            for key in keys_to_remove:
                del self._key_vault_cache[key]
                stats["secrets_cleared"] += 1

            logger.info(f"Cleared cache for tenant {tenant_id}: {stats}")
        else:
            # Clear all caches
            stats["credentials_cleared"] = len(self._credentials)
            stats["secrets_cleared"] = len(self._key_vault_cache)
            self._credentials.clear()
            self._key_vault_cache.clear()
            logger.info(f"Cleared all credential caches: {stats}")

        return stats

    def get_cache_stats(self) -> dict[str, any]:
        """Get cache statistics for monitoring.

        Returns:
            Dict with cache statistics
        """
        time.time()
        return {
            "credential_cache_size": len(self._credentials),
            "secret_cache_size": len(self._key_vault_cache),
            "credential_ttl_seconds": self._credential_ttl,
            "expired_credentials": sum(
                1 for c in self._credentials.values() if c.is_expired()
            ),
            "expiring_soon": sum(
                1 for c in self._credentials.values() if c.should_refresh() and not c.is_expired()
            ),
        }

    def refresh_all_credentials(self) -> dict[str, int]:
        """Force refresh all cached credentials.

        SECURITY: Use this for emergency credential rotation or security incidents.

        Returns:
            Dict with refresh statistics
        """
        stats = {"refreshed": 0, "failed": 0}
        tenant_ids = list(self._credentials.keys())

        for tenant_id in tenant_ids:
            try:
                self.get_credential(tenant_id, force_refresh=True)
                stats["refreshed"] += 1
            except Exception as e:
                logger.error(f"Failed to refresh credential for tenant {tenant_id}: {e}")
                stats["failed"] += 1

        logger.info(f"Bulk credential refresh completed: {stats}")
        return stats


# Global client manager instance
azure_client_manager = AzureClientManager()

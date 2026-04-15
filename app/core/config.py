"""Core configuration settings.

Centralized configuration using Pydantic Settings for environment
variable management with sensible defaults.

Azure Key Vault Integration:
- Auto-refresh of secrets with TTL-based caching
- Soft-delete protection verification
- Secret rotation support
- Access policy management helpers
"""

import logging
import os
import secrets
import threading
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app import __version__

logger = logging.getLogger(__name__)

# Azure Key Vault caching configuration
KEY_VAULT_CACHE_TTL_SECONDS = int(
    os.environ.get("KEY_VAULT_CACHE_TTL_SECONDS", "300")
)  # 5 min default
KEY_VAULT_REFRESH_BUFFER_SECONDS = int(
    os.environ.get("KEY_VAULT_REFRESH_BUFFER", "60")
)  # Refresh 1 min before expiry
KEY_VAULT_SOFT_DELETE_ENABLED = (
    os.environ.get("KEY_VAULT_SOFT_DELETE_ENABLED", "true").lower() == "true"
)


@dataclass
class KeyVaultSecretCache:
    """Cache entry for a Key Vault secret with TTL."""

    value: str
    fetched_at: float
    ttl_seconds: int
    secret_name: str
    version: str | None = None

    @property
    def is_expired(self) -> bool:
        """Check if the cached secret has expired."""
        return time.time() > self.fetched_at + self.ttl_seconds

    @property
    def expires_in_seconds(self) -> float:
        """Seconds until cache entry expires."""
        expiry = self.fetched_at + self.ttl_seconds
        remaining = expiry - time.time()
        return max(0, remaining)

    @property
    def needs_refresh(self) -> bool:
        """Check if cache needs refresh (with buffer time)."""
        return self.expires_in_seconds < KEY_VAULT_REFRESH_BUFFER_SECONDS


@dataclass
class KeyVaultMetadata:
    """Azure Key Vault metadata and configuration status."""

    vault_url: str | None = None
    is_configured: bool = False
    soft_delete_enabled: bool = True
    purge_protection_enabled: bool = False
    last_access_time: float = field(default_factory=time.time)
    access_policy_count: int = 0
    secret_count: int = 0
    cached_secrets: list[str] = field(default_factory=list)
    failed_secrets: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to dictionary for diagnostics."""
        return {
            "vault_url": self.vault_url,
            "is_configured": self.is_configured,
            "soft_delete_enabled": self.soft_delete_enabled,
            "purge_protection_enabled": self.purge_protection_enabled,
            "last_access_time": self.last_access_time,
            "access_policy_count": self.access_policy_count,
            "secret_count": self.secret_count,
            "cached_secrets": self.cached_secrets,
            "failed_secrets": self.failed_secrets,
        }


class KeyVaultSecretManager:
    """Manages Azure Key Vault secrets with caching and auto-refresh.

    Features:
    - TTL-based secret caching to reduce API calls
    - Auto-refresh before expiry with configurable buffer
    - Soft-delete protection awareness
    - Thread-safe concurrent access
    - Detailed metadata tracking
    """

    def __init__(self):
        self._cache: dict[str, KeyVaultSecretCache] = {}
        self._lock = threading.RLock()
        self._metadata = KeyVaultMetadata()
        self._client: Any = None

    def _get_client(self, vault_url: str | None = None) -> Any:
        """Get or create Azure Key Vault client."""
        if self._client is None:
            try:
                from azure.identity import DefaultAzureCredential
                from azure.keyvault.secrets import SecretClient

                credential = DefaultAzureCredential()
                url = vault_url or os.environ.get("KEY_VAULT_URL", "")

                if not url:
                    raise ValueError("Key Vault URL not configured")

                self._client = SecretClient(vault_url=url, credential=credential)
                self._metadata.vault_url = url
                self._metadata.is_configured = True

            except ImportError:
                logger.warning("Azure Key Vault SDK not available")
                raise

        return self._client

    def get_secret(
        self, secret_name: str, vault_url: str | None = None, force_refresh: bool = False
    ) -> str | None:
        """Get secret from cache or Key Vault with auto-refresh.

        Args:
            secret_name: Name of the secret to retrieve
            vault_url: Optional Key Vault URL (uses env var if not provided)
            force_refresh: Force refresh from Key Vault even if cached

        Returns:
            Secret value or None if not found/error
        """
        cache_key = f"{vault_url or 'default'}:{secret_name}"

        with self._lock:
            # Check cache first
            cached = self._cache.get(cache_key)

            if not force_refresh and cached and not cached.needs_refresh:
                logger.debug(f"Key Vault cache hit for {secret_name}")
                self._metadata.last_access_time = time.time()
                return cached.value

            # Need to fetch from Key Vault
            try:
                client = self._get_client(vault_url)
                secret = client.get_secret(secret_name)

                # Cache the secret
                self._cache[cache_key] = KeyVaultSecretCache(
                    value=secret.value,
                    fetched_at=time.time(),
                    ttl_seconds=KEY_VAULT_CACHE_TTL_SECONDS,
                    secret_name=secret_name,
                    version=secret.properties.version,
                )

                # Update metadata
                if secret_name not in self._metadata.cached_secrets:
                    self._metadata.cached_secrets.append(secret_name)
                if secret_name in self._metadata.failed_secrets:
                    self._metadata.failed_secrets.remove(secret_name)

                logger.debug(f"Key Vault secret fetched and cached: {secret_name}")
                return secret.value

            except Exception as e:
                logger.warning(f"Failed to fetch Key Vault secret {secret_name}: {e}")

                # Return stale cache if available (graceful degradation)
                if cached:
                    logger.info(f"Returning stale cached value for {secret_name}")
                    if secret_name not in self._metadata.failed_secrets:
                        self._metadata.failed_secrets.append(secret_name)
                    return cached.value

                if secret_name not in self._metadata.failed_secrets:
                    self._metadata.failed_secrets.append(secret_name)
                return None

    def get_secret_with_version(
        self, secret_name: str, version: str, vault_url: str | None = None
    ) -> str | None:
        """Get specific version of a secret."""
        try:
            client = self._get_client(vault_url)
            secret = client.get_secret(secret_name, version)
            return secret.value
        except Exception as e:
            logger.warning(f"Failed to fetch secret version {secret_name}/{version}: {e}")
            return None

    def invalidate_secret(self, secret_name: str, vault_url: str | None = None) -> bool:
        """Invalidate cached secret to force refresh on next access."""
        cache_key = f"{vault_url or 'default'}:{secret_name}"

        with self._lock:
            if cache_key in self._cache:
                del self._cache[cache_key]
                if secret_name in self._metadata.cached_secrets:
                    self._metadata.cached_secrets.remove(secret_name)
                logger.debug(f"Invalidated Key Vault cache for {secret_name}")
                return True
            return False

    def invalidate_all(self) -> int:
        """Clear all cached secrets."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._metadata.cached_secrets.clear()
            logger.info(f"Cleared all {count} Key Vault cached secrets")
            return count

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            time.time()
            active = sum(1 for c in self._cache.values() if not c.is_expired)
            expired = len(self._cache) - active

            return {
                "total_cached": len(self._cache),
                "active": active,
                "expired": expired,
                "cache_ttl_seconds": KEY_VAULT_CACHE_TTL_SECONDS,
                "refresh_buffer_seconds": KEY_VAULT_REFRESH_BUFFER_SECONDS,
            }

    def get_metadata(self) -> KeyVaultMetadata:
        """Get Key Vault metadata."""
        return self._metadata

    def verify_soft_delete(self, vault_url: str | None = None) -> bool:
        """Verify soft-delete is enabled on the Key Vault."""
        try:
            from azure.identity import DefaultAzureCredential
            from azure.mgmt.keyvault import KeyVaultManagementClient

            credential = DefaultAzureCredential()
            subscription_id = os.environ.get("AZURE_SUBSCRIPTION_ID")

            if not subscription_id:
                logger.warning("AZURE_SUBSCRIPTION_ID not set, cannot verify soft-delete")
                return True  # Assume enabled for safety

            kv_client = KeyVaultManagementClient(credential, subscription_id)

            # Extract vault name from URL
            url = vault_url or self._metadata.vault_url or os.environ.get("KEY_VAULT_URL", "")
            if not url:
                return True

            vault_name = url.split(".")[0].replace("https://", "")
            resource_group = os.environ.get("AZURE_RESOURCE_GROUP", "")

            if not resource_group:
                logger.warning("AZURE_RESOURCE_GROUP not set, cannot verify soft-delete")
                return True

            vault = kv_client.vaults.get(resource_group, vault_name)

            self._metadata.soft_delete_enabled = vault.properties.enable_soft_delete or False
            self._metadata.purge_protection_enabled = (
                vault.properties.enable_purge_protection or False
            )

            if not self._metadata.soft_delete_enabled and KEY_VAULT_SOFT_DELETE_ENABLED:
                logger.warning(
                    f"Key Vault {vault_name} does not have soft-delete enabled! "
                    "This is a security risk for secret recovery."
                )

            return self._metadata.soft_delete_enabled

        except Exception as e:
            logger.warning(f"Could not verify Key Vault soft-delete status: {e}")
            return True  # Assume enabled for safety


# Global Key Vault secret manager instance
key_vault_manager = KeyVaultSecretManager()


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Security features:
    - Debug mode validation (cannot be True in production)
    - CORS origin validation (no wildcards in production)
    - Safe defaults for all settings
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # =========================================================================
    # Environment Detection
    # =========================================================================

    environment: Literal["development", "staging", "production"] = Field(
        default="production",
        alias="ENVIRONMENT",
    )

    # Azure-specific settings
    azure_region: str | None = Field(default=None, alias="AZURE_REGION")
    azure_subscription_id: str | None = Field(default=None, alias="AZURE_SUBSCRIPTION_ID")
    azure_resource_group: str | None = Field(default=None, alias="AZURE_RESOURCE_GROUP")
    azure_managed_identity_object_id: str | None = Field(
        default=None, alias="AZURE_MANAGED_IDENTITY_OBJECT_ID"
    )

    # Application
    app_name: str = "Azure Governance Platform"
    app_version: str = __version__
    debug: bool = False
    log_level: str = "INFO"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    database_url: str = "sqlite:///./data/governance.db"

    # =========================================================================
    # Authentication & Authorization
    # =========================================================================

    # JWT Configuration
    jwt_secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = Field(
        default=30, alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    jwt_refresh_token_expire_days: int = Field(default=7, alias="JWT_REFRESH_TOKEN_EXPIRE_DAYS")

    # Azure AD / Entra ID OAuth2 Configuration
    azure_ad_tenant_id: str | None = Field(default=None, alias="AZURE_AD_TENANT_ID")
    azure_ad_client_id: str | None = Field(default=None, alias="AZURE_AD_CLIENT_ID")
    azure_ad_client_secret: str | None = Field(default=None, alias="AZURE_AD_CLIENT_SECRET")
    azure_ad_authority: str = Field(
        default="https://login.microsoftonline.com/common", alias="AZURE_AD_AUTHORITY"
    )
    azure_ad_token_endpoint: str = Field(
        default="https://login.microsoftonline.com/common/oauth2/v2.0/token",
        alias="AZURE_AD_TOKEN_ENDPOINT",
    )
    azure_ad_authorization_endpoint: str = Field(
        default="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        alias="AZURE_AD_AUTHORIZATION_ENDPOINT",
    )
    azure_ad_jwks_uri: str = Field(
        default="https://login.microsoftonline.com/common/discovery/v2.0/keys",
        alias="AZURE_AD_JWKS_URI",
    )
    azure_ad_issuer: str = Field(
        default="https://login.microsoftonline.com/common/v2.0", alias="AZURE_AD_ISSUER"
    )

    # OAuth2 Scopes
    oauth2_scopes: list[str] = Field(
        default_factory=lambda: ["openid", "profile", "email", "User.Read"], alias="OAUTH2_SCOPES"
    )

    # Allowed OAuth2 redirect URIs (whitelist)
    allowed_redirect_uris_str: str = Field(
        default="http://localhost:8000/login,http://localhost:8000/auth/callback",
        alias="ALLOWED_REDIRECT_URIS",
    )

    # Legacy Azure Authentication (for backend service calls)
    azure_tenant_id: str | None = None
    azure_client_id: str | None = None
    azure_client_secret: str | None = None

    # OIDC Workload Identity Federation (replaces client secrets)
    use_oidc_federation: bool = Field(default=False, alias="USE_OIDC_FEDERATION")
    azure_managed_identity_client_id: str | None = Field(
        default=None,
        alias="AZURE_MANAGED_IDENTITY_CLIENT_ID",
        description="Client ID of user-assigned managed identity. Leave empty for system-assigned.",
    )
    oidc_allow_dev_fallback: bool = Field(
        default=False,
        alias="OIDC_ALLOW_DEV_FALLBACK",
        description=(
            "Allow DefaultAzureCredential fallback when not on App Service. "
            "Set to true for local development only. NEVER enable in production."
        ),
    )

    # Phase B: Multi-tenant App Registration (single secret for all tenants)
    azure_multi_tenant_app_id: str | None = Field(
        default=None,
        alias="AZURE_MULTI_TENANT_APP_ID",
        description=(
            "Client ID of the multi-tenant app registration (Phase B). "
            "When set, all tenants use this single app instead of per-tenant apps. "
            "Reduces secret rotation from 5 secrets to 1 secret."
        ),
    )
    azure_multi_tenant_client_secret: str | None = Field(
        default=None,
        alias="AZURE_MULTI_TENANT_CLIENT_SECRET",
        description=(
            "Client secret for the multi-tenant app (Phase B). "
            "In production, this should be a Key Vault reference like "
            "@Microsoft.KeyVault(SecretUri=https://...)."
        ),
    )
    use_multi_tenant_app: bool = Field(
        default=False,
        alias="USE_MULTI_TENANT_APP",
        description=(
            "Enable Phase B multi-tenant app authentication. "
            "When true, uses AZURE_MULTI_TENANT_APP_ID for all tenants. "
            "Requires admin consent in each tenant."
        ),
    )

    # Phase C: Zero-Secrets UAMI Authentication (no secrets required)
    use_uami_auth: bool = Field(
        default=False,
        alias="USE_UAMI_AUTH",
        description=(
            "Enable Phase C zero-secrets authentication via User-Assigned Managed Identity. "
            "When true, uses UAMI with Federated Identity Credential instead of client secrets. "
            "This is the most secure authentication option with zero secrets in configuration."
        ),
    )
    uami_client_id: str | None = Field(
        default=None,
        alias="UAMI_CLIENT_ID",
        description=(
            "Client ID of the User-Assigned Managed Identity for Phase C. "
            "The UAMI should have a Federated Identity Credential attached to the multi-tenant app. "
            "Required when USE_UAMI_AUTH=true."
        ),
    )
    uami_principal_id: str | None = Field(
        default=None,
        alias="UAMI_PRINCIPAL_ID",
        description=(
            "Principal ID (Object ID) of the User-Assigned Managed Identity. "
            "Used for role assignments and RBAC configuration."
        ),
    )
    federated_identity_credential_id: str | None = Field(
        default="github-actions-federation",
        alias="FEDERATED_IDENTITY_CREDENTIAL_ID",
        description=(
            "Name/ID of the Federated Identity Credential on the multi-tenant app. "
            "Links the UAMI to the app registration for OIDC federation."
        ),
    )

    # Azure Lighthouse Configuration
    managed_identity_object_id: str | None = Field(
        default=None,
        alias="MANAGED_IDENTITY_OBJECT_ID",
        description="Object ID of the Managed Identity for Lighthouse delegation",
    )
    lighthouse_enabled: bool = Field(
        default=True,
        alias="LIGHTHOUSE_ENABLED",
        description="Enable self-service onboarding via Azure Lighthouse",
    )

    # Key Vault (for multi-tenant credentials and secrets)
    key_vault_url: str | None = None

    # Key Vault Caching Configuration
    key_vault_cache_ttl_seconds: int = Field(
        default=300,
        alias="KEY_VAULT_CACHE_TTL_SECONDS",
        description="TTL for cached Key Vault secrets in seconds",
    )
    key_vault_auto_refresh: bool = Field(
        default=True,
        alias="KEY_VAULT_AUTO_REFRESH",
        description="Auto-refresh secrets before TTL expiry",
    )
    key_vault_soft_delete_check: bool = Field(
        default=True,
        alias="KEY_VAULT_SOFT_DELETE_CHECK",
        description="Verify soft-delete is enabled on Key Vault",
    )

    # Multi-tenant configuration
    # Comma-separated list of tenant IDs to manage
    managed_tenant_ids: list[str] = Field(default_factory=list)

    # Sync Configuration
    cost_sync_interval_hours: int = 24
    compliance_sync_interval_hours: int = 4
    resource_sync_interval_hours: int = 1
    identity_sync_interval_hours: int = 24
    sync_stale_threshold_hours: int = Field(
        default=24,
        alias="SYNC_STALE_THRESHOLD_HOURS",
        description="Hours after which sync data is considered stale",
    )

    # Alerting
    teams_webhook_url: str | None = None
    cost_anomaly_threshold_percent: float = 20.0
    compliance_alert_threshold_percent: float = 5.0

    # Notifications
    notification_enabled: bool = False
    notification_min_severity: str = "warning"  # info, warning, error, critical
    notification_cooldown_minutes: int = 30

    # CORS (RESTRICTED in production - no wildcards allowed)
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    cors_allow_methods: list[str] = Field(
        default_factory=lambda: ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    )
    cors_allow_headers: list[str] = Field(
        default_factory=lambda: ["Authorization", "Content-Type", "Accept", "X-Requested-With"]
    )
    cors_allow_credentials: bool = True

    # Caching Configuration
    cache_enabled: bool = Field(default=True, alias="CACHE_ENABLED")
    redis_url: str | None = Field(default=None, alias="REDIS_URL")
    cache_default_ttl_seconds: int = Field(default=300, alias="CACHE_DEFAULT_TTL_SECONDS")  # 5 min
    cache_max_ttl_seconds: int = Field(default=86400, alias="CACHE_MAX_TTL_SECONDS")  # 24 hours
    cache_ttl_cost_summary: int = Field(default=3600, alias="CACHE_TTL_COST_SUMMARY")  # 1 hour
    cache_ttl_compliance_summary: int = Field(
        default=1800, alias="CACHE_TTL_COMPLIANCE_SUMMARY"
    )  # 30 min
    cache_ttl_resource_inventory: int = Field(
        default=900, alias="CACHE_TTL_RESOURCE_INVENTORY"
    )  # 15 min
    cache_ttl_identity_summary: int = Field(
        default=3600, alias="CACHE_TTL_IDENTITY_SUMMARY"
    )  # 1 hour
    cache_ttl_riverside_summary: int = Field(
        default=900, alias="CACHE_TTL_RIVERSIDE_SUMMARY"
    )  # 15 min

    # Production Hardening Defaults
    cache_default_ttl: int = 300
    cache_max_ttl: int = 3600
    cors_allowed_origins: str = ""
    rate_limit_default: int = 100

    # Database Configuration - General
    database_pool_size: int = Field(default=3, alias="DB_POOL_SIZE")
    database_max_overflow: int = Field(default=2, alias="DB_MAX_OVERFLOW")
    database_pool_timeout: int = Field(default=30, alias="DB_POOL_TIMEOUT")
    slow_query_threshold_ms: float = Field(default=500.0, alias="SLOW_QUERY_THRESHOLD_MS")
    enable_query_logging: bool = Field(default=False, alias="ENABLE_QUERY_LOGGING")

    # =========================================================================
    # Azure SQL Specific Configuration
    # =========================================================================
    # Connection Pool Optimization for Azure SQL
    azure_sql_pool_size: int = Field(
        default=5,
        alias="AZURE_SQL_POOL_SIZE",
        description="Number of connections to keep in pool. 5-10 is optimal for most Azure SQL workloads",
    )
    azure_sql_max_overflow: int = Field(
        default=10,
        alias="AZURE_SQL_MAX_OVERFLOW",
        description="Extra connections beyond pool_size when needed",
    )
    azure_sql_pool_timeout: int = Field(
        default=30,
        alias="AZURE_SQL_POOL_TIMEOUT",
        description="Seconds to wait for connection from pool",
    )
    azure_sql_pool_pre_ping: bool = Field(
        default=True,
        alias="AZURE_SQL_POOL_PRE_PING",
        description="Verify connections before use (critical for Azure SQL)",
    )
    azure_sql_pool_recycle: int = Field(
        default=1800,
        alias="AZURE_SQL_POOL_RECYCLE",
        description="Seconds before recycling connections (Azure SQL timeout is ~30 min)",
    )
    azure_sql_use_null_pool: bool = Field(
        default=False,
        alias="AZURE_SQL_USE_NULL_POOL",
        description="Use NullPool for serverless scenarios (Azure Functions)",
    )

    # Connection Retry Configuration
    azure_sql_connection_retry_attempts: int = Field(
        default=5,
        alias="AZURE_SQL_CONNECTION_RETRY_ATTEMPTS",
        description="Max retry attempts for transient Azure SQL faults",
    )
    azure_sql_connection_retry_delay: float = Field(
        default=1.0,
        alias="AZURE_SQL_CONNECTION_RETRY_DELAY",
        description="Initial retry delay in seconds (uses exponential backoff)",
    )

    # Query Store and Monitoring
    azure_sql_enable_query_store: bool = Field(
        default=True,
        alias="AZURE_SQL_ENABLE_QUERY_STORE",
        description="Enable Query Store for performance monitoring",
    )
    azure_sql_query_store_max_size_mb: int = Field(
        default=100,
        alias="AZURE_SQL_QUERY_STORE_MAX_SIZE_MB",
        description="Max storage for Query Store data",
    )
    azure_sql_query_store_retention_days: int = Field(
        default=30,
        alias="AZURE_SQL_QUERY_STORE_RETENTION_DAYS",
        description="Days to retain Query Store data",
    )

    # Azure Functions / Serverless Detection
    is_azure_functions: bool = Field(
        default=False,
        alias="AZURE_FUNCTIONS_ENVIRONMENT",
        description="True when running in Azure Functions",
    )

    @field_validator("is_azure_functions", mode="before")
    @classmethod
    def detect_azure_functions(cls, v: bool | None) -> bool:
        """Auto-detect Azure Functions environment."""
        if v:
            return True
        # Auto-detect from Azure Functions environment variables
        return any(
            [
                os.getenv("FUNCTIONS_WORKER_RUNTIME") is not None,
                os.getenv("FUNCTIONS_EXTENSION_VERSION") is not None,
                os.getenv("AZURE_FUNCTIONS_ENVIRONMENT") is not None,
            ]
        )

    # Performance & Bulk Operations
    bulk_batch_size: int = Field(default=1000, alias="BULK_BATCH_SIZE")
    sync_chunk_size: int = Field(default=1000, alias="SYNC_CHUNK_SIZE")
    enable_parallel_sync: bool = Field(default=True, alias="ENABLE_PARALLEL_SYNC")
    max_parallel_tenants: int = Field(default=5, alias="MAX_PARALLEL_TENANTS")

    # OpenTelemetry Tracing
    enable_tracing: bool = Field(default=False, alias="ENABLE_TRACING")
    otel_exporter_endpoint: str | None = Field(default=None, alias="OTEL_EXPORTER_ENDPOINT")
    otel_exporter_headers: str | None = Field(default=None, alias="OTEL_EXPORTER_HEADERS")

    # =========================================================================
    # Security Validators
    # =========================================================================

    @field_validator("environment", mode="before")
    @classmethod
    def detect_environment(cls, v: str | None) -> str:
        """Auto-detect environment from common environment variables."""
        if v:
            return v.lower()

        # Check common environment indicators
        if os.getenv("PRODUCTION") or os.getenv("PROD"):
            return "production"
        if os.getenv("STAGING"):
            return "staging"

        # Check for production-like hostnames or settings
        hostname = os.getenv("HOSTNAME", "").lower()
        if any(x in hostname for x in ["prod", "production", "prd"]):
            return "production"

        return "development"

    @model_validator(mode="after")
    def validate_debug_mode(self):
        """CRITICAL: Prevent debug mode in production."""
        if self.environment == "production" and self.debug:
            logger.error(
                "CRITICAL SECURITY ERROR: DEBUG mode cannot be enabled in production! "
                "Set DEBUG=false or ENVIRONMENT=development"
            )
            raise ValueError("DEBUG cannot be True in production environment")

        if self.debug and self.environment != "development":
            logger.warning(
                f"WARNING: DEBUG mode enabled in {self.environment} environment. "
                "This is not recommended for security reasons."
            )

        return self

    @model_validator(mode="after")
    def validate_cors_origins(self):
        """CRITICAL: Prevent wildcard CORS in production."""
        if self.environment == "production":
            # Check for wildcards in origins
            for origin in self.cors_origins:
                if origin == "*" or origin.strip() == "*":
                    logger.error(
                        "CRITICAL SECURITY ERROR: Wildcard (*) CORS origin not allowed in production! "
                        "Set explicit origins in CORS_ORIGINS"
                    )
                    raise ValueError("Wildcard CORS origin (*) not allowed in production")

            # Check for localhost in production
            for origin in self.cors_origins:
                if "localhost" in origin.lower() or "127.0.0.1" in origin:
                    logger.warning(
                        f"WARNING: localhost found in CORS origins for production: {origin}. "
                        "This may be a security risk."
                    )

            # Ensure we have explicit origins configured
            if not self.cors_origins or self.cors_origins == ["http://localhost:3000"]:
                logger.error(
                    "CRITICAL SECURITY ERROR: Default CORS origins used in production! "
                    "Configure CORS_ORIGINS with your production domains"
                )
                raise ValueError("CORS origins must be explicitly configured in production")

        return self

    @model_validator(mode="after")
    def validate_jwt_secret_production(self):
        """CRITICAL: Require explicit JWT_SECRET_KEY in production."""
        if self.environment == "production":
            # Check if the key was auto-generated (not explicitly set)
            # A production deployment MUST have a stable, explicitly-set key
            # so tokens survive restarts and work across multiple instances
            explicit_key = os.getenv("JWT_SECRET_KEY")
            if not explicit_key:
                logger.error(
                    "CRITICAL SECURITY ERROR: JWT_SECRET_KEY must be explicitly set "
                    "in production! Auto-generated keys change on restart and break "
                    "existing tokens. Set JWT_SECRET_KEY in your environment."
                )
                raise ValueError(
                    "JWT_SECRET_KEY must be explicitly set in production environment. "
                    'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
                )
        return self

    @field_validator("managed_tenant_ids", mode="before")
    @classmethod
    def parse_managed_tenant_ids(cls, v: str | list[str]) -> list[str]:
        """Parse managed tenant IDs from comma-separated string or list."""
        if isinstance(v, str):
            return [tid.strip() for tid in v.split(",") if tid.strip()]
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """Validate JWT secret key is not default/weak."""
        if len(v) < 32:
            logger.warning(
                "JWT secret key is too short (< 32 characters). "
                'Generate a strong key with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )
        return v

    @field_validator("cors_allow_methods", mode="before")
    @classmethod
    def parse_cors_methods(cls, v: str | list[str]) -> list[str]:
        """Parse CORS methods from string or list."""
        if isinstance(v, str):
            return [method.strip().upper() for method in v.split(",") if method.strip()]
        return [method.upper() for method in v]

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def allowed_redirect_uris(self) -> set[str]:
        """Parse comma-separated redirect URIs into a set for O(1) lookup.

        Auto-includes the Azure App Service hostname if WEBSITE_HOSTNAME is set,
        preventing misconfigured ALLOWED_REDIRECT_URIS from breaking login.
        """
        uris = {uri.strip() for uri in self.allowed_redirect_uris_str.split(",") if uri.strip()}

        # Azure App Service always sets WEBSITE_HOSTNAME — auto-include it
        import os

        hostname = os.environ.get("WEBSITE_HOSTNAME")
        if hostname:
            base = f"https://{hostname}"
            uris.add(f"{base}/login")
            uris.add(f"{base}/auth/callback")

        return uris

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"

    @property
    def is_configured(self) -> bool:
        """Check if minimum Azure configuration is present.

        When OIDC federation is enabled, client secret is not required.
        Instead we verify that at least one OIDC credential source is
        detectable: App Service (WEBSITE_SITE_NAME), Workload Identity
        (AZURE_FEDERATED_TOKEN_FILE), or explicit dev fallback flag.
        Checking azure_client_id here is wrong — it's the managing-tenant
        app ID, not the per-tenant OIDC identity.
        """
        if self.use_oidc_federation:
            has_app_service = bool(os.environ.get("WEBSITE_SITE_NAME"))
            has_workload_identity = bool(os.environ.get("AZURE_FEDERATED_TOKEN_FILE"))
            has_dev_fallback = self.oidc_allow_dev_fallback
            has_credential_source = has_app_service or has_workload_identity or has_dev_fallback
            return bool(self.azure_tenant_id and has_credential_source)
        return all(
            [
                self.azure_tenant_id,
                self.azure_client_id,
                self.azure_client_secret,
            ]
        )

    @property
    def is_containerized(self) -> bool:
        """Check if running in a container environment."""
        return (
            os.getenv("KUBERNETES_SERVICE_HOST") is not None
            or os.getenv("CONTAINER") is not None
            or os.path.exists("/.dockerenv")
        )

    @property
    def is_azure_app_service(self) -> bool:
        """Check if running in Azure App Service."""
        return os.getenv("WEBSITE_SITE_NAME") is not None

    @property
    def app_insights_enabled(self) -> bool:
        """Check if Application Insights is configured."""
        return bool(self.app_insights_connection_string)

    @property
    def app_insights_connection_string(self) -> str | None:
        """Get Application Insights connection string."""
        return os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")

    @property
    def key_vault_health(self) -> dict[str, Any]:
        """Get Key Vault health status and metadata."""
        metadata = key_vault_manager.get_metadata()
        cache_stats = key_vault_manager.get_cache_stats()

        return {
            "is_configured": metadata.is_configured and bool(self.key_vault_url),
            "vault_url": self.key_vault_url,
            "soft_delete_enabled": metadata.soft_delete_enabled,
            "purge_protection_enabled": metadata.purge_protection_enabled,
            "cached_secrets_count": len(metadata.cached_secrets),
            "failed_secrets": metadata.failed_secrets,
            "cache_stats": cache_stats,
        }

    def get_key_vault_secret(self, secret_name: str, force_refresh: bool = False) -> str | None:
        """Get secret from Key Vault with caching and auto-refresh.

        This method provides:
        - Automatic caching with TTL
        - Auto-refresh before expiry
        - Graceful fallback to stale cache on errors
        - Thread-safe concurrent access

        Args:
            secret_name: Name of the secret to retrieve
            force_refresh: Force refresh from Key Vault even if cached

        Returns:
            Secret value or None if not found/error
        """
        if not self.key_vault_url:
            logger.debug(f"Key Vault not configured, cannot fetch {secret_name}")
            return None

        return key_vault_manager.get_secret(
            secret_name=secret_name, vault_url=self.key_vault_url, force_refresh=force_refresh
        )

    def invalidate_key_vault_secret(self, secret_name: str) -> bool:
        """Invalidate cached Key Vault secret."""
        return key_vault_manager.invalidate_secret(secret_name, self.key_vault_url)

    def get_cache_ttl(self, data_type: str) -> int:
        """Get TTL for a specific data type, clamped to max."""
        ttl_map = {
            "cost_summary": self.cache_ttl_cost_summary,
            "compliance_summary": self.cache_ttl_compliance_summary,
            "resource_inventory": self.cache_ttl_resource_inventory,
            "identity_summary": self.cache_ttl_identity_summary,
            "riverside_summary": self.cache_ttl_riverside_summary,
        }
        ttl = ttl_map.get(data_type, self.cache_default_ttl_seconds)
        return min(ttl, self.cache_max_ttl_seconds)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

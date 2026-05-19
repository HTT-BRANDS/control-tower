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
from functools import lru_cache
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app import __version__
from app.core.config_keyvault import (
    KEY_VAULT_CACHE_TTL_SECONDS as KEY_VAULT_CACHE_TTL_SECONDS,
)
from app.core.config_keyvault import (
    KEY_VAULT_REFRESH_BUFFER_SECONDS as KEY_VAULT_REFRESH_BUFFER_SECONDS,
)
from app.core.config_keyvault import (
    KEY_VAULT_SOFT_DELETE_ENABLED as KEY_VAULT_SOFT_DELETE_ENABLED,
)
from app.core.config_keyvault import (
    KeyVaultMetadata as KeyVaultMetadata,
)
from app.core.config_keyvault import (
    KeyVaultSecretCache as KeyVaultSecretCache,
)
from app.core.config_keyvault import (
    KeyVaultSecretManager as KeyVaultSecretManager,
)
from app.core.config_keyvault import (
    key_vault_manager,
)
from app.core.config_mixins import RuntimeSettingsMixin

logger = logging.getLogger(__name__)


class Settings(RuntimeSettingsMixin, BaseSettings):
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

    environment: Literal["development", "test", "staging", "production"] = Field(
        default="production",
        alias="ENVIRONMENT",
    )

    azure_region: str | None = Field(default=None, alias="AZURE_REGION")
    azure_subscription_id: str | None = Field(default=None, alias="AZURE_SUBSCRIPTION_ID")
    azure_resource_group: str | None = Field(default=None, alias="AZURE_RESOURCE_GROUP")
    azure_managed_identity_object_id: str | None = Field(
        default=None, alias="AZURE_MANAGED_IDENTITY_OBJECT_ID"
    )

    app_name: str = "HTT Control Tower"
    app_version: str = __version__
    debug: bool = False
    log_level: str = "INFO"

    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str = "sqlite:///./data/governance.db"

    jwt_secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = Field(
        default=30, alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    jwt_refresh_token_expire_days: int = Field(default=7, alias="JWT_REFRESH_TOKEN_EXPIRE_DAYS")

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

    oauth2_scopes: list[str] = Field(
        default_factory=lambda: ["openid", "profile", "email", "User.Read"], alias="OAUTH2_SCOPES"
    )

    allowed_redirect_uris_str: str = Field(
        default="http://localhost:8000/login,http://localhost:8000/auth/callback",
        alias="ALLOWED_REDIRECT_URIS",
    )

    azure_tenant_id: str | None = None
    azure_client_id: str | None = None
    azure_client_secret: str | None = None

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

    managed_identity_object_id: str | None = Field(
        default=None,
        alias="MANAGED_IDENTITY_OBJECT_ID",
        description="Object ID of the User-Assigned Managed Identity (for UAMI/OIDC modes)",
    )

    key_vault_url: str | None = None

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

    managed_tenant_ids: list[str] = Field(default_factory=list)

    cost_sync_interval_hours: int = 24
    compliance_sync_interval_hours: int = 4
    resource_sync_interval_hours: int = 1
    identity_sync_interval_hours: int = 24
    disable_background_schedulers: bool = Field(
        default=False,
        alias="BROWSER_TEST_DISABLE_SCHEDULERS",
        description=(
            "Disable background schedulers for the browser-test harness only. "
            "This is allowlisted to explicit non-deployable test contexts and must fail closed elsewhere."
        ),
    )
    e2e_harness: bool = Field(
        default=False,
        alias="E2E_HARNESS",
        description="Explicit allowlist marker for the browser-test harness.",
    )
    sync_stale_threshold_hours: int = Field(
        default=24,
        alias="SYNC_STALE_THRESHOLD_HOURS",
        description="Hours after which sync data is considered stale",
    )

    teams_webhook_url: str | None = None
    cost_anomaly_threshold_percent: float = 20.0
    compliance_alert_threshold_percent: float = 5.0

    notification_enabled: bool = False
    notification_min_severity: str = "warning"  # info, warning, error, critical
    notification_cooldown_minutes: int = 30

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    cors_allow_methods: list[str] = Field(
        default_factory=lambda: ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    )
    cors_allow_headers: list[str] = Field(
        default_factory=lambda: ["Authorization", "Content-Type", "Accept", "X-Requested-With"]
    )
    cors_allow_credentials: bool = True

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

    cache_default_ttl: int = 300
    cache_max_ttl: int = 3600
    cors_allowed_origins: str = ""
    rate_limit_default: int = 100

    @field_validator("environment", mode="before")
    @classmethod
    def detect_environment(cls, v: str | None) -> str:
        """Auto-detect environment from common environment variables."""
        if v:
            return v.lower()

        if os.getenv("PRODUCTION") or os.getenv("PROD"):
            return "production"
        if os.getenv("STAGING"):
            return "staging"

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
            for origin in self.cors_origins:
                if origin == "*" or origin.strip() == "*":
                    logger.error(
                        "CRITICAL SECURITY ERROR: Wildcard (*) CORS origin not allowed in production! "
                        "Set explicit origins in CORS_ORIGINS"
                    )
                    raise ValueError("Wildcard CORS origin (*) not allowed in production")

            for origin in self.cors_origins:
                if "localhost" in origin.lower() or "127.0.0.1" in origin:
                    logger.warning(
                        f"WARNING: localhost found in CORS origins for production: {origin}. "
                        "This may be a security risk."
                    )

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

    @model_validator(mode="after")
    def validate_browser_test_scheduler_disable_scope(self):
        """Fail closed unless scheduler disable is explicitly allowlisted for browser tests."""
        if not self.disable_background_schedulers:
            return self

        allowed_context = self.environment == "test" and self.e2e_harness
        if not allowed_context:
            raise ValueError(
                "BROWSER_TEST_DISABLE_SCHEDULERS is allowed only when ENVIRONMENT=test "
                "and E2E_HARNESS=true in the browser-test harness"
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

    @property
    def allowed_redirect_uris(self) -> set[str]:
        """Parse comma-separated redirect URIs into a set for O(1) lookup.

        Auto-includes the Azure App Service hostname if WEBSITE_HOSTNAME is set,
        preventing misconfigured ALLOWED_REDIRECT_URIS from breaking login.
        """
        uris = {uri.strip() for uri in self.allowed_redirect_uris_str.split(",") if uri.strip()}

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
    def is_test(self) -> bool:
        """Check if running in the explicit test environment."""
        return self.environment == "test"

    @property
    def allows_direct_login(self) -> bool:
        """Allow direct login only for development or the explicit browser-test harness."""
        return self.is_development or (self.is_test and self.e2e_harness)

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

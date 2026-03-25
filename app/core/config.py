"""Core configuration settings.

Centralized configuration using Pydantic Settings for environment
variable management with sensible defaults.
"""

import logging
import os
import secrets
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app import __version__

logger = logging.getLogger(__name__)


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
        default="development",
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

    # Multi-tenant configuration
    # Comma-separated list of tenant IDs to manage
    managed_tenant_ids: list[str] = Field(default_factory=list)

    # Sync Configuration
    cost_sync_interval_hours: int = 24
    compliance_sync_interval_hours: int = 4
    resource_sync_interval_hours: int = 1
    identity_sync_interval_hours: int = 24

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

    # Database Configuration
    database_pool_size: int = Field(default=5, alias="DB_POOL_SIZE")
    database_max_overflow: int = Field(default=10, alias="DB_MAX_OVERFLOW")
    database_pool_timeout: int = Field(default=30, alias="DB_POOL_TIMEOUT")
    slow_query_threshold_ms: float = Field(default=500.0, alias="SLOW_QUERY_THRESHOLD_MS")
    enable_query_logging: bool = Field(default=False, alias="ENABLE_QUERY_LOGGING")

    # Performance & Bulk Operations
    bulk_batch_size: int = Field(default=1000, alias="BULK_BATCH_SIZE")
    sync_chunk_size: int = Field(default=1000, alias="SYNC_CHUNK_SIZE")
    enable_parallel_sync: bool = Field(default=True, alias="ENABLE_PARALLEL_SYNC")
    max_parallel_tenants: int = Field(default=5, alias="MAX_PARALLEL_TENANTS")

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

        When OIDC federation is enabled, client secret is not required —
        the Managed Identity assertion provides authentication.
        """
        if self.use_oidc_federation:
            return bool(self.azure_tenant_id and self.azure_client_id)
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
        return bool(os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"))

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

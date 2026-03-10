"""Riverside Tenant Configuration for DMARC/DKIM Insights.

This module contains hardcoded configuration for Tyler's 5 Riverside tenants.
All sensitive credentials are stored in Azure Key Vault and referenced here.

Security Notes:
- Client secrets are NOT stored in this file
- Use Key Vault references for production
- Rotate credentials regularly
- Follow least privilege principle for Graph API permissions

Tenant List:
1. HTT (Head-To-Toe)
2. BCC (Bishops)
3. FN (Frenchies)
4. TLL (Lash Lounge)
5. DCE (Delta Crown Extensions) - Placeholder for later setup
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TenantConfig:
    """Configuration for a single Azure tenant.

    Attributes:
        tenant_id: Azure AD tenant ID (GUID)
        name: Human-readable tenant name
        code: Short tenant code (e.g., HTT, BCC)
        admin_email: Global admin email address
        app_id: Azure AD app registration client ID
        key_vault_secret_name: Name of client secret in Key Vault
        domains: List of custom domains managed in this tenant
        is_active: Whether this tenant is currently monitored
        is_riverside: Whether this is a Riverside-managed tenant
        priority: Tenant priority for sync operations (1=highest)
    """
    tenant_id: str
    name: str
    code: str
    admin_email: str
    app_id: str
    key_vault_secret_name: str
    domains: list[str] = field(default_factory=list)
    is_active: bool = True
    is_riverside: bool = True
    priority: int = 5


@dataclass(frozen=True)
class GraphPermissions:
    """Required Microsoft Graph API permissions for DMARC/DKIM monitoring.

    These permissions follow the principle of least privilege.
    All are Application permissions requiring admin consent.
    """

    # Read security reports including email authentication reports
    REPORTS_READ_ALL: str = "Reports.Read.All"

    # Read security events and alerts
    SECURITY_EVENTS_READ_ALL: str = "SecurityEvents.Read.All"

    # Read domain information for custom domain verification
    DOMAIN_READ_ALL: str = "Domain.Read.All"

    # Read directory data (users, groups, apps)
    DIRECTORY_READ_ALL: str = "Directory.Read.All"

    @classmethod
    def all_permissions(cls) -> list[str]:
        """Return all required permissions as a list."""
        return [
            cls.REPORTS_READ_ALL,
            cls.SECURITY_EVENTS_READ_ALL,
            cls.DOMAIN_READ_ALL,
            cls.DIRECTORY_READ_ALL,
        ]

    @classmethod
    def permission_descriptions(cls) -> dict[str, str]:
        """Return human-readable descriptions of each permission."""
        return {
            cls.REPORTS_READ_ALL: "Read all usage reports including email security reports",
            cls.SECURITY_EVENTS_READ_ALL: "Read security events and alerts",
            cls.DOMAIN_READ_ALL: "Read all domain properties including verification status",
            cls.DIRECTORY_READ_ALL: "Read directory data (users, groups, applications)",
        }


# =============================================================================
# RIVERSIDE TENANT CONFIGURATIONS
# =============================================================================

RIVERSIDE_TENANTS: dict[str, TenantConfig] = {
    "HTT": TenantConfig(
        tenant_id="0c0e35dc-188a-4eb3-b8ba-61752154b407",
        name="Head-To-Toe (HTT)",
        code="HTT",
        admin_email="tyler.granlund-admin@httbrands.com",
        app_id="1e3e8417-49f1-4d08-b7be-47045d8a12e9",
        key_vault_secret_name="htt-client-secret",
        domains=["httbrands.com"],
        is_active=True,
        is_riverside=True,
        priority=1,
    ),
    "BCC": TenantConfig(
        tenant_id="b5380912-79ec-452d-a6ca-6d897b19b294",
        name="Bishops (BCC)",
        code="BCC",
        admin_email="tyler.granlund-Admin@bishopsbs.onmicrosoft.com",
        app_id="4861906b-2079-4335-923f-a55cc0e44d64",
        key_vault_secret_name="bcc-client-secret",
        domains=["bishopsbs.onmicrosoft.com"],
        is_active=True,
        is_riverside=True,
        priority=2,
    ),
    "FN": TenantConfig(
        tenant_id="98723287-044b-4bbb-9294-19857d4128a0",
        name="Frenchies (FN)",
        code="FN",
        admin_email="tyler.granlund-Admin@ftgfrenchiesoutlook.onmicrosoft.com",
        app_id="7648d04d-ccc4-43ac-bace-da1b68bf11b4",
        key_vault_secret_name="fn-client-secret",
        domains=["ftgfrenchiesoutlook.onmicrosoft.com"],
        is_active=True,
        is_riverside=True,
        priority=3,
    ),
    "TLL": TenantConfig(
        tenant_id="3c7d2bf3-b597-4766-b5cb-2b489c2904d6",
        name="Lash Lounge (TLL)",
        code="TLL",
        admin_email="tyler.granlund-Admin@LashLoungeFranchise.onmicrosoft.com",
        app_id="52531a02-78fd-44ba-9ab9-b29675767955",
        key_vault_secret_name="tll-client-secret",
        domains=["LashLoungeFranchise.onmicrosoft.com"],
        is_active=True,
        is_riverside=True,
        priority=4,
    ),
    "DCE": TenantConfig(
        tenant_id="ce62e17d-2feb-4e67-a115-8ea4af68da30",
        name="Delta Crown Extensions (DCE)",
        code="DCE",
        admin_email="tyler.granlund-admin_httbrands.com#EXT#@deltacrown.onmicrosoft.com",
        app_id="79c22a10-3f2d-4e6a-bddc-ee65c9a46cb0",
        key_vault_secret_name="dce-client-secret",
        domains=["deltacrown.onmicrosoft.com"],
        is_active=True,
        is_riverside=True,
        priority=5,
    ),
}


# =============================================================================
# DMARC/DKIM MONITORING CONFIGURATION
# =============================================================================

@dataclass(frozen=True)
class DmarcDkimConfig:
    """Configuration for DMARC/DKIM monitoring across all tenants."""

    # Graph API endpoints for email authentication
    GRAPH_BASE_URL: str = "https://graph.microsoft.com/v1.0"

    # Security report endpoints
    EMAIL_AUTHENTICATION_REPORTS_ENDPOINT: str = "/reports/getEmailActivityUserDetail"
    SECURITY_ALERTS_ENDPOINT: str = "/security/alerts"

    # Sync intervals (in minutes)
    DMARC_SYNC_INTERVAL_MINUTES: int = 60
    DKIM_SYNC_INTERVAL_MINUTES: int = 60

    # Alert thresholds
    DMARC_FAILURE_THRESHOLD_PERCENT: float = 5.0
    DKIM_FAILURE_THRESHOLD_PERCENT: float = 5.0

    # Data retention (days)
    DMARC_DATA_RETENTION_DAYS: int = 90

    @classmethod
    def get_graph_endpoints(cls) -> dict[str, str]:
        """Return all relevant Graph API endpoints for DMARC/DKIM."""
        base = cls.GRAPH_BASE_URL
        return {
            "email_activity": f"{base}{cls.EMAIL_AUTHENTICATION_REPORTS_ENDPOINT}",
            "security_alerts": f"{base}{cls.SECURITY_ALERTS_ENDPOINT}",
            "domains": f"{base}/domains",
            "organization": f"{base}/organization",
        }


# =============================================================================
# KEY VAULT CONFIGURATION
# =============================================================================

KEY_VAULT_CONFIG = {
    # Key Vault URL should be set via environment variable
    # Format: https://{vault-name}.vault.azure.net/
    "vault_url_env_var": "KEY_VAULT_URL",

    # Secret naming convention for tenant credentials
    "secret_name_template": "{tenant_code.lower()}-client-secret",

    # Certificate-based auth (preferred over secrets)
    "use_certificate_auth": False,  # Set to True when certificates are available
    "certificate_env_var": "AZURE_CLIENT_CERTIFICATE_PATH",
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_active_tenants() -> dict[str, TenantConfig]:
    """Return only active tenant configurations."""
    return {
        code: config
        for code, config in RIVERSIDE_TENANTS.items()
        if config.is_active
    }


def get_tenant_by_id(tenant_id: str) -> TenantConfig | None:
    """Get tenant configuration by tenant ID."""
    for config in RIVERSIDE_TENANTS.values():
        if config.tenant_id == tenant_id:
            return config
    return None


def get_tenant_by_code(code: str) -> TenantConfig | None:
    """Get tenant configuration by short code (e.g., 'HTT')."""
    return RIVERSIDE_TENANTS.get(code.upper())


def get_all_tenant_ids() -> list[str]:
    """Return list of all tenant IDs."""
    return [config.tenant_id for config in RIVERSIDE_TENANTS.values()]


def get_all_active_tenant_ids() -> list[str]:
    """Return list of active tenant IDs."""
    return [
        config.tenant_id
        for config in RIVERSIDE_TENANTS.values()
        if config.is_active
    ]


def get_key_vault_secret_name(tenant_code: str) -> str:
    """Generate the Key Vault secret name for a tenant's client secret."""
    config = get_tenant_by_code(tenant_code)
    if not config:
        raise ValueError(f"Unknown tenant code: {tenant_code}")
    return config.key_vault_secret_name


def validate_tenant_config() -> list[str]:
    """Validate all tenant configurations and return list of issues."""
    issues = []

    for code, config in RIVERSIDE_TENANTS.items():
        # Check for unconfigured or missing values
        if config.tenant_id in ("TBD", "", None):
            issues.append(f"{code}: Tenant ID is not set")

        if config.app_id in ("TBD", "", None):
            issues.append(f"{code}: App ID is not set")

        # Validate UUID format
        import uuid
        try:
            if config.tenant_id not in ("TBD", "", None):
                uuid.UUID(config.tenant_id)
        except ValueError:
            issues.append(f"{code}: Tenant ID is not a valid UUID")

        try:
            if config.app_id not in ("TBD", "", None):
                uuid.UUID(config.app_id)
        except ValueError:
            issues.append(f"{code}: App ID is not a valid UUID")

        # Check admin email format
        if "@" not in config.admin_email:
            issues.append(f"{code}: Admin email is invalid")

    return issues


# =============================================================================
# DEFAULT SETTINGS FOR NEW TENANTS
# =============================================================================

DEFAULT_TENANT_SETTINGS = {
    # Graph API version to use
    "graph_api_version": "v1.0",

    # Default sync intervals (hours)
    "sync_intervals": {
        "dmarc_dkim": 1,
        "security_alerts": 1,
        "domain_status": 24,
    },

    # Monitoring flags
    "monitoring": {
        "enable_dmarc_monitoring": True,
        "enable_dkim_monitoring": True,
        "enable_spf_monitoring": True,
        "alert_on_failure": True,
    },

    # Retry configuration
    "retry": {
        "max_retries": 3,
        "backoff_factor": 2.0,
        "initial_delay_seconds": 1,
    },
}

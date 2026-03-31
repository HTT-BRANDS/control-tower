"""Identity-related Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class IdentitySummary(BaseModel):
    """Identity governance summary across tenants."""

    total_users: int
    active_users: int
    guest_users: int
    mfa_enabled_percent: float
    privileged_users: int
    stale_accounts: int
    service_principals: int
    by_tenant: list["TenantIdentitySummary"] = Field(default_factory=list)


class TenantIdentitySummary(BaseModel):
    """Identity summary for a single tenant."""

    tenant_id: str
    tenant_name: str
    total_users: int
    guest_users: int
    mfa_enabled_percent: float
    privileged_users: int
    stale_accounts_30d: int
    stale_accounts_90d: int


class UserSummary(BaseModel):
    """User summary for a tenant."""

    tenant_id: str
    tenant_name: str
    total_users: int
    active_users: int
    guest_users: int
    member_users: int
    mfa_enabled_count: int
    mfa_disabled_count: int
    mfa_enabled_percent: float


class GroupSummary(BaseModel):
    """Group summary for a tenant."""

    tenant_id: str
    tenant_name: str
    total_groups: int
    security_groups: int
    microsoft_365_groups: int
    mail_enabled_groups: int
    dynamic_groups: int
    synced_groups: int


class IdentityStats(BaseModel):
    """Identity statistics for a tenant."""

    tenant_id: str
    tenant_name: str
    users: UserSummary
    groups: GroupSummary
    privileged_accounts: int
    service_principals: int
    managed_identities: int
    stale_accounts_30d: int
    stale_accounts_90d: int
    snapshot_date: datetime


class PrivilegedAccount(BaseModel):
    """Privileged account details."""

    tenant_id: str
    tenant_name: str
    user_principal_name: str
    display_name: str
    user_type: str  # Member, Guest
    role_name: str
    role_scope: str
    is_permanent: bool
    mfa_enabled: bool
    last_sign_in: datetime | None = None
    risk_level: str = "Medium"  # Low, Medium, High


class GuestAccount(BaseModel):
    """Guest account details."""

    tenant_id: str
    tenant_name: str
    user_principal_name: str
    display_name: str
    invited_by: str | None = None
    created_at: datetime | None = None
    last_sign_in: datetime | None = None
    is_stale: bool = False
    days_inactive: int = 0


class StaleAccount(BaseModel):
    """Stale account details."""

    tenant_id: str
    tenant_name: str
    user_principal_name: str
    display_name: str
    user_type: str
    last_sign_in: datetime | None = None
    days_inactive: int
    has_licenses: bool
    has_privileged_roles: bool


class UserAccount(BaseModel):
    """Basic user account details."""

    id: str = Field(description="Azure AD user object ID")
    tenant_id: str
    tenant_name: str
    user_principal_name: str
    display_name: str
    user_type: str = Field(default="Member", description="Member or Guest")
    account_enabled: bool = True
    mfa_enabled: bool = False
    last_sign_in: datetime | None = None
    created_at: datetime | None = None
    job_title: str | None = None
    department: str | None = None
    office_location: str | None = None


# Update forward references
IdentitySummary.model_rebuild()

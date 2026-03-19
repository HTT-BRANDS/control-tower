"""License-related Pydantic schemas for per-user license tracking.

Models surface per-user Microsoft 365 / Entra license assignments
enriched with SKU names and service plan details retrieved from
Microsoft Graph ``/users/{id}/licenseDetails`` and
``/subscribedSkus``.
"""

from pydantic import BaseModel, Field


class ServicePlanDetail(BaseModel):
    """Details for a single service plan within a license SKU assignment."""

    service_plan_id: str = Field(description="GUID of the service plan")
    service_plan_name: str = Field(description="Human-readable service plan name, e.g. 'EXCHANGE_S_ENTERPRISE'")
    provisioning_status: str = Field(
        description="Provisioning status: Success, Disabled, PendingInput, etc."
    )
    applies_to: str = Field(default="User", description="Who the plan applies to: User or Company")


class UserLicense(BaseModel):
    """A single license SKU assignment for one user.

    Returned by ``GET /users/{id}/licenseDetails``, enriched with
    the user's identity fields.
    """

    user_id: str = Field(description="Azure AD object ID of the user")
    user_principal_name: str = Field(description="UPN of the user, e.g. alice@contoso.com")
    display_name: str = Field(description="Display name of the user")
    sku_id: str = Field(description="GUID of the license SKU")
    sku_part_number: str = Field(
        description="Human-readable SKU identifier, e.g. 'ENTERPRISEPREMIUM' (E5)"
    )
    service_plans: list[ServicePlanDetail] = Field(
        default_factory=list,
        description="Service plans included in this SKU assignment",
    )


class UserLicenseSummary(BaseModel):
    """Aggregated license summary for a single user across all their SKU assignments.

    Used by ``list_tenant_licenses`` which enumerates all licensed users
    without fetching per-user ``licenseDetails`` (cost-efficient).
    """

    tenant_id: str = Field(description="Azure tenant ID")
    user_id: str = Field(description="Azure AD object ID of the user")
    user_principal_name: str = Field(description="UPN of the user")
    display_name: str = Field(description="Display name of the user")
    assigned_sku_ids: list[str] = Field(
        default_factory=list,
        description="List of assigned license SKU GUIDs",
    )
    assigned_sku_part_numbers: list[str] = Field(
        default_factory=list,
        description="List of human-readable SKU part numbers, e.g. ['ENTERPRISEPREMIUM']",
    )
    license_count: int = Field(default=0, description="Total number of licenses assigned")

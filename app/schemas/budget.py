"""Budget-related Pydantic schemas.

Schemas for budget management, alerts, thresholds, and sync operations.
"""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


# =============================================================================
# Budget Schemas
# =============================================================================


class BudgetBase(BaseModel):
    """Base budget schema with common fields."""

    name: str = Field(..., min_length=1, max_length=255, description="Budget name")
    amount: float = Field(..., gt=0, description="Budget amount limit")
    time_grain: str = Field(default="Monthly", description="Budget period granularity")
    category: str = Field(default="Cost", description="Budget category (Cost or Usage)")
    start_date: date = Field(..., description="Budget period start date")
    end_date: date | None = Field(default=None, description="Budget period end date")
    resource_group: str | None = Field(
        default=None, max_length=255, description="Resource group scope (null for subscription)"
    )
    currency: str = Field(default="USD", max_length=10, description="Currency code")

    model_config = ConfigDict(from_attributes=True)


class BudgetCreate(BudgetBase):
    """Schema for creating a new budget."""

    tenant_id: str = Field(..., min_length=1, description="Tenant ID")
    subscription_id: str = Field(..., min_length=1, description="Subscription ID")
    thresholds: list["BudgetThresholdConfig"] = Field(
        default_factory=list, description="Alert thresholds to create"
    )
    notifications: list["BudgetNotificationConfig"] = Field(
        default_factory=list, description="Notification channels"
    )


class BudgetUpdate(BaseModel):
    """Schema for updating an existing budget."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    amount: float | None = Field(default=None, gt=0)
    time_grain: str | None = Field(default=None)
    category: str | None = Field(default=None)
    start_date: date | None = Field(default=None)
    end_date: date | None = Field(default=None)
    resource_group: str | None = Field(default=None, max_length=255)
    currency: str | None = Field(default=None, max_length=10)
    status: str | None = Field(default=None)

    model_config = ConfigDict(from_attributes=True)


class BudgetResponse(BudgetBase):
    """Full budget response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Budget UUID")
    tenant_id: str = Field(..., description="Tenant ID")
    subscription_id: str = Field(..., description="Subscription ID")

    # Current spending
    current_spend: float = Field(default=0.0, description="Current spending amount")
    forecasted_spend: float | None = Field(default=None, description="Forecasted spending")
    utilization_percentage: float = Field(default=0.0, description="Budget utilization %")

    # Status
    status: str = Field(default="active", description="Budget status")

    # Azure metadata
    azure_budget_id: str | None = Field(default=None, description="Full Azure resource ID")
    etag: str | None = Field(default=None, description="ETag for optimistic concurrency")

    # Timestamps
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    last_synced_at: datetime | None = Field(default=None, description="Last sync timestamp")

    # Related data
    thresholds: list["BudgetThresholdResponse"] = Field(default_factory=list)
    recent_alerts: list["BudgetAlertResponse"] = Field(default_factory=list)

    # Computed properties
    remaining_amount: float = Field(..., description="Remaining budget amount")
    is_exceeded: bool = Field(default=False, description="Whether budget is exceeded")
    days_remaining: int | None = Field(default=None, description="Days until budget ends")


class BudgetListItem(BaseModel):
    """Simplified budget item for list views."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    amount: float
    current_spend: float
    utilization_percentage: float
    status: str
    time_grain: str
    currency: str
    start_date: date
    end_date: date | None
    subscription_id: str
    resource_group: str | None
    alert_count: int = Field(default=0, description="Number of pending alerts")
    last_synced_at: datetime | None


class BudgetSummary(BaseModel):
    """Aggregated budget summary for dashboard."""

    total_budgets: int = Field(..., description="Total number of budgets")
    total_budget_amount: float = Field(..., description="Sum of all budget amounts")
    total_current_spend: float = Field(..., description="Sum of all current spending")
    overall_utilization: float = Field(..., description="Overall utilization percentage")

    # Status breakdown
    active_count: int = Field(default=0)
    warning_count: int = Field(default=0)
    critical_count: int = Field(default=0)
    exceeded_count: int = Field(default=0)

    # Alert summary
    pending_alerts: int = Field(default=0)
    acknowledged_alerts: int = Field(default=0)

    # Per-tenant breakdown
    by_tenant: list["BudgetByTenant"] = Field(default_factory=list)


class BudgetByTenant(BaseModel):
    """Budget summary grouped by tenant."""

    tenant_id: str
    tenant_name: str
    budget_count: int
    total_amount: float
    total_spend: float
    utilization_percentage: float


# =============================================================================
# Threshold Schemas
# =============================================================================


class BudgetThresholdConfig(BaseModel):
    """Configuration for a budget alert threshold."""

    percentage: float = Field(..., ge=0, le=500, description="Threshold percentage")
    alert_type: str = Field(default="warning", description="Alert type (warning, critical, etc)")
    contact_emails: list[str] = Field(default_factory=list)
    contact_roles: list[str] = Field(default_factory=list)
    contact_groups: list[str] = Field(default_factory=list)
    is_enabled: bool = Field(default=True)

    @field_validator("percentage")
    @classmethod
    def validate_percentage(cls, v: float) -> float:
        """Validate percentage is within reasonable bounds."""
        if v < 0 or v > 500:
            raise ValueError("Percentage must be between 0 and 500")
        return round(v, 2)


class BudgetThresholdCreate(BudgetThresholdConfig):
    """Schema for creating a budget threshold."""

    budget_id: str = Field(..., description="Budget ID")


class BudgetThresholdUpdate(BaseModel):
    """Schema for updating a budget threshold."""

    percentage: float | None = Field(default=None, ge=0, le=500)
    alert_type: str | None = Field(default=None)
    contact_emails: list[str] | None = Field(default=None)
    contact_roles: list[str] | None = Field(default=None)
    contact_groups: list[str] | None = Field(default=None)
    is_enabled: bool | None = Field(default=None)


class BudgetThresholdResponse(BaseModel):
    """Full budget threshold response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    budget_id: str
    percentage: float
    amount: float | None
    alert_type: str
    contact_emails: str | None  # JSON string
    contact_roles: str | None  # JSON string
    contact_groups: str | None  # JSON string
    is_enabled: bool
    trigger_count: int
    last_triggered_at: datetime | None
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Alert Schemas
# =============================================================================


class BudgetAlertResponse(BaseModel):
    """Budget alert response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    budget_id: str
    budget_name: str | None = Field(default=None, description="Budget name for display")
    tenant_id: str | None = Field(default=None, description="Tenant ID for display")
    subscription_id: str | None = Field(default=None, description="Subscription ID for display")

    threshold_id: int | None
    alert_type: str
    status: str

    threshold_percentage: float
    threshold_amount: float
    current_spend: float
    forecasted_spend: float | None
    utilization_percentage: float

    triggered_at: datetime
    acknowledged_at: datetime | None
    acknowledged_by: str | None
    resolved_at: datetime | None
    resolution_note: str | None

    notification_sent: bool
    notification_sent_at: datetime | None


class BudgetAlertAcknowledge(BaseModel):
    """Request to acknowledge a budget alert."""

    resolution_note: str | None = Field(
        default=None, max_length=1000, description="Optional note about resolution"
    )


class BudgetAlertBulkAcknowledge(BaseModel):
    """Request to acknowledge multiple budget alerts."""

    alert_ids: list[int] = Field(..., min_length=1, description="List of alert IDs to acknowledge")
    resolution_note: str | None = Field(default=None, max_length=1000)


class BudgetAlertBulkResponse(BaseModel):
    """Response after bulk acknowledging alerts."""

    success: bool
    acknowledged_count: int
    failed_ids: list[int]
    acknowledged_at: datetime


# =============================================================================
# Notification Schemas
# =============================================================================


class BudgetNotificationConfig(BaseModel):
    """Configuration for budget notifications."""

    notification_type: str = Field(..., description="Type: email, webhook, teams")
    config: dict[str, Any] = Field(default_factory=dict, description="Type-specific config")
    is_enabled: bool = Field(default=True)


class BudgetNotificationCreate(BudgetNotificationConfig):
    """Schema for creating a budget notification."""

    budget_id: str = Field(..., description="Budget ID")


class BudgetNotificationResponse(BaseModel):
    """Budget notification response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    budget_id: str
    notification_type: str
    config: str | None  # JSON string
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


# =============================================================================
# Sync Schemas
# =============================================================================


class BudgetSyncRequest(BaseModel):
    """Request to sync budgets from Azure."""

    tenant_ids: list[str] | None = Field(
        default=None, description="Specific tenants to sync (null for all)"
    )
    subscription_ids: list[str] | None = Field(
        default=None, description="Specific subscriptions to sync (null for all)"
    )
    sync_type: str = Field(default="incremental", description="Sync type: full, incremental")


class BudgetSyncResultResponse(BaseModel):
    """Budget sync operation result."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: str
    sync_type: str
    status: str

    budgets_synced: int
    budgets_created: int
    budgets_updated: int
    budgets_deleted: int
    alerts_triggered: int
    errors_count: int

    error_message: str | None
    error_details: str | None

    started_at: datetime
    completed_at: datetime | None
    duration_seconds: float | None


# =============================================================================
# Query Parameter Schemas
# =============================================================================


class BudgetListParams(BaseModel):
    """Query parameters for listing budgets."""

    tenant_ids: list[str] | None = Field(default=None)
    subscription_ids: list[str] | None = Field(default=None)
    status: str | None = Field(default=None, pattern="^(active|warning|critical|exceeded)$")
    time_grain: str | None = Field(default=None)
    name_filter: str | None = Field(default=None, max_length=255)

    # Pagination
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)

    # Sorting
    sort_by: str = Field(default="created_at")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")


class BudgetAlertListParams(BaseModel):
    """Query parameters for listing budget alerts."""

    tenant_ids: list[str] | None = Field(default=None)
    budget_ids: list[str] | None = Field(default=None)
    alert_types: list[str] | None = Field(default=None)
    status: str | None = Field(default=None, pattern="^(pending|acknowledged|resolved|dismissed)$")

    # Date range
    triggered_after: datetime | None = Field(default=None)
    triggered_before: datetime | None = Field(default=None)

    # Pagination
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)

    # Sorting
    sort_by: str = Field(default="triggered_at")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")


class BudgetTrendData(BaseModel):
    """Budget trend data point for charts."""

    date: date
    spend: float
    budget_amount: float
    utilization_percentage: float


class BudgetForecastData(BaseModel):
    """Budget forecast data point."""

    date: date
    forecasted_spend: float
    confidence_lower: float | None
    confidence_upper: float | None
    projected_utilization: float


# Update forward references
BudgetResponse.model_rebuild()
BudgetSummary.model_rebuild()

"""Cost-related Pydantic schemas."""

from datetime import date, datetime

from pydantic import BaseModel, Field


class CostSummary(BaseModel):
    """Aggregated cost summary across all tenants."""

    total_cost: float = Field(..., description="Total cost across all tenants")
    currency: str = "USD"
    period_start: date
    period_end: date
    tenant_count: int
    subscription_count: int
    cost_change_percent: float | None = Field(
        None, description="Percentage change from previous period"
    )
    top_services: list["ServiceCost"] = Field(default_factory=list)


class ServiceCost(BaseModel):
    """Cost breakdown by service."""

    service_name: str
    cost: float
    percentage_of_total: float


class CostByTenant(BaseModel):
    """Cost breakdown by tenant."""

    tenant_id: str
    tenant_name: str
    total_cost: float
    currency: str = "USD"
    subscription_costs: list["SubscriptionCost"] = Field(default_factory=list)


class SubscriptionCost(BaseModel):
    """Cost per subscription."""

    subscription_id: str
    subscription_name: str
    cost: float


class CostTrend(BaseModel):
    """Cost trend data point."""

    date: date
    cost: float
    forecast: float | None = None


class CostBreakdown(BaseModel):
    """Cost breakdown by service, resource, or tag."""

    group_key: str = Field(..., description="Service name, resource type, or tag value")
    group_by: str = Field(..., description="Grouping dimension: service, resource, tag")
    total_cost: float
    previous_period_cost: float | None = None
    change_percent: float | None = None
    item_count: int = Field(default=0, description="Number of items in this group")
    currency: str = "USD"


class CostAnomaly(BaseModel):
    """Cost anomaly alert."""

    id: int
    tenant_id: str
    tenant_name: str
    subscription_id: str
    detected_at: datetime
    anomaly_type: str
    description: str
    expected_cost: float
    actual_cost: float
    percentage_change: float
    service_name: str | None = None
    is_acknowledged: bool = False
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None


class AnomalyTrend(BaseModel):
    """Anomaly trend data point over time."""

    period: str  # e.g., "2024-01"
    anomaly_count: int
    total_impact: float  # total unexpected cost
    acknowledged_count: int
    unacknowledged_count: int


class AnomaliesByService(BaseModel):
    """Anomalies grouped by service."""

    service_name: str
    anomaly_count: int
    total_impact: float
    avg_percentage_change: float
    latest_anomaly_at: datetime


class TopAnomaly(BaseModel):
    """Top anomaly by impact."""

    anomaly: CostAnomaly
    impact_score: float  # calculated based on cost impact and percentage change


class BulkAcknowledgeRequest(BaseModel):
    """Request to acknowledge multiple anomalies."""

    anomaly_ids: list[int]


class BulkAcknowledgeResponse(BaseModel):
    """Response after bulk acknowledging anomalies."""

    success: bool
    acknowledged_count: int
    failed_ids: list[int]
    acknowledged_at: datetime


class CostForecast(BaseModel):
    """Cost forecast data point."""

    date: date
    forecasted_cost: float
    confidence_lower: float | None = None
    confidence_upper: float | None = None


class CostFilterParams(BaseModel):
    """Query parameters for filtering costs."""

    tenant_ids: list[str] | None = None
    start_date: date | None = None
    end_date: date | None = None
    service_names: list[str] | None = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    sort_by: str = Field(default="date")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")


# Update forward references
CostSummary.model_rebuild()
CostByTenant.model_rebuild()

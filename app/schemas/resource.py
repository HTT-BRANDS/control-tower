"""Resource-related Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class ResourceItem(BaseModel):
    """Individual resource in inventory."""

    id: str
    tenant_id: str
    tenant_name: str
    subscription_id: str
    subscription_name: str
    resource_group: str
    resource_type: str
    name: str
    location: str
    provisioning_state: str | None = None
    sku: str | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    is_orphaned: bool = False
    estimated_monthly_cost: float | None = None
    last_synced: datetime


class ResourceInventory(BaseModel):
    """Resource inventory summary."""

    total_resources: int
    resources_by_type: dict[str, int] = Field(default_factory=dict)
    resources_by_location: dict[str, int] = Field(default_factory=dict)
    resources_by_tenant: dict[str, int] = Field(default_factory=dict)
    orphaned_resources: int
    orphaned_estimated_cost: float
    resources: list[ResourceItem] = Field(default_factory=list)


class TaggingCompliance(BaseModel):
    """Tagging compliance summary."""

    total_resources: int
    fully_tagged: int
    partially_tagged: int
    untagged: int
    compliance_percent: float
    required_tags: list[str] = Field(default_factory=list)
    missing_tags_by_resource: list["MissingTags"] = Field(default_factory=list)


class MissingTags(BaseModel):
    """Resources with missing required tags."""

    resource_id: str
    resource_name: str
    resource_type: str
    missing_tags: list[str]


class OrphanedResource(BaseModel):
    """Orphaned resource details."""

    resource_id: str
    resource_name: str
    resource_type: str
    tenant_name: str
    subscription_name: str
    estimated_monthly_cost: float | None
    days_inactive: int
    reason: str  # no_activity, no_dependencies, etc.


class IdleResource(BaseModel):
    """Idle resource details."""

    id: int
    resource_id: str
    tenant_id: str
    tenant_name: str
    subscription_id: str
    detected_at: datetime
    idle_type: str  # low_cpu, no_connections, etc.
    description: str
    estimated_monthly_savings: float | None
    idle_days: int
    is_reviewed: bool = False
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_notes: str | None = None


class IdleResourceSummary(BaseModel):
    """Summary of idle resources."""

    total_count: int
    total_potential_savings_monthly: float
    total_potential_savings_annual: float
    by_type: dict[str, int] = Field(default_factory=dict)
    by_tenant: dict[str, int] = Field(default_factory=dict)


class TagResourceRequest(BaseModel):
    """Request to tag a resource as reviewed."""

    notes: str | None = None


class TagResourceResponse(BaseModel):
    """Response after tagging a resource."""

    success: bool
    resource_id: str
    tagged_at: datetime


class ResourceFilterParams(BaseModel):
    """Query parameters for filtering resources."""

    tenant_ids: list[str] | None = None
    resource_type: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    limit: int = Field(default=500, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    sort_by: str = Field(default="name")
    sort_order: str = Field(default="asc", pattern="^(asc|desc)$")


# Update forward references
TaggingCompliance.model_rebuild()


# ==========================================================================
# Bulk Operation Schemas
# ==========================================================================


class ResourceFilterCriteria(BaseModel):
    """Filter criteria for bulk resource operations."""

    tenant_ids: list[str] | None = None
    resource_types: list[str] | None = None
    subscription_ids: list[str] | None = None
    resource_group: str | None = None
    tag_criteria: dict[str, str] | None = None
    location: str | None = None


class BulkTagOperation(BaseModel):
    """Request to tag multiple resources."""

    resource_ids: list[str] | None = None
    resource_filter: ResourceFilterCriteria | None = None
    tags: dict[str, str] = Field(default_factory=dict)
    required_tags: list[str] | None = None
    overwrite_existing: bool = True


class TagOperationResult(BaseModel):
    """Result of a single tag operation."""

    resource_id: str | None
    resource_name: str | None
    success: bool
    message: str


class BulkTagResponse(BaseModel):
    """Response from bulk tag operation."""

    success: bool
    message: str
    total_processed: int
    success_count: int
    failed_count: int
    results: list[TagOperationResult] = Field(default_factory=list)


class BulkAnomalyAcknowledgeRequest(BaseModel):
    """Request to acknowledge multiple anomalies."""

    anomaly_ids: list[int]
    notes: str | None = None


class BulkAnomalyAcknowledgeResponse(BaseModel):
    """Response from bulk anomaly acknowledgment."""

    success: bool
    acknowledged_count: int
    total_requested: int
    acknowledged_by: str
    acknowledged_at: datetime
    notes: str | None = None


class BulkRecommendationDismissRequest(BaseModel):
    """Request to dismiss multiple recommendations."""

    recommendation_ids: list[int]
    reason: str


class BulkRecommendationDismissResponse(BaseModel):
    """Response from bulk recommendation dismissal."""

    success: bool
    dismissed_count: int
    total_requested: int
    dismissed_by: str
    dismissed_at: datetime
    reason: str


class BulkIdleResourceReviewRequest(BaseModel):
    """Request to review multiple idle resources."""

    idle_resource_ids: list[int]
    notes: str | None = None


class BulkIdleResourceReviewResponse(BaseModel):
    """Response from bulk idle resource review."""

    success: bool
    reviewed_count: int
    total_requested: int
    reviewed_by: str
    reviewed_at: datetime
    notes: str | None = None


# Update forward references
TaggingCompliance.model_rebuild()
BulkTagResponse.model_rebuild()

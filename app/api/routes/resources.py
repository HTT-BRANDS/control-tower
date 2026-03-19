"""Resource management API routes.

SECURITY FEATURES:
- UUID validation on tenant IDs
- Strict input validation via Pydantic schemas
- Rate limiting on resource-intensive endpoints
"""

import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.services.resource_service import ResourceService
from app.core.auth import User, get_current_user
from app.core.authorization import (
    TenantAuthorization,
    get_tenant_authorization,
)
from app.core.database import get_db
from app.core.rate_limit import rate_limit
from app.schemas.resource import (
    IdleResource,
    IdleResourceSummary,
    OrphanedResource,
    ResourceInventory,
    TaggingCompliance,
    TagResourceRequest,
    TagResourceResponse,
)

# UUID validation pattern
UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def validate_tenant_id(tenant_id: str | None) -> str | None:
    """Validate tenant_id is a valid UUID.

    Args:
        tenant_id: The tenant ID to validate

    Returns:
        Validated UUID or None

    Raises:
        HTTPException: 400 if invalid format
    """
    if tenant_id is None:
        return None

    if not UUID_PATTERN.match(tenant_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tenant_id must be a valid UUID format (e.g., '12345678-1234-1234-1234-123456789abc')",
        )

    return tenant_id.lower()


# Type alias for validated tenant_id query parameter
ValidatedTenantId = Annotated[
    str | None,
    Query(
        description="Tenant UUID",
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    ),
]


class ValidatedResourceFilterParams(BaseModel):
    """Validated query parameters for filtering resources."""

    model_config = {"extra": "forbid"}

    tenant_id: str | None = Field(
        None,
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    )
    tenant_ids: list[str] | None = None
    resource_type: str | None = Field(None, max_length=100)
    limit: int = Field(default=500, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    sort_by: str = Field(default="name", max_length=50)
    sort_order: str = Field(default="asc", pattern="^(asc|desc)$")


router = APIRouter(
    prefix="/api/v1/resources",
    tags=["resources"],
    dependencies=[Depends(get_current_user)],
)


@router.get(
    "",
    response_model=ResourceInventory,
    dependencies=[Depends(rate_limit("default"))],
)
async def get_resources(
    tenant_id: ValidatedTenantId = None,
    tenant_ids: list[str] | None = Query(default=None, description="List of tenant UUIDs"),
    resource_type: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=500, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="name", max_length=50),
    sort_order: str = Query(default="asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get resource inventory with filtering and pagination.

    Args:
        tenant_id: Filter by single tenant (deprecated, use tenant_ids)
        tenant_ids: Filter by specific tenants
        resource_type: Filter by resource type
        limit: Maximum results to return
        offset: Pagination offset
        sort_by: Field to sort by
        sort_order: Sort direction (asc or desc)
    """
    authz.ensure_at_least_one_tenant()

    # Validate and filter tenant access
    if tenant_id:
        authz.validate_access(tenant_id)

    filtered_tenant_ids = authz.filter_tenant_ids(tenant_ids)
    if tenant_ids and not filtered_tenant_ids:
        # User requested specific tenants but has access to none
        return ResourceInventory(resources=[], total_resources=0, total_cost=0.0)

    service = ResourceService(db)
    inventory = await service.get_resource_inventory(
        tenant_id=tenant_id,
        resource_type=resource_type,
        limit=limit,
    )

    # Apply tenant isolation
    accessible_tenants = authz.accessible_tenant_ids
    inventory.resources = [
        r
        for r in inventory.resources
        if r.tenant_id in accessible_tenants
        and (not filtered_tenant_ids or r.tenant_id in filtered_tenant_ids)
    ]
    inventory.total_resources = len(inventory.resources)

    return inventory


@router.get(
    "/orphaned",
    response_model=list[OrphanedResource],
    dependencies=[Depends(rate_limit("default"))],
)
async def get_orphaned_resources(
    tenant_ids: list[str] | None = Query(default=None, description="List of tenant UUIDs"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get orphaned resources with filtering and pagination.

    Args:
        tenant_ids: Filter by specific tenants
        limit: Maximum results to return
        offset: Pagination offset
    """
    authz.ensure_at_least_one_tenant()

    filtered_tenant_ids = authz.filter_tenant_ids(tenant_ids)

    service = ResourceService(db)
    orphaned = await service.get_orphaned_resources()

    # Apply tenant isolation
    accessible_tenants = authz.accessible_tenant_ids
    orphaned = [
        o
        for o in orphaned
        if o.tenant_name in accessible_tenants
        and (not filtered_tenant_ids or o.tenant_name in filtered_tenant_ids)
    ]

    return orphaned[offset : offset + limit]


@router.get(
    "/idle",
    response_model=list[IdleResource],
    dependencies=[Depends(rate_limit("default"))],
)
async def get_idle_resources(
    tenant_ids: list[str] | None = Query(default=None, description="List of tenant UUIDs"),
    idle_type: str | None = Query(default=None, max_length=50),
    is_reviewed: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="estimated_monthly_savings", max_length=50),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get idle resources with filtering and pagination.

    Args:
        tenant_ids: Filter by specific tenants
        idle_type: Filter by idle type (e.g., low_cpu, no_connections)
        is_reviewed: Filter by review status
        limit: Maximum results to return
        offset: Pagination offset
        sort_by: Field to sort by
        sort_order: Sort direction (asc or desc)
    """
    authz.ensure_at_least_one_tenant()

    # Filter tenant_ids to only accessible ones
    filtered_tenant_ids = authz.filter_tenant_ids(tenant_ids)

    service = ResourceService(db)
    return service.get_idle_resources(
        tenant_ids=filtered_tenant_ids,
        idle_type=idle_type,
        is_reviewed=is_reviewed,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get(
    "/idle/summary",
    response_model=IdleResourceSummary,
    dependencies=[Depends(rate_limit("default"))],
)
async def get_idle_resources_summary(
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get summary of idle resources."""
    authz.ensure_at_least_one_tenant()
    service = ResourceService(db)
    accessible_tenants = authz.accessible_tenant_ids
    return await service.get_idle_resources_summary(tenant_ids=accessible_tenants)


@router.post(
    "/idle/{idle_resource_id}/tag",
    response_model=TagResourceResponse,
    dependencies=[Depends(rate_limit("auth"))],
)
async def tag_idle_resource(
    idle_resource_id: int = Path(..., ge=1, description="Idle resource ID"),
    request_data: TagResourceRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Tag an idle resource as reviewed.

    Args:
        idle_resource_id: ID of the idle resource to tag
        request_data: Optional review notes
        current_user: User performing the tagging
    """
    # Get the idle resource to validate tenant access
    from app.models.resource import IdleResource

    idle_resource = db.query(IdleResource).filter(IdleResource.id == idle_resource_id).first()
    if idle_resource:
        authz.validate_access(idle_resource.tenant_id)

    service = ResourceService(db)
    return await service.tag_idle_resource_as_reviewed(
        idle_resource_id=idle_resource_id,
        user=current_user.id,
        notes=request_data.notes if request_data else None,
    )


@router.get(
    "/tagging",
    response_model=TaggingCompliance,
    dependencies=[Depends(rate_limit("default"))],
)
async def get_tagging_compliance(
    required_tags: list[str] | None = Query(default=None, max_length=50),
    tenant_ids: list[str] | None = Query(default=None, description="List of tenant UUIDs"),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get tagging compliance summary.

    Args:
        required_tags: List of required tags to check
        tenant_ids: Filter by specific tenants
    """
    authz.ensure_at_least_one_tenant()

    # Filter tenant_ids to only accessible ones
    authz.filter_tenant_ids(tenant_ids)

    service = ResourceService(db)
    return await service.get_tagging_compliance(required_tags=required_tags)


# --- Resource Lifecycle History (RM-004) ---


@router.get("/{resource_id}/history")
async def get_resource_history(
    resource_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get lifecycle history for a specific resource.

    Returns create/update/delete events detected during sync runs.
    Ordered by detection time, newest first.
    """
    from app.api.services.resource_lifecycle_service import ResourceLifecycleService

    svc = ResourceLifecycleService(db)
    events = svc.get_history(resource_id, limit=limit, offset=offset)
    return {
        "resource_id": resource_id,
        "events": [e.to_dict() for e in events],
        "count": len(events),
        "limit": limit,
        "offset": offset,
    }

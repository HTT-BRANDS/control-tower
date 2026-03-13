"""Cost management API routes."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.services.cost_service import CostService
from app.core.auth import User, get_current_user
from app.core.authorization import (
    TenantAuthorization,
    get_tenant_authorization,
)
from app.core.database import get_db
from app.schemas.cost import (
    BulkAcknowledgeRequest,
    BulkAcknowledgeResponse,
    CostByTenant,
    CostSummary,
    CostTrend,
)

router = APIRouter(
    prefix="/api/v1/costs",
    tags=["costs"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/summary", response_model=CostSummary)
async def get_cost_summary(
    period_days: int = Query(default=30, ge=1, le=365),
    tenant_ids: list[str] | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get aggregated cost summary across all tenants.

    Args:
        period_days: Number of days to look back (used if start_date not provided)
        tenant_ids: Filter by specific tenants
        start_date: Optional explicit start date
        end_date: Optional explicit end date
    """
    authz.ensure_at_least_one_tenant()

    # Filter tenant_ids to only accessible ones
    filtered_tenant_ids = authz.filter_tenant_ids(tenant_ids)

    service = CostService(db)
    # Use filtered tenant IDs if specified, otherwise use all accessible tenants
    effective_tenant_ids = (
        filtered_tenant_ids if filtered_tenant_ids else authz.accessible_tenant_ids
    )
    return await service.get_cost_summary(period_days=period_days, tenant_ids=effective_tenant_ids)


@router.get("/by-tenant", response_model=list[CostByTenant])
async def get_costs_by_tenant(
    period_days: int = Query(default=30, ge=1, le=365),
    tenant_ids: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get cost breakdown by tenant.

    Args:
        period_days: Number of days to look back
        tenant_ids: Filter by specific tenants
    """
    authz.ensure_at_least_one_tenant()

    filtered_tenant_ids = authz.filter_tenant_ids(tenant_ids)

    service = CostService(db)
    costs = await service.get_costs_by_tenant(period_days=period_days)

    # Apply tenant isolation
    accessible_tenants = authz.accessible_tenant_ids
    costs = [
        c
        for c in costs
        if c.tenant_id in accessible_tenants
        and (not filtered_tenant_ids or c.tenant_id in filtered_tenant_ids)
    ]

    return costs


@router.get("/trends", response_model=list[CostTrend])
async def get_cost_trends(
    days: int = Query(default=30, ge=7, le=365),
    tenant_ids: list[str] | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get daily cost trends.

    Args:
        days: Number of days of history
        tenant_ids: Filter by specific tenants
        start_date: Optional explicit start date
        end_date: Optional explicit end date
    """
    authz.ensure_at_least_one_tenant()

    # Filter tenant_ids to only accessible ones
    filtered_tenant_ids = authz.filter_tenant_ids(tenant_ids)

    service = CostService(db)
    # Use filtered tenant IDs if specified, otherwise use all accessible tenants
    effective_tenant_ids = (
        filtered_tenant_ids if filtered_tenant_ids else authz.accessible_tenant_ids
    )
    return await service.get_cost_trends(days=days, tenant_ids=effective_tenant_ids)


@router.get("/trends/forecast")
async def get_cost_forecast(
    days: int = Query(default=30, ge=7, le=90),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get cost forecast using simple linear projection.

    Args:
        days: Number of days to forecast
    """
    authz.ensure_at_least_one_tenant()
    service = CostService(db)
    # Filter forecast to only accessible tenants
    return await service.get_cost_forecast(days=days, tenant_ids=authz.accessible_tenant_ids)


@router.get("/anomalies")
async def get_cost_anomalies(
    acknowledged: bool | None = Query(default=None),
    tenant_ids: list[str] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="detected_at"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get cost anomalies with filtering and pagination.

    Args:
        acknowledged: Filter by acknowledged status
        tenant_ids: Filter by specific tenants
        limit: Maximum results to return
        offset: Pagination offset
        sort_by: Field to sort by
        sort_order: Sort direction (asc or desc)
    """
    authz.ensure_at_least_one_tenant()

    filtered_tenant_ids = authz.filter_tenant_ids(tenant_ids)

    service = CostService(db)
    anomalies = service.get_anomalies(acknowledged=acknowledged)

    # Apply tenant isolation
    accessible_tenants = authz.accessible_tenant_ids
    anomalies = [
        a
        for a in anomalies
        if a.tenant_id in accessible_tenants
        and (not filtered_tenant_ids or a.tenant_id in filtered_tenant_ids)
    ]

    return anomalies[offset : offset + limit]


@router.get("/anomalies/trends")
async def get_anomaly_trends(
    months: int = Query(default=6, ge=1, le=24),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get anomaly trends over time grouped by month.

    Args:
        months: Number of months to analyze
    """
    authz.ensure_at_least_one_tenant()
    service = CostService(db)
    # Filter trends to only accessible tenants
    return await service.get_anomaly_trends(months=months, tenant_ids=authz.accessible_tenant_ids)


@router.get("/anomalies/by-service")
async def get_anomalies_by_service(
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get anomalies grouped by service.

    Args:
        limit: Maximum number of services to return
    """
    authz.ensure_at_least_one_tenant()
    service = CostService(db)
    # Filter results to only accessible tenants
    return await service.get_anomalies_by_service(
        limit=limit, tenant_ids=authz.accessible_tenant_ids
    )


@router.get("/anomalies/top")
async def get_top_anomalies(
    n: int = Query(default=10, ge=1, le=50),
    acknowledged: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get top N anomalies by impact.

    Args:
        n: Number of top anomalies to return
        acknowledged: Filter by acknowledged status
    """
    authz.ensure_at_least_one_tenant()
    service = CostService(db)
    anomalies = service.get_top_anomalies(n=n, acknowledged=acknowledged)

    # Apply tenant isolation
    accessible_tenants = authz.accessible_tenant_ids
    return [a for a in anomalies if a.anomaly.tenant_id in accessible_tenants]


@router.post("/anomalies/{anomaly_id}/acknowledge")
async def acknowledge_anomaly(
    anomaly_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Acknowledge a cost anomaly."""
    from fastapi import HTTPException

    from app.models.cost import CostAnomaly

    # Validate user has access to the anomaly's tenant
    anomaly = db.query(CostAnomaly).filter(CostAnomaly.id == anomaly_id).first()
    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly not found")

    if anomaly.tenant_id not in authz.accessible_tenant_ids:
        raise HTTPException(
            status_code=403,
            detail="Access denied: You don't have permission to access this anomaly's tenant",
        )

    service = CostService(db)
    success = await service.acknowledge_anomaly(anomaly_id, user=current_user.id)
    return {"success": success}


@router.post("/anomalies/bulk-acknowledge", response_model=BulkAcknowledgeResponse)
async def bulk_acknowledge_anomalies(
    request: BulkAcknowledgeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Acknowledge multiple cost anomalies at once.

    Args:
        request: Contains list of anomaly IDs to acknowledge
        current_user: User performing the acknowledgment
    """
    from fastapi import HTTPException

    from app.models.cost import CostAnomaly

    # Validate user has access to all anomaly tenants
    anomalies = db.query(CostAnomaly).filter(CostAnomaly.id.in_(request.anomaly_ids)).all()

    # Check if all anomalies were found
    if len(anomalies) != len(request.anomaly_ids):
        found_ids = {a.id for a in anomalies}
        missing_ids = set(request.anomaly_ids) - found_ids
        raise HTTPException(
            status_code=404,
            detail=f"Anomalies not found: {missing_ids}",
        )

    # Validate access to all tenant IDs
    inaccessible_tenants = [
        a.tenant_id for a in anomalies if a.tenant_id not in authz.accessible_tenant_ids
    ]
    if inaccessible_tenants:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: You don't have permission to access tenants: {set(inaccessible_tenants)}",
        )

    service = CostService(db)
    return await service.bulk_acknowledge_anomalies(request.anomaly_ids, user=current_user.id)

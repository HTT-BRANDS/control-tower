"""Budget management API routes.

Provides REST endpoints for budget CRUD operations, alerts, and Azure sync.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.services.budget_service import BudgetService, BudgetServiceError
from app.core.auth import User, get_current_user
from app.core.authorization import TenantAuthorization, get_tenant_authorization
from app.core.database import get_db
from app.schemas.budget import (
    BudgetAlertAcknowledge,
    BudgetAlertBulkAcknowledge,
    BudgetAlertBulkResponse,
    BudgetAlertResponse,
    BudgetCreate,
    BudgetListItem,
    BudgetResponse,
    BudgetSummary,
    BudgetSyncRequest,
    BudgetSyncResultResponse,
    BudgetUpdate,
)

router = APIRouter(
    prefix="/api/v1/budgets",
    tags=["budgets"],
    dependencies=[Depends(get_current_user)],
)


# =============================================================================
# Budget CRUD Routes
# =============================================================================


@router.get("", response_model=list[BudgetListItem])
async def list_budgets(
    tenant_ids: list[str] | None = Query(default=None),
    subscription_ids: list[str] | None = Query(default=None),
    status: str | None = Query(default=None, pattern="^(active|warning|critical|exceeded)$"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """List budgets with optional filtering and pagination.

    Args:
        tenant_ids: Filter by specific tenants
        subscription_ids: Filter by specific subscriptions
        status: Filter by budget status (active, warning, critical, exceeded)
        limit: Maximum results to return
        offset: Pagination offset
        sort_by: Field to sort by
        sort_order: Sort direction (asc or desc)

    Returns:
        List of budget list items
    """
    authz.ensure_at_least_one_tenant()

    # Filter tenant_ids to only accessible ones
    filtered_tenant_ids = authz.filter_tenant_ids(tenant_ids)

    service = BudgetService(db)
    return await service.get_budgets(
        tenant_ids=filtered_tenant_ids,
        subscription_ids=subscription_ids,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
async def create_budget(
    data: BudgetCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Create a new budget.

    Args:
        data: Budget creation data including thresholds and notifications

    Returns:
        Created budget with full details

    Raises:
        HTTPException: If user doesn't have access to tenant
    """
    # Validate user has access to the tenant
    if data.tenant_id not in authz.accessible_tenant_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You don't have permission to create budgets in this tenant",
        )

    service = BudgetService(db)
    try:
        return await service.create_budget(data)
    except BudgetServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("/summary", response_model=BudgetSummary)
async def get_budget_summary(
    tenant_ids: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get aggregated budget summary across accessible tenants.

    Args:
        tenant_ids: Filter by specific tenants (optional)

    Returns:
        Budget summary with status breakdown and alert counts
    """
    authz.ensure_at_least_one_tenant()

    filtered_tenant_ids = authz.filter_tenant_ids(tenant_ids)
    effective_tenant_ids = (
        filtered_tenant_ids if filtered_tenant_ids else authz.accessible_tenant_ids
    )

    service = BudgetService(db)
    return await service.get_budget_summary(tenant_ids=effective_tenant_ids)


@router.get("/{budget_id}", response_model=BudgetResponse)
async def get_budget(
    budget_id: str,
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get detailed budget information by ID.

    Args:
        budget_id: Budget UUID

    Returns:
        Budget details including thresholds and recent alerts

    Raises:
        HTTPException: If budget not found or access denied
    """
    from app.models.budget import Budget

    # Validate user has access to the budget's tenant
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found",
        )

    if budget.tenant_id not in authz.accessible_tenant_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You don't have permission to view this budget",
        )

    service = BudgetService(db)
    result = await service.get_budget(budget_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found",
        )

    return result


@router.patch("/{budget_id}", response_model=BudgetResponse)
async def update_budget(
    budget_id: str,
    data: BudgetUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Update an existing budget.

    Args:
        budget_id: Budget UUID
        data: Update data (only provided fields will be updated)

    Returns:
        Updated budget details

    Raises:
        HTTPException: If budget not found or access denied
    """
    from app.models.budget import Budget

    # Validate user has access to the budget's tenant
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found",
        )

    if budget.tenant_id not in authz.accessible_tenant_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You don't have permission to update this budget",
        )

    service = BudgetService(db)
    try:
        result = await service.update_budget(budget_id, data)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Budget not found",
            )
        return result
    except BudgetServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(
    budget_id: str,
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Delete a budget.

    Args:
        budget_id: Budget UUID

    Raises:
        HTTPException: If budget not found or access denied
    """
    from app.models.budget import Budget

    # Validate user has access to the budget's tenant
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found",
        )

    if budget.tenant_id not in authz.accessible_tenant_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You don't have permission to delete this budget",
        )

    service = BudgetService(db)
    try:
        success = await service.delete_budget(budget_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Budget not found",
            )
    except BudgetServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


# =============================================================================
# Budget Alert Routes
# =============================================================================


@router.get("/{budget_id}/alerts", response_model=list[BudgetAlertResponse])
async def get_budget_alerts(
    budget_id: str,
    status: str | None = Query(default=None, pattern="^(pending|acknowledged|resolved|dismissed)$"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get alerts for a specific budget.

    Args:
        budget_id: Budget UUID
        status: Filter by alert status
        limit: Maximum results to return
        offset: Pagination offset

    Returns:
        List of budget alerts
    """
    from app.models.budget import Budget

    # Validate user has access to the budget's tenant
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found",
        )

    if budget.tenant_id not in authz.accessible_tenant_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You don't have permission to view this budget's alerts",
        )

    service = BudgetService(db)
    return await service.get_budget_alerts(
        budget_id=budget_id,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.get("/alerts/all", response_model=list[BudgetAlertResponse])
async def get_all_budget_alerts(
    tenant_ids: list[str] | None = Query(default=None),
    alert_types: list[str] | None = Query(default=None),
    status: str | None = Query(default=None, pattern="^(pending|acknowledged|resolved|dismissed)$"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get all budget alerts across accessible tenants.

    Args:
        tenant_ids: Filter by specific tenants
        alert_types: Filter by alert types
        status: Filter by alert status
        limit: Maximum results to return
        offset: Pagination offset

    Returns:
        List of budget alerts
    """
    authz.ensure_at_least_one_tenant()

    filtered_tenant_ids = authz.filter_tenant_ids(tenant_ids)
    effective_tenant_ids = (
        filtered_tenant_ids if filtered_tenant_ids else authz.accessible_tenant_ids
    )

    service = BudgetService(db)
    alerts = await service.get_budget_alerts(
        tenant_ids=effective_tenant_ids,
        status=status,
        limit=limit,
        offset=offset,
    )

    # Filter by alert types if specified
    if alert_types:
        alerts = [a for a in alerts if a.alert_type in alert_types]

    return alerts


@router.post("/alerts/{alert_id}/acknowledge", response_model=dict)
async def acknowledge_alert(
    alert_id: int,
    request: BudgetAlertAcknowledge | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Acknowledge a budget alert.

    Args:
        alert_id: Alert ID
        request: Optional acknowledgment with resolution note

    Returns:
        Success status
    """
    from app.models.budget import BudgetAlert

    # Validate user has access to the alert's tenant
    alert = db.query(BudgetAlert).filter(BudgetAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    if alert.budget.tenant_id not in authz.accessible_tenant_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You don't have permission to acknowledge this alert",
        )

    service = BudgetService(db)
    note = request.resolution_note if request else None
    success = await service.acknowledge_alert(alert_id, current_user.id, note)

    return {"success": success}


@router.post("/alerts/bulk-acknowledge", response_model=BudgetAlertBulkResponse)
async def bulk_acknowledge_alerts(
    request: BudgetAlertBulkAcknowledge,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Acknowledge multiple budget alerts at once.

    Args:
        request: Contains list of alert IDs and optional resolution note

    Returns:
        Bulk acknowledgment result
    """
    from app.models.budget import BudgetAlert

    # Validate user has access to all alert tenants
    alerts = db.query(BudgetAlert).filter(BudgetAlert.id.in_(request.alert_ids)).all()

    if len(alerts) != len(request.alert_ids):
        found_ids = {a.id for a in alerts}
        missing_ids = set(request.alert_ids) - found_ids
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alerts not found: {missing_ids}",
        )

    # Check access to all tenants
    inaccessible_tenants = [
        a.budget.tenant_id for a in alerts if a.budget.tenant_id not in authz.accessible_tenant_ids
    ]
    if inaccessible_tenants:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: No permission for tenants: {set(inaccessible_tenants)}",
        )

    service = BudgetService(db)
    return await service.bulk_acknowledge_alerts(
        request.alert_ids, current_user.id, request.resolution_note
    )


# =============================================================================
# Budget Sync Routes
# =============================================================================


@router.post("/{budget_id}/sync", response_model=BudgetSyncResultResponse)
async def sync_single_budget(
    budget_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Sync a single budget from Azure.

    Args:
        budget_id: Budget UUID

    Returns:
        Sync result
    """
    from app.models.budget import Budget

    # Validate user has access to the budget's tenant
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found",
        )

    if budget.tenant_id not in authz.accessible_tenant_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You don't have permission to sync this budget",
        )

    service = BudgetService(db)
    try:
        return await service.sync_budgets_from_azure(
            tenant_id=budget.tenant_id,
            subscription_ids=[budget.subscription_id],
        )
    except BudgetServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post("/sync/all", response_model=BudgetSyncResultResponse)
async def sync_all_budgets(
    request: BudgetSyncRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Sync budgets from Azure for accessible tenants.

    Args:
        request: Optional sync parameters

    Returns:
        Sync result
    """
    authz.ensure_at_least_one_tenant()

    # Filter tenant IDs to accessible ones
    if request and request.tenant_ids:
        filtered_tenant_ids = authz.filter_tenant_ids(request.tenant_ids)
        if not filtered_tenant_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: No valid tenant IDs provided",
            )
        tenant_id = filtered_tenant_ids[0]  # Sync one tenant at a time for now
    else:
        tenant_id = authz.accessible_tenant_ids[0]

    service = BudgetService(db)
    try:
        return await service.sync_budgets_from_azure(
            tenant_id=tenant_id,
            subscription_ids=request.subscription_ids if request else None,
        )
    except BudgetServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

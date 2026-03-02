"""Riverside compliance tracking API routes.

This module provides REST API endpoints for Riverside Company compliance
tracking with the July 8, 2026 deadline and $4M financial risk.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.services.riverside_service import RiversideService
from app.core.auth import User, get_current_user
from app.core.authorization import (
    TenantAuthorization,
    get_tenant_authorization,
)
from app.core.database import get_db

router = APIRouter(
    tags=["riverside"],
    dependencies=[Depends(get_current_user)],
)
templates = Jinja2Templates(directory="app/templates")


@router.get("/riverside", response_class=HTMLResponse)
async def riverside_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Riverside compliance dashboard page."""
    return templates.TemplateResponse(
        "pages/riverside_dashboard.html",
        {"request": request},
    )


# ============================================================================
# API Routes
# ============================================================================

@router.get("/api/v1/riverside/summary", response_model=dict)
async def get_riverside_summary(
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get executive summary for Riverside compliance dashboard.

    Returns comprehensive summary including:
    - Days to deadline (July 8, 2026)
    - Financial risk ($4M)
    - Overall maturity score
    - MFA coverage across tenants
    - Device compliance
    - Critical gaps count
    """
    authz.ensure_at_least_one_tenant()
    service = RiversideService(db)
    # TODO: Filter by accessible tenants
    return service.get_riverside_summary()


@router.get("/api/v1/riverside/mfa-status", response_model=dict)
async def get_mfa_status(
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get MFA tracking status for all tenants.

    Returns MFA enrollment metrics including:
    - Total users and MFA enrollment count
    - Coverage percentage per tenant
    - Admin account MFA status
    - Unprotected user count
    """
    authz.ensure_at_least_one_tenant()
    service = RiversideService(db)
    # TODO: Filter by accessible tenants
    return service.get_mfa_status()


@router.get("/api/v1/riverside/maturity-scores", response_model=dict)
async def get_maturity_scores(
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get maturity scores for all domains and tenants.

    Returns maturity scoring including:
    - Overall maturity average
    - Domain scores (IAM, GS, DS)
    - Per-tenant breakdown
    - Days remaining until deadline
    """
    authz.ensure_at_least_one_tenant()
    service = RiversideService(db)
    # TODO: Filter by accessible tenants
    return service.get_maturity_scores()


@router.get("/api/v1/riverside/requirements", response_model=dict)
async def get_requirements(
    category: str | None = Query(default=None, description="Filter by category (IAM, GS, DS)"),
    priority: str | None = Query(default=None, description="Filter by priority (P0, P1, P2)"),
    status: str | None = Query(default=None, description="Filter by status (not_started, in_progress, completed, blocked)"),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get requirements list with optional filtering.

    Returns filtered requirements with statistics by status and priority.
    """
    authz.ensure_at_least_one_tenant()
    service = RiversideService(db)
    # TODO: Filter by accessible tenants
    return service.get_requirements(category=category, priority=priority, status=status)


@router.get("/api/v1/riverside/gaps", response_model=dict)
async def get_gaps(
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get critical gaps analysis.

    Returns critical gaps categorized by priority:
    - Immediate action items (P0 + overdue)
    - High priority gaps
    - Medium priority gaps
    """
    authz.ensure_at_least_one_tenant()
    service = RiversideService(db)
    # TODO: Filter by accessible tenants
    return service.get_gaps()


@router.post("/api/v1/riverside/sync")
async def trigger_sync(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Trigger manual sync of all Riverside compliance data.

    Requires operator or admin role.

    This will sync:
    - MFA data from Graph API
    - Device compliance from Intune
    - Requirement status
    - Maturity scores
    """
    # Check user has appropriate role
    if not any(role in current_user.roles for role in ["admin", "operator"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Riverside sync requires operator or admin role",
        )

    authz.ensure_at_least_one_tenant()
    service = RiversideService(db)
    results = await service.sync_all()
    return {
        "status": "success",
        "message": "Riverside sync completed",
        "results": results,
    }

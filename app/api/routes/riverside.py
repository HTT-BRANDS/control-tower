"""Riverside compliance tracking API routes.

This module provides REST API endpoints for Riverside Company compliance
tracking with the July 8, 2026 deadline and $4M financial risk.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.api.services.riverside_service import RiversideService
from app.core.auth import User, get_current_user
from app.core.authorization import (
    TenantAuthorization,
    get_tenant_authorization,
)
from app.core.database import get_db
from app.core.templates import templates
from app.core.tenant_context import get_brand_context_for_request

router = APIRouter(
    tags=["riverside"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/riverside", response_class=HTMLResponse)
async def riverside_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Riverside compliance dashboard page."""
    brand_context = get_brand_context_for_request(request)
    return templates.TemplateResponse(
        request,
        "pages/riverside_dashboard.html",
        {**brand_context},
    )


@router.get("/partials/riverside-badge", response_class=HTMLResponse)
async def riverside_badge(
    request: Request,
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """HTMX partial for Riverside navigation badge."""
    authz.ensure_at_least_one_tenant()
    service = RiversideService(db)
    summary = await service.get_riverside_summary()
    brand_context = get_brand_context_for_request(request)

    return templates.TemplateResponse(
        request,
        "components/riverside_badge.html",
        {
            "total_critical_gaps": summary.get("total_critical_gaps", 0),
            **brand_context,
        },
    )


# ============================================================================
# API Routes
# ============================================================================


@router.get("/api/v1/riverside/summary", response_model=dict)
async def get_riverside_summary(
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get executive summary for Riverside compliance dashboard."""
    authz.ensure_at_least_one_tenant()
    service = RiversideService(db)
    return await service.get_riverside_summary()


@router.get("/api/v1/riverside/mfa-status", response_model=dict)
async def get_mfa_status(
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get MFA tracking status for all tenants."""
    authz.ensure_at_least_one_tenant()
    service = RiversideService(db)
    return await service.get_mfa_status()


@router.get("/api/v1/riverside/maturity-scores", response_model=dict)
async def get_maturity_scores(
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get maturity scores for all domains and tenants."""
    authz.ensure_at_least_one_tenant()
    service = RiversideService(db)
    return await service.get_maturity_scores()


@router.get("/api/v1/riverside/requirements")
async def get_requirements(
    request: Request,
    category: str | None = Query(default=None, description="Filter by category (IAM, GS, DS)"),
    priority: str | None = Query(default=None, description="Filter by priority (P0, P1, P2)"),
    status: str | None = Query(
        default=None, description="Filter by status (not_started, in_progress, completed, blocked)"
    ),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get requirements list with optional filtering.

    Content negotiation (f8f2):
      - HX-Request header present → renders partials/riverside_requirements_list.html
        so pages/riverside.html can HTMX-swap directly without JS re-rendering.
      - Otherwise → returns JSON for programmatic API consumers (preflight
        checks, external integrations, staging e2e).
    """
    authz.ensure_at_least_one_tenant()
    service = RiversideService(db)
    data = service.get_requirements(category=category, priority=priority, status=status)
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request, "partials/riverside_requirements_list.html", data
        )
    return data


@router.get("/api/v1/riverside/gaps")
async def get_gaps(
    request: Request,
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get critical gaps analysis.

    Content negotiation (f8f2): see get_requirements docstring.
    Renders partials/riverside_alerts_panel.html for HTMX requests,
    returns JSON otherwise.
    """
    authz.ensure_at_least_one_tenant()
    service = RiversideService(db)
    data = await service.get_gaps()
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request, "partials/riverside_alerts_panel.html", data)
    return data


@router.post("/api/v1/riverside/sync")
async def trigger_sync(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Trigger manual sync of all Riverside compliance data.

    Requires operator or admin role.
    """
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

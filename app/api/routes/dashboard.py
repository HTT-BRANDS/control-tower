"""Dashboard API routes."""

import asyncio
import logging
import traceback
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.services.compliance_service import ComplianceService
from app.api.services.cost_service import CostService
from app.api.services.identity_service import IdentityService
from app.api.services.monitoring_service import MonitoringService
from app.api.services.resource_service import ResourceService
from app.core.auth import User, get_current_user
from app.core.authorization import (
    TenantAuthorization,
    get_tenant_authorization,
    get_user_tenants,
)
from app.core.database import get_db
from app.core.templates import templates
from app.core.tenant_context import get_brand_context_for_request
from app.models.compliance import ComplianceSnapshot
from app.models.cost import CostSnapshot
from app.models.identity import IdentitySnapshot
from app.models.monitoring import Alert, SyncJobLog
from app.models.resource import Resource
from app.models.tenant import Tenant

router = APIRouter(
    tags=["dashboard"],
    dependencies=[Depends(get_current_user)],
)


def _coerce_utc_datetime(value: datetime | None) -> datetime | None:
    """Normalize datetimes to UTC-aware values for template-safe arithmetic."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _prepare_sync_logs_for_display(logs: list[SyncJobLog]) -> list[SyncJobLog]:
    """Normalize sync log datetimes before Jinja renders relative timestamps."""
    for log in logs:
        log.started_at = _coerce_utc_datetime(log.started_at)
        log.ended_at = _coerce_utc_datetime(log.ended_at)
    return logs


async def _get_dashboard_data(
    db: Session,
    authz: TenantAuthorization,
) -> dict:
    """Get dashboard data with tenant filtering.

    Args:
        db: Database session
        authz: Tenant authorization

    Returns:
        Dictionary with dashboard data
    """
    authz.ensure_at_least_one_tenant()

    # Get summary data from all services concurrently (filtered by tenant access)

    cost_svc = CostService(db)
    compliance_svc = ComplianceService(db)
    resource_svc = ResourceService(db)
    identity_svc = IdentityService(db)

    cost_summary, compliance_summary, resource_inventory, identity_summary = await asyncio.gather(
        cost_svc.get_cost_summary(),
        compliance_svc.get_compliance_summary(),
        resource_svc.get_resource_inventory(limit=10),
        identity_svc.get_identity_summary(),
    )

    # Apply tenant isolation to resources
    accessible_tenants = authz.accessible_tenant_ids
    resource_inventory.resources = [
        r for r in resource_inventory.resources if r.tenant_id in accessible_tenants
    ]
    resource_inventory.total_resources = len(resource_inventory.resources)

    # ct-lzi (P1): Use actual model synced_at timestamps, NOT SyncJobLog.started_at.
    # The job log records when the *sync process ran* (or even when it failed
    # gracefully), but it does NOT reflect whether data actually arrived in the
    # database. A job can complete while bringing back zero rows because of an
    # auth error — the UI then happily shows "Synced 0h ago" while the real data
    # is days stale. That exact scenario is how ct-y47 went undetected for 7 days.
    #
    # We now query MAX(synced_at) from the actual domain tables scoped to the
    # accessible tenant set. If a tenant has no rows in a domain table, the
    # timestamp is None and the UI will show "Synced never" — which is the honest
    # signal.
    sync_types = ["costs", "compliance", "resources", "identity"]
    last_synced: dict[str, Any] = {}
    tenant_ids = list(authz.accessible_tenant_ids)
    if tenant_ids:
        last_synced["costs"] = (
            db.query(func.max(CostSnapshot.synced_at))
            .filter(CostSnapshot.tenant_id.in_(tenant_ids))
            .scalar()
        )
        last_synced["compliance"] = (
            db.query(func.max(ComplianceSnapshot.synced_at))
            .filter(ComplianceSnapshot.tenant_id.in_(tenant_ids))
            .scalar()
        )
        last_synced["resources"] = (
            db.query(func.max(Resource.synced_at))
            .filter(Resource.tenant_id.in_(tenant_ids))
            .scalar()
        )
        last_synced["identity"] = (
            db.query(func.max(IdentitySnapshot.synced_at))
            .filter(IdentitySnapshot.tenant_id.in_(tenant_ids))
            .scalar()
        )
    else:
        last_synced = dict.fromkeys(sync_types)

    # Compute stale syncs for the UI banner (>48 hours old or never synced)
    stale_syncs: list[str] = []
    now = datetime.now(UTC)
    max_age = 48 * 3600  # 48 hours in seconds
    for sync_type, sync_time in last_synced.items():
        if sync_time is None:
            stale_syncs.append(f"{sync_type} (never)")
            continue
        # DB datetimes may be naive (SQLite) — coerce to UTC-aware so the
        # subtraction below never mixes naive/aware operands.
        sync_time = _coerce_utc_datetime(sync_time)
        last_synced[sync_type] = sync_time
        if (now - sync_time).total_seconds() > max_age:
            stale_syncs.append(sync_type)

    return {
        "cost_summary": cost_summary,
        "compliance_summary": compliance_summary,
        "resource_inventory": resource_inventory,
        "identity_summary": identity_summary,
        "last_synced": last_synced,
        "stale_syncs": stale_syncs,
    }


logger = logging.getLogger(__name__)


@router.get("/dashboard")
async def dashboard_page(
    request: Request,
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
    tenant_id: str | None = None,
):
    """Main dashboard view with optional tenant scope filter."""
    try:
        data = await _get_dashboard_data(db, authz)
        brand_context = get_brand_context_for_request(request)

        # Build tenant list for scope selector
        if "admin" in authz.user.roles:
            tenants = db.query(Tenant).filter(Tenant.is_active).all()
        else:
            tenants = get_user_tenants(authz.user, db, include_inactive=False)

        # Surface the "no tenants configured anywhere" case explicitly. Non-admins
        # already get a 403 from ensure_at_least_one_tenant(); admins on an empty
        # tenant table (e.g. unseeded staging) would otherwise see a silently-blank
        # dashboard with zero-value KPI cards. The template branches on this flag.
        no_tenants_configured = len(tenants) == 0

        return templates.TemplateResponse(
            request,
            "pages/dashboard.html",
            {
                **data,
                **brand_context,
                "tenants": tenants,
                "selected_tenant_id": tenant_id or "",
                "no_tenants_configured": no_tenants_configured,
            },
        )
    except Exception as exc:
        tb = traceback.format_exc()
        logger.error(f"Dashboard error: {exc}\n{tb}")
        return JSONResponse(
            status_code=500,
            content={
                "error": str(exc),
                "traceback": tb,
            },
        )


@router.get("/partials/cost-summary-card", response_class=HTMLResponse)
async def cost_summary_card(request: Request, db: Session = Depends(get_db)):
    """HTMX partial: Cost summary card."""
    cost_svc = CostService(db)
    summary = await cost_svc.get_cost_summary()

    return templates.TemplateResponse(
        request,
        "components/cost_summary_card.html",
        {"summary": summary},
    )


@router.get("/partials/compliance-gauge", response_class=HTMLResponse)
async def compliance_gauge(request: Request, db: Session = Depends(get_db)):
    """HTMX partial: Compliance score gauge."""
    compliance_svc = ComplianceService(db)
    summary = await compliance_svc.get_compliance_summary()

    return templates.TemplateResponse(
        request,
        "components/compliance_gauge.html",
        {"summary": summary},
    )


@router.get("/partials/resource-stats", response_class=HTMLResponse)
async def resource_stats(request: Request, db: Session = Depends(get_db)):
    """HTMX partial: Resource statistics."""
    resource_svc = ResourceService(db)
    inventory = await resource_svc.get_resource_inventory()

    return templates.TemplateResponse(
        request,
        "components/resource_stats.html",
        {"inventory": inventory},
    )


@router.get("/partials/identity-stats", response_class=HTMLResponse)
async def identity_stats(request: Request, db: Session = Depends(get_db)):
    """HTMX partial: Identity statistics."""
    identity_svc = IdentityService(db)
    summary = await identity_svc.get_identity_summary()

    return templates.TemplateResponse(
        request,
        "components/identity_stats.html",
        {"summary": summary},
    )


# ============================================================================
# Sync Dashboard Routes
# ============================================================================


@router.get("/sync-dashboard", response_class=HTMLResponse)
async def sync_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Main sync dashboard page for DevOps/SRE monitoring."""
    authz.ensure_at_least_one_tenant()
    monitoring = MonitoringService(db)

    # Get overall sync status
    overall_status = monitoring.get_overall_status()

    # Get recent sync history (last 20 jobs) filtered by accessible tenants
    recent_logs = _prepare_sync_logs_for_display(
        monitoring.get_recent_logs(
            limit=20,
            include_running=True,
            tenant_ids=authz.accessible_tenant_ids,
        )
    )

    # Get active alerts
    active_alerts = monitoring.get_active_alerts()[:10]
    alert_stats = monitoring.get_alert_stats()

    # Get tenant sync status (filtered by access)
    tenant_status = await _get_tenant_sync_status(db, monitoring, authz)

    # Get metrics for all job types
    metrics = monitoring.get_metrics()

    return templates.TemplateResponse(
        request,
        "pages/sync_dashboard.html",
        {
            "overall_status": overall_status,
            "recent_logs": recent_logs,
            "active_alerts": active_alerts,
            "alert_stats": alert_stats,
            "tenant_status": tenant_status,
            "metrics": metrics,
            "last_refresh": datetime.now(UTC),
        },
    )


async def _get_tenant_sync_status(
    db: Session, monitoring: MonitoringService, authz: TenantAuthorization
) -> list[dict]:
    """Get per-tenant sync status for all sync types."""
    # Only get tenants the user has access to
    if "admin" in authz.user.roles:
        tenants = db.query(Tenant).filter(Tenant.is_active).all()
    else:
        tenants = get_user_tenants(authz.user, db, include_inactive=False)
    sync_types = ["costs", "compliance", "resources", "identity"]

    tenant_status = []
    for tenant in tenants:
        tenant_syncs = []
        overall_health = "healthy"

        for sync_type in sync_types:
            # Get last log for this tenant and sync type
            last_log = (
                db.query(SyncJobLog)
                .filter(
                    SyncJobLog.job_type == sync_type,
                    SyncJobLog.tenant_id == tenant.id,
                )
                .order_by(SyncJobLog.started_at.desc())
                .first()
            )

            if last_log:
                # Calculate staleness
                started_at = _coerce_utc_datetime(last_log.started_at)
                last_log.started_at = started_at
                hours_since_sync = (datetime.now(UTC) - started_at).total_seconds() / 3600
                expected_interval = 24  # hours

                if last_log.status == "failed":
                    status = "error"
                    overall_health = "error" if overall_health == "healthy" else overall_health
                elif hours_since_sync > expected_interval * 2:
                    status = "stale"
                    overall_health = "warning" if overall_health == "healthy" else overall_health
                elif hours_since_sync > expected_interval * 1.5:
                    status = "warning"
                    overall_health = "warning" if overall_health == "healthy" else overall_health
                else:
                    status = "healthy"

                tenant_syncs.append(
                    {
                        "sync_type": sync_type,
                        "status": status,
                        "last_run": last_log.started_at,
                        "last_status": last_log.status,
                        "records_processed": last_log.records_processed,
                        "errors_count": last_log.errors_count,
                    }
                )
            else:
                tenant_syncs.append(
                    {
                        "sync_type": sync_type,
                        "status": "never_run",
                        "last_run": None,
                        "last_status": None,
                        "records_processed": 0,
                        "errors_count": 0,
                    }
                )
                if overall_health == "healthy":
                    overall_health = "warning"

        # Count alerts for this tenant
        tenant_alerts = (
            db.query(Alert)
            .filter(
                Alert.tenant_id == tenant.id,
                Alert.is_resolved == 0,
            )
            .count()
        )

        tenant_status.append(
            {
                "tenant": tenant,
                "syncs": tenant_syncs,
                "overall_health": overall_health,
                "alert_count": tenant_alerts,
            }
        )

    return tenant_status


@router.get("/partials/sync-status-card", response_class=HTMLResponse)
async def sync_status_card_partial(request: Request, db: Session = Depends(get_db)):
    """HTMX partial: Live sync status card (refreshes every 30s)."""
    monitoring = MonitoringService(db)
    overall_status = monitoring.get_overall_status()
    metrics = monitoring.get_metrics()

    return templates.TemplateResponse(
        request,
        "components/sync/sync_status_card.html",
        {
            "status": overall_status,
            "metrics": metrics,
            "last_refresh": datetime.now(UTC),
        },
    )


@router.get("/partials/sync-history-table", response_class=HTMLResponse)
async def sync_history_table_partial(
    request: Request,
    limit: int = 15,
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """HTMX partial: Recent sync jobs table."""
    monitoring = MonitoringService(db)
    recent_logs = _prepare_sync_logs_for_display(
        monitoring.get_recent_logs(
            limit=limit,
            include_running=True,
            tenant_ids=authz.accessible_tenant_ids,
        )
    )

    return templates.TemplateResponse(
        request,
        "components/sync/sync_history_table.html",
        {
            "logs": recent_logs,
            "last_refresh": datetime.now(UTC),
        },
    )


@router.get("/partials/active-alerts", response_class=HTMLResponse)
async def active_alerts_partial(request: Request, db: Session = Depends(get_db)):
    """HTMX partial: Active alerts panel."""
    monitoring = MonitoringService(db)
    active_alerts = monitoring.get_active_alerts()[:10]
    alert_stats = monitoring.get_alert_stats()

    return templates.TemplateResponse(
        request,
        "components/sync/active_alerts.html",
        {
            "alerts": active_alerts,
            "stats": alert_stats,
            "last_refresh": datetime.now(UTC),
        },
    )


@router.get("/partials/tenant-sync-status", response_class=HTMLResponse)
async def tenant_sync_status_partial(
    request: Request,
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """HTMX partial: Per-tenant sync status grid."""
    monitoring = MonitoringService(db)
    tenant_status = await _get_tenant_sync_status(db, monitoring, authz)

    return templates.TemplateResponse(
        request,
        "components/sync/tenant_sync_grid.html",
        {
            "tenant_status": tenant_status,
            "last_refresh": datetime.now(UTC),
        },
    )


# ============================================================================
# DMARC Dashboard Routes
# ============================================================================


@router.get("/dmarc", response_class=HTMLResponse)
async def dmarc_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """DMARC/DKIM security dashboard page."""
    return templates.TemplateResponse(
        request,
        "pages/dmarc_dashboard.html",
    )


# Public routes (no auth required)
public_router = APIRouter(tags=["public"])


def _login_context(request: Request) -> dict[str, Any]:
    """Build login template context, gating the dev form server-side.

    ct-0b1: never ship the dev username/password form HTML to production.
    The form is only rendered when settings.environment == "development".
    """
    from app.core.config import get_settings

    settings = get_settings()
    return {"is_dev": settings.environment == "development"}


@public_router.get("/login")
async def login_page_public(request: Request):
    """ct-tdu: legacy /login path — 301-redirects to canonical /auth/login.

    Previously this route served byte-identical HTML to ``/auth/login``
    (15,457 chars each), wasting a render and creating two URLs for the
    same page (bad for analytics, social sharing, and any "copy login
    link" workflow). Now ``/auth/login`` is the single canonical URL and
    ``/login`` is a permanent redirect so external bookmarks and old
    deep-links keep working.

    The redirect preserves the query string (e.g. ``?next=/costs``)
    via Starlette's default RedirectResponse behavior on the path.
    """
    from fastapi.responses import RedirectResponse

    target = "/auth/login"
    if request.url.query:
        target = f"{target}?{request.url.query}"
    # 301 = permanent; browsers and search engines will cache the swap.
    return RedirectResponse(url=target, status_code=301)


@public_router.get("/auth/login", response_class=HTMLResponse)
async def auth_login_page(request: Request):
    """Canonical login page (ct-tdu chose /auth/login as the canonical URL)."""
    return templates.TemplateResponse(request, "login.html", _login_context(request))

"""Sync job management API routes.

SECURITY FEATURES:
- Rate limiting on sync triggers (prevents abuse)
- Strict input validation
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.api.services.monitoring_service import MonitoringService
from app.core.auth import User, get_current_user
from app.core.authorization import (
    TenantAuthorization,
    get_tenant_authorization,
    validate_tenants_access,
)
from app.core.database import get_db
from app.core.rate_limit import rate_limit
from app.core.scheduler import get_scheduler, trigger_manual_sync
from app.core.tenant_context import get_brand_context_for_request

router = APIRouter(
    prefix="/api/v1/sync",
    tags=["sync"],
    dependencies=[Depends(get_current_user)],
)
templates = Jinja2Templates(directory="app/templates")

SyncType = Literal["costs", "compliance", "resources", "identity"]


@router.post(
    "/{sync_type}",
    dependencies=[Depends(rate_limit("sync"))],  # Strict rate limit for sync triggers
)
async def trigger_sync(
    sync_type: SyncType,
    current_user: User = Depends(get_current_user),
):
    """Trigger a manual sync job."""
    success = await trigger_manual_sync(sync_type)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown sync type: {sync_type}",
        )
    return {"status": "triggered", "sync_type": sync_type}


@router.get(
    "/status",
    dependencies=[Depends(rate_limit("default"))],
)
async def get_sync_status(
    current_user: User = Depends(get_current_user),
):
    """Get status of sync jobs."""
    scheduler = get_scheduler()
    if not scheduler:
        return {"status": "scheduler_not_initialized", "jobs": []}

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
        })

    return {"status": "running", "jobs": jobs}


@router.get(
    "/status/health",
    dependencies=[Depends(rate_limit("default"))],
)
async def get_sync_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get overall sync health status with metrics."""
    monitoring = MonitoringService(db)
    return monitoring.get_overall_status()


@router.get(
    "/history",
    dependencies=[Depends(rate_limit("default"))],
)
async def get_sync_history(
    job_type: str | None = Query(None, max_length=50),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get recent sync job execution history."""
    authz.ensure_at_least_one_tenant()
    monitoring = MonitoringService(db)
    logs = monitoring.get_recent_logs(
        job_type=job_type, limit=limit, include_running=False
    )

    # Filter logs by tenant access
    accessible_tenants = authz.accessible_tenant_ids
    logs = [log for log in logs if not log.tenant_id or log.tenant_id in accessible_tenants]

    return {
        "logs": [
            {
                "id": log.id,
                "job_type": log.job_type,
                "tenant_id": log.tenant_id,
                "status": log.status,
                "started_at": log.started_at.isoformat() if log.started_at else None,
                "ended_at": log.ended_at.isoformat() if log.ended_at else None,
                "duration_ms": log.duration_ms,
                "records_processed": log.records_processed,
                "errors_count": log.errors_count,
                "error_message": log.error_message,
            }
            for log in logs
        ]
    }


@router.get(
    "/metrics",
    dependencies=[Depends(rate_limit("default"))],
)
async def get_sync_metrics(
    job_type: str | None = Query(None, max_length=50),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get aggregate sync job metrics."""
    authz.ensure_at_least_one_tenant()
    monitoring = MonitoringService(db)
    metrics = monitoring.get_metrics(job_type=job_type)

    # Filter metrics by tenant access
    accessible_tenants = authz.accessible_tenant_ids
    metrics = [m for m in metrics if not m.tenant_id or m.tenant_id in accessible_tenants]

    return {
        "metrics": [
            {
                "job_type": m.job_type,
                "calculated_at": m.calculated_at.isoformat() if m.calculated_at else None,
                "total_runs": m.total_runs,
                "successful_runs": m.successful_runs,
                "failed_runs": m.failed_runs,
                "success_rate": m.success_rate,
                "avg_duration_ms": m.avg_duration_ms,
                "min_duration_ms": m.min_duration_ms,
                "max_duration_ms": m.max_duration_ms,
                "avg_records_processed": m.avg_records_processed,
                "total_records_processed": m.total_records_processed,
                "total_errors": m.total_errors,
                "last_run_at": m.last_run_at.isoformat() if m.last_run_at else None,
                "last_success_at": m.last_success_at.isoformat() if m.last_success_at else None,
                "last_failure_at": m.last_failure_at.isoformat() if m.last_failure_at else None,
                "last_error_message": m.last_error_message,
            }
            for m in metrics
        ]
    }


@router.get(
    "/alerts",
    dependencies=[Depends(rate_limit("default"))],
)
async def get_sync_alerts(
    job_type: str | None = Query(None, max_length=50),
    severity: str | None = Query(None, pattern="^(info|warning|error|critical)$"),
    include_resolved: bool = Query(False),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get sync job alerts."""
    authz.ensure_at_least_one_tenant()
    monitoring = MonitoringService(db)

    if include_resolved:
        # Get all alerts (not just active)
        from app.models.monitoring import Alert

        query = db.query(Alert)
        if job_type:
            query = query.filter(Alert.job_type == job_type)
        if severity:
            query = query.filter(Alert.severity == severity)
        alerts = query.order_by(Alert.created_at.desc()).limit(100).all()
    else:
        alerts = monitoring.get_active_alerts(job_type=job_type, severity=severity)

    # Filter alerts by tenant access
    accessible_tenants = authz.accessible_tenant_ids
    alerts = [a for a in alerts if not a.tenant_id or a.tenant_id in accessible_tenants]

    return {
        "alerts": [
            {
                "id": alert.id,
                "alert_type": alert.alert_type,
                "severity": alert.severity,
                "job_type": alert.job_type,
                "tenant_id": alert.tenant_id,
                "title": alert.title,
                "message": alert.message,
                "is_resolved": bool(alert.is_resolved),
                "created_at": alert.created_at.isoformat() if alert.created_at else None,
                "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
                "resolved_by": alert.resolved_by,
            }
            for alert in alerts
        ],
        "stats": monitoring.get_alert_stats() if not include_resolved else None,
    }


@router.post(
    "/alerts/{alert_id}/resolve",
    dependencies=[Depends(rate_limit("auth"))],
)
async def resolve_alert(
    alert_id: int = Path(..., ge=1, description="Alert ID"),
    resolved_by: str = Query("system", max_length=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resolve a sync job alert."""
    monitoring = MonitoringService(db)
    try:
        alert = monitoring.resolve_alert(alert_id, resolved_by=resolved_by)
        return {
            "id": alert.id,
            "alert_type": alert.alert_type,
            "is_resolved": bool(alert.is_resolved),
            "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
            "resolved_by": alert.resolved_by,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ============================================================================
# HTMX Partials
# ============================================================================


@router.get("/partials/sync-status", response_class=HTMLResponse)
async def sync_status_partial(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """HTMX partial: Sync status card."""
    monitoring = MonitoringService(db)
    status = monitoring.get_overall_status()
    metrics = monitoring.get_metrics()
    brand_context = get_brand_context_for_request(request)

    return templates.TemplateResponse(
        "components/sync_status.html",
        {
            "request": request,
            "status": status,
            "metrics": metrics,
            **brand_context,
        },
    )


@router.get("/partials/sync-alerts", response_class=HTMLResponse)
async def sync_alerts_partial(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """HTMX partial: Recent alerts panel."""
    monitoring = MonitoringService(db)
    alerts = monitoring.get_active_alerts()[:10]  # Limit to 10 most recent
    stats = monitoring.get_alert_stats()
    brand_context = get_brand_context_for_request(request)

    return templates.TemplateResponse(
        "components/sync_alerts.html",
        {
            "request": request,
            "alerts": alerts,
            "stats": stats,
            **brand_context,
        },
    )

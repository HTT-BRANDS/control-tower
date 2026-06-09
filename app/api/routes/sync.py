"""Sync job management API routes.

SECURITY FEATURES:
- Rate limiting on sync triggers (prevents abuse)
- Strict input validation
"""

import asyncio
import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.api.services.monitoring_service import MonitoringService
from app.core.auth import User, get_current_user, require_roles
from app.core.authorization import (
    TenantAuthorization,
    get_tenant_authorization,
)
from app.core.database import get_db, get_db_context
from app.core.rate_limit import rate_limit
from app.core.scheduler import get_scheduler, trigger_manual_sync
from app.core.sync.status_snapshot import build_sync_snapshot
from app.core.sync.utils import explain_tenant_sync_eligibility
from app.core.templates import templates
from app.core.tenant_context import get_brand_context_for_request

router = APIRouter(
    prefix="/api/v1/sync",
    tags=["sync"],
    dependencies=[Depends(get_current_user)],
)

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


@router.post(
    "/trigger/{sync_type}",
    dependencies=[Depends(rate_limit("sync"))],
)
async def trigger_sync_named(
    sync_type: SyncType,
    current_user: User = Depends(get_current_user),
):
    """Trigger a manual sync job at /trigger/{sync_type}.

    Canonical endpoint for sync triggers — mirrors POST /{sync_type} but
    sits at a more explicit path so API consumers can tell at a glance
    that this is a write operation, not a resource path.
    """
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
        jobs.append(
            {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            }
        )

    return {"status": "running", "jobs": jobs}


# Server-Sent Events: real-time sync status stream (bd ct-7d6).
# SSE (not WebSocket) is intentional — one-way push, EventSource auto-reconnect,
# works under `connect-src 'self'` CSP + cookie auth with no Azure App Service
# WebSocket toggle. The frontend client lives in static/js/realtimeSync.js.
_SSE_INTERVAL_SECONDS = 8.0
_SSE_MAX_LIFETIME_SECONDS = 3600.0  # recycle long-lived streams hourly


async def _sync_event_stream(request: Request):
    """Yield text/event-stream frames with the current sync snapshot.

    Opens a fresh short-lived DB session per tick (never holds a connection
    open for the whole stream) and stops cleanly when the client disconnects.
    """
    elapsed = 0.0
    # Send an initial snapshot immediately so the UI doesn't wait one interval.
    while elapsed <= _SSE_MAX_LIFETIME_SECONDS:
        if await request.is_disconnected():
            break
        try:
            with get_db_context() as db:
                snapshot = build_sync_snapshot(db)
            payload = json.dumps(snapshot, separators=(",", ":"))
            yield f"event: sync\ndata: {payload}\n\n"
        except Exception:  # pragma: no cover - keep the stream alive on a blip
            # Comment frame keeps the connection warm without emitting bad data.
            yield ": snapshot-error\n\n"
        await asyncio.sleep(_SSE_INTERVAL_SECONDS)
        elapsed += _SSE_INTERVAL_SECONDS


@router.get("/stream")
async def stream_sync_status(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Real-time sync status via Server-Sent Events.

    Emits a JSON snapshot (see build_sync_snapshot) every few seconds under the
    `sync` event name. Auth is enforced by the router's get_current_user
    dependency; the browser's EventSource handles reconnection.
    """
    return StreamingResponse(
        _sync_event_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable proxy buffering (nginx/Azure)
            "Connection": "keep-alive",
        },
    )


@router.get(
    "/status/diagnostics",
    dependencies=[Depends(rate_limit("default"))],
)
async def get_sync_diagnostics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "operator"])),
):
    """Return secret-safe production sync diagnostics.

    This endpoint intentionally reports *configuration shape* and recent
    outcomes, not secret values. Its job is to answer: "will sync jobs have
    any chance of authenticating and producing records?" without making us
    spelunk App Service settings and SQL like caffeinated goblins.
    """
    from app.core.config import get_settings
    from app.models.monitoring import SyncJobLog, SyncJobMetrics
    from app.models.tenant import Tenant

    settings = get_settings()
    tenants = db.query(Tenant).filter(Tenant.is_active).order_by(Tenant.name).all()
    tenant_rows = []
    for tenant in tenants:
        decision = explain_tenant_sync_eligibility(tenant)
        tenant_rows.append(
            {
                "name": tenant.name,
                "tenant_id": tenant.tenant_id,
                "eligible": decision.eligible,
                "auth_mode": decision.auth_mode,
                "reason": decision.reason,
                "client_id_present": bool(tenant.client_id),
                "client_secret_ref_present": bool(tenant.client_secret_ref),
                "expected_standard_secret_names": [
                    f"{tenant.tenant_id}-client-id",
                    f"{tenant.tenant_id}-client-secret",
                ]
                if settings.key_vault_url and not tenant.client_secret_ref
                else [],
            }
        )

    recent_logs = db.query(SyncJobLog).order_by(SyncJobLog.started_at.desc()).limit(20).all()
    metrics = db.query(SyncJobMetrics).order_by(SyncJobMetrics.job_type).all()

    return {
        "configuration": {
            "environment": settings.environment,
            "key_vault_configured": bool(settings.key_vault_url),
            "use_oidc_federation": bool(settings.use_oidc_federation),
            "use_uami_auth": bool(settings.use_uami_auth),
            "shared_azure_client_id_present": bool(settings.azure_client_id),
            "shared_azure_client_secret_present": bool(settings.azure_client_secret),
        },
        "tenants": tenant_rows,
        "recent_logs": [
            {
                "job_type": log.job_type,
                "tenant_id": log.tenant_id,
                "status": log.status,
                "started_at": log.started_at.isoformat() if log.started_at else None,
                "ended_at": log.ended_at.isoformat() if log.ended_at else None,
                "records_processed": log.records_processed,
                "errors_count": log.errors_count,
                "error_message": log.error_message,
            }
            for log in recent_logs
        ],
        "metrics": [
            {
                "job_type": metric.job_type,
                "success_rate": metric.success_rate,
                "last_run_at": metric.last_run_at.isoformat() if metric.last_run_at else None,
                "last_success_at": metric.last_success_at.isoformat()
                if metric.last_success_at
                else None,
                "last_failure_at": metric.last_failure_at.isoformat()
                if metric.last_failure_at
                else None,
                "last_error_message": metric.last_error_message,
            }
            for metric in metrics
        ],
    }


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
    logs = monitoring.get_recent_logs(job_type=job_type, limit=limit, include_running=False)

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

    # Note: SyncJobMetrics are global (per job_type), not tenant-specific
    # Tenant filtering happens at the job log level

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
        raise HTTPException(status_code=404, detail=str(e)) from e


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
        request,
        "components/sync_status.html",
        {
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
        request,
        "components/sync_alerts.html",
        {
            "alerts": alerts,
            "stats": stats,
            **brand_context,
        },
    )

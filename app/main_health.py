"""Root, health, and status routes registered by app.main."""

from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.database import get_db


def register_health_and_status_routes(
    app,
    settings,
    cache_manager,
    get_blacklist_backend,
    get_blacklist_size,
) -> None:
    """Register lightweight root, health, and status endpoints."""

    @app.get("/health")
    async def health_check():
        """Basic health check endpoint."""
        return {
            "status": "healthy",
            "version": settings.app_version,
            "environment": settings.environment,
        }

    @app.get("/healthz/data")
    async def healthz_data_alias(db: Session = Depends(get_db)):
        """Friendly alias for /api/v1/health/data."""
        from app.api.routes.health import data_freshness_check

        return await data_freshness_check(db=db)

    @app.get("/healthz/scheduler")
    async def healthz_scheduler():
        """Background-scheduler heartbeat (ct-ar3).

        Surfaces whether the in-process scheduler is running and, per job, the
        next run + last success/error/missed + an ``overdue`` flag. This makes
        the silent-stall failure mode (ct-cne) observable and gives the
        freshness alert (ct-vuv) a scheduler-level signal to complement the
        data-age check in /healthz/data.
        """
        from app.core.scheduler import get_scheduler_health

        return get_scheduler_health()

    @app.get("/health/detailed")
    async def detailed_health_check():
        """Detailed health check with component status and pool statistics.

        Each component reports a string status that participates in the
        overall rollup via ``healthy_values``. ``azure_configured`` is the
        outlier: a deliberately un-configured non-production environment
        (staging, dev) must NOT mark the system ``degraded`` just because
        it lacks Azure AD credentials. See ct-czv AC #2.
        """
        from sqlalchemy import text

        from app.core.database import _IS_SQLITE, SessionLocal, _get_engine
        from app.core.scheduler import get_scheduler

        # azure_configured uses a string sentinel that participates in the
        # healthy_values set below rather than a bare True/False, so the
        # rollup logic stays declarative (no special-case branches).
        azure_status: str
        if settings.is_configured:
            azure_status = "configured"
        elif settings.is_production:
            azure_status = "missing"
        else:
            azure_status = "not_required"

        components: dict[str, Any] = {
            "database": "unknown",
            "scheduler": "unknown",
            "cache": "unknown",
            "azure_configured": azure_status,
        }
        pool_stats: dict[str, Any] = {}

        try:
            db = SessionLocal()
            db.execute(text("SELECT 1"))
            db.close()
            components["database"] = "healthy"

            if not _IS_SQLITE:
                pool = _get_engine().pool
                pool_stats = {
                    "size": pool.size(),
                    "checked_in": pool.checkedin(),
                    "checked_out": pool.checkedout(),
                    "overflow": pool.overflow(),
                }
        except Exception as exc:
            components["database"] = f"unhealthy: {str(exc)}"

        scheduler = get_scheduler()
        components["scheduler"] = "running" if scheduler and scheduler.running else "not_running"

        # Bounded cache probe — the previous ``get_metrics()`` call only
        # checked the in-process metrics counters and never reflected a
        # wedged Redis connection. The shared helper actually round-trips
        # the backend with a timeout (ct-czv).
        cache_probe = await cache_manager.check_health(
            probe_key="root_health_detailed_probe",
        )
        cache_probe_status = cache_probe.get("status", "unhealthy")
        # Mirror the shape the previous version exposed: the components map
        # holds a short label that participates in the healthy_values set.
        # "healthy"/"disabled" both count as fine for liveness purposes.
        components["cache"] = (
            cache_probe.get("backend", "unknown")
            if cache_probe_status in {"healthy", "disabled"}
            else cache_probe_status
        )

        blacklist_backend = get_blacklist_backend()
        components["token_blacklist"] = blacklist_backend
        healthy_values = {
            "healthy",
            "running",
            "memory",
            "redis",
            "configured",
            "not_required",
            True,
        }

        return {
            "status": "healthy"
            if all(value in healthy_values for value in components.values())
            else "degraded",
            "version": settings.app_version,
            "components": components,
            "cache_metrics": cache_probe,
            "database_pool": pool_stats if pool_stats else "n/a (SQLite)",
            "token_blacklist": {
                "backend": blacklist_backend,
                "size": get_blacklist_size(),
            },
        }

    @app.get("/api/v1/status")
    async def get_system_status():
        """Get detailed system status and health metrics."""
        from sqlalchemy import text

        from app.api.services.monitoring_service import MonitoringService
        from app.core.database import SessionLocal, get_db_stats
        from app.core.monitoring import get_performance_dashboard
        from app.core.scheduler import get_scheduler

        status = {
            "status": "healthy",
            "version": settings.app_version,
            "timestamp": datetime.now(UTC).isoformat(),
            "components": {},
            "sync_jobs": {},
            "alerts": {},
            "performance": {},
            "cache": {},
        }

        try:
            db = SessionLocal()
            db_stats = get_db_stats(db)
            db.execute(text("SELECT 1"))
            db.close()
            status["components"]["database"] = "healthy"
            status["database_stats"] = db_stats
        except Exception as exc:
            status["components"]["database"] = f"unhealthy: {str(exc)}"
            status["status"] = "degraded"

        try:
            scheduler = get_scheduler()
            if scheduler and scheduler.running:
                status["components"]["scheduler"] = "running"
                status["sync_jobs"]["active_jobs"] = len(scheduler.get_jobs())
            else:
                status["components"]["scheduler"] = "not_running"
        except Exception as exc:
            status["components"]["scheduler"] = f"error: {str(exc)}"

        try:
            cache_metrics = cache_manager.get_metrics()
            status["cache"] = cache_metrics
            status["components"]["cache"] = cache_metrics.get("backend", "unknown")
        except Exception as exc:
            status["components"]["cache"] = f"error: {str(exc)}"

        try:
            status["performance"] = get_performance_dashboard()
        except Exception as exc:
            status["performance"] = {"error": str(exc)}

        try:
            db = SessionLocal()
            monitoring = MonitoringService(db)
            status["alerts"] = {
                "active_count": len(monitoring.get_active_alerts()),
                "recent_count": len(monitoring.get_active_alerts()),
            }
            db.close()
        except Exception as exc:
            status["alerts"] = {"error": str(exc)}

        return status

    @app.get("/")
    async def root(request: Request):
        """Root endpoint - redirect to dashboard or login."""
        has_token = request.cookies.get("access_token") or (
            request.headers.get("Authorization", "").startswith("Bearer ")
        )
        if has_token:
            return RedirectResponse(url="/dashboard")
        return RedirectResponse(url="/auth/login")

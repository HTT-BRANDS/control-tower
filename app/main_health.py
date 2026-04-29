"""Root, health, and status routes registered by app.main."""

from datetime import UTC, datetime

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

    @app.get("/health/detailed")
    async def detailed_health_check():
        """Detailed health check with component status and pool statistics."""
        from sqlalchemy import text

        from app.core.database import _IS_SQLITE, SessionLocal, _get_engine
        from app.core.scheduler import get_scheduler

        components = {
            "database": "unknown",
            "scheduler": "unknown",
            "cache": "unknown",
            "azure_configured": settings.is_configured,
        }
        pool_stats = {}

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

        try:
            cache_metrics = cache_manager.get_metrics()
            components["cache"] = cache_metrics.get("backend", "unknown")
        except Exception as exc:
            components["cache"] = f"error: {str(exc)}"

        blacklist_backend = get_blacklist_backend()
        components["token_blacklist"] = blacklist_backend
        healthy_values = {"healthy", "running", "memory", "redis", True}

        try:
            cm = cache_manager.get_metrics()
            detailed_cache_metrics = {
                "backend": cm.get("backend", "unknown"),
                "hit_rate_percent": cm.get("hit_rate_percent", 0),
                "hits": cm.get("hits", 0),
                "misses": cm.get("misses", 0),
                "sets": cm.get("sets", 0),
                "deletes": cm.get("deletes", 0),
                "avg_get_time_ms": cm.get("avg_get_time_ms", 0),
            }
        except Exception as exc:
            detailed_cache_metrics = {"error": str(exc)}

        return {
            "status": "healthy"
            if all(value in healthy_values for value in components.values())
            else "degraded",
            "version": settings.app_version,
            "components": components,
            "cache_metrics": detailed_cache_metrics,
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

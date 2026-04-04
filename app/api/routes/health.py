"""Health check API routes.

Provides API-specific health status endpoints for monitoring and load balancers.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.cache import cache_manager
from app.core.config import get_settings
from app.core.database import _IS_SQLITE, _get_engine, get_db
from app.core.scheduler import get_scheduler

router = APIRouter(
    prefix="/api/v1/health",
    tags=["System"],
)


@router.get("")
async def api_health_check(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get API health status.

    Returns the overall health status of the API and its dependencies.
    This endpoint can be accessed without authentication for load balancer health checks,
    but will include additional details when authenticated.

    Returns:
        Health status including:
        - API status (healthy/degraded/unhealthy)
        - Version and environment info
        - Database connectivity status
        - Cache status
        - Scheduler status
        - Azure configuration status
    """
    settings = get_settings()
    checks: dict[str, Any] = {}
    overall_status = "healthy"

    # Check database connectivity with pool stats
    try:
        start = datetime.now(UTC)
        db.execute(text("SELECT 1"))
        db_time_ms = (datetime.now(UTC) - start).total_seconds() * 1000

        pool_stats = {}
        if not _IS_SQLITE:
            engine = _get_engine()
            pool = engine.pool
            pool_stats = {
                "size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
            }

        checks["database"] = {
            "status": "healthy",
            "response_time_ms": round(db_time_ms, 2),
            "pool": pool_stats if pool_stats else "n/a (SQLite)",
        }
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}
        overall_status = "degraded"

    # Check cache
    try:
        await cache_manager.set("health_check", "ok", ttl_seconds=10)
        cache_value = await cache_manager.get("health_check")
        cache_metrics = cache_manager.get_metrics()

        if cache_value == "ok":
            checks["cache"] = {
                "status": "healthy",
                "backend": cache_metrics.get("backend", "unknown"),
                "hit_rate_percent": cache_metrics.get("hit_rate_percent", 0),
            }
        else:
            checks["cache"] = {"status": "degraded", "error": "Cache read/write mismatch"}
            if overall_status == "healthy":
                overall_status = "degraded"
    except Exception as e:
        checks["cache"] = {"status": "unhealthy", "error": str(e)}
        overall_status = "degraded"

    # Check scheduler
    try:
        scheduler = get_scheduler()
        if scheduler and scheduler.running:
            checks["scheduler"] = {
                "status": "healthy",
                "active_jobs": len(scheduler.get_jobs()),
            }
        else:
            checks["scheduler"] = {"status": "degraded", "error": "Scheduler not running"}
            if overall_status == "healthy":
                overall_status = "degraded"
    except Exception as e:
        checks["scheduler"] = {"status": "degraded", "error": str(e)}
        if overall_status == "healthy":
            overall_status = "degraded"

    # Check Azure configuration (without making actual API calls)
    azure_configured = all(
        [
            settings.azure_ad_tenant_id,
            settings.azure_ad_client_id,
            settings.azure_ad_client_secret,
        ]
    )
    checks["azure_configured"] = azure_configured

    response: dict[str, Any] = {
        "status": overall_status,
        "version": settings.app_version,
        "environment": settings.environment,
        "timestamp": datetime.now(UTC).isoformat(),
        "checks": checks,
    }

    # Check if user is authenticated for additional details
    auth_header = request.headers.get("Authorization")
    has_auth = bool(auth_header and auth_header.startswith("Bearer "))
    if has_auth:
        response["authenticated"] = True

    return response


@router.get("/detailed")
async def api_health_check_detailed(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get detailed API health status with component metrics.

    This endpoint provides more comprehensive health information including
    detailed metrics for each component. Can be accessed without authentication
    but some sensitive details may be redacted.

    Returns:
        Detailed health status with metrics for all components.
    """
    settings = get_settings()
    checks: dict[str, Any] = {}
    overall_status = "healthy"

    # Check authentication status
    auth_header = request.headers.get("Authorization")
    has_auth = bool(auth_header and auth_header.startswith("Bearer "))

    # Detailed database check
    try:
        from app.core.database import get_db_stats

        start = datetime.now(UTC)
        db.execute(text("SELECT 1"))
        db_time_ms = (datetime.now(UTC) - start).total_seconds() * 1000
        db_stats = get_db_stats(db)

        pool_stats = {}
        if not _IS_SQLITE:
            engine = _get_engine()
            pool = engine.pool
            pool_stats = {
                "size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
            }

        checks["database"] = {
            "status": "healthy",
            "response_time_ms": round(db_time_ms, 2),
            "pool": pool_stats if pool_stats else "n/a (SQLite)",
            "stats": db_stats if has_auth else "redacted (auth required)",
        }
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}
        overall_status = "degraded"

    # Detailed cache check
    try:
        await cache_manager.set("health_check_detailed", "ok", ttl_seconds=10)
        cache_value = await cache_manager.get("health_check_detailed")
        cache_metrics = cache_manager.get_metrics()

        if cache_value == "ok":
            checks["cache"] = {
                "status": "healthy",
                "backend": cache_metrics.get("backend", "unknown"),
                "hit_rate_percent": cache_metrics.get("hit_rate_percent", 0),
                "hits": cache_metrics.get("hits", 0),
                "misses": cache_metrics.get("misses", 0),
                "sets": cache_metrics.get("sets", 0),
                "deletes": cache_metrics.get("deletes", 0),
                "avg_get_time_ms": cache_metrics.get("avg_get_time_ms", 0),
            }
        else:
            checks["cache"] = {"status": "degraded", "error": "Cache read/write mismatch"}
            if overall_status == "healthy":
                overall_status = "degraded"
    except Exception as e:
        checks["cache"] = {"status": "unhealthy", "error": str(e)}
        overall_status = "degraded"

    # Scheduler details
    try:
        scheduler = get_scheduler()
        if scheduler and scheduler.running:
            jobs = scheduler.get_jobs()
            checks["scheduler"] = {
                "status": "healthy",
                "active_jobs": len(jobs),
                "jobs": [
                    {
                        "id": job.id,
                        "name": job.name,
                        "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                    }
                    for job in jobs[:10]  # Limit job details
                ]
                if has_auth
                else "redacted (auth required)",
            }
        else:
            checks["scheduler"] = {"status": "degraded", "error": "Scheduler not running"}
            if overall_status == "healthy":
                overall_status = "degraded"
    except Exception as e:
        checks["scheduler"] = {"status": "degraded", "error": str(e)}
        if overall_status == "healthy":
            overall_status = "degraded"

    # Azure configuration
    azure_configured = all(
        [
            settings.azure_ad_tenant_id,
            settings.azure_ad_client_id,
            settings.azure_ad_client_secret,
        ]
    )
    checks["azure_configured"] = azure_configured

    # JWT configuration
    checks["jwt_configured"] = bool(settings.jwt_secret_key)

    response: dict[str, Any] = {
        "status": overall_status,
        "version": settings.app_version,
        "environment": settings.environment,
        "timestamp": datetime.now(UTC).isoformat(),
        "checks": checks,
    }

    if has_auth:
        response["authenticated"] = True

    return response

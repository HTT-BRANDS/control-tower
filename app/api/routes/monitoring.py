"""Performance monitoring API routes."""

import time
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.services.azure_client import azure_client_manager
from app.core.auth import User, get_current_user
from app.core.cache import cache_manager
from app.core.database import _get_engine, get_db
from app.core.monitoring import (
    get_cache_stats,
    get_performance_dashboard,
    performance_monitor,
    reset_metrics,
)

router = APIRouter(
    prefix="/monitoring",
    tags=["monitoring"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/performance")
async def get_performance_metrics() -> dict[str, Any]:
    """Get comprehensive performance metrics.

    Returns cache stats, sync job performance, and query metrics.
    """
    return get_performance_dashboard()


@router.get("/cache")
async def get_cache_metrics() -> dict[str, Any]:
    """Get cache hit/miss metrics and statistics."""
    return get_cache_stats()


@router.get("/sync-jobs")
async def get_sync_job_metrics(
    job_type: str | None = None,
    tenant_id: str | None = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Get sync job performance metrics.

    Args:
        job_type: Filter by job type (e.g., 'resources', 'costs')
        tenant_id: Filter by tenant ID
        limit: Maximum number of records to return
    """
    return performance_monitor.get_sync_metrics(job_type, tenant_id, limit)


@router.get("/queries")
async def get_query_metrics(
    slow_only: bool = False,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Get query performance metrics.

    Args:
        slow_only: Only return slow queries (above threshold)
        limit: Maximum number of records to return
    """
    return performance_monitor.get_query_metrics(slow_only, limit)


@router.post("/reset")
async def reset_performance_metrics() -> dict[str, str]:
    """Reset all performance metrics. Use with caution!"""
    reset_metrics()
    return {"status": "Metrics reset successfully"}


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Quick health check with basic performance indicators."""
    cache_metrics = get_cache_stats()
    perf_summary = get_performance_dashboard()

    # Determine health status based on cache hit rate
    hit_rate = cache_metrics.get("hit_rate_percent", 0)
    if hit_rate < 50:
        cache_health = "poor"
    elif hit_rate < 80:
        cache_health = "fair"
    else:
        cache_health = "good"

    return {
        "status": "healthy",
        "cache_health": cache_health,
        "cache_hit_rate": hit_rate,
        "total_sync_jobs": perf_summary["sync_jobs"]["total_jobs"],
        "total_queries": perf_summary["queries"]["total_queries"],
        "slow_queries": perf_summary["queries"]["slow_queries"],
    }


@router.get("/health/deep")
async def health_check_deep(db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Deep health check that verifies all dependencies.

    Checks:
    - Database connectivity with pool statistics
    - Cache availability with hit/miss metrics
    - Azure API connectivity (lightweight call)
    """
    from app.core.config import settings
    from app.core.database import _IS_SQLITE

    checks = {}
    overall_status = "healthy"

    # Check database with pool stats
    try:
        start = time.time()
        db.execute(text("SELECT 1"))
        db_time = (time.time() - start) * 1000

        # Get connection pool statistics
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
            "response_time_ms": round(db_time, 2),
            "pool": pool_stats if pool_stats else "n/a (SQLite)",
        }
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}
        overall_status = "degraded"

    # Check cache with detailed metrics via the shared, timeout-bounded probe.
    # See app/core/cache/manager.py::CacheManager.check_health and ct-czv —
    # the previous inline await pair could hang a liveness probe indefinitely
    # against a wedged Redis backend.
    cache_probe = await cache_manager.check_health()
    checks["cache"] = cache_probe
    if cache_probe["status"] not in {"healthy", "disabled"}:
        overall_status = "degraded"

    # Check Azure (lightweight - just credential check)
    try:
        # Use first tenant for health check
        from app.core.tenants_config import RIVERSIDE_TENANTS

        first_tenant = list(RIVERSIDE_TENANTS.keys())[0]

        # Just verify we can get a credential (don't actually call API)
        _ = azure_client_manager.get_credential(first_tenant)
        checks["azure_auth"] = {"status": "healthy"}
    except Exception as e:
        checks["azure_auth"] = {"status": "degraded", "error": str(e)}
        overall_status = "degraded"

    return {"status": overall_status, "version": settings.app_version, "checks": checks}

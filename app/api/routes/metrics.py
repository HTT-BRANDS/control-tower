"""
Metrics API Routes

Application metrics for monitoring and alerting.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.cache import cache_manager
from app.core.database import get_db

router = APIRouter(
    prefix="/api/v1/metrics",
    tags=["metrics"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/health")
async def health_metrics():
    """Basic health metrics."""
    from app.core.config import settings

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "status": "healthy",
        "version": settings.app_version,
    }


@router.get("/cache")
async def cache_metrics():
    """Cache performance metrics."""
    stats = cache_manager.get_metrics()
    if hasattr(stats, 'to_dict'):
        stats = stats.to_dict()
    elif not isinstance(stats, dict):
        stats = {}
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "hits": stats.get("hits", 0),
        "misses": stats.get("misses", 0),
        "hit_rate": stats.get("hit_rate", 0),
        "size": stats.get("size", 0),
    }


@router.get("/database")
async def database_metrics(db: Session = Depends(get_db)):
    """Database connection metrics."""
    return {"timestamp": datetime.now(UTC).isoformat(), "status": "connected"}

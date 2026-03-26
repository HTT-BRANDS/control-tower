"""
Metrics API Routes

Application metrics for monitoring and alerting.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.cache import cache_manager

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])


@router.get("/health")
async def health_metrics():
    """Basic health metrics."""
    from app.core.config import settings
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "status": "healthy",
        "version": settings.app_version
    }


@router.get("/cache")
async def cache_metrics():
    """Cache performance metrics."""
    stats = await cache_manager.get_stats()
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "hits": stats.get('hits', 0),
        "misses": stats.get('misses', 0),
        "hit_rate": stats.get('hit_rate', 0),
        "size": stats.get('size', 0)
    }


@router.get("/database")
async def database_metrics(db: Session = Depends(get_db)):
    """Database connection metrics."""
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "status": "connected"
    }

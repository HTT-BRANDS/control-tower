"""Performance monitoring and metrics collection.

Provides:
- Cache hit/miss metrics
- Query duration tracking
- Sync job performance metrics (records per second)
- Performance dashboard data
"""

import logging
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, TypeVar

from app.core.cache import cache_manager
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

T = TypeVar("T")


@dataclass
class SyncJobMetrics:
    """Metrics for a sync job execution."""

    job_type: str
    tenant_id: str | None = None
    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    end_time: datetime | None = None
    records_processed: int = 0
    records_inserted: int = 0
    records_updated: int = 0
    errors: int = 0
    duration_seconds: float = 0.0

    @property
    def records_per_second(self) -> float:
        """Calculate processing rate."""
        if self.duration_seconds > 0:
            return self.records_processed / self.duration_seconds
        return 0.0

    def complete(self) -> None:
        """Mark job as complete and calculate duration."""
        self.end_time = datetime.now(UTC)
        self.duration_seconds = (self.end_time - self.start_time).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "job_type": self.job_type,
            "tenant_id": self.tenant_id,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": round(self.duration_seconds, 2),
            "records_processed": self.records_processed,
            "records_inserted": self.records_inserted,
            "records_updated": self.records_updated,
            "errors": self.errors,
            "records_per_second": round(self.records_per_second, 2),
        }


@dataclass
class QueryMetrics:
    """Metrics for database query performance."""

    query_name: str
    duration_ms: float
    rows_returned: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    slow: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_name": self.query_name,
            "duration_ms": round(self.duration_ms, 2),
            "rows_returned": self.rows_returned,
            "timestamp": self.timestamp.isoformat(),
            "slow": self.slow,
        }


class PerformanceMonitor:
    """Centralized performance monitoring."""

    def __init__(self):
        self._sync_metrics: list[SyncJobMetrics] = []
        self._query_metrics: list[QueryMetrics] = []
        self._max_history = 1000  # Keep last N metrics

    def start_sync_job(
        self,
        job_type: str,
        tenant_id: str | None = None,
    ) -> SyncJobMetrics:
        """Start tracking a sync job.

        Usage:
            metrics = monitor.start_sync_job("resources", tenant_id="abc")
            try:
                # ... do work ...
                metrics.records_processed = 1000
            finally:
                metrics.complete()
                monitor.record_sync_job(metrics)
        """
        return SyncJobMetrics(
            job_type=job_type,
            tenant_id=tenant_id,
        )

    def record_sync_job(self, metrics: SyncJobMetrics) -> None:
        """Record completed sync job metrics."""
        if not metrics.end_time:
            metrics.complete()

        self._sync_metrics.append(metrics)

        # Trim history
        if len(self._sync_metrics) > self._max_history:
            self._sync_metrics = self._sync_metrics[-self._max_history :]

        # Log performance summary
        logger.info(
            f"Sync job {metrics.job_type} completed: "
            f"{metrics.records_processed} records in {metrics.duration_seconds:.2f}s "
            f"({metrics.records_per_second:.2f} rec/s)"
        )

    def record_query(
        self,
        query_name: str,
        duration_ms: float,
        rows_returned: int = 0,
    ) -> None:
        """Record query performance metrics."""
        is_slow = duration_ms > settings.slow_query_threshold_ms

        metrics = QueryMetrics(
            query_name=query_name,
            duration_ms=duration_ms,
            rows_returned=rows_returned,
            slow=is_slow,
        )

        self._query_metrics.append(metrics)

        if len(self._query_metrics) > self._max_history:
            self._query_metrics = self._query_metrics[-self._max_history :]

        if is_slow:
            logger.warning(f"Slow query detected: {query_name} took {duration_ms:.2f}ms")

    def get_cache_metrics(self) -> dict[str, Any]:
        """Get current cache metrics."""
        return cache_manager.get_metrics()

    def get_sync_metrics(
        self,
        job_type: str | None = None,
        tenant_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get sync job metrics with optional filtering."""
        metrics = self._sync_metrics

        if job_type:
            metrics = [m for m in metrics if m.job_type == job_type]
        if tenant_id:
            metrics = [m for m in metrics if m.tenant_id == tenant_id]

        return [m.to_dict() for m in metrics[-limit:]]

    def get_query_metrics(
        self,
        slow_only: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get query metrics with optional filtering."""
        metrics = self._query_metrics

        if slow_only:
            metrics = [m for m in metrics if m.slow]

        return [m.to_dict() for m in metrics[-limit:]]

    def get_performance_summary(self) -> dict[str, Any]:
        """Get comprehensive performance summary."""
        cache_metrics = self.get_cache_metrics()

        # Calculate sync job averages
        if self._sync_metrics:
            avg_records_per_second = sum(m.records_per_second for m in self._sync_metrics) / len(
                self._sync_metrics
            )
            avg_duration = sum(m.duration_seconds for m in self._sync_metrics) / len(
                self._sync_metrics
            )
            total_records = sum(m.records_processed for m in self._sync_metrics)
            total_errors = sum(m.errors for m in self._sync_metrics)
        else:
            avg_records_per_second = 0.0
            avg_duration = 0.0
            total_records = 0
            total_errors = 0

        # Calculate query averages
        if self._query_metrics:
            avg_query_time = sum(m.duration_ms for m in self._query_metrics) / len(
                self._query_metrics
            )
            slow_query_count = sum(1 for m in self._query_metrics if m.slow)
        else:
            avg_query_time = 0.0
            slow_query_count = 0

        return {
            "cache": cache_metrics,
            "sync_jobs": {
                "total_jobs": len(self._sync_metrics),
                "avg_records_per_second": round(avg_records_per_second, 2),
                "avg_duration_seconds": round(avg_duration, 2),
                "total_records_processed": total_records,
                "total_errors": total_errors,
            },
            "queries": {
                "total_queries": len(self._query_metrics),
                "avg_duration_ms": round(avg_query_time, 2),
                "slow_queries": slow_query_count,
                "slow_query_threshold_ms": settings.slow_query_threshold_ms,
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self._sync_metrics.clear()
        self._query_metrics.clear()
        logger.info("Performance metrics reset")


# Global monitor instance
performance_monitor = PerformanceMonitor()


@contextmanager
def track_query(query_name: str):
    """Context manager to track query execution time.

    Usage:
        with track_query("get_resources"):
            results = db.query(Resource).all()
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        # Note: rows_returned would need to be captured separately
        performance_monitor.record_query(query_name, duration_ms)


def track_sync_job(job_type: str, tenant_id: str | None = None):
    """Decorator to track sync job performance.

    Usage:
        @track_sync_job("resources", tenant_id="abc")
        async def sync_resources():
            # ... do work ...
            return {"processed": 1000}
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        async def async_wrapper(*args, **kwargs) -> T:
            metrics = performance_monitor.start_sync_job(job_type, tenant_id)
            try:
                result = await func(*args, **kwargs)

                # Try to extract metrics from result
                if isinstance(result, dict):
                    metrics.records_processed = result.get("processed", 0)
                    metrics.records_inserted = result.get("inserted", 0)
                    metrics.records_updated = result.get("updated", 0)
                    metrics.errors = result.get("errors", 0)

                return result
            finally:
                performance_monitor.record_sync_job(metrics)

        def sync_wrapper(*args, **kwargs) -> T:
            metrics = performance_monitor.start_sync_job(job_type, tenant_id)
            try:
                result = func(*args, **kwargs)

                if isinstance(result, dict):
                    metrics.records_processed = result.get("processed", 0)
                    metrics.records_inserted = result.get("inserted", 0)
                    metrics.records_updated = result.get("updated", 0)
                    metrics.errors = result.get("errors", 0)

                return result
            finally:
                performance_monitor.record_sync_job(metrics)

        if __import__("asyncio").iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# Convenience functions
def get_performance_dashboard() -> dict[str, Any]:
    """Get data for performance dashboard."""
    return performance_monitor.get_performance_summary()


def get_cache_stats() -> dict[str, Any]:
    """Get cache statistics."""
    return cache_manager.get_metrics()


def reset_metrics() -> None:
    """Reset all performance metrics."""
    performance_monitor.reset()

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings as _default_get_settings


@dataclass
class CacheMetrics:
    """Cache performance metrics."""

    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    errors: int = 0
    total_get_time_ms: float = 0.0
    total_set_time_ms: float = 0.0

    # Azure Redis specific metrics
    connection_failures: int = 0
    retry_attempts: int = 0
    cluster_failovers: int = 0
    last_health_check: float = 0.0
    avg_connection_time_ms: float = 0.0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate percentage."""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0

    @property
    def avg_get_time_ms(self) -> float:
        """Average get operation time in milliseconds."""
        total = self.hits + self.misses
        return self.total_get_time_ms / total if total > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "deletes": self.deletes,
            "errors": self.errors,
            "hit_rate_percent": round(self.hit_rate, 2),
            "avg_get_time_ms": round(self.avg_get_time_ms, 3),
            "avg_set_time_ms": round(self.total_set_time_ms / max(self.sets, 1), 3),
            "connection_failures": self.connection_failures,
            "retry_attempts": self.retry_attempts,
            "cluster_failovers": self.cluster_failovers,
        }


def get_settings():
    """Return public cache settings provider so legacy monkeypatches still work."""
    public_module = sys.modules.get("app.core.cache")
    if public_module is None:
        return _default_get_settings()
    provider = getattr(public_module, "get_settings", _default_get_settings)
    return provider()


def get_public_cache_manager():
    """Return public cache manager so legacy monkeypatches still work."""
    public_module = sys.modules.get("app.core.cache")
    if public_module is None:
        return None
    return getattr(public_module, "cache_manager", None)

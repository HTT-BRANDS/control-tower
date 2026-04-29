from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from .common import CacheMetrics

logger = logging.getLogger(__name__)


class InMemoryCache:
    """In-memory cache implementation with TTL support."""

    def __init__(self):
        self._cache: dict[str, tuple[Any, float | None]] = {}
        self._lock = asyncio.Lock()
        self._metrics = CacheMetrics()

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        start = time.perf_counter()
        try:
            async with self._lock:
                if key not in self._cache:
                    self._metrics.misses += 1
                    return None

                value, expiry = self._cache[key]
                if expiry is not None and time.time() > expiry:
                    del self._cache[key]
                    self._metrics.misses += 1
                    return None

                self._metrics.hits += 1
                return value
        finally:
            self._metrics.total_get_time_ms += (time.perf_counter() - start) * 1000

    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int | None = None,
    ) -> None:
        """Set value in cache with optional TTL."""
        start = time.perf_counter()
        try:
            async with self._lock:
                expiry = time.time() + ttl_seconds if ttl_seconds else None
                self._cache[key] = (value, expiry)
                self._metrics.sets += 1
        except Exception as e:
            self._metrics.errors += 1
            logger.warning(f"Cache set error: {e}")
        finally:
            self._metrics.total_set_time_ms += (time.perf_counter() - start) * 1000

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._metrics.deletes += 1
                return True
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern (simple substring match)."""
        async with self._lock:
            keys_to_delete = [k for k in self._cache if pattern in k]
            for key in keys_to_delete:
                del self._cache[key]
            self._metrics.deletes += len(keys_to_delete)
            return len(keys_to_delete)

    async def clear(self) -> None:
        """Clear all cached values."""
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._metrics.deletes += count

    def get_metrics(self) -> CacheMetrics:
        """Get cache metrics."""
        return self._metrics

    async def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count removed."""
        now = time.time()
        async with self._lock:
            expired = [
                k for k, (_, expiry) in self._cache.items() if expiry is not None and now > expiry
            ]
            for key in expired:
                del self._cache[key]
            return len(expired)

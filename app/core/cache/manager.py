from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from typing import Any

from .common import get_settings
from .inmemory import InMemoryCache
from .redis import RedisCache

logger = logging.getLogger(__name__)


class CacheManager:
    """Unified cache manager with fallback support."""

    # Hardcoded fallback TTLs for data types not covered by settings.
    # Settings-based TTLs (via CACHE_TTL_* env vars) take precedence.
    _FALLBACK_TTLS: dict[str, int] = {
        "tenant_list": int(os.environ.get("CACHE_TTL_TENANT_LIST", "300")),
        "anomaly_list": int(os.environ.get("CACHE_TTL_ANOMALY_LIST", "600")),
        "recommendation_list": int(os.environ.get("CACHE_TTL_RECOMMENDATION_LIST", "600")),
        "dashboard_data": int(os.environ.get("CACHE_TTL_DASHBOARD_DATA", "300")),
    }

    @staticmethod
    def _resolve_ttl(data_type: str) -> int:
        """Resolve TTL for a data type from settings, with fallbacks.

        Lookup order:
        1. Settings per-type TTL (CACHE_TTL_* env vars) via settings.get_cache_ttl()
        2. _FALLBACK_TTLS for types not in settings
        3. settings.cache_default_ttl_seconds (CACHE_DEFAULT_TTL_SECONDS)

        The result is always clamped to settings.cache_max_ttl_seconds.
        """
        settings = get_settings()
        # settings.get_cache_ttl already returns default & clamps to max
        # for types it knows about. For unknown types it returns the default.
        ttl = settings.get_cache_ttl(data_type)

        # If settings returned the default, check our local fallback table
        # in case we have a more specific value for this data type.
        if ttl == settings.cache_default_ttl_seconds and data_type in CacheManager._FALLBACK_TTLS:
            ttl = CacheManager._FALLBACK_TTLS[data_type]

        return min(ttl, settings.cache_max_ttl_seconds)

    def __init__(self):
        self._cache: InMemoryCache | RedisCache | None = None
        self._cache_type: str = "none"

    async def initialize(self) -> None:
        """Initialize cache backend."""
        settings = get_settings()

        if not settings.cache_enabled:
            logger.info("Cache disabled via configuration")
            self._cache = InMemoryCache()  # Still use memory for structure
            self._cache_type = "memory_disabled"
            return

        # Try Redis first
        if settings.redis_url:
            try:
                self._cache = RedisCache(settings.redis_url)
                await self._cache._get_redis()  # Test connection
                self._cache_type = "redis"
                logger.info("Using Redis cache")
                return
            except Exception as e:
                logger.warning(f"Redis unavailable, using in-memory cache: {e}")

        # Fall back to in-memory
        self._cache = InMemoryCache()
        self._cache_type = "memory"
        logger.info("Using in-memory cache")

    def _get_cache(self) -> InMemoryCache | RedisCache:
        """Get cache instance, initializing if needed."""
        if self._cache is None:
            # Synchronous fallback for non-async contexts
            self._cache = InMemoryCache()
            self._cache_type = "memory_sync"
        return self._cache

    def generate_key(
        self,
        prefix: str,
        tenant_id: str | None = None,
        *args,
        **kwargs,
    ) -> str:
        """Generate a cache key with tenant isolation.

        Args:
            prefix: Key prefix (e.g., 'cost_summary')
            tenant_id: Optional tenant ID for isolation
            *args: Additional positional args to hash
            **kwargs: Additional keyword args to hash
        """
        parts = ["azuregov", prefix]

        if tenant_id:
            parts.append(f"tenant:{tenant_id}")

        # Hash additional args for uniqueness
        if args or kwargs:
            arg_str = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
            arg_hash = hashlib.md5(arg_str.encode(), usedforsecurity=False).hexdigest()[:8]
            parts.append(arg_hash)

        return ":".join(parts)

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        if not get_settings().cache_enabled:
            return None
        return await self._get_cache().get(key)

    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int | None = None,
        data_type: str | None = None,
    ) -> None:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Override TTL, or use data_type default
            data_type: Data type for default TTL lookup
        """
        if not get_settings().cache_enabled:
            return

        if ttl_seconds is None and data_type:
            ttl_seconds = self._resolve_ttl(data_type)

        # Clamp explicit TTL to configured maximum
        if ttl_seconds is not None:
            max_ttl = get_settings().cache_max_ttl_seconds
            ttl_seconds = min(ttl_seconds, max_ttl)

        await self._get_cache().set(key, value, ttl_seconds)

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not get_settings().cache_enabled:
            return False
        return await self._get_cache().delete(key)

    async def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern."""
        if not get_settings().cache_enabled:
            return 0
        return await self._get_cache().delete_pattern(pattern)

    async def invalidate_tenant(self, tenant_id: str) -> int:
        """Invalidate all cache entries for a tenant."""
        pattern = f"tenant:{tenant_id}"
        count = await self.delete_pattern(pattern)
        logger.info(f"Invalidated {count} cache entries for tenant {tenant_id}")
        return count

    async def invalidate_data_type(self, data_type: str) -> int:
        """Invalidate all cache entries for a data type."""
        pattern = f":{data_type}:"
        count = await self.delete_pattern(pattern)
        logger.info(f"Invalidated {count} cache entries for {data_type}")
        return count

    async def clear(self) -> None:
        """Clear all cache entries."""
        if get_settings().cache_enabled:
            await self._get_cache().clear()

    def get_metrics(self) -> dict[str, Any]:
        """Get cache metrics."""
        metrics = self._get_cache().get_metrics()
        return {
            "backend": self._cache_type,
            **metrics.to_dict(),
        }

    async def cleanup(self) -> int:
        """Run cleanup tasks (remove expired entries)."""
        if isinstance(self._cache, InMemoryCache):
            return await self._cache.cleanup_expired()
        return 0

    async def check_health(
        self,
        *,
        probe_key: str = "__cache_health_probe__",
        timeout_seconds: float = 2.0,
    ) -> dict[str, Any]:
        """Run a bounded round-trip probe against the cache backend.

        This is the single source of truth for "is the cache responsive?"
        checks used by /health/detailed, /api/v1/health, /api/v1/health/detailed,
        and the monitoring endpoint. Previously each of those endpoints ran its
        own inline ``await set(...); await get(...)`` pair with no timeout,
        which meant a single slow/wedged Redis connection could hang every
        liveness probe simultaneously (see ct-czv).

        Returns a dict with at minimum a ``status`` key (one of
        ``healthy`` | ``disabled`` | ``degraded`` | ``unhealthy``) plus
        diagnostic context. Always returns; never raises.
        """
        settings = get_settings()
        backend_name = self._cache_type or "unknown"

        if not settings.cache_enabled:
            return {
                "status": "disabled",
                "backend": backend_name,
                "reason": "cache_enabled=False in settings",
            }

        async def _probe() -> tuple[bool, Any]:
            await self.set(probe_key, "ok", ttl_seconds=10)
            return True, await self.get(probe_key)

        try:
            _, value = await asyncio.wait_for(_probe(), timeout=timeout_seconds)
        except TimeoutError:
            return {
                "status": "degraded",
                "backend": backend_name,
                "error": f"cache probe exceeded {timeout_seconds:.1f}s — backend unresponsive",
            }
        except Exception as exc:
            return {
                "status": "unhealthy",
                "backend": backend_name,
                "error": str(exc),
            }

        if value != "ok":
            return {
                "status": "degraded",
                "backend": backend_name,
                "error": "cache read/write mismatch",
            }

        metrics = self.get_metrics()
        return {
            "status": "healthy",
            "backend": metrics.get("backend", backend_name),
            "hit_rate_percent": metrics.get("hit_rate_percent", 0),
            "hits": metrics.get("hits", 0),
            "misses": metrics.get("misses", 0),
            "sets": metrics.get("sets", 0),
            "deletes": metrics.get("deletes", 0),
            "avg_get_time_ms": metrics.get("avg_get_time_ms", 0),
        }


# Global cache manager instance
cache_manager = CacheManager()


# Default TTL values for easy import
def get_cache_ttl(data_type: str) -> int:
    """Get TTL for a data type from settings."""
    return CacheManager._resolve_ttl(data_type)


async def invalidate_on_sync_completion(tenant_id: str | None = None) -> None:
    """Invalidate cache entries after sync completion.

    This should be called after successful sync operations to ensure
    fresh data is served.

    Args:
        tenant_id: Optional tenant ID to invalidate only that tenant's data
    """
    if not get_settings().cache_enabled:
        return

    if tenant_id:
        await cache_manager.invalidate_tenant(tenant_id)
    else:
        # Invalidate all summary data types
        for data_type in [
            "cost_summary",
            "compliance_summary",
            "resource_inventory",
            "identity_summary",
            "riverside_summary",
            "dashboard_data",
        ]:
            await cache_manager.invalidate_data_type(data_type)

    logger.info(f"Cache invalidated after sync for tenant: {tenant_id or 'all'}")


# Convenience functions for common operations
async def get_cached(key: str) -> Any | None:
    """Get value from cache."""
    return await cache_manager.get(key)


async def set_cached(
    key: str,
    value: Any,
    ttl_seconds: int | None = None,
    data_type: str | None = None,
) -> None:
    """Set value in cache."""
    await cache_manager.set(key, value, ttl_seconds, data_type)


async def delete_cached(key: str) -> bool:
    """Delete value from cache."""
    return await cache_manager.delete(key)

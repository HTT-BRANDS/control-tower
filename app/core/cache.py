"""Caching utility with Redis or in-memory fallback.

Provides a unified caching interface that uses Redis when available,
falling back to in-memory dictionary storage for local development.

Features:
- Cache decorator for expensive operations
- Tenant-isolated cache keys
- Configurable TTL per data type
- Cache invalidation on sync completion
- Hit/miss metrics tracking
"""

import asyncio
import functools
import hashlib
import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from app.core.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


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
        }


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
                k for k, (_, expiry) in self._cache.items()
                if expiry is not None and now > expiry
            ]
            for key in expired:
                del self._cache[key]
            return len(expired)


class RedisCache:
    """Redis cache implementation."""

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._redis = None
        self._metrics = CacheMetrics()
        self._lock = asyncio.Lock()
        self._initialized = False

    async def _get_redis(self):
        """Lazy initialization of Redis connection."""
        if not self._initialized:
            async with self._lock:
                if not self._initialized:
                    try:
                        import redis.asyncio as redis
                        self._redis = redis.from_url(
                            self.redis_url,
                            decode_responses=True,
                            socket_connect_timeout=5,
                            socket_timeout=5,
                            retry_on_timeout=True,
                        )
                        # Test connection
                        await self._redis.ping()
                        self._initialized = True
                        logger.info("Redis cache initialized")
                    except ImportError:
                        logger.error("redis package not installed, falling back to memory")
                        raise RuntimeError("Redis not available")
                    except Exception as e:
                        logger.error(f"Redis connection failed: {e}")
                        raise RuntimeError(f"Redis connection failed: {e}")
        return self._redis

    async def get(self, key: str) -> Any | None:
        """Get value from Redis."""
        start = time.perf_counter()
        try:
            redis = await self._get_redis()
            value = await redis.get(key)
            if value is None:
                self._metrics.misses += 1
                return None
            self._metrics.hits += 1
            return json.loads(value)
        except Exception as e:
            self._metrics.errors += 1
            logger.warning(f"Redis get error: {e}")
            return None
        finally:
            self._metrics.total_get_time_ms += (time.perf_counter() - start) * 1000

    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int | None = None,
    ) -> None:
        """Set value in Redis with optional TTL."""
        start = time.perf_counter()
        try:
            redis = await self._get_redis()
            serialized = json.dumps(value, default=str)
            if ttl_seconds:
                await redis.setex(key, ttl_seconds, serialized)
            else:
                await redis.set(key, serialized)
            self._metrics.sets += 1
        except Exception as e:
            self._metrics.errors += 1
            logger.warning(f"Redis set error: {e}")
        finally:
            self._metrics.total_set_time_ms += (time.perf_counter() - start) * 1000

    async def delete(self, key: str) -> bool:
        """Delete key from Redis."""
        try:
            redis = await self._get_redis()
            result = await redis.delete(key)
            if result > 0:
                self._metrics.deletes += 1
            return result > 0
        except Exception as e:
            self._metrics.errors += 1
            logger.warning(f"Redis delete error: {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern."""
        try:
            redis = await self._get_redis()
            keys = await redis.keys(f"*{pattern}*")
            if keys:
                result = await redis.delete(*keys)
                self._metrics.deletes += result
                return result
            return 0
        except Exception as e:
            self._metrics.errors += 1
            logger.warning(f"Redis delete_pattern error: {e}")
            return 0

    async def clear(self) -> None:
        """Clear all cached values."""
        try:
            redis = await self._get_redis()
            await redis.flushdb()
            logger.info("Redis cache cleared")
        except Exception as e:
            self._metrics.errors += 1
            logger.warning(f"Redis clear error: {e}")

    def get_metrics(self) -> CacheMetrics:
        """Get cache metrics."""
        return self._metrics

    async def cleanup_expired(self) -> int:
        """Redis handles expiration automatically."""
        return 0


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
            arg_hash = hashlib.md5(arg_str.encode()).hexdigest()[:8]
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


# Global cache manager instance
cache_manager = CacheManager()


# Default TTL values for easy import
def get_cache_ttl(data_type: str) -> int:
    """Get TTL for a data type from settings."""
    return CacheManager._resolve_ttl(data_type)


def cached(
    data_type: str,
    ttl_seconds: int | None = None,
    key_generator: Callable | None = None,
):
    """Decorator to cache function results.

    Args:
        data_type: Type of data being cached (for TTL lookup)
        ttl_seconds: Override TTL, uses data_type default if None
        key_generator: Optional custom key generator function

    Example:
        @cached("cost_summary", ttl_seconds=3600)
        async def get_cost_summary(self, tenant_id: str | None = None):
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            settings = get_settings()
            if not settings.cache_enabled:
                return await func(*args, **kwargs)

            # Generate cache key
            if key_generator:
                cache_key = key_generator(*args, **kwargs)
            else:
                # Extract tenant_id from kwargs if present
                tenant_id = kwargs.get("tenant_id")
                # Try to find tenant_id in args (common pattern: self, db, tenant_id)
                if tenant_id is None and len(args) >= 3:
                    tenant_id = args[2] if isinstance(args[2], str) else None

                # Build args/kwargs for key hashing (exclude self and db)
                key_args = args[2:] if len(args) > 2 else ()
                cache_key = cache_manager.generate_key(
                    data_type, tenant_id, *key_args, **kwargs
                )

            # Try to get from cache
            cached_value = await cache_manager.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_value

            # Call function and cache result
            result = await func(*args, **kwargs)

            # Only cache successful results (not exceptions)
            if result is not None:
                await cache_manager.set(
                    cache_key, result,
                    ttl_seconds=ttl_seconds,
                    data_type=data_type,
                )
                logger.debug(f"Cache set: {cache_key}")

            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            # For sync functions, use a simpler approach
            # Run async cache operations in the event loop if available
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're in an async context, but function is sync
                    # Just call the function without caching
                    return func(*args, **kwargs)
                else:
                    # Run async wrapper in the loop
                    return loop.run_until_complete(async_wrapper(*args, **kwargs))
            except RuntimeError:
                # No event loop, just call the function
                return func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


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

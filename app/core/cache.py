from __future__ import annotations

import asyncio
import functools
import hashlib
import inspect
import json
import logging
import os
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, TypeVar

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.tenant import Tenant

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


T = TypeVar("T")

# Azure Redis-specific constants
AZURE_REDIS_MAX_RETRIES = int(os.environ.get("AZURE_REDIS_MAX_RETRIES", "3"))
AZURE_REDIS_RETRY_DELAY_BASE = float(os.environ.get("AZURE_REDIS_RETRY_DELAY", "1.0"))
AZURE_REDIS_RETRY_MAX_DELAY = float(os.environ.get("AZURE_REDIS_RETRY_MAX_DELAY", "60.0"))
AZURE_REDIS_CONNECTION_TIMEOUT = int(os.environ.get("AZURE_REDIS_CONNECTION_TIMEOUT", "10"))
AZURE_REDIS_SOCKET_TIMEOUT = int(os.environ.get("AZURE_REDIS_SOCKET_TIMEOUT", "10"))
AZURE_REDIS_HEALTH_CHECK_INTERVAL = int(os.environ.get("AZURE_REDIS_HEALTH_CHECK_INTERVAL", "30"))
AZURE_REDIS_CLUSTER_ENABLED = (
    os.environ.get("AZURE_REDIS_CLUSTER_ENABLED", "false").lower() == "true"
)


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


@dataclass
class AzureRedisDiagnostics:
    """Azure Cache for Redis diagnostics information."""

    shard_count: int = 0
    is_cluster_mode: bool = False
    redis_version: str = "unknown"
    used_memory_mb: float = 0.0
    used_memory_rss_mb: float = 0.0
    connected_clients: int = 0
    blocked_clients: int = 0
    keyspace_hits: int = 0
    keyspace_misses: int = 0
    ops_per_sec: float = 0.0
    network_in_kb: float = 0.0
    network_out_kb: float = 0.0
    replication_lag_seconds: float = 0.0
    is_primary: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert diagnostics to dictionary."""
        return {
            "shard_count": self.shard_count,
            "is_cluster_mode": self.is_cluster_mode,
            "redis_version": self.redis_version,
            "used_memory_mb": round(self.used_memory_mb, 2),
            "used_memory_rss_mb": round(self.used_memory_rss_mb, 2),
            "connected_clients": self.connected_clients,
            "blocked_clients": self.blocked_clients,
            "keyspace_hit_rate": round(
                self.keyspace_hits / max(self.keyspace_hits + self.keyspace_misses, 1) * 100, 2
            ),
            "ops_per_sec": round(self.ops_per_sec, 2),
            "network_in_kb": round(self.network_in_kb, 2),
            "network_out_kb": round(self.network_out_kb, 2),
            "replication_lag_seconds": round(self.replication_lag_seconds, 2),
            "is_primary": self.is_primary,
        }


def azure_redis_retry(max_retries: int = AZURE_REDIS_MAX_RETRIES):
    """Decorator for Azure Redis operations with exponential backoff retry logic.

    Implements Azure best practices for handling Redis connection failures:
    - Exponential backoff with jitter to avoid thundering herd
    - Maximum retry delay cap
    - Specific handling for Azure Redis transient errors
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(self, *args, **kwargs)
                except Exception as e:
                    last_exception = e
                    error_str = str(e).lower()

                    # Don't retry on certain errors
                    if any(
                        err in error_str
                        for err in ["authentication", "unauthorized", "invalid password"]
                    ):
                        logger.error(f"Azure Redis auth error (not retrying): {e}")
                        raise e from None

                    if attempt < max_retries:
                        # Exponential backoff with jitter
                        delay = min(
                            AZURE_REDIS_RETRY_DELAY_BASE * (2**attempt) + random.uniform(0, 1),
                            AZURE_REDIS_RETRY_MAX_DELAY,
                        )
                        logger.warning(
                            f"Azure Redis operation failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                            f"Retrying in {delay:.2f}s..."
                        )
                        if hasattr(self, "_metrics"):
                            self._metrics.retry_attempts += 1
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"Azure Redis operation failed after {max_retries + 1} attempts: {e}"
                        )
                        if hasattr(self, "_metrics"):
                            self._metrics.connection_failures += 1
                        raise last_exception from e

            raise last_exception

        return wrapper

    return decorator


def get_azure_redis_connection_kwargs(redis_url: str) -> dict[str, Any]:
    """Build connection kwargs optimized for Azure Cache for Redis.

    Applies Azure-specific optimizations:
    - Connection pooling for high throughput
    - Health check intervals
    - SSL/TLS configuration for Azure
    - Socket keepalive for long-lived connections
    """
    kwargs: dict[str, Any] = {
        "decode_responses": True,
        "socket_connect_timeout": AZURE_REDIS_CONNECTION_TIMEOUT,
        "socket_timeout": AZURE_REDIS_SOCKET_TIMEOUT,
        "retry_on_timeout": True,
        "health_check_interval": AZURE_REDIS_HEALTH_CHECK_INTERVAL,
        "socket_keepalive": True,
        "socket_keepalive_options": {
            1: 1,  # TCP_KEEPIDLE
            2: 1,  # TCP_KEEPINTVL
            3: 5,  # TCP_KEEPCNT
        },
    }

    # Detect Azure Redis from URL pattern (ssl=True, port 6380)
    if "ssl=true" in redis_url.lower() or ":6380" in redis_url:
        kwargs["ssl"] = True
        kwargs["ssl_cert_reqs"] = "required"
        logger.debug("Azure Redis SSL connection detected")

    # Connection pooling for high-throughput scenarios
    # Azure Redis Premium/Enterprise supports 10K+ connections
    kwargs["max_connections"] = int(os.environ.get("AZURE_REDIS_MAX_CONNECTIONS", "50"))

    return kwargs
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


class RedisCache:
    """Azure Cache for Redis implementation with advanced features.

    Features:
    - Connection multiplexing for high-throughput scenarios
    - Azure Redis clustering support (Premium tier)
    - Automatic failover handling
    - Connection diagnostics and health monitoring
    - Exponential backoff retry logic
    - Azure Redis AUTH token refresh
    """

    def __init__(self, redis_url: str, enable_clustering: bool = AZURE_REDIS_CLUSTER_ENABLED):
        self.redis_url = redis_url
        self._redis: Any = None
        self._cluster_client: Any = None
        self._metrics = CacheMetrics()
        self._lock = asyncio.Lock()
        self._initialized = False
        self._enable_clustering = enable_clustering
        self._is_cluster_mode = False
        self._diagnostics = AzureRedisDiagnostics()
        self._connection_pool: Any = None
        self._health_check_task: asyncio.Task | None = None
        self._shutdown = False

    async def _get_redis(self):
        """Lazy initialization of Redis connection with Azure optimizations."""
        if self._shutdown:
            raise RuntimeError("Redis client has been shut down")

        if not self._initialized:
            async with self._lock:
                if not self._initialized and not self._shutdown:
                    await self._initialize_connection()
        return self._redis

    async def _initialize_connection(self):
        """Initialize Redis connection with Azure-specific optimizations."""
        start_time = time.perf_counter()
        try:
            import redis.asyncio as redis

            # Get Azure-optimized connection kwargs
            conn_kwargs = get_azure_redis_connection_kwargs(self.redis_url)

            # Attempt connection
            self._redis = redis.from_url(self.redis_url, **conn_kwargs)

            # Test connection with ping
            await self._redis.ping()

            # Detect if running in cluster mode
            await self._detect_cluster_mode()

            # Start health check background task
            if AZURE_REDIS_HEALTH_CHECK_INTERVAL > 0:
                self._health_check_task = asyncio.create_task(self._health_check_loop())

            self._initialized = True
            connection_time = (time.perf_counter() - start_time) * 1000
            self._metrics.avg_connection_time_ms = connection_time

            logger.info(
                f"Azure Redis cache initialized "
                f"(cluster_mode={self._is_cluster_mode}, "
                f"connection_time={connection_time:.2f}ms)"
            )

        except ImportError as import_err:
            logger.error("redis package not installed, falling back to memory")
            raise RuntimeError("Redis not available") from import_err
        except Exception as e:
            self._metrics.connection_failures += 1
            logger.error(f"Azure Redis connection failed: {e}")
            raise RuntimeError(f"Azure Redis connection failed: {e}") from e

    async def _detect_cluster_mode(self):
        """Detect if Azure Redis is running in cluster mode."""
        try:
            info = await self._redis.info("server")
            self._diagnostics.redis_version = info.get("redis_version", "unknown")

            # Check for cluster configuration
            cluster_info = await self._redis.info("cluster")
            self._is_cluster_mode = cluster_info.get("cluster_enabled", 0) == 1

            if self._is_cluster_mode:
                self._diagnostics.is_cluster_mode = True
                # Count shards in cluster
                nodes = await self._redis.execute_command("CLUSTER", "NODES")
                shard_count = len([n for n in nodes.split("\n") if "master" in n])
                self._diagnostics.shard_count = shard_count
                logger.info(f"Azure Redis cluster detected with {shard_count} shards")

                # Initialize cluster client for advanced operations
                if self._enable_clustering:
                    await self._init_cluster_client()

        except Exception as e:
            logger.debug(f"Could not detect cluster mode: {e}")
            self._is_cluster_mode = False

    async def _init_cluster_client(self):
        """Initialize Redis Cluster client for multi-shard operations."""
        try:
            from redis.asyncio.cluster import RedisCluster

            # Parse startup nodes from URL
            conn_kwargs = get_azure_redis_connection_kwargs(self.redis_url)
            conn_kwargs["skip_full_coverage_check"] = True
            conn_kwargs["require_full_coverage"] = False

            self._cluster_client = RedisCluster.from_url(self.redis_url, **conn_kwargs)
            logger.info("Azure Redis cluster client initialized")
        except ImportError:
            logger.warning("Redis cluster support not available")
        except Exception as e:
            logger.warning(f"Could not initialize cluster client: {e}")

    async def _health_check_loop(self):
        """Background task for periodic health checks and diagnostics."""
        while not self._shutdown:
            try:
                await asyncio.sleep(AZURE_REDIS_HEALTH_CHECK_INTERVAL)

                if self._redis:
                    # Update diagnostics
                    await self._update_diagnostics()

                    # Check replication lag if in replicated setup
                    if not self._is_cluster_mode:
                        await self._check_replication_lag()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Health check error: {e}")

    async def _update_diagnostics(self):
        """Update Azure Redis diagnostics information."""
        try:
            info = await self._redis.info()

            memory_info = info.get("memory", {})
            self._diagnostics.used_memory_mb = memory_info.get("used_memory", 0) / (1024 * 1024)
            self._diagnostics.used_memory_rss_mb = memory_info.get("used_memory_rss", 0) / (
                1024 * 1024
            )

            client_info = info.get("clients", {})
            self._diagnostics.connected_clients = client_info.get("connected_clients", 0)
            self._diagnostics.blocked_clients = client_info.get("blocked_clients", 0)

            stats_info = info.get("stats", {})
            self._diagnostics.keyspace_hits = stats_info.get("keyspace_hits", 0)
            self._diagnostics.keyspace_misses = stats_info.get("keyspace_misses", 0)
            self._diagnostics.ops_per_sec = stats_info.get("instantaneous_ops_per_sec", 0)

            # Network I/O (in KB)
            self._diagnostics.network_in_kb = stats_info.get("total_net_input_bytes", 0) / 1024
            self._diagnostics.network_out_kb = stats_info.get("total_net_output_bytes", 0) / 1024

            self._diagnostics.last_health_check = time.time()

        except Exception as e:
            logger.debug(f"Could not update diagnostics: {e}")

    async def _check_replication_lag(self):
        """Check replication lag for Azure Redis replicated setup."""
        try:
            info = await self._redis.info("replication")
            role = info.get("role", "unknown")
            self._diagnostics.is_primary = role == "master"

            if role == "slave":
                lag = info.get("master_last_io_seconds_ago", 0)
                self._diagnostics.replication_lag_seconds = lag

                if lag > 60:
                    logger.warning(f"Azure Redis replication lag: {lag}s")

        except Exception as e:
            logger.debug(f"Could not check replication: {e}")

    def get_diagnostics(self) -> AzureRedisDiagnostics:
        """Get Azure Redis diagnostics information."""
        return self._diagnostics

    @azure_redis_retry()
    async def get(self, key: str) -> Any | None:
        """Get value from Azure Redis with retry logic."""
        start = time.perf_counter()
        try:
            redis = await self._get_redis()

            # Use cluster client if available and in cluster mode
            client = (
                self._cluster_client if (self._is_cluster_mode and self._cluster_client) else redis
            )

            value = await client.get(key)
            if value is None:
                self._metrics.misses += 1
                return None
            self._metrics.hits += 1
            return json.loads(value)
        except Exception as e:
            self._metrics.errors += 1
            logger.warning(f"Azure Redis get error: {e}")
            raise  # Let retry decorator handle it
        finally:
            self._metrics.total_get_time_ms += (time.perf_counter() - start) * 1000

    @azure_redis_retry()
    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int | None = None,
    ) -> None:
        """Set value in Azure Redis with optional TTL and retry logic."""
        start = time.perf_counter()
        try:
            redis = await self._get_redis()

            # Use cluster client if available
            client = (
                self._cluster_client if (self._is_cluster_mode and self._cluster_client) else redis
            )

            serialized = json.dumps(value, default=str)
            if ttl_seconds:
                await client.setex(key, ttl_seconds, serialized)
            else:
                await client.set(key, serialized)
            self._metrics.sets += 1
        except Exception as e:
            self._metrics.errors += 1
            logger.warning(f"Azure Redis set error: {e}")
            raise
        finally:
            self._metrics.total_set_time_ms += (time.perf_counter() - start) * 1000

    @azure_redis_retry()
    async def delete(self, key: str) -> bool:
        """Delete key from Azure Redis with retry logic."""
        try:
            redis = await self._get_redis()
            client = (
                self._cluster_client if (self._is_cluster_mode and self._cluster_client) else redis
            )

            result = await client.delete(key)
            if result > 0:
                self._metrics.deletes += 1
            return result > 0
        except Exception as e:
            self._metrics.errors += 1
            logger.warning(f"Azure Redis delete error: {e}")
            raise

    @azure_redis_retry()
    async def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern with Azure Redis optimizations."""
        try:
            redis = await self._get_redis()

            # In cluster mode, we need to scan all shards
            if self._is_cluster_mode and self._cluster_client:
                return await self._delete_pattern_cluster(pattern)

            # Standard mode - use SCAN to avoid blocking
            deleted = 0
            cursor = 0
            while True:
                cursor, keys = await redis.scan(cursor, match=f"*{pattern}*", count=100)
                if keys:
                    result = await redis.delete(*keys)
                    deleted += result
                if cursor == 0:
                    break

            self._metrics.deletes += deleted
            return deleted

        except Exception as e:
            self._metrics.errors += 1
            logger.warning(f"Azure Redis delete_pattern error: {e}")
            raise

    async def _delete_pattern_cluster(self, pattern: str) -> int:
        """Delete keys matching pattern across all cluster shards."""
        if not self._cluster_client:
            return 0

        deleted = 0
        try:
            # Scan and delete across all nodes
            for node in self._cluster_client.get_primaries():
                node_client = node.client
                cursor = 0
                while True:
                    cursor, keys = await node_client.scan(cursor, match=f"*{pattern}*", count=100)
                    if keys:
                        result = await node_client.delete(*keys)
                        deleted += result
                    if cursor == 0:
                        break

            self._metrics.deletes += deleted
            return deleted
        except Exception as e:
            logger.warning(f"Cluster delete_pattern error: {e}")
            raise

    @azure_redis_retry()
    async def clear(self) -> None:
        """Clear all cached values with Azure Redis safety checks."""
        try:
            redis = await self._get_redis()

            # Safety check - don't clear in production without confirmation
            if os.environ.get("ENVIRONMENT") == "production":
                logger.warning("Clearing Redis cache in production environment")

            if self._is_cluster_mode:
                # Flush all shards in cluster
                for node in self._cluster_client.get_primaries():
                    await node.client.flushdb()
            else:
                await redis.flushdb()

            logger.info("Azure Redis cache cleared")
        except Exception as e:
            self._metrics.errors += 1
            logger.warning(f"Azure Redis clear error: {e}")
            raise

    def get_metrics(self) -> CacheMetrics:
        """Get cache metrics."""
        return self._metrics

    async def cleanup_expired(self) -> int:
        """Redis handles expiration automatically."""
        return 0

    async def shutdown(self):
        """Gracefully shutdown Redis connections."""
        self._shutdown = True

        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        if self._redis:
            await self._redis.close()
        if self._cluster_client:
            await self._cluster_client.close()

        logger.info("Azure Redis connections closed")

    # Connection multiplexing methods for high-throughput scenarios
    async def mget(self, keys: list[str]) -> list[Any | None]:
        """Multi-get for batch retrieval - uses connection multiplexing."""
        if not keys:
            return []

        redis = await self._get_redis()
        client = self._cluster_client if (self._is_cluster_mode and self._cluster_client) else redis

        try:
            values = await client.mget(keys)
            results = []
            for v in values:
                if v is None:
                    self._metrics.misses += 1
                    results.append(None)
                else:
                    self._metrics.hits += 1
                    results.append(json.loads(v))
            return results
        except Exception as e:
            self._metrics.errors += 1
            logger.warning(f"Azure Redis mget error: {e}")
            return [None] * len(keys)

    async def mset(self, key_values: dict[str, Any], ttl_seconds: int | None = None) -> None:
        """Multi-set for batch write - uses connection multiplexing."""
        if not key_values:
            return

        redis = await self._get_redis()
        client = self._cluster_client if (self._is_cluster_mode and self._cluster_client) else redis

        try:
            pipe = client.pipeline()
            for key, value in key_values.items():
                serialized = json.dumps(value, default=str)
                if ttl_seconds:
                    pipe.setex(key, ttl_seconds, serialized)
                else:
                    pipe.set(key, serialized)

            await pipe.execute()
            self._metrics.sets += len(key_values)
        except Exception as e:
            self._metrics.errors += 1
            logger.warning(f"Azure Redis mset error: {e}")


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
                # Exclude tenant_id from kwargs to avoid duplicate parameter
                key_kwargs = {k: v for k, v in kwargs.items() if k != "tenant_id"}
                cache_key = cache_manager.generate_key(
                    data_type, tenant_id, *key_args, **key_kwargs
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
                    cache_key,
                    result,
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
        if inspect.iscoroutinefunction(func):
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


# =============================================================================
# Tenant Caching Utilities (N+1 Query Fix)
# =============================================================================


@lru_cache(maxsize=1)
def get_tenant_name_map() -> dict[str, str]:
    """
    Cached tenant ID to name mapping.
    Cache expires every 5 minutes or when explicitly cleared.

    This eliminates the N+1 query problem where we query all tenants
    for each resource lookup.
    """
    db = SessionLocal()
    try:
        return {str(t.id): t.name for t in db.query(Tenant).all()}
    finally:
        db.close()


def clear_tenant_cache():
    """Clear the tenant cache after tenant updates."""
    get_tenant_name_map.cache_clear()


def get_tenant_name(tenant_id: str) -> str | None:
    """Get tenant name by ID (cached).

    Args:
        tenant_id: The tenant ID to look up

    Returns:
        Tenant name or None if not found

    Example:
        # OLD (N+1 problem):
        # for t in db.query(Tenant).all():
        #     if t.id == resource.tenant_id:
        #         tenant_name = t.name

        # NEW (cached):
        tenant_name = get_tenant_name(str(resource.tenant_id))
    """
    return get_tenant_name_map().get(tenant_id)

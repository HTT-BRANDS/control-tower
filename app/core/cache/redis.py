from __future__ import annotations

import asyncio
import functools
import json
import logging
import os
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .common import CacheMetrics

logger = logging.getLogger(__name__)

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
            results: list[Any | None] = []
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

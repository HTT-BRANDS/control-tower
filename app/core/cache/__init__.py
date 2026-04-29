from __future__ import annotations

from app.core.config import get_settings

from .common import CacheMetrics
from .decorator import cached
from .inmemory import InMemoryCache
from .manager import (
    CacheManager,
    cache_manager,
    delete_cached,
    get_cache_ttl,
    get_cached,
    invalidate_on_sync_completion,
    set_cached,
)
from .redis import (
    AZURE_REDIS_CLUSTER_ENABLED,
    AZURE_REDIS_CONNECTION_TIMEOUT,
    AZURE_REDIS_HEALTH_CHECK_INTERVAL,
    AZURE_REDIS_MAX_RETRIES,
    AZURE_REDIS_RETRY_DELAY_BASE,
    AZURE_REDIS_RETRY_MAX_DELAY,
    AZURE_REDIS_SOCKET_TIMEOUT,
    AzureRedisDiagnostics,
    RedisCache,
    azure_redis_retry,
    get_azure_redis_connection_kwargs,
)
from .tenant_names import clear_tenant_cache, get_tenant_name, get_tenant_name_map

__all__ = [
    "AZURE_REDIS_CLUSTER_ENABLED",
    "AZURE_REDIS_CONNECTION_TIMEOUT",
    "AZURE_REDIS_HEALTH_CHECK_INTERVAL",
    "AZURE_REDIS_MAX_RETRIES",
    "AZURE_REDIS_RETRY_DELAY_BASE",
    "AZURE_REDIS_RETRY_MAX_DELAY",
    "AZURE_REDIS_SOCKET_TIMEOUT",
    "AzureRedisDiagnostics",
    "CacheManager",
    "CacheMetrics",
    "InMemoryCache",
    "RedisCache",
    "azure_redis_retry",
    "cache_manager",
    "cached",
    "clear_tenant_cache",
    "delete_cached",
    "get_azure_redis_connection_kwargs",
    "get_cache_ttl",
    "get_cached",
    "get_settings",
    "get_tenant_name",
    "get_tenant_name_map",
    "invalidate_on_sync_completion",
    "set_cached",
]

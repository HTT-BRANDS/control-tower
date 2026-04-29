from __future__ import annotations

import asyncio
import functools
import inspect
import logging
from collections.abc import Callable
from typing import TypeVar

from .common import get_public_cache_manager, get_settings

logger = logging.getLogger(__name__)
T = TypeVar("T")


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
                cache_key = get_public_cache_manager().generate_key(
                    data_type, tenant_id, *key_args, **key_kwargs
                )

            # Try to get from cache
            cached_value = await get_public_cache_manager().get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_value

            # Call function and cache result
            result = await func(*args, **kwargs)

            # Only cache successful results (not exceptions)
            if result is not None:
                await get_public_cache_manager().set(
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

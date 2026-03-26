"""
HTTP Client Configuration with Timeouts

Ensures all external API calls have appropriate timeouts to prevent hanging.
"""

import asyncio
from collections.abc import Coroutine
from typing import TypeVar, Callable, Any
from functools import wraps
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')

# Default timeouts (seconds)
DEFAULT_TIMEOUT = 30.0
AZURE_API_TIMEOUT = 60.0  # Azure APIs can be slow
GRAPH_API_TIMEOUT = 30.0
HEALTH_CHECK_TIMEOUT = 10.0


class TimeoutError(Exception):
    """Custom timeout error with context."""

    def __init__(self, operation: str, timeout: float, details: str = ""):
        self.operation = operation
        self.timeout = timeout
        self.details = details
        super().__init__(f"Operation '{operation}' timed out after {timeout}s: {details}")


async def with_timeout(
    coro: Coroutine[Any, Any, T],
    timeout: float = DEFAULT_TIMEOUT,
    operation_name: str = "operation"
) -> T:
    """
    Execute a coroutine with a timeout.

    Args:
        coro: The coroutine to execute
        timeout: Timeout in seconds
        operation_name: Name for logging/debugging

    Raises:
        TimeoutError: If operation exceeds timeout
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning(
            f"Operation '{operation_name}' timed out after {timeout}s",
            extra={"operation": operation_name, "timeout": timeout}
        )
        raise TimeoutError(operation_name, timeout)


def timeout_async(
    timeout: float = DEFAULT_TIMEOUT,
    operation_name: str | None = None
):
    """
    Decorator to add timeout to async functions.

    Usage:
        @timeout_async(timeout=30.0, operation_name="azure_list_subscriptions")
        async def list_subscriptions(self, tenant_id: str):
            ...
    """
    def decorator(func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., Coroutine[Any, Any, T]]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            name = operation_name or func.__name__
            return await with_timeout(
                func(*args, **kwargs),
                timeout=timeout,
                operation_name=name
            )
        return wrapper
    return decorator


# Pre-configured timeout values for different operations
class Timeouts:
    """Predefined timeout values for common operations."""

    AZURE_LIST = 30.0           # List operations (subscriptions, resources)
    AZURE_GET = 20.0            # Get single resource
    AZURE_CREATE = 120.0        # Create operations (can be slow)
    AZURE_DELETE = 60.0         # Delete operations
    AZURE_POLL = 300.0          # Long-running operation polling

    GRAPH_USER = 15.0           # Get user from Graph
    GRAPH_LIST = 30.0           # List users/groups
    GRAPH_SEARCH = 45.0         # Search operations

    HEALTH_CHECK = 10.0         # Health check calls
    CACHE_OPERATION = 5.0       # Cache get/set
    DB_QUERY = 30.0             # Database queries

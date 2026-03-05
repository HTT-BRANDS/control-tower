"""Retry utilities for Azure API calls."""

import asyncio
import logging
import random
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import TypeVar

from azure.core.exceptions import ClientAuthenticationError, HttpResponseError
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

T = TypeVar('T')

# Retryable HTTP status codes
RETRYABLE_STATUS_CODES = {429, 502, 503, 504}

# Non-retryable exceptions
NON_RETRYABLE_EXCEPTIONS = (
    ClientAuthenticationError,
    ValueError,
    TypeError,
    KeyError,
    SQLAlchemyError,
)


@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""

    max_retries: int = 3
    backoff_factor: float = 1.0
    max_wait: float = 60.0
    retryable_exceptions: tuple = (Exception,)


def is_retryable_error(error: Exception) -> bool:
    """Determine if an error is retryable."""
    # Non-retryable exceptions
    if isinstance(error, NON_RETRYABLE_EXCEPTIONS):
        return False

    # HTTP errors - check status code
    if isinstance(error, HttpResponseError):
        if hasattr(error, 'status_code'):
            return error.status_code in RETRYABLE_STATUS_CODES
        return False

    # Connection and timeout errors are retryable
    error_type = type(error).__name__
    if error_type in ['TimeoutError', 'ConnectionError', 'ConnectionResetError']:
        return True

    # Default: retry unknown errors
    return True


def retry_with_backoff(policy: RetryPolicy | None = None):
    """Decorator that retries async functions with exponential backoff."""
    if policy is None:
        policy = RetryPolicy()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(policy.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # Don't retry non-retryable errors
                    if not is_retryable_error(e):
                        logger.warning(f"Non-retryable error in {func.__name__}: {e}")
                        raise

                    # Last attempt failed
                    if attempt >= policy.max_retries:
                        logger.error(
                            f"{func.__name__} failed after {policy.max_retries + 1} attempts: {e}"
                        )
                        raise

                    # Calculate backoff with jitter
                    wait_time = min(
                        policy.backoff_factor * (2 ** attempt) + random.uniform(0, 1),
                        policy.max_wait,
                    )

                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1}/{policy.max_retries + 1} "
                        f"failed: {e}. Retrying in {wait_time:.1f}s..."
                    )
                    await asyncio.sleep(wait_time)

            # Should never reach here
            raise last_exception if last_exception else RuntimeError("Unexpected retry failure")

        return wrapper

    return decorator


# Predefined policies for different Azure services
COST_SYNC_POLICY = RetryPolicy(max_retries=3, backoff_factor=2.0)
COMPLIANCE_SYNC_POLICY = RetryPolicy(max_retries=3, backoff_factor=1.0)
RESOURCE_SYNC_POLICY = RetryPolicy(max_retries=5, backoff_factor=1.5)
IDENTITY_SYNC_POLICY = RetryPolicy(max_retries=3, backoff_factor=1.0)
GRAPH_API_POLICY = RetryPolicy(max_retries=3, backoff_factor=1.0, max_wait=30.0)
RIVERSIDE_SYNC_POLICY = RetryPolicy(max_retries=3, backoff_factor=1.0, max_wait=30.0)
DMARC_SYNC_POLICY = RetryPolicy(max_retries=3, backoff_factor=1.0, max_wait=30.0)

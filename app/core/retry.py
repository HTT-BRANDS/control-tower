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

T = TypeVar("T")

# Retryable HTTP status codes (transient / rate-limited)
RETRYABLE_STATUS_CODES = {429, 502, 503, 504}

# Non-retryable HTTP status codes (permission / auth / client errors)
# Retrying these is pointless — the same credentials will fail again.
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404, 405, 409, 422}

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


def _get_status_code(error: Exception) -> int | None:
    """Extract HTTP status code from various exception types.

    Azure SDK raises HttpResponseError; httpx raises HTTPStatusError.
    Both carry the status code but on different attributes.
    """
    # Azure SDK: HttpResponseError.status_code
    if isinstance(error, HttpResponseError):
        return getattr(error, "status_code", None)

    # httpx: HTTPStatusError.response.status_code
    if type(error).__name__ == "HTTPStatusError":
        response = getattr(error, "response", None)
        if response is not None:
            return getattr(response, "status_code", None)

    return None


def is_retryable_error(error: Exception) -> bool:
    """Determine if an error is retryable.

    Non-retryable errors include:
    - Explicitly non-retryable exception types (auth errors, programming bugs)
    - HTTP 4xx client errors (401, 403, 404, etc.) — same creds will fail again
    - HttpResponseError without a status_code (can't determine if transient)

    Retryable errors include:
    - HTTP 429 (rate limit), 502, 503, 504 (transient server errors)
    - Timeout / connection errors
    - Unknown errors (safe default: retry once)
    """
    # Non-retryable exceptions
    if isinstance(error, NON_RETRYABLE_EXCEPTIONS):
        return False

    # Extract status code from any HTTP error type
    status_code = _get_status_code(error)

    # HttpResponseError / httpx error WITH a status code
    if status_code is not None:
        # Explicitly non-retryable status codes take precedence
        if status_code in NON_RETRYABLE_STATUS_CODES:
            return False
        # Only known retryable codes get retried
        return status_code in RETRYABLE_STATUS_CODES

    # HttpResponseError WITHOUT a status_code is non-retryable —
    # we can't tell if it's transient or permanent.
    if isinstance(error, HttpResponseError):
        return False

    # Connection and timeout errors are retryable
    error_type = type(error).__name__
    if error_type in ["TimeoutError", "ConnectionError", "ConnectionResetError"]:
        return True

    # Default: retry unknown errors (but only once — the policy controls max)
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
                        policy.backoff_factor * (2**attempt) + random.uniform(0, 1),
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
BUDGET_SYNC_POLICY = RetryPolicy(max_retries=3, backoff_factor=2.0)

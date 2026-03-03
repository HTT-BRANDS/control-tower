"""Rate limiting module for API security.

Provides Redis-based rate limiting with per-endpoint and per-user limits.
Includes automatic cleanup, configurable windows, and graceful fallback.

Also provides TokenBucketRateLimiter for Azure API throttling with support
for multiple Azure service rate limits (ARM, Graph, Cost, Security).
"""

import asyncio
import logging
import random
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class RateLimitStrategy(str, Enum):
    """Rate limiting strategies."""

    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    requests: int = 100
    window_seconds: int = 60
    strategy: RateLimitStrategy = RateLimitStrategy.FIXED_WINDOW
    key_prefix: str = "rl"


# Default rate limits per endpoint type
DEFAULT_LIMITS = {
    "default": RateLimitConfig(requests=100, window_seconds=60),
    "auth": RateLimitConfig(requests=10, window_seconds=60),  # Stricter for auth
    "login": RateLimitConfig(requests=5, window_seconds=300),  # Very strict for login
    "sync": RateLimitConfig(requests=5, window_seconds=60),  # Expensive operations
    "bulk": RateLimitConfig(requests=3, window_seconds=60),
    "exports": RateLimitConfig(requests=10, window_seconds=60),
    "health": RateLimitConfig(requests=30, window_seconds=60),
}


class RateLimiter:
    """Redis-based rate limiter with fallback to in-memory.

    Features:
    - Per-user and per-endpoint rate limiting
    - Configurable time windows and request counts
    - Automatic key expiration
    - Graceful degradation without Redis
    """

    def __init__(self) -> None:
        self._redis = None
        self._memory_cache: dict[str, tuple[int, float]] = {}  # (count, reset_time)
        self._settings = get_settings()
        self._enabled = True
        self._init_redis()

    def _init_redis(self) -> None:
        """Initialize Redis connection if available."""
        if not self._settings.redis_url:
            logger.info("Redis URL not configured, using in-memory rate limiting")
            return

        try:
            import redis.asyncio as redis

            self._redis = redis.from_url(
                self._settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            logger.info("Redis rate limiter initialized")
        except ImportError:
            logger.warning("redis package not installed, using in-memory rate limiting")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}, using in-memory")

    def _get_key(self, identifier: str, endpoint: str) -> str:
        """Generate rate limit key."""
        return f"rate_limit:{endpoint}:{identifier}"

    def _get_client_identifier(self, request: Request) -> str:
        """Extract client identifier from request.

        Uses X-Forwarded-For header if present, falls back to client host.
        Also includes user ID if authenticated.
        """
        # Get IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"

        # Add user ID if authenticated
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return f"{ip}:{user_id}"

        return ip

    async def _check_redis_limit(
        self, key: str, config: RateLimitConfig
    ) -> tuple[bool, dict]:
        """Check rate limit using Redis.

        Returns:
            Tuple of (allowed, headers_dict)
        """
        if not self._redis:
            raise RuntimeError("Redis not available")

        import time

        now = time.time()
        window_start = int(now // config.window_seconds) * config.window_seconds
        window_key = f"{key}:{window_start}"

        pipe = self._redis.pipeline()
        pipe.incr(window_key)
        pipe.expire(window_key, config.window_seconds)
        results = await pipe.execute()

        current_count = results[0]
        remaining = max(0, config.requests - current_count)
        reset_time = window_start + config.window_seconds

        headers = {
            "X-RateLimit-Limit": str(config.requests),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(reset_time)),
            "X-RateLimit-Window": str(config.window_seconds),
        }

        if current_count > config.requests:
            return False, headers

        return True, headers

    def _check_memory_limit(
        self, key: str, config: RateLimitConfig
    ) -> tuple[bool, dict]:
        """Check rate limit using in-memory cache.

        Returns:
            Tuple of (allowed, headers_dict)
        """
        import time

        now = time.time()
        window_start = int(now // config.window_seconds) * config.window_seconds
        window_key = f"{key}:{window_start}"

        # Clean old entries periodically
        if len(self._memory_cache) > 10000:
            self._memory_cache = {
                k: v for k, v in self._memory_cache.items() if v[1] > now
            }

        # Get or create entry
        if window_key not in self._memory_cache:
            self._memory_cache[window_key] = (0, window_start + config.window_seconds)

        count, reset_time = self._memory_cache[window_key]
        count += 1
        self._memory_cache[window_key] = (count, reset_time)

        remaining = max(0, config.requests - count)

        headers = {
            "X-RateLimit-Limit": str(config.requests),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(reset_time)),
            "X-RateLimit-Window": str(config.window_seconds),
        }

        if count > config.requests:
            return False, headers

        return True, headers

    async def is_allowed(
        self, request: Request, config: RateLimitConfig | None = None
    ) -> tuple[bool, dict]:
        """Check if request is within rate limit.

        Args:
            request: FastAPI request object
            config: Rate limit config, uses default if not provided

        Returns:
            Tuple of (allowed, rate_limit_headers)
        """
        if not self._enabled:
            return True, {}

        config = config or DEFAULT_LIMITS["default"]
        identifier = self._get_client_identifier(request)
        endpoint = request.url.path
        key = self._get_key(identifier, endpoint)

        try:
            if self._redis:
                return await self._check_redis_limit(key, config)
            else:
                return self._check_memory_limit(key, config)
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # Fail open - allow request if rate limiting fails
            return True, {}

    async def check_rate_limit(
        self,
        request: Request,
        limit_type: str = "default",
        custom_config: RateLimitConfig | None = None,
    ) -> None:
        """Check rate limit and raise HTTPException if exceeded.

        Args:
            request: FastAPI request object
            limit_type: Type of limit to apply (key in DEFAULT_LIMITS)
            custom_config: Optional custom config override

        Raises:
            HTTPException: 429 Too Many Requests if limit exceeded
        """
        config = custom_config or DEFAULT_LIMITS.get(limit_type, DEFAULT_LIMITS["default"])
        allowed, headers = await self.is_allowed(request, config)

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later.",
                headers={
                    **headers,
                    "Retry-After": str(config.window_seconds),
                },
            )

        # Store headers for response
        request.state.rate_limit_headers = headers

    def get_limit_config(self, endpoint_path: str) -> RateLimitConfig:
        """Get appropriate rate limit config for an endpoint.

        Args:
            endpoint_path: The API endpoint path

        Returns:
            RateLimitConfig for the endpoint
        """
        path_lower = endpoint_path.lower()

        # Check for specific endpoint types
        if any(p in path_lower for p in ["/auth/login", "/token"]):
            return DEFAULT_LIMITS["login"]
        elif "/auth/" in path_lower:
            return DEFAULT_LIMITS["auth"]
        elif "/sync" in path_lower:
            return DEFAULT_LIMITS["sync"]
        elif "/bulk" in path_lower:
            return DEFAULT_LIMITS["bulk"]
        elif "/exports" in path_lower:
            return DEFAULT_LIMITS["exports"]
        elif "/health" in path_lower:
            return DEFAULT_LIMITS["health"]

        return DEFAULT_LIMITS["default"]


# Global rate limiter instance
rate_limiter = RateLimiter()


def rate_limit(
    limit_type: str = "default",
    custom_config: RateLimitConfig | None = None,
) -> Callable:
    """Decorator/FastAPI dependency for rate limiting.

    Usage:
        @router.get("/endpoint")
        async def endpoint(request: Request, _=Depends(rate_limit("default"))):
            pass

    Args:
        limit_type: Type of limit to apply
        custom_config: Optional custom rate limit config

    Returns:
        Dependency callable
    """

    async def check_limit(request: Request) -> None:
        await rate_limiter.check_rate_limit(request, limit_type, custom_config)

    return check_limit


async def apply_rate_limit_headers(request: Request, response: JSONResponse) -> None:
    """Apply rate limit headers to response.

    Call this in a response middleware to add rate limit headers.

    Args:
        request: FastAPI request object
        response: FastAPI response object
    """
    headers = getattr(request.state, "rate_limit_headers", {})
    for key, value in headers.items():
        response.headers[key] = str(value)


# =============================================================================
# Token Bucket Rate Limiter for Azure API Throttling
# =============================================================================

# Azure API Rate Limits
AZURE_API_RATE_LIMITS = {
    "arm": {"rate": 3.3, "description": "Azure Resource Manager"},  # 300ms between requests
    "graph": {"rate": 10.0, "description": "Microsoft Graph API"},  # 100ms between requests
    "cost": {"rate": 0.008, "description": "Cost Management"},  # 125s between requests (1/125)
    "security": {"rate": 0.083, "description": "Security Center"},  # 12s between requests (1/12)
}


class TokenBucketRateLimiter:
    """Token bucket rate limiter for API throttling.

    Implements the token bucket algorithm for smooth rate limiting with burst
    support. Thread-safe for concurrent access.

    Supports Azure API rate limits:
    - ARM: 3.3 req/s (300ms between requests)
    - Graph: 10 req/s (100ms between requests)
    - Cost: 0.008 req/s (125s between requests)
    - Security: 0.083 req/s (12s between requests)

    Args:
        rate_per_second: Tokens added to bucket per second
        burst_size: Maximum tokens in bucket (burst capacity)
    """

    def __init__(self, rate_per_second: float, burst_size: int) -> None:
        """Initialize token bucket rate limiter.

        Args:
            rate_per_second: Tokens added to bucket per second
            burst_size: Maximum tokens in bucket (burst capacity)
        """
        if rate_per_second <= 0:
            raise ValueError("rate_per_second must be positive")
        if burst_size <= 0:
            raise ValueError("burst_size must be positive")

        self.rate_per_second = rate_per_second
        self.burst_size = burst_size
        self._tokens = float(burst_size)  # Start with full bucket
        self._last_update = time.monotonic()
        self._lock = threading.Lock()

    def _add_tokens(self) -> None:
        """Add tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self._last_update
        tokens_to_add = elapsed * self.rate_per_second
        self._tokens = min(self.burst_size, self._tokens + tokens_to_add)
        self._last_update = now

    def acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens from the bucket.

        Args:
            tokens: Number of tokens to acquire (default: 1)

        Returns:
            True if tokens were acquired, False otherwise
        """
        if tokens <= 0:
            raise ValueError("tokens must be positive")
        if tokens > self.burst_size:
            raise ValueError(f"tokens ({tokens}) exceeds burst_size ({self.burst_size})")

        with self._lock:
            self._add_tokens()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    def acquire_with_wait(self, tokens: int = 1, timeout: float | None = None) -> bool:
        """Acquire tokens, waiting if necessary.

        Args:
            tokens: Number of tokens to acquire (default: 1)
            timeout: Maximum time to wait in seconds (None = wait indefinitely)

        Returns:
            True if tokens were acquired, False if timeout reached
        """
        if timeout is not None and timeout < 0:
            raise ValueError("timeout must be non-negative")

        start_time = time.monotonic()

        while True:
            if self.acquire(tokens):
                return True

            # Calculate wait time needed
            wait_needed = self.get_wait_time(tokens)

            if timeout is not None:
                elapsed = time.monotonic() - start_time
                remaining_timeout = timeout - elapsed
                if remaining_timeout <= 0:
                    return False
                wait_needed = min(wait_needed, remaining_timeout)

            time.sleep(wait_needed)

    async def acquire_async(self, tokens: int = 1) -> bool:
        """Async version of acquire - try to acquire tokens without blocking.

        Args:
            tokens: Number of tokens to acquire (default: 1)

        Returns:
            True if tokens were acquired, False otherwise
        """
        return self.acquire(tokens)

    async def acquire_async_with_wait(
        self, tokens: int = 1, timeout: float | None = None
    ) -> bool:
        """Async version of acquire with wait.

        Args:
            tokens: Number of tokens to acquire (default: 1)
            timeout: Maximum time to wait in seconds (None = wait indefinitely)

        Returns:
            True if tokens were acquired, False if timeout reached
        """
        if timeout is not None and timeout < 0:
            raise ValueError("timeout must be non-negative")

        start_time = time.monotonic()

        while True:
            if await self.acquire_async(tokens):
                return True

            wait_needed = self.get_wait_time(tokens)

            if timeout is not None:
                elapsed = time.monotonic() - start_time
                remaining_timeout = timeout - elapsed
                if remaining_timeout <= 0:
                    return False
                wait_needed = min(wait_needed, remaining_timeout)

            await asyncio.sleep(wait_needed)

    def get_wait_time(self, tokens: int = 1) -> float:
        """Get the time needed to wait for tokens to be available.

        Args:
            tokens: Number of tokens needed (default: 1)

        Returns:
            Time in seconds to wait for tokens to be available
        """
        if tokens <= 0:
            raise ValueError("tokens must be positive")

        with self._lock:
            self._add_tokens()
            if self._tokens >= tokens:
                return 0.0

            tokens_needed = tokens - self._tokens
            return tokens_needed / self.rate_per_second

    def get_current_tokens(self) -> float:
        """Get current token count (for testing/monitoring).

        Returns:
            Current number of tokens in the bucket
        """
        with self._lock:
            self._add_tokens()
            return self._tokens


class MultiApiRateLimiter:
    """Manage multiple rate limiters for different Azure APIs.

    Pre-configured limiters for:
    - arm: 3.3 req/s (Azure Resource Manager)
    - graph: 10 req/s (Microsoft Graph API)
    - cost: 0.008 req/s (Cost Management)
    - security: 0.083 req/s (Security Center)
    """

    def __init__(self) -> None:
        """Initialize with pre-configured rate limiters."""
        self._limiters: dict[str, TokenBucketRateLimiter] = {}
        self._lock = threading.Lock()

        # Initialize pre-configured limiters
        for api_name, config in AZURE_API_RATE_LIMITS.items():
            # Burst size = 1 for strict rate limiting, can be adjusted
            burst_size = 3 if config["rate"] >= 1.0 else 1
            self._limiters[api_name] = TokenBucketRateLimiter(
                rate_per_second=config["rate"],
                burst_size=burst_size,
            )

    def get_limiter(self, api_name: str) -> TokenBucketRateLimiter:
        """Get rate limiter for a specific API.

        Args:
            api_name: Name of the API (arm, graph, cost, security)

        Returns:
            TokenBucketRateLimiter for the API

        Raises:
            KeyError: If api_name is not recognized
        """
        if api_name not in self._limiters:
            raise KeyError(
                f"Unknown API: {api_name}. "
                f"Available: {list(self._limiters.keys())}"
            )
        return self._limiters[api_name]

    def acquire(self, api_name: str, tokens: int = 1) -> bool:
        """Try to acquire tokens from a specific API limiter.

        Args:
            api_name: Name of the API
            tokens: Number of tokens to acquire

        Returns:
            True if tokens were acquired, False otherwise
        """
        limiter = self.get_limiter(api_name)
        return limiter.acquire(tokens)

    async def acquire_async(self, api_name: str, tokens: int = 1) -> bool:
        """Async version of acquire.

        Args:
            api_name: Name of the API
            tokens: Number of tokens to acquire

        Returns:
            True if tokens were acquired, False otherwise
        """
        limiter = self.get_limiter(api_name)
        return await limiter.acquire_async(tokens)

    def acquire_with_wait(
        self, api_name: str, tokens: int = 1, timeout: float | None = None
    ) -> bool:
        """Acquire tokens from a specific API limiter, waiting if necessary.

        Args:
            api_name: Name of the API
            tokens: Number of tokens to acquire
            timeout: Maximum time to wait in seconds

        Returns:
            True if tokens were acquired, False if timeout reached
        """
        limiter = self.get_limiter(api_name)
        return limiter.acquire_with_wait(tokens, timeout)

    async def acquire_async_with_wait(
        self, api_name: str, tokens: int = 1, timeout: float | None = None
    ) -> bool:
        """Async version of acquire with wait.

        Args:
            api_name: Name of the API
            tokens: Number of tokens to acquire
            timeout: Maximum time to wait in seconds

        Returns:
            True if tokens were acquired, False if timeout reached
        """
        limiter = self.get_limiter(api_name)
        return await limiter.acquire_async_with_wait(tokens, timeout)

    def acquire_all(self, tokens: int = 1) -> bool:
        """Try to acquire tokens from all API limiters.

        This is useful when you need to respect all API limits simultaneously.

        Args:
            tokens: Number of tokens to acquire from each limiter

        Returns:
            True if tokens were acquired from all limiters, False otherwise
        """
        # First check all limiters without consuming
        for limiter in self._limiters.values():
            if limiter.get_wait_time(tokens) > 0:
                return False

        # Then acquire from all
        for limiter in self._limiters.values():
            if not limiter.acquire(tokens):
                # This shouldn't happen due to the check above
                return False

        return True

    def get_wait_time(self, api_name: str, tokens: int = 1) -> float:
        """Get wait time for a specific API limiter.

        Args:
            api_name: Name of the API
            tokens: Number of tokens needed

        Returns:
            Time in seconds to wait for tokens to be available
        """
        limiter = self.get_limiter(api_name)
        return limiter.get_wait_time(tokens)

    def register_limiter(
        self, api_name: str, limiter: TokenBucketRateLimiter
    ) -> None:
        """Register a custom rate limiter for an API.

        Args:
            api_name: Name of the API
            limiter: TokenBucketRateLimiter instance
        """
        with self._lock:
            self._limiters[api_name] = limiter


# =============================================================================
# Exponential Backoff and Retry Utilities
# =============================================================================


def calculate_backoff(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
) -> float:
    """Calculate exponential backoff with full jitter.

    Uses "full jitter" strategy as recommended by AWS:
    https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/

    Formula: random(0, min(max_delay, base_delay * 2^attempt))

    Args:
        attempt: The retry attempt number (0-indexed)
        base_delay: Base delay in seconds (default: 1.0)
        max_delay: Maximum delay in seconds (default: 60.0)
        jitter: Whether to apply full jitter (default: True)

    Returns:
        Delay in seconds before next retry
    """
    if attempt < 0:
        raise ValueError("attempt must be non-negative")
    if base_delay <= 0:
        raise ValueError("base_delay must be positive")
    if max_delay <= 0:
        raise ValueError("max_delay must be positive")

    # Calculate exponential delay
    exponential_delay = base_delay * (2 ** attempt)
    capped_delay = min(exponential_delay, max_delay)

    if jitter:
        # Full jitter: random value between 0 and capped_delay
        return random.uniform(0, capped_delay)
    else:
        return capped_delay


def extract_retry_after(headers: dict[str, Any], default: float = 60.0) -> float:
    """Extract Retry-After from response headers.

    Handles both delay-seconds format and HTTP-date format.

    Args:
        headers: Response headers dictionary
        default: Default value if Retry-After not present or invalid

    Returns:
        Seconds to wait before retry
    """
    retry_after = headers.get("Retry-After") or headers.get("retry-after")

    if retry_after is None:
        return default

    try:
        # Try parsing as seconds (integer)
        return float(retry_after)
    except (ValueError, TypeError):
        pass

    try:
        # Try parsing as HTTP-date
        from datetime import datetime
        from email.utils import parsedate_to_datetime

        retry_date = parsedate_to_datetime(str(retry_after))
        wait_seconds = (retry_date - datetime.now(retry_date.tzinfo)).total_seconds()
        return max(0, wait_seconds)
    except (ValueError, TypeError, ImportError):
        pass

    logger.warning(f"Could not parse Retry-After header: {retry_after}")
    return default


# =============================================================================
# Global instances
# =============================================================================

# Multi-API rate limiter for Azure services
multi_api_limiter = MultiApiRateLimiter()

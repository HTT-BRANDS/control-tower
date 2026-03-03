"""Resilience patterns combining rate limiting and circuit breaker.

This module provides a unified interface for resilient Azure API calls,
combining token bucket rate limiting, circuit breaker protection, and
exponential backoff retry logic.

Example:
    # Using ResilientAzureClient
    client = ResilientAzureClient(
        api_name="arm",
        rate_limiter=TokenBucketRateLimiter(rate_per_second=3.3, burst_size=3),
        circuit_breaker=CircuitBreaker(name="arm_api")
    )
    result = await client.call_with_retry(my_api_function, arg1, arg2)

    # Using resilient_api_call helper
    result = await resilient_api_call(
        func=my_api_function,
        api_name="graph",
        max_retries=3,
    )
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar

from app.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    circuit_breaker_registry,
)
from app.core.rate_limit import (
    TokenBucketRateLimiter,
    calculate_backoff,
    extract_retry_after,
    multi_api_limiter,
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ResilienceError(Exception):
    """Exception raised when all resilience mechanisms fail."""

    def __init__(
        self,
        message: str,
        api_name: str | None = None,
        attempts: int = 0,
        last_error: Exception | None = None,
    ) -> None:
        """Initialize the error.

        Args:
            message: Error message
            api_name: Name of the API that failed
            attempts: Number of retry attempts made
            last_error: The last exception that caused the failure
        """
        super().__init__(message)
        self.api_name = api_name
        self.attempts = attempts
        self.last_error = last_error


@dataclass
class ResilienceConfig:
    """Configuration for resilient API calls.

    Attributes:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay for exponential backoff
        max_delay: Maximum delay between retries
        jitter: Whether to apply jitter to backoff
        rate_limit_timeout: Timeout for rate limit acquisition
        respect_retry_after: Whether to respect Retry-After header
    """

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    jitter: bool = True
    rate_limit_timeout: float = 300.0  # 5 minutes
    respect_retry_after: bool = True


class ResilientAzureClient:
    """Azure client with rate limiting and circuit breaker protection.

    Combines:
    - TokenBucketRateLimiter for API throttling
    - CircuitBreaker for fault tolerance
    - Exponential backoff for retries

    Example:
        client = ResilientAzureClient(
            api_name="arm",
            rate_limiter=TokenBucketRateLimiter(rate_per_second=3.3, burst_size=3),
            circuit_breaker=CircuitBreaker(name="arm_api")
        )
        result = await client.call(my_function, arg1, arg2)
    """

    def __init__(
        self,
        api_name: str,
        rate_limiter: TokenBucketRateLimiter | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        config: ResilienceConfig | None = None,
    ) -> None:
        """Initialize the resilient client.

        Args:
            api_name: Name of the API (arm, graph, cost, security)
            rate_limiter: Token bucket rate limiter (uses multi_api_limiter if None)
            circuit_breaker: Circuit breaker (uses registry if None)
            config: Resilience configuration
        """
        self.api_name = api_name
        self.config = config or ResilienceConfig()

        # Get or create rate limiter
        if rate_limiter is None:
            try:
                self.rate_limiter = multi_api_limiter.get_limiter(api_name)
            except KeyError:
                # For unknown APIs, create a default rate limiter with reasonable defaults
                self.rate_limiter = TokenBucketRateLimiter(
                    rate_per_second=10.0, burst_size=5
                )
        else:
            self.rate_limiter = rate_limiter

        # Get or create circuit breaker
        if circuit_breaker is None:
            breaker_name = f"{api_name}_api"
            if circuit_breaker_registry.is_registered(breaker_name):
                self.circuit_breaker = circuit_breaker_registry.get(breaker_name)
            else:
                self.circuit_breaker = circuit_breaker_registry.get_or_create(
                    breaker_name,
                    CircuitBreakerConfig(
                        failure_threshold=5,
                        recovery_timeout=300.0,
                        success_threshold=2,
                        expected_exception=(Exception,),
                    ),
                )
        else:
            self.circuit_breaker = circuit_breaker

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute a function with rate limiting and circuit breaker protection.

        Args:
            func: The async function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            The result of the function call

        Raises:
            CircuitBreakerError: If the circuit is open
            Exception: Any exception raised by the function
        """
        # Wait for rate limit token
        acquired = await self.rate_limiter.acquire_async_with_wait(
            tokens=1,
            timeout=self.config.rate_limit_timeout,
        )
        if not acquired:
            raise ResilienceError(
                f"Rate limit timeout for {self.api_name}",
                api_name=self.api_name,
            )

        # Execute with circuit breaker
        return await self.circuit_breaker.call_async(func, *args, **kwargs)

    async def call_with_retry(
        self,
        func: Callable[..., T],
        *args,
        max_retries: int | None = None,
        **kwargs,
    ) -> T:
        """Execute a function with full resilience stack including retries.

        Args:
            func: The async function to execute
            *args: Positional arguments for the function
            max_retries: Override max retries from config
            **kwargs: Keyword arguments for the function

        Returns:
            The result of the function call

        Raises:
            ResilienceError: If all retries are exhausted
            CircuitBreakerError: If the circuit is open
        """
        max_retries = max_retries or self.config.max_retries
        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                return await self.call(func, *args, **kwargs)
            except CircuitBreakerError:
                # Don't retry on circuit breaker open - fail fast
                raise
            except Exception as e:
                last_error = e

                if attempt >= max_retries:
                    # All retries exhausted
                    raise ResilienceError(
                        f"All {max_retries + 1} attempts failed for {self.api_name}",
                        api_name=self.api_name,
                        attempts=attempt + 1,
                        last_error=last_error,
                    ) from last_error

                # Check for Retry-After header
                retry_after = None
                if self.config.respect_retry_after and hasattr(e, "response"):
                    response = getattr(e, "response", None)
                    if response and hasattr(response, "headers"):
                        headers = response.headers
                        retry_after = extract_retry_after(headers, default=None)

                if retry_after is not None:
                    wait_time = retry_after
                    logger.warning(
                        f"{self.api_name}: Retry-After header suggests {wait_time:.1f}s wait"
                    )
                else:
                    # Calculate exponential backoff
                    wait_time = calculate_backoff(
                        attempt=attempt,
                        base_delay=self.config.base_delay,
                        max_delay=self.config.max_delay,
                        jitter=self.config.jitter,
                    )

                logger.warning(
                    f"{self.api_name}: Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                    f"Retrying in {wait_time:.1f}s..."
                )
                await asyncio.sleep(wait_time)

        # Should never reach here
        raise ResilienceError(
            "Unexpected retry loop exit",
            api_name=self.api_name,
            attempts=max_retries + 1,
            last_error=last_error,
        )

    def get_state(self) -> dict[str, Any]:
        """Get current state of the resilient client.

        Returns:
            Dictionary with current state information
        """
        return {
            "api_name": self.api_name,
            "circuit_state": self.circuit_breaker.state.value,
            "circuit_is_open": self.circuit_breaker.is_open,
            "rate_tokens": self.rate_limiter.get_current_tokens(),
            "rate_burst_size": self.rate_limiter.burst_size,
            "rate_per_second": self.rate_limiter.rate_per_second,
        }


async def resilient_api_call(
    func: Callable[..., T],
    api_name: str,
    max_retries: int = 3,
    rate_limiter: TokenBucketRateLimiter | None = None,
    circuit_breaker: CircuitBreaker | None = None,
    config: ResilienceConfig | None = None,
    *args,
    **kwargs,
) -> T:
    """Execute API call with full resilience stack.

    Convenience function that creates a ResilientAzureClient and executes
    the function with all resilience mechanisms.

    Args:
        func: The async function to execute
        api_name: Name of the API (arm, graph, cost, security)
        max_retries: Maximum retry attempts
        rate_limiter: Optional custom rate limiter
        circuit_breaker: Optional custom circuit breaker
        config: Optional resilience configuration
        *args: Positional arguments for the function
        **kwargs: Keyword arguments for the function

    Returns:
        The result of the function call

    Raises:
        ResilienceError: If all retries are exhausted
        CircuitBreakerError: If the circuit is open

    Example:
        result = await resilient_api_call(
            func=fetch_azure_resources,
            api_name="arm",
            max_retries=3,
            subscription_id="12345"
        )
    """
    client = ResilientAzureClient(
        api_name=api_name,
        rate_limiter=rate_limiter,
        circuit_breaker=circuit_breaker,
        config=config or ResilienceConfig(max_retries=max_retries),
    )

    return await client.call_with_retry(func, *args, **kwargs)


# Pre-configured resilient clients for Azure services

def get_arm_client(config: ResilienceConfig | None = None) -> ResilientAzureClient:
    """Get resilient client for Azure Resource Manager API.

    Args:
        config: Optional resilience configuration

    Returns:
        ResilientAzureClient configured for ARM API (3.3 req/s)
    """
    return ResilientAzureClient(
        api_name="arm",
        config=config,
    )


def get_graph_client(config: ResilienceConfig | None = None) -> ResilientAzureClient:
    """Get resilient client for Microsoft Graph API.

    Args:
        config: Optional resilience configuration

    Returns:
        ResilientAzureClient configured for Graph API (10 req/s)
    """
    return ResilientAzureClient(
        api_name="graph",
        config=config,
    )


def get_cost_client(config: ResilienceConfig | None = None) -> ResilientAzureClient:
    """Get resilient client for Cost Management API.

    Args:
        config: Optional resilience configuration

    Returns:
        ResilientAzureClient configured for Cost API (0.008 req/s)
    """
    return ResilientAzureClient(
        api_name="cost",
        config=config,
    )


def get_security_client(config: ResilienceConfig | None = None) -> ResilientAzureClient:
    """Get resilient client for Security Center API.

    Args:
        config: Optional resilience configuration

    Returns:
        ResilientAzureClient configured for Security API (0.083 req/s)
    """
    return ResilientAzureClient(
        api_name="security",
        config=config,
    )

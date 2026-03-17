"""Circuit breaker pattern for Azure API calls."""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import TypeVar

from azure.core.exceptions import HttpResponseError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, requests pass through
    OPEN = "open"  # Failure threshold reached, requests fail fast
    HALF_OPEN = "half_open"  # Testing if service is back to normal


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""

    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    success_threshold: int = 3
    expected_exception: tuple = (Exception,)


class CircuitBreaker:
    """Circuit breaker implementation for resilient API calls.

    The circuit breaker has three states:
    - CLOSED: Normal operation, requests allowed through
    - OPEN: Failure threshold reached, requests fail immediately with CircuitBreakerError
    - HALF_OPEN: Recovery timeout passed, testing if service is back

    State transitions:
    - CLOSED -> OPEN: failures >= failure_threshold
    - OPEN -> HALF_OPEN: recovery_timeout elapsed
    - HALF_OPEN -> CLOSED: success_threshold consecutive successes
    - HALF_OPEN -> OPEN: any failure
    - CLOSED -> CLOSED: failures reset on success
    """

    def __init__(self, name: str, config: CircuitBreakerConfig | None = None) -> None:
        """Initialize circuit breaker.

        Args:
            name: Identifier for this circuit breaker (used in logging)
            config: Configuration parameters, uses defaults if not provided
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()

        # State management
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: datetime | None = None
        self._lock = threading.RLock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        with self._lock:
            return self._state

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (requests should fail fast)."""
        with self._lock:
            return self._state == CircuitState.OPEN

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (requests allowed through)."""
        with self._lock:
            return self._state == CircuitState.CLOSED

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)."""
        with self._lock:
            return self._state == CircuitState.HALF_OPEN

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self._last_failure_time is None:
            return False
        elapsed = (datetime.utcnow() - self._last_failure_time).total_seconds()
        return elapsed >= self.config.recovery_timeout

    def record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    logger.info(
                        f"Circuit breaker '{self.name}' closed after {self._success_count} "
                        "consecutive successes"
                    )
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success in closed state
                if self._failure_count > 0:
                    self._failure_count = 0
                    logger.debug(f"Circuit breaker '{self.name}' failure count reset")

    def record_failure(self) -> None:
        """Record a failed call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.utcnow()

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open state opens the circuit again
                logger.warning(
                    f"Circuit breaker '{self.name}' reopened due to failure in half-open state"
                )
                self._state = CircuitState.OPEN
                self._success_count = 0
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.config.failure_threshold:
                    logger.error(
                        f"Circuit breaker '{self.name}' opened after {self._failure_count} "
                        f"consecutive failures"
                    )
                    self._state = CircuitState.OPEN

    def can_execute(self) -> bool:
        """Check if a call is allowed to execute.

        Returns:
            True if call should proceed, False if circuit is open
        """
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return True
            elif self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    logger.info(
                        f"Circuit breaker '{self.name}' entering half-open state to test recovery"
                    )
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                    return True
                return False
            elif self._state == CircuitState.HALF_OPEN:
                return True
            return True

    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute a function with circuit breaker protection.

        Args:
            func: The function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            The result of the function call

        Raises:
            CircuitBreakerError: If the circuit is open
            Exception: Any exception raised by the function
        """
        if not self.can_execute():
            raise CircuitBreakerError(
                f"Circuit breaker '{self.name}' is open - call rejected",
                breaker_name=self.name,
            )

        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            # Only record failures for expected exception types
            if isinstance(e, self.config.expected_exception):
                self.record_failure()
            raise

    async def call_async(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute an async function with circuit breaker protection.

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
        if not self.can_execute():
            raise CircuitBreakerError(
                f"Circuit breaker '{self.name}' is open - call rejected",
                breaker_name=self.name,
            )

        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            # Only record failures for expected exception types
            if isinstance(e, self.config.expected_exception):
                self.record_failure()
            raise


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is open."""

    def __init__(self, message: str, breaker_name: str | None = None) -> None:
        """Initialize the error.

        Args:
            message: Error message
            breaker_name: Name of the circuit breaker that tripped
        """
        super().__init__(message)
        self.breaker_name = breaker_name


def circuit_breaker(
    breaker: CircuitBreaker | None = None,
    config: CircuitBreakerConfig | None = None,
    name: str | None = None,
):
    """Decorator that wraps functions with circuit breaker protection.

    Args:
        breaker: Existing circuit breaker instance to use
        config: Configuration for new circuit breaker (if breaker not provided)
        name: Name for new circuit breaker (if breaker not provided)

    Returns:
        Decorator function
    """
    if breaker is None:
        if name is None:
            name = "default"
        breaker = CircuitBreaker(name=name, config=config)

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            return await breaker.call_async(func, *args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            return breaker.call(func, *args, **kwargs)

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers.

    Provides centralized management of circuit breakers for different
    services and APIs. Thread-safe for concurrent access.

    Example:
        registry = CircuitBreakerRegistry()
        registry.register("cost_sync", CircuitBreaker(name="cost_sync"))
        breaker = registry.get("cost_sync")
        breaker = registry.get_or_create("identity_sync", CircuitBreakerConfig(...))
    """

    def __init__(self) -> None:
        """Initialize the registry."""
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()

    def register(self, name: str, breaker: CircuitBreaker) -> None:
        """Register a circuit breaker.

        Args:
            name: Unique name for the circuit breaker
            breaker: CircuitBreaker instance to register

        Raises:
            ValueError: If a breaker with the same name already exists
        """
        with self._lock:
            if name in self._breakers:
                raise ValueError(f"Circuit breaker '{name}' already registered")
            self._breakers[name] = breaker
            logger.debug(f"Registered circuit breaker: {name}")

    def get(self, name: str) -> CircuitBreaker:
        """Get a circuit breaker by name.

        Args:
            name: Name of the circuit breaker

        Returns:
            CircuitBreaker instance

        Raises:
            KeyError: If no breaker with the given name exists
        """
        with self._lock:
            if name not in self._breakers:
                raise KeyError(f"Circuit breaker '{name}' not found")
            return self._breakers[name]

    def get_or_create(
        self, name: str, config: CircuitBreakerConfig | None = None
    ) -> CircuitBreaker:
        """Get a circuit breaker or create one if it doesn't exist.

        Args:
            name: Name of the circuit breaker
            config: Configuration for new circuit breaker (if created)

        Returns:
            CircuitBreaker instance (existing or newly created)
        """
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(name=name, config=config)
                logger.debug(f"Created new circuit breaker: {name}")
            return self._breakers[name]

    def unregister(self, name: str) -> bool:
        """Unregister a circuit breaker.

        Args:
            name: Name of the circuit breaker to unregister

        Returns:
            True if the breaker was found and removed, False otherwise
        """
        with self._lock:
            if name in self._breakers:
                del self._breakers[name]
                logger.debug(f"Unregistered circuit breaker: {name}")
                return True
            return False

    def get_all_states(self) -> dict[str, CircuitState]:
        """Get states of all registered circuit breakers.

        Returns:
            Dictionary mapping breaker names to their current states
        """
        with self._lock:
            return {name: breaker.state for name, breaker in self._breakers.items()}

    def reset_all(self) -> None:
        """Reset all circuit breakers to CLOSED state."""
        with self._lock:
            for name, breaker in self._breakers.items():
                # Reset internal state
                with breaker._lock:
                    breaker._state = CircuitState.CLOSED
                    breaker._failure_count = 0
                    breaker._success_count = 0
                    breaker._last_failure_time = None
                logger.info(f"Reset circuit breaker: {name}")

    def reset(self, name: str) -> bool:
        """Reset a specific circuit breaker to CLOSED state.

        Args:
            name: Name of the circuit breaker to reset

        Returns:
            True if the breaker was found and reset, False otherwise
        """
        with self._lock:
            if name not in self._breakers:
                return False

            breaker = self._breakers[name]
            with breaker._lock:
                breaker._state = CircuitState.CLOSED
                breaker._failure_count = 0
                breaker._success_count = 0
                breaker._last_failure_time = None
            logger.info(f"Reset circuit breaker: {name}")
            return True

    def list_breakers(self) -> list[str]:
        """List all registered circuit breaker names.

        Returns:
            List of registered breaker names
        """
        with self._lock:
            return list(self._breakers.keys())

    def is_registered(self, name: str) -> bool:
        """Check if a circuit breaker is registered.

        Args:
            name: Name of the circuit breaker

        Returns:
            True if registered, False otherwise
        """
        with self._lock:
            return name in self._breakers


# Pre-configured circuit breakers for Azure services
COST_SYNC_BREAKER = CircuitBreaker(
    name="cost_sync",
    config=CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=300.0,  # 5 minutes
        success_threshold=2,
        expected_exception=(HttpResponseError, ConnectionError, TimeoutError),
    ),
)

COMPLIANCE_SYNC_BREAKER = CircuitBreaker(
    name="compliance_sync",
    config=CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=300.0,
        success_threshold=2,
        expected_exception=(HttpResponseError, ConnectionError, TimeoutError),
    ),
)

RESOURCE_SYNC_BREAKER = CircuitBreaker(
    name="resource_sync",
    config=CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=300.0,
        success_threshold=2,
        expected_exception=(HttpResponseError, ConnectionError, TimeoutError),
    ),
)

IDENTITY_SYNC_BREAKER = CircuitBreaker(
    name="identity_sync",
    config=CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=180.0,  # 3 minutes
        success_threshold=2,
        expected_exception=(HttpResponseError, ConnectionError, TimeoutError),
    ),
)

GRAPH_API_BREAKER = CircuitBreaker(
    name="graph_api",
    config=CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=300.0,
        success_threshold=2,
        expected_exception=(HttpResponseError, ConnectionError, TimeoutError),
    ),
)

RIVERSIDE_SYNC_BREAKER = CircuitBreaker(
    name="riverside_sync",
    config=CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=300.0,
        success_threshold=2,
        expected_exception=(HttpResponseError, ConnectionError, TimeoutError),
    ),
)

DMARC_SYNC_BREAKER = CircuitBreaker(
    name="dmarc_sync",
    config=CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=300.0,
        success_threshold=2,
        expected_exception=(HttpResponseError, ConnectionError, TimeoutError),
    ),
)

BUDGET_SYNC_BREAKER = CircuitBreaker(
    name="budget_sync",
    config=CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=300.0,
        success_threshold=2,
        expected_exception=(HttpResponseError, ConnectionError, TimeoutError),
    ),
)

# Global registry instance
circuit_breaker_registry = CircuitBreakerRegistry()

# Register pre-configured breakers
circuit_breaker_registry.register("cost_sync", COST_SYNC_BREAKER)
circuit_breaker_registry.register("compliance_sync", COMPLIANCE_SYNC_BREAKER)
circuit_breaker_registry.register("resource_sync", RESOURCE_SYNC_BREAKER)
circuit_breaker_registry.register("identity_sync", IDENTITY_SYNC_BREAKER)
circuit_breaker_registry.register("graph_api", GRAPH_API_BREAKER)
circuit_breaker_registry.register("riverside_sync", RIVERSIDE_SYNC_BREAKER)
circuit_breaker_registry.register("dmarc_sync", DMARC_SYNC_BREAKER)
circuit_breaker_registry.register("budget_sync", BUDGET_SYNC_BREAKER)

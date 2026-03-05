"""Unit tests for circuit breaker module."""

import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitState,
    circuit_breaker_registry,
)


class TestCircuitBreakerInitialization:
    """Test circuit breaker initialization and initial state."""

    def test_circuit_starts_in_closed_state(self):
        """Test that a new circuit breaker starts in CLOSED state."""
        breaker = CircuitBreaker(name="test_breaker")
        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_closed is True
        assert breaker.is_open is False
        assert breaker.is_half_open is False

    def test_circuit_uses_default_config(self):
        """Test that circuit breaker uses default config when none provided."""
        breaker = CircuitBreaker(name="test_breaker")
        assert breaker.config.failure_threshold == 5
        assert breaker.config.recovery_timeout == 60.0
        assert breaker.config.success_threshold == 3
        assert breaker.config.expected_exception == (Exception,)

    def test_circuit_uses_custom_config(self):
        """Test that circuit breaker uses custom config when provided."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=30.0,
            success_threshold=2,
            expected_exception=(ValueError, TypeError),
        )
        breaker = CircuitBreaker(name="test_breaker", config=config)
        assert breaker.config.failure_threshold == 3
        assert breaker.config.recovery_timeout == 30.0
        assert breaker.config.success_threshold == 2
        assert breaker.config.expected_exception == (ValueError, TypeError)


class TestCircuitBreakerClosedState:
    """Test circuit breaker behavior in CLOSED state."""

    def test_stays_closed_after_failures_below_threshold(self):
        """Test that circuit stays CLOSED when failures are below threshold."""
        config = CircuitBreakerConfig(failure_threshold=5)
        breaker = CircuitBreaker(name="test_breaker", config=config)

        # Record 4 failures (below threshold of 5)
        for _ in range(4):
            breaker.record_failure()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_closed is True

    def test_transitions_to_open_after_threshold_failures(self):
        """Test that circuit transitions to OPEN after reaching failure threshold."""
        config = CircuitBreakerConfig(failure_threshold=5)
        breaker = CircuitBreaker(name="test_breaker", config=config)

        # Record exactly threshold number of failures
        for _ in range(5):
            breaker.record_failure()

        assert breaker.state == CircuitState.OPEN
        assert breaker.is_open is True

    def test_record_success_resets_failure_count_in_closed(self):
        """Test that record_success() resets failure count in CLOSED state."""
        config = CircuitBreakerConfig(failure_threshold=5)
        breaker = CircuitBreaker(name="test_breaker", config=config)

        # Record some failures
        for _ in range(3):
            breaker.record_failure()

        # Record a success - should reset failure count
        breaker.record_success()

        # Verify we can add more failures before hitting threshold
        # If failure count was reset, we need 5 more failures to open
        for _ in range(4):
            breaker.record_failure()

        # Should still be closed (only 4 failures since reset)
        assert breaker.state == CircuitState.CLOSED

    def test_successful_call_execution_in_closed_state(self):
        """Test that calls execute successfully in CLOSED state."""
        breaker = CircuitBreaker(name="test_breaker")
        mock_func = MagicMock(return_value="success")

        result = breaker.call(mock_func, "arg1", key="value")

        assert result == "success"
        mock_func.assert_called_once_with("arg1", key="value")
        assert breaker.state == CircuitState.CLOSED


class TestCircuitBreakerOpenState:
    """Test circuit breaker behavior in OPEN state."""

    def test_open_state_raises_circuit_breaker_error(self):
        """Test that OPEN state raises CircuitBreakerError for calls."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker(name="test_breaker", config=config)

        # Open the circuit
        for _ in range(3):
            breaker.record_failure()

        assert breaker.is_open is True

        # Try to make a call - should raise CircuitBreakerError
        mock_func = MagicMock(return_value="success")
        with pytest.raises(CircuitBreakerError) as exc_info:
            breaker.call(mock_func)

        assert "test_breaker" in str(exc_info.value)
        assert "open" in str(exc_info.value).lower()
        mock_func.assert_not_called()

    def test_circuit_breaker_error_has_breaker_name_attribute(self):
        """Test that CircuitBreakerError has circuit_name attribute."""
        config = CircuitBreakerConfig(failure_threshold=2)
        breaker = CircuitBreaker(name="my_circuit", config=config)

        # Open the circuit
        for _ in range(2):
            breaker.record_failure()

        # Try to make a call
        mock_func = MagicMock()
        with pytest.raises(CircuitBreakerError) as exc_info:
            breaker.call(mock_func)

        # Verify breaker_name attribute exists and has correct value
        assert hasattr(exc_info.value, "breaker_name")
        assert exc_info.value.breaker_name == "my_circuit"

    @patch("app.core.circuit_breaker.datetime")
    def test_transitions_to_half_open_after_recovery_timeout(self, mock_datetime):
        """Test that circuit transitions to HALF_OPEN after recovery timeout."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=60.0,
        )
        breaker = CircuitBreaker(name="test_breaker", config=config)

        # Set initial time
        initial_time = datetime(2025, 1, 1, 12, 0, 0)
        mock_datetime.utcnow.return_value = initial_time

        # Open the circuit
        for _ in range(2):
            breaker.record_failure()

        assert breaker.state == CircuitState.OPEN

        # Advance time by 30 seconds (less than recovery timeout)
        mock_datetime.utcnow.return_value = initial_time + timedelta(seconds=30)

        # Circuit should still be OPEN and reject calls
        assert breaker.can_execute() is False
        assert breaker.state == CircuitState.OPEN

        # Advance time by 60+ seconds (past recovery timeout)
        mock_datetime.utcnow.return_value = initial_time + timedelta(seconds=61)

        # Circuit should transition to HALF_OPEN on next check
        assert breaker.can_execute() is True
        assert breaker.state == CircuitState.HALF_OPEN


class TestCircuitBreakerHalfOpenState:
    """Test circuit breaker behavior in HALF_OPEN state."""

    @patch("app.core.circuit_breaker.datetime")
    def test_half_open_to_closed_after_success_threshold(self, mock_datetime):
        """Test that circuit transitions from HALF_OPEN to CLOSED after success threshold."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=60.0,
            success_threshold=3,
        )
        breaker = CircuitBreaker(name="test_breaker", config=config)

        # Set initial time and open the circuit
        initial_time = datetime(2025, 1, 1, 12, 0, 0)
        mock_datetime.utcnow.return_value = initial_time
        for _ in range(2):
            breaker.record_failure()

        assert breaker.state == CircuitState.OPEN

        # Advance time to trigger HALF_OPEN state
        mock_datetime.utcnow.return_value = initial_time + timedelta(seconds=61)
        breaker.can_execute()  # This transitions to HALF_OPEN

        assert breaker.state == CircuitState.HALF_OPEN

        # Record success_threshold - 1 successes (should stay HALF_OPEN)
        for _ in range(2):
            breaker.record_success()

        assert breaker.state == CircuitState.HALF_OPEN

        # Record one more success to reach threshold
        breaker.record_success()

        # Should transition to CLOSED
        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_closed is True

    @patch("app.core.circuit_breaker.datetime")
    def test_half_open_to_open_on_failure(self, mock_datetime):
        """Test that circuit transitions from HALF_OPEN to OPEN on any failure."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=60.0,
            success_threshold=3,
        )
        breaker = CircuitBreaker(name="test_breaker", config=config)

        # Set initial time and open the circuit
        initial_time = datetime(2025, 1, 1, 12, 0, 0)
        mock_datetime.utcnow.return_value = initial_time
        for _ in range(2):
            breaker.record_failure()

        # Transition to HALF_OPEN
        mock_datetime.utcnow.return_value = initial_time + timedelta(seconds=61)
        breaker.can_execute()

        assert breaker.state == CircuitState.HALF_OPEN

        # Record a couple successes first
        breaker.record_success()
        breaker.record_success()
        assert breaker.state == CircuitState.HALF_OPEN

        # Single failure should reopen the circuit
        breaker.record_failure()

        assert breaker.state == CircuitState.OPEN
        assert breaker.is_open is True

    @patch("app.core.circuit_breaker.datetime")
    def test_half_open_allows_call_execution(self, mock_datetime):
        """Test that calls are allowed in HALF_OPEN state."""
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=60.0)
        breaker = CircuitBreaker(name="test_breaker", config=config)

        # Open the circuit
        initial_time = datetime(2025, 1, 1, 12, 0, 0)
        mock_datetime.utcnow.return_value = initial_time
        for _ in range(2):
            breaker.record_failure()

        # Transition to HALF_OPEN
        mock_datetime.utcnow.return_value = initial_time + timedelta(seconds=61)
        breaker.can_execute()

        # Should allow execution in HALF_OPEN state
        mock_func = MagicMock(return_value="success")
        result = breaker.call(mock_func)

        assert result == "success"
        mock_func.assert_called_once()


class TestCircuitBreakerExceptionHandling:
    """Test circuit breaker exception handling."""

    def test_only_expected_exceptions_trigger_failure(self):
        """Test that only expected exceptions trigger circuit breaker failure."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            expected_exception=(ValueError,),
        )
        breaker = CircuitBreaker(name="test_breaker", config=config)

        # Raise an expected exception - should count as failure
        mock_func = MagicMock(side_effect=ValueError("expected"))
        with pytest.raises(ValueError):
            breaker.call(mock_func)

        assert breaker._failure_count == 1

        # Raise an unexpected exception - should NOT count as failure
        mock_func = MagicMock(side_effect=TypeError("unexpected"))
        with pytest.raises(TypeError):
            breaker.call(mock_func)

        # Failure count should still be 1
        assert breaker._failure_count == 1
        assert breaker.state == CircuitState.CLOSED

    def test_exception_propagates_to_caller(self):
        """Test that exceptions from called functions propagate to caller."""
        breaker = CircuitBreaker(name="test_breaker")
        mock_func = MagicMock(side_effect=RuntimeError("Something went wrong"))

        with pytest.raises(RuntimeError, match="Something went wrong"):
            breaker.call(mock_func)


class TestCircuitBreakerRegistry:
    """Test circuit breaker registry functionality."""

    def test_register_and_get_breaker(self):
        """Test registering and retrieving a circuit breaker."""
        registry = circuit_breaker_registry
        breaker = CircuitBreaker(name="new_test_breaker")

        registry.register("new_test_breaker", breaker)
        retrieved = registry.get("new_test_breaker")

        assert retrieved is breaker

    def test_get_nonexistent_breaker_raises_error(self):
        """Test that getting a non-existent breaker raises KeyError."""
        registry = circuit_breaker_registry

        with pytest.raises(KeyError, match="not found"):
            registry.get("does_not_exist_breaker")

    def test_reset_all_resets_all_breakers(self):
        """Test that reset_all() resets all registered circuit breakers."""
        registry = circuit_breaker_registry

        # Create and register some breakers
        breaker1 = CircuitBreaker(
            name="breaker1",
            config=CircuitBreakerConfig(failure_threshold=2),
        )
        breaker2 = CircuitBreaker(
            name="breaker2",
            config=CircuitBreakerConfig(failure_threshold=2),
        )

        registry.register("breaker1", breaker1)
        registry.register("breaker2", breaker2)

        # Open both circuits
        for _ in range(2):
            breaker1.record_failure()
            breaker2.record_failure()

        assert breaker1.state == CircuitState.OPEN
        assert breaker2.state == CircuitState.OPEN

        # Reset all
        registry.reset_all()

        # Both should be CLOSED
        assert breaker1.state == CircuitState.CLOSED
        assert breaker2.state == CircuitState.CLOSED
        assert breaker1._failure_count == 0
        assert breaker2._failure_count == 0

    def test_get_all_states(self):
        """Test getting states of all registered breakers."""
        registry = circuit_breaker_registry

        breaker1 = CircuitBreaker(
            name="state_test_1",
            config=CircuitBreakerConfig(failure_threshold=2),
        )
        breaker2 = CircuitBreaker(name="state_test_2")

        registry.register("state_test_1", breaker1)
        registry.register("state_test_2", breaker2)

        # Open first breaker
        for _ in range(2):
            breaker1.record_failure()

        states = registry.get_all_states()

        assert states["state_test_1"] == CircuitState.OPEN
        assert states["state_test_2"] == CircuitState.CLOSED


class TestCircuitBreakerEdgeCases:
    """Test edge cases and corner scenarios."""

    def test_circuit_breaker_with_zero_failures(self):
        """Test that circuit stays closed with no failures."""
        breaker = CircuitBreaker(name="test_breaker")
        mock_func = MagicMock(return_value="success")

        # Make multiple successful calls
        for _ in range(10):
            result = breaker.call(mock_func)
            assert result == "success"

        assert breaker.state == CircuitState.CLOSED

    def test_concurrent_access_safety(self):
        """Test that circuit breaker is thread-safe."""
        import threading

        breaker = CircuitBreaker(
            name="test_breaker",
            config=CircuitBreakerConfig(failure_threshold=10),
        )

        def record_failures():
            for _ in range(5):
                breaker.record_failure()

        threads = [threading.Thread(target=record_failures) for _ in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Should have recorded all 15 failures safely
        assert breaker._failure_count == 15
        assert breaker.state == CircuitState.OPEN

    @patch("app.core.circuit_breaker.datetime")
    def test_multiple_recovery_attempts(self, mock_datetime):
        """Test multiple recovery attempts after repeated failures."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=60.0,
            success_threshold=2,
        )
        breaker = CircuitBreaker(name="test_breaker", config=config)

        initial_time = datetime(2025, 1, 1, 12, 0, 0)
        mock_datetime.utcnow.return_value = initial_time

        # First failure cycle
        for _ in range(2):
            breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # First recovery attempt
        mock_datetime.utcnow.return_value = initial_time + timedelta(seconds=61)
        breaker.can_execute()
        assert breaker.state == CircuitState.HALF_OPEN

        # Fail again in half-open
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Second recovery attempt
        mock_datetime.utcnow.return_value = initial_time + timedelta(seconds=122)
        breaker.can_execute()
        assert breaker.state == CircuitState.HALF_OPEN

        # This time succeed
        breaker.record_success()
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED

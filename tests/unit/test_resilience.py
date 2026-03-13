"""Unit tests for app.core.resilience module.

Tests resilience patterns including rate limiting, circuit breaker,
and exponential backoff retry logic.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.core.circuit_breaker import CircuitBreakerError, CircuitState
from app.core.resilience import (
    ResilienceConfig,
    ResilienceError,
    ResilientAzureClient,
    resilient_api_call,
)


class TestResilienceError:
    """Tests for ResilienceError exception."""

    def test_resilience_error_has_correct_attributes(self):
        """Test that ResilienceError stores all expected attributes."""
        # Arrange
        api_name = "test_api"
        attempts = 5
        original_error = ValueError("Original failure")
        message = "All retries exhausted"

        # Act
        error = ResilienceError(
            message=message,
            api_name=api_name,
            attempts=attempts,
            last_error=original_error,
        )

        # Assert
        assert str(error) == message
        assert error.api_name == api_name
        assert error.attempts == attempts
        assert error.last_error is original_error

    def test_resilience_error_with_minimal_args(self):
        """Test ResilienceError with only required message argument."""
        # Act
        error = ResilienceError("Something went wrong")

        # Assert
        assert str(error) == "Something went wrong"
        assert error.api_name is None
        assert error.attempts == 0
        assert error.last_error is None


class TestResilienceConfig:
    """Tests for ResilienceConfig dataclass."""

    def test_resilience_config_defaults_are_sensible(self):
        """Test that ResilienceConfig has sensible default values."""
        # Act
        config = ResilienceConfig()

        # Assert - verify all defaults are appropriate
        assert config.max_retries == 3  # Reasonable retry count
        assert config.base_delay == 1.0  # 1 second base delay
        assert config.max_delay == 60.0  # Cap at 1 minute
        assert config.jitter is True  # Prevent thundering herd
        assert config.rate_limit_timeout == 300.0  # 5 minutes
        assert config.respect_retry_after is True  # Honor server guidance

    def test_resilience_config_custom_values(self):
        """Test ResilienceConfig accepts custom values."""
        # Act
        config = ResilienceConfig(
            max_retries=5,
            base_delay=2.0,
            max_delay=120.0,
            jitter=False,
            rate_limit_timeout=600.0,
            respect_retry_after=False,
        )

        # Assert
        assert config.max_retries == 5
        assert config.base_delay == 2.0
        assert config.max_delay == 120.0
        assert config.jitter is False
        assert config.rate_limit_timeout == 600.0
        assert config.respect_retry_after is False


class TestResilientAzureClient:
    """Tests for ResilientAzureClient."""

    @pytest.mark.asyncio
    async def test_call_with_retry_succeeds_on_first_try(self):
        """Test ResilientAzureClient succeeds immediately with healthy function."""
        # Arrange
        mock_rate_limiter = Mock()
        mock_rate_limiter.acquire_async_with_wait = AsyncMock(return_value=True)

        mock_circuit_breaker = Mock()
        mock_func = AsyncMock(return_value="success!")

        # Circuit breaker should properly await and return the result
        async def circuit_call(func, *args, **kwargs):
            return await func(*args, **kwargs)

        mock_circuit_breaker.call_async = AsyncMock(side_effect=circuit_call)

        client = ResilientAzureClient(
            api_name="test_api",
            rate_limiter=mock_rate_limiter,
            circuit_breaker=mock_circuit_breaker,
        )

        # Act
        result = await client.call_with_retry(mock_func, "arg1", key="value")

        # Assert
        assert result == "success!"
        mock_func.assert_called_once_with("arg1", key="value")
        mock_rate_limiter.acquire_async_with_wait.assert_called_once()
        mock_circuit_breaker.call_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_with_retry_retries_on_failure_then_succeeds(self):
        """Test ResilientAzureClient retries transient failures then succeeds."""
        # Arrange
        mock_rate_limiter = Mock()
        mock_rate_limiter.acquire_async_with_wait = AsyncMock(return_value=True)

        mock_circuit_breaker = Mock()
        # Circuit breaker passes through the exception on first two calls, succeeds on third
        call_count = 0

        async def circuit_call_side_effect(func, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise RuntimeError(f"Transient failure {call_count}")
            return await func(*args, **kwargs)

        mock_circuit_breaker.call_async = AsyncMock(side_effect=circuit_call_side_effect)
        mock_func = AsyncMock(return_value="finally worked!")

        config = ResilienceConfig(max_retries=3, base_delay=0.01)  # Fast retry for test
        client = ResilientAzureClient(
            api_name="test_api",
            rate_limiter=mock_rate_limiter,
            circuit_breaker=mock_circuit_breaker,
            config=config,
        )

        # Act
        result = await client.call_with_retry(mock_func)

        # Assert
        assert result == "finally worked!"
        assert call_count == 3  # Failed twice, succeeded on third
        assert mock_rate_limiter.acquire_async_with_wait.call_count == 3

    @pytest.mark.asyncio
    async def test_call_with_retry_raises_resilience_error_after_max_retries(self):
        """Test ResilientAzureClient raises ResilienceError after exhausting retries."""
        # Arrange
        mock_rate_limiter = Mock()
        mock_rate_limiter.acquire_async_with_wait = AsyncMock(return_value=True)

        mock_circuit_breaker = Mock()
        failure_error = RuntimeError("Persistent failure")

        async def always_fail(func, *args, **kwargs):
            raise failure_error

        mock_circuit_breaker.call_async = AsyncMock(side_effect=always_fail)
        mock_func = AsyncMock()

        config = ResilienceConfig(max_retries=2, base_delay=0.01)  # Fast retry for test
        client = ResilientAzureClient(
            api_name="failing_api",
            rate_limiter=mock_rate_limiter,
            circuit_breaker=mock_circuit_breaker,
            config=config,
        )

        # Act & Assert
        with pytest.raises(ResilienceError) as exc_info:
            await client.call_with_retry(mock_func)

        error = exc_info.value
        assert "All 3 attempts failed for failing_api" in str(error)
        assert error.api_name == "failing_api"
        assert error.attempts == 3  # max_retries=2 means 3 total attempts (0, 1, 2)
        assert error.last_error is failure_error
        # Should have tried 3 times (initial + 2 retries)
        assert mock_rate_limiter.acquire_async_with_wait.call_count == 3

    @pytest.mark.asyncio
    async def test_circuit_breaker_integration_open_circuit_fails_immediately(self):
        """Test that OPEN circuit breaker fails immediately without retries."""
        # Arrange
        mock_rate_limiter = Mock()
        mock_rate_limiter.acquire_async_with_wait = AsyncMock(return_value=True)

        mock_circuit_breaker = Mock()
        mock_circuit_breaker.state = CircuitState.OPEN
        mock_circuit_breaker.is_open = True

        # Circuit breaker raises error when open
        circuit_error = CircuitBreakerError(
            "Circuit breaker is OPEN",
            breaker_name="test_circuit",
        )
        mock_circuit_breaker.call_async = AsyncMock(side_effect=circuit_error)

        mock_func = AsyncMock(return_value="should not be called")

        config = ResilienceConfig(max_retries=3, base_delay=0.01)
        client = ResilientAzureClient(
            api_name="test_api",
            rate_limiter=mock_rate_limiter,
            circuit_breaker=mock_circuit_breaker,
            config=config,
        )

        # Act & Assert - Should fail fast without retries
        with pytest.raises(CircuitBreakerError) as exc_info:
            await client.call_with_retry(mock_func)

        # Assert - circuit breaker error propagates immediately
        assert exc_info.value is circuit_error
        # Should only attempt once (no retries on circuit breaker open)
        mock_rate_limiter.acquire_async_with_wait.assert_called_once()
        mock_circuit_breaker.call_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_rate_limit_timeout_raises_resilience_error(self):
        """Test that rate limit timeout raises ResilienceError."""
        # Arrange
        mock_rate_limiter = Mock()
        mock_rate_limiter.acquire_async_with_wait = AsyncMock(return_value=False)  # Timeout!

        mock_circuit_breaker = Mock()
        mock_func = AsyncMock()

        client = ResilientAzureClient(
            api_name="throttled_api",
            rate_limiter=mock_rate_limiter,
            circuit_breaker=mock_circuit_breaker,
        )

        # Act & Assert
        # Note: rate limit timeout actually gets caught and retried by call_with_retry
        # So we expect ResilienceError after retries exhausted, not immediate failure
        with pytest.raises(ResilienceError) as exc_info:
            await client.call_with_retry(mock_func)

        error = exc_info.value
        # The error message will indicate all attempts failed
        assert error.api_name == "throttled_api"
        # Function should not have been called since rate limit failed
        mock_func.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_state_returns_current_state(self):
        """Test get_state returns comprehensive state information."""
        # Arrange
        mock_rate_limiter = Mock()
        mock_rate_limiter.get_current_tokens = Mock(return_value=5.2)
        mock_rate_limiter.burst_size = 10
        mock_rate_limiter.rate_per_second = 3.3

        mock_circuit_breaker = Mock()
        mock_circuit_breaker.state = CircuitState.CLOSED
        mock_circuit_breaker.is_open = False

        client = ResilientAzureClient(
            api_name="arm",
            rate_limiter=mock_rate_limiter,
            circuit_breaker=mock_circuit_breaker,
        )

        # Act
        state = client.get_state()

        # Assert
        assert state["api_name"] == "arm"
        assert state["circuit_state"] == "closed"  # CircuitState.CLOSED.value is lowercase
        assert state["circuit_is_open"] is False
        assert state["rate_tokens"] == 5.2
        assert state["rate_burst_size"] == 10
        assert state["rate_per_second"] == 3.3


class TestResilientApiCallHelper:
    """Tests for resilient_api_call helper function."""

    @pytest.mark.asyncio
    async def test_resilient_api_call_succeeds_with_healthy_function(self):
        """Test resilient_api_call succeeds with a healthy function."""
        # Arrange
        mock_func = AsyncMock(return_value={"data": "success"})

        # Mock the rate limiter and circuit breaker
        mock_rate_limiter = Mock()
        mock_rate_limiter.acquire_async_with_wait = AsyncMock(return_value=True)

        mock_circuit_breaker = Mock()

        # Circuit breaker should properly await and return the result
        async def circuit_call(func, *args, **kwargs):
            return await func(*args, **kwargs)

        mock_circuit_breaker.call_async = AsyncMock(side_effect=circuit_call)

        # Act
        result = await resilient_api_call(
            func=mock_func,
            api_name="test_api",
            max_retries=3,
            rate_limiter=mock_rate_limiter,
            circuit_breaker=mock_circuit_breaker,
            param1="value1",
            param2="value2",
        )

        # Assert
        assert result == {"data": "success"}
        mock_func.assert_called_once_with(param1="value1", param2="value2")

    @pytest.mark.asyncio
    async def test_resilient_api_call_retries_on_transient_failure(self):
        """Test resilient_api_call retries on transient failures."""
        # Arrange
        call_attempts = 0

        async def flaky_function():
            nonlocal call_attempts
            call_attempts += 1
            if call_attempts < 3:
                raise ConnectionError(f"Transient error {call_attempts}")
            return "recovered!"

        mock_rate_limiter = Mock()
        mock_rate_limiter.acquire_async_with_wait = AsyncMock(return_value=True)

        mock_circuit_breaker = Mock()

        # Circuit breaker passes through - first 2 fail, 3rd succeeds
        async def circuit_passthrough(func, *args, **kwargs):
            return await func(*args, **kwargs)

        mock_circuit_breaker.call_async = AsyncMock(side_effect=circuit_passthrough)

        config = ResilienceConfig(max_retries=3, base_delay=0.01)

        # Act
        result = await resilient_api_call(
            func=flaky_function,
            api_name="flaky_api",
            max_retries=3,
            rate_limiter=mock_rate_limiter,
            circuit_breaker=mock_circuit_breaker,
            config=config,
        )

        # Assert
        assert result == "recovered!"
        assert call_attempts == 3  # Failed twice, succeeded on third

    @pytest.mark.asyncio
    async def test_resilient_api_call_propagates_resilience_error(self):
        """Test resilient_api_call propagates ResilienceError after exhaustion."""

        # Arrange
        async def always_fail():
            raise ValueError("Persistent error")

        mock_rate_limiter = Mock()
        mock_rate_limiter.acquire_async_with_wait = AsyncMock(return_value=True)

        mock_circuit_breaker = Mock()

        async def circuit_passthrough(func, *args, **kwargs):
            return await func(*args, **kwargs)

        mock_circuit_breaker.call_async = AsyncMock(side_effect=circuit_passthrough)

        config = ResilienceConfig(max_retries=2, base_delay=0.01)

        # Act & Assert
        with pytest.raises(ResilienceError) as exc_info:
            await resilient_api_call(
                func=always_fail,
                api_name="doomed_api",
                max_retries=2,
                rate_limiter=mock_rate_limiter,
                circuit_breaker=mock_circuit_breaker,
                config=config,
            )

        error = exc_info.value
        assert error.api_name == "doomed_api"
        assert error.attempts == 3  # 2 retries + 1 initial = 3 attempts
        assert isinstance(error.last_error, ValueError)


class TestResilientAzureClientSync:
    """Tests for ResilientAzureClient with synchronous functions."""

    @pytest.mark.asyncio
    async def test_call_with_sync_function_wraps_in_thread(self):
        """Test ResilientAzureClient handles sync functions via asyncio.to_thread."""
        # Arrange
        mock_rate_limiter = Mock()
        mock_rate_limiter.acquire_async_with_wait = AsyncMock(return_value=True)

        mock_circuit_breaker = Mock()

        # Mock circuit breaker to call the wrapped async function
        async def circuit_call_side_effect(func, *args, **kwargs):
            # The func here will be the async wrapper
            return await func(*args, **kwargs)

        mock_circuit_breaker.call_async = AsyncMock(side_effect=circuit_call_side_effect)

        # Create a SYNC function (not async)
        def sync_function(value):
            return f"sync result: {value}"

        client = ResilientAzureClient(
            api_name="test_api",
            rate_limiter=mock_rate_limiter,
            circuit_breaker=mock_circuit_breaker,
        )

        # Act - call_with_retry should handle sync function
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = "sync result: test"
            result = await client.call_with_retry(sync_function, "test")

        # Assert
        assert result == "sync result: test"
        mock_to_thread.assert_called_once_with(sync_function, "test")

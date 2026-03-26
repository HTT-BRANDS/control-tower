"""
Tests for HTTP Client Timeout utilities
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from app.core.http_client import (
    with_timeout,
    timeout_async,
    TimeoutError,
    Timeouts,
    DEFAULT_TIMEOUT
)


class TestWithTimeout:
    """Test the with_timeout utility function."""

    @pytest.mark.asyncio
    async def test_successful_completion(self):
        """Coro completes before timeout - returns result."""
        async def quick_task():
            return "success"

        result = await with_timeout(
            quick_task(),
            timeout=1.0,
            operation_name="test_op"
        )

        assert result == "success"

    @pytest.mark.asyncio
    async def test_timeout_raises_custom_error(self):
        """Coro exceeds timeout - raises TimeoutError."""
        async def slow_task():
            await asyncio.sleep(10)
            return "never"

        with pytest.raises(TimeoutError) as exc_info:
            await with_timeout(
                slow_task(),
                timeout=0.01,
                operation_name="slow_test"
            )

        assert "slow_test" in str(exc_info.value)
        assert "0.01s" in str(exc_info.value)
        assert exc_info.value.operation == "slow_test"
        assert exc_info.value.timeout == 0.01

    @pytest.mark.asyncio
    async def test_exception_propagation(self):
        """Coro raises exception - exception propagates."""
        async def failing_task():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            await with_timeout(
                failing_task(),
                timeout=1.0,
                operation_name="failing_test"
            )

    @pytest.mark.asyncio
    async def test_logging_on_timeout(self, caplog):
        """Timeout is logged at warning level."""
        async def slow_task():
            await asyncio.sleep(10)

        with pytest.raises(TimeoutError):
            with caplog.at_level("WARNING"):
                await with_timeout(
                    slow_task(),
                    timeout=0.01,
                    operation_name="logged_op"
                )

        assert "logged_op" in caplog.text
        assert "timed out" in caplog.text


class TestTimeoutAsyncDecorator:
    """Test the @timeout_async decorator."""

    @pytest.mark.asyncio
    async def test_decorator_success(self):
        """Decorated function completes successfully."""
        @timeout_async(timeout=1.0)
        async def my_function(x: int) -> int:
            return x * 2

        result = await my_function(5)
        assert result == 10

    @pytest.mark.asyncio
    async def test_decorator_timeout(self):
        """Decorated function times out."""
        @timeout_async(timeout=0.01, operation_name="decorated_slow")
        async def slow_function():
            await asyncio.sleep(10)
            return "never"

        with pytest.raises(TimeoutError) as exc_info:
            await slow_function()

        assert "decorated_slow" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_decorator_uses_function_name(self):
        """Decorator uses function name when operation_name not provided."""
        @timeout_async(timeout=0.01)
        async def named_function():
            await asyncio.sleep(10)

        with pytest.raises(TimeoutError) as exc_info:
            await named_function()

        assert "named_function" in str(exc_info.value)


class TestTimeoutsClass:
    """Test the Timeouts predefined values."""

    def test_timeouts_exist(self):
        """All expected timeout constants exist."""
        assert hasattr(Timeouts, "AZURE_LIST")
        assert hasattr(Timeouts, "AZURE_GET")
        assert hasattr(Timeouts, "AZURE_CREATE")
        assert hasattr(Timeouts, "AZURE_DELETE")
        assert hasattr(Timeouts, "AZURE_POLL")
        assert hasattr(Timeouts, "GRAPH_USER")
        assert hasattr(Timeouts, "GRAPH_LIST")
        assert hasattr(Timeouts, "GRAPH_SEARCH")
        assert hasattr(Timeouts, "HEALTH_CHECK")
        assert hasattr(Timeouts, "CACHE_OPERATION")
        assert hasattr(Timeouts, "DB_QUERY")

    def test_timeout_values_reasonable(self):
        """Timeout values are reasonable positive numbers."""
        timeouts = [
            Timeouts.AZURE_LIST,
            Timeouts.AZURE_GET,
            Timeouts.AZURE_CREATE,
            Timeouts.AZURE_DELETE,
            Timeouts.AZURE_POLL,
            Timeouts.GRAPH_USER,
            Timeouts.HEALTH_CHECK,
            Timeouts.CACHE_OPERATION,
            Timeouts.DB_QUERY,
        ]

        for timeout in timeouts:
            assert timeout > 0
            assert timeout < 600  # No timeout should be > 10 minutes

    def test_create_operations_have_longer_timeout(self):
        """Create operations have longer timeout than gets."""
        assert Timeouts.AZURE_CREATE > Timeouts.AZURE_GET

    def test_health_check_is_fast(self):
        """Health check timeout is short."""
        assert Timeouts.HEALTH_CHECK <= 10.0

    def test_cache_operation_is_fast(self):
        """Cache operations should be fast."""
        assert Timeouts.CACHE_OPERATION <= 5.0

"""
Tests for app/core/http_client.py – HTTP Client timeout utilities.

Covers module-level constants, TimeoutError formatting,
with_timeout() behaviour, the @timeout_async decorator,
and Timeouts predefined values.
"""

import asyncio

import pytest

from app.core.http_client import (
    AZURE_API_TIMEOUT,
    DEFAULT_TIMEOUT,
    GRAPH_API_TIMEOUT,
    HEALTH_CHECK_TIMEOUT,
    TimeoutError,
    Timeouts,
    timeout_async,
    with_timeout,
)

# ── Module-level constants ───────────────────────────────────────────


class TestModuleConstants:
    """Module-level timeout constants are sensible defaults."""

    def test_default_timeout_value(self):
        assert DEFAULT_TIMEOUT == 30.0

    def test_azure_api_timeout_value(self):
        assert AZURE_API_TIMEOUT == 60.0

    def test_graph_api_timeout_value(self):
        assert GRAPH_API_TIMEOUT == 30.0

    def test_health_check_timeout_value(self):
        assert HEALTH_CHECK_TIMEOUT == 10.0

    def test_all_constants_are_positive_floats(self):
        for val in (DEFAULT_TIMEOUT, AZURE_API_TIMEOUT, GRAPH_API_TIMEOUT, HEALTH_CHECK_TIMEOUT):
            assert isinstance(val, float)
            assert val > 0


# ── TimeoutError ─────────────────────────────────────────────────────


class TestTimeoutError:
    """Custom TimeoutError carries structured context."""

    def test_message_without_details(self):
        err = TimeoutError("fetch_users", 15.0)
        assert str(err) == "Operation 'fetch_users' timed out after 15.0s: "

    def test_message_with_details(self):
        err = TimeoutError("fetch_users", 15.0, details="Graph returned 504")
        assert str(err) == "Operation 'fetch_users' timed out after 15.0s: Graph returned 504"

    def test_attributes_stored(self):
        err = TimeoutError("op", 5.0, "extra")
        assert err.operation == "op"
        assert err.timeout == 5.0
        assert err.details == "extra"

    def test_is_exception_subclass(self):
        assert issubclass(TimeoutError, Exception)

    def test_details_defaults_to_empty_string(self):
        err = TimeoutError("op", 1.0)
        assert err.details == ""


# ── with_timeout ─────────────────────────────────────────────────────


class TestWithTimeout:
    """Async with_timeout wrapper."""

    async def test_returns_result_for_fast_coro(self):
        async def quick():
            return 42

        result = await with_timeout(quick(), timeout=1.0, operation_name="quick")
        assert result == 42

    async def test_raises_timeout_error_for_slow_coro(self):
        async def slow():
            await asyncio.sleep(10)

        with pytest.raises(TimeoutError) as exc_info:
            await with_timeout(slow(), timeout=0.01, operation_name="slow_op")

        assert exc_info.value.operation == "slow_op"
        assert exc_info.value.timeout == 0.01

    async def test_uses_default_timeout_and_operation_name(self):
        """When called with only coro, defaults are applied (no crash)."""

        async def instant():
            return "ok"

        # Should use DEFAULT_TIMEOUT and operation_name="operation"
        result = await with_timeout(instant())
        assert result == "ok"

    async def test_propagates_non_timeout_exception(self):
        async def boom():
            raise RuntimeError("kaboom")

        with pytest.raises(RuntimeError, match="kaboom"):
            await with_timeout(boom(), timeout=5.0)

    async def test_timeout_error_chains_original(self):
        """The custom TimeoutError chains from the stdlib TimeoutError."""

        async def slow():
            await asyncio.sleep(10)

        with pytest.raises(TimeoutError) as exc_info:
            await with_timeout(slow(), timeout=0.01, operation_name="chain_test")

        assert exc_info.value.__cause__ is not None

    async def test_logs_warning_on_timeout(self, caplog):
        async def slow():
            await asyncio.sleep(10)

        with pytest.raises(TimeoutError):
            with caplog.at_level("WARNING"):
                await with_timeout(slow(), timeout=0.01, operation_name="log_check")

        assert "log_check" in caplog.text
        assert "timed out" in caplog.text


# ── @timeout_async decorator ─────────────────────────────────────────


class TestTimeoutAsyncDecorator:
    """Decorator factory that wraps async functions with a timeout."""

    async def test_decorated_function_returns_result(self):
        @timeout_async(timeout=1.0)
        async def double(x: int) -> int:
            return x * 2

        assert await double(7) == 14

    async def test_decorated_function_times_out(self):
        @timeout_async(timeout=0.01, operation_name="dec_slow")
        async def sluggish():
            await asyncio.sleep(10)

        with pytest.raises(TimeoutError) as exc_info:
            await sluggish()

        assert "dec_slow" in str(exc_info.value)

    async def test_infers_operation_name_from_function(self):
        @timeout_async(timeout=0.01)
        async def my_special_func():
            await asyncio.sleep(10)

        with pytest.raises(TimeoutError) as exc_info:
            await my_special_func()

        assert "my_special_func" in str(exc_info.value)

    async def test_preserves_function_metadata(self):
        @timeout_async(timeout=1.0, operation_name="meta")
        async def documented():
            """I have a docstring."""

        assert documented.__name__ == "documented"
        assert documented.__doc__ == "I have a docstring."

    async def test_passes_args_and_kwargs(self):
        @timeout_async(timeout=1.0)
        async def add(a: int, b: int, *, extra: int = 0) -> int:
            return a + b + extra

        assert await add(1, 2, extra=10) == 13


# ── Timeouts class ───────────────────────────────────────────────────


class TestTimeoutsClass:
    """Predefined timeout constants for common operations."""

    def test_azure_create_exceeds_azure_get(self):
        assert Timeouts.AZURE_CREATE > Timeouts.AZURE_GET

    def test_azure_poll_is_longest(self):
        assert Timeouts.AZURE_POLL >= max(
            Timeouts.AZURE_LIST,
            Timeouts.AZURE_GET,
            Timeouts.AZURE_CREATE,
            Timeouts.AZURE_DELETE,
        )

    def test_cache_operation_is_fastest(self):
        assert Timeouts.CACHE_OPERATION <= Timeouts.HEALTH_CHECK

    def test_all_values_positive_and_bounded(self):
        all_timeouts = [
            Timeouts.AZURE_LIST,
            Timeouts.AZURE_GET,
            Timeouts.AZURE_CREATE,
            Timeouts.AZURE_DELETE,
            Timeouts.AZURE_POLL,
            Timeouts.GRAPH_USER,
            Timeouts.GRAPH_LIST,
            Timeouts.GRAPH_SEARCH,
            Timeouts.HEALTH_CHECK,
            Timeouts.CACHE_OPERATION,
            Timeouts.DB_QUERY,
        ]
        for t in all_timeouts:
            assert isinstance(t, int | float)
            assert 0 < t < 600, f"Timeout {t} out of expected range"

    def test_specific_values_match_source(self):
        """Pin-check a few values to catch accidental changes."""
        assert Timeouts.AZURE_LIST == 30.0
        assert Timeouts.AZURE_POLL == 300.0
        assert Timeouts.HEALTH_CHECK == 10.0
        assert Timeouts.CACHE_OPERATION == 5.0
        assert Timeouts.DB_QUERY == 30.0

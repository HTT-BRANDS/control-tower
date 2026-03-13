"""Tests for rate limiting and resilience functionality.

This module tests:
- TokenBucketRateLimiter
- MultiApiRateLimiter
- Exponential backoff with jitter
- Retry-After header extraction
- ResilientAzureClient
- resilient_api_call helper
"""

import threading
import time
from datetime import UTC, datetime, timedelta

import pytest

from app.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitState,
    circuit_breaker_registry,
)
from app.core.rate_limit import (
    AZURE_API_RATE_LIMITS,
    MultiApiRateLimiter,
    TokenBucketRateLimiter,
    calculate_backoff,
    extract_retry_after,
    multi_api_limiter,
)
from app.core.resilience import (
    ResilienceConfig,
    ResilienceError,
    ResilientAzureClient,
    get_arm_client,
    get_cost_client,
    get_graph_client,
    get_security_client,
    resilient_api_call,
)

# =============================================================================
# TokenBucketRateLimiter Tests
# =============================================================================


class TestTokenBucketRateLimiter:
    """Tests for TokenBucketRateLimiter."""

    def test_init_valid_params(self):
        """Test initialization with valid parameters."""
        limiter = TokenBucketRateLimiter(rate_per_second=10.0, burst_size=5)
        assert limiter.rate_per_second == 10.0
        assert limiter.burst_size == 5
        assert limiter.get_current_tokens() == 5.0

    def test_init_invalid_rate(self):
        """Test initialization with invalid rate."""
        with pytest.raises(ValueError, match="rate_per_second must be positive"):
            TokenBucketRateLimiter(rate_per_second=0, burst_size=5)
        with pytest.raises(ValueError, match="rate_per_second must be positive"):
            TokenBucketRateLimiter(rate_per_second=-1, burst_size=5)

    def test_init_invalid_burst(self):
        """Test initialization with invalid burst size."""
        with pytest.raises(ValueError, match="burst_size must be positive"):
            TokenBucketRateLimiter(rate_per_second=10.0, burst_size=0)
        with pytest.raises(ValueError, match="burst_size must be positive"):
            TokenBucketRateLimiter(rate_per_second=10.0, burst_size=-1)

    def test_acquire_success(self):
        """Test successful token acquisition."""
        limiter = TokenBucketRateLimiter(rate_per_second=10.0, burst_size=5)
        assert limiter.acquire() is True
        # Allow for small floating point variations due to time elapsed
        assert 3.9 <= limiter.get_current_tokens() <= 4.1

    def test_acquire_multiple_tokens(self):
        """Test acquiring multiple tokens at once."""
        limiter = TokenBucketRateLimiter(rate_per_second=10.0, burst_size=5)
        assert limiter.acquire(tokens=3) is True
        # Allow for small floating point variations due to time elapsed
        assert 1.9 <= limiter.get_current_tokens() <= 2.1

    def test_acquire_insufficient_tokens(self):
        """Test acquisition when insufficient tokens available."""
        limiter = TokenBucketRateLimiter(rate_per_second=10.0, burst_size=2)
        assert limiter.acquire() is True  # 1 token left
        assert limiter.acquire(tokens=2) is False  # Need 2, only 1 available

    def test_acquire_empty_bucket(self):
        """Test acquisition when bucket is empty."""
        limiter = TokenBucketRateLimiter(rate_per_second=1.0, burst_size=1)
        assert limiter.acquire() is True  # Empty the bucket
        assert limiter.acquire() is False  # Bucket is empty

    def test_acquire_invalid_tokens(self):
        """Test acquisition with invalid token count."""
        limiter = TokenBucketRateLimiter(rate_per_second=10.0, burst_size=5)
        with pytest.raises(ValueError, match="tokens must be positive"):
            limiter.acquire(tokens=0)
        with pytest.raises(ValueError, match="tokens must be positive"):
            limiter.acquire(tokens=-1)

    def test_acquire_exceeds_burst(self):
        """Test acquisition when tokens exceed burst size."""
        limiter = TokenBucketRateLimiter(rate_per_second=10.0, burst_size=5)
        with pytest.raises(ValueError, match="exceeds burst_size"):
            limiter.acquire(tokens=10)

    def test_token_refill(self):
        """Test that tokens are refilled over time."""
        limiter = TokenBucketRateLimiter(rate_per_second=10.0, burst_size=5)
        assert limiter.acquire(tokens=5) is True  # Empty the bucket
        assert limiter.get_current_tokens() < 1.0

        # Wait for refill
        time.sleep(0.2)  # Should get 2 tokens (10 tokens/s * 0.2s)
        tokens = limiter.get_current_tokens()
        assert tokens >= 1.5  # Should have at least 1.5 tokens

    def test_acquire_with_wait_success(self):
        """Test acquire with wait - success case."""
        limiter = TokenBucketRateLimiter(rate_per_second=10.0, burst_size=1)
        assert limiter.acquire() is True  # Empty the bucket

        start = time.monotonic()
        result = limiter.acquire_with_wait(timeout=1.0)
        elapsed = time.monotonic() - start

        assert result is True
        assert elapsed >= 0.08  # Should wait at least ~0.1s for 1 token at 10/s

    def test_acquire_with_wait_timeout(self):
        """Test acquire with wait - timeout case."""
        limiter = TokenBucketRateLimiter(rate_per_second=0.1, burst_size=1)  # Very slow
        assert limiter.acquire() is True  # Empty the bucket

        start = time.monotonic()
        result = limiter.acquire_with_wait(timeout=0.05)  # Short timeout
        elapsed = time.monotonic() - start

        assert result is False
        assert elapsed < 0.2  # Should timeout quickly

    def test_acquire_with_wait_invalid_timeout(self):
        """Test acquire with wait with invalid timeout."""
        limiter = TokenBucketRateLimiter(rate_per_second=10.0, burst_size=5)
        with pytest.raises(ValueError, match="timeout must be non-negative"):
            limiter.acquire_with_wait(timeout=-1)

    def test_get_wait_time(self):
        """Test wait time calculation."""
        limiter = TokenBucketRateLimiter(rate_per_second=10.0, burst_size=5)
        limiter.acquire(tokens=5)  # Empty the bucket

        wait_time = limiter.get_wait_time(tokens=1)
        assert wait_time >= 0.08  # Should need ~0.1s for 1 token

        wait_time = limiter.get_wait_time(tokens=2)
        assert wait_time >= 0.15  # Should need ~0.2s for 2 tokens

    def test_get_wait_time_sufficient_tokens(self):
        """Test wait time when tokens are available."""
        limiter = TokenBucketRateLimiter(rate_per_second=10.0, burst_size=5)
        wait_time = limiter.get_wait_time(tokens=1)
        assert wait_time == 0.0

    def test_get_wait_time_invalid_tokens(self):
        """Test wait time with invalid token count."""
        limiter = TokenBucketRateLimiter(rate_per_second=10.0, burst_size=5)
        with pytest.raises(ValueError, match="tokens must be positive"):
            limiter.get_wait_time(tokens=0)

    @pytest.mark.asyncio
    async def test_acquire_async(self):
        """Test async acquire."""
        limiter = TokenBucketRateLimiter(rate_per_second=10.0, burst_size=5)
        result = await limiter.acquire_async()
        assert result is True
        # Allow for small floating point variations due to time elapsed
        assert 3.9 <= limiter.get_current_tokens() <= 4.1

    @pytest.mark.asyncio
    async def test_acquire_async_with_wait(self):
        """Test async acquire with wait."""
        limiter = TokenBucketRateLimiter(rate_per_second=10.0, burst_size=1)
        await limiter.acquire_async()  # Empty the bucket

        start = time.monotonic()
        result = await limiter.acquire_async_with_wait(timeout=1.0)
        elapsed = time.monotonic() - start

        assert result is True
        assert elapsed >= 0.05

    def test_thread_safety(self):
        """Test thread safety of token bucket."""
        limiter = TokenBucketRateLimiter(rate_per_second=1000.0, burst_size=100)
        results = []
        errors = []

        def acquire_tokens():
            try:
                for _ in range(10):
                    result = limiter.acquire()
                    results.append(result)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=acquire_tokens) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 100
        # Most should succeed given high rate limit
        assert sum(results) >= 50


# =============================================================================
# MultiApiRateLimiter Tests
# =============================================================================


class TestMultiApiRateLimiter:
    """Tests for MultiApiRateLimiter."""

    def test_init_preconfigured_limiters(self):
        """Test initialization creates limiters for all Azure APIs."""
        limiter = MultiApiRateLimiter()

        for api_name in AZURE_API_RATE_LIMITS:
            assert limiter.get_limiter(api_name) is not None

    def test_get_limiter_invalid(self):
        """Test getting limiter for invalid API."""
        limiter = MultiApiRateLimiter()
        with pytest.raises(KeyError, match="Unknown API"):
            limiter.get_limiter("invalid_api")

    def test_acquire(self):
        """Test acquire from specific API."""
        limiter = MultiApiRateLimiter()

        # Graph has 10 req/s, so we should be able to acquire
        assert limiter.acquire("graph") is True
        assert limiter.acquire("graph") is True

    def test_acquire_with_wait(self):
        """Test acquire with wait from specific API."""
        limiter = MultiApiRateLimiter()

        # Empty the graph limiter
        for _ in range(3):
            limiter.acquire("graph")

        # This should wait and succeed
        result = limiter.acquire_with_wait("graph", timeout=1.0)
        assert result is True

    @pytest.mark.asyncio
    async def test_acquire_async(self):
        """Test async acquire."""
        limiter = MultiApiRateLimiter()
        result = await limiter.acquire_async("graph")
        assert result is True

    def test_acquire_all(self):
        """Test acquire from all APIs."""
        limiter = MultiApiRateLimiter()

        # First call should succeed
        assert limiter.acquire_all() is True

        # Cost API is very slow (0.008 req/s), so subsequent calls may fail
        # But since we use small burst sizes, this should still work
        result = limiter.acquire_all()
        # Result depends on timing, so just verify it doesn't crash
        assert isinstance(result, bool)

    def test_get_wait_time(self):
        """Test get wait time for specific API."""
        limiter = MultiApiRateLimiter()

        # Empty the graph limiter
        for _ in range(5):
            limiter.acquire("graph")

        wait_time = limiter.get_wait_time("graph")
        assert wait_time > 0

    def test_register_limiter(self):
        """Test registering custom limiter."""
        limiter = MultiApiRateLimiter()
        custom_limiter = TokenBucketRateLimiter(rate_per_second=100.0, burst_size=10)

        limiter.register_limiter("custom", custom_limiter)
        retrieved = limiter.get_limiter("custom")
        assert retrieved is custom_limiter

    def test_rate_limits_configuration(self):
        """Test that Azure API rate limits are configured correctly."""
        # ARM: 3.3 req/s
        assert AZURE_API_RATE_LIMITS["arm"]["rate"] == 3.3
        # Graph: 10 req/s
        assert AZURE_API_RATE_LIMITS["graph"]["rate"] == 10.0
        # Cost: 0.008 req/s
        assert AZURE_API_RATE_LIMITS["cost"]["rate"] == 0.008
        # Security: 0.083 req/s
        assert AZURE_API_RATE_LIMITS["security"]["rate"] == 0.083


# =============================================================================
# Exponential Backoff Tests
# =============================================================================


class TestCalculateBackoff:
    """Tests for exponential backoff calculation."""

    def test_basic_backoff(self):
        """Test basic backoff calculation."""
        delay = calculate_backoff(attempt=0, base_delay=1.0, max_delay=60.0, jitter=False)
        assert delay == 1.0

        delay = calculate_backoff(attempt=1, base_delay=1.0, max_delay=60.0, jitter=False)
        assert delay == 2.0

        delay = calculate_backoff(attempt=2, base_delay=1.0, max_delay=60.0, jitter=False)
        assert delay == 4.0

    def test_backoff_max_delay(self):
        """Test that max delay is respected."""
        delay = calculate_backoff(attempt=10, base_delay=1.0, max_delay=10.0, jitter=False)
        assert delay == 10.0

    def test_backoff_with_jitter(self):
        """Test backoff with jitter."""
        delay = calculate_backoff(attempt=1, base_delay=1.0, max_delay=60.0, jitter=True)
        # With full jitter, should be between 0 and 2.0
        assert 0 <= delay <= 2.0

    def test_backoff_jitter_distribution(self):
        """Test that jitter provides reasonable distribution."""
        delays = [
            calculate_backoff(attempt=2, base_delay=1.0, max_delay=60.0, jitter=True)
            for _ in range(100)
        ]
        # Should have variation
        assert min(delays) < max(delays)
        # All should be within bounds
        assert all(0 <= d <= 4.0 for d in delays)

    def test_backoff_invalid_attempt(self):
        """Test with invalid attempt number."""
        with pytest.raises(ValueError, match="attempt must be non-negative"):
            calculate_backoff(attempt=-1, base_delay=1.0, max_delay=60.0)

    def test_backoff_invalid_base_delay(self):
        """Test with invalid base delay."""
        with pytest.raises(ValueError, match="base_delay must be positive"):
            calculate_backoff(attempt=0, base_delay=0, max_delay=60.0)
        with pytest.raises(ValueError, match="base_delay must be positive"):
            calculate_backoff(attempt=0, base_delay=-1, max_delay=60.0)

    def test_backoff_invalid_max_delay(self):
        """Test with invalid max delay."""
        with pytest.raises(ValueError, match="max_delay must be positive"):
            calculate_backoff(attempt=0, base_delay=1.0, max_delay=0)
        with pytest.raises(ValueError, match="max_delay must be positive"):
            calculate_backoff(attempt=0, base_delay=1.0, max_delay=-1)


# =============================================================================
# Retry-After Header Tests
# =============================================================================


class TestExtractRetryAfter:
    """Tests for Retry-After header extraction."""

    def test_extract_seconds(self):
        """Test extracting seconds value."""
        headers = {"Retry-After": "120"}
        result = extract_retry_after(headers, default=60.0)
        assert result == 120.0

    def test_extract_seconds_lowercase_header(self):
        """Test extracting with lowercase header."""
        headers = {"retry-after": "60"}
        result = extract_retry_after(headers, default=30.0)
        assert result == 60.0

    def test_extract_missing_header(self):
        """Test extracting when header is missing."""
        headers = {}
        result = extract_retry_after(headers, default=60.0)
        assert result == 60.0

    def test_extract_http_date(self):
        """Test extracting HTTP-date format."""
        future = datetime.now(UTC) + timedelta(seconds=120)
        headers = {"Retry-After": future.strftime("%a, %d %b %Y %H:%M:%S GMT")}
        result = extract_retry_after(headers, default=60.0)
        # Should be approximately 120 seconds (allow for test execution time)
        assert 110 <= result <= 130

    def test_extract_invalid_value(self):
        """Test extracting invalid value."""
        headers = {"Retry-After": "invalid"}
        result = extract_retry_after(headers, default=60.0)
        assert result == 60.0

    def test_extract_past_date(self):
        """Test extracting past HTTP-date (should return 0 or small value)."""
        past = datetime.now(UTC) - timedelta(seconds=60)
        headers = {"Retry-After": past.strftime("%a, %d %b %Y %H:%M:%S GMT")}
        result = extract_retry_after(headers, default=60.0)
        # Should return 0 or very small value since date is in the past
        assert result >= 0


# =============================================================================
# ResilientAzureClient Tests
# =============================================================================


class TestResilientAzureClient:
    """Tests for ResilientAzureClient."""

    @pytest.fixture
    def mock_async_func(self):
        """Create a mock async function."""

        async def func(*args, **kwargs):
            return {"result": "success", "args": args, "kwargs": kwargs}

        return func

    @pytest.fixture
    def mock_failing_func(self):
        """Create a mock async function that fails."""

        async def func(*args, **kwargs):
            raise ConnectionError("Simulated API failure")

        return func

    @pytest.mark.asyncio
    async def test_call_success(self, mock_async_func):
        """Test successful call."""
        client = ResilientAzureClient(api_name="graph")
        result = await client.call(mock_async_func, "arg1", key="value")
        assert result["result"] == "success"
        assert result["args"] == ("arg1",)
        assert result["kwargs"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_call_rate_limited(self):
        """Test call with rate limiting."""
        # Create a client with very slow rate limit
        rate_limiter = TokenBucketRateLimiter(rate_per_second=0.1, burst_size=1)
        client = ResilientAzureClient(
            api_name="test",
            rate_limiter=rate_limiter,
            config=ResilienceConfig(rate_limit_timeout=0.01),
        )

        async def async_func():
            return "result"

        await client.call(async_func)

        # Second call should timeout
        async def async_func2():
            return "result"

        with pytest.raises(ResilienceError, match="Rate limit timeout"):
            await client.call(async_func2)

    @pytest.mark.asyncio
    async def test_call_circuit_breaker_open(self):
        """Test call when circuit breaker is open."""
        breaker = CircuitBreaker(
            name="test_breaker",
            config=CircuitBreakerConfig(failure_threshold=1),
        )
        # Force open the circuit
        breaker.record_failure()
        breaker.record_failure()

        # Use a custom rate limiter since "test" is not a predefined API
        rate_limiter = TokenBucketRateLimiter(rate_per_second=10.0, burst_size=5)
        client = ResilientAzureClient(
            api_name="test",
            rate_limiter=rate_limiter,
            circuit_breaker=breaker,
        )

        async def async_func():
            return "result"

        with pytest.raises(CircuitBreakerError):
            await client.call(async_func)

    @pytest.mark.asyncio
    async def test_call_with_retry_success(self, mock_async_func):
        """Test call with retry - success case."""
        client = ResilientAzureClient(
            api_name="graph",
            config=ResilienceConfig(max_retries=3),
        )
        result = await client.call_with_retry(mock_async_func)
        assert result["result"] == "success"

    @pytest.mark.asyncio
    async def test_call_with_retry_eventual_success(self):
        """Test call with retry - eventual success."""
        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return "success"

        client = ResilientAzureClient(
            api_name="graph",
            config=ResilienceConfig(
                max_retries=5,
                base_delay=0.01,  # Short delay for test
                jitter=False,
            ),
        )
        result = await client.call_with_retry(flaky_func)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_call_with_retry_exhausted(self, mock_failing_func):
        """Test call with retry - all retries exhausted."""
        client = ResilientAzureClient(
            api_name="graph",
            config=ResilienceConfig(
                max_retries=2,
                base_delay=0.01,
                jitter=False,
            ),
        )
        with pytest.raises(ResilienceError, match="All.*attempts failed"):
            await client.call_with_retry(mock_failing_func)

    @pytest.mark.asyncio
    async def test_call_with_retry_circuit_breaker(self):
        """Test that circuit breaker errors are not retried."""
        breaker = CircuitBreaker(
            name="test_breaker",
            config=CircuitBreakerConfig(failure_threshold=1),
        )
        breaker.record_failure()
        breaker.record_failure()

        # Use a custom rate limiter since "test" is not a predefined API
        rate_limiter = TokenBucketRateLimiter(rate_per_second=10.0, burst_size=5)
        client = ResilientAzureClient(
            api_name="test",
            rate_limiter=rate_limiter,
            circuit_breaker=breaker,
            config=ResilienceConfig(max_retries=5),
        )

        async def async_func():
            return "result"

        with pytest.raises(CircuitBreakerError):
            await client.call_with_retry(async_func)

    def test_get_state(self):
        """Test getting client state."""
        client = ResilientAzureClient(api_name="graph")
        state = client.get_state()

        assert state["api_name"] == "graph"
        assert state["circuit_state"] == "closed"
        assert state["circuit_is_open"] is False
        assert "rate_tokens" in state
        assert "rate_burst_size" in state
        assert "rate_per_second" in state

    @pytest.mark.asyncio
    async def test_respect_retry_after_header(self):
        """Test that Retry-After header is respected over exponential backoff.

        Uses Retry-After: 0 (instant retry) with a very large base_delay so
        we can deterministically prove the header was used: if backoff were
        used instead, the test would take ~100s and time out.
        """

        class MockResponse:
            headers = {"Retry-After": "0"}

        class MockError(Exception):
            response = MockResponse()

        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise MockError("Rate limited")
            return "success"

        # base_delay=100 ensures backoff would take ~100s if header is ignored
        client = ResilientAzureClient(
            api_name="graph",
            config=ResilienceConfig(
                max_retries=3,
                respect_retry_after=True,
                base_delay=100.0,
            ),
        )

        start = time.monotonic()
        result = await client.call_with_retry(flaky_func)
        elapsed = time.monotonic() - start

        assert result == "success"
        assert call_count == 2
        # Retry-After: 0 means near-instant retry (~0s wait).
        # If backoff were used instead, elapsed would be ~100s.
        # A 5s bound is extremely generous and will never flake.
        assert elapsed < 5.0


# =============================================================================
# resilient_api_call Tests
# =============================================================================


class TestResilientApiCall:
    """Tests for resilient_api_call helper function."""

    @pytest.mark.asyncio
    async def test_successful_call(self):
        """Test successful API call."""

        async def test_func(x, y):
            return x + y

        result = await resilient_api_call(
            func=test_func,
            api_name="graph",
            max_retries=3,
            x=1,
            y=2,
        )
        assert result == 3

    @pytest.mark.asyncio
    async def test_with_retry(self):
        """Test API call with retry."""
        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Temporary failure")
            return "success"

        result = await resilient_api_call(
            func=flaky_func,
            api_name="graph",
            max_retries=3,
            config=ResilienceConfig(base_delay=0.01, jitter=False),
        )
        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_all_retries_fail(self):
        """Test when all retries are exhausted."""

        async def failing_func():
            raise ConnectionError("Persistent failure")

        with pytest.raises(ResilienceError):
            await resilient_api_call(
                func=failing_func,
                api_name="graph",
                max_retries=2,
                config=ResilienceConfig(base_delay=0.01, jitter=False),
            )


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestConvenienceFunctions:
    """Tests for convenience client functions."""

    def test_get_arm_client(self):
        """Test getting ARM client."""
        client = get_arm_client()
        assert client.api_name == "arm"
        assert client.rate_limiter.rate_per_second == 3.3

    def test_get_graph_client(self):
        """Test getting Graph client."""
        client = get_graph_client()
        assert client.api_name == "graph"
        assert client.rate_limiter.rate_per_second == 10.0

    def test_get_cost_client(self):
        """Test getting Cost client."""
        client = get_cost_client()
        assert client.api_name == "cost"
        assert client.rate_limiter.rate_per_second == 0.008

    def test_get_security_client(self):
        """Test getting Security client."""
        client = get_security_client()
        assert client.api_name == "security"
        assert client.rate_limiter.rate_per_second == 0.083

    def test_custom_config(self):
        """Test clients with custom config."""
        config = ResilienceConfig(max_retries=10, base_delay=2.0)
        client = get_graph_client(config=config)
        assert client.config.max_retries == 10
        assert client.config.base_delay == 2.0


# =============================================================================
# Global Instance Tests
# =============================================================================


class TestGlobalInstances:
    """Tests for global instances."""

    def test_multi_api_limiter_exists(self):
        """Test that global multi_api_limiter exists."""
        assert multi_api_limiter is not None
        # Should have all Azure APIs
        for api_name in AZURE_API_RATE_LIMITS:
            assert multi_api_limiter.get_limiter(api_name) is not None

    def test_registry_has_preconfigured_breakers(self):
        """Test that registry has pre-configured breakers."""
        assert circuit_breaker_registry.is_registered("cost_sync")
        assert circuit_breaker_registry.is_registered("graph_api")
        assert circuit_breaker_registry.is_registered("identity_sync")

    def test_registry_get_all_states(self):
        """Test getting all breaker states."""
        states = circuit_breaker_registry.get_all_states()
        assert "cost_sync" in states
        assert "graph_api" in states
        assert all(isinstance(s, CircuitState) for s in states.values())

    def test_registry_reset_all(self):
        """Test resetting all breakers."""
        # Open a breaker
        breaker = circuit_breaker_registry.get("cost_sync")
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.is_open

        # Reset all
        circuit_breaker_registry.reset_all()
        assert breaker.is_closed

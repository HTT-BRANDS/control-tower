"""Unit tests for app/core/cache.py.

Tests cache metrics, in-memory cache, cache manager, and cached decorator.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.core.cache import (
    CacheManager,
    CacheMetrics,
    InMemoryCache,
    cached,
)

# ============================================================================
# CacheMetrics Tests
# ============================================================================


def test_cache_metrics_defaults():
    """Test CacheMetrics initializes with zero values."""
    metrics = CacheMetrics()
    assert metrics.hits == 0
    assert metrics.misses == 0
    assert metrics.sets == 0
    assert metrics.deletes == 0
    assert metrics.errors == 0
    assert metrics.total_get_time_ms == 0.0
    assert metrics.total_set_time_ms == 0.0


def test_cache_metrics_hit_rate_with_hits_and_misses():
    """Test hit_rate calculation with actual hits and misses."""
    metrics = CacheMetrics(hits=75, misses=25)
    assert metrics.hit_rate == 75.0  # 75 / 100 * 100


def test_cache_metrics_hit_rate_zero_total():
    """Test hit_rate returns 0.0 when no operations have occurred."""
    metrics = CacheMetrics(hits=0, misses=0)
    assert metrics.hit_rate == 0.0


def test_cache_metrics_avg_get_time_ms():
    """Test avg_get_time_ms calculation."""
    metrics = CacheMetrics(hits=3, misses=2, total_get_time_ms=50.0)
    # 5 total gets, 50ms total = 10ms average
    assert metrics.avg_get_time_ms == 10.0


def test_cache_metrics_avg_get_time_ms_zero_operations():
    """Test avg_get_time_ms returns 0.0 when no operations."""
    metrics = CacheMetrics(total_get_time_ms=0.0)
    assert metrics.avg_get_time_ms == 0.0


def test_cache_metrics_to_dict():
    """Test CacheMetrics.to_dict() serializes correctly."""
    metrics = CacheMetrics(
        hits=80,
        misses=20,
        sets=50,
        deletes=10,
        errors=2,
        total_get_time_ms=500.0,
    )
    result = metrics.to_dict()

    assert result["hits"] == 80
    assert result["misses"] == 20
    assert result["sets"] == 50
    assert result["deletes"] == 10
    assert result["errors"] == 2
    assert result["hit_rate_percent"] == 80.0  # 80 / 100 * 100
    assert result["avg_get_time_ms"] == 5.0  # 500 / 100


# ============================================================================
# InMemoryCache Tests
# ============================================================================


@pytest.mark.asyncio
async def test_inmemory_cache_get_miss_returns_none():
    """Test get() returns None for cache miss."""
    cache = InMemoryCache()
    result = await cache.get("nonexistent_key")
    assert result is None
    assert cache.get_metrics().misses == 1
    assert cache.get_metrics().hits == 0


@pytest.mark.asyncio
async def test_inmemory_cache_set_and_get_hit():
    """Test set() followed by get() returns stored value."""
    cache = InMemoryCache()
    await cache.set("test_key", {"data": "value123"})
    result = await cache.get("test_key")

    assert result == {"data": "value123"}
    assert cache.get_metrics().sets == 1
    assert cache.get_metrics().hits == 1


@pytest.mark.asyncio
async def test_inmemory_cache_ttl_expiration():
    """Test entries with TTL expire and return None."""
    cache = InMemoryCache()

    # Mock time.time() to control expiration
    with patch("time.time") as mock_time:
        # Set initial time to 1000
        mock_time.return_value = 1000.0
        await cache.set("ttl_key", "data", ttl_seconds=10)

        # Immediately after, should still be valid
        mock_time.return_value = 1005.0  # 5 seconds later
        result = await cache.get("ttl_key")
        assert result == "data"
        assert cache.get_metrics().hits == 1

        # After expiry (11 seconds later)
        mock_time.return_value = 1011.0
        result = await cache.get("ttl_key")
        assert result is None
        assert cache.get_metrics().misses == 1


@pytest.mark.asyncio
async def test_inmemory_cache_delete_removes_entry():
    """Test delete() removes an entry from cache."""
    cache = InMemoryCache()
    await cache.set("key_to_delete", "some_value")

    # Verify it exists
    result = await cache.get("key_to_delete")
    assert result == "some_value"

    # Delete it
    deleted = await cache.delete("key_to_delete")
    assert deleted is True
    assert cache.get_metrics().deletes == 1

    # Verify it's gone
    result = await cache.get("key_to_delete")
    assert result is None


@pytest.mark.asyncio
async def test_inmemory_cache_delete_nonexistent_returns_false():
    """Test delete() returns False for nonexistent key."""
    cache = InMemoryCache()
    deleted = await cache.delete("nonexistent")
    assert deleted is False
    assert cache.get_metrics().deletes == 0


@pytest.mark.asyncio
async def test_inmemory_cache_clear_empties_all():
    """Test clear() removes all entries."""
    cache = InMemoryCache()

    # Add multiple entries
    await cache.set("key1", "value1")
    await cache.set("key2", "value2")
    await cache.set("key3", "value3")

    # Verify they exist
    assert await cache.get("key1") == "value1"
    assert await cache.get("key2") == "value2"

    # Clear all
    await cache.clear()
    assert cache.get_metrics().deletes == 3

    # Verify all gone
    assert await cache.get("key1") is None
    assert await cache.get("key2") is None
    assert await cache.get("key3") is None


@pytest.mark.asyncio
async def test_inmemory_cache_cleanup_expired():
    """Test cleanup_expired() removes only expired entries."""
    cache = InMemoryCache()

    with patch("time.time") as mock_time:
        # Set up entries with different TTLs
        mock_time.return_value = 1000.0
        await cache.set("short_ttl", "value1", ttl_seconds=5)
        await cache.set("long_ttl", "value2", ttl_seconds=100)
        await cache.set("no_ttl", "value3")  # No expiry

        # Move time forward past short TTL
        mock_time.return_value = 1010.0

        # Run cleanup
        removed = await cache.cleanup_expired()
        assert removed == 1

        # Verify short_ttl is gone, others remain
        assert await cache.get("short_ttl") is None
        assert await cache.get("long_ttl") == "value2"
        assert await cache.get("no_ttl") == "value3"


# ============================================================================
# CacheManager Tests
# ============================================================================


@pytest.mark.asyncio
async def test_cache_manager_get_set_roundtrip():
    """Test CacheManager get/set roundtrip."""
    manager = CacheManager()
    await manager.initialize()

    with patch("app.core.cache.get_settings") as mock_settings:
        settings = MagicMock()
        settings.cache_enabled = True
        settings.cache_max_ttl_seconds = 3600
        mock_settings.return_value = settings

        key = "test:key:123"
        value = {"tenant": "abc", "data": [1, 2, 3]}

        await manager.set(key, value, ttl_seconds=300)
        result = await manager.get(key)

        assert result == value


@pytest.mark.asyncio
async def test_cache_manager_delete_removes_entry():
    """Test CacheManager delete() removes entry."""
    manager = CacheManager()
    await manager.initialize()

    with patch("app.core.cache.get_settings") as mock_settings:
        settings = MagicMock()
        settings.cache_enabled = True
        settings.cache_max_ttl_seconds = 3600
        mock_settings.return_value = settings

        key = "delete:test"
        await manager.set(key, "value")
        assert await manager.get(key) == "value"

        deleted = await manager.delete(key)
        assert deleted is True
        assert await manager.get(key) is None


@pytest.mark.asyncio
async def test_cache_manager_get_metrics_returns_cache_metrics():
    """Test CacheManager get_metrics() returns metrics dict."""
    manager = CacheManager()
    await manager.initialize()

    with patch("app.core.cache.get_settings") as mock_settings:
        settings = MagicMock()
        settings.cache_enabled = True
        settings.cache_max_ttl_seconds = 3600
        mock_settings.return_value = settings

        # Perform some operations
        await manager.set("key1", "value1")
        await manager.get("key1")  # hit
        await manager.get("key_missing")  # miss

        metrics = manager.get_metrics()

        assert "backend" in metrics
        assert "hits" in metrics
        assert "misses" in metrics
        assert "sets" in metrics
        assert metrics["hits"] >= 1
        assert metrics["misses"] >= 1
        assert metrics["sets"] >= 1


@pytest.mark.asyncio
async def test_cache_manager_invalidate_tenant():
    """Test invalidate_tenant() removes tenant-specific entries."""
    manager = CacheManager()
    await manager.initialize()

    with patch("app.core.cache.get_settings") as mock_settings:
        settings = MagicMock()
        settings.cache_enabled = True
        settings.cache_max_ttl_seconds = 3600
        mock_settings.return_value = settings

        # Create keys for multiple tenants
        tenant_a_key = manager.generate_key("data", tenant_id="tenant_a")
        tenant_b_key = manager.generate_key("data", tenant_id="tenant_b")

        await manager.set(tenant_a_key, "data_a")
        await manager.set(tenant_b_key, "data_b")

        # Invalidate tenant A
        count = await manager.invalidate_tenant("tenant_a")
        assert count >= 1

        # Verify tenant A data is gone, tenant B remains
        assert await manager.get(tenant_a_key) is None
        assert await manager.get(tenant_b_key) == "data_b"


@pytest.mark.asyncio
async def test_cache_manager_generate_key_with_tenant_isolation():
    """Test generate_key() includes tenant ID for isolation."""
    manager = CacheManager()

    key1 = manager.generate_key("cost_summary", tenant_id="tenant_123")
    key2 = manager.generate_key("cost_summary", tenant_id="tenant_456")
    key3 = manager.generate_key("cost_summary")  # No tenant

    # Keys should be different
    assert key1 != key2
    assert key1 != key3
    assert key2 != key3

    # Keys should contain tenant info
    assert "tenant:tenant_123" in key1
    assert "tenant:tenant_456" in key2
    assert "tenant:" not in key3


# ============================================================================
# cached() Decorator Tests
# ============================================================================


@pytest.mark.asyncio
async def test_cached_decorator_caches_function_result():
    """Test cached() decorator caches async function results."""
    # Create fresh cache manager for this test
    test_manager = CacheManager()

    with (
        patch("app.core.cache.get_settings") as mock_settings,
        patch("app.core.cache.cache_manager", test_manager),
    ):
        settings = MagicMock()
        settings.cache_enabled = True
        settings.cache_default_ttl_seconds = 300
        settings.cache_max_ttl_seconds = 3600
        mock_settings.return_value = settings

        # Initialize cache manager
        await test_manager.initialize()

        call_count = 0

        # Use typical service method signature: (self, db, param)
        class FakeService:
            @cached(data_type="test_data", ttl_seconds=60)
            async def expensive_operation(self, db, param: str) -> dict:
                nonlocal call_count
                call_count += 1
                return {"result": f"computed_{param}", "count": call_count}

        service = FakeService()

        # First call - should execute function
        result1 = await service.expensive_operation(None, "abc")
        assert result1["result"] == "computed_abc"
        assert result1["count"] == 1
        assert call_count == 1

        # Second call with same param - should return cached value
        result2 = await service.expensive_operation(None, "abc")
        assert result2["result"] == "computed_abc"
        assert result2["count"] == 1  # Same count, from cache
        assert call_count == 1  # Function not called again

        # Different param - should execute function again
        result3 = await service.expensive_operation(None, "xyz")
        assert result3["result"] == "computed_xyz"
        assert result3["count"] == 2
        assert call_count == 2


@pytest.mark.asyncio
async def test_cached_decorator_respects_cache_disabled():
    """Test cached() decorator bypasses cache when disabled."""
    call_count = 0

    with patch("app.core.cache.get_settings") as mock_settings:
        settings = MagicMock()
        settings.cache_enabled = False  # Disabled
        mock_settings.return_value = settings

        @cached(data_type="test_data")
        async def get_data(value: str) -> str:
            nonlocal call_count
            call_count += 1
            return f"result_{value}"

        # Multiple calls should execute function each time
        result1 = await get_data("test")
        result2 = await get_data("test")

        assert result1 == "result_test"
        assert result2 == "result_test"
        assert call_count == 2  # Function called twice, no caching


@pytest.mark.asyncio
async def test_cached_decorator_with_tenant_id_kwarg():
    """Test cached() decorator extracts tenant_id from kwargs."""
    # Create fresh cache manager for this test
    test_manager = CacheManager()

    with (
        patch("app.core.cache.get_settings") as mock_settings,
        patch("app.core.cache.cache_manager", test_manager),
    ):
        settings = MagicMock()
        settings.cache_enabled = True
        settings.cache_default_ttl_seconds = 300
        settings.cache_max_ttl_seconds = 3600
        settings.get_cache_ttl = MagicMock(return_value=300)
        mock_settings.return_value = settings

        await test_manager.initialize()

        call_count = 0

        # Use typical service method signature: (self, db, tenant_id)
        class FakeService:
            @cached(data_type="tenant_data")
            async def get_tenant_data(self, db, tenant_id: str) -> dict:
                """Signature matches typical service method: (self, db, tenant_id)."""
                nonlocal call_count
                call_count += 1
                return {"tenant": tenant_id, "count": call_count}

        service = FakeService()

        # Call with different tenant IDs
        result1 = await service.get_tenant_data(None, "tenant_a")
        result2 = await service.get_tenant_data(None, "tenant_a")  # Should be cached
        result3 = await service.get_tenant_data(None, "tenant_b")  # Different tenant

        assert result1["tenant"] == "tenant_a"
        assert result1["count"] == 1
        assert result2["count"] == 1  # From cache
        assert result3["tenant"] == "tenant_b"
        assert result3["count"] == 2
        assert call_count == 2  # Only called twice (tenant_a once, tenant_b once)


@pytest.mark.asyncio
async def test_cached_decorator_does_not_cache_none_results():
    """Test cached() decorator skips caching None results."""
    # Create fresh cache manager for this test
    test_manager = CacheManager()

    with (
        patch("app.core.cache.get_settings") as mock_settings,
        patch("app.core.cache.cache_manager", test_manager),
    ):
        settings = MagicMock()
        settings.cache_enabled = True
        settings.cache_default_ttl_seconds = 300
        settings.cache_max_ttl_seconds = 3600
        settings.get_cache_ttl = MagicMock(return_value=300)
        mock_settings.return_value = settings

        await test_manager.initialize()

        call_count = 0

        @cached(data_type="nullable_data")
        async def get_nullable_data(return_none: bool) -> dict | None:
            nonlocal call_count
            call_count += 1
            if return_none:
                return None
            return {"data": "value", "count": call_count}

        # First call returns None - should not be cached
        result1 = await get_nullable_data(return_none=True)
        assert result1 is None
        assert call_count == 1

        # Second call with same params - should call function again (None not cached)
        result2 = await get_nullable_data(return_none=True)
        assert result2 is None
        assert call_count == 2

        # Call with non-None result
        result3 = await get_nullable_data(return_none=False)
        assert result3["data"] == "value"
        assert call_count == 3

        # Same call should be cached
        result4 = await get_nullable_data(return_none=False)
        assert result4["count"] == 3  # From cache
        assert call_count == 3  # Not called again

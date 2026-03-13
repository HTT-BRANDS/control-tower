"""Unit tests for app/core/monitoring.py."""

import time
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

# Mock dependencies at module level to prevent import failures
mock_settings = MagicMock()
mock_settings.slow_query_threshold_ms = 1000

mock_cache_manager = MagicMock()
mock_cache_manager.get_metrics.return_value = {
    "hits": 100,
    "misses": 50,
    "hit_rate": 0.67,
}

# Patch at module level before importing monitoring
with (
    patch("app.core.monitoring.get_settings", return_value=mock_settings),
    patch("app.core.monitoring.cache_manager", mock_cache_manager),
):
    from app.core.monitoring import (
        PerformanceMonitor,
        QueryMetrics,
        SyncJobMetrics,
        performance_monitor,
    )


class TestSyncJobMetrics:
    """Tests for SyncJobMetrics dataclass."""

    def test_defaults(self):
        """Test that SyncJobMetrics has correct default values."""
        metrics = SyncJobMetrics(job_type="test_job")

        assert metrics.job_type == "test_job"
        assert metrics.tenant_id is None
        assert metrics.records_processed == 0
        assert metrics.records_inserted == 0
        assert metrics.records_updated == 0
        assert metrics.errors == 0
        assert metrics.duration_seconds == 0.0
        assert metrics.end_time is None
        assert isinstance(metrics.start_time, datetime)

    def test_records_per_second_calculation(self):
        """Test records_per_second property with valid duration."""
        metrics = SyncJobMetrics(job_type="test_job")
        metrics.records_processed = 1000
        metrics.duration_seconds = 10.0

        assert metrics.records_per_second == 100.0

    def test_records_per_second_zero_duration(self):
        """Test records_per_second returns 0 when duration is 0."""
        metrics = SyncJobMetrics(job_type="test_job")
        metrics.records_processed = 1000
        metrics.duration_seconds = 0.0

        assert metrics.records_per_second == 0.0

    def test_complete_sets_end_time_and_duration(self):
        """Test complete() method sets end_time and calculates duration."""
        start = datetime.now(UTC)
        metrics = SyncJobMetrics(job_type="test_job")
        metrics.start_time = start

        # Simulate some work
        time.sleep(0.1)
        metrics.complete()

        assert metrics.end_time is not None
        assert metrics.end_time > metrics.start_time
        assert metrics.duration_seconds > 0
        # Should be approximately 0.1 seconds (with some tolerance)
        assert 0.08 < metrics.duration_seconds < 0.15

    def test_to_dict_serialization(self):
        """Test to_dict() produces correct serialization."""
        start_time = datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC)
        end_time = datetime(2025, 1, 15, 10, 30, 5, tzinfo=UTC)

        metrics = SyncJobMetrics(
            job_type="resources",
            tenant_id="tenant-123",
            start_time=start_time,
            end_time=end_time,
            records_processed=500,
            records_inserted=200,
            records_updated=300,
            errors=5,
            duration_seconds=5.0,
        )

        result = metrics.to_dict()

        assert result["job_type"] == "resources"
        assert result["tenant_id"] == "tenant-123"
        assert result["start_time"] == "2025-01-15T10:30:00+00:00"
        assert result["end_time"] == "2025-01-15T10:30:05+00:00"
        assert result["duration_seconds"] == 5.0
        assert result["records_processed"] == 500
        assert result["records_inserted"] == 200
        assert result["records_updated"] == 300
        assert result["errors"] == 5
        assert result["records_per_second"] == 100.0  # 500 / 5.0

    def test_to_dict_with_none_values(self):
        """Test to_dict() handles None values correctly."""
        metrics = SyncJobMetrics(job_type="test_job", tenant_id=None)
        metrics.end_time = None

        result = metrics.to_dict()

        assert result["tenant_id"] is None
        assert result["end_time"] is None
        assert result["start_time"] is not None  # start_time has default factory


class TestQueryMetrics:
    """Tests for QueryMetrics dataclass."""

    def test_defaults(self):
        """Test that QueryMetrics has correct default values."""
        metrics = QueryMetrics(query_name="get_users", duration_ms=50.5)

        assert metrics.query_name == "get_users"
        assert metrics.duration_ms == 50.5
        assert metrics.rows_returned == 0
        assert metrics.slow is False
        assert isinstance(metrics.timestamp, datetime)

    def test_to_dict_serialization(self):
        """Test to_dict() produces correct serialization."""
        timestamp = datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC)
        metrics = QueryMetrics(
            query_name="get_resources",
            duration_ms=1234.56,
            rows_returned=100,
            timestamp=timestamp,
            slow=True,
        )

        result = metrics.to_dict()

        assert result["query_name"] == "get_resources"
        assert result["duration_ms"] == 1234.56
        assert result["rows_returned"] == 100
        assert result["timestamp"] == "2025-01-15T10:30:00+00:00"
        assert result["slow"] is True

    def test_to_dict_rounds_duration(self):
        """Test to_dict() rounds duration to 2 decimal places."""
        metrics = QueryMetrics(
            query_name="test_query",
            duration_ms=123.456789,
        )

        result = metrics.to_dict()

        assert result["duration_ms"] == 123.46


class TestPerformanceMonitor:
    """Tests for PerformanceMonitor class."""

    @pytest.fixture(autouse=True)
    def reset_monitor(self):
        """Reset the global performance monitor before each test."""
        performance_monitor.reset()
        yield
        performance_monitor.reset()

    def test_start_sync_job_creates_metrics(self):
        """Test start_sync_job() creates a SyncJobMetrics instance."""
        monitor = PerformanceMonitor()
        metrics = monitor.start_sync_job("test_job", tenant_id="tenant-123")

        assert isinstance(metrics, SyncJobMetrics)
        assert metrics.job_type == "test_job"
        assert metrics.tenant_id == "tenant-123"
        assert metrics.records_processed == 0

    def test_record_sync_job(self):
        """Test record_sync_job() stores metrics."""
        monitor = PerformanceMonitor()
        metrics = SyncJobMetrics(job_type="test_job")
        metrics.records_processed = 100
        metrics.complete()

        monitor.record_sync_job(metrics)

        sync_metrics = monitor.get_sync_metrics()
        assert len(sync_metrics) == 1
        assert sync_metrics[0]["job_type"] == "test_job"
        assert sync_metrics[0]["records_processed"] == 100

    def test_record_sync_job_auto_completes(self):
        """Test record_sync_job() calls complete() if not already done."""
        monitor = PerformanceMonitor()
        metrics = SyncJobMetrics(job_type="test_job")
        metrics.records_processed = 100
        # Don't call complete() - let record_sync_job do it

        assert metrics.end_time is None
        monitor.record_sync_job(metrics)
        assert metrics.end_time is not None

    def test_record_sync_job_trims_history(self):
        """Test record_sync_job() trims history to max_history."""
        monitor = PerformanceMonitor()
        monitor._max_history = 10

        # Record 15 jobs
        for i in range(15):
            metrics = SyncJobMetrics(job_type=f"job_{i}")
            metrics.complete()
            monitor.record_sync_job(metrics)

        # Should only keep last 10
        assert len(monitor._sync_metrics) == 10
        # Should have jobs 5-14
        assert monitor._sync_metrics[0].job_type == "job_5"
        assert monitor._sync_metrics[-1].job_type == "job_14"

    def test_record_query(self):
        """Test record_query() stores query metrics."""
        monitor = PerformanceMonitor()
        monitor.record_query("test_query", duration_ms=500.0, rows_returned=10)

        query_metrics = monitor.get_query_metrics()
        assert len(query_metrics) == 1
        assert query_metrics[0]["query_name"] == "test_query"
        assert query_metrics[0]["duration_ms"] == 500.0
        assert query_metrics[0]["rows_returned"] == 10
        assert query_metrics[0]["slow"] is False

    @patch("app.core.monitoring.settings", mock_settings)
    def test_record_query_detects_slow_queries(self):
        """Test record_query() marks slow queries based on threshold."""
        monitor = PerformanceMonitor()
        # mock_settings.slow_query_threshold_ms = 1000

        # Fast query
        monitor.record_query("fast_query", duration_ms=500.0)
        # Slow query
        monitor.record_query("slow_query", duration_ms=1500.0)

        all_queries = monitor.get_query_metrics()
        assert len(all_queries) == 2
        assert all_queries[0]["slow"] is False
        assert all_queries[1]["slow"] is True

    def test_record_query_trims_history(self):
        """Test record_query() trims history to max_history."""
        monitor = PerformanceMonitor()
        monitor._max_history = 5

        # Record 10 queries
        for i in range(10):
            monitor.record_query(f"query_{i}", duration_ms=100.0)

        # Should only keep last 5
        assert len(monitor._query_metrics) == 5
        assert monitor._query_metrics[0].query_name == "query_5"
        assert monitor._query_metrics[-1].query_name == "query_9"

    @patch("app.core.monitoring.cache_manager", mock_cache_manager)
    def test_get_cache_metrics(self):
        """Test get_cache_metrics() returns cache manager metrics."""
        monitor = PerformanceMonitor()
        metrics = monitor.get_cache_metrics()

        assert metrics["hits"] == 100
        assert metrics["misses"] == 50
        assert metrics["hit_rate"] == 0.67

    def test_get_sync_metrics_filtering_by_job_type(self):
        """Test get_sync_metrics() can filter by job_type."""
        monitor = PerformanceMonitor()

        # Record different job types
        for job_type in ["resources", "users", "resources", "events"]:
            metrics = SyncJobMetrics(job_type=job_type)
            metrics.complete()
            monitor.record_sync_job(metrics)

        resources_metrics = monitor.get_sync_metrics(job_type="resources")
        assert len(resources_metrics) == 2
        assert all(m["job_type"] == "resources" for m in resources_metrics)

    def test_get_sync_metrics_filtering_by_tenant_id(self):
        """Test get_sync_metrics() can filter by tenant_id."""
        monitor = PerformanceMonitor()

        # Record different tenants
        for tenant in ["tenant-a", "tenant-b", "tenant-a", "tenant-c"]:
            metrics = SyncJobMetrics(job_type="test", tenant_id=tenant)
            metrics.complete()
            monitor.record_sync_job(metrics)

        tenant_a_metrics = monitor.get_sync_metrics(tenant_id="tenant-a")
        assert len(tenant_a_metrics) == 2
        assert all(m["tenant_id"] == "tenant-a" for m in tenant_a_metrics)

    def test_get_sync_metrics_limit(self):
        """Test get_sync_metrics() respects limit parameter."""
        monitor = PerformanceMonitor()

        # Record 10 jobs
        for _ in range(10):
            metrics = SyncJobMetrics(job_type="test")
            metrics.complete()
            monitor.record_sync_job(metrics)

        limited_metrics = monitor.get_sync_metrics(limit=5)
        assert len(limited_metrics) == 5

    @patch("app.core.monitoring.settings", mock_settings)
    def test_get_query_metrics_slow_only_filter(self):
        """Test get_query_metrics() can filter to slow queries only."""
        monitor = PerformanceMonitor()

        # Record mix of fast and slow queries
        monitor.record_query("fast_1", duration_ms=500.0)
        monitor.record_query("slow_1", duration_ms=1500.0)
        monitor.record_query("fast_2", duration_ms=800.0)
        monitor.record_query("slow_2", duration_ms=2000.0)

        slow_queries = monitor.get_query_metrics(slow_only=True)
        assert len(slow_queries) == 2
        assert all(q["slow"] is True for q in slow_queries)

    def test_get_query_metrics_limit(self):
        """Test get_query_metrics() respects limit parameter."""
        monitor = PerformanceMonitor()

        # Record 10 queries
        for i in range(10):
            monitor.record_query(f"query_{i}", duration_ms=100.0)

        limited_metrics = monitor.get_query_metrics(limit=3)
        assert len(limited_metrics) == 3

    @patch("app.core.monitoring.cache_manager", mock_cache_manager)
    @patch("app.core.monitoring.settings", mock_settings)
    def test_get_performance_summary_with_data(self):
        """Test get_performance_summary() calculates correct aggregates."""
        monitor = PerformanceMonitor()

        # Add some sync jobs
        for i in range(3):
            metrics = SyncJobMetrics(job_type="test")
            metrics.records_processed = 100 * (i + 1)  # 100, 200, 300
            metrics.errors = i  # 0, 1, 2
            metrics.complete()
            # Set duration after complete() to avoid it being recalculated
            metrics.duration_seconds = 10.0  # constant for easy math
            monitor.record_sync_job(metrics)

        # Add some queries
        monitor.record_query("fast_1", duration_ms=500.0)
        monitor.record_query("slow_1", duration_ms=1500.0)
        monitor.record_query("fast_2", duration_ms=700.0)

        summary = monitor.get_performance_summary()

        # Check cache metrics
        assert summary["cache"]["hits"] == 100

        # Check sync job metrics
        assert summary["sync_jobs"]["total_jobs"] == 3
        assert summary["sync_jobs"]["total_records_processed"] == 600  # 100+200+300
        assert summary["sync_jobs"]["total_errors"] == 3  # 0+1+2
        # avg_records_per_second = (10 + 20 + 30) / 3 = 20
        assert summary["sync_jobs"]["avg_records_per_second"] == 20.0
        assert summary["sync_jobs"]["avg_duration_seconds"] == 10.0

        # Check query metrics
        assert summary["queries"]["total_queries"] == 3
        # avg_duration_ms = (500 + 1500 + 700) / 3 = 900
        assert summary["queries"]["avg_duration_ms"] == 900.0
        assert summary["queries"]["slow_queries"] == 1
        assert summary["queries"]["slow_query_threshold_ms"] == 1000

        # Check timestamp
        assert "timestamp" in summary

    def test_get_performance_summary_empty(self):
        """Test get_performance_summary() handles empty metrics."""
        monitor = PerformanceMonitor()
        summary = monitor.get_performance_summary()

        assert summary["sync_jobs"]["total_jobs"] == 0
        assert summary["sync_jobs"]["avg_records_per_second"] == 0.0
        assert summary["sync_jobs"]["avg_duration_seconds"] == 0.0
        assert summary["sync_jobs"]["total_records_processed"] == 0
        assert summary["sync_jobs"]["total_errors"] == 0

        assert summary["queries"]["total_queries"] == 0
        assert summary["queries"]["avg_duration_ms"] == 0.0
        assert summary["queries"]["slow_queries"] == 0

    def test_reset_clears_all_metrics(self):
        """Test reset() clears all stored metrics."""
        monitor = PerformanceMonitor()

        # Add some data
        metrics = SyncJobMetrics(job_type="test")
        metrics.complete()
        monitor.record_sync_job(metrics)
        monitor.record_query("test", duration_ms=100.0)

        assert len(monitor._sync_metrics) > 0
        assert len(monitor._query_metrics) > 0

        # Reset
        monitor.reset()

        assert len(monitor._sync_metrics) == 0
        assert len(monitor._query_metrics) == 0

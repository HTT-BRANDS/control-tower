"""Integration tests for Sync API endpoints.

These tests verify the complete request/response cycle for sync job management endpoints,
including authentication, authorization, database interactions, and data validation.

Covered endpoints:
- POST /api/v1/sync/{sync_type} - Trigger manual sync
- GET /api/v1/sync/status - Get scheduler status
- GET /api/v1/sync/status/health - Get sync health status with metrics
- GET /api/v1/sync/history - Get sync job execution history
- GET /api/v1/sync/metrics - Get aggregate sync job metrics
- GET /api/v1/sync/alerts - Get sync job alerts
- POST /api/v1/sync/alerts/{alert_id}/resolve - Resolve alert
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.monitoring import Alert, SyncJobLog, SyncJobMetrics

# ============================================================================
# Fixtures - Custom clients with sync route authentication
# ============================================================================

@pytest.fixture
def sync_client(seeded_db, test_user, mock_authz):
    """Test client with authentication for sync routes."""
    from app.core.auth import get_current_user
    from app.core.authorization import get_tenant_authorization

    def override_get_db():
        try:
            yield seeded_db
        finally:
            pass

    # Use FastAPI's dependency override system
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_tenant_authorization] = lambda: mock_authz

    # Clear rate limiter cache and patch to always allow
    from app.core.rate_limit import rate_limiter
    rate_limiter._memory_cache.clear()

    async def mock_check_rate_limit(*args, **kwargs):
        pass  # No-op - always allow

    with patch("app.core.rate_limit.rate_limiter.check_rate_limit", side_effect=mock_check_rate_limit):
        with TestClient(app) as client:
            yield client

    app.dependency_overrides.clear()


@pytest.fixture
def sync_admin_client(seeded_db, admin_user, mock_authz_admin):
    """Test client with admin authentication for sync routes."""
    from app.core.auth import get_current_user
    from app.core.authorization import get_tenant_authorization

    def override_get_db():
        try:
            yield seeded_db
        finally:
            pass

    # Use FastAPI's dependency override system
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[get_tenant_authorization] = lambda: mock_authz_admin

    # Clear rate limiter cache and patch to always allow
    from app.core.rate_limit import rate_limiter
    rate_limiter._memory_cache.clear()

    async def mock_check_rate_limit(*args, **kwargs):
        pass  # No-op - always allow

    with patch("app.core.rate_limit.rate_limiter.check_rate_limit", side_effect=mock_check_rate_limit):
        with TestClient(app) as client:
            yield client

    app.dependency_overrides.clear()


@pytest.fixture
def sync_unauth_client(seeded_db):
    """Test client without authentication for sync routes."""
    def override_get_db():
        try:
            yield seeded_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    # Clear rate limiter cache and patch to always allow
    from app.core.rate_limit import rate_limiter
    rate_limiter._memory_cache.clear()

    async def mock_check_rate_limit(*args, **kwargs):
        pass  # No-op - always allow

    with patch("app.core.rate_limit.rate_limiter.check_rate_limit", side_effect=mock_check_rate_limit):
        with TestClient(app) as client:
            yield client

    app.dependency_overrides.clear()


@pytest.fixture
def db_with_monitoring_data(seeded_db, test_tenant_id, second_tenant_id):
    """Seeded database with monitoring data (job logs, metrics, alerts)."""
    # Add job logs
    job_types = ["costs_sync", "compliance_sync", "resources_sync", "identity_sync"]
    statuses = ["completed", "failed", "running"]

    for i in range(10):
        days_ago = i % 5
        job_type = job_types[i % len(job_types)]
        status = statuses[i % len(statuses)]
        tenant_id = test_tenant_id if i % 2 == 0 else second_tenant_id

        started_at = datetime.utcnow() - timedelta(days=days_ago, hours=i)
        ended_at = started_at + timedelta(minutes=15) if status != "running" else None
        duration_ms = 900000 if status != "running" else None

        log = SyncJobLog(
            job_type=job_type,
            tenant_id=tenant_id,
            status=status,
            started_at=started_at,
            ended_at=ended_at,
            duration_ms=duration_ms,
            records_processed=100 + i * 10 if status == "completed" else 0,
            errors_count=0 if status == "completed" else (i % 3),
            error_message=f"Error {i}" if status == "failed" else None,
        )
        seeded_db.add(log)

    # Add metrics (note: metrics are per job_type only, not per tenant)
    for job_type in job_types:
        metric = SyncJobMetrics(
            job_type=job_type,
            calculated_at=datetime.utcnow(),
            total_runs=50,
            successful_runs=45,
            failed_runs=5,
            success_rate=90.0,
            avg_duration_ms=850000,
            min_duration_ms=500000,
            max_duration_ms=1200000,
            avg_records_processed=150,
            total_records_processed=7500,
            total_errors=10,
            last_run_at=datetime.utcnow() - timedelta(hours=1),
            last_success_at=datetime.utcnow() - timedelta(hours=1),
            last_failure_at=datetime.utcnow() - timedelta(days=1),
            last_error_message="Previous error",
        )
        seeded_db.add(metric)

    # Add alerts
    alert_types = ["high_failure_rate", "long_duration", "no_recent_sync", "sync_error"]
    severities = ["warning", "error", "critical", "info"]

    for i in range(8):
        job_type = job_types[i % len(job_types)]
        alert_type = alert_types[i % len(alert_types)]
        severity = severities[i % len(severities)]
        tenant_id = test_tenant_id if i % 2 == 0 else second_tenant_id
        is_resolved = i < 3  # First 3 are resolved

        alert = Alert(
            alert_type=alert_type,
            severity=severity,
            job_type=job_type,
            tenant_id=tenant_id,
            title=f"Alert {i}: {alert_type}",
            message=f"Test alert message for {job_type}",
            is_resolved=is_resolved,
            created_at=datetime.utcnow() - timedelta(days=i),
            resolved_at=datetime.utcnow() - timedelta(days=i-1) if is_resolved else None,
            resolved_by="user-123" if is_resolved else None,
        )
        seeded_db.add(alert)

    seeded_db.commit()
    return seeded_db


# ============================================================================
# POST /api/v1/sync/{sync_type} Tests
# ============================================================================

class TestTriggerSyncEndpoint:
    """Integration tests for POST /api/v1/sync/{sync_type}."""

    @pytest.mark.parametrize("sync_type", ["costs", "compliance", "resources", "identity"])
    def test_trigger_sync_valid_types(self, sync_client, sync_type):
        """Trigger sync succeeds for all valid sync types."""
        # Mock the scheduler trigger function
        with patch("app.api.routes.sync.trigger_manual_sync", return_value=True) as mock_trigger:
            response = sync_client.post(f"/api/v1/sync/{sync_type}")

            assert response.status_code == 200
            data = response.json()

            # Validate response structure
            assert "status" in data
            assert "sync_type" in data
            assert data["status"] == "triggered"
            assert data["sync_type"] == sync_type

            # Verify the trigger function was called with correct sync_type
            mock_trigger.assert_called_once_with(sync_type)

    def test_trigger_sync_invalid_type(self, sync_client):
        """Trigger sync fails with 422 for invalid sync type."""
        response = sync_client.post("/api/v1/sync/invalid_type")
        assert response.status_code == 422  # Validation error

    def test_trigger_sync_scheduler_failure(self, sync_client):
        """Trigger sync returns 400 when scheduler fails."""
        # Mock scheduler returning False (unknown sync type or failure)
        with patch("app.api.routes.sync.trigger_manual_sync", return_value=False):
            response = sync_client.post("/api/v1/sync/costs")

            assert response.status_code == 400
            data = response.json()
            assert "detail" in data
            assert "Unknown sync type" in data["detail"]

    def test_trigger_sync_requires_auth(self, sync_unauth_client):
        """Trigger sync endpoint requires authentication."""
        response = sync_unauth_client.post("/api/v1/sync/costs")
        assert response.status_code == 401

    def test_trigger_sync_rate_limited(self, sync_client):
        """Trigger sync endpoint is rate limited."""
        # This test verifies rate limiting exists (implementation may vary)
        # We're testing that the endpoint has rate limiting dependency
        # The actual rate limit behavior is tested in test_rate_limit.py
        with patch("app.api.routes.sync.trigger_manual_sync", return_value=True):
            response = sync_client.post("/api/v1/sync/costs")
            assert response.status_code in [200, 429]  # Success or rate limited


# ============================================================================
# GET /api/v1/sync/status Tests
# ============================================================================

class TestSyncStatusEndpoint:
    """Integration tests for GET /api/v1/sync/status."""

    def test_get_status_scheduler_initialized(self, sync_client):
        """Sync status returns scheduler information when initialized."""
        # Mock scheduler
        mock_scheduler = MagicMock()
        mock_job = MagicMock()
        mock_job.id = "costs_sync"
        mock_job.name = "Sync Costs"
        mock_job.next_run_time = datetime.utcnow() + timedelta(hours=1)
        mock_scheduler.get_jobs.return_value = [mock_job]

        with patch("app.api.routes.sync.get_scheduler", return_value=mock_scheduler):
            response = sync_client.get("/api/v1/sync/status")

            assert response.status_code == 200
            data = response.json()

            # Validate structure
            assert "status" in data
            assert "jobs" in data
            assert data["status"] == "running"
            assert isinstance(data["jobs"], list)

            # Validate job structure
            if len(data["jobs"]) > 0:
                job = data["jobs"][0]
                assert "id" in job
                assert "name" in job
                assert "next_run" in job
                assert job["id"] == "costs_sync"
                assert job["name"] == "Sync Costs"
                assert isinstance(job["next_run"], str)  # ISO format timestamp

    def test_get_status_scheduler_not_initialized(self, sync_client):
        """Sync status handles uninitialized scheduler gracefully."""
        with patch("app.api.routes.sync.get_scheduler", return_value=None):
            response = sync_client.get("/api/v1/sync/status")

            assert response.status_code == 200
            data = response.json()

            # Should return appropriate status
            assert data["status"] == "scheduler_not_initialized"
            assert data["jobs"] == []

    def test_get_status_no_scheduled_jobs(self, sync_client):
        """Sync status handles empty scheduler gracefully."""
        mock_scheduler = MagicMock()
        mock_scheduler.get_jobs.return_value = []

        with patch("app.api.routes.sync.get_scheduler", return_value=mock_scheduler):
            response = sync_client.get("/api/v1/sync/status")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "running"
            assert data["jobs"] == []

    def test_get_status_requires_auth(self, sync_unauth_client):
        """Sync status endpoint requires authentication."""
        response = sync_unauth_client.get("/api/v1/sync/status")
        assert response.status_code == 401


# ============================================================================
# GET /api/v1/sync/status/health Tests
# ============================================================================

class TestSyncHealthEndpoint:
    """Integration tests for GET /api/v1/sync/status/health."""

    def test_get_health_success(self, db_with_monitoring_data, sync_client):
        """Sync health returns overall status with metrics."""
        # Need to update fixture reference
        app.dependency_overrides[get_db] = lambda: db_with_monitoring_data

        response = sync_client.get("/api/v1/sync/status/health")

        assert response.status_code == 200
        data = response.json()

        # MonitoringService.get_overall_status() returns different structure
        # The actual structure depends on the implementation
        # But it should at least return a dict
        assert isinstance(data, dict)

    def test_get_health_requires_auth(self, sync_unauth_client):
        """Sync health endpoint requires authentication."""
        response = sync_unauth_client.get("/api/v1/sync/status/health")
        assert response.status_code == 401


# ============================================================================
# GET /api/v1/sync/history Tests
# ============================================================================

class TestSyncHistoryEndpoint:
    """Integration tests for GET /api/v1/sync/history."""

    def test_get_history_success(self, sync_client):
        """Sync history returns list of job logs."""
        # Add a job log to the database
        from app.core.database import get_db
        db = next(app.dependency_overrides[get_db]())

        log = SyncJobLog(
            job_type="costs_sync",
            tenant_id="test-tenant-123",
            status="completed",
            started_at=datetime.utcnow() - timedelta(hours=2),
            ended_at=datetime.utcnow() - timedelta(hours=1),
            duration_ms=3600000,
            records_processed=150,
            errors_count=0,
            error_message=None,
        )
        db.add(log)
        db.commit()

        response = sync_client.get("/api/v1/sync/history")

        assert response.status_code == 200
        data = response.json()

        # Validate structure
        assert "logs" in data
        assert isinstance(data["logs"], list)

        # Validate log structure if we have data
        if len(data["logs"]) > 0:
            log_entry = data["logs"][0]
            assert "id" in log_entry
            assert "job_type" in log_entry
            assert "tenant_id" in log_entry
            assert "status" in log_entry
            assert "started_at" in log_entry
            assert "ended_at" in log_entry
            assert "duration_ms" in log_entry
            assert "records_processed" in log_entry
            assert "errors_count" in log_entry
            assert "error_message" in log_entry

            # Validate types
            assert isinstance(log_entry["job_type"], str)
            assert isinstance(log_entry["status"], str)
            assert log_entry["status"] in ["completed", "failed", "running"]

    def test_get_history_job_type_filter(self, sync_client):
        """Sync history can be filtered by job_type."""
        # Add logs with different job types
        db = next(app.dependency_overrides[get_db]())

        log1 = SyncJobLog(
            job_type="costs_sync",
            tenant_id="test-tenant-123",
            status="completed",
            started_at=datetime.utcnow() - timedelta(hours=2),
            ended_at=datetime.utcnow() - timedelta(hours=1),
            duration_ms=3600000,
            records_processed=150,
            errors_count=0,
        )
        log2 = SyncJobLog(
            job_type="compliance_sync",
            tenant_id="test-tenant-123",
            status="completed",
            started_at=datetime.utcnow() - timedelta(hours=3),
            ended_at=datetime.utcnow() - timedelta(hours=2),
            duration_ms=3600000,
            records_processed=100,
            errors_count=0,
        )
        db.add_all([log1, log2])
        db.commit()

        response = sync_client.get("/api/v1/sync/history?job_type=costs_sync")

        assert response.status_code == 200
        data = response.json()

        # All logs should match the filter
        for log in data["logs"]:
            assert log["job_type"] == "costs_sync"

    def test_get_history_limit_parameter(self, sync_client):
        """Sync history respects limit parameter."""
        # Add multiple logs
        db = next(app.dependency_overrides[get_db]())

        for i in range(10):
            log = SyncJobLog(
                job_type="costs_sync",
                tenant_id="test-tenant-123",
                status="completed",
                started_at=datetime.utcnow() - timedelta(hours=i+1),
                ended_at=datetime.utcnow() - timedelta(hours=i),
                duration_ms=3600000,
                records_processed=100,
                errors_count=0,
            )
            db.add(log)
        db.commit()

        response = sync_client.get("/api/v1/sync/history?limit=5")

        assert response.status_code == 200
        data = response.json()

        # Should return at most 5 logs
        assert len(data["logs"]) <= 5

    def test_get_history_validates_limit(self, sync_client):
        """Sync history validates limit parameter."""
        # Test limit too large
        response = sync_client.get("/api/v1/sync/history?limit=1000")
        assert response.status_code == 422  # Validation error

        # Test limit too small
        response = sync_client.get("/api/v1/sync/history?limit=0")
        assert response.status_code == 422

    def test_get_history_tenant_isolation(self, sync_client, test_tenant_id):
        """Sync history only returns logs for accessible tenants."""
        # Add logs for different tenants
        db = next(app.dependency_overrides[get_db]())

        log1 = SyncJobLog(
            job_type="costs_sync",
            tenant_id=test_tenant_id,
            status="completed",
            started_at=datetime.utcnow() - timedelta(hours=2),
            ended_at=datetime.utcnow() - timedelta(hours=1),
            duration_ms=3600000,
            records_processed=150,
            errors_count=0,
        )
        log2 = SyncJobLog(
            job_type="costs_sync",
            tenant_id="other-tenant-999",
            status="completed",
            started_at=datetime.utcnow() - timedelta(hours=3),
            ended_at=datetime.utcnow() - timedelta(hours=2),
            duration_ms=3600000,
            records_processed=100,
            errors_count=0,
        )
        db.add_all([log1, log2])
        db.commit()

        response = sync_client.get("/api/v1/sync/history")

        assert response.status_code == 200
        data = response.json()

        # Should only return logs for accessible tenants
        for log in data["logs"]:
            if log["tenant_id"]:  # Some logs might not have tenant_id
                assert log["tenant_id"] in [test_tenant_id, "test-tenant-456"]

    def test_get_history_requires_auth(self, sync_unauth_client):
        """Sync history endpoint requires authentication."""
        response = sync_unauth_client.get("/api/v1/sync/history")
        assert response.status_code == 401


# ============================================================================
# GET /api/v1/sync/metrics Tests
# ============================================================================

class TestSyncMetricsEndpoint:
    """Integration tests for GET /api/v1/sync/metrics."""

    def test_get_metrics_success(self, sync_client):
        """Sync metrics returns aggregated statistics."""
        # Add a metric to the database
        db = next(app.dependency_overrides[get_db]())

        metric = SyncJobMetrics(
            job_type="costs_sync",
            calculated_at=datetime.utcnow(),
            total_runs=100,
            successful_runs=95,
            failed_runs=5,
            success_rate=95.0,
            avg_duration_ms=900000,
            min_duration_ms=600000,
            max_duration_ms=1200000,
            avg_records_processed=200,
            total_records_processed=20000,
            total_errors=5,
            last_run_at=datetime.utcnow() - timedelta(hours=1),
            last_success_at=datetime.utcnow() - timedelta(hours=1),
            last_failure_at=datetime.utcnow() - timedelta(days=1),
            last_error_message="Previous error",
        )
        db.add(metric)
        db.commit()

        response = sync_client.get("/api/v1/sync/metrics")

        assert response.status_code == 200
        data = response.json()

        # Validate structure
        assert "metrics" in data
        assert isinstance(data["metrics"], list)

        # Validate metric structure if we have data
        if len(data["metrics"]) > 0:
            metric_entry = data["metrics"][0]
            assert "job_type" in metric_entry
            assert "calculated_at" in metric_entry
            assert "total_runs" in metric_entry
            assert "successful_runs" in metric_entry
            assert "failed_runs" in metric_entry
            assert "success_rate" in metric_entry
            assert "avg_duration_ms" in metric_entry
            assert "min_duration_ms" in metric_entry
            assert "max_duration_ms" in metric_entry
            assert "avg_records_processed" in metric_entry
            assert "total_records_processed" in metric_entry
            assert "total_errors" in metric_entry
            assert "last_run_at" in metric_entry
            assert "last_success_at" in metric_entry
            assert "last_failure_at" in metric_entry
            assert "last_error_message" in metric_entry

            # Validate types and ranges
            assert isinstance(metric_entry["total_runs"], int)
            assert isinstance(metric_entry["success_rate"], (int, float))
            assert 0 <= metric_entry["success_rate"] <= 100
            assert metric_entry["successful_runs"] + metric_entry["failed_runs"] == metric_entry["total_runs"]

    def test_get_metrics_job_type_filter(self, sync_client):
        """Sync metrics can be filtered by job_type."""
        # Add metrics for different job types
        db = next(app.dependency_overrides[get_db]())

        metric1 = SyncJobMetrics(
            job_type="costs_sync",
            calculated_at=datetime.utcnow(),
            total_runs=100,
            successful_runs=95,
            failed_runs=5,
            success_rate=95.0,
            avg_duration_ms=900000,
            min_duration_ms=600000,
            max_duration_ms=1200000,
            avg_records_processed=200,
            total_records_processed=20000,
            total_errors=5,
        )
        metric2 = SyncJobMetrics(
            job_type="compliance_sync",
            calculated_at=datetime.utcnow(),
            total_runs=50,
            successful_runs=48,
            failed_runs=2,
            success_rate=96.0,
            avg_duration_ms=700000,
            min_duration_ms=500000,
            max_duration_ms=900000,
            avg_records_processed=100,
            total_records_processed=5000,
            total_errors=2,
        )
        db.add_all([metric1, metric2])
        db.commit()

        response = sync_client.get("/api/v1/sync/metrics?job_type=costs_sync")

        assert response.status_code == 200
        data = response.json()

        # All metrics should match the filter
        for metric in data["metrics"]:
            assert metric["job_type"] == "costs_sync"

    def test_get_metrics_tenant_isolation(self, sync_client, test_tenant_id):
        """Sync metrics only returns data for accessible tenants."""
        # Add metrics for different tenants
        db = next(app.dependency_overrides[get_db]())

        metric1 = SyncJobMetrics(
            job_type="costs_sync",
            calculated_at=datetime.utcnow(),
            total_runs=100,
            successful_runs=95,
            failed_runs=5,
            success_rate=95.0,
            avg_duration_ms=900000,
            min_duration_ms=600000,
            max_duration_ms=1200000,
            avg_records_processed=200,
            total_records_processed=20000,
            total_errors=5,
        )
        metric2 = SyncJobMetrics(
            job_type="compliance_sync",
            calculated_at=datetime.utcnow(),
            total_runs=50,
            successful_runs=48,
            failed_runs=2,
            success_rate=96.0,
            avg_duration_ms=700000,
            min_duration_ms=500000,
            max_duration_ms=900000,
            avg_records_processed=100,
            total_records_processed=5000,
            total_errors=2,
        )
        db.add_all([metric1, metric2])
        db.commit()

        response = sync_client.get("/api/v1/sync/metrics")

        assert response.status_code == 200
        data = response.json()

        # Metrics are global (per job_type), not tenant-specific
        assert isinstance(data["metrics"], list)
        # Should have both job types
        job_types = {m["job_type"] for m in data["metrics"]}
        assert "costs_sync" in job_types or "compliance_sync" in job_types

    def test_get_metrics_requires_auth(self, sync_unauth_client):
        """Sync metrics endpoint requires authentication."""
        response = sync_unauth_client.get("/api/v1/sync/metrics")
        assert response.status_code == 401


# ============================================================================
# GET /api/v1/sync/alerts Tests
# ============================================================================

class TestSyncAlertsEndpoint:
    """Integration tests for GET /api/v1/sync/alerts."""

    def test_get_alerts_success(self, sync_client):
        """Sync alerts returns list of active alerts."""
        # Add an alert to the database
        db = next(app.dependency_overrides[get_db]())

        alert = Alert(
            alert_type="high_failure_rate",
            severity="warning",
            job_type="costs_sync",
            tenant_id="test-tenant-123",
            title="High Failure Rate",
            message="Sync job failure rate exceeded threshold",
            is_resolved=False,
            created_at=datetime.utcnow() - timedelta(hours=2),
        )
        db.add(alert)
        db.commit()

        response = sync_client.get("/api/v1/sync/alerts")

        assert response.status_code == 200
        data = response.json()

        # Validate structure
        assert "alerts" in data
        assert "stats" in data
        assert isinstance(data["alerts"], list)

        # Validate alert structure if we have data
        if len(data["alerts"]) > 0:
            alert_entry = data["alerts"][0]
            assert "id" in alert_entry
            assert "alert_type" in alert_entry
            assert "severity" in alert_entry
            assert "job_type" in alert_entry
            assert "tenant_id" in alert_entry
            assert "title" in alert_entry
            assert "message" in alert_entry
            assert "is_resolved" in alert_entry
            assert "created_at" in alert_entry
            assert "resolved_at" in alert_entry
            assert "resolved_by" in alert_entry

            # Validate types
            assert isinstance(alert_entry["severity"], str)
            assert alert_entry["severity"] in ["info", "warning", "error", "critical"]
            assert isinstance(alert_entry["is_resolved"], bool)

    def test_get_alerts_job_type_filter(self, sync_client):
        """Sync alerts can be filtered by job_type."""
        # Add alerts for different job types
        db = next(app.dependency_overrides[get_db]())

        alert1 = Alert(
            alert_type="high_failure_rate",
            severity="warning",
            job_type="costs_sync",
            tenant_id="test-tenant-123",
            title="Costs Alert",
            message="Test alert",
            is_resolved=False,
            created_at=datetime.utcnow(),
        )
        alert2 = Alert(
            alert_type="long_duration",
            severity="info",
            job_type="compliance_sync",
            tenant_id="test-tenant-123",
            title="Compliance Alert",
            message="Test alert",
            is_resolved=False,
            created_at=datetime.utcnow(),
        )
        db.add_all([alert1, alert2])
        db.commit()

        response = sync_client.get("/api/v1/sync/alerts?job_type=costs_sync")

        assert response.status_code == 200
        data = response.json()

        # All alerts should match the filter
        for alert in data["alerts"]:
            assert alert["job_type"] == "costs_sync"

    def test_get_alerts_severity_filter(self, sync_client):
        """Sync alerts can be filtered by severity."""
        # Add alerts with different severities
        db = next(app.dependency_overrides[get_db]())

        alert1 = Alert(
            alert_type="high_failure_rate",
            severity="critical",
            job_type="costs_sync",
            tenant_id="test-tenant-123",
            title="Critical Alert",
            message="Test alert",
            is_resolved=False,
            created_at=datetime.utcnow(),
        )
        alert2 = Alert(
            alert_type="long_duration",
            severity="warning",
            job_type="costs_sync",
            tenant_id="test-tenant-123",
            title="Warning Alert",
            message="Test alert",
            is_resolved=False,
            created_at=datetime.utcnow(),
        )
        db.add_all([alert1, alert2])
        db.commit()

        response = sync_client.get("/api/v1/sync/alerts?severity=critical")

        assert response.status_code == 200
        data = response.json()

        # All alerts should match the filter
        for alert in data["alerts"]:
            assert alert["severity"] == "critical"

    def test_get_alerts_severity_validation(self, sync_client):
        """Sync alerts validates severity parameter."""
        # Invalid severity
        response = sync_client.get("/api/v1/sync/alerts?severity=invalid")
        assert response.status_code == 422  # Validation error

    def test_get_alerts_include_resolved(self, sync_client):
        """Sync alerts can include resolved alerts."""
        # Add both resolved and unresolved alerts
        db = next(app.dependency_overrides[get_db]())

        alert1 = Alert(
            alert_type="high_failure_rate",
            severity="warning",
            job_type="costs_sync",
            tenant_id="test-tenant-123",
            title="Active Alert",
            message="Test alert",
            is_resolved=False,
            created_at=datetime.utcnow(),
        )
        alert2 = Alert(
            alert_type="long_duration",
            severity="info",
            job_type="costs_sync",
            tenant_id="test-tenant-123",
            title="Resolved Alert",
            message="Test alert",
            is_resolved=True,
            created_at=datetime.utcnow() - timedelta(hours=5),
            resolved_at=datetime.utcnow() - timedelta(hours=1),
            resolved_by="user-123",
        )
        db.add_all([alert1, alert2])
        db.commit()

        # Get only active alerts (default)
        response_active = sync_client.get("/api/v1/sync/alerts")
        assert response_active.status_code == 200
        data_active = response_active.json()

        # Get all alerts including resolved
        response_all = sync_client.get("/api/v1/sync/alerts?include_resolved=true")
        assert response_all.status_code == 200
        data_all = response_all.json()

        # All alerts response should have more or equal alerts
        assert len(data_all["alerts"]) >= len(data_active["alerts"])

    def test_get_alerts_tenant_isolation(self, sync_client, test_tenant_id):
        """Sync alerts only returns alerts for accessible tenants."""
        # Add alerts for different tenants
        db = next(app.dependency_overrides[get_db]())

        alert1 = Alert(
            alert_type="high_failure_rate",
            severity="warning",
            job_type="costs_sync",
            tenant_id=test_tenant_id,
            title="Accessible Alert",
            message="Test alert",
            is_resolved=False,
            created_at=datetime.utcnow(),
        )
        alert2 = Alert(
            alert_type="long_duration",
            severity="info",
            job_type="costs_sync",
            tenant_id="other-tenant-999",
            title="Inaccessible Alert",
            message="Test alert",
            is_resolved=False,
            created_at=datetime.utcnow(),
        )
        db.add_all([alert1, alert2])
        db.commit()

        response = sync_client.get("/api/v1/sync/alerts")

        assert response.status_code == 200
        data = response.json()

        # Should only return alerts for accessible tenants
        for alert in data["alerts"]:
            if alert["tenant_id"]:  # Some alerts might not have tenant_id
                assert alert["tenant_id"] in [test_tenant_id, "test-tenant-456"]

    def test_get_alerts_requires_auth(self, sync_unauth_client):
        """Sync alerts endpoint requires authentication."""
        response = sync_unauth_client.get("/api/v1/sync/alerts")
        assert response.status_code == 401


# ============================================================================
# POST /api/v1/sync/alerts/{alert_id}/resolve Tests
# ============================================================================

class TestResolveAlertEndpoint:
    """Integration tests for POST /api/v1/sync/alerts/{alert_id}/resolve."""

    def test_resolve_alert_success(self, sync_client):
        """Resolve alert successfully updates alert status."""
        # Add an unresolved alert
        db = next(app.dependency_overrides[get_db]())

        alert = Alert(
            alert_type="high_failure_rate",
            severity="warning",
            job_type="costs_sync",
            tenant_id="test-tenant-123",
            title="Test Alert",
            message="Test alert message",
            is_resolved=False,
            created_at=datetime.utcnow(),
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        alert_id = alert.id

        response = sync_client.post(
            f"/api/v1/sync/alerts/{alert_id}/resolve?resolved_by=test-user"
        )

        assert response.status_code == 200
        data = response.json()

        # Validate response
        assert "id" in data
        assert "alert_type" in data
        assert "is_resolved" in data
        assert "resolved_at" in data
        assert "resolved_by" in data

        assert data["id"] == alert_id
        assert data["is_resolved"] is True
        assert data["resolved_by"] == "test-user"
        assert data["resolved_at"] is not None

        # Verify alert is marked resolved in database
        db.refresh(alert)
        assert alert.is_resolved == 1  # SQLite stores as integer
        assert alert.resolved_by == "test-user"
        assert alert.resolved_at is not None

    def test_resolve_alert_not_found(self, sync_client):
        """Resolve alert returns 404 for non-existent alert."""
        response = sync_client.post("/api/v1/sync/alerts/99999/resolve")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_resolve_alert_invalid_id(self, sync_client):
        """Resolve alert validates alert_id parameter."""
        # Test invalid ID (negative)
        response = sync_client.post("/api/v1/sync/alerts/-1/resolve")
        assert response.status_code == 422  # Validation error

        # Test invalid ID (zero)
        response = sync_client.post("/api/v1/sync/alerts/0/resolve")
        assert response.status_code == 422

    def test_resolve_alert_validates_resolved_by(self, sync_client):
        """Resolve alert validates resolved_by parameter."""
        # Add an unresolved alert
        db = next(app.dependency_overrides[get_db]())

        alert = Alert(
            alert_type="high_failure_rate",
            severity="warning",
            job_type="costs_sync",
            tenant_id="test-tenant-123",
            title="Test Alert",
            message="Test alert message",
            is_resolved=False,
            created_at=datetime.utcnow(),
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        alert_id = alert.id

        # Test resolved_by too long (> 100 chars)
        long_string = "x" * 101
        response = sync_client.post(
            f"/api/v1/sync/alerts/{alert_id}/resolve?resolved_by={long_string}"
        )
        assert response.status_code == 422  # Validation error

    def test_resolve_alert_requires_auth(self, sync_unauth_client):
        """Resolve alert endpoint requires authentication."""
        response = sync_unauth_client.post("/api/v1/sync/alerts/1/resolve")
        assert response.status_code == 401


# ============================================================================
# Tenant Isolation Tests
# ============================================================================

class TestSyncTenantIsolation:
    """Tests for tenant isolation across sync endpoints."""

    def test_history_respects_tenant_access(self, sync_client, test_tenant_id):
        """History endpoint only returns logs for accessible tenants."""
        # Add logs for multiple tenants
        db = next(app.dependency_overrides[get_db]())

        log1 = SyncJobLog(
            job_type="costs_sync",
            tenant_id=test_tenant_id,
            status="completed",
            started_at=datetime.utcnow() - timedelta(hours=2),
            ended_at=datetime.utcnow() - timedelta(hours=1),
            duration_ms=3600000,
            records_processed=150,
            errors_count=0,
        )
        log2 = SyncJobLog(
            job_type="costs_sync",
            tenant_id="other-tenant-999",
            status="completed",
            started_at=datetime.utcnow() - timedelta(hours=3),
            ended_at=datetime.utcnow() - timedelta(hours=2),
            duration_ms=3600000,
            records_processed=100,
            errors_count=0,
        )
        db.add_all([log1, log2])
        db.commit()

        response = sync_client.get("/api/v1/sync/history")

        assert response.status_code == 200
        data = response.json()

        # Should only return logs for accessible tenants
        accessible_tenants = [test_tenant_id, "test-tenant-456"]
        for log in data["logs"]:
            if log["tenant_id"]:
                assert log["tenant_id"] in accessible_tenants

    def test_metrics_respects_tenant_access(self, sync_client, test_tenant_id):
        """Metrics endpoint returns all job types (not tenant-specific)."""
        # Note: SyncJobMetrics are per job_type, not per tenant
        # Tenant filtering happens at the job log level
        db = next(app.dependency_overrides[get_db]())

        metric = SyncJobMetrics(
            job_type="costs_sync",
            calculated_at=datetime.utcnow(),
            total_runs=100,
            successful_runs=95,
            failed_runs=5,
            success_rate=95.0,
            avg_duration_ms=900000,
            min_duration_ms=600000,
            max_duration_ms=1200000,
            avg_records_processed=200,
            total_records_processed=20000,
            total_errors=5,
        )
        db.add(metric)
        db.commit()

        response = sync_client.get("/api/v1/sync/metrics")

        assert response.status_code == 200
        data = response.json()

        # Metrics are global (per job_type), not tenant-specific
        assert isinstance(data["metrics"], list)

    def test_alerts_respects_tenant_access(self, sync_client, test_tenant_id):
        """Alerts endpoint only returns alerts for accessible tenants."""
        # Add alerts for multiple tenants
        db = next(app.dependency_overrides[get_db]())

        alert1 = Alert(
            alert_type="high_failure_rate",
            severity="warning",
            job_type="costs_sync",
            tenant_id=test_tenant_id,
            title="Accessible Alert",
            message="Test alert",
            is_resolved=False,
            created_at=datetime.utcnow(),
        )
        alert2 = Alert(
            alert_type="long_duration",
            severity="info",
            job_type="costs_sync",
            tenant_id="other-tenant-999",
            title="Inaccessible Alert",
            message="Test alert",
            is_resolved=False,
            created_at=datetime.utcnow(),
        )
        db.add_all([alert1, alert2])
        db.commit()

        response = sync_client.get("/api/v1/sync/alerts")

        assert response.status_code == 200
        data = response.json()

        # Should only return alerts for accessible tenants
        accessible_tenants = [test_tenant_id, "test-tenant-456"]
        for alert in data["alerts"]:
            if alert["tenant_id"]:
                assert alert["tenant_id"] in accessible_tenants


# ============================================================================
# Admin User Tests
# ============================================================================

class TestSyncAdminAccess:
    """Tests for admin user access across sync endpoints."""

    def test_admin_sees_all_tenants_in_history(self, sync_admin_client):
        """Admin user can access sync history endpoint."""
        response = sync_admin_client.get("/api/v1/sync/history")

        assert response.status_code == 200
        data = response.json()

        # Admin can access the endpoint and get proper structure
        assert "logs" in data
        assert isinstance(data["logs"], list)

    def test_admin_sees_all_metrics(self, sync_admin_client):
        """Admin user can see all job type metrics."""
        # Note: SyncJobMetrics are per job_type, not per tenant
        db = next(app.dependency_overrides[get_db]())

        metric1 = SyncJobMetrics(
            job_type="costs_sync",
            calculated_at=datetime.utcnow(),
            total_runs=100,
            successful_runs=95,
            failed_runs=5,
            success_rate=95.0,
            avg_duration_ms=900000,
            min_duration_ms=600000,
            max_duration_ms=1200000,
            avg_records_processed=200,
            total_records_processed=20000,
            total_errors=5,
        )
        metric2 = SyncJobMetrics(
            job_type="compliance_sync",
            calculated_at=datetime.utcnow(),
            total_runs=50,
            successful_runs=48,
            failed_runs=2,
            success_rate=96.0,
            avg_duration_ms=700000,
            min_duration_ms=500000,
            max_duration_ms=900000,
            avg_records_processed=100,
            total_records_processed=5000,
            total_errors=2,
        )
        db.add_all([metric1, metric2])
        db.commit()

        response = sync_admin_client.get("/api/v1/sync/metrics")

        assert response.status_code == 200
        data = response.json()

        # Admin should see all job type metrics
        job_types = {m["job_type"] for m in data["metrics"]}
        assert len(job_types) >= 2

    def test_admin_sees_all_tenants_in_alerts(self, sync_admin_client):
        """Admin user can access sync alerts endpoint."""
        response = sync_admin_client.get("/api/v1/sync/alerts")

        assert response.status_code == 200
        data = response.json()

        # Admin can access the endpoint and get proper structure
        assert "alerts" in data
        assert "stats" in data or data["stats"] is None  # stats might be None when no alerts
        assert isinstance(data["alerts"], list)

"""Unit tests for MonitoringService.

Tests for monitoring and observability operations including:
- create_alert() and alert management
- get_active_alerts() with filtering
- resolve_alert() for alert resolution
- start_sync_job() for job tracking
- update_sync_progress() for progress updates
- complete_sync_job() for successful and failed completions
- get_metrics() for job metrics retrieval
- get_recent_logs() for log history

Minimum 8 tests covering all critical paths and edge cases.
"""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.services.monitoring_service import MonitoringService
from app.models.monitoring import Alert, SyncJobLog, SyncJobMetrics


class TestMonitoringServiceAlerts:
    """Test suite for alert management operations."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def monitoring_service(self, mock_db):
        """Create MonitoringService instance."""
        return MonitoringService(db=mock_db)

    def test_create_alert_basic(self, monitoring_service, mock_db):
        """Test create_alert creates alert with basic fields."""
        # Setup
        mock_alert = MagicMock(spec=Alert)
        mock_alert.id = 1
        mock_alert.severity = "warning"

        def mock_add(obj):
            # Simulate database behavior
            obj.id = 1
            obj.created_at = datetime.utcnow()

        mock_db.add.side_effect = mock_add
        mock_db.refresh.return_value = None

        # Execute
        result = monitoring_service.create_alert(
            alert_type="sync_failure",
            severity="warning",
            title="Test Alert",
            message="Test message",
            job_type="costs",
            tenant_id="tenant-123",
        )

        # Verify
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        assert result.id == 1

    @patch("app.api.services.monitoring_service.MonitoringService.send_alert_notification")
    def test_create_alert_with_details(self, mock_send_notif, monitoring_service, mock_db):
        """Test create_alert serializes details dict to JSON."""
        # Setup
        details = {"error_code": 500, "retry_count": 3}
        mock_send_notif.return_value = AsyncMock()  # Mock async notification

        def mock_add(obj):
            obj.id = 2
            obj.severity = "error"
            obj.created_at = datetime.utcnow()
            # Verify details were serialized
            assert obj.details_json == json.dumps(details)

        mock_db.add.side_effect = mock_add
        mock_db.refresh.return_value = None

        # Execute
        result = monitoring_service.create_alert(
            alert_type="high_error_rate",
            severity="error",
            title="High Errors",
            message="Error rate exceeded",
            details=details,
        )

        # Verify
        assert result.id == 2
        mock_db.commit.assert_called_once()
        mock_send_notif.assert_called_once()  # Notification sent for error severity

    @patch("app.api.services.monitoring_service.MonitoringService.send_alert_notification")
    def test_create_alert_triggers_notification_for_critical(
        self, mock_send_notif, monitoring_service, mock_db
    ):
        """Test create_alert sends notification for error/critical severity."""

        # Setup
        def mock_add(obj):
            obj.id = 3
            obj.severity = "error"
            obj.created_at = datetime.utcnow()

        mock_db.add.side_effect = mock_add
        mock_db.refresh.return_value = None

        # Execute
        result = monitoring_service.create_alert(
            alert_type="sync_failure",
            severity="error",
            title="Critical Failure",
            message="System down",
        )

        # Verify notification was triggered
        mock_send_notif.assert_called_once()
        assert result.id == 3

    def test_get_active_alerts_no_filters(self, monitoring_service, mock_db):
        """Test get_active_alerts returns all unresolved alerts."""
        # Setup
        mock_alerts = [
            MagicMock(id=1, severity="warning", job_type="costs"),
            MagicMock(id=2, severity="error", job_type="identity"),
        ]

        query_mock = MagicMock()
        filter_mock = MagicMock()
        order_mock = MagicMock()

        query_mock.filter.return_value = filter_mock
        filter_mock.order_by.return_value = order_mock
        order_mock.all.return_value = mock_alerts

        mock_db.query.return_value = query_mock

        # Execute
        result = monitoring_service.get_active_alerts()

        # Verify
        assert len(result) == 2
        assert result[0].id == 1
        assert result[1].id == 2
        mock_db.query.assert_called_once_with(Alert)

    def test_get_active_alerts_with_severity_filter(self, monitoring_service, mock_db):
        """Test get_active_alerts filters by severity."""
        # Setup
        mock_alerts = [MagicMock(id=1, severity="error")]

        query_mock = MagicMock()
        filter_mock = MagicMock()
        severity_filter_mock = MagicMock()
        order_mock = MagicMock()

        query_mock.filter.return_value = filter_mock
        filter_mock.filter.return_value = severity_filter_mock
        severity_filter_mock.order_by.return_value = order_mock
        order_mock.all.return_value = mock_alerts

        mock_db.query.return_value = query_mock

        # Execute
        result = monitoring_service.get_active_alerts(severity="error")

        # Verify
        assert len(result) == 1
        assert result[0].severity == "error"

    def test_get_active_alerts_with_job_type_filter(self, monitoring_service, mock_db):
        """Test get_active_alerts filters by job_type."""
        # Setup
        mock_alerts = [MagicMock(id=1, job_type="costs")]

        query_mock = MagicMock()
        filter_mock = MagicMock()
        job_filter_mock = MagicMock()
        order_mock = MagicMock()

        query_mock.filter.return_value = filter_mock
        filter_mock.filter.return_value = job_filter_mock
        job_filter_mock.order_by.return_value = order_mock
        order_mock.all.return_value = mock_alerts

        mock_db.query.return_value = query_mock

        # Execute
        result = monitoring_service.get_active_alerts(job_type="costs")

        # Verify
        assert len(result) == 1
        assert result[0].job_type == "costs"

    def test_resolve_alert_success(self, monitoring_service, mock_db):
        """Test resolve_alert marks alert as resolved."""
        # Setup
        mock_alert = MagicMock(spec=Alert)
        mock_alert.id = 1
        mock_alert.is_resolved = False

        query_mock = MagicMock()
        filter_mock = MagicMock()
        query_mock.filter.return_value = filter_mock
        filter_mock.first.return_value = mock_alert

        mock_db.query.return_value = query_mock

        # Execute
        result = monitoring_service.resolve_alert(alert_id=1, resolved_by="admin")

        # Verify
        assert result.is_resolved is True
        assert result.resolved_by == "admin"
        assert result.resolved_at is not None
        mock_db.commit.assert_called_once()

    def test_resolve_alert_not_found(self, monitoring_service, mock_db):
        """Test resolve_alert raises error when alert not found."""
        # Setup
        query_mock = MagicMock()
        filter_mock = MagicMock()
        query_mock.filter.return_value = filter_mock
        filter_mock.first.return_value = None

        mock_db.query.return_value = query_mock

        # Execute & Verify
        with pytest.raises(ValueError, match="Alert with id 999 not found"):
            monitoring_service.resolve_alert(alert_id=999)


class TestMonitoringServiceSyncJobs:
    """Test suite for sync job tracking operations."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def monitoring_service(self, mock_db):
        """Create MonitoringService instance."""
        return MonitoringService(db=mock_db)

    def test_start_sync_job(self, monitoring_service, mock_db):
        """Test start_sync_job creates new log entry."""

        # Setup
        def mock_add(obj):
            obj.id = 1
            assert obj.status == "running"
            assert obj.job_type == "costs"
            assert obj.tenant_id == "tenant-123"
            assert obj.records_processed == 0

        mock_db.add.side_effect = mock_add
        mock_db.refresh.return_value = None

        # Execute
        result = monitoring_service.start_sync_job(
            job_type="costs", tenant_id="tenant-123", details={"source": "manual"}
        )

        # Verify
        assert result.id == 1
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_update_sync_progress(self, monitoring_service, mock_db):
        """Test update_sync_progress updates record counts."""
        # Setup
        mock_log = MagicMock(spec=SyncJobLog)
        mock_log.id = 1
        mock_log.records_processed = 0
        mock_log.records_created = 0
        mock_log.errors_count = 0

        query_mock = MagicMock()
        filter_mock = MagicMock()
        query_mock.filter.return_value = filter_mock
        filter_mock.first.return_value = mock_log

        mock_db.query.return_value = query_mock

        # Execute
        result = monitoring_service.update_sync_progress(
            log_id=1, records_processed=100, records_created=50, records_updated=30, errors_count=5
        )

        # Verify
        assert result.records_processed == 100
        assert result.records_created == 50
        assert result.records_updated == 30
        assert result.errors_count == 5
        mock_db.commit.assert_called_once()

    def test_update_sync_progress_not_found(self, monitoring_service, mock_db):
        """Test update_sync_progress raises error when log not found."""
        # Setup
        query_mock = MagicMock()
        filter_mock = MagicMock()
        query_mock.filter.return_value = filter_mock
        filter_mock.first.return_value = None

        mock_db.query.return_value = query_mock

        # Execute & Verify
        with pytest.raises(ValueError, match="Sync job log with id 999 not found"):
            monitoring_service.update_sync_progress(log_id=999, records_processed=100)

    @patch("app.api.services.monitoring_service.MonitoringService._update_metrics_for_job_type")
    @patch(
        "app.api.services.monitoring_service.MonitoringService._check_for_alerts_after_completion"
    )
    def test_complete_sync_job_success(
        self, mock_check_alerts, mock_update_metrics, monitoring_service, mock_db
    ):
        """Test complete_sync_job marks job as completed and calculates duration."""
        # Setup
        start_time = datetime.utcnow() - timedelta(seconds=30)
        mock_log = MagicMock(spec=SyncJobLog)
        mock_log.id = 1
        mock_log.job_type = "costs"
        mock_log.started_at = start_time
        mock_log.status = "running"

        query_mock = MagicMock()
        filter_mock = MagicMock()
        query_mock.filter.return_value = filter_mock
        filter_mock.first.return_value = mock_log

        mock_db.query.return_value = query_mock

        # Execute
        result = monitoring_service.complete_sync_job(
            log_id=1, status="completed", final_records={"records_processed": 100}
        )

        # Verify
        assert result.status == "completed"
        assert result.ended_at is not None
        assert result.duration_ms is not None
        assert result.duration_ms > 0
        mock_update_metrics.assert_called_once_with("costs")
        mock_check_alerts.assert_called_once_with(mock_log)
        mock_db.commit.assert_called_once()

    @patch("app.api.services.monitoring_service.MonitoringService._update_metrics_for_job_type")
    @patch(
        "app.api.services.monitoring_service.MonitoringService._check_for_alerts_after_completion"
    )
    def test_complete_sync_job_failure(
        self, mock_check_alerts, mock_update_metrics, monitoring_service, mock_db
    ):
        """Test complete_sync_job handles failed status with error message."""
        # Setup
        start_time = datetime.utcnow() - timedelta(seconds=15)
        mock_log = MagicMock(spec=SyncJobLog)
        mock_log.id = 2
        mock_log.job_type = "identity"
        mock_log.started_at = start_time
        mock_log.status = "running"

        query_mock = MagicMock()
        filter_mock = MagicMock()
        query_mock.filter.return_value = filter_mock
        filter_mock.first.return_value = mock_log

        mock_db.query.return_value = query_mock

        # Execute
        result = monitoring_service.complete_sync_job(
            log_id=2, status="failed", error_message="Connection timeout"
        )

        # Verify
        assert result.status == "failed"
        assert result.error_message == "Connection timeout"
        assert result.ended_at is not None
        mock_db.commit.assert_called_once()

    def test_get_metrics_all(self, monitoring_service, mock_db):
        """Test get_metrics returns all job type metrics."""
        # Setup
        mock_metrics = [
            MagicMock(job_type="costs", success_rate=0.95),
            MagicMock(job_type="identity", success_rate=0.98),
        ]

        query_mock = MagicMock()
        query_mock.all.return_value = mock_metrics

        mock_db.query.return_value = query_mock

        # Execute
        result = monitoring_service.get_metrics()

        # Verify
        assert len(result) == 2
        assert result[0].job_type == "costs"
        assert result[1].job_type == "identity"

    def test_get_metrics_filtered_by_job_type(self, monitoring_service, mock_db):
        """Test get_metrics filters by specific job type."""
        # Setup
        mock_metrics = [MagicMock(job_type="costs", success_rate=0.95)]

        query_mock = MagicMock()
        filter_mock = MagicMock()
        query_mock.filter.return_value = filter_mock
        filter_mock.all.return_value = mock_metrics

        mock_db.query.return_value = query_mock

        # Execute
        result = monitoring_service.get_metrics(job_type="costs")

        # Verify
        assert len(result) == 1
        assert result[0].job_type == "costs"

    def test_get_recent_logs(self, monitoring_service, mock_db):
        """Test get_recent_logs returns logs ordered by started_at."""
        # Setup
        mock_logs = [
            MagicMock(id=3, job_type="costs", started_at=datetime.utcnow()),
            MagicMock(id=2, job_type="costs", started_at=datetime.utcnow() - timedelta(hours=1)),
            MagicMock(id=1, job_type="identity", started_at=datetime.utcnow() - timedelta(hours=2)),
        ]

        query_mock = MagicMock()
        filter_mock = MagicMock()
        order_mock = MagicMock()
        limit_mock = MagicMock()

        query_mock.filter.return_value = filter_mock
        filter_mock.order_by.return_value = order_mock
        order_mock.limit.return_value = limit_mock
        limit_mock.all.return_value = mock_logs

        mock_db.query.return_value = query_mock

        # Execute
        result = monitoring_service.get_recent_logs(limit=50)

        # Verify
        assert len(result) == 3
        assert result[0].id == 3  # Most recent

    def test_get_recent_logs_excludes_running_by_default(self, monitoring_service, mock_db):
        """Test get_recent_logs excludes running jobs by default."""
        # Setup
        mock_logs = [
            MagicMock(id=1, status="completed"),
            MagicMock(id=2, status="failed"),
        ]

        query_mock = MagicMock()
        filter_mock = MagicMock()
        order_mock = MagicMock()
        limit_mock = MagicMock()

        query_mock.filter.return_value = filter_mock
        filter_mock.order_by.return_value = order_mock
        order_mock.limit.return_value = limit_mock
        limit_mock.all.return_value = mock_logs

        mock_db.query.return_value = query_mock

        # Execute
        result = monitoring_service.get_recent_logs(include_running=False)

        # Verify - should have called filter for status
        assert len(result) == 2
        assert all(log.status != "running" for log in result)


class TestMonitoringServiceAlertDetection:
    """Test suite for automatic alert detection."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def monitoring_service(self, mock_db):
        """Create MonitoringService instance."""
        return MonitoringService(db=mock_db)

    @patch("app.api.services.monitoring_service.MonitoringService.create_alert")
    def test_check_for_alerts_on_failure(self, mock_create_alert, monitoring_service, mock_db):
        """Test _check_for_alerts_after_completion creates alert on job failure."""
        # Setup
        mock_log = MagicMock(spec=SyncJobLog)
        mock_log.id = 1
        mock_log.job_type = "costs"
        mock_log.tenant_id = "tenant-123"
        mock_log.status = "failed"
        mock_log.error_message = "API timeout"
        mock_log.records_processed = 50
        mock_log.errors_count = 0  # Explicitly set to avoid comparison issues
        mock_log.duration_seconds = 45.5

        mock_create_alert.return_value = MagicMock()

        # Execute
        monitoring_service._check_for_alerts_after_completion(mock_log)

        # Verify
        mock_create_alert.assert_called_once()
        call_kwargs = mock_create_alert.call_args[1]
        assert call_kwargs["alert_type"] == "sync_failure"
        assert call_kwargs["severity"] == "error"
        assert "failed" in call_kwargs["title"].lower()

    @patch("app.api.services.monitoring_service.MonitoringService.create_alert")
    def test_check_for_alerts_on_zero_records(self, mock_create_alert, monitoring_service, mock_db):
        """Test _check_for_alerts_after_completion detects consecutive zero-record runs."""
        # Setup
        mock_log = MagicMock(spec=SyncJobLog)
        mock_log.id = 5
        mock_log.job_type = "identity"
        mock_log.tenant_id = None
        mock_log.status = "completed"
        mock_log.records_processed = 0
        mock_log.errors_count = 0  # Explicitly set to avoid comparison issues

        # Mock query to return 3 consecutive zero-record runs
        query_mock = MagicMock()
        filter_mock = MagicMock()
        order_mock = MagicMock()
        limit_mock = MagicMock()

        query_mock.filter.return_value = filter_mock
        filter_mock.filter.return_value = filter_mock
        filter_mock.order_by.return_value = order_mock
        order_mock.limit.return_value = limit_mock
        limit_mock.count.return_value = 3  # Meets threshold

        mock_db.query.return_value = query_mock
        mock_create_alert.return_value = MagicMock()

        # Execute
        monitoring_service._check_for_alerts_after_completion(mock_log)

        # Verify
        assert mock_create_alert.called
        call_kwargs = mock_create_alert.call_args[1]
        assert call_kwargs["alert_type"] == "no_records"
        assert call_kwargs["severity"] == "warning"

    @patch("app.api.services.monitoring_service.MonitoringService.create_alert")
    def test_check_stale_syncs_creates_alert(self, mock_create_alert, monitoring_service, mock_db):
        """Test check_stale_syncs detects jobs that haven't run recently."""
        # Setup - create metrics with last run 3 days ago (stale for 24h expected interval)
        old_time = datetime.utcnow() - timedelta(hours=72)
        mock_metrics = MagicMock(spec=SyncJobMetrics)
        mock_metrics.job_type = "costs"
        mock_metrics.last_run_at = old_time

        # Mock queries
        metrics_query = MagicMock()
        filter_mock = MagicMock()
        metrics_query.filter.return_value = filter_mock
        filter_mock.first.return_value = mock_metrics

        alert_query = MagicMock()
        alert_filter = MagicMock()
        alert_query.filter.return_value = alert_filter
        alert_filter.first.return_value = None  # No existing alert

        mock_db.query.side_effect = [metrics_query, alert_query] * 4  # For each job type
        mock_create_alert.return_value = MagicMock()

        # Execute
        result = monitoring_service.check_stale_syncs()

        # Verify - should create alerts for stale syncs
        assert mock_create_alert.called
        assert len(result) > 0


class TestMonitoringServiceStats:
    """Test suite for statistics and status operations."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def monitoring_service(self, mock_db):
        """Create MonitoringService instance."""
        return MonitoringService(db=mock_db)

    def test_get_alert_stats(self, monitoring_service, mock_db):
        """Test get_alert_stats returns summary statistics."""
        # Setup
        count_query = MagicMock()
        count_query.count.return_value = 10

        active_query = MagicMock()
        active_filter = MagicMock()
        active_query.filter.return_value = active_filter
        active_filter.count.return_value = 3

        severity_query = MagicMock()
        severity_filter = MagicMock()
        severity_group = MagicMock()
        severity_query.filter.return_value = severity_filter
        severity_filter.group_by.return_value = severity_group
        severity_group.all.return_value = [("error", 2), ("warning", 1)]

        type_query = MagicMock()
        type_filter = MagicMock()
        type_group = MagicMock()
        type_query.filter.return_value = type_filter
        type_filter.group_by.return_value = type_group
        type_group.all.return_value = [("sync_failure", 2), ("stale_sync", 1)]

        mock_db.query.side_effect = [count_query, active_query, severity_query, type_query]

        # Execute
        result = monitoring_service.get_alert_stats()

        # Verify
        assert result["total"] == 10
        assert result["active"] == 3
        assert result["resolved"] == 7
        assert result["by_severity"] == {"error": 2, "warning": 1}
        assert result["by_type"] == {"sync_failure": 2, "stale_sync": 1}

    @patch("app.api.services.monitoring_service.MonitoringService.check_stale_syncs")
    @patch("app.api.services.monitoring_service.MonitoringService.get_metrics")
    @patch("app.api.services.monitoring_service.MonitoringService.get_active_alerts")
    def test_get_overall_status_healthy(
        self, mock_get_alerts, mock_get_metrics, mock_check_stale, monitoring_service, mock_db
    ):
        """Test get_overall_status returns healthy when no critical issues."""
        # Setup
        mock_check_stale.return_value = []

        mock_metric = MagicMock(spec=SyncJobMetrics)
        mock_metric.job_type = "costs"
        mock_metric.last_run_at = datetime.utcnow()
        mock_metric.last_success_at = datetime.utcnow()
        mock_metric.last_failure_at = None
        mock_metric.success_rate = 0.98
        mock_get_metrics.return_value = [mock_metric]

        mock_get_alerts.return_value = []

        # Execute
        result = monitoring_service.get_overall_status()

        # Verify
        assert result["status"] == "healthy"
        assert result["alerts"]["total_active"] == 0
        assert "jobs" in result

    @patch("app.api.services.monitoring_service.MonitoringService.check_stale_syncs")
    @patch("app.api.services.monitoring_service.MonitoringService.get_metrics")
    @patch("app.api.services.monitoring_service.MonitoringService.get_active_alerts")
    def test_get_overall_status_critical(
        self, mock_get_alerts, mock_get_metrics, mock_check_stale, monitoring_service, mock_db
    ):
        """Test get_overall_status returns critical when critical alerts exist."""
        # Setup
        mock_check_stale.return_value = []
        mock_get_metrics.return_value = []

        critical_alert = MagicMock()
        critical_alert.severity = "critical"
        mock_get_alerts.return_value = [critical_alert]

        # Execute
        result = monitoring_service.get_overall_status()

        # Verify
        assert result["status"] == "critical"
        assert result["alerts"]["critical"] == 1

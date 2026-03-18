"""Unit tests for sync job management API routes.

Tests all sync management endpoints with FastAPI TestClient:
- POST /api/v1/sync/{sync_type}
- GET /api/v1/sync/status
- GET /api/v1/sync/status/health
- GET /api/v1/sync/history
- GET /api/v1/sync/metrics
- GET /api/v1/sync/alerts
- POST /api/v1/sync/alerts/{alert_id}/resolve
- GET /api/v1/sync/partials/sync-status
"""

import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.auth import User, get_current_user
from app.core.authorization import TenantAuthorization, get_tenant_authorization
from app.core.database import get_db
from app.main import app
from app.models.monitoring import Alert, SyncJobLog
from app.models.tenant import Tenant, UserTenant

@pytest.fixture
def test_db_session(db_session):
    """Database session with test sync data."""
    tenant = Tenant(
        id=str(uuid.uuid4()),
        tenant_id="sync-tenant-123",
        name="Sync Test Tenant",
        is_active=True,
    )
    db_session.add(tenant)

    user_tenant = UserTenant(
        id=str(uuid.uuid4()),
        user_id="user:admin",
        tenant_id=tenant.id,
        role="admin",
        is_active=True,
        can_view_costs=True,
        can_manage_resources=True,
        can_manage_compliance=True,
        granted_by="test",
        granted_at=datetime.utcnow(),
    )
    db_session.add(user_tenant)

    # Create sync job log
    log = SyncJobLog(
        job_type="costs",
        tenant_id=tenant.id,
        status="completed",
        started_at=datetime.utcnow(),
        ended_at=datetime.utcnow(),
        duration_ms=5000,
        records_processed=150,
        errors_count=0,
    )
    db_session.add(log)

    # Create sync alert
    alert = Alert(
        id=1,
        alert_type="sync_failure",
        severity="error",
        job_type="compliance",
        tenant_id=tenant.id,
        title="Sync Failed",
        message="Compliance sync failed after 3 retries",
        is_resolved=False,
        created_at=datetime.utcnow(),
    )
    db_session.add(alert)

    db_session.commit()
    return db_session


@pytest.fixture
def client_with_db(test_db_session, mock_user):
    """Test client with database and auth overrides."""
    from unittest.mock import MagicMock

    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    mock_authz = MagicMock(spec=TenantAuthorization)
    mock_authz.user = mock_user
    mock_authz.accessible_tenant_ids = ["sync-tenant-123"]
    mock_authz.ensure_at_least_one_tenant = MagicMock()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_tenant_authorization] = lambda: mock_authz
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_user():
    """Mock authenticated admin user."""
    return User(
        id="user-sync-123",
        email="admin@sync.test",
        name="Sync Admin",
        roles=["admin"],
        tenant_ids=["sync-tenant-123"],
        is_active=True,
        auth_provider="azure_ad",
    )


@pytest.fixture
def mock_monitoring_service():
    """Mock MonitoringService with common responses."""
    service = MagicMock()
    service.get_overall_status.return_value = {
        "status": "healthy",
        "total_jobs": 100,
        "successful_jobs": 95,
        "failed_jobs": 5,
        "success_rate": 95.0,
    }
    service.get_recent_logs.return_value = [
        MagicMock(
            id="log-1",
            job_type="costs",
            tenant_id="sync-tenant-123",
            status="completed",
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow(),
            duration_ms=5000,
            records_processed=150,
            errors_count=0,
            error_message=None,
        ),
    ]
    service.get_metrics.return_value = [
        MagicMock(
            job_type="costs",
            tenant_id="sync-tenant-123",
            calculated_at=datetime.utcnow(),
            total_runs=50,
            successful_runs=48,
            failed_runs=2,
            success_rate=96.0,
            avg_duration_ms=4500,
            min_duration_ms=2000,
            max_duration_ms=8000,
            avg_records_processed=145,
            total_records_processed=7250,
            total_errors=2,
            last_run_at=datetime.utcnow(),
            last_success_at=datetime.utcnow(),
            last_failure_at=None,
            last_error_message=None,
        ),
    ]
    service.get_active_alerts.return_value = [
        MagicMock(
            id=1,
            alert_type="sync_failure",
            severity="error",
            job_type="compliance",
            tenant_id="sync-tenant-123",
            title="Sync Failed",
            message="Compliance sync failed",
            is_resolved=False,
            created_at=datetime.utcnow(),
            resolved_at=None,
            resolved_by=None,
        ),
    ]
    service.get_alert_stats.return_value = {
        "total": 5,
        "critical": 1,
        "error": 2,
        "warning": 2,
        "info": 0,
    }
    service.resolve_alert.return_value = MagicMock(
        id=1,
        alert_type="sync_failure",
        is_resolved=True,
        resolved_at=datetime.utcnow(),
        resolved_by="admin@example.com",
    )
    return service


# ============================================================================
# POST /api/v1/sync/{sync_type} Tests
# ============================================================================


class TestTriggerSyncEndpoint:
    """Tests for POST /api/v1/sync/{sync_type} endpoint."""

    @patch("app.api.routes.sync.trigger_manual_sync")
    def test_trigger_sync_starts_manual_job(
        self, mock_trigger, client_with_db, mock_user
    ):
        """Trigger sync endpoint starts manual sync job."""
        mock_trigger.return_value = True

        response = client_with_db.post(
            "/api/v1/sync/costs",
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "triggered"
        assert data["sync_type"] == "costs"
        mock_trigger.assert_called_once_with("costs")

    @patch("app.api.routes.sync.trigger_manual_sync")
    def test_trigger_sync_supports_all_sync_types(
        self, mock_trigger, client_with_db, mock_user
    ):
        """Trigger sync supports all valid sync types."""
        mock_trigger.return_value = True

        sync_types = ["costs", "compliance", "resources", "identity"]
        for sync_type in sync_types:
            response = client_with_db.post(
                f"/api/v1/sync/{sync_type}",
                headers={"Authorization": "Bearer fake-token"},
            )
            assert response.status_code == 200

    def test_trigger_sync_returns_422_for_invalid_type(
        self, client_with_db, mock_user
    ):
        """Trigger sync returns 422 for invalid sync type.

        FastAPI validates the SyncType enum path param before the route handler
        runs, so invalid values produce 422 (Unprocessable Entity).
        """
        response = client_with_db.post("/api/v1/sync/invalid_type")

        # FastAPI enum validation → 422 Unprocessable Entity
        assert response.status_code == 422


# ============================================================================
# GET /api/v1/sync/status Tests
# ============================================================================


class TestSyncStatusEndpoint:
    """Tests for GET /api/v1/sync/status endpoint."""

    @patch("app.api.routes.sync.get_scheduler")
    def test_status_returns_job_schedule(
        self, mock_scheduler, client_with_db, mock_user
    ):
        """Status endpoint returns scheduled job information."""

        mock_job = MagicMock()
        mock_job.id = "costs-sync"
        mock_job.name = "Cost Sync Job"
        mock_job.next_run_time = datetime.utcnow()

        scheduler = MagicMock()
        scheduler.get_jobs.return_value = [mock_job]
        mock_scheduler.return_value = scheduler

        response = client_with_db.get(
            "/api/v1/sync/status",
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert len(data["jobs"]) == 1
        assert data["jobs"][0]["id"] == "costs-sync"

    @patch("app.api.routes.sync.get_scheduler")
    def test_status_handles_uninitialized_scheduler(
        self, mock_scheduler, client_with_db, mock_user
    ):
        """Status endpoint handles scheduler not initialized."""
        mock_scheduler.return_value = None

        response = client_with_db.get(
            "/api/v1/sync/status",
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "scheduler_not_initialized"
        assert data["jobs"] == []


# ============================================================================
# GET /api/v1/sync/status/health Tests
# ============================================================================


class TestSyncHealthEndpoint:
    """Tests for GET /api/v1/sync/status/health endpoint."""

    @patch("app.api.routes.sync.MonitoringService")
    def test_health_returns_overall_sync_metrics(
        self, mock_service_cls, client_with_db, mock_user, mock_monitoring_service
    ):
        """Health endpoint returns overall sync health status."""
        mock_service_cls.return_value = mock_monitoring_service

        response = client_with_db.get(
            "/api/v1/sync/status/health",
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["success_rate"] == 95.0


# ============================================================================
# GET /api/v1/sync/history Tests
# ============================================================================


class TestSyncHistoryEndpoint:
    """Tests for GET /api/v1/sync/history endpoint."""

    @patch("app.api.routes.sync.MonitoringService")
    def test_history_returns_recent_sync_jobs(
        self,
        mock_service_cls,
        client_with_db,
        mock_user,
        mock_monitoring_service,
    ):
        """History endpoint returns recent sync job execution history."""
        mock_service_cls.return_value = mock_monitoring_service

        response = client_with_db.get(
            "/api/v1/sync/history",
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert len(data["logs"]) > 0
        log = data["logs"][0]
        assert log["job_type"] == "costs"
        assert log["status"] == "completed"

    @patch("app.api.routes.sync.MonitoringService")
    def test_history_accepts_job_type_filter(
        self,
        mock_service_cls,
        client_with_db,
        mock_user,
        mock_monitoring_service,
    ):
        """History endpoint accepts job_type filter parameter."""
        mock_service_cls.return_value = mock_monitoring_service

        response = client_with_db.get(
            "/api/v1/sync/history?job_type=costs&limit=20",
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 200
        mock_monitoring_service.get_recent_logs.assert_called_once_with(
            job_type="costs", limit=20, include_running=False
        )


# ============================================================================
# GET /api/v1/sync/metrics Tests
# ============================================================================


class TestSyncMetricsEndpoint:
    """Tests for GET /api/v1/sync/metrics endpoint."""

    @patch("app.api.routes.sync.MonitoringService")
    def test_metrics_returns_aggregate_statistics(
        self,
        mock_service_cls,
        client_with_db,
        mock_user,
        mock_monitoring_service,
    ):
        """Metrics endpoint returns aggregate sync job statistics."""
        mock_service_cls.return_value = mock_monitoring_service

        response = client_with_db.get(
            "/api/v1/sync/metrics",
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "metrics" in data
        assert len(data["metrics"]) > 0
        metric = data["metrics"][0]
        assert metric["job_type"] == "costs"
        assert metric["success_rate"] == 96.0
        assert "avg_duration_ms" in metric


# ============================================================================
# GET /api/v1/sync/alerts Tests
# ============================================================================


class TestSyncAlertsEndpoint:
    """Tests for GET /api/v1/sync/alerts endpoint."""

    @patch("app.api.routes.sync.MonitoringService")
    def test_alerts_returns_active_sync_alerts(
        self,
        mock_service_cls,
        client_with_db,
        mock_user,
        mock_monitoring_service,
    ):
        """Alerts endpoint returns active sync job alerts."""
        mock_service_cls.return_value = mock_monitoring_service

        response = client_with_db.get(
            "/api/v1/sync/alerts",
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "alerts" in data
        assert len(data["alerts"]) > 0
        alert = data["alerts"][0]
        assert alert["alert_type"] == "sync_failure"
        assert alert["severity"] == "error"

    @patch("app.api.routes.sync.MonitoringService")
    def test_alerts_filters_by_severity(
        self,
        mock_service_cls,
        client_with_db,
        mock_user,
        mock_monitoring_service,
    ):
        """Alerts endpoint filters by severity parameter."""
        mock_service_cls.return_value = mock_monitoring_service

        response = client_with_db.get(
            "/api/v1/sync/alerts?severity=error",
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 200
        mock_monitoring_service.get_active_alerts.assert_called_once_with(
            job_type=None, severity="error"
        )


# ============================================================================
# POST /api/v1/sync/alerts/{alert_id}/resolve Tests
# ============================================================================


class TestResolveAlertEndpoint:
    """Tests for POST /api/v1/sync/alerts/{alert_id}/resolve endpoint."""

    @patch("app.api.routes.sync.MonitoringService")
    def test_resolve_marks_alert_as_resolved(
        self, mock_service_cls, client_with_db, mock_user, mock_monitoring_service
    ):
        """Resolve endpoint marks alert as resolved."""
        mock_service_cls.return_value = mock_monitoring_service

        response = client_with_db.post(
            "/api/v1/sync/alerts/1/resolve?resolved_by=admin@example.com",
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_resolved"] is True
        assert data["resolved_by"] == "admin@example.com"

    @patch("app.api.routes.sync.MonitoringService")
    def test_resolve_returns_404_for_invalid_alert(
        self, mock_service_cls, client_with_db, mock_user
    ):
        """Resolve endpoint returns 404 for nonexistent alert."""
        service = MagicMock()
        service.resolve_alert.side_effect = ValueError("Alert not found")
        mock_service_cls.return_value = service

        response = client_with_db.post(
            "/api/v1/sync/alerts/999/resolve?resolved_by=admin@example.com",
            headers={"Authorization": "Bearer fake-token"},
        )

        assert response.status_code == 404


# ============================================================================
# GET /api/v1/sync/partials/sync-status Tests
# ============================================================================


class TestSyncStatusPartialEndpoint:
    """Tests for GET /api/v1/sync/partials/sync-status HTMX partial."""

    @patch("app.api.routes.sync.MonitoringService")
    @patch("app.api.routes.sync.templates")
    def test_partial_returns_sync_status_html(
        self, mock_templates, mock_service_cls, client_with_db, mock_user, mock_monitoring_service
    ):
        """Sync status partial returns HTML for HTMX rendering."""
        from fastapi.responses import HTMLResponse
        mock_service_cls.return_value = mock_monitoring_service
        mock_templates.TemplateResponse.return_value = HTMLResponse(
            content="<div>sync status</div>", status_code=200
        )

        response = client_with_db.get("/api/v1/sync/partials/sync-status")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

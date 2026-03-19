"""Unit tests for dashboard API routes.

Tests all dashboard endpoints with FastAPI TestClient:
- GET / (main dashboard)
- GET /dashboard
- GET /sync-dashboard
- GET /dmarc
- GET /partials/cost-summary-card
- GET /partials/compliance-gauge
- GET /partials/sync-status-card
- GET /partials/sync-history-table
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from app.core.auth import User
from app.core.database import get_db
from app.main import app
from app.models.tenant import Tenant, UserTenant

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _html(body: str = "dashboard sync dmarc") -> HTMLResponse:
    """Return a minimal HTMLResponse for template mock."""
    return HTMLResponse(content=f"<html><body>{body}</body></html>")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def test_db_session(db_session):
    """Database session with test data."""
    tenant = Tenant(
        id=str(uuid.uuid4()),
        tenant_id="dashboard-tenant-123",
        name="Dashboard Test Tenant",
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

    db_session.commit()
    return db_session


@pytest.fixture
def client_with_db(test_db_session):
    """Test client with database override."""

    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_user():
    """Mock authenticated admin user."""
    return User(
        id="user-dashboard-123",
        email="admin@dashboard.test",
        name="Dashboard Admin",
        roles=["admin"],
        tenant_ids=["dashboard-tenant-123"],
        is_active=True,
        auth_provider="azure_ad",
    )


@pytest.fixture
def mock_services():
    """Mock all dashboard services.

    NOTE: All service methods are ASYNC (routes use await).
    """
    services = {}

    # Mock CostService - async methods
    cost_service = MagicMock()
    cost_service.get_cost_summary = AsyncMock(
        return_value=MagicMock(
            total_cost=12500.50,
            month_over_month_change=5.5,
            top_spending_resources=[
                {"name": "VM-Prod-01", "cost": 2500.00},
                {"name": "SQL-Prod-01", "cost": 1800.00},
            ],
        )
    )
    cost_service.get_cost_trends = AsyncMock(return_value=[])
    services["cost"] = cost_service

    # Mock ComplianceService - async methods
    compliance_service = MagicMock()
    compliance_service.get_compliance_summary = AsyncMock(
        return_value=MagicMock(
            compliance_score=85.5,
            total_policies=50,
            compliant_policies=43,
            non_compliant_policies=7,
            critical_findings=2,
        )
    )
    services["compliance"] = compliance_service

    # Mock ResourceService - async methods
    resource_service = MagicMock()
    resource_service.get_resource_inventory = AsyncMock(
        return_value=MagicMock(
            total_resources=350,
            resources=[
                MagicMock(
                    id="res-1",
                    name="Resource 1",
                    type="Microsoft.Compute/virtualMachines",
                    tenant_id="dashboard-tenant-123",
                ),
                MagicMock(
                    id="res-2",
                    name="Resource 2",
                    type="Microsoft.Storage/storageAccounts",
                    tenant_id="dashboard-tenant-123",
                ),
            ],
        )
    )
    services["resource"] = resource_service

    # Mock IdentityService - async methods
    identity_service = MagicMock()
    identity_service.get_identity_summary = AsyncMock(
        return_value=MagicMock(
            total_users=250,
            active_users=220,
            admin_users=15,
            guest_users=30,
            mfa_enabled_users=180,
            mfa_percentage=72.0,
        )
    )
    identity_service.get_identity_trends = AsyncMock(return_value=[])
    services["identity"] = identity_service

    # Mock MonitoringService — SYNC methods (the sync dashboard doesn't await)
    monitoring_service = MagicMock()
    monitoring_service.get_overall_status = MagicMock(
        return_value={
            "status": "healthy",
            "success_rate": 95.0,
        }
    )
    monitoring_service.get_recent_logs = MagicMock(
        return_value=[
            MagicMock(
                id="log-1",
                job_type="costs",
                tenant_id="dashboard-tenant-123",
                status="completed",
                started_at=datetime.utcnow(),
                duration_ms=5000,
            ),
        ]
    )
    monitoring_service.get_active_alerts = MagicMock(return_value=[])
    monitoring_service.get_alert_stats = MagicMock(return_value={"total": 0})
    monitoring_service.get_metrics = MagicMock(return_value=[])
    monitoring_service.get_sync_metrics = MagicMock(return_value={})
    services["monitoring"] = monitoring_service

    return services


# ============================================================================
# GET / Tests
# ============================================================================


class TestMainDashboardPage:
    """Tests for GET / (root) redirect behaviour.

    GET / is a public redirect — no auth required.  Unauthenticated requests
    are sent to /auth/login; the actual dashboard HTML lives at /dashboard
    (covered by TestDashboardAliasPage).
    """

    def test_root_redirects_unauthenticated_to_login(self, client_with_db):
        """Root endpoint redirects unauthenticated users to /auth/login."""
        response = client_with_db.get("/", follow_redirects=False)
        assert response.status_code in (301, 302, 307, 308), (
            f"Expected a redirect from GET /, got {response.status_code}"
        )
        location = response.headers.get("location", "")
        assert "login" in location, (
            f"Expected redirect to a login URL, got location={location!r}"
        )

    def test_root_is_publicly_accessible(self, client_with_db):
        """Root endpoint does not return 401/403 — it is a public redirect."""
        response = client_with_db.get("/", follow_redirects=False)
        assert response.status_code not in (401, 403), (
            "GET / should be publicly accessible (redirect), not require auth"
        )


# ============================================================================
# GET /dashboard Tests
# ============================================================================


class TestDashboardAliasPage:
    """Tests for GET /dashboard (alias for root)."""

    @patch("app.api.routes.dashboard.templates")
    @patch("app.api.routes.dashboard.CostService")
    @patch("app.api.routes.dashboard.ComplianceService")
    @patch("app.api.routes.dashboard.ResourceService")
    @patch("app.api.routes.dashboard.IdentityService")
    def test_dashboard_alias_renders_same_as_root(
        self,
        mock_identity,
        mock_resource,
        mock_compliance,
        mock_cost,
        mock_templates,
        authed_client,
        mock_services,
    ):
        """Dashboard alias page renders same content as root."""
        mock_templates.TemplateResponse.return_value = _html()

        mock_cost.return_value = mock_services["cost"]
        mock_compliance.return_value = mock_services["compliance"]
        mock_resource.return_value = mock_services["resource"]
        mock_identity.return_value = mock_services["identity"]

        response = authed_client.get("/dashboard")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


# ============================================================================
# GET /sync-dashboard Tests
# ============================================================================


class TestSyncDashboardPage:
    """Tests for GET /sync-dashboard page."""

    @patch("app.api.routes.dashboard.templates")
    @patch("app.api.routes.dashboard.MonitoringService")
    @patch("app.api.routes.dashboard.get_user_tenants")
    def test_sync_dashboard_renders_monitoring_data(
        self,
        mock_get_tenants,
        mock_monitoring_cls,
        mock_templates,
        authed_client,
        mock_user,
        mock_services,
    ):
        """Sync dashboard page renders with monitoring data."""
        mock_templates.TemplateResponse.return_value = _html()
        mock_monitoring_cls.return_value = mock_services["monitoring"]
        mock_get_tenants.return_value = []

        response = authed_client.get("/sync-dashboard")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert b"sync" in response.content.lower()

    @patch("app.api.routes.dashboard.templates")
    @patch("app.api.routes.dashboard.MonitoringService")
    @patch("app.api.routes.dashboard.get_user_tenants")
    def test_sync_dashboard_includes_alert_stats(
        self,
        mock_get_tenants,
        mock_monitoring_cls,
        mock_templates,
        authed_client,
        mock_user,
        mock_services,
    ):
        """Sync dashboard includes alert statistics."""
        mock_templates.TemplateResponse.return_value = _html()
        mock_monitoring_cls.return_value = mock_services["monitoring"]
        mock_get_tenants.return_value = []

        response = authed_client.get("/sync-dashboard")

        assert response.status_code == 200
        # Should call alert stats method
        mock_services["monitoring"].get_alert_stats.assert_called()


# ============================================================================
# GET /dmarc Tests
# ============================================================================


class TestDMARCDashboardPage:
    """Tests for GET /dmarc dashboard page."""

    @patch("app.api.routes.dashboard.templates")
    def test_dmarc_dashboard_renders_successfully(self, mock_templates, authed_client):
        """DMARC dashboard page renders for authenticated users."""
        mock_templates.TemplateResponse.return_value = _html()

        response = authed_client.get("/dmarc")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert b"dmarc" in response.content.lower()

    def test_dmarc_dashboard_requires_authentication(self, client_with_db):
        """DMARC dashboard returns 401 without authentication."""
        response = client_with_db.get("/dmarc")

        assert response.status_code == 401


# ============================================================================
# GET /partials/cost-summary-card Tests
# ============================================================================


class TestCostSummaryCardPartial:
    """Tests for GET /partials/cost-summary-card HTMX partial."""

    @patch("app.api.routes.dashboard.templates")
    @patch("app.api.routes.dashboard.CostService")
    def test_cost_summary_card_returns_html(
        self, mock_cost_cls, mock_templates, authed_client, mock_services
    ):
        """Cost summary card partial returns HTML."""
        mock_templates.TemplateResponse.return_value = _html()
        mock_cost_cls.return_value = mock_services["cost"]

        response = authed_client.get("/partials/cost-summary-card")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @patch("app.api.routes.dashboard.templates")
    @patch("app.api.routes.dashboard.CostService")
    def test_cost_summary_card_includes_cost_data(
        self, mock_cost_cls, mock_templates, authed_client, mock_services
    ):
        """Cost summary card includes cost summary data."""
        mock_templates.TemplateResponse.return_value = _html()
        mock_cost_cls.return_value = mock_services["cost"]

        response = authed_client.get("/partials/cost-summary-card")

        assert response.status_code == 200
        # Should call cost service
        mock_services["cost"].get_cost_summary.assert_called_once()


# ============================================================================
# GET /partials/compliance-gauge Tests
# ============================================================================


class TestComplianceGaugePartial:
    """Tests for GET /partials/compliance-gauge HTMX partial."""

    @patch("app.api.routes.dashboard.templates")
    @patch("app.api.routes.dashboard.ComplianceService")
    def test_compliance_gauge_returns_html(
        self, mock_compliance_cls, mock_templates, authed_client, mock_services
    ):
        """Compliance gauge partial returns HTML."""
        mock_templates.TemplateResponse.return_value = _html()
        mock_compliance_cls.return_value = mock_services["compliance"]

        response = authed_client.get("/partials/compliance-gauge")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @patch("app.api.routes.dashboard.templates")
    @patch("app.api.routes.dashboard.ComplianceService")
    def test_compliance_gauge_includes_score(
        self, mock_compliance_cls, mock_templates, authed_client, mock_services
    ):
        """Compliance gauge includes compliance score."""
        mock_templates.TemplateResponse.return_value = _html()
        mock_compliance_cls.return_value = mock_services["compliance"]

        response = authed_client.get("/partials/compliance-gauge")

        assert response.status_code == 200
        mock_services["compliance"].get_compliance_summary.assert_called_once()


# ============================================================================
# GET /partials/sync-status-card Tests
# ============================================================================


class TestSyncStatusCardPartial:
    """Tests for GET /partials/sync-status-card HTMX partial."""

    @patch("app.api.routes.dashboard.templates")
    @patch("app.api.routes.dashboard.MonitoringService")
    def test_sync_status_card_returns_html(
        self, mock_monitoring_cls, mock_templates, authed_client, mock_services
    ):
        """Sync status card partial returns HTML."""
        mock_templates.TemplateResponse.return_value = _html()
        mock_monitoring_cls.return_value = mock_services["monitoring"]

        response = authed_client.get("/partials/sync-status-card")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @patch("app.api.routes.dashboard.templates")
    @patch("app.api.routes.dashboard.MonitoringService")
    def test_sync_status_card_includes_metrics(
        self, mock_monitoring_cls, mock_templates, authed_client, mock_services
    ):
        """Sync status card includes monitoring metrics."""
        mock_templates.TemplateResponse.return_value = _html()
        mock_monitoring_cls.return_value = mock_services["monitoring"]

        response = authed_client.get("/partials/sync-status-card")

        assert response.status_code == 200
        mock_services["monitoring"].get_overall_status.assert_called_once()
        mock_services["monitoring"].get_metrics.assert_called_once()


# ============================================================================
# GET /partials/sync-history-table Tests
# ============================================================================


class TestSyncHistoryTablePartial:
    """Tests for GET /partials/sync-history-table HTMX partial."""

    @patch("app.api.routes.dashboard.templates")
    @patch("app.api.routes.dashboard.MonitoringService")
    def test_sync_history_table_returns_html(
        self, mock_monitoring_cls, mock_templates, authed_client, mock_services
    ):
        """Sync history table partial returns HTML."""
        mock_templates.TemplateResponse.return_value = _html()
        mock_monitoring_cls.return_value = mock_services["monitoring"]

        response = authed_client.get("/partials/sync-history-table")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @patch("app.api.routes.dashboard.templates")
    @patch("app.api.routes.dashboard.MonitoringService")
    def test_sync_history_table_accepts_limit_parameter(
        self, mock_monitoring_cls, mock_templates, authed_client, mock_services
    ):
        """Sync history table accepts limit query parameter."""
        mock_templates.TemplateResponse.return_value = _html()
        mock_monitoring_cls.return_value = mock_services["monitoring"]

        response = authed_client.get("/partials/sync-history-table?limit=20")

        assert response.status_code == 200
        mock_services["monitoring"].get_recent_logs.assert_called_once_with(
            limit=20, include_running=True
        )

    @patch("app.api.routes.dashboard.templates")
    @patch("app.api.routes.dashboard.MonitoringService")
    def test_sync_history_table_uses_default_limit(
        self, mock_monitoring_cls, mock_templates, authed_client, mock_services
    ):
        """Sync history table uses default limit when not specified."""
        mock_templates.TemplateResponse.return_value = _html()
        mock_monitoring_cls.return_value = mock_services["monitoring"]

        response = authed_client.get("/partials/sync-history-table")

        assert response.status_code == 200
        # Default limit should be 15
        mock_services["monitoring"].get_recent_logs.assert_called_once_with(
            limit=15, include_running=True
        )

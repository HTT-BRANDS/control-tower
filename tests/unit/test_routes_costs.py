"""Unit tests for cost management API routes.

Tests all cost endpoints with FastAPI TestClient:
- GET /api/v1/costs/summary
- GET /api/v1/costs/by-tenant
- GET /api/v1/costs/trends
- GET /api/v1/costs/anomalies
- POST /api/v1/costs/anomalies/{anomaly_id}/acknowledge
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.cost import CostByTenant, CostSummary, CostTrend

# ============================================================================
# GET /api/v1/costs/summary Tests
# ============================================================================


class TestCostSummaryEndpoint:
    """Tests for GET /api/v1/costs/summary endpoint."""

    @patch("app.api.routes.costs.CostService")
    def test_get_summary_success(self, mock_service_cls, authed_client):
        """Cost summary endpoint returns aggregated data."""
        mock_svc = MagicMock()
        mock_svc.get_cost_summary = AsyncMock(
            return_value=CostSummary(
                total_cost=1500.50,
                currency="USD",
                period_start=date(2024, 1, 1),
                period_end=date(2024, 1, 31),
                tenant_count=1,
                subscription_count=2,
                cost_change_percent=5.2,
            )
        )
        mock_service_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/costs/summary?period_days=30")

        assert response.status_code == 200
        data = response.json()
        assert data["total_cost"] == 1500.50
        assert data["tenant_count"] == 1

    def test_get_summary_requires_auth(self, client):
        """Cost summary endpoint returns 401 without authentication."""
        response = client.get("/api/v1/costs/summary")
        assert response.status_code == 401

    def test_get_summary_validates_period_days(self, authed_client):
        """Cost summary validates period_days parameter."""
        response = authed_client.get("/api/v1/costs/summary?period_days=500")
        assert response.status_code == 422


# ============================================================================
# GET /api/v1/costs/by-tenant Tests
# ============================================================================


class TestCostsByTenantEndpoint:
    """Tests for GET /api/v1/costs/by-tenant endpoint."""

    @patch("app.api.routes.costs.CostService")
    def test_get_costs_by_tenant_success(self, mock_service_cls, authed_client):
        """Costs by tenant endpoint returns tenant breakdown."""
        mock_svc = MagicMock()
        mock_svc.get_costs_by_tenant = AsyncMock(
            return_value=[
                CostByTenant(
                    tenant_id="test-tenant-123",
                    tenant_name="Test Tenant",
                    total_cost=1000.0,
                ),
            ]
        )
        mock_service_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/costs/by-tenant")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["tenant_id"] == "test-tenant-123"

    def test_get_costs_by_tenant_requires_auth(self, client):
        """Costs by tenant endpoint returns 401 without authentication."""
        response = client.get("/api/v1/costs/by-tenant")
        assert response.status_code == 401


# ============================================================================
# GET /api/v1/costs/trends Tests
# ============================================================================


class TestCostTrendsEndpoint:
    """Tests for GET /api/v1/costs/trends endpoint."""

    @patch("app.api.routes.costs.CostService")
    def test_get_cost_trends_success(self, mock_service_cls, authed_client):
        """Cost trends endpoint returns time series data."""
        mock_svc = MagicMock()
        mock_svc.get_cost_trends = AsyncMock(
            return_value=[
                CostTrend(date=date(2024, 1, 1), cost=100.0),
                CostTrend(date=date(2024, 1, 2), cost=110.0),
            ]
        )
        mock_service_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/costs/trends?days=30")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

    def test_get_cost_trends_requires_auth(self, client):
        """Cost trends endpoint returns 401 without authentication."""
        response = client.get("/api/v1/costs/trends")
        assert response.status_code == 401


# ============================================================================
# GET /api/v1/costs/anomalies Tests
# ============================================================================


class TestCostAnomaliesEndpoint:
    """Tests for GET /api/v1/costs/anomalies endpoint."""

    @patch("app.api.routes.costs.CostService")
    def test_get_anomalies_success(self, mock_service_cls, authed_client):
        """Cost anomalies endpoint returns anomaly list."""
        mock_svc = MagicMock()
        mock_anomaly = MagicMock()
        mock_anomaly.tenant_id = "test-tenant-123"
        mock_anomaly.id = 1
        mock_svc.get_anomalies.return_value = [mock_anomaly]  # sync in route
        mock_service_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/costs/anomalies")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_anomalies_requires_auth(self, client):
        """Cost anomalies endpoint returns 401 without authentication."""
        response = client.get("/api/v1/costs/anomalies")
        assert response.status_code == 401

    @patch("app.api.routes.costs.CostService")
    def test_get_anomalies_with_filters(self, mock_service_cls, authed_client):
        """Cost anomalies endpoint supports filtering."""
        mock_svc = MagicMock()
        mock_svc.get_anomalies.return_value = []  # sync in route
        mock_service_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/costs/anomalies?acknowledged=false&limit=10")

        assert response.status_code == 200
        mock_svc.get_anomalies.assert_called_once()


# ============================================================================
# POST /api/v1/costs/anomalies/{anomaly_id}/acknowledge Tests
# ============================================================================


class TestAcknowledgeAnomalyEndpoint:
    """Tests for POST /api/v1/costs/anomalies/{anomaly_id}/acknowledge."""

    @patch("app.api.routes.costs.CostService")
    def test_acknowledge_anomaly_success(self, mock_service_cls, authed_client, db_session):
        """Acknowledge anomaly endpoint succeeds."""
        from app.models.cost import CostAnomaly

        # Route queries DB for the anomaly before calling service
        anomaly = CostAnomaly(
            tenant_id="test-tenant-123",
            subscription_id="sub-123",
            anomaly_type="spike",
            description="Unusual cost increase",
            expected_cost=100.0,
            actual_cost=250.0,
            percentage_change=150.0,
        )
        db_session.add(anomaly)
        db_session.commit()

        mock_svc = MagicMock()
        mock_svc.acknowledge_anomaly = AsyncMock(return_value=True)
        mock_service_cls.return_value = mock_svc

        url = f"/api/v1/costs/anomalies/{anomaly.id}/acknowledge"
        response = authed_client.post(url)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_acknowledge_anomaly_requires_auth(self, client):
        """Acknowledge anomaly endpoint returns 401 without authentication."""
        response = client.post("/api/v1/costs/anomalies/1/acknowledge")
        assert response.status_code == 401

    def test_acknowledge_anomaly_not_found(self, authed_client):
        """Acknowledge unknown anomaly returns 404."""
        response = authed_client.post("/api/v1/costs/anomalies/99999/acknowledge")
        assert response.status_code == 404

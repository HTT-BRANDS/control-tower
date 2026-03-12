"""Unit tests for compliance monitoring API routes.

Tests all compliance endpoints with FastAPI TestClient:
- GET /api/v1/compliance/summary
- GET /api/v1/compliance/scores
- GET /api/v1/compliance/non-compliant
- GET /api/v1/compliance/trends
- GET /api/v1/compliance/status
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.compliance import ComplianceScore, ComplianceSummary, PolicyStatus

# ============================================================================
# GET /api/v1/compliance/summary Tests
# ============================================================================


class TestComplianceSummaryEndpoint:
    """Tests for GET /api/v1/compliance/summary endpoint."""

    @patch("app.api.routes.compliance.ComplianceService")
    def test_get_summary_success(self, mock_service_cls, authed_client):
        """Compliance summary endpoint returns aggregated data."""
        mock_svc = MagicMock()
        mock_svc.get_compliance_summary = AsyncMock(
            return_value=ComplianceSummary(
                average_compliance_percent=85.5,
                total_compliant_resources=850,
                total_non_compliant_resources=150,
                total_exempt_resources=10,
            )
        )
        mock_service_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/compliance/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["average_compliance_percent"] == 85.5
        assert data["total_compliant_resources"] == 850

    def test_get_summary_requires_auth(self, client):
        """Compliance summary endpoint returns 401 without authentication."""
        response = client.get("/api/v1/compliance/summary")
        assert response.status_code == 401


# ============================================================================
# GET /api/v1/compliance/scores Tests
# ============================================================================


class TestComplianceScoresEndpoint:
    """Tests for GET /api/v1/compliance/scores endpoint."""

    @patch("app.api.routes.compliance.ComplianceService")
    def test_get_scores_success(self, mock_service_cls, authed_client):
        """Compliance scores endpoint returns score data."""
        mock_svc = MagicMock()
        mock_svc.get_scores_by_tenant = AsyncMock(
            return_value=[
                ComplianceScore(
                    tenant_id="test-tenant-123",
                    tenant_name="Test Tenant",
                    overall_compliance_percent=85.5,
                    compliant_resources=85,
                    non_compliant_resources=15,
                    exempt_resources=0,
                    last_updated=datetime.now(UTC),
                ),
            ]
        )
        mock_service_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/compliance/scores")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1

    def test_get_scores_requires_auth(self, client):
        """Compliance scores endpoint returns 401 without authentication."""
        response = client.get("/api/v1/compliance/scores")
        assert response.status_code == 401

    @patch("app.api.routes.compliance.ComplianceService")
    def test_get_scores_with_pagination(self, mock_service_cls, authed_client):
        """Compliance scores endpoint supports pagination."""
        mock_svc = MagicMock()
        mock_svc.get_scores_by_tenant = AsyncMock(return_value=[])
        mock_service_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/compliance/scores?limit=50&offset=10")
        assert response.status_code == 200


# ============================================================================
# GET /api/v1/compliance/non-compliant Tests
# ============================================================================


class TestNonCompliantEndpoint:
    """Tests for GET /api/v1/compliance/non-compliant endpoint."""

    @patch("app.api.routes.compliance.ComplianceService")
    def test_get_non_compliant_success(self, mock_service_cls, authed_client):
        """Non-compliant endpoint returns policy violations."""
        mock_svc = MagicMock()
        mock_svc.get_non_compliant_policies.return_value = [  # sync in route
            PolicyStatus(
                policy_definition_id="policy-123",
                policy_name="Test Policy",
                policy_category="Security",
                compliance_state="NonCompliant",
                non_compliant_count=5,
                tenant_id="test-tenant-123",
                subscription_id="sub-123",
                severity="High",
            ),
        ]
        mock_service_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/compliance/non-compliant")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["severity"] == "High"

    def test_get_non_compliant_requires_auth(self, client):
        """Non-compliant endpoint returns 401 without authentication."""
        response = client.get("/api/v1/compliance/non-compliant")
        assert response.status_code == 401

    @patch("app.api.routes.compliance.ComplianceService")
    def test_get_non_compliant_filters_by_severity(
        self, mock_service_cls, authed_client
    ):
        """Non-compliant endpoint filters by severity."""
        mock_svc = MagicMock()
        mock_svc.get_non_compliant_policies.return_value = []  # sync in route
        mock_service_cls.return_value = mock_svc

        response = authed_client.get(
            "/api/v1/compliance/non-compliant?severity=High"
        )
        assert response.status_code == 200


# ============================================================================
# GET /api/v1/compliance/trends Tests
# ============================================================================


class TestComplianceTrendsEndpoint:
    """Tests for GET /api/v1/compliance/trends endpoint."""

    @patch("app.api.routes.compliance.ComplianceService")
    def test_get_trends_success(self, mock_service_cls, authed_client):
        """Compliance trends endpoint returns time series data."""
        mock_svc = MagicMock()
        mock_svc.get_compliance_trends = AsyncMock(
            return_value=[
                {"date": "2024-01-01", "score": 85.0},
                {"date": "2024-01-02", "score": 87.0},
            ]
        )
        mock_service_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/compliance/trends?days=30")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

    def test_get_trends_requires_auth(self, client):
        """Compliance trends endpoint returns 401 without authentication."""
        response = client.get("/api/v1/compliance/trends")
        assert response.status_code == 401


# ============================================================================
# GET /api/v1/compliance/status Tests
# ============================================================================


class TestComplianceStatusEndpoint:
    """Tests for GET /api/v1/compliance/status endpoint."""

    def test_get_status_success(self, authed_client):
        """Compliance status endpoint returns status metrics."""
        response = authed_client.get("/api/v1/compliance/status")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_get_status_requires_auth(self, client):
        """Compliance status endpoint returns 401 without authentication."""
        response = client.get("/api/v1/compliance/status")
        assert response.status_code == 401

    def test_get_status_with_no_data(self, authed_client):
        """Compliance status endpoint handles empty database."""
        response = authed_client.get("/api/v1/compliance/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "initializing", "warning"]

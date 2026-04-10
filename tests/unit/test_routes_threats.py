"""Unit tests for threat intelligence API routes.

Tests all threat endpoints with FastAPI TestClient:
- GET /api/v1/threats/cybeta
- GET /api/v1/threats/summary/{tenant_id}
"""

from unittest.mock import MagicMock, patch

# ============================================================================
# GET /api/v1/threats/cybeta Tests
# ============================================================================


SAMPLE_THREATS = [
    {
        "tenant_id": "test-tenant-123",
        "threat_score": 72.5,
        "vulnerability_count": 15,
        "malicious_domain_alerts": 3,
        "peer_comparison_percentile": 65.0,
        "snapshot_date": "2024-06-15T00:00:00",
    },
    {
        "tenant_id": "test-tenant-123",
        "threat_score": 68.0,
        "vulnerability_count": 12,
        "malicious_domain_alerts": 1,
        "peer_comparison_percentile": 70.0,
        "snapshot_date": "2024-06-14T00:00:00",
    },
]


class TestGetCybetaThreats:
    """Tests for GET /api/v1/threats/cybeta endpoint."""

    @patch("app.api.routes.threats.get_threat_intel_service")
    def test_get_cybeta_threats_returns_list(self, mock_get_service, authed_client):
        """Cybeta threats endpoint returns a list of threat records."""
        mock_service = MagicMock()
        mock_service.get_cybeta_threats.return_value = SAMPLE_THREATS
        mock_get_service.return_value = mock_service

        response = authed_client.get("/api/v1/threats/cybeta")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

    @patch("app.api.routes.threats.get_threat_intel_service")
    def test_get_cybeta_threats_response_shape(self, mock_get_service, authed_client):
        """Each threat record contains expected fields."""
        mock_service = MagicMock()
        mock_service.get_cybeta_threats.return_value = SAMPLE_THREATS[:1]
        mock_get_service.return_value = mock_service

        response = authed_client.get("/api/v1/threats/cybeta")

        assert response.status_code == 200
        record = response.json()[0]
        expected_keys = {
            "tenant_id",
            "threat_score",
            "vulnerability_count",
            "malicious_domain_alerts",
            "peer_comparison_percentile",
            "snapshot_date",
        }
        assert expected_keys.issubset(record.keys())
        assert record["threat_score"] == 72.5
        assert record["vulnerability_count"] == 15

    @patch("app.api.routes.threats.get_threat_intel_service")
    def test_get_cybeta_threats_filters_by_tenant_ids(
        self, mock_get_service, authed_client, mock_authz
    ):
        """Cybeta threats endpoint passes filtered tenant_ids to service."""
        mock_service = MagicMock()
        mock_service.get_cybeta_threats.return_value = SAMPLE_THREATS[:1]
        mock_get_service.return_value = mock_service
        mock_authz.filter_tenant_ids.return_value = ["test-tenant-123"]

        response = authed_client.get("/api/v1/threats/cybeta?tenant_ids=test-tenant-123")

        assert response.status_code == 200
        # Verify the service was called with the filtered tenant IDs
        call_kwargs = mock_service.get_cybeta_threats.call_args
        assert call_kwargs.kwargs["tenant_ids"] == ["test-tenant-123"]

    @patch("app.api.routes.threats.get_threat_intel_service")
    def test_get_cybeta_threats_filters_by_date_range(self, mock_get_service, authed_client):
        """Cybeta threats endpoint passes date range filters to service."""
        mock_service = MagicMock()
        mock_service.get_cybeta_threats.return_value = SAMPLE_THREATS
        mock_get_service.return_value = mock_service

        response = authed_client.get(
            "/api/v1/threats/cybeta?start_date=2024-06-01&end_date=2024-06-30"
        )

        assert response.status_code == 200
        call_kwargs = mock_service.get_cybeta_threats.call_args.kwargs
        # FastAPI parses date query params into date objects
        assert str(call_kwargs["start_date"]) == "2024-06-01"
        assert str(call_kwargs["end_date"]) == "2024-06-30"

    @patch("app.api.routes.threats.get_threat_intel_service")
    def test_get_cybeta_threats_empty_results(self, mock_get_service, authed_client):
        """Cybeta threats endpoint returns empty list when no data exists."""
        mock_service = MagicMock()
        mock_service.get_cybeta_threats.return_value = []
        mock_get_service.return_value = mock_service

        response = authed_client.get("/api/v1/threats/cybeta")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_get_cybeta_threats_requires_auth(self, client):
        """Cybeta threats endpoint returns 401 without authentication."""
        response = client.get("/api/v1/threats/cybeta")

        assert response.status_code == 401


# ============================================================================
# GET /api/v1/threats/summary/{tenant_id} Tests
# ============================================================================


SAMPLE_SUMMARY = {
    "tenant_id": "test-tenant-123",
    "status": "available",
    "latest_threat_score": 72.5,
    "latest_vulnerability_count": 15,
    "latest_malicious_domain_alerts": 3,
    "peer_comparison_percentile": 65.0,
    "latest_snapshot_date": "2024-06-15T00:00:00",
    "message": "Threat data retrieved successfully",
}

EMPTY_SUMMARY = {
    "tenant_id": "test-tenant-123",
    "status": "no_data",
    "message": "No threat data available for this tenant",
    "latest_threat_score": None,
    "latest_vulnerability_count": 0,
    "latest_snapshot_date": None,
}


class TestGetThreatSummary:
    """Tests for GET /api/v1/threats/summary/{tenant_id} endpoint."""

    @patch("app.api.routes.threats.get_threat_intel_service")
    def test_get_threat_summary_returns_data(self, mock_get_service, authed_client):
        """Threat summary endpoint returns summary for a tenant."""
        mock_service = MagicMock()
        mock_service.get_threat_summary.return_value = SAMPLE_SUMMARY
        mock_get_service.return_value = mock_service

        response = authed_client.get("/api/v1/threats/summary/test-tenant-123")

        assert response.status_code == 200
        data = response.json()
        assert data["tenant_id"] == "test-tenant-123"
        assert data["status"] == "available"
        assert data["latest_threat_score"] == 72.5

    @patch("app.api.routes.threats.get_threat_intel_service")
    def test_get_threat_summary_no_data(self, mock_get_service, authed_client):
        """Threat summary returns no_data status when tenant has no threats."""
        mock_service = MagicMock()
        mock_service.get_threat_summary.return_value = EMPTY_SUMMARY
        mock_get_service.return_value = mock_service

        response = authed_client.get("/api/v1/threats/summary/test-tenant-123")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "no_data"
        assert data["latest_threat_score"] is None
        assert data["latest_vulnerability_count"] == 0

    def test_get_threat_summary_requires_auth(self, client):
        """Threat summary endpoint returns 401 without authentication."""
        response = client.get("/api/v1/threats/summary/test-tenant-123")

        assert response.status_code == 401

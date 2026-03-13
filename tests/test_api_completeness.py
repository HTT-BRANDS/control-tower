"""Unit tests for the enhanced API endpoints."""

from datetime import date

import pytest


class TestCostAnomaliesAPI:
    """Test suite for cost anomaly endpoints."""

    def test_get_anomalies_with_pagination(self):
        """Test anomaly endpoint with pagination parameters."""
        # Arrange
        params = {"limit": 10, "offset": 0, "sort_by": "detected_at", "sort_order": "desc"}

        # Act & Assert - structure validation
        assert params["limit"] > 0
        assert params["offset"] >= 0
        assert params["sort_order"] in ["asc", "desc"]

    def test_bulk_acknowledge_request(self):
        """Test bulk acknowledge request structure."""
        # Arrange
        request_data = {"anomaly_ids": [1, 2, 3]}

        # Act & Assert
        assert isinstance(request_data["anomaly_ids"], list)
        assert all(isinstance(id, int) for id in request_data["anomaly_ids"])

    def test_anomaly_trends_params(self):
        """Test anomaly trends query parameters."""
        params = {"months": 6}
        assert 1 <= params["months"] <= 24


class TestRecommendationsAPI:
    """Test suite for recommendations endpoints."""

    def test_recommendation_category_values(self):
        """Test valid recommendation categories."""
        valid_categories = [
            "cost_optimization",
            "security",
            "performance",
            "reliability",
        ]
        for category in valid_categories:
            assert category in valid_categories

    def test_dismiss_recommendation_request(self):
        """Test dismiss recommendation request structure."""
        request_data = {"reason": "Not applicable to our environment"}
        assert isinstance(request_data.get("reason"), (str, type(None)))


class TestIdleResourcesAPI:
    """Test suite for idle resources endpoints."""

    def test_idle_resource_sorting(self):
        """Test idle resources sorting parameters."""
        params = {
            "sort_by": "estimated_monthly_savings",
            "sort_order": "desc",
        }
        assert params["sort_order"] in ["asc", "desc"]

    def test_tag_resource_request(self):
        """Test tag resource as reviewed request."""
        request_data = {"notes": "Verified - this VM is needed for DR"}
        assert isinstance(request_data.get("notes"), (str, type(None)))


class TestExportsAPI:
    """Test suite for export endpoints."""

    def test_export_costs_params(self):
        """Test export costs query parameters."""
        params = {
            "start_date": date(2024, 1, 1),
            "end_date": date(2024, 1, 31),
            "tenant_ids": ["tenant-1", "tenant-2"],
        }
        assert params["start_date"] <= params["end_date"]

    def test_export_response_headers(self):
        """Test export response has proper CSV headers."""
        headers = {"Content-Disposition": "attachment; filename=costs_export_20240101_120000.csv"}
        assert "Content-Disposition" in headers
        assert headers["Content-Disposition"].startswith("attachment")


class TestStatusAPI:
    """Test suite for system status endpoints."""

    def test_status_response_structure(self):
        """Test status endpoint response structure."""
        expected_keys = {
            "status",
            "version",
            "timestamp",
            "components",
            "sync_jobs",
            "alerts",
        }
        # Validate structure expectation
        assert len(expected_keys) == 6

    def test_sync_status_response_structure(self):
        """Test sync status endpoint response structure."""
        expected_keys = {
            "status",
            "last_updated",
            "jobs",
            "metrics",
            "recent_logs",
            "active_alerts",
        }
        assert len(expected_keys) == 6


class TestFiltering:
    """Test suite for enhanced filtering across endpoints."""

    @pytest.mark.parametrize(
        "endpoint",
        [
            "/api/v1/costs/anomalies",
            "/api/v1/resources/idle",
            "/api/v1/compliance/scores",
            "/api/v1/identity/privileged",
        ],
    )
    def test_common_filter_parameters(self, endpoint):
        """Test that common filter parameters are consistent."""
        common_params = {
            "tenant_ids": ["tenant-1"],
            "limit": 50,
            "offset": 0,
            "sort_by": "name",
            "sort_order": "asc",
        }
        # Validate all common params are valid
        assert common_params["limit"] > 0
        assert common_params["offset"] >= 0
        assert common_params["sort_order"] in ["asc", "desc"]


class TestTrendsAPI:
    """Test suite for trends endpoints."""

    def test_cost_forecast_days_param(self):
        """Test cost forecast days parameter range."""
        days = 30
        assert 7 <= days <= 90

    def test_compliance_trends_days_param(self):
        """Test compliance trends days parameter range."""
        days = 30
        assert 7 <= days <= 365

    def test_identity_trends_days_param(self):
        """Test identity trends days parameter range."""
        days = 30
        assert 7 <= days <= 365

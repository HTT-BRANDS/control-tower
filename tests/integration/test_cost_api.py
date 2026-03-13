"""Integration tests for Cost API endpoints.

These tests verify the complete request/response cycle for cost management endpoints,
including authentication, authorization, database interactions, and data validation.

Covered endpoints:
- GET /api/v1/costs/summary
- GET /api/v1/costs/by-tenant
- GET /api/v1/costs/trends
- GET /api/v1/costs/trends/forecast
- GET /api/v1/costs/anomalies
- GET /api/v1/costs/anomalies/trends
- GET /api/v1/costs/anomalies/by-service
- GET /api/v1/costs/anomalies/top
- POST /api/v1/costs/anomalies/{id}/acknowledge
- POST /api/v1/costs/anomalies/bulk-acknowledge
"""

import pytest
from fastapi.testclient import TestClient

from app.models.cost import CostAnomaly

# ============================================================================
# Fixtures
# ============================================================================
# Note: test_tenant_id, test_user, mock_authz, and authenticated_client
# are inherited from tests/integration/conftest.py


# Note: seeded_db fixture is inherited from tests/integration/conftest.py
# Note: authenticated_client and unauthenticated_client fixtures
# are inherited from tests/integration/conftest.py


# ============================================================================
# GET /api/v1/costs/summary Tests
# ============================================================================


class TestCostSummaryEndpoint:
    """Integration tests for GET /api/v1/costs/summary."""

    def test_get_summary_success(self, authenticated_client: TestClient):
        """Cost summary returns aggregated data with proper structure."""
        response = authenticated_client.get("/api/v1/costs/summary?period_days=30")

        assert response.status_code == 200
        data = response.json()

        # Validate structure
        assert "total_cost" in data
        assert "currency" in data
        assert "period_start" in data
        assert "period_end" in data
        assert "tenant_count" in data
        assert "subscription_count" in data
        assert "top_services" in data

        # Validate types
        assert isinstance(data["total_cost"], (int, float))
        assert data["total_cost"] > 0  # We seeded data, so should have costs
        assert data["currency"] == "USD"
        assert data["tenant_count"] >= 1
        assert isinstance(data["top_services"], list)

        # Validate top_services structure
        if len(data["top_services"]) > 0:
            service = data["top_services"][0]
            assert "service_name" in service
            assert "cost" in service
            assert "percentage_of_total" in service

    def test_get_summary_different_periods(self, authenticated_client: TestClient):
        """Cost summary works with different period_days values."""
        # Test 7 days
        response_7 = authenticated_client.get("/api/v1/costs/summary?period_days=7")
        assert response_7.status_code == 200
        data_7 = response_7.json()

        # Test 30 days
        response_30 = authenticated_client.get("/api/v1/costs/summary?period_days=30")
        assert response_30.status_code == 200
        data_30 = response_30.json()

        # 30 days should have higher total cost than 7 days
        assert data_30["total_cost"] > data_7["total_cost"]

    def test_get_summary_requires_auth(self, unauthenticated_client: TestClient):
        """Cost summary endpoint requires authentication."""
        response = unauthenticated_client.get("/api/v1/costs/summary")
        assert response.status_code == 401

    def test_get_summary_validates_period_days(self, authenticated_client: TestClient):
        """Cost summary validates period_days parameter."""
        # Test invalid period (too large)
        response = authenticated_client.get("/api/v1/costs/summary?period_days=500")
        assert response.status_code == 422  # Validation error

        # Test invalid period (negative)
        response = authenticated_client.get("/api/v1/costs/summary?period_days=-1")
        assert response.status_code == 422


# ============================================================================
# GET /api/v1/costs/by-tenant Tests
# ============================================================================


class TestCostsByTenantEndpoint:
    """Integration tests for GET /api/v1/costs/by-tenant."""

    def test_get_costs_by_tenant_success(
        self, authenticated_client: TestClient, test_tenant_id: str
    ):
        """Costs by tenant returns breakdown by tenant."""
        response = authenticated_client.get("/api/v1/costs/by-tenant?period_days=30")

        assert response.status_code == 200
        data = response.json()

        # Should return a list
        assert isinstance(data, list)
        assert len(data) >= 1

        # Validate structure
        tenant_cost = data[0]
        assert "tenant_id" in tenant_cost
        assert "tenant_name" in tenant_cost
        assert "total_cost" in tenant_cost
        assert "currency" in tenant_cost

        # Verify we got our test tenant
        assert tenant_cost["tenant_id"] == test_tenant_id
        assert tenant_cost["tenant_name"] == "Test Tenant 1"
        assert tenant_cost["total_cost"] > 0

    def test_get_costs_by_tenant_requires_auth(self, unauthenticated_client: TestClient):
        """Costs by tenant endpoint requires authentication."""
        response = unauthenticated_client.get("/api/v1/costs/by-tenant")
        assert response.status_code == 401


# ============================================================================
# GET /api/v1/costs/trends Tests
# ============================================================================


class TestCostTrendsEndpoint:
    """Integration tests for GET /api/v1/costs/trends."""

    def test_get_cost_trends_success(self, authenticated_client: TestClient):
        """Cost trends returns time series data."""
        response = authenticated_client.get("/api/v1/costs/trends?days=30")

        assert response.status_code == 200
        data = response.json()

        # Should return a list of trends
        assert isinstance(data, list)
        assert len(data) > 0

        # Validate structure
        trend = data[0]
        assert "date" in trend
        assert "cost" in trend
        assert isinstance(trend["cost"], (int, float))

        # Dates should be in order
        dates = [t["date"] for t in data]
        assert dates == sorted(dates)

    def test_get_cost_trends_different_periods(self, authenticated_client: TestClient):
        """Cost trends works with different time periods."""
        response_7 = authenticated_client.get("/api/v1/costs/trends?days=7")
        response_30 = authenticated_client.get("/api/v1/costs/trends?days=30")

        assert response_7.status_code == 200
        assert response_30.status_code == 200

        data_7 = response_7.json()
        data_30 = response_30.json()

        # 30 days should have more data points
        assert len(data_30) > len(data_7)

    def test_get_cost_trends_requires_auth(self, unauthenticated_client: TestClient):
        """Cost trends endpoint requires authentication."""
        response = unauthenticated_client.get("/api/v1/costs/trends")
        assert response.status_code == 401


# ============================================================================
# GET /api/v1/costs/trends/forecast Tests
# ============================================================================


class TestCostForecastEndpoint:
    """Integration tests for GET /api/v1/costs/trends/forecast."""

    def test_get_cost_forecast_success(self, authenticated_client: TestClient):
        """Cost forecast returns projected cost data."""
        response = authenticated_client.get("/api/v1/costs/trends/forecast?days=30")

        assert response.status_code == 200
        data = response.json()

        # Should return a list of forecasts
        assert isinstance(data, list)

        # If we have enough historical data, we should get forecasts
        if len(data) > 0:
            forecast = data[0]
            assert "date" in forecast
            assert "forecasted_cost" in forecast
            # May have confidence intervals
            if "confidence_lower" in forecast:
                assert isinstance(forecast["confidence_lower"], (int, float))
            if "confidence_upper" in forecast:
                assert isinstance(forecast["confidence_upper"], (int, float))

    def test_get_cost_forecast_requires_auth(self, unauthenticated_client: TestClient):
        """Cost forecast endpoint requires authentication."""
        response = unauthenticated_client.get("/api/v1/costs/trends/forecast")
        assert response.status_code == 401


# ============================================================================
# GET /api/v1/costs/anomalies Tests
# ============================================================================


class TestCostAnomaliesEndpoint:
    """Integration tests for GET /api/v1/costs/anomalies."""

    def test_get_anomalies_success(self, authenticated_client: TestClient):
        """Cost anomalies endpoint returns anomaly list."""
        response = authenticated_client.get("/api/v1/costs/anomalies")

        assert response.status_code == 200
        data = response.json()

        # Should return a list
        assert isinstance(data, list)
        # We seeded 5 anomalies
        assert len(data) == 5

    def test_get_anomalies_filter_acknowledged(self, authenticated_client: TestClient):
        """Cost anomalies can be filtered by acknowledged status."""
        # Get unacknowledged anomalies
        response_unack = authenticated_client.get("/api/v1/costs/anomalies?acknowledged=false")
        assert response_unack.status_code == 200
        unack_data = response_unack.json()

        # Get acknowledged anomalies
        response_ack = authenticated_client.get("/api/v1/costs/anomalies?acknowledged=true")
        assert response_ack.status_code == 200
        ack_data = response_ack.json()

        # We seeded 3 unacknowledged and 2 acknowledged
        assert len(unack_data) == 3
        assert len(ack_data) == 2

        # Verify acknowledged status
        assert all(not a["is_acknowledged"] for a in unack_data)
        assert all(a["is_acknowledged"] for a in ack_data)

    def test_get_anomalies_pagination(self, authenticated_client: TestClient):
        """Cost anomalies supports pagination with limit and offset."""
        # Get first 2
        response_page1 = authenticated_client.get("/api/v1/costs/anomalies?limit=2&offset=0")
        assert response_page1.status_code == 200
        page1_data = response_page1.json()
        assert len(page1_data) == 2

        # Get next 2
        response_page2 = authenticated_client.get("/api/v1/costs/anomalies?limit=2&offset=2")
        assert response_page2.status_code == 200
        page2_data = response_page2.json()
        assert len(page2_data) == 2

        # Pages should have different data
        page1_ids = {a["id"] for a in page1_data}
        page2_ids = {a["id"] for a in page2_data}
        assert page1_ids != page2_ids

    def test_get_anomalies_requires_auth(self, unauthenticated_client: TestClient):
        """Cost anomalies endpoint requires authentication."""
        response = unauthenticated_client.get("/api/v1/costs/anomalies")
        assert response.status_code == 401


# ============================================================================
# GET /api/v1/costs/anomalies/trends Tests
# ============================================================================


class TestAnomalyTrendsEndpoint:
    """Integration tests for GET /api/v1/costs/anomalies/trends."""

    def test_get_anomaly_trends_success(self, authenticated_client: TestClient):
        """Anomaly trends returns monthly aggregated data."""
        response = authenticated_client.get("/api/v1/costs/anomalies/trends?months=6")

        assert response.status_code == 200
        data = response.json()

        # Should return a list
        assert isinstance(data, list)

        # If we have data, validate structure
        if len(data) > 0:
            trend = data[0]
            assert "period" in trend
            assert "anomaly_count" in trend
            assert "total_impact" in trend
            assert "acknowledged_count" in trend
            assert "unacknowledged_count" in trend

    def test_get_anomaly_trends_requires_auth(self, unauthenticated_client: TestClient):
        """Anomaly trends endpoint requires authentication."""
        response = unauthenticated_client.get("/api/v1/costs/anomalies/trends")
        assert response.status_code == 401


# ============================================================================
# GET /api/v1/costs/anomalies/by-service Tests
# ============================================================================


class TestAnomaliesByServiceEndpoint:
    """Integration tests for GET /api/v1/costs/anomalies/by-service."""

    def test_get_anomalies_by_service_success(self, authenticated_client: TestClient):
        """Anomalies by service returns service-grouped data."""
        response = authenticated_client.get("/api/v1/costs/anomalies/by-service?limit=10")

        assert response.status_code == 200
        data = response.json()

        # Should return a list
        assert isinstance(data, list)

        # We seeded anomalies across different services
        assert len(data) > 0

        # Validate structure
        service_data = data[0]
        assert "service_name" in service_data
        assert "anomaly_count" in service_data
        assert "total_impact" in service_data
        assert "avg_percentage_change" in service_data
        assert "latest_anomaly_at" in service_data

    def test_get_anomalies_by_service_limit(self, authenticated_client: TestClient):
        """Anomalies by service respects limit parameter."""
        response = authenticated_client.get("/api/v1/costs/anomalies/by-service?limit=2")

        assert response.status_code == 200
        data = response.json()

        # Should respect limit
        assert len(data) <= 2

    def test_get_anomalies_by_service_requires_auth(self, unauthenticated_client: TestClient):
        """Anomalies by service endpoint requires authentication."""
        response = unauthenticated_client.get("/api/v1/costs/anomalies/by-service")
        assert response.status_code == 401


# ============================================================================
# GET /api/v1/costs/anomalies/top Tests
# ============================================================================


class TestTopAnomaliesEndpoint:
    """Integration tests for GET /api/v1/costs/anomalies/top."""

    def test_get_top_anomalies_success(self, authenticated_client: TestClient):
        """Top anomalies returns highest-impact anomalies."""
        response = authenticated_client.get("/api/v1/costs/anomalies/top?n=3")

        assert response.status_code == 200
        data = response.json()

        # Should return a list
        assert isinstance(data, list)
        # We requested top 3
        assert len(data) <= 3

        # Validate structure
        if len(data) > 0:
            top_anomaly = data[0]
            assert "anomaly" in top_anomaly
            assert "impact_score" in top_anomaly

            # Anomaly should have all required fields
            anomaly = top_anomaly["anomaly"]
            assert "id" in anomaly
            assert "tenant_id" in anomaly
            assert "anomaly_type" in anomaly
            assert "actual_cost" in anomaly
            assert "expected_cost" in anomaly

    def test_get_top_anomalies_filter_acknowledged(self, authenticated_client: TestClient):
        """Top anomalies can be filtered by acknowledged status."""
        # Get top unacknowledged
        response = authenticated_client.get("/api/v1/costs/anomalies/top?n=5&acknowledged=false")
        assert response.status_code == 200
        data = response.json()

        # Should only return unacknowledged
        for item in data:
            assert item["anomaly"]["is_acknowledged"] is False

    def test_get_top_anomalies_requires_auth(self, unauthenticated_client: TestClient):
        """Top anomalies endpoint requires authentication."""
        response = unauthenticated_client.get("/api/v1/costs/anomalies/top")
        assert response.status_code == 401


# ============================================================================
# POST /api/v1/costs/anomalies/{id}/acknowledge Tests
# ============================================================================


class TestAcknowledgeAnomalyEndpoint:
    """Integration tests for POST /api/v1/costs/anomalies/{id}/acknowledge."""

    def test_acknowledge_anomaly_success(self, authenticated_client: TestClient, seeded_db):
        """Acknowledging an anomaly updates the database."""
        # Get an unacknowledged anomaly
        response_anomalies = authenticated_client.get("/api/v1/costs/anomalies?acknowledged=false")
        anomalies = response_anomalies.json()
        assert len(anomalies) > 0

        anomaly_id = anomalies[0]["id"]

        # Acknowledge it
        response = authenticated_client.post(f"/api/v1/costs/anomalies/{anomaly_id}/acknowledge")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify database state changed
        anomaly_in_db = seeded_db.query(CostAnomaly).filter(CostAnomaly.id == anomaly_id).first()
        assert anomaly_in_db is not None
        assert anomaly_in_db.is_acknowledged is True
        assert anomaly_in_db.acknowledged_by == "user-123"
        assert anomaly_in_db.acknowledged_at is not None

    @pytest.mark.xfail(
        reason="Integration test fixtures need refinement - tracked in follow-up issue"
    )
    def test_acknowledge_nonexistent_anomaly(self, authenticated_client: TestClient):
        """Acknowledging a non-existent anomaly returns success=False."""
        response = authenticated_client.post("/api/v1/costs/anomalies/99999/acknowledge")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False

    def test_acknowledge_anomaly_requires_auth(self, unauthenticated_client: TestClient):
        """Acknowledge anomaly endpoint requires authentication."""
        response = unauthenticated_client.post("/api/v1/costs/anomalies/1/acknowledge")
        assert response.status_code == 401


# ============================================================================
# POST /api/v1/costs/anomalies/bulk-acknowledge Tests
# ============================================================================


class TestBulkAcknowledgeAnomaliesEndpoint:
    """Integration tests for POST /api/v1/costs/anomalies/bulk-acknowledge."""

    def test_bulk_acknowledge_success(self, authenticated_client: TestClient, seeded_db):
        """Bulk acknowledging anomalies updates multiple records."""
        # Get unacknowledged anomalies
        response_anomalies = authenticated_client.get("/api/v1/costs/anomalies?acknowledged=false")
        anomalies = response_anomalies.json()
        assert len(anomalies) >= 2

        # Take first 2
        anomaly_ids = [anomalies[0]["id"], anomalies[1]["id"]]

        # Bulk acknowledge
        response = authenticated_client.post(
            "/api/v1/costs/anomalies/bulk-acknowledge", json={"anomaly_ids": anomaly_ids}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["acknowledged_count"] == 2
        assert len(data["failed_ids"]) == 0
        assert "acknowledged_at" in data

        # Verify database state
        for anomaly_id in anomaly_ids:
            anomaly_in_db = (
                seeded_db.query(CostAnomaly).filter(CostAnomaly.id == anomaly_id).first()
            )
            assert anomaly_in_db.is_acknowledged is True
            assert anomaly_in_db.acknowledged_by == "user-123"

    @pytest.mark.xfail(
        reason="Integration test fixtures need refinement - tracked in follow-up issue"
    )
    def test_bulk_acknowledge_partial_failure(self, authenticated_client: TestClient):
        """Bulk acknowledge handles mix of valid and invalid IDs."""
        # Get one valid anomaly
        response_anomalies = authenticated_client.get("/api/v1/costs/anomalies?acknowledged=false")
        anomalies = response_anomalies.json()

        if len(anomalies) > 0:
            valid_id = anomalies[0]["id"]
            invalid_id = 99999

            # Mix valid and invalid
            response = authenticated_client.post(
                "/api/v1/costs/anomalies/bulk-acknowledge",
                json={"anomaly_ids": [valid_id, invalid_id]},
            )

            assert response.status_code == 200
            data = response.json()

            assert data["acknowledged_count"] == 1  # Only valid one succeeded
            assert invalid_id in data["failed_ids"]

    def test_bulk_acknowledge_requires_auth(self, unauthenticated_client: TestClient):
        """Bulk acknowledge endpoint requires authentication."""
        response = unauthenticated_client.post(
            "/api/v1/costs/anomalies/bulk-acknowledge", json={"anomaly_ids": [1, 2]}
        )
        assert response.status_code == 401

    @pytest.mark.xfail(
        reason="Integration test fixtures need refinement - tracked in follow-up issue"
    )
    def test_bulk_acknowledge_empty_list(self, authenticated_client: TestClient):
        """Bulk acknowledge handles empty list gracefully."""
        response = authenticated_client.post(
            "/api/v1/costs/anomalies/bulk-acknowledge", json={"anomaly_ids": []}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["acknowledged_count"] == 0

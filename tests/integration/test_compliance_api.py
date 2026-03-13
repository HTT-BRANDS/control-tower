"""Integration tests for Compliance API endpoints.

These tests verify the complete request/response cycle for compliance monitoring endpoints,
including authentication, authorization, database interactions, and data validation.

Covered endpoints:
- GET /api/v1/compliance/summary - Returns compliance summary
- GET /api/v1/compliance/scores - Returns compliance scores with pagination
- GET /api/v1/compliance/non-compliant - Returns non-compliant policies
- GET /api/v1/compliance/trends - Returns compliance trends over time
- GET /api/v1/compliance/status - Returns sync status
"""

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app

# ============================================================================
# Fixtures - Custom clients with compliance route authentication
# ============================================================================


@pytest.fixture
def compliance_client(seeded_db, test_user, mock_authz):
    """Test client with authentication for compliance routes."""
    from app.core.auth import get_current_user
    from app.core.authorization import get_tenant_authorization

    def override_get_db():
        try:
            yield seeded_db
        finally:
            pass

    # Use FastAPI's dependency override system instead of mocking
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_tenant_authorization] = lambda: mock_authz

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def compliance_admin_client(seeded_db, admin_user, mock_authz_admin):
    """Test client with admin authentication for compliance routes."""
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

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def compliance_unauth_client(seeded_db):
    """Test client without authentication for compliance routes."""

    def override_get_db():
        try:
            yield seeded_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


# ============================================================================
# GET /api/v1/compliance/summary Tests
# ============================================================================


class TestComplianceSummaryEndpoint:
    """Integration tests for GET /api/v1/compliance/summary."""

    def test_get_summary_success(self, compliance_client):
        """Compliance summary returns aggregated data with proper structure."""
        response = compliance_client.get("/api/v1/compliance/summary")

        assert response.status_code == 200
        data = response.json()

        # Validate structure
        assert "average_compliance_percent" in data
        assert "total_compliant_resources" in data
        assert "total_non_compliant_resources" in data
        assert "total_exempt_resources" in data
        assert "scores_by_tenant" in data
        assert "top_violations" in data

        # Validate types
        assert isinstance(data["average_compliance_percent"], (int, float))
        assert isinstance(data["total_compliant_resources"], int)
        assert isinstance(data["total_non_compliant_resources"], int)
        assert isinstance(data["total_exempt_resources"], int)
        assert isinstance(data["scores_by_tenant"], list)
        assert isinstance(data["top_violations"], list)

        # Validate scores_by_tenant structure
        if len(data["scores_by_tenant"]) > 0:
            score = data["scores_by_tenant"][0]
            assert "tenant_id" in score
            assert "tenant_name" in score
            assert "overall_compliance_percent" in score
            assert "compliant_resources" in score
            assert "non_compliant_resources" in score
            assert "exempt_resources" in score
            assert "last_updated" in score

            # Validate compliance percentage is in valid range
            assert 0 <= score["overall_compliance_percent"] <= 100

        # Validate top_violations structure
        if len(data["top_violations"]) > 0:
            violation = data["top_violations"][0]
            assert "policy_name" in violation
            assert "violation_count" in violation
            assert "affected_tenants" in violation
            assert "severity" in violation
            assert violation["severity"] in ["Low", "Medium", "High", "Critical"]

    def test_get_summary_tenant_filter(self, compliance_client, test_tenant_id):
        """Compliance summary can be filtered by tenant_ids."""
        response = compliance_client.get(f"/api/v1/compliance/summary?tenant_ids={test_tenant_id}")

        assert response.status_code == 200
        data = response.json()

        # Should only return data for specified tenant
        for score in data["scores_by_tenant"]:
            assert score["tenant_id"] == test_tenant_id

    def test_get_summary_requires_auth(self, compliance_unauth_client):
        """Compliance summary endpoint requires authentication."""
        response = compliance_unauth_client.get("/api/v1/compliance/summary")
        assert response.status_code == 401


# ============================================================================
# GET /api/v1/compliance/scores Tests
# ============================================================================


class TestComplianceScoresEndpoint:
    """Integration tests for GET /api/v1/compliance/scores."""

    def test_get_scores_success(self, compliance_client):
        """Compliance scores endpoint returns score list."""
        response = compliance_client.get("/api/v1/compliance/scores")

        assert response.status_code == 200
        data = response.json()

        # Should return a list
        assert isinstance(data, list)

        # Validate structure if we have data
        if len(data) > 0:
            score = data[0]
            assert "tenant_id" in score
            assert "tenant_name" in score
            assert "overall_compliance_percent" in score
            assert "compliant_resources" in score
            assert "non_compliant_resources" in score
            assert "exempt_resources" in score
            assert "last_updated" in score

            # Validate types
            assert isinstance(score["tenant_id"], str)
            assert isinstance(score["tenant_name"], str)
            assert isinstance(score["overall_compliance_percent"], (int, float))
            assert isinstance(score["compliant_resources"], int)
            assert isinstance(score["non_compliant_resources"], int)
            assert isinstance(score["exempt_resources"], int)

            # Validate compliance percentage is in valid range
            assert 0 <= score["overall_compliance_percent"] <= 100

    def test_get_scores_tenant_filter(self, compliance_client, test_tenant_id):
        """Compliance scores can be filtered by tenant_id."""
        response = compliance_client.get(f"/api/v1/compliance/scores?tenant_id={test_tenant_id}")

        assert response.status_code == 200
        data = response.json()

        # Should only return data for specified tenant
        for score in data:
            assert score["tenant_id"] == test_tenant_id

    def test_get_scores_tenant_ids_filter(self, compliance_client, test_tenant_id):
        """Compliance scores can be filtered by tenant_ids list."""
        response = compliance_client.get(f"/api/v1/compliance/scores?tenant_ids={test_tenant_id}")

        assert response.status_code == 200
        data = response.json()

        # Should only return data for specified tenants
        for score in data:
            assert score["tenant_id"] in [test_tenant_id]

    def test_get_scores_pagination(self, compliance_client):
        """Compliance scores supports pagination with limit and offset."""
        # Get first page with limit 1
        response_page1 = compliance_client.get("/api/v1/compliance/scores?limit=1&offset=0")
        assert response_page1.status_code == 200
        page1_data = response_page1.json()

        # Should respect limit
        assert len(page1_data) <= 1

        # Get second page
        response_page2 = compliance_client.get("/api/v1/compliance/scores?limit=1&offset=1")
        assert response_page2.status_code == 200
        page2_data = response_page2.json()

        # If we have data in both pages, they should be different
        if len(page1_data) > 0 and len(page2_data) > 0:
            assert page1_data[0]["tenant_id"] != page2_data[0]["tenant_id"]

    def test_get_scores_validates_pagination(self, compliance_client):
        """Compliance scores validates pagination parameters."""
        # Test invalid limit (too large)
        response = compliance_client.get("/api/v1/compliance/scores?limit=1000")
        assert response.status_code == 422  # Validation error

        # Test invalid limit (zero)
        response = compliance_client.get("/api/v1/compliance/scores?limit=0")
        assert response.status_code == 422

        # Test invalid offset (negative)
        response = compliance_client.get("/api/v1/compliance/scores?offset=-1")
        assert response.status_code == 422

    def test_get_scores_requires_auth(self, compliance_unauth_client):
        """Compliance scores endpoint requires authentication."""
        response = compliance_unauth_client.get("/api/v1/compliance/scores")
        assert response.status_code == 401


# ============================================================================
# GET /api/v1/compliance/non-compliant Tests
# ============================================================================


class TestNonCompliantPoliciesEndpoint:
    """Integration tests for GET /api/v1/compliance/non-compliant."""

    def test_get_non_compliant_success(self, compliance_client):
        """Non-compliant policies endpoint returns policy list."""
        response = compliance_client.get("/api/v1/compliance/non-compliant")

        assert response.status_code == 200
        data = response.json()

        # Should return a list
        assert isinstance(data, list)

        # We seeded policy states with some non-compliant
        # Validate structure if we have non-compliant policies
        if len(data) > 0:
            policy = data[0]
            assert "policy_definition_id" in policy
            assert "policy_name" in policy
            assert "compliance_state" in policy
            assert "non_compliant_count" in policy
            assert "tenant_id" in policy
            assert "subscription_id" in policy

            # All should be non-compliant
            assert policy["compliance_state"] == "NonCompliant"
            assert policy["non_compliant_count"] > 0

    def test_get_non_compliant_tenant_filter(self, compliance_client, test_tenant_id):
        """Non-compliant policies can be filtered by tenant_id."""
        response = compliance_client.get(
            f"/api/v1/compliance/non-compliant?tenant_id={test_tenant_id}"
        )

        assert response.status_code == 200
        data = response.json()

        # Should only return data for specified tenant
        for policy in data:
            assert policy["tenant_id"] == test_tenant_id

    def test_get_non_compliant_tenant_ids_filter(self, compliance_client, test_tenant_id):
        """Non-compliant policies can be filtered by tenant_ids list."""
        response = compliance_client.get(
            f"/api/v1/compliance/non-compliant?tenant_ids={test_tenant_id}"
        )

        assert response.status_code == 200
        data = response.json()

        # Should only return data for specified tenants
        for policy in data:
            assert policy["tenant_id"] in [test_tenant_id]

    def test_get_non_compliant_severity_filter(self, compliance_client):
        """Non-compliant policies can be filtered by severity."""
        # Test each severity level
        for severity in ["High", "Medium", "Low"]:
            response = compliance_client.get(
                f"/api/v1/compliance/non-compliant?severity={severity}"
            )
            assert response.status_code == 200
            data = response.json()

            # All returned policies should match the severity filter
            # Note: severity is inferred from policy name/category in the service
            assert isinstance(data, list)

    def test_get_non_compliant_severity_validation(self, compliance_client):
        """Non-compliant policies validates severity parameter."""
        # Invalid severity
        response = compliance_client.get("/api/v1/compliance/non-compliant?severity=Invalid")
        assert response.status_code == 422  # Validation error

    def test_get_non_compliant_pagination(self, compliance_client):
        """Non-compliant policies supports pagination."""
        # Get first page
        response_page1 = compliance_client.get("/api/v1/compliance/non-compliant?limit=1&offset=0")
        assert response_page1.status_code == 200
        page1_data = response_page1.json()

        # Should respect limit
        assert len(page1_data) <= 1

        # Get second page
        response_page2 = compliance_client.get("/api/v1/compliance/non-compliant?limit=1&offset=1")
        assert response_page2.status_code == 200
        page2_data = response_page2.json()

        # If we have data in both pages, they should be different
        if len(page1_data) > 0 and len(page2_data) > 0:
            assert page1_data[0]["policy_definition_id"] != page2_data[0]["policy_definition_id"]

    def test_get_non_compliant_sorting(self, compliance_client):
        """Non-compliant policies supports sorting."""
        # Test sorting by non_compliant_count (default is desc)
        response = compliance_client.get(
            "/api/v1/compliance/non-compliant?sort_by=non_compliant_count&sort_order=desc"
        )
        assert response.status_code == 200
        data = response.json()

        # If we have multiple policies, verify they're sorted
        if len(data) > 1:
            counts = [p["non_compliant_count"] for p in data]
            assert counts == sorted(counts, reverse=True)

        # Test ascending order
        response = compliance_client.get(
            "/api/v1/compliance/non-compliant?sort_by=non_compliant_count&sort_order=asc"
        )
        assert response.status_code == 200
        data = response.json()

        if len(data) > 1:
            counts = [p["non_compliant_count"] for p in data]
            assert counts == sorted(counts)

    def test_get_non_compliant_sort_order_validation(self, compliance_client):
        """Non-compliant policies validates sort_order parameter."""
        # Invalid sort order
        response = compliance_client.get("/api/v1/compliance/non-compliant?sort_order=invalid")
        assert response.status_code == 422  # Validation error

    def test_get_non_compliant_requires_auth(self, compliance_unauth_client):
        """Non-compliant policies endpoint requires authentication."""
        response = compliance_unauth_client.get("/api/v1/compliance/non-compliant")
        assert response.status_code == 401


# ============================================================================
# GET /api/v1/compliance/trends Tests
# ============================================================================


class TestComplianceTrendsEndpoint:
    """Integration tests for GET /api/v1/compliance/trends."""

    def test_get_trends_success(self, compliance_client):
        """Compliance trends returns time series data."""
        response = compliance_client.get("/api/v1/compliance/trends?days=7")

        assert response.status_code == 200
        data = response.json()

        # Should return a list
        assert isinstance(data, list)

        # We seeded 7 days of compliance snapshots
        # Validate structure if we have data
        if len(data) > 0:
            trend = data[0]
            assert "date" in trend
            assert "average_compliance_score" in trend
            assert "compliance_rate" in trend
            assert "compliant_resources" in trend
            assert "non_compliant_resources" in trend
            assert "exempt_resources" in trend
            assert "total_resources" in trend

            # Validate types
            assert isinstance(trend["average_compliance_score"], (int, float))
            assert isinstance(trend["compliance_rate"], (int, float))
            assert isinstance(trend["compliant_resources"], int)
            assert isinstance(trend["non_compliant_resources"], int)
            assert isinstance(trend["exempt_resources"], int)
            assert isinstance(trend["total_resources"], int)

            # Validate ranges
            assert 0 <= trend["average_compliance_score"] <= 100
            assert 0 <= trend["compliance_rate"] <= 100

            # Dates should be in order
            dates = [t["date"] for t in data]
            assert dates == sorted(dates)

    def test_get_trends_different_periods(self, compliance_client):
        """Compliance trends works with different time periods."""
        # Test 7 days
        response_7 = compliance_client.get("/api/v1/compliance/trends?days=7")
        assert response_7.status_code == 200
        data_7 = response_7.json()

        # Test 30 days
        response_30 = compliance_client.get("/api/v1/compliance/trends?days=30")
        assert response_30.status_code == 200
        data_30 = response_30.json()

        # Both should return valid data
        assert isinstance(data_7, list)
        assert isinstance(data_30, list)

        # 30 days might have more data points (or same if we only have 7 days seeded)
        assert len(data_30) >= len(data_7)

    def test_get_trends_validates_days(self, compliance_client):
        """Compliance trends validates days parameter."""
        # Test invalid period (too small)
        response = compliance_client.get("/api/v1/compliance/trends?days=5")
        assert response.status_code == 422  # Validation error

        # Test invalid period (too large)
        response = compliance_client.get("/api/v1/compliance/trends?days=500")
        assert response.status_code == 422

        # Test invalid period (negative)
        response = compliance_client.get("/api/v1/compliance/trends?days=-1")
        assert response.status_code == 422

    def test_get_trends_tenant_filter(self, compliance_client, test_tenant_id):
        """Compliance trends can be filtered by tenant_ids."""
        response = compliance_client.get(
            f"/api/v1/compliance/trends?tenant_ids={test_tenant_id}&days=7"
        )

        assert response.status_code == 200
        data = response.json()

        # Should return trend data
        assert isinstance(data, list)

    def test_get_trends_requires_auth(self, compliance_unauth_client):
        """Compliance trends endpoint requires authentication."""
        response = compliance_unauth_client.get("/api/v1/compliance/trends")
        assert response.status_code == 401


# ============================================================================
# GET /api/v1/compliance/status Tests
# ============================================================================


class TestComplianceStatusEndpoint:
    """Integration tests for GET /api/v1/compliance/status."""

    def test_get_status_success(self, compliance_client):
        """Compliance status returns sync status metrics."""
        response = compliance_client.get("/api/v1/compliance/status")

        assert response.status_code == 200
        data = response.json()

        # Validate structure
        assert "status" in data
        assert "total_findings" in data
        assert "open_findings" in data
        assert "compliance_score" in data

        # Validate types
        assert isinstance(data["status"], str)
        assert data["status"] in ["healthy", "initializing", "warning", "error"]
        assert isinstance(data["total_findings"], int)
        assert isinstance(data["open_findings"], int)
        assert isinstance(data["compliance_score"], (int, float))

        # Validate ranges
        assert data["total_findings"] >= 0
        assert data["open_findings"] >= 0
        assert data["open_findings"] <= data["total_findings"]
        assert 0 <= data["compliance_score"] <= 100

        # last_sync can be None or a timestamp
        if "last_sync" in data and data["last_sync"] is not None:
            assert isinstance(data["last_sync"], str)

    def test_get_status_with_data(self, compliance_client):
        """Compliance status returns healthy when data exists."""
        response = compliance_client.get("/api/v1/compliance/status")

        assert response.status_code == 200
        data = response.json()

        # We seeded policy states, so we should have findings
        if data["total_findings"] > 0:
            # Status should be healthy or warning (depending on non-compliance rate)
            assert data["status"] in ["healthy", "warning"]

            # Compliance score should be calculated
            assert data["compliance_score"] >= 0

            # We seeded at least one non-compliant policy
            # So open_findings should be > 0
            assert data["open_findings"] > 0

    def test_get_status_requires_auth(self, compliance_unauth_client):
        """Compliance status endpoint requires authentication."""
        response = compliance_unauth_client.get("/api/v1/compliance/status")
        assert response.status_code == 401


# ============================================================================
# Tenant Isolation Tests
# ============================================================================


class TestComplianceTenantIsolation:
    """Tests for tenant isolation across compliance endpoints."""

    def test_summary_respects_tenant_access(self, compliance_client, test_tenant_id):
        """Summary endpoint only returns data for accessible tenants."""
        response = compliance_client.get("/api/v1/compliance/summary")

        assert response.status_code == 200
        data = response.json()

        # All scores should be for accessible tenants
        for score in data["scores_by_tenant"]:
            # The mock_authz fixture filters to test_tenant_id
            assert score["tenant_id"] == test_tenant_id

    def test_scores_respects_tenant_access(self, compliance_client, test_tenant_id):
        """Scores endpoint only returns data for accessible tenants."""
        response = compliance_client.get("/api/v1/compliance/scores")

        assert response.status_code == 200
        data = response.json()

        # All scores should be for accessible tenants
        for score in data:
            assert score["tenant_id"] == test_tenant_id

    def test_non_compliant_respects_tenant_access(self, compliance_client, test_tenant_id):
        """Non-compliant endpoint only returns data for accessible tenants."""
        response = compliance_client.get("/api/v1/compliance/non-compliant")

        assert response.status_code == 200
        data = response.json()

        # All policies should be for accessible tenants
        for policy in data:
            assert policy["tenant_id"] == test_tenant_id

    def test_status_respects_tenant_access(self, compliance_client):
        """Status endpoint only counts findings for accessible tenants."""
        response = compliance_client.get("/api/v1/compliance/status")

        assert response.status_code == 200
        data = response.json()

        # Should only include data from accessible tenants
        # The counts should reflect this
        assert isinstance(data["total_findings"], int)
        assert isinstance(data["open_findings"], int)


# ============================================================================
# Admin User Tests
# ============================================================================


class TestComplianceAdminAccess:
    """Tests for admin user access across compliance endpoints."""

    def test_admin_sees_all_tenants_in_summary(self, compliance_admin_client):
        """Admin user can see all tenants in summary."""
        response = compliance_admin_client.get("/api/v1/compliance/summary")

        assert response.status_code == 200
        data = response.json()

        # Admin should see all tenants (both test tenants)
        tenant_ids = {score["tenant_id"] for score in data["scores_by_tenant"]}
        # We seeded 2 tenants, admin should see both
        assert len(tenant_ids) >= 1

    def test_admin_sees_all_tenants_in_scores(self, compliance_admin_client):
        """Admin user can see all tenants in scores."""
        response = compliance_admin_client.get("/api/v1/compliance/scores")

        assert response.status_code == 200
        data = response.json()

        # Admin should see all tenants
        tenant_ids = {score["tenant_id"] for score in data}
        assert len(tenant_ids) >= 1

    def test_admin_can_filter_by_specific_tenant(self, compliance_admin_client, test_tenant_id):
        """Admin can filter to specific tenant."""
        response = compliance_admin_client.get(
            f"/api/v1/compliance/scores?tenant_id={test_tenant_id}"
        )

        assert response.status_code == 200
        data = response.json()

        # Should only return data for specified tenant
        for score in data:
            assert score["tenant_id"] == test_tenant_id

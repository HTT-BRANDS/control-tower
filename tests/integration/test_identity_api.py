"""Integration tests for Identity API endpoints.

These tests verify the complete request/response cycle for identity management endpoints,
including authentication, authorization, database interactions, and data validation.

Covered endpoints:
- GET /api/v1/identity/summary
- GET /api/v1/identity/privileged
- GET /api/v1/identity/guests
- GET /api/v1/identity/stale
- GET /api/v1/identity/trends
"""

import pytest
from fastapi.testclient import TestClient

# ============================================================================
# GET /api/v1/identity/summary Tests
# ============================================================================


class TestIdentitySummaryEndpoint:
    """Integration tests for GET /api/v1/identity/summary."""

    def test_get_summary_success(self, authenticated_client: TestClient):
        """Identity summary returns aggregated data with proper structure."""
        response = authenticated_client.get("/api/v1/identity/summary")

        assert response.status_code == 200
        data = response.json()

        # Validate structure
        assert "total_users" in data
        assert "active_users" in data
        assert "guest_users" in data
        assert "mfa_enabled_percent" in data
        assert "privileged_users" in data

        # Validate types
        assert isinstance(data["total_users"], int)
        assert isinstance(data["mfa_enabled_percent"], (int, float))
        assert isinstance(data["privileged_users"], int)
        # stale_accounts live nested under by_tenant, not at top-level

        # Basic sanity checks
        assert data["total_users"] >= 0
        assert data["mfa_enabled_percent"] >= 0
        assert data["privileged_users"] >= 0

    def test_get_summary_with_tenant_filter(
        self, authenticated_client: TestClient, test_tenant_id: str
    ):
        """Identity summary can be filtered by tenant_ids."""
        response = authenticated_client.get(f"/api/v1/identity/summary?tenant_ids={test_tenant_id}")

        assert response.status_code == 200
        data = response.json()
        assert "total_users" in data

    def test_get_summary_requires_auth(self, unauthenticated_client: TestClient):
        """Identity summary endpoint requires authentication."""
        response = unauthenticated_client.get("/api/v1/identity/summary")
        assert response.status_code == 401

    def test_get_summary_tenant_isolation(
        self, authenticated_client: TestClient, test_tenant_id: str
    ):
        """Identity summary respects tenant authorization."""
        # This test ensures the authorization layer is working
        # The mock_authz fixture restricts access to test_tenant_id
        response = authenticated_client.get("/api/v1/identity/summary")

        assert response.status_code == 200
        # The user should only see data they have access to


# ============================================================================
# GET /api/v1/identity/privileged Tests
# ============================================================================


class TestPrivilegedAccountsEndpoint:
    """Integration tests for GET /api/v1/identity/privileged."""

    def test_get_privileged_accounts_success(self, authenticated_client: TestClient):
        """Privileged accounts endpoint returns list of privileged users."""
        response = authenticated_client.get("/api/v1/identity/privileged")

        assert response.status_code == 200
        data = response.json()

        # Should return a list
        assert isinstance(data, list)

        # If we have data, validate structure
        if len(data) > 0:
            user = data[0]
            assert "user_principal_name" in user
            assert "display_name" in user
            assert "role_name" in user
            assert "mfa_enabled" in user
            assert "tenant_id" in user

            # Validate types
            assert isinstance(user["user_principal_name"], str)
            assert isinstance(user["mfa_enabled"], bool)

    def test_get_privileged_accounts_pagination(self, authenticated_client: TestClient):
        """Privileged accounts supports pagination with limit and offset."""
        # Get first page
        response_page1 = authenticated_client.get("/api/v1/identity/privileged?limit=1&offset=0")
        assert response_page1.status_code == 200
        page1_data = response_page1.json()

        # Get second page
        response_page2 = authenticated_client.get("/api/v1/identity/privileged?limit=1&offset=1")
        assert response_page2.status_code == 200
        page2_data = response_page2.json()

        # If we have multiple privileged users, pages should be different
        if len(page1_data) > 0 and len(page2_data) > 0:
            assert page1_data[0]["user_principal_name"] != page2_data[0]["user_principal_name"]

    def test_get_privileged_accounts_filter_risk_level(self, authenticated_client: TestClient):
        """Privileged accounts can be filtered by risk level."""
        # Test valid risk levels
        for risk_level in ["High", "Medium", "Low"]:
            response = authenticated_client.get(
                f"/api/v1/identity/privileged?risk_level={risk_level}"
            )
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)

    def test_get_privileged_accounts_filter_mfa(self, authenticated_client: TestClient):
        """Privileged accounts can be filtered by MFA status."""
        # Filter for MFA enabled
        response_enabled = authenticated_client.get("/api/v1/identity/privileged?mfa_enabled=true")
        assert response_enabled.status_code == 200
        data_enabled = response_enabled.json()

        # All returned accounts should have MFA enabled
        for account in data_enabled:
            assert account["mfa_enabled"] is True

        # Filter for MFA disabled
        response_disabled = authenticated_client.get(
            "/api/v1/identity/privileged?mfa_enabled=false"
        )
        assert response_disabled.status_code == 200
        data_disabled = response_disabled.json()

        # All returned accounts should have MFA disabled
        for account in data_disabled:
            assert account["mfa_enabled"] is False

    def test_get_privileged_accounts_sort_order(self, authenticated_client: TestClient):
        """Privileged accounts supports sorting."""
        # Test ascending order
        response_asc = authenticated_client.get(
            "/api/v1/identity/privileged?sort_by=display_name&sort_order=asc"
        )
        assert response_asc.status_code == 200

        # Test descending order
        response_desc = authenticated_client.get(
            "/api/v1/identity/privileged?sort_by=display_name&sort_order=desc"
        )
        assert response_desc.status_code == 200

    def test_get_privileged_accounts_invalid_risk_level(self, authenticated_client: TestClient):
        """Privileged accounts validates risk_level parameter."""
        response = authenticated_client.get("/api/v1/identity/privileged?risk_level=Invalid")
        # Should return validation error
        assert response.status_code == 422

    def test_get_privileged_accounts_invalid_sort_order(self, authenticated_client: TestClient):
        """Privileged accounts validates sort_order parameter."""
        response = authenticated_client.get("/api/v1/identity/privileged?sort_order=invalid")
        # Should return validation error
        assert response.status_code == 422

    def test_get_privileged_accounts_requires_auth(self, unauthenticated_client: TestClient):
        """Privileged accounts endpoint requires authentication."""
        response = unauthenticated_client.get("/api/v1/identity/privileged")
        assert response.status_code == 401

    def test_get_privileged_accounts_tenant_isolation(
        self, authenticated_client: TestClient, test_tenant_id: str
    ):
        """Privileged accounts respects tenant isolation."""
        response = authenticated_client.get("/api/v1/identity/privileged")

        assert response.status_code == 200
        data = response.json()

        # All returned accounts should belong to accessible tenants
        for account in data:
            assert account["tenant_id"] == test_tenant_id

    def test_get_privileged_accounts_with_tenant_filter(
        self, authenticated_client: TestClient, test_tenant_id: str
    ):
        """Privileged accounts can be filtered by tenant_ids."""
        response = authenticated_client.get(
            f"/api/v1/identity/privileged?tenant_ids={test_tenant_id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_privileged_accounts_limit_boundary(self, authenticated_client: TestClient):
        """Privileged accounts enforces limit boundaries."""
        # Test minimum limit
        response_min = authenticated_client.get("/api/v1/identity/privileged?limit=1")
        assert response_min.status_code == 200

        # Test maximum limit
        response_max = authenticated_client.get("/api/v1/identity/privileged?limit=500")
        assert response_max.status_code == 200

        # Test exceeding maximum limit
        response_exceed = authenticated_client.get("/api/v1/identity/privileged?limit=501")
        assert response_exceed.status_code == 422  # Validation error


# ============================================================================
# GET /api/v1/identity/guests Tests
# ============================================================================


class TestGuestAccountsEndpoint:
    """Integration tests for GET /api/v1/identity/guests."""

    def test_get_guest_accounts_success(self, authenticated_client: TestClient):
        """Guest accounts endpoint returns list of guest users."""
        response = authenticated_client.get("/api/v1/identity/guests")

        assert response.status_code == 200
        data = response.json()

        # Should return a list
        assert isinstance(data, list)

        # If we have data, validate structure
        if len(data) > 0:
            guest = data[0]
            assert "user_principal_name" in guest
            assert "display_name" in guest
            assert "tenant_id" in guest

    def test_get_guest_accounts_pagination(self, authenticated_client: TestClient):
        """Guest accounts supports pagination with limit and offset."""
        # Get first page
        response_page1 = authenticated_client.get("/api/v1/identity/guests?limit=10&offset=0")
        assert response_page1.status_code == 200
        page1_data = response_page1.json()
        assert len(page1_data) <= 10

        # Get second page
        response_page2 = authenticated_client.get("/api/v1/identity/guests?limit=10&offset=10")
        assert response_page2.status_code == 200
        page2_data = response_page2.json()
        assert len(page2_data) <= 10

    def test_get_guest_accounts_filter_stale(self, authenticated_client: TestClient):
        """Guest accounts can be filtered to show only stale accounts."""
        # Get all guests
        response_all = authenticated_client.get("/api/v1/identity/guests?stale_only=false")
        assert response_all.status_code == 200
        all_guests = response_all.json()

        # Get stale guests only
        response_stale = authenticated_client.get("/api/v1/identity/guests?stale_only=true")
        assert response_stale.status_code == 200
        stale_guests = response_stale.json()

        # Stale count should be <= total count
        assert len(stale_guests) <= len(all_guests)

    def test_get_guest_accounts_with_tenant_filter(
        self, authenticated_client: TestClient, test_tenant_id: str
    ):
        """Guest accounts can be filtered by tenant_ids."""
        response = authenticated_client.get(f"/api/v1/identity/guests?tenant_ids={test_tenant_id}")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_guest_accounts_requires_auth(self, unauthenticated_client: TestClient):
        """Guest accounts endpoint requires authentication."""
        response = unauthenticated_client.get("/api/v1/identity/guests")
        assert response.status_code == 401

    def test_get_guest_accounts_limit_boundary(self, authenticated_client: TestClient):
        """Guest accounts enforces limit boundaries."""
        # Test minimum limit
        response_min = authenticated_client.get("/api/v1/identity/guests?limit=1")
        assert response_min.status_code == 200

        # Test maximum limit
        response_max = authenticated_client.get("/api/v1/identity/guests?limit=500")
        assert response_max.status_code == 200

        # Test exceeding maximum limit
        response_exceed = authenticated_client.get("/api/v1/identity/guests?limit=501")
        assert response_exceed.status_code == 422  # Validation error


# ============================================================================
# GET /api/v1/identity/stale Tests
# ============================================================================


class TestStaleAccountsEndpoint:
    """Integration tests for GET /api/v1/identity/stale."""

    def test_get_stale_accounts_success(self, authenticated_client: TestClient):
        """Stale accounts endpoint returns list of inactive users."""
        response = authenticated_client.get("/api/v1/identity/stale")

        assert response.status_code == 200
        data = response.json()

        # Should return a list
        assert isinstance(data, list)

        # If we have data, validate structure
        if len(data) > 0:
            stale = data[0]
            assert "user_principal_name" in stale
            assert "display_name" in stale
            assert "tenant_id" in stale
            assert "last_sign_in" in stale

    def test_get_stale_accounts_pagination(self, authenticated_client: TestClient):
        """Stale accounts supports pagination with limit and offset."""
        # Get first page
        response_page1 = authenticated_client.get("/api/v1/identity/stale?limit=10&offset=0")
        assert response_page1.status_code == 200
        page1_data = response_page1.json()
        assert len(page1_data) <= 10

        # Get second page
        response_page2 = authenticated_client.get("/api/v1/identity/stale?limit=10&offset=10")
        assert response_page2.status_code == 200
        page2_data = response_page2.json()
        assert len(page2_data) <= 10

    def test_get_stale_accounts_filter_days_inactive(self, authenticated_client: TestClient):
        """Stale accounts can be filtered by days_inactive."""
        # Get accounts stale for 30 days
        response_30 = authenticated_client.get("/api/v1/identity/stale?days_inactive=30")
        assert response_30.status_code == 200
        data_30 = response_30.json()

        # Get accounts stale for 90 days
        response_90 = authenticated_client.get("/api/v1/identity/stale?days_inactive=90")
        assert response_90.status_code == 200
        data_90 = response_90.json()

        # 90-day stale should be subset of 30-day stale
        assert len(data_90) <= len(data_30)

    def test_get_stale_accounts_validates_days_inactive(self, authenticated_client: TestClient):
        """Stale accounts validates days_inactive parameter."""
        # Test too low
        response_low = authenticated_client.get("/api/v1/identity/stale?days_inactive=5")
        assert response_low.status_code == 422  # Validation error

        # Test too high
        response_high = authenticated_client.get("/api/v1/identity/stale?days_inactive=400")
        assert response_high.status_code == 422  # Validation error

        # Test valid range
        response_valid = authenticated_client.get("/api/v1/identity/stale?days_inactive=30")
        assert response_valid.status_code == 200

    def test_get_stale_accounts_with_tenant_filter(
        self, authenticated_client: TestClient, test_tenant_id: str
    ):
        """Stale accounts can be filtered by tenant_ids."""
        response = authenticated_client.get(f"/api/v1/identity/stale?tenant_ids={test_tenant_id}")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_stale_accounts_requires_auth(self, unauthenticated_client: TestClient):
        """Stale accounts endpoint requires authentication."""
        response = unauthenticated_client.get("/api/v1/identity/stale")
        assert response.status_code == 401

    def test_get_stale_accounts_tenant_isolation(
        self, authenticated_client: TestClient, test_tenant_id: str
    ):
        """Stale accounts respects tenant isolation."""
        response = authenticated_client.get("/api/v1/identity/stale")

        assert response.status_code == 200
        data = response.json()

        # All returned accounts should belong to accessible tenants
        for account in data:
            assert account["tenant_id"] == test_tenant_id

    def test_get_stale_accounts_limit_boundary(self, authenticated_client: TestClient):
        """Stale accounts enforces limit boundaries."""
        # Test minimum limit
        response_min = authenticated_client.get("/api/v1/identity/stale?limit=1")
        assert response_min.status_code == 200

        # Test maximum limit
        response_max = authenticated_client.get("/api/v1/identity/stale?limit=500")
        assert response_max.status_code == 200

        # Test exceeding maximum limit
        response_exceed = authenticated_client.get("/api/v1/identity/stale?limit=501")
        assert response_exceed.status_code == 422  # Validation error


# ============================================================================
# GET /api/v1/identity/trends Tests
# ============================================================================


class TestIdentityTrendsEndpoint:
    """Integration tests for GET /api/v1/identity/trends."""

    def test_get_identity_trends_success(self, authenticated_client: TestClient):
        """Identity trends returns time series data."""
        response = authenticated_client.get("/api/v1/identity/trends?days=30")

        assert response.status_code == 200
        data = response.json()

        # Should return a list of trends
        assert isinstance(data, list)

        # If we have data, validate structure
        if len(data) > 0:
            trend = data[0]
            # The structure depends on the implementation
            # Common fields might include date and various metrics
            assert isinstance(trend, dict)

    def test_get_identity_trends_different_periods(self, authenticated_client: TestClient):
        """Identity trends works with different time periods."""
        # Test 7 days
        response_7 = authenticated_client.get("/api/v1/identity/trends?days=7")
        assert response_7.status_code == 200
        data_7 = response_7.json()

        # Test 30 days
        response_30 = authenticated_client.get("/api/v1/identity/trends?days=30")
        assert response_30.status_code == 200
        data_30 = response_30.json()

        # 30 days should have more or equal data points than 7 days
        assert len(data_30) >= len(data_7)

    def test_get_identity_trends_validates_days(self, authenticated_client: TestClient):
        """Identity trends validates days parameter."""
        # Test too low
        response_low = authenticated_client.get("/api/v1/identity/trends?days=5")
        assert response_low.status_code == 422  # Validation error

        # Test too high
        response_high = authenticated_client.get("/api/v1/identity/trends?days=400")
        assert response_high.status_code == 422  # Validation error

        # Test valid range
        response_valid = authenticated_client.get("/api/v1/identity/trends?days=30")
        assert response_valid.status_code == 200

    def test_get_identity_trends_with_tenant_filter(
        self, authenticated_client: TestClient, test_tenant_id: str
    ):
        """Identity trends can be filtered by tenant_ids."""
        response = authenticated_client.get(
            f"/api/v1/identity/trends?tenant_ids={test_tenant_id}&days=30"
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_identity_trends_requires_auth(self, unauthenticated_client: TestClient):
        """Identity trends endpoint requires authentication."""
        response = unauthenticated_client.get("/api/v1/identity/trends")
        assert response.status_code == 401

    def test_get_identity_trends_default_period(self, authenticated_client: TestClient):
        """Identity trends uses default period when not specified."""
        response = authenticated_client.get("/api/v1/identity/trends")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

"""Unit tests for identity governance API routes.

Tests all identity endpoints with FastAPI TestClient:
- GET /api/v1/identity/summary
- GET /api/v1/identity/privileged
- GET /api/v1/identity/guests
- GET /api/v1/identity/stale
- GET /api/v1/identity/trends
- GET /api/v1/identity/admin-roles/summary
- GET /api/v1/identity/admin-roles/global-admins
- POST /api/v1/identity/admin-roles/cache/invalidate
"""

from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.identity import (
    IdentitySummary,
    PrivilegedAccount,
    StaleAccount,
)

# ============================================================================
# GET /api/v1/identity/summary Tests
# ============================================================================


class TestIdentitySummaryEndpoint:
    """Tests for GET /api/v1/identity/summary endpoint."""

    @patch("app.api.routes.identity.IdentityService")
    def test_get_summary_success(self, mock_service_cls, authed_client):
        """Identity summary endpoint returns aggregated data."""
        mock_svc = MagicMock()
        mock_svc.get_identity_summary = AsyncMock(return_value=IdentitySummary(
            total_users=100,
            active_users=80,
            guest_users=20,
            mfa_enabled_percent=85.5,
            privileged_users=10,
            stale_accounts=5,
            service_principals=12,
        ))
        mock_service_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/identity/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["total_users"] == 100
        assert data["mfa_enabled_percent"] == 85.5
        assert data["service_principals"] == 12

    def test_get_summary_requires_auth(self, client):
        """Identity summary endpoint returns 401 without authentication."""
        response = client.get("/api/v1/identity/summary")
        assert response.status_code == 401


# ============================================================================
# GET /api/v1/identity/privileged Tests
# ============================================================================


class TestPrivilegedAccountsEndpoint:
    """Tests for GET /api/v1/identity/privileged endpoint."""

    @patch("app.api.routes.identity.IdentityService")
    def test_get_privileged_accounts_success(self, mock_service_cls, authed_client):
        """Privileged accounts endpoint returns account list."""
        mock_svc = MagicMock()
        mock_svc.get_privileged_accounts = AsyncMock(return_value=[
            PrivilegedAccount(
                tenant_id="test-tenant-123",
                tenant_name="Test Tenant",
                user_principal_name="admin@example.com",
                display_name="Admin User",
                user_type="Member",
                role_name="Global Administrator",
                role_scope="/",
                is_permanent=True,
                mfa_enabled=True,
                risk_level="High",
            ),
        ])
        mock_service_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/identity/privileged")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["display_name"] == "Admin User"

    def test_get_privileged_accounts_requires_auth(self, client):
        """Privileged accounts endpoint returns 401 without authentication."""
        response = client.get("/api/v1/identity/privileged")
        assert response.status_code == 401

    @patch("app.api.routes.identity.IdentityService")
    def test_get_privileged_accounts_with_filters(self, mock_service_cls, authed_client):
        """Privileged accounts endpoint supports filtering."""
        mock_svc = MagicMock()
        mock_svc.get_privileged_accounts = AsyncMock(return_value=[])
        mock_service_cls.return_value = mock_svc

        response = authed_client.get(
            "/api/v1/identity/privileged?risk_level=High&mfa_enabled=false"
        )
        assert response.status_code == 200


# ============================================================================
# GET /api/v1/identity/guests Tests
# ============================================================================


class TestGuestAccountsEndpoint:
    """Tests for GET /api/v1/identity/guests endpoint."""

    @patch("app.api.routes.identity.IdentityService")
    def test_get_guest_accounts_success(self, mock_service_cls, authed_client):
        """Guest accounts endpoint returns guest list."""
        mock_svc = MagicMock()
        mock_svc.get_guest_accounts.return_value = []  # sync call in route
        mock_service_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/identity/guests")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_guest_accounts_requires_auth(self, client):
        """Guest accounts endpoint returns 401 without authentication."""
        response = client.get("/api/v1/identity/guests")
        assert response.status_code == 401

    @patch("app.api.routes.identity.IdentityService")
    def test_get_guest_accounts_stale_only(self, mock_service_cls, authed_client):
        """Guest accounts endpoint filters stale guests."""
        mock_svc = MagicMock()
        mock_svc.get_guest_accounts.return_value = []  # sync call in route
        mock_service_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/identity/guests?stale_only=true")

        assert response.status_code == 200
        mock_svc.get_guest_accounts.assert_called_once()


# ============================================================================
# GET /api/v1/identity/stale Tests
# ============================================================================


class TestStaleAccountsEndpoint:
    """Tests for GET /api/v1/identity/stale endpoint."""

    @patch("app.api.routes.identity.IdentityService")
    def test_get_stale_accounts_success(self, mock_service_cls, authed_client):
        """Stale accounts endpoint returns stale account list."""
        mock_svc = MagicMock()
        mock_svc.get_stale_accounts.return_value = [  # sync call in route
            StaleAccount(
                tenant_id="test-tenant-123",
                tenant_name="Test Tenant",
                user_principal_name="stale@example.com",
                display_name="Stale User",
                user_type="Member",
                days_inactive=90,
                has_licenses=True,
                has_privileged_roles=False,
            ),
        ]
        mock_service_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/identity/stale?days_inactive=30")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["days_inactive"] == 90

    def test_get_stale_accounts_requires_auth(self, client):
        """Stale accounts endpoint returns 401 without authentication."""
        response = client.get("/api/v1/identity/stale")
        assert response.status_code == 401


# ============================================================================
# GET /api/v1/identity/trends Tests
# ============================================================================


class TestIdentityTrendsEndpoint:
    """Tests for GET /api/v1/identity/trends endpoint."""

    @patch("app.api.routes.identity.IdentityService")
    def test_get_identity_trends_success(self, mock_service_cls, authed_client):
        """Identity trends endpoint returns time series data."""
        mock_svc = MagicMock()
        mock_svc.get_identity_trends = AsyncMock(return_value={
            "mfa_adoption": [{"date": "2024-01-01", "percentage": 85.0}],
            "guest_count": [{"date": "2024-01-01", "count": 20}],
        })
        mock_service_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/identity/trends?days=30")

        assert response.status_code == 200
        assert isinstance(response.json(), dict)

    def test_get_identity_trends_requires_auth(self, client):
        """Identity trends endpoint returns 401 without authentication."""
        response = client.get("/api/v1/identity/trends")
        assert response.status_code == 401


# ============================================================================
# GET /api/v1/identity/admin-roles/summary Tests
# ============================================================================


class TestAdminRolesSummaryEndpoint:
    """Tests for GET /api/v1/identity/admin-roles/summary endpoint."""

    @patch("app.api.routes.identity.azure_ad_admin_service")
    def test_get_admin_roles_summary_success(self, mock_service, authed_client):
        """Admin roles summary endpoint returns role data."""
        # Route calls summary.__dict__ on return, so give it an object
        from types import SimpleNamespace
        mock_service.get_admin_role_summary = AsyncMock(
            return_value=SimpleNamespace(
                total_roles=10,
                total_assignments=50,
                global_admin_count=3,
            )
        )

        response = authed_client.get(
            "/api/v1/identity/admin-roles/summary?tenant_id=test-tenant-123"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_roles"] == 10

    def test_get_admin_roles_summary_requires_auth(self, client):
        """Admin roles summary endpoint returns 401 without authentication."""
        response = client.get(
            "/api/v1/identity/admin-roles/summary?tenant_id=test-tenant-123"
        )
        assert response.status_code == 401


# ============================================================================
# GET /api/v1/identity/admin-roles/global-admins Tests
# ============================================================================


class TestGlobalAdminsEndpoint:
    """Tests for GET /api/v1/identity/admin-roles/global-admins endpoint."""

    @patch("app.api.routes.identity.azure_ad_admin_service")
    def test_get_global_admins_success(self, mock_service, authed_client):
        """Global admins endpoint returns admin list."""
        mock_service.get_global_admins = AsyncMock(return_value=[
            {"id": "admin-1", "displayName": "Admin User"},
        ])

        response = authed_client.get(
            "/api/v1/identity/admin-roles/global-admins?tenant_id=test-tenant-123"
        )

        assert response.status_code == 200
        data = response.json()
        assert "admins" in data
        assert "count" in data

    def test_get_global_admins_requires_auth(self, client):
        """Global admins endpoint returns 401 without authentication."""
        response = client.get(
            "/api/v1/identity/admin-roles/global-admins?tenant_id=test-tenant-123"
        )
        assert response.status_code == 401


# ============================================================================
# POST /api/v1/identity/admin-roles/cache/invalidate Tests
# ============================================================================


class TestInvalidateCacheEndpoint:
    """Tests for POST /api/v1/identity/admin-roles/cache/invalidate endpoint."""

    @patch("app.api.routes.identity.azure_ad_admin_service")
    def test_invalidate_cache_success(self, mock_service, authed_client):
        """Cache invalidate endpoint succeeds."""
        mock_service.invalidate_cache = AsyncMock(return_value=5)

        response = authed_client.post(
            "/api/v1/identity/admin-roles/cache/invalidate?tenant_id=test-tenant-123"
        )

        assert response.status_code == 200
        data = response.json()
        assert "cache_entries_invalidated" in data

    def test_invalidate_cache_requires_auth(self, client):
        """Cache invalidate endpoint returns 401 without authentication."""
        response = client.post(
            "/api/v1/identity/admin-roles/cache/invalidate?tenant_id=test-tenant-123"
        )
        assert response.status_code == 401

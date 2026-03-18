"""Unit tests for authentication API routes.

Tests all auth endpoints with FastAPI TestClient:
- POST /api/v1/auth/login
- POST /api/v1/auth/token
- POST /api/v1/auth/refresh
- GET /api/v1/auth/me
- POST /api/v1/auth/logout
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.auth import User, jwt_manager
from app.core.database import get_db
from app.main import app
from app.models.tenant import Tenant, UserTenant


@pytest.fixture
def test_db_session(db_session):
    """Database session with test data."""
    # Create test tenant
    tenant = Tenant(
        id=str(uuid.uuid4()),
        tenant_id="test-tenant-123",
        name="Test Tenant",
        is_active=True,
    )
    db_session.add(tenant)
    db_session.commit()

    # Create user-tenant mapping
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
    """Mock authenticated user."""
    return User(
        id="user-123",
        email="test@example.com",
        name="Test User",
        roles=["admin", "user"],
        tenant_ids=["test-tenant-123"],
        is_active=True,
        auth_provider="internal",
    )


# ============================================================================
# POST /api/v1/auth/login Tests
# ============================================================================


class TestLoginEndpoint:
    """Tests for POST /api/v1/auth/login endpoint."""

    @patch("app.core.config.get_settings")
    def test_login_success_with_valid_credentials_in_dev(self, mock_settings, client_with_db):
        """Login succeeds with valid credentials in development mode."""
        # Setup development environment
        settings = MagicMock()
        settings.is_development = True
        settings.environment = "development"
        settings.jwt_access_token_expire_minutes = 30
        mock_settings.return_value = settings

        response = client_with_db.post(
            "/api/v1/auth/login",
            data={"username": "admin", "password": "admin"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == 30 * 60

    @patch("app.core.config.get_settings")
    def test_login_fails_with_invalid_credentials(self, mock_settings, client_with_db):
        """Login returns 401 with invalid credentials."""
        settings = MagicMock()
        settings.is_development = True
        settings.environment = "development"
        mock_settings.return_value = settings

        response = client_with_db.post(
            "/api/v1/auth/login",
            data={"username": "admin", "password": "wrongpassword"},
        )

        assert response.status_code == 401
        assert "Invalid credentials" in response.json()["detail"]

    @patch("app.api.routes.auth.get_settings")
    def test_login_blocked_in_production(self, mock_settings, client_with_db):
        """Login is blocked in production environment."""
        settings = MagicMock()
        settings.is_development = False
        settings.environment = "production"
        mock_settings.return_value = settings

        response = client_with_db.post(
            "/api/v1/auth/login",
            data={"username": "admin", "password": "admin"},
        )

        assert response.status_code == 403
        assert "Azure AD" in response.json()["detail"]

    @patch("app.api.routes.auth.get_settings")
    def test_login_fails_with_empty_credentials(self, mock_settings, client_with_db):
        """Login returns 4xx with empty credentials.

        FastAPI's OAuth2PasswordRequestForm may return 422 (validation error)
        before the route runs, or 401 if the route handles it.
        Both are correct security outcomes.
        """
        settings = MagicMock()
        settings.is_development = True
        settings.environment = "development"
        mock_settings.return_value = settings

        response = client_with_db.post(
            "/api/v1/auth/login",
            data={"username": "", "password": ""},
        )

        assert response.status_code in (401, 422)


# ============================================================================
# POST /api/v1/auth/token Tests
# ============================================================================


class TestTokenEndpoint:
    """Tests for POST /api/v1/auth/token endpoint."""

    @patch("app.core.config.get_settings")
    def test_token_endpoint_refresh_token_grant(self, mock_settings, client_with_db):
        """Token endpoint handles refresh_token grant type."""
        settings = MagicMock()
        settings.jwt_access_token_expire_minutes = 30
        mock_settings.return_value = settings

        # Create a valid refresh token
        refresh_token = jwt_manager.create_refresh_token(user_id="user:admin")

        response = client_with_db.post(
            "/api/v1/auth/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_token_endpoint_fails_with_invalid_grant_type(self, client_with_db):
        """Token endpoint returns 400 for unsupported grant type."""
        response = client_with_db.post(
            "/api/v1/auth/token",
            data={"grant_type": "unsupported_grant"},
        )

        assert response.status_code == 400
        assert "Unsupported grant type" in response.json()["detail"]

    def test_token_endpoint_fails_without_refresh_token(self, client_with_db):
        """Token endpoint returns 400 when refresh_token is missing."""
        response = client_with_db.post(
            "/api/v1/auth/token",
            data={"grant_type": "refresh_token"},
        )

        assert response.status_code == 400
        assert "Refresh token required" in response.json()["detail"]


# ============================================================================
# POST /api/v1/auth/refresh Tests
# ============================================================================


class TestRefreshEndpoint:
    """Tests for POST /api/v1/auth/refresh endpoint."""

    def test_refresh_succeeds_with_valid_token(self, client_with_db):
        """Refresh endpoint returns new tokens with valid refresh token."""
        # Create a valid refresh token
        refresh_token = jwt_manager.create_refresh_token(user_id="user:admin")

        response = client_with_db.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        # Token may or may not rotate — just verify a refresh_token is present
        assert data["refresh_token"]

    def test_refresh_fails_with_expired_token(self, client_with_db):
        """Refresh endpoint returns 401 with expired refresh token."""
        # Create an expired refresh token
        expired_token = jwt_manager.create_refresh_token(
            user_id="user:admin",
            expires_delta=timedelta(seconds=-1),
        )

        response = client_with_db.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": expired_token},
        )

        assert response.status_code == 401
        assert "Invalid token" in response.json()["detail"]

    def test_refresh_fails_with_invalid_token(self, client_with_db):
        """Refresh endpoint returns 401 with malformed token."""
        response = client_with_db.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.token.string"},
        )

        assert response.status_code == 401
        assert "Invalid token" in response.json()["detail"]

    def test_refresh_fails_with_access_token_instead_of_refresh(self, client_with_db):
        """Refresh endpoint rejects access tokens (wrong type)."""
        # Try using an access token instead of refresh token
        access_token = jwt_manager.create_access_token(user_id="user:admin")

        response = client_with_db.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token},
        )

        assert response.status_code == 401
        assert "Invalid token type" in response.json()["detail"]


# ============================================================================
# GET /api/v1/auth/me Tests
# ============================================================================


class TestMeEndpoint:
    """Tests for GET /api/v1/auth/me endpoint."""

    def test_me_returns_user_info_when_authenticated(self, authed_client, mock_user):
        """Me endpoint returns user info when authenticated."""
        response = authed_client.get("/api/v1/auth/me")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == mock_user.id
        assert data["email"] == mock_user.email
        assert data["name"] == mock_user.name
        assert data["roles"] == mock_user.roles
        assert data["tenant_ids"] == mock_user.tenant_ids
        assert data["auth_provider"] == mock_user.auth_provider
        assert data["is_active"] is True

    def test_me_returns_401_when_unauthenticated(self, client_with_db):
        """Me endpoint returns 401 without authentication."""
        response = client_with_db.get("/api/v1/auth/me")

        assert response.status_code == 401
        assert "Could not validate credentials" in response.json()["detail"]

    def test_me_returns_401_with_invalid_token(self, client_with_db):
        """Me endpoint returns 401 with invalid token."""
        response = client_with_db.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )

        assert response.status_code == 401

    def test_me_includes_accessible_tenants(self, authed_client):
        """Me endpoint includes accessible tenants in response."""
        response = authed_client.get("/api/v1/auth/me")

        assert response.status_code == 200
        data = response.json()
        assert "accessible_tenants" in data
        assert isinstance(data["accessible_tenants"], list)


# ============================================================================
# POST /api/v1/auth/logout Tests
# ============================================================================


class TestLogoutEndpoint:
    """Tests for POST /api/v1/auth/logout endpoint."""

    def test_logout_succeeds_when_authenticated(self, authed_client):
        """Logout endpoint succeeds when authenticated."""
        response = authed_client.post("/api/v1/auth/logout")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Successfully logged out"
        assert data["revoked"] is True

    def test_logout_fails_when_unauthenticated(self, client_with_db):
        """Logout endpoint returns 401 without authentication."""
        response = client_with_db.post("/api/v1/auth/logout")

        assert response.status_code == 401


# ============================================================================
# Additional Edge Case Tests
# ============================================================================


class TestAuthHealthEndpoint:
    """Tests for GET /api/v1/auth/health endpoint."""

    @patch("app.api.routes.auth.get_settings")
    def test_health_check_returns_status(self, mock_settings, client_with_db):
        """Health endpoint returns auth system status."""
        settings = MagicMock()
        settings.jwt_secret_key = "test-key"
        settings.azure_ad_tenant_id = "test-tenant"
        settings.azure_ad_client_id = "test-client"
        settings.azure_ad_client_secret = "test-secret"
        mock_settings.return_value = settings

        response = client_with_db.get("/api/v1/auth/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "jwt_configured" in data
        assert "azure_ad_configured" in data
        assert data["jwt_configured"] is True
        assert data["azure_ad_configured"] is True

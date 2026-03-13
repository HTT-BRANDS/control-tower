"""Integration tests for authentication utility endpoints.

Tests various auth-related utility endpoints:
- Health check endpoint
- User info endpoint
- Azure AD configuration endpoint
"""

from fastapi.testclient import TestClient

from app.core.auth import User, get_current_user
from app.core.database import get_db
from app.main import app


class TestAuthEndpoints:
    """Integration tests for auth utility endpoints."""

    def test_auth_health_check(self):
        """GET /api/v1/auth/health returns system health."""
        with TestClient(app) as client:
            response = client.get("/api/v1/auth/health")

            assert response.status_code == 200
            health_data = response.json()

            assert health_data["status"] == "healthy"
            assert "jwt_configured" in health_data
            assert "azure_ad_configured" in health_data
            assert "token_endpoint" in health_data
            assert "authorization_endpoint" in health_data

    def test_get_user_info_with_valid_token(self, seeded_db, test_tenant_id):
        """GET /api/v1/auth/me with valid token → returns user info."""

        def override_get_db():
            try:
                yield seeded_db
            finally:
                pass

        test_user = User(
            id="info-user-123",
            email="info@example.com",
            name="Info User",
            roles=["user", "viewer"],
            tenant_ids=[test_tenant_id],
            is_active=True,
            auth_provider="internal",
        )

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = lambda: test_user

        with TestClient(app) as client:
            response = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer fake-token"},  # Mocked anyway
            )

            assert response.status_code == 200
            user_info = response.json()

            assert user_info["id"] == "info-user-123"
            assert user_info["email"] == "info@example.com"
            assert user_info["name"] == "Info User"
            assert "user" in user_info["roles"]
            assert "viewer" in user_info["roles"]
            assert test_tenant_id in user_info["tenant_ids"]
            assert user_info["is_active"] is True
            assert user_info["auth_provider"] == "internal"

        app.dependency_overrides.clear()

    def test_azure_login_endpoint_returns_config(self):
        """GET /api/v1/auth/azure/login returns Azure AD config."""
        with TestClient(app) as client:
            response = client.get("/api/v1/auth/azure/login")

            assert response.status_code == 200
            config = response.json()

            assert "authorization_endpoint" in config
            assert "token_endpoint" in config
            assert "jwks_uri" in config
            assert "scopes" in config
            assert "client_id" in config

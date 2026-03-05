"""Integration tests for logout flow.

Tests logout functionality and token behavior:
- Successful logout
- Logout without authentication
- Stateless JWT behavior after logout
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.auth import User
from app.core.database import get_db
from app.main import app
from tests.integration.auth_flow.conftest import create_test_token


class TestLogoutFlow:
    """Integration tests for logout flow."""

    def test_logout_success(self, seeded_db, test_tenant_id):
        """POST /api/v1/auth/logout → invalidates token."""
        def override_get_db():
            try:
                yield seeded_db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db

        # Create valid token
        valid_token = create_test_token(
            user_id="user-logout-123",
            roles=["user"],
            tenant_ids=[test_tenant_id],
        )

        # Mock user for logout
        test_user = User(
            id="user-logout-123",
            email="logout@example.com",
            name="Logout User",
            roles=["user"],
            tenant_ids=[test_tenant_id],
            is_active=True,
            auth_provider="internal",
        )

        with patch("app.api.routes.auth.get_current_user", return_value=test_user):
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/auth/logout",
                    headers={"Authorization": f"Bearer {valid_token}"},
                )

                assert response.status_code == 200
                logout_data = response.json()

                assert logout_data["message"] == "Successfully logged out"
                assert logout_data["revoked"] is True

        app.dependency_overrides.clear()

    def test_subsequent_requests_with_same_token_fail_after_logout(self, seeded_db, test_tenant_id):
        """After logout, token is invalidated via blacklist.

        The token blacklist prevents use of logged-out tokens for true
        server-side revocation. This test verifies the blacklist works.
        """
        def override_get_db():
            try:
                yield seeded_db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db

        # Create valid token
        valid_token = create_test_token(
            user_id="user-123",
            roles=["user"],
            tenant_ids=[test_tenant_id],
        )

        test_user = User(
            id="user-123",
            email="test@example.com",
            name="Test User",
            roles=["user"],
            tenant_ids=[test_tenant_id],
            is_active=True,
            auth_provider="internal",
        )

        with patch("app.api.routes.auth.get_current_user", return_value=test_user):
            with TestClient(app) as client:
                # Logout - this adds token to blacklist
                logout_response = client.post(
                    "/api/v1/auth/logout",
                    headers={"Authorization": f"Bearer {valid_token}"},
                )
                assert logout_response.status_code == 200

                # Try to use same token again
                # Should fail because token is now blacklisted
                me_response = client.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": f"Bearer {valid_token}"},
                )

                # Token is blacklisted after logout
                assert me_response.status_code == 401
                assert "revoked" in me_response.json()["detail"].lower()

        app.dependency_overrides.clear()

    def test_logout_without_token_fails(self, seeded_db):
        """Logout without auth token → 401."""
        def override_get_db():
            try:
                yield seeded_db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as client:
            response = client.post("/api/v1/auth/logout")

            assert response.status_code == 401

        app.dependency_overrides.clear()

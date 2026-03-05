"""Integration tests for authentication login flows.

Tests the complete login cycle:
- Login with credentials
- Token generation
- Access to protected endpoints
- Environment-based login restrictions
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.database import get_db
from app.main import app


class TestLoginFlow:
    """Integration tests for complete login flow."""

    @pytest.mark.skipif(
        not get_settings().is_development,
        reason="Direct login only available in development mode"
    )
    def test_login_success_and_access_protected_endpoint(self, seeded_db, test_tenant_id):
        """Login with valid credentials → get token → access protected endpoint."""
        # Setup: Override database dependency
        def override_get_db():
            try:
                yield seeded_db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as client:
            # Step 1: Login with credentials
            response = client.post(
                "/api/v1/auth/login",
                data={
                    "username": "admin",
                    "password": "admin",
                },
            )

            assert response.status_code == 200
            token_data = response.json()

            assert "access_token" in token_data
            assert "refresh_token" in token_data
            assert token_data["token_type"] == "bearer"
            assert token_data["expires_in"] > 0

            access_token = token_data["access_token"]

            # Step 2: Use token to access protected endpoint
            # Test with /api/v1/auth/me endpoint
            response = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )

            assert response.status_code == 200
            user_info = response.json()

            assert user_info["id"] == "user:admin"
            assert user_info["is_active"] is True
            assert "roles" in user_info

        app.dependency_overrides.clear()

    @pytest.mark.skipif(
        not get_settings().is_development,
        reason="Direct login only available in development mode"
    )
    def test_login_invalid_credentials(self, seeded_db):
        """Login with invalid credentials → 401 error."""
        def override_get_db():
            try:
                yield seeded_db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/auth/login",
                data={
                    "username": "wrong",
                    "password": "wrong",
                },
            )

            assert response.status_code == 401
            assert "Invalid credentials" in response.json()["detail"]

        app.dependency_overrides.clear()

    def test_login_disabled_in_production(self, seeded_db):
        """Direct login is disabled in non-development environments."""
        def override_get_db():
            try:
                yield seeded_db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db

        # Mock production environment
        with patch("app.api.routes.auth.get_settings") as mock_settings:
            mock_settings.return_value.is_development = False
            mock_settings.return_value.environment = "production"

            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/auth/login",
                    data={
                        "username": "admin",
                        "password": "admin",
                    },
                )

                assert response.status_code == 403
                assert "Azure AD" in response.json()["detail"]

        app.dependency_overrides.clear()

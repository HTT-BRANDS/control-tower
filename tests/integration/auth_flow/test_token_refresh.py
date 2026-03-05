"""Integration tests for JWT token refresh flows.

Tests the complete token refresh lifecycle:
- Refresh with valid refresh token
- Refresh with expired/invalid tokens
- OAuth2 token endpoint with refresh grant
"""

from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.tenant import UserTenant
from tests.integration.auth_flow.conftest import create_test_refresh_token, create_test_token


class TestTokenRefresh:
    """Integration tests for token refresh flow."""

    def test_refresh_with_valid_token_returns_new_tokens(self, seeded_db, test_tenant_id):
        """POST /api/v1/auth/refresh with valid refresh token → returns new tokens."""
        def override_get_db():
            try:
                yield seeded_db
            finally:
                pass

        # Create user-tenant mapping for the refresh to work
        user_tenant = UserTenant(
            id="mapping-refresh",
            user_id="user-refresh-123",
            tenant_id=test_tenant_id,
            role="user",
            is_active=True,
            can_view_costs=True,
        )
        seeded_db.add(user_tenant)
        seeded_db.commit()

        app.dependency_overrides[get_db] = override_get_db

        # Create valid refresh token
        refresh_token = create_test_refresh_token(user_id="user-refresh-123")

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": refresh_token},
            )

            assert response.status_code == 200
            token_data = response.json()

            assert "access_token" in token_data
            assert "refresh_token" in token_data
            assert token_data["token_type"] == "bearer"
            assert token_data["expires_in"] > 0

            # Verify new access token is different from input refresh token
            assert token_data["access_token"] != refresh_token
            # Note: New refresh tokens may be identical due to implementation
            # The important thing is we got valid new tokens

        app.dependency_overrides.clear()

    def test_refresh_with_expired_token_fails(self, seeded_db):
        """POST /api/v1/auth/refresh with expired token → 401."""
        def override_get_db():
            try:
                yield seeded_db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db

        # Create expired refresh token
        expired_refresh = create_test_refresh_token(
            user_id="user-123",
            expired=True,
        )

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": expired_refresh},
            )

            assert response.status_code == 401

        app.dependency_overrides.clear()

    def test_refresh_with_invalid_token_fails(self, seeded_db):
        """POST /api/v1/auth/refresh with invalid token → 401."""
        def override_get_db():
            try:
                yield seeded_db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": "totally-bogus-token"},
            )

            assert response.status_code == 401
            assert "Invalid" in response.json()["detail"]

        app.dependency_overrides.clear()

    def test_refresh_with_access_token_fails(self, seeded_db, test_tenant_id):
        """POST /api/v1/auth/refresh with access token instead of refresh → 401."""
        def override_get_db():
            try:
                yield seeded_db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db

        # Create access token (not a refresh token)
        access_token = create_test_token(
            user_id="user-123",
            roles=["user"],
            tenant_ids=[test_tenant_id],
        )

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": access_token},
            )

            # Should fail because token type is "access" not "refresh"
            assert response.status_code == 401
            assert "Invalid token type" in response.json()["detail"]

        app.dependency_overrides.clear()

    def test_token_endpoint_with_refresh_grant_type(self, seeded_db, test_tenant_id):
        """POST /api/v1/auth/token with grant_type=refresh_token works."""
        def override_get_db():
            try:
                yield seeded_db
            finally:
                pass

        # Create user-tenant mapping
        user_tenant = UserTenant(
            id="mapping-token-refresh",
            user_id="user-token-123",
            tenant_id=test_tenant_id,
            role="admin",
            is_active=True,
        )
        seeded_db.add(user_tenant)
        seeded_db.commit()

        app.dependency_overrides[get_db] = override_get_db

        refresh_token = create_test_refresh_token(user_id="user-token-123")

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/auth/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                },
            )

            assert response.status_code == 200
            token_data = response.json()
            assert "access_token" in token_data
            assert "refresh_token" in token_data

        app.dependency_overrides.clear()

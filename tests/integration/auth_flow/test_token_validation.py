"""Integration tests for JWT token validation.

Tests various token validation scenarios:
- Valid tokens granting access
- Invalid/malformed tokens denying access
- Expired tokens denying access
- Missing tokens denying access
"""

from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from tests.integration.auth_flow.conftest import create_test_token


class TestTokenValidation:
    """Integration tests for token validation."""

    def test_valid_token_grants_access(self, seeded_db, test_tenant_id):
        """Valid token → access granted (200)."""
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

        with TestClient(app) as client:
            response = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {valid_token}"},
            )

            assert response.status_code == 200
            user_info = response.json()
            assert user_info["id"] == "user-123"

        app.dependency_overrides.clear()

    def test_invalid_token_denies_access(self, seeded_db):
        """Invalid token → access denied (401)."""
        def override_get_db():
            try:
                yield seeded_db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as client:
            response = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer invalid-garbage-token"},
            )

            assert response.status_code == 401
            # The error message can vary, just ensure it's an auth error
            assert "detail" in response.json()

        app.dependency_overrides.clear()

    def test_expired_token_denies_access(self, seeded_db):
        """Expired token → access denied (401)."""
        def override_get_db():
            try:
                yield seeded_db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db

        # Create expired token
        expired_token = create_test_token(
            user_id="user-123",
            expired=True,
        )

        with TestClient(app) as client:
            response = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {expired_token}"},
            )

            assert response.status_code == 401
            assert "expired" in response.json()["detail"].lower()

        app.dependency_overrides.clear()

    def test_missing_token_denies_access(self, seeded_db):
        """No token → access denied (401)."""
        def override_get_db():
            try:
                yield seeded_db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as client:
            response = client.get("/api/v1/auth/me")

            # Without auth, FastAPI returns 401 for protected endpoints
            assert response.status_code == 401

        app.dependency_overrides.clear()

    def test_malformed_authorization_header(self, seeded_db):
        """Malformed Authorization header → 401."""
        def override_get_db():
            try:
                yield seeded_db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app) as client:
            # Test without "Bearer" prefix
            response = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "NotBearer token123"},
            )

            assert response.status_code == 401

        app.dependency_overrides.clear()

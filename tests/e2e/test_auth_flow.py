"""E2E tests for authentication flows.

Tests login, token lifecycle, user info, and logout via Playwright
against the real FastAPI server.

IMPORTANT: The login endpoint returns tokens in HttpOnly Set-Cookie
headers, NOT in the JSON response body. Tests must check cookies.
"""

import httpx as _httpx
import pytest
from playwright.sync_api import APIRequestContext


class TestLoginAPI:
    """Test the login API endpoint directly.

    Uses httpx directly (not the shared Playwright unauth_api_context)
    to avoid cookie leakage — Playwright APIRequestContext auto-stores
    Set-Cookie headers, which would make subsequent "unauthenticated"
    tests fail (they'd have the access_token cookie).
    """

    def test_successful_login_returns_cookies(self, base_url: str):
        """POST /api/v1/auth/login with valid creds sets HttpOnly token cookies."""
        resp = _httpx.post(
            f"{base_url}/api/v1/auth/login",
            data={"username": "admin", "password": "admin"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        assert resp.status_code == 200
        data = resp.json()

        # Tokens are in HttpOnly cookies, NOT in the JSON body
        assert data.get("cookies_set") is True
        assert data["token_type"] == "bearer"
        assert isinstance(data["expires_in"], int)
        assert data["expires_in"] > 0

        # Verify tokens are in Set-Cookie headers
        cookie_names = [c.name for c in resp.cookies.jar]
        assert "access_token" in cookie_names, f"No access_token cookie; got: {cookie_names}"
        assert "refresh_token" in cookie_names, f"No refresh_token cookie; got: {cookie_names}"

    def test_invalid_password_returns_401(self, unauth_api_context: APIRequestContext):
        """POST /api/v1/auth/login with wrong password returns 401."""
        resp = unauth_api_context.post(
            "/api/v1/auth/login",
            form={
                "username": "admin",
                "password": "wrongpassword",
            },
        )
        assert resp.status == 401

    def test_empty_credentials_returns_error(self, unauth_api_context: APIRequestContext):
        """POST /api/v1/auth/login with empty form returns 401 or 422."""
        resp = unauth_api_context.post(
            "/api/v1/auth/login",
            form={
                "username": "",
                "password": "",
            },
        )
        assert resp.status in (401, 422)

    def test_unknown_user_returns_401(self, unauth_api_context: APIRequestContext):
        """POST /api/v1/auth/login with unknown user returns 401."""
        resp = unauth_api_context.post(
            "/api/v1/auth/login",
            form={
                "username": "nonexistent",
                "password": "whatever",
            },
        )
        assert resp.status == 401


class TestTokenAccess:
    """Test that tokens grant/deny access correctly."""

    def test_valid_token_accesses_me(self, api_context: APIRequestContext):
        """GET /api/v1/auth/me with valid token returns user info."""
        resp = api_context.get("/api/v1/auth/me")
        assert resp.status == 200
        data = resp.json()
        assert "id" in data or "user_id" in data or "sub" in data
        assert "roles" in data

    def test_no_token_returns_401(self, base_url: str):
        """GET /api/v1/auth/me without token returns 401.

        Uses httpx directly to ensure no cookies leak from Playwright context.
        """
        resp = _httpx.get(f"{base_url}/api/v1/auth/me", timeout=10)
        assert resp.status_code in (401, 403)

    def test_invalid_token_returns_401(self, unauth_api_context: APIRequestContext):
        """GET /api/v1/auth/me with garbage token returns 401."""
        resp = unauth_api_context.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.garbage.token"},
        )
        assert resp.status in (401, 403)

    def test_user_info_has_expected_fields(self, api_context: APIRequestContext):
        """GET /api/v1/auth/me response has id, roles, tenant_ids."""
        resp = api_context.get("/api/v1/auth/me")
        assert resp.status == 200
        data = resp.json()
        # The user info should have roles and some identifier
        assert "roles" in data
        assert isinstance(data["roles"], list)

    def test_user_tenants_endpoint(self, api_context: APIRequestContext):
        """GET /api/v1/auth/me/tenants returns tenant list."""
        resp = api_context.get("/api/v1/auth/me/tenants")
        # May return 200 with list or 404 if not implemented
        assert resp.status in (200, 404)
        if resp.status == 200:
            data = resp.json()
            assert isinstance(data, list | dict)


class TestTokenRefresh:
    """Test token refresh flow."""

    def test_refresh_token_grants_new_access_token(
        self,
        base_url: str,
        auth_tokens: dict,
    ):
        """POST /api/v1/auth/token with refresh_token grant returns new tokens.

        Uses httpx to avoid polluting shared Playwright contexts with cookies.
        """
        resp = _httpx.post(
            f"{base_url}/api/v1/auth/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": auth_tokens["refresh_token"],
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        assert resp.status_code == 200

        # New tokens come back as Set-Cookie
        cookie_names = [c.name for c in resp.cookies.jar]
        assert "access_token" in cookie_names

    def test_invalid_refresh_token_returns_401(self, unauth_api_context: APIRequestContext):
        """POST /api/v1/auth/token with bad refresh token returns 401."""
        resp = unauth_api_context.post(
            "/api/v1/auth/token",
            form={
                "grant_type": "refresh_token",
                "refresh_token": "invalid.refresh.token",
            },
        )
        assert resp.status in (401, 400)

    def test_unsupported_grant_type_returns_400(self, unauth_api_context: APIRequestContext):
        """POST /api/v1/auth/token with unsupported grant type returns 400."""
        resp = unauth_api_context.post(
            "/api/v1/auth/token",
            form={
                "grant_type": "client_credentials",
            },
        )
        assert resp.status == 400


class TestLogout:
    """Test logout/token invalidation."""

    def test_logout_returns_success(self, base_url: str, auth_token: str):
        """POST /api/v1/auth/logout invalidates the token."""
        # Use the session-scoped token to verify auth works
        me_resp = _httpx.get(
            f"{base_url}/api/v1/auth/me",
            headers={"Authorization": f"Bearer {auth_token}"},
            timeout=10,
        )
        assert me_resp.status_code == 200

        # Get a fresh token for logout so we don't invalidate the shared one
        import time

        time.sleep(1)  # Brief pause to avoid rate limiting
        login_resp = _httpx.post(
            f"{base_url}/api/v1/auth/login",
            data={"username": "admin", "password": "admin"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        if login_resp.status_code == 429:
            pytest.skip("Rate limited — cannot acquire fresh token for logout test")
        assert login_resp.status_code == 200

        # Extract fresh token from Set-Cookie
        fresh_token = None
        for cookie in login_resp.cookies.jar:
            if cookie.name == "access_token":
                fresh_token = cookie.value
                break
        assert fresh_token, "No access_token cookie in login response"

        # Logout with the fresh token
        logout_resp = _httpx.post(
            f"{base_url}/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {fresh_token}"},
            timeout=10,
        )
        assert logout_resp.status_code == 200

    def test_logout_without_auth_returns_error(self, base_url: str):
        """POST /api/v1/auth/logout without auth returns 401.

        Uses httpx directly to ensure no cookies leak from Playwright context.
        """
        resp = _httpx.post(f"{base_url}/api/v1/auth/logout", timeout=10)
        assert resp.status_code in (401, 403)

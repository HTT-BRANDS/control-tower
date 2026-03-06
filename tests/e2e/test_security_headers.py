"""E2E tests for security response headers."""

import pytest
from playwright.sync_api import APIRequestContext


class TestSecurityHeaders:
    """Verify security headers on various endpoints."""

    @pytest.mark.parametrize(
        "path",
        [
            "/health",
            "/health/detailed",
            "/api/v1/status",
        ],
    )
    def test_x_frame_options(self, unauth_api_context: APIRequestContext, path: str):
        resp = unauth_api_context.get(path)
        assert resp.headers.get("x-frame-options") == "DENY"

    @pytest.mark.parametrize(
        "path",
        [
            "/health",
            "/health/detailed",
            "/api/v1/status",
        ],
    )
    def test_x_content_type_options(self, unauth_api_context: APIRequestContext, path: str):
        resp = unauth_api_context.get(path)
        assert resp.headers.get("x-content-type-options") == "nosniff"

    @pytest.mark.parametrize(
        "path",
        [
            "/health",
            "/health/detailed",
        ],
    )
    def test_xss_protection(self, unauth_api_context: APIRequestContext, path: str):
        resp = unauth_api_context.get(path)
        assert resp.headers.get("x-xss-protection") == "1; mode=block"

    @pytest.mark.parametrize(
        "path",
        [
            "/health",
            "/health/detailed",
        ],
    )
    def test_referrer_policy(self, unauth_api_context: APIRequestContext, path: str):
        resp = unauth_api_context.get(path)
        assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    @pytest.mark.parametrize(
        "path",
        [
            "/health",
            "/health/detailed",
        ],
    )
    def test_permissions_policy(self, unauth_api_context: APIRequestContext, path: str):
        resp = unauth_api_context.get(path)
        pp = resp.headers.get("permissions-policy", "")
        assert "camera=()" in pp
        assert "microphone=()" in pp

    @pytest.mark.parametrize(
        "path",
        [
            "/health",
            "/health/detailed",
        ],
    )
    def test_content_security_policy(self, unauth_api_context: APIRequestContext, path: str):
        resp = unauth_api_context.get(path)
        csp = resp.headers.get("content-security-policy", "")
        assert "default-src" in csp

    def test_no_hsts_in_development(self, unauth_api_context: APIRequestContext):
        """HSTS should NOT be set in development mode."""
        resp = unauth_api_context.get("/health")
        assert resp.headers.get("strict-transport-security") is None

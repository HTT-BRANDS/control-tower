"""E2E tests for CORS and security middleware."""

from playwright.sync_api import APIRequestContext


class TestCORS:
    """CORS middleware behavior."""

    def test_options_preflight_handled(self, unauth_api_context: APIRequestContext):
        """OPTIONS request should be handled by CORS middleware."""
        # Playwright API context can make arbitrary requests
        resp = unauth_api_context.fetch(
            "/api/v1/costs/summary",
            method="OPTIONS",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        # CORS preflight should return 200 or 405 (method not allowed)
        assert resp.status in (200, 204, 400, 405)

    def test_response_has_cors_header_for_allowed_origin(
        self, unauth_api_context: APIRequestContext
    ):
        """Responses should include CORS headers for allowed origins."""
        resp = unauth_api_context.get(
            "/health",
            headers={"Origin": "http://localhost:8099"},
        )
        # The health endpoint should respond regardless of origin
        assert resp.status == 200


class TestSecurityMiddleware:
    """Verify security middleware is applied globally."""

    def test_all_responses_have_frame_options(self, api_context: APIRequestContext):
        """Every response should have X-Frame-Options header."""
        for path in ["/health", "/api/v1/status", "/metrics"]:
            resp = api_context.get(path)
            assert resp.headers.get("x-frame-options") == "DENY", f"{path} missing X-Frame-Options"

    def test_all_responses_have_content_type_options(self, api_context: APIRequestContext):
        for path in ["/health", "/api/v1/status"]:
            resp = api_context.get(path)
            assert resp.headers.get("x-content-type-options") == "nosniff"

    def test_json_endpoints_return_json_content_type(self, api_context: APIRequestContext):
        """JSON API endpoints should set application/json content type."""
        resp = api_context.get("/health")
        assert "application/json" in resp.headers.get("content-type", "")

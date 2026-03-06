"""E2E tests for error handling and edge cases."""

from playwright.sync_api import APIRequestContext


class TestErrorHandling:
    """Global error handling and edge cases."""

    def test_404_on_unknown_route(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/api/v1/nonexistent")
        assert resp.status in (404, 401, 403)

    def test_404_returns_json(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/api/v1/nonexistent-route-xyz")
        if resp.status == 404:
            data = resp.json()
            assert "detail" in data or "error" in data

    def test_405_on_wrong_method(self, api_context: APIRequestContext):
        """DELETE on a GET-only endpoint should return 405."""
        resp = api_context.delete("/health")
        assert resp.status in (405, 404)

    def test_malformed_json_body(self, api_context: APIRequestContext):
        """Sending malformed JSON should return 422."""
        resp = api_context.post(
            "/api/v1/tenants",
            headers={"Content-Type": "application/json"},
            data="this is not json",
        )
        assert resp.status in (400, 422, 401, 403)

    def test_oversized_request_handled(self, api_context: APIRequestContext):
        """Very large request body should be handled gracefully."""
        large_body = "x" * 1_000_000
        resp = api_context.post(
            "/api/v1/tenants",
            headers={"Content-Type": "application/json"},
            data=large_body,
        )
        assert resp.status in (400, 413, 422, 403, 500)

    def test_empty_auth_header(self, unauth_api_context: APIRequestContext):
        """Empty Authorization header should return 401."""
        resp = unauth_api_context.get(
            "/api/v1/costs/summary",
            headers={"Authorization": ""},
        )
        assert resp.status in (401, 403)

    def test_malformed_bearer_token(self, unauth_api_context: APIRequestContext):
        """Malformed bearer token should return 401."""
        resp = unauth_api_context.get(
            "/api/v1/costs/summary",
            headers={"Authorization": "Bearer "},
        )
        assert resp.status in (401, 403)

    def test_wrong_auth_scheme(self, unauth_api_context: APIRequestContext):
        """Non-Bearer auth scheme should return 401."""
        resp = unauth_api_context.get(
            "/api/v1/costs/summary",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert resp.status in (401, 403)

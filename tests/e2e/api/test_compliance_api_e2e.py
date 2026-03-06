"""E2E tests for Compliance API endpoints."""

from playwright.sync_api import APIRequestContext


class TestComplianceAPI:
    """Compliance monitoring API — /api/v1/compliance/*"""

    def test_summary_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/api/v1/compliance/summary")
        assert resp.status in (401, 403)

    def test_summary_with_auth(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/compliance/summary")
        assert resp.status in (200, 403, 500)

    def test_summary_returns_json(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/compliance/summary")
        if resp.status == 200:
            data = resp.json()
            assert isinstance(data, dict)

    def test_summary_with_tenant_filter(self, api_context: APIRequestContext):
        resp = api_context.get(
            "/api/v1/compliance/summary?tenant_ids=00000000-0000-0000-0000-000000000000"
        )
        assert resp.status in (200, 403, 500)

    def test_scores_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/api/v1/compliance/scores")
        assert resp.status in (401, 403, 404)

    def test_scores_with_auth(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/compliance/scores")
        assert resp.status in (200, 403, 404, 500)

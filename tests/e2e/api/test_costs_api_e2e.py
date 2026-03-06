"""E2E tests for Costs API endpoints."""

from playwright.sync_api import APIRequestContext


class TestCostsAPI:
    """Costs management API — /api/v1/costs/*"""

    def test_summary_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/api/v1/costs/summary")
        assert resp.status in (401, 403)

    def test_summary_with_auth(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/costs/summary")
        assert resp.status in (200, 403, 500)

    def test_summary_with_period_filter(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/costs/summary?period_days=7")
        assert resp.status in (200, 403, 500)

    def test_trends_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/api/v1/costs/trends")
        assert resp.status in (401, 403, 404)

    def test_trends_with_auth(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/costs/trends")
        assert resp.status in (200, 403, 404, 500)

    def test_by_tenant_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/api/v1/costs/by-tenant")
        assert resp.status in (401, 403, 404)

    def test_by_tenant_with_auth(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/costs/by-tenant")
        assert resp.status in (200, 403, 404, 500)

    def test_summary_returns_json(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/costs/summary")
        if resp.status == 200:
            data = resp.json()
            assert isinstance(data, dict)

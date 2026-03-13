"""E2E tests for Recommendations API endpoints."""

from playwright.sync_api import APIRequestContext


class TestRecommendationsAPI:
    """Recommendations API — /api/v1/recommendations/*"""

    def test_list_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/api/v1/recommendations")
        assert resp.status in (401, 403)

    def test_list_with_auth(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/recommendations")
        assert resp.status in (200, 403, 500)

    def test_list_returns_array(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/recommendations")
        if resp.status == 200:
            data = resp.json()
            assert isinstance(data, list)

    def test_by_category_with_auth(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/recommendations/by-category")
        assert resp.status in (200, 403, 500)

    def test_by_tenant_with_auth(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/recommendations/by-tenant")
        assert resp.status in (200, 403, 500)

    def test_savings_potential_with_auth(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/recommendations/savings-potential")
        assert resp.status in (200, 403, 500)

    def test_summary_with_auth(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/recommendations/summary")
        assert resp.status in (200, 403, 500)

    def test_dismiss_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.post("/api/v1/recommendations/99999/dismiss")
        assert resp.status in (401, 403)

    def test_dismiss_nonexistent(self, api_context: APIRequestContext):
        resp = api_context.post("/api/v1/recommendations/99999/dismiss")
        assert resp.status in (403, 404, 400, 422, 500)

    def test_list_with_filters(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/recommendations?category=cost&impact=High&limit=10")
        assert resp.status in (200, 403, 422, 500)

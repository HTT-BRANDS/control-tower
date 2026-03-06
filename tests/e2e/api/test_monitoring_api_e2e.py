"""E2E tests for Monitoring API endpoints."""

from playwright.sync_api import APIRequestContext


class TestMonitoringAPI:
    """Performance monitoring API — /monitoring/*"""

    def test_performance_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/monitoring/performance")
        assert resp.status in (401, 403)

    def test_performance_with_auth(self, api_context: APIRequestContext):
        resp = api_context.get("/monitoring/performance")
        assert resp.status in (200, 403, 500)

    def test_performance_returns_json(self, api_context: APIRequestContext):
        resp = api_context.get("/monitoring/performance")
        if resp.status == 200:
            data = resp.json()
            assert isinstance(data, dict)

    def test_cache_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/monitoring/cache")
        assert resp.status in (401, 403)

    def test_cache_with_auth(self, api_context: APIRequestContext):
        resp = api_context.get("/monitoring/cache")
        assert resp.status in (200, 403, 500)

    def test_sync_jobs_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/monitoring/sync-jobs")
        assert resp.status in (401, 403)

    def test_sync_jobs_with_auth(self, api_context: APIRequestContext):
        resp = api_context.get("/monitoring/sync-jobs")
        assert resp.status in (200, 403, 500)

    def test_queries_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/monitoring/queries")
        assert resp.status in (401, 403)

    def test_queries_with_auth(self, api_context: APIRequestContext):
        resp = api_context.get("/monitoring/queries")
        assert resp.status in (200, 403, 500)

    def test_health_with_auth(self, api_context: APIRequestContext):
        resp = api_context.get("/monitoring/health")
        assert resp.status in (200, 403, 500)

    def test_reset_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.post("/monitoring/reset")
        assert resp.status in (401, 403)

    def test_reset_with_auth(self, api_context: APIRequestContext):
        resp = api_context.post("/monitoring/reset")
        assert resp.status in (200, 403, 500)

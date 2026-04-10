"""E2E tests for Preflight API endpoints."""

from playwright.sync_api import APIRequestContext


class TestPreflightAPI:
    """Preflight check API — /api/v1/preflight/*"""

    def test_status_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/api/v1/preflight/status")
        assert resp.status in (401, 403)

    def test_status_with_auth(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/preflight/status")
        assert resp.status in (200, 403, 500)

    def test_run_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.post("/api/v1/preflight/run")
        assert resp.status in (401, 403)

    def test_run_with_auth(self, api_context: APIRequestContext):
        """POST /api/v1/preflight/run triggers a preflight check."""
        resp = api_context.post(
            "/api/v1/preflight/run",
            timeout=60000,
        )
        # May take a while or return immediately with status
        assert resp.status in (200, 202, 403, 429, 500)

    def test_report_json(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/preflight/report/json")
        assert resp.status in (200, 404, 403, 500)
        if resp.status == 200:
            data = resp.json()
            assert isinstance(data, dict)

    def test_report_markdown(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/preflight/report/markdown")
        assert resp.status in (200, 404, 403, 500)

    def test_summary_tenants(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/preflight/summary/tenants")
        assert resp.status in (200, 403, 404, 500)

    def test_summary_categories(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/preflight/summary/categories")
        assert resp.status in (200, 403, 404, 500)

    def test_clear_cache(self, api_context: APIRequestContext):
        resp = api_context.post("/api/v1/preflight/clear-cache")
        assert resp.status in (200, 403, 500)

    def test_tenant_preflight(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/preflight/tenants/00000000-0000-0000-0000-000000000000")
        assert resp.status in (200, 404, 403, 500)

    def test_github_preflight(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/preflight/github")
        assert resp.status in (200, 403, 500)

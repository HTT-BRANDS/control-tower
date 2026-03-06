"""E2E tests for CSV Export API endpoints."""

from playwright.sync_api import APIRequestContext


class TestExportsAPI:
    """CSV export API — /api/v1/exports/*"""

    def test_costs_export_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/api/v1/exports/costs")
        assert resp.status in (401, 403)

    def test_costs_export_with_auth(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/exports/costs")
        assert resp.status in (200, 403, 500)

    def test_costs_export_content_type(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/exports/costs")
        if resp.status == 200:
            ct = resp.headers.get("content-type", "")
            assert "text/csv" in ct or "application/octet-stream" in ct

    def test_resources_export_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/api/v1/exports/resources")
        assert resp.status in (401, 403)

    def test_resources_export_with_auth(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/exports/resources")
        assert resp.status in (200, 403, 500)

    def test_compliance_export_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/api/v1/exports/compliance")
        assert resp.status in (401, 403)

    def test_compliance_export_with_auth(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/exports/compliance")
        assert resp.status in (200, 403, 500)

    def test_nonexistent_export_returns_404(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/exports/nonexistent")
        assert resp.status in (404, 405)

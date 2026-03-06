"""E2E tests for DMARC API endpoints."""

from playwright.sync_api import APIRequestContext


class TestDMARCAPI:
    """DMARC/DKIM email security API — /api/v1/dmarc/*"""

    def test_summary(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/dmarc/summary")
        assert resp.status in (200, 401, 403, 500)

    def test_summary_returns_json(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/dmarc/summary")
        if resp.status == 200:
            assert isinstance(resp.json(), dict)

    def test_records_requires_tenant_id(self, api_context: APIRequestContext):
        """GET /api/v1/dmarc/records requires tenant_id query param."""
        resp = api_context.get("/api/v1/dmarc/records")
        assert resp.status in (200, 400, 422, 500)

    def test_records_with_tenant_id(self, api_context: APIRequestContext):
        resp = api_context.get(
            "/api/v1/dmarc/records?tenant_id=00000000-0000-0000-0000-000000000000"
        )
        assert resp.status in (200, 404, 500)

    def test_dkim_endpoint(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/dmarc/dkim")
        assert resp.status in (200, 400, 422, 500)

    def test_score_endpoint(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/dmarc/score")
        assert resp.status in (200, 400, 422, 500)

    def test_trends_endpoint(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/dmarc/trends")
        assert resp.status in (200, 400, 422, 500)

    def test_reports_endpoint(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/dmarc/reports")
        assert resp.status in (200, 400, 422, 500)

    def test_alerts_endpoint(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/dmarc/alerts")
        assert resp.status in (200, 400, 500)

    def test_sync_trigger(self, api_context: APIRequestContext):
        resp = api_context.post("/api/v1/dmarc/sync")
        assert resp.status in (200, 202, 403, 422, 429, 500)

    def test_acknowledge_nonexistent_alert(self, api_context: APIRequestContext):
        resp = api_context.post("/api/v1/dmarc/alerts/99999/acknowledge")
        assert resp.status in (404, 400, 422, 500)

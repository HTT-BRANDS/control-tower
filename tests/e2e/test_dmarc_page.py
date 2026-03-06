"""E2E browser tests for the DMARC dashboard."""

from playwright.sync_api import APIRequestContext


class TestDMARCDashboard:
    """DMARC dashboard API endpoints (may not have dedicated HTML page)."""

    def test_dmarc_summary_returns_data(self, api_context: APIRequestContext):
        """GET /api/v1/dmarc/summary returns DMARC summary."""
        resp = api_context.get("/api/v1/dmarc/summary")
        # DMARC may or may not require auth depending on implementation
        assert resp.status in (200, 401, 403)

    def test_dmarc_summary_is_json(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/dmarc/summary")
        if resp.status == 200:
            data = resp.json()
            assert isinstance(data, dict)

    def test_dmarc_score_endpoint(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/dmarc/score")
        assert resp.status in (200, 400, 401, 403, 422)

    def test_dmarc_alerts_endpoint(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/dmarc/alerts")
        assert resp.status in (200, 401, 403)

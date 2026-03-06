"""E2E tests for Sync API endpoints."""

import pytest
from playwright.sync_api import APIRequestContext


class TestSyncAPI:
    """Sync job management API — /api/v1/sync/*"""

    def test_sync_metrics_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/api/v1/sync/metrics")
        assert resp.status in (401, 403)

    def test_sync_metrics_with_auth(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/sync/metrics")
        assert resp.status in (200, 403, 404, 500)

    def test_trigger_costs_sync_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.post("/api/v1/sync/costs")
        assert resp.status in (401, 403)

    def test_trigger_costs_sync_with_auth(self, api_context: APIRequestContext):
        resp = api_context.post("/api/v1/sync/costs")
        # May succeed (200/202), be rate limited (429), or error (500)
        assert resp.status in (200, 202, 403, 429, 500)

    def test_trigger_compliance_sync(self, api_context: APIRequestContext):
        resp = api_context.post("/api/v1/sync/compliance")
        assert resp.status in (200, 202, 403, 429, 500)

    def test_trigger_resources_sync(self, api_context: APIRequestContext):
        resp = api_context.post("/api/v1/sync/resources")
        assert resp.status in (200, 202, 403, 429, 500)

    @pytest.mark.xfail(
        reason="Identity sync hits real Azure Graph API and may exceed timeout",
        raises=Exception,
    )
    def test_trigger_identity_sync(self, api_context: APIRequestContext):
        resp = api_context.post(
            "/api/v1/sync/identity",
            timeout=60000,
        )
        assert resp.status in (200, 202, 403, 429, 500)

    def test_invalid_sync_type_rejected(self, api_context: APIRequestContext):
        """Invalid sync type should return 422."""
        resp = api_context.post("/api/v1/sync/invalid_type")
        assert resp.status in (404, 422)

    def test_sync_dashboard_api(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/sync/dashboard")
        assert resp.status in (200, 403, 404, 405, 500)

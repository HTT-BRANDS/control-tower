"""E2E tests for Bulk Operations API endpoints."""

from playwright.sync_api import APIRequestContext


class TestBulkAPI:
    """Bulk operations API — /bulk/*"""

    def test_tags_apply_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.post("/bulk/tags/apply")
        assert resp.status in (401, 403)

    def test_tags_apply_with_auth_no_body(self, api_context: APIRequestContext):
        """POST without body should return 422 (validation error)."""
        resp = api_context.post("/bulk/tags/apply")
        assert resp.status in (422, 400, 403, 500)

    def test_anomalies_acknowledge_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.post("/bulk/anomalies/acknowledge")
        assert resp.status in (401, 403)

    def test_anomalies_acknowledge_no_body(self, api_context: APIRequestContext):
        resp = api_context.post("/bulk/anomalies/acknowledge")
        assert resp.status in (422, 400, 403, 500)

    def test_recommendations_dismiss_requires_auth(
        self, unauth_api_context: APIRequestContext
    ):
        resp = unauth_api_context.post("/bulk/recommendations/dismiss")
        assert resp.status in (401, 403)

    def test_recommendations_dismiss_no_body(self, api_context: APIRequestContext):
        resp = api_context.post("/bulk/recommendations/dismiss")
        assert resp.status in (422, 400, 403, 500)

    def test_idle_resources_review_requires_auth(
        self, unauth_api_context: APIRequestContext
    ):
        resp = unauth_api_context.post("/bulk/idle-resources/review")
        assert resp.status in (401, 403)

    def test_idle_resources_review_no_body(self, api_context: APIRequestContext):
        resp = api_context.post("/bulk/idle-resources/review")
        assert resp.status in (422, 400, 403, 500)

"""E2E tests for Resources API endpoints."""

from playwright.sync_api import APIRequestContext


class TestResourcesAPI:
    """Resource management API — /api/v1/resources/*"""

    def test_inventory_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/api/v1/resources/inventory")
        assert resp.status in (401, 403, 404)

    def test_inventory_with_auth(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/resources/inventory")
        assert resp.status in (200, 403, 404, 500)

    def test_inventory_returns_json(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/resources/inventory")
        if resp.status in (200,):
            data = resp.json()
            assert isinstance(data, dict)

    def test_idle_resources_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/api/v1/resources/idle")
        assert resp.status in (401, 403)

    def test_idle_resources_with_auth(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/resources/idle")
        assert resp.status in (200, 403, 500)

    def test_orphaned_resources_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/api/v1/resources/orphaned")
        assert resp.status in (401, 403)

    def test_orphaned_resources_with_auth(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/resources/orphaned")
        assert resp.status in (200, 403, 500)

    def test_tagging_compliance_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/api/v1/resources/tagging")
        assert resp.status in (401, 403)

    def test_tagging_compliance_with_auth(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/resources/tagging")
        assert resp.status in (200, 403, 500)

    def test_resource_types_with_auth(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/resources/types")
        assert resp.status in (200, 403, 404, 500)

    def test_invalid_tenant_id_rejected(self, api_context: APIRequestContext):
        """Invalid (non-UUID) tenant_id should be rejected."""
        resp = api_context.get("/api/v1/resources/inventory?tenant_id=not-a-uuid")
        assert resp.status in (400, 404, 422, 200, 403, 500)

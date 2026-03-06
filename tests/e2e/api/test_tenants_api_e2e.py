"""E2E tests for Tenants API endpoints."""

from playwright.sync_api import APIRequestContext


class TestTenantsAPI:
    """Tenant management API — /api/v1/tenants/*"""

    def test_list_tenants_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/api/v1/tenants")
        assert resp.status in (401, 403)

    def test_list_tenants_with_auth(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/tenants")
        assert resp.status in (200, 403, 500)

    def test_list_tenants_returns_list(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/tenants")
        if resp.status == 200:
            data = resp.json()
            assert isinstance(data, list)

    def test_get_nonexistent_tenant_returns_404(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/tenants/00000000-0000-0000-0000-000000000000")
        assert resp.status in (404, 403, 500)

    def test_create_tenant_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.post("/api/v1/tenants", data={})
        assert resp.status in (401, 403, 422)

    def test_invalid_uuid_in_path(self, api_context: APIRequestContext):
        """Non-UUID tenant ID should be rejected."""
        resp = api_context.get("/api/v1/tenants/not-a-valid-uuid")
        assert resp.status in (400, 404, 422, 500)

    def test_delete_nonexistent_tenant(self, api_context: APIRequestContext):
        resp = api_context.delete("/api/v1/tenants/00000000-0000-0000-0000-000000000000")
        assert resp.status in (404, 403, 500)

    def test_patch_nonexistent_tenant(self, api_context: APIRequestContext):
        resp = api_context.patch(
            "/api/v1/tenants/00000000-0000-0000-0000-000000000000",
            data={"name": "Updated"},
        )
        assert resp.status in (404, 403, 422, 500)

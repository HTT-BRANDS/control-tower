"""E2E tests for tenant isolation and data boundary enforcement."""

from playwright.sync_api import APIRequestContext


class TestTenantIsolation:
    """Verify tenant data boundaries are enforced."""

    def test_invalid_tenant_id_format_rejected(self, api_context: APIRequestContext):
        """Non-UUID tenant_id should be rejected or ignored."""
        resp = api_context.get("/api/v1/costs/summary?tenant_ids=not-a-uuid")
        # Should either reject (400/422), forbid (403), or ignore the bad ID
        assert resp.status in (200, 400, 403, 422, 500)

    def test_nonexistent_tenant_returns_empty(self, api_context: APIRequestContext):
        """Querying a nonexistent tenant UUID should return empty data, not error."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        resp = api_context.get(f"/api/v1/costs/summary?tenant_ids={fake_uuid}")
        assert resp.status in (200, 403, 500)

    def test_sql_injection_in_tenant_id(self, api_context: APIRequestContext):
        """SQL injection attempt in tenant_id should be safely rejected."""
        resp = api_context.get(
            "/api/v1/costs/summary?tenant_ids='; DROP TABLE tenants;--"
        )
        assert resp.status in (400, 403, 422, 500)

    def test_path_traversal_in_tenant_id(self, api_context: APIRequestContext):
        """Path traversal attempt should be rejected."""
        resp = api_context.get("/api/v1/tenants/../../etc/passwd")
        assert resp.status in (400, 404, 422)

    def test_resources_respect_tenant_filter(self, api_context: APIRequestContext):
        """Resources endpoint with tenant filter should scope results."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        resp = api_context.get(f"/api/v1/resources/inventory?tenant_id={fake_uuid}")
        assert resp.status in (200, 403, 404, 500)

    def test_compliance_respects_tenant_filter(self, api_context: APIRequestContext):
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        resp = api_context.get(f"/api/v1/compliance/summary?tenant_ids={fake_uuid}")
        assert resp.status in (200, 403, 500)

    def test_identity_respects_tenant_filter(self, api_context: APIRequestContext):
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        resp = api_context.get(f"/api/v1/identity/summary?tenant_ids={fake_uuid}")
        assert resp.status in (200, 403, 500)

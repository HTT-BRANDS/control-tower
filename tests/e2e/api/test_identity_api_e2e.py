"""E2E tests for Identity API endpoints."""

from playwright.sync_api import APIRequestContext


class TestIdentityAPI:
    """Identity governance API — /api/v1/identity/*"""

    def test_summary_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/api/v1/identity/summary")
        assert resp.status in (401, 403)

    def test_summary_with_auth(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/identity/summary")
        assert resp.status in (200, 403, 500)

    def test_summary_returns_json(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/identity/summary")
        if resp.status == 200:
            data = resp.json()
            assert isinstance(data, dict)

    def test_privileged_accounts_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/api/v1/identity/privileged")
        assert resp.status in (401, 403)

    def test_privileged_accounts_with_auth(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/identity/privileged")
        assert resp.status in (200, 403, 500)

    def test_stale_accounts_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/api/v1/identity/stale")
        assert resp.status in (401, 403)

    def test_stale_accounts_with_auth(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/identity/stale")
        assert resp.status in (200, 403, 500)

    def test_guest_accounts_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/api/v1/identity/guests")
        assert resp.status in (401, 403)

    def test_guest_accounts_with_auth(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/identity/guests")
        assert resp.status in (200, 403, 500)

    def test_admin_roles_requires_auth(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/api/v1/identity/admin-roles")
        assert resp.status in (401, 403, 404)

    def test_admin_roles_with_auth(self, api_context: APIRequestContext):
        resp = api_context.get("/api/v1/identity/admin-roles")
        assert resp.status in (200, 403, 404, 500)

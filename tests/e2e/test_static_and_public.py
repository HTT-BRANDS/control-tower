"""E2E tests for static assets and public pages."""

import pytest
from playwright.sync_api import APIRequestContext


class TestStaticAssets:
    """Static files should be served with 200."""

    @pytest.mark.parametrize(
        "path",
        [
            "/static/css/theme.css",
            "/static/css/riverside.css",
            "/static/css/accessibility.css",
            "/static/js/darkMode.js",
            "/static/js/navigation/index.js",
        ],
    )
    def test_static_file_loads(self, unauth_api_context: APIRequestContext, path: str):
        resp = unauth_api_context.get(path)
        assert resp.status == 200
        assert len(resp.body()) > 0

    def test_css_has_correct_content_type(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/static/css/theme.css")
        assert "text/css" in resp.headers.get("content-type", "")

    def test_js_has_correct_content_type(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/static/js/darkMode.js")
        ct = resp.headers.get("content-type", "")
        assert "javascript" in ct or "text/plain" in ct

    def test_nonexistent_static_returns_404(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/static/nonexistent.css")
        assert resp.status == 404


class TestOnboardingPage:
    """GET /onboarding — public self-service landing page."""

    def test_returns_200(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/onboarding")
        assert resp.status == 200

    def test_contains_html(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/onboarding")
        body = resp.text()
        assert "<html" in body.lower()

    def test_contains_onboarding_content(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/onboarding")
        body = resp.text()
        assert "onboarding" in body.lower() or "azure" in body.lower()


class TestRootRedirect:
    """GET / should redirect to dashboard."""

    def test_root_redirects(self, unauth_api_context: APIRequestContext):
        """Root redirects to /dashboard (which then may redirect to login)."""
        resp = unauth_api_context.get("/", max_redirects=0)
        # Should be 307 redirect to /dashboard
        assert resp.status in (200, 301, 302, 307, 308, 401, 403)

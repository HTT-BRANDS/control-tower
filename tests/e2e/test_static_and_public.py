"""E2E tests for static assets and public/canonical entry pages."""

from __future__ import annotations

import pytest
from playwright.sync_api import APIRequestContext


class TestStaticAssets:
    """Static files should match the current tokenized design-system bundle."""

    @pytest.mark.parametrize(
        ("path", "content_type", "required_snippet"),
        [
            ("/static/css/design-tokens.css", "text/css", "--"),
            ("/static/css/tailwind-output.css", "text/css", "tailwind"),
            ("/static/css/design-utilities.css", "text/css", "skip-link"),
            ("/static/js/darkMode.js", "javascript", "dark"),
            ("/static/js/mobileMenu.js", "javascript", "mobile"),
            ("/static/js/ds-tabs.js", "javascript", "tab"),
            ("/static/js/navigation/navigation.bundle.js", "javascript", "Navigation"),
            ("/static/favicon.svg", "image/svg+xml", "<svg"),
        ],
    )
    def test_static_file_loads_with_expected_contract(
        self,
        unauth_api_context: APIRequestContext,
        path: str,
        content_type: str,
        required_snippet: str,
    ):
        resp = unauth_api_context.get(path)
        assert resp.status == 200, f"{path} returned {resp.status}"
        assert len(resp.body()) > 0, f"{path} was empty"
        assert content_type in resp.headers.get("content-type", "").lower(), path
        assert required_snippet.lower() in resp.text().lower(), path

    @pytest.mark.parametrize(
        "stale_path",
        [
            "/static/css/theme.css",
            "/static/css/riverside.css",
            "/static/css/accessibility.css",
        ],
    )
    def test_removed_legacy_css_is_not_part_of_contract(
        self, unauth_api_context: APIRequestContext, stale_path: str
    ):
        resp = unauth_api_context.get(stale_path)
        assert resp.status == 404

    def test_nonexistent_static_returns_404(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/static/nonexistent.css")
        assert resp.status == 404


class TestCanonicalLoginPage:
    """Public entry route contracts."""

    def test_legacy_login_redirects_to_canonical_login(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/login?next=/dashboard", max_redirects=0)
        assert resp.status == 301
        assert resp.headers["location"] == "/auth/login?next=/dashboard"

    def test_canonical_login_returns_html(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/auth/login")
        assert resp.status == 200
        assert "text/html" in resp.headers.get("content-type", "").lower()
        body = resp.text().lower()
        assert "<html" in body
        assert "sign in with microsoft" in body
        assert 'data-testid="login-shell"' in body


class TestRootRedirect:
    """GET / should send users toward the authenticated app shell."""

    def test_root_redirects(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/", max_redirects=0)
        assert resp.status in (301, 302, 307, 308)
        assert resp.headers.get("location") in {"/dashboard", "/auth/login", "/login"}

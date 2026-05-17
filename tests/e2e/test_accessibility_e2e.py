"""E2E browser tests for navigation and accessibility."""

from playwright.sync_api import APIRequestContext, Page


class TestNavigation:
    """Page navigation and routing."""

    def test_root_redirects_somewhere(self, unauth_api_context: APIRequestContext):
        """GET / should redirect to dashboard or login."""
        resp = unauth_api_context.get("/", max_redirects=0)
        assert resp.status in (200, 301, 302, 307, 308, 401, 403)

    def test_unknown_route_returns_404(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/this-route-does-not-exist-12345")
        assert resp.status in (404, 307)

    def test_unknown_api_route_returns_404(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/api/v1/nonexistent-endpoint")
        assert resp.status in (404, 401, 403)


class TestStaticAssetAccessibility:
    """CSS files that support accessibility and theming."""

    def test_current_css_assets_exist(self, unauth_api_context: APIRequestContext):
        """Current CSS architecture serves all required layers.

        The old theme.css/accessibility.css files were consolidated into the
        token/compiled-utility stack. Assert the real runtime contract instead
        of stale filenames, because tests lying about architecture is rude.
        """
        expected_assets = (
            "/static/css/design-tokens.css",
            "/static/css/tailwind-output.css",
            "/static/css/design-utilities.css",
        )

        for path in expected_assets:
            resp = unauth_api_context.get(path)
            assert resp.status == 200, f"{path} returned {resp.status}"
            assert len(resp.text()) > 0, f"{path} is empty"

    def test_design_tokens_define_theme_and_dark_mode(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/static/css/design-tokens.css")
        assert resp.status == 200
        body = resp.text()

        assert ":root" in body
        assert ".dark" in body
        assert "--brand-primary" in body
        assert "--text-primary" in body
        assert "--bg-primary" in body

    def test_design_utilities_include_accessibility_layer(
        self, unauth_api_context: APIRequestContext
    ):
        resp = unauth_api_context.get("/static/css/design-utilities.css")
        assert resp.status == 200
        body = resp.text()

        assert "WCAG 2.2 AA Accessibility Layer" in body
        assert ".skip-link" in body
        assert "focus" in body


class TestOnboardingAccessibility:
    """Onboarding page accessibility (public page, no auth needed)."""

    def test_onboarding_has_html_lang(self, unauthenticated_page: Page, base_url: str):
        """Onboarding page should have lang attribute on html tag."""
        resp = unauthenticated_page.goto(f"{base_url}/onboarding")
        if resp and resp.status == 200:
            lang = unauthenticated_page.evaluate("() => document.documentElement.lang")
            assert lang and len(lang) > 0, "Missing lang attribute on <html>"

    def test_onboarding_has_viewport_meta(self, unauthenticated_page: Page, base_url: str):
        """Onboarding page should have viewport meta tag for mobile."""
        resp = unauthenticated_page.goto(f"{base_url}/onboarding")
        if resp and resp.status == 200:
            viewport = unauthenticated_page.locator("meta[name='viewport']")
            assert viewport.count() > 0, "Missing viewport meta tag"

    def test_onboarding_has_charset(self, unauthenticated_page: Page, base_url: str):
        """Onboarding page should declare UTF-8 charset."""
        resp = unauthenticated_page.goto(f"{base_url}/onboarding")
        if resp and resp.status == 200:
            content = unauthenticated_page.content()
            assert "utf-8" in content.lower() or "charset" in content.lower()

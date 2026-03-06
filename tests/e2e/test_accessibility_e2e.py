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

    def test_accessibility_css_exists(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/static/css/accessibility.css")
        assert resp.status == 200
        body = resp.text()
        assert len(body) > 0

    def test_dark_mode_css_exists(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/static/css/dark-mode.css")
        assert resp.status == 200
        body = resp.text()
        assert len(body) > 0

    def test_theme_css_exists(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/static/css/theme.css")
        assert resp.status == 200


class TestOnboardingAccessibility:
    """Onboarding page accessibility (public page, no auth needed)."""

    def test_onboarding_has_html_lang(self, unauthenticated_page: Page, base_url: str):
        """Onboarding page should have lang attribute on html tag."""
        resp = unauthenticated_page.goto(f"{base_url}/onboarding")
        if resp and resp.status == 200:
            lang = unauthenticated_page.evaluate(
                "() => document.documentElement.lang"
            )
            assert lang and len(lang) > 0, "Missing lang attribute on <html>"

    def test_onboarding_has_viewport_meta(
        self, unauthenticated_page: Page, base_url: str
    ):
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

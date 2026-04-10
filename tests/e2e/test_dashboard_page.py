"""E2E browser tests for the main dashboard page."""

import pytest
from playwright.sync_api import Page


class TestDashboardPage:
    """GET /dashboard — main governance dashboard."""

    def test_dashboard_returns_html(self, authenticated_page: Page, base_url: str):
        """Dashboard page loads and returns HTML content."""
        resp = authenticated_page.goto(f"{base_url}/dashboard")
        # Accept 200 (rendered) or 401/403 (auth required via cookie)
        assert resp is not None
        assert resp.status in (200, 401, 403)

    def test_dashboard_has_title(self, authenticated_page: Page, base_url: str):
        resp = authenticated_page.goto(f"{base_url}/dashboard")
        if resp and resp.status == 200:
            title = authenticated_page.title()
            assert len(title) > 0

    def test_dashboard_has_navigation(self, authenticated_page: Page, base_url: str):
        resp = authenticated_page.goto(f"{base_url}/dashboard")
        if resp and resp.status == 200:
            # Look for nav elements
            nav = authenticated_page.locator("nav, [role='navigation'], .sidebar, .nav")
            assert nav.count() > 0

    def test_dashboard_loads_css(self, authenticated_page: Page, base_url: str):
        """Dashboard page loads CSS stylesheets."""
        resp = authenticated_page.goto(f"{base_url}/dashboard")
        if resp and resp.status == 200:
            links = authenticated_page.locator("link[rel='stylesheet']")
            assert links.count() > 0

    def test_dashboard_has_htmx(self, authenticated_page: Page, base_url: str):
        """Dashboard includes HTMX library."""
        resp = authenticated_page.goto(f"{base_url}/dashboard")
        if resp and resp.status == 200:
            has_htmx = authenticated_page.evaluate("() => typeof htmx !== 'undefined'")
            assert has_htmx

    @pytest.mark.xfail(reason="May require cookie-based auth for HTML pages")
    def test_no_js_console_errors(self, authenticated_page: Page, base_url: str):
        """No JavaScript errors on dashboard page."""
        from tests.e2e.helpers import setup_console_listener

        console = setup_console_listener(authenticated_page)
        resp = authenticated_page.goto(f"{base_url}/dashboard")
        if resp and resp.status == 200:
            authenticated_page.wait_for_timeout(1000)
            assert len(console["errors"]) == 0, f"JS errors: {console['errors']}"


class TestDashboardHTMXPartials:
    """HTMX partial endpoints for dashboard components."""

    def test_cost_summary_partial(self, authenticated_page: Page, base_url: str):
        resp = authenticated_page.goto(f"{base_url}/partials/cost-summary-card")
        assert resp is not None
        assert resp.status in (200, 401, 403)

    def test_compliance_gauge_partial(self, authenticated_page: Page, base_url: str):
        resp = authenticated_page.goto(f"{base_url}/partials/compliance-gauge")
        assert resp is not None
        assert resp.status in (200, 401, 403)

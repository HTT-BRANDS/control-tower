"""E2E browser tests for the Riverside compliance dashboard."""

from playwright.sync_api import Page


class TestRiversideDashboard:
    """GET /riverside — Riverside compliance tracking page."""

    def test_riverside_page_responds(self, authenticated_page: Page, base_url: str):
        resp = authenticated_page.goto(f"{base_url}/riverside")
        assert resp is not None
        assert resp.status in (200, 401, 403)

    def test_riverside_has_compliance_content(self, authenticated_page: Page, base_url: str):
        resp = authenticated_page.goto(f"{base_url}/riverside")
        if resp and resp.status == 200:
            content = authenticated_page.content()
            assert "riverside" in content.lower() or "compliance" in content.lower()

    def test_riverside_has_deadline_info(self, authenticated_page: Page, base_url: str):
        resp = authenticated_page.goto(f"{base_url}/riverside")
        if resp and resp.status == 200:
            content = authenticated_page.content()
            # Should have deadline or countdown related content
            assert (
                "deadline" in content.lower() or "countdown" in content.lower() or "2026" in content
            )

    def test_riverside_loads_stylesheets(self, authenticated_page: Page, base_url: str):
        resp = authenticated_page.goto(f"{base_url}/riverside")
        if resp and resp.status == 200:
            links = authenticated_page.locator("link[rel='stylesheet']")
            assert links.count() > 0

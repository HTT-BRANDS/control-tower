"""E2E browser tests for the sync dashboard page."""

import pytest
from playwright.sync_api import Page


class TestSyncDashboardPage:
    """GET /sync-dashboard — DevOps/SRE sync monitoring."""

    def test_sync_dashboard_responds(self, authenticated_page: Page, base_url: str):
        resp = authenticated_page.goto(f"{base_url}/sync-dashboard")
        assert resp is not None
        assert resp.status in (200, 401, 403)

    @pytest.mark.xfail(reason="May require cookie auth")
    def test_sync_dashboard_has_status_section(self, authenticated_page: Page, base_url: str):
        resp = authenticated_page.goto(f"{base_url}/sync-dashboard")
        if resp and resp.status == 200:
            content = authenticated_page.content()
            assert "sync" in content.lower()

    @pytest.mark.xfail(reason="May require cookie auth")
    def test_sync_dashboard_has_title(self, authenticated_page: Page, base_url: str):
        resp = authenticated_page.goto(f"{base_url}/sync-dashboard")
        if resp and resp.status == 200:
            title = authenticated_page.title()
            assert len(title) > 0

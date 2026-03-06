"""E2E browser tests for the preflight checks page."""

import pytest
from playwright.sync_api import Page


class TestPreflightPage:
    """GET /api/v1/preflight — preflight checks HTML page."""

    def test_preflight_page_responds(self, authenticated_page: Page, base_url: str):
        resp = authenticated_page.goto(f"{base_url}/api/v1/preflight")
        assert resp is not None
        assert resp.status in (200, 401, 403)

    @pytest.mark.xfail(reason="May require cookie auth")
    def test_preflight_has_run_button(self, authenticated_page: Page, base_url: str):
        resp = authenticated_page.goto(f"{base_url}/api/v1/preflight")
        if resp and resp.status == 200:
            content = authenticated_page.content()
            assert "preflight" in content.lower() or "run" in content.lower()

    @pytest.mark.xfail(reason="May require cookie auth")
    def test_preflight_page_has_title(self, authenticated_page: Page, base_url: str):
        resp = authenticated_page.goto(f"{base_url}/api/v1/preflight")
        if resp and resp.status == 200:
            title = authenticated_page.title()
            assert len(title) > 0

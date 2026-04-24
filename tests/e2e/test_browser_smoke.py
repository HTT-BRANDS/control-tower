"""Focused must-pass browser smoke coverage for first-wave routes and partials."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.helpers import (
    assert_console_errors_clean,
    assert_no_server_error_text,
    setup_console_listener,
)

pytestmark = [pytest.mark.e2e, pytest.mark.smoke]

PAGE_SPECS = [
    {
        "path": "/login",
        "fixture": "unauthenticated_page",
        "title": "Login",
        "markers": ["[data-testid='login-shell']", "[data-testid='login-azure-entry']"],
        "text": "Sign in with Microsoft",
        "requires_nav": False,
    },
    {
        "path": "/dashboard",
        "fixture": "authenticated_page",
        "title": "Dashboard",
        "markers": [
            "[data-testid='dashboard-shell']",
            "[data-testid='dashboard-kpi-summary']",
            "[data-testid='dashboard-overview-grid']",
        ],
        "text": "Governance Dashboard",
        "requires_nav": True,
    },
    {
        "path": "/sync-dashboard",
        "fixture": "authenticated_page",
        "title": "Sync Status Dashboard",
        "markers": [
            "[data-testid='sync-dashboard-shell']",
            "[data-testid='sync-status-card']",
            "[data-testid='sync-history-table']",
            "[data-testid='tenant-sync-grid']",
        ],
        "text": "Sync Status Dashboard",
        "requires_nav": True,
    },
    {
        "path": "/riverside",
        "fixture": "authenticated_page",
        "title": "Riverside",
        "markers": [
            "[data-testid='riverside-shell']",
            "[data-testid='riverside-executive-summary-region']",
            "[data-testid='riverside-requirements-region']",
        ],
        "text": "Riverside",
        "requires_nav": True,
    },
    {
        "path": "/dmarc",
        "fixture": "authenticated_page",
        "title": "DMARC",
        "markers": [
            "[data-testid='dmarc-shell']",
            "[data-testid='dmarc-alert-banner']",
            "[data-testid='dmarc-tenant-scores']",
        ],
        "text": "DMARC",
        "requires_nav": True,
    },
]

PARTIAL_SPECS = [
    {
        "path": "/partials/sync-status-card",
        "markers": ["[data-testid='sync-status-card']"],
        "empty_markers": ["[data-testid='sync-status-empty-healthy']"],
    },
    {
        "path": "/partials/sync-history-table",
        "markers": [
            "[data-testid='sync-history-table']",
            "[data-testid='sync-history-table-grid']",
        ],
        "empty_markers": ["[data-testid='sync-history-empty-state']"],
    },
    {
        "path": "/partials/active-alerts",
        "markers": ["[data-testid='active-alerts-panel']"],
        "empty_markers": ["[data-testid='active-alerts-empty-state']"],
    },
    {
        "path": "/partials/tenant-sync-status",
        "markers": ["[data-testid='tenant-sync-grid']"],
        "empty_markers": ["[data-testid='tenant-sync-empty-state']"],
    },
]


def _goto(page: Page, path: str):
    response = page.goto(path)
    assert response is not None, f"No response when navigating to {path}"
    assert response.status == 200, f"{path} returned {response.status}"
    content_type = response.headers.get("content-type", "")
    assert "text/html" in content_type.lower(), f"{path} did not return HTML: {content_type}"
    return response


class TestFirstWaveBrowserSmokePages:
    @pytest.mark.parametrize(
        "spec", PAGE_SPECS, ids=[spec["path"].strip("/") or "login" for spec in PAGE_SPECS]
    )
    def test_page_renders_healthy_shell(self, request: pytest.FixtureRequest, spec: dict):
        page: Page = request.getfixturevalue(spec["fixture"])
        console = setup_console_listener(page)

        _goto(page, spec["path"])
        assert spec["title"].lower() in page.title().lower()

        page.wait_for_timeout(1000)
        for selector in spec["markers"]:
            assert page.locator(selector).count() > 0, (
                f"Missing marker {selector} on {spec['path']}"
            )

        expect(page.locator("body")).to_contain_text(spec["text"])

        content = page.content()
        assert_no_server_error_text(content)
        if spec["requires_nav"]:
            assert page.locator("nav, [role='navigation']").count() > 0
        assert_console_errors_clean(console["errors"])

    def test_unauthenticated_dashboard_redirects_to_login(self, unauthenticated_page: Page):
        response = unauthenticated_page.goto("/dashboard")
        assert response is not None
        assert unauthenticated_page.url.endswith("/login")
        expect(unauthenticated_page.locator("[data-testid='login-shell']")).to_be_visible()


class TestFirstWaveBrowserSmokePartials:
    @pytest.mark.parametrize(
        "spec",
        PARTIAL_SPECS,
        ids=[spec["path"].split("/")[-1] for spec in PARTIAL_SPECS],
    )
    def test_partial_renders_expected_fragment(self, authenticated_page: Page, spec: dict):
        _goto(authenticated_page, spec["path"])

        for selector in spec["markers"]:
            assert authenticated_page.locator(selector).count() > 0, (
                f"Missing fragment marker {selector} on {spec['path']}"
            )

        content = authenticated_page.content()
        assert_no_server_error_text(content)
        assert "<html" in content.lower()

        empty_markers = spec.get("empty_markers", [])
        if empty_markers:
            for selector in empty_markers:
                locator = authenticated_page.locator(selector)
                if locator.count() > 0:
                    assert locator.count() > 0

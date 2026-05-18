"""Browser proof that seeded local data actually renders in product pages.

These tests intentionally sit between the DB-only ``local_data_smoke.py`` and
full visual regression. The contract is simple: when the dedicated local DB is
seeded, core pages must fetch their API data and replace loading/placeholder UI
with real values. Rendering a beautiful empty shell is not a feature. Shocking,
I know.
"""

from __future__ import annotations

from collections.abc import Iterable

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.helpers import (
    assert_console_errors_clean,
    assert_no_server_error_text,
    setup_console_listener,
)

pytestmark = [pytest.mark.e2e, pytest.mark.smoke]

EXPECTED_TENANT_TEXT = "HTT Brands Corporate"

FETCH_PAGE_SPECS = [
    {
        "path": "/costs",
        "heading": "Cost Management",
        "api_paths": (
            "/api/v1/costs/summary",
            "/api/v1/costs/by-tenant",
            "/api/v1/costs/anomalies",
        ),
        "populated_selectors": ("#total-cost", "#tenant-count", "#subscription-count"),
        "table_selectors": ("#tenant-costs-table tr", "#anomalies-table tr"),
        "empty_text": ("No tenant cost data available",),
        "body_text": ("$", "Cost by Tenant"),
    },
    {
        "path": "/compliance",
        "heading": "Compliance Monitoring",
        "api_paths": (
            "/api/v1/compliance/summary",
            "/api/v1/compliance/scores",
            "/api/v1/compliance/non-compliant",
        ),
        "populated_selectors": ("#overall-score", "#total-policies", "#compliant-count"),
        "table_selectors": ("#scores-table tr",),
        "empty_text": ("No compliance data",),
        "body_text": ("%", "Compliance Scores by Tenant"),
    },
    {
        "path": "/resources",
        "heading": "Resource Inventory",
        "api_paths": (
            "/api/v1/resources",
            "/api/v1/resources/idle",
            "/api/v1/resources/orphaned",
            "/api/v1/resources/tagging",
        ),
        "populated_selectors": ("#total-resources", "#idle-count", "#tagging-score"),
        "table_selectors": ("#resources-table tr",),
        "empty_text": ("No resources found",),
        "body_text": ("Microsoft.", "%"),
    },
    {
        "path": "/identity",
        "heading": "Identity & Access",
        "api_paths": (
            "/api/v1/identity/summary",
            "/api/v1/identity/privileged",
            "/api/v1/identity/guests",
            "/api/v1/identity/stale",
        ),
        "populated_selectors": ("#total-users", "#guest-count", "#privileged-count"),
        "table_selectors": ("#privileged-table tr",),
        "empty_text": ("No privileged users found",),
        "body_text": ("@", "Privileged Users"),
    },
]

HTMX_PAGE_SPECS = [
    {
        "path": "/sync-dashboard",
        "heading": "Sync Status Dashboard",
        "api_paths": (
            "/partials/sync-status-card",
            "/partials/active-alerts",
            "/partials/sync-history-table",
            "/partials/tenant-sync-status",
        ),
        "visible_markers": (
            "[data-testid='sync-status-card']",
            "[data-testid='sync-history-table']",
            "[data-testid='tenant-sync-grid']",
        ),
        "empty_text": (
            "No sync history yet",
            "No tenants configured",
        ),
        "body_text": ("HTT Brands Corporate",),
    },
    {
        "path": "/riverside",
        "heading": "Riverside",
        "api_paths": (
            "/api/v1/riverside/summary",
            "/api/v1/riverside/maturity-scores",
        ),
        "visible_markers": (
            "[data-testid='riverside-shell']",
            "[data-testid='riverside-executive-summary-region']",
            "[data-testid='riverside-requirements-region']",
        ),
        "empty_text": ("Unable to load",),
        "body_text": ("Domain Maturity Scores", "Requirements"),
    },
    {
        "path": "/dmarc",
        "heading": "DMARC",
        "api_paths": (
            "/api/v1/dmarc/summary",
            "/api/v1/dmarc/trends?days=30",
        ),
        "visible_markers": (
            "[data-testid='dmarc-shell']",
            "[data-testid='dmarc-tenant-scores']",
        ),
        "empty_text": ("Loading tenants…", "Loading alerts…"),
        "body_text": ("Security Score", "Domains"),
    },
]


def _goto_html(page: Page, path: str) -> None:
    response = page.goto(path)
    assert response is not None, f"No response when navigating to {path}"
    assert response.status == 200, f"{path} returned {response.status}"
    assert "text/html" in response.headers.get("content-type", "").lower()


def _capture_api_statuses(page: Page, api_paths: Iterable[str]) -> dict[str, int]:
    pending = set(api_paths)
    seen: dict[str, int] = {}

    def record_response(response):
        url = response.url
        for api_path in tuple(pending):
            if api_path in url:
                seen[api_path] = response.status
                pending.remove(api_path)

    page.on("response", record_response)
    return seen


def _assert_api_paths_ok(seen: dict[str, int], api_paths: Iterable[str]) -> None:
    missing = [path for path in api_paths if path not in seen]
    bad = {path: status for path, status in seen.items() if status >= 400}
    assert not missing, f"Expected browser fetches did not happen: {missing}; seen={seen}"
    assert not bad, f"Browser data fetches failed: {bad}"


def _assert_real_values(page: Page, selectors: Iterable[str]) -> None:
    for selector in selectors:
        locator = page.locator(selector).first
        expect(locator).to_be_visible()
        expect(locator).not_to_have_text("--")
        expect(locator).not_to_have_text("Loading...")


def _assert_rows_rendered(page: Page, selectors: Iterable[str]) -> None:
    for selector in selectors:
        expect(page.locator(selector).first).to_be_visible()
        assert page.locator(selector).count() > 0, f"No rendered rows for {selector}"


def _assert_no_seeded_empty_copy(page: Page, snippets: Iterable[str]) -> None:
    body = page.locator("body")
    for snippet in snippets:
        expect(body).not_to_contain_text(snippet)


def _assert_body_contains(page: Page, snippets: Iterable[str]) -> None:
    body = page.locator("body")
    for snippet in snippets:
        expect(body).to_contain_text(snippet)


class TestSeededDataFetchingPages:
    @pytest.mark.parametrize(
        "spec", FETCH_PAGE_SPECS, ids=[spec["path"].strip("/") for spec in FETCH_PAGE_SPECS]
    )
    def test_js_fetch_page_renders_seeded_data(self, authenticated_page: Page, spec: dict):
        console = setup_console_listener(authenticated_page)
        seen = _capture_api_statuses(authenticated_page, spec["api_paths"])

        _goto_html(authenticated_page, spec["path"])
        expect(
            authenticated_page.get_by_role("heading", name=spec["heading"]).first
        ).to_be_visible()

        _assert_real_values(authenticated_page, spec["populated_selectors"])
        _assert_rows_rendered(authenticated_page, spec["table_selectors"])
        _assert_api_paths_ok(seen, spec["api_paths"])
        _assert_body_contains(authenticated_page, spec["body_text"])
        _assert_no_seeded_empty_copy(authenticated_page, spec["empty_text"])

        assert_no_server_error_text(authenticated_page.content())
        assert_console_errors_clean(console["errors"])

    @pytest.mark.parametrize(
        "spec", HTMX_PAGE_SPECS, ids=[spec["path"].strip("/") for spec in HTMX_PAGE_SPECS]
    )
    def test_htmx_and_dashboard_pages_render_seeded_data(
        self, authenticated_page: Page, spec: dict
    ):
        console = setup_console_listener(authenticated_page)
        seen = _capture_api_statuses(authenticated_page, spec["api_paths"])

        _goto_html(authenticated_page, spec["path"])
        expect(
            authenticated_page.get_by_role("heading", name=spec["heading"]).first
        ).to_be_visible()

        for marker in spec["visible_markers"]:
            expect(authenticated_page.locator(marker).first).to_be_visible()

        _assert_api_paths_ok(seen, spec["api_paths"])
        _assert_body_contains(authenticated_page, spec["body_text"])
        _assert_no_seeded_empty_copy(authenticated_page, spec["empty_text"])

        assert_no_server_error_text(authenticated_page.content())
        assert_console_errors_clean(console["errors"])

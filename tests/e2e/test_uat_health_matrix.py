"""Focused UAT health matrix for routes, APIs, middleware, and live data pulls.

This is the "is the app actually useful after login?" suite. It intentionally
checks broad contracts rather than pixel-perfect implementation details:

* protected pages render real shells instead of blank HTML/JSON errors;
* critical APIs return JSON without 404/500 faceplants;
* data-fetching pages actually call their backing endpoints;
* middleware/security headers apply to HTML, API, partial, and error responses;
* HTMX pages do not clobber the browser URL to a partial endpoint.
"""

from __future__ import annotations

from collections.abc import Iterable

import pytest
from playwright.sync_api import APIRequestContext, Page, expect

from tests.e2e.helpers import (
    assert_console_errors_clean,
    assert_no_server_error_text,
    setup_console_listener,
)

pytestmark = [pytest.mark.e2e, pytest.mark.smoke]

SECURITY_HEADER_PATHS = (
    "/auth/login",
    "/api/v1/health",
    "/partials/sync-status-card",
    "/this-route-should-not-exist",
)

CRITICAL_API_SPECS = (
    ("/api/v1/health", {"status"}),
    ("/api/v1/status", {"status", "version"}),
    ("/api/v1/auth/me", {"email", "roles"}),
    ("/api/v1/costs/summary", {"total_cost", "currency"}),
    ("/api/v1/costs/by-tenant", None),
    ("/api/v1/costs/anomalies", None),
    ("/api/v1/compliance/summary", {"average_compliance_percent", "scores_by_tenant"}),
    ("/api/v1/compliance/scores", None),
    ("/api/v1/compliance/non-compliant", None),
    ("/api/v1/resources", {"total_resources", "resources"}),
    ("/api/v1/resources/idle", None),
    ("/api/v1/resources/orphaned", None),
    ("/api/v1/resources/tagging", None),
    ("/api/v1/identity/summary", {"total_users", "guest_users"}),
    ("/api/v1/identity/privileged", None),
    ("/api/v1/identity/guests", None),
    ("/api/v1/identity/stale", None),
    ("/api/v1/dmarc/summary", {"total_domains", "average_security_score"}),
    ("/api/v1/dmarc/trends?days=30", None),
    ("/api/v1/tenants", None),
    ("/api/v1/sync/status", None),
    ("/monitoring/health", {"status"}),
)

PROTECTED_PAGE_SPECS = (
    ("/dashboard", "Governance Dashboard", ("[data-testid='dashboard-shell']",)),
    ("/costs", "Cost Management", ("#total-cost", "#tenant-count")),
    ("/compliance", "Compliance Monitoring", ("#overall-score", "#total-policies")),
    ("/resources", "Resource Inventory", ("#total-resources", "#idle-count")),
    ("/identity", "Identity & Access", ("#total-users", "#guest-count")),
    ("/sync-dashboard", "Sync Status Dashboard", ("[data-testid='sync-dashboard-shell']",)),
    ("/riverside", "Riverside", ("[data-testid='riverside-shell']",)),
    ("/dmarc", "DMARC", ("[data-testid='dmarc-shell']",)),
    ("/design-system", "Design System", ("main",)),
    ("/topology", "Topology", ("main",)),
    ("/api/v1/preflight", "Preflight", ("main",)),
    ("/privacy", "Privacy", ("main",)),
    ("/admin", "Admin", ("main",)),
)

DATA_FETCH_PAGE_SPECS = (
    (
        "/costs",
        (
            "/api/v1/costs/summary",
            "/api/v1/costs/by-tenant",
            "/api/v1/costs/anomalies",
        ),
    ),
    (
        "/compliance",
        (
            "/api/v1/compliance/summary",
            "/api/v1/compliance/scores",
            "/api/v1/compliance/non-compliant",
        ),
    ),
    (
        "/resources",
        (
            "/api/v1/resources",
            "/api/v1/resources/idle",
            "/api/v1/resources/orphaned",
            "/api/v1/resources/tagging",
        ),
    ),
    (
        "/identity",
        (
            "/api/v1/identity/summary",
            "/api/v1/identity/privileged",
            "/api/v1/identity/guests",
            "/api/v1/identity/stale",
        ),
    ),
)

HTMX_URL_STABILITY_PATHS = ("/sync-dashboard", "/riverside", "/dmarc")


def _assert_security_headers(headers: dict[str, str], path: str) -> None:
    assert headers.get("x-frame-options") == "DENY", path
    assert headers.get("x-content-type-options") == "nosniff", path
    assert headers.get("referrer-policy") == "strict-origin-when-cross-origin", path
    assert "camera=()" in headers.get("permissions-policy", ""), path
    csp = headers.get("content-security-policy", "")
    assert "default-src" in csp, path
    assert "object-src 'none'" in csp, path


def _assert_json_response(resp, path: str):
    assert resp.status < 500, f"{path} returned server error {resp.status}: {resp.text()}"
    assert resp.status != 404, f"{path} is missing"
    assert resp.status in (200, 401, 403), f"{path} returned unexpected {resp.status}"
    if resp.status == 200:
        assert "application/json" in resp.headers.get("content-type", "").lower(), path
        return resp.json()
    return None


def _capture_statuses(page: Page, paths: Iterable[str]) -> dict[str, int]:
    pending = set(paths)
    seen: dict[str, int] = {}

    def record(response):
        for path in tuple(pending):
            if path in response.url:
                seen[path] = response.status
                pending.remove(path)

    page.on("response", record)
    return seen


class TestUATHealthMatrix:
    @pytest.mark.parametrize(
        "path", SECURITY_HEADER_PATHS, ids=lambda value: value.strip("/") or "root"
    )
    def test_security_headers_cover_response_classes(self, authenticated_page: Page, path: str):
        response = authenticated_page.goto(path)
        assert response is not None, f"No response for {path}"
        assert response.status < 500, f"{path} returned {response.status}"
        _assert_security_headers(response.headers, path)

    @pytest.mark.parametrize(
        ("path", "expected_keys"),
        CRITICAL_API_SPECS,
        ids=[spec[0].replace("/api/v1/", "") for spec in CRITICAL_API_SPECS],
    )
    def test_critical_api_contracts_are_live(
        self, api_context: APIRequestContext, path: str, expected_keys: set[str] | None
    ):
        resp = api_context.get(path)
        data = _assert_json_response(resp, path)
        if data is not None and expected_keys:
            assert isinstance(data, dict), f"{path} must return an object"
            missing = expected_keys - set(data)
            assert not missing, f"{path} missing keys {missing}; got {sorted(data)}"

    @pytest.mark.parametrize(
        ("path", "heading", "selectors"),
        PROTECTED_PAGE_SPECS,
        ids=[spec[0].strip("/").replace("/", "_") for spec in PROTECTED_PAGE_SPECS],
    )
    def test_authenticated_pages_render_non_blank_shells(
        self, authenticated_page: Page, path: str, heading: str, selectors: tuple[str, ...]
    ):
        console = setup_console_listener(authenticated_page)
        response = authenticated_page.goto(path)
        assert response is not None, f"No response for {path}"
        assert response.status == 200, f"{path} returned {response.status}"
        assert "text/html" in response.headers.get("content-type", "").lower(), path

        expect(authenticated_page.get_by_role("heading", name=heading).first).to_be_visible()
        for selector in selectors:
            expect(authenticated_page.locator(selector).first).to_be_visible()

        body_text = authenticated_page.locator("body").inner_text(timeout=3000).strip()
        assert len(body_text) > 100, f"{path} rendered suspiciously blank body"
        assert_no_server_error_text(authenticated_page.content())
        assert_console_errors_clean(console["errors"])

    @pytest.mark.parametrize(
        ("path", "api_paths"),
        DATA_FETCH_PAGE_SPECS,
        ids=[spec[0].strip("/") for spec in DATA_FETCH_PAGE_SPECS],
    )
    def test_data_pages_pull_their_backing_apis(
        self, authenticated_page: Page, path: str, api_paths: tuple[str, ...]
    ):
        seen = _capture_statuses(authenticated_page, api_paths)
        response = authenticated_page.goto(path)
        assert response is not None and response.status == 200
        authenticated_page.wait_for_load_state("networkidle")

        missing = [api_path for api_path in api_paths if api_path not in seen]
        failures = {api_path: status for api_path, status in seen.items() if status >= 400}
        assert not missing, f"{path} did not fetch expected APIs: {missing}; seen={seen}"
        assert not failures, f"{path} data fetch failures: {failures}"

        body = authenticated_page.locator("body")
        expect(body).not_to_contain_text("Internal Server Error")
        expect(body).not_to_contain_text("Traceback")
        visible_loading_count = authenticated_page.locator("text=Loading...").evaluate_all(
            """elements => elements.filter(el => {
                const style = window.getComputedStyle(el);
                const rect = el.getBoundingClientRect();
                return style.visibility !== 'hidden'
                    && style.display !== 'none'
                    && rect.width > 0
                    && rect.height > 0;
            }).length"""
        )
        assert visible_loading_count == 0, f"{path} still has visible loading placeholders"

    @pytest.mark.parametrize("path", HTMX_URL_STABILITY_PATHS)
    def test_htmx_pages_do_not_clobber_url_to_partials(self, authenticated_page: Page, path: str):
        response = authenticated_page.goto(path)
        assert response is not None and response.status == 200
        authenticated_page.wait_for_timeout(1000)
        assert authenticated_page.url.endswith(path), (
            f"{path} navigated/clobbered URL to {authenticated_page.url}"
        )

        reload_response = authenticated_page.reload()
        assert reload_response is not None and reload_response.status == 200
        expect(authenticated_page.locator("main").first).to_be_visible()
        body_text = authenticated_page.locator("body").inner_text(timeout=3000).strip()
        assert len(body_text) > 100

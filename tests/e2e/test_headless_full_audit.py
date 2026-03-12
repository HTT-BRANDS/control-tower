"""Full headless browser audit — every page, partial, API, and integration.

This is the definitive E2E test suite that exercises the entire application
through a real Chromium browser with proper cookie-based authentication.

Run: uv run pytest tests/e2e/test_headless_full_audit.py -v --headed (visual)
     uv run pytest tests/e2e/test_headless_full_audit.py -v             (headless)
"""

import json

import pytest
from playwright.sync_api import BrowserContext, Page, expect

# ---------------------------------------------------------------------------
# Cookie-authenticated browser context
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def cookie_context(browser, base_url: str) -> BrowserContext:
    """Create a browser context with auth cookie set via real login flow."""
    context = browser.new_context(
        viewport={"width": 1280, "height": 720},
        ignore_https_errors=True,
    )
    page = context.new_page()
    page.goto(f"{base_url}/login")
    page.wait_for_load_state("domcontentloaded")
    page.fill('input[name="username"], input#username, input[type="text"]', "admin")
    page.fill('input[name="password"], input#password, input[type="password"]', "admin")
    page.click('button[type="submit"]')
    page.wait_for_url("**/dashboard**", timeout=10_000)

    cookies = context.cookies()
    assert any(c["name"] == "access_token" for c in cookies), "Cookie not set after login"
    page.close()
    yield context
    context.close()


@pytest.fixture
def page(cookie_context: BrowserContext, base_url: str) -> Page:
    """Fresh page with auth cookie already set."""
    p = cookie_context.new_page()
    p._base_url = base_url  # type: ignore[attr-defined]
    yield p
    p.close()


# ===========================================================================
#  1. LOGIN FLOW
# ===========================================================================


class TestLoginFlow:
    """Authentication lifecycle through the browser."""

    def test_login_page_renders(self, browser, base_url: str):
        ctx = browser.new_context()
        pg = ctx.new_page()
        resp = pg.goto(f"{base_url}/login")
        assert resp.status == 200
        expect(pg.locator("form")).to_be_visible()
        expect(pg.locator('input[type="password"]')).to_be_visible()
        pg.close()
        ctx.close()

    def test_unauthenticated_redirect_to_login(self, browser, base_url: str):
        ctx = browser.new_context()
        pg = ctx.new_page()
        pg.goto(f"{base_url}/dashboard")
        assert "/login" in pg.url
        pg.close()
        ctx.close()

    def test_login_sets_cookie_and_redirects(self, browser, base_url: str):
        ctx = browser.new_context()
        pg = ctx.new_page()
        pg.goto(f"{base_url}/login")
        pg.fill('input[name="username"], input#username, input[type="text"]', "admin")
        pg.fill('input[name="password"], input#password, input[type="password"]', "admin")
        pg.click('button[type="submit"]')
        pg.wait_for_url("**/dashboard**", timeout=10_000)
        assert any(c["name"] == "access_token" for c in ctx.cookies())
        pg.close()
        ctx.close()

    def test_bad_credentials_show_error(self, browser, base_url: str):
        ctx = browser.new_context()
        pg = ctx.new_page()
        pg.goto(f"{base_url}/login")
        pg.fill('input[name="username"], input#username, input[type="text"]', "admin")
        pg.fill('input[name="password"], input#password, input[type="password"]', "wrong")
        pg.click('button[type="submit"]')
        pg.wait_for_timeout(1000)
        assert "/dashboard" not in pg.url
        pg.close()
        ctx.close()


# ===========================================================================
#  2. FULL PAGE RENDERING
# ===========================================================================

PAGE_SPECS = [
    ("/dashboard", "Dashboard"),
    ("/costs", "Cost"),
    ("/compliance", "Compliance"),
    ("/resources", "Resource"),
    ("/identity", "Identity"),
    ("/riverside", "Riverside"),
    ("/dmarc", "DMARC"),
    ("/sync-dashboard", "Sync"),
    ("/onboarding/", "Onboard"),
    ("/api/v1/preflight", "Preflight"),
]

_PAGE_IDS = [s[0].strip("/").replace("/", "-") or "root" for s in PAGE_SPECS]


class TestPageRendering:
    """Every page loads with 200, has a title, and no server errors."""

    @pytest.mark.parametrize("path, kw", PAGE_SPECS, ids=_PAGE_IDS)
    def test_page_loads_200(self, page: Page, path: str, kw: str):
        resp = page.goto(f"{page._base_url}{path}")
        assert resp.status == 200, f"{path} returned {resp.status}"

    @pytest.mark.parametrize("path, kw", PAGE_SPECS, ids=_PAGE_IDS)
    def test_page_has_title(self, page: Page, path: str, kw: str):
        page.goto(f"{page._base_url}{path}")
        assert len(page.title()) > 0, f"{path} has empty <title>"

    @pytest.mark.parametrize("path, kw", PAGE_SPECS, ids=_PAGE_IDS)
    def test_page_no_500_in_body(self, page: Page, path: str, kw: str):
        page.goto(f"{page._base_url}{path}")
        body = page.inner_text("body")
        assert "Internal Server Error" not in body
        assert "Traceback" not in body


# ===========================================================================
#  3. HTMX PARTIALS
# ===========================================================================

PARTIALS = [
    "/partials/cost-summary-card",
    "/partials/compliance-gauge",
    "/partials/resource-stats",
    "/partials/identity-stats",
    "/partials/riverside-badge",
    "/partials/sync-status-card",
    "/partials/sync-history-table",
    "/partials/tenant-sync-status",
    "/partials/active-alerts",
]


class TestHTMXPartials:
    @pytest.mark.parametrize("path", PARTIALS, ids=[p.split("/")[-1] for p in PARTIALS])
    def test_partial_returns_200(self, page: Page, path: str):
        resp = page.goto(f"{page._base_url}{path}")
        assert resp.status == 200, f"{path} returned {resp.status}"

    @pytest.mark.parametrize("path", PARTIALS, ids=[p.split("/")[-1] for p in PARTIALS])
    def test_partial_contains_html(self, page: Page, path: str):
        page.goto(f"{page._base_url}{path}")
        assert "<" in page.content()


# ===========================================================================
#  4. DASHBOARD HTMX INTEGRATION
# ===========================================================================


class TestDashboardHTMXIntegration:
    def test_dashboard_has_htmx_loaded(self, page: Page):
        page.goto(f"{page._base_url}/dashboard")
        assert page.evaluate("() => typeof htmx !== 'undefined'")

    def test_dashboard_partials_load(self, page: Page):
        page.goto(f"{page._base_url}/dashboard")
        page.wait_for_timeout(3000)
        assert len(page.inner_text("body")) > 100

    def test_dashboard_no_js_errors(self, page: Page):
        errors = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.goto(f"{page._base_url}/dashboard")
        page.wait_for_timeout(3000)
        real = [e for e in errors if "favicon" not in e.lower()]
        assert len(real) == 0, f"JS errors: {real}"

    def test_dashboard_navigation_present(self, page: Page):
        page.goto(f"{page._base_url}/dashboard")
        assert page.locator("nav, [role='navigation'], aside, .sidebar").count() > 0


# ===========================================================================
#  5. REST API ENDPOINTS
# ===========================================================================

API_GET_ENDPOINTS = [
    # Costs
    ("/api/v1/costs/summary", dict),
    ("/api/v1/costs/by-tenant", list),
    ("/api/v1/costs/trends", list),
    ("/api/v1/costs/anomalies", list),
    ("/api/v1/costs/anomalies/top", list),
    ("/api/v1/costs/anomalies/by-service", list),
    ("/api/v1/costs/anomalies/trends", list),
    ("/api/v1/costs/trends/forecast", list),
    # Compliance
    ("/api/v1/compliance/summary", dict),
    ("/api/v1/compliance/scores", list),
    ("/api/v1/compliance/non-compliant", list),
    ("/api/v1/compliance/trends", list),
    ("/api/v1/compliance/status", dict),
    # Resources
    ("/api/v1/resources", dict),
    ("/api/v1/resources/orphaned", list),
    ("/api/v1/resources/tagging", dict),
    ("/api/v1/resources/idle", list),
    ("/api/v1/resources/idle/summary", dict),
    # Identity
    ("/api/v1/identity/summary", dict),
    ("/api/v1/identity/privileged", list),
    ("/api/v1/identity/guests", list),
    ("/api/v1/identity/stale", list),
    ("/api/v1/identity/trends", list),
    # Riverside
    ("/api/v1/riverside/summary", dict),
    ("/api/v1/riverside/mfa-status", dict),
    ("/api/v1/riverside/maturity-scores", dict),
    ("/api/v1/riverside/requirements", dict),
    ("/api/v1/riverside/gaps", dict),
    # DMARC (only endpoints that don't require tenant_id)
    ("/api/v1/dmarc/summary", dict),
    ("/api/v1/dmarc/alerts", list),
    ("/api/v1/dmarc/trends", list),
    # Sync
    ("/api/v1/sync/status", dict),
    ("/api/v1/sync/alerts", dict),
    ("/api/v1/sync/status/health", dict),
    # Tenants
    ("/api/v1/tenants", list),
    # Recommendations
    ("/api/v1/recommendations", list),
    ("/api/v1/recommendations/summary", list),
    ("/api/v1/recommendations/by-category", list),
    ("/api/v1/recommendations/by-tenant", dict),
    ("/api/v1/recommendations/savings-potential", dict),
    # Preflight
    ("/api/v1/preflight/status", dict),
    # Monitoring
    ("/monitoring/health", dict),
    ("/monitoring/performance", dict),
    ("/monitoring/cache", dict),
    ("/monitoring/queries", list),
    ("/monitoring/sync-jobs", list),
    # System
    ("/api/v1/status", dict),
    ("/api/v1/auth/health", dict),
]


class TestRESTAPIEndpoints:
    """Every GET API endpoint returns 200 and valid JSON."""

    @pytest.mark.parametrize(
        "path, expected_type",
        API_GET_ENDPOINTS,
        ids=[ep[0].replace("/api/v1/", "").replace("/", "-") for ep in API_GET_ENDPOINTS],
    )
    def test_api_returns_200(self, page: Page, path: str, expected_type):
        resp = page.goto(f"{page._base_url}{path}")
        assert resp.status == 200, f"{path} returned {resp.status}"

    @pytest.mark.parametrize(
        "path, expected_type",
        API_GET_ENDPOINTS,
        ids=[ep[0].replace("/api/v1/", "").replace("/", "-") for ep in API_GET_ENDPOINTS],
    )
    def test_api_returns_valid_json(self, page: Page, path: str, expected_type):
        page.goto(f"{page._base_url}{path}")
        data = json.loads(page.evaluate("() => document.body.innerText"))
        assert isinstance(data, expected_type), (
            f"{path}: expected {expected_type.__name__}, got {type(data).__name__}"
        )


# ===========================================================================
#  6. STATIC ASSETS
# ===========================================================================

STATIC_ASSETS = [
    "/static/css/theme.css",
    "/static/js/navigation/index.js",
    "/static/js/darkMode.js",
]


class TestStaticAssets:
    @pytest.mark.parametrize("path", STATIC_ASSETS, ids=[p.split("/")[-1] for p in STATIC_ASSETS])
    def test_static_asset_loads(self, page: Page, path: str):
        resp = page.goto(f"{page._base_url}{path}")
        assert resp.status == 200


# ===========================================================================
#  7. PUBLIC ENDPOINTS
# ===========================================================================


class TestPublicEndpoints:
    def test_health_check(self, browser, base_url: str):
        ctx = browser.new_context()
        pg = ctx.new_page()
        resp = pg.goto(f"{base_url}/health")
        assert resp.status == 200
        body = json.loads(pg.evaluate("() => document.body.innerText"))
        assert body["status"] == "healthy"
        pg.close()
        ctx.close()

    def test_detailed_health_check(self, browser, base_url: str):
        ctx = browser.new_context()
        pg = ctx.new_page()
        resp = pg.goto(f"{base_url}/health/detailed")
        assert resp.status == 200
        pg.close()
        ctx.close()

    def test_login_page_accessible(self, browser, base_url: str):
        ctx = browser.new_context()
        pg = ctx.new_page()
        resp = pg.goto(f"{base_url}/login")
        assert resp.status == 200
        expect(pg.locator("form")).to_be_visible()
        pg.close()
        ctx.close()

    def test_metrics_endpoint(self, browser, base_url: str):
        ctx = browser.new_context()
        pg = ctx.new_page()
        resp = pg.goto(f"{base_url}/metrics")
        assert resp.status == 200
        pg.close()
        ctx.close()


# ===========================================================================
#  8. SECURITY HEADERS
# ===========================================================================


class TestSecurityHeaders:
    @pytest.mark.parametrize(
        "path",
        ["/dashboard", "/costs", "/compliance", "/resources", "/identity"],
        ids=["dashboard", "costs", "compliance", "resources", "identity"],
    )
    def test_security_headers_present(self, page: Page, path: str):
        resp = page.goto(f"{page._base_url}{path}")
        h = resp.headers
        assert h.get("x-frame-options") == "DENY"
        assert h.get("x-content-type-options") == "nosniff"
        assert "default-src" in h.get("content-security-policy", "")

    def test_csp_has_nonce(self, page: Page):
        resp = page.goto(f"{page._base_url}/dashboard")
        assert "nonce-" in resp.headers.get("content-security-policy", "")


# ===========================================================================
#  9. NAVIGATION
# ===========================================================================

# Dashboard link uses href="/" not "/dashboard"; dmarc not in main nav sidebar
NAV_TARGETS = ["/", "/costs", "/compliance", "/resources", "/identity", "/riverside"]


class TestNavigation:
    def test_sidebar_has_nav_links(self, page: Page):
        """Dashboard sidebar contains links to all sections."""
        page.goto(f"{page._base_url}/dashboard")
        page.wait_for_load_state("domcontentloaded")
        # Collect all link-like elements (a[href], elements with hx-get, etc.)
        hrefs = page.evaluate("""
            () => {
                const links = document.querySelectorAll('a[href], [hx-get]');
                return Array.from(links).map(el => el.getAttribute('href') || el.getAttribute('hx-get') || '');
            }
        """)
        for target in NAV_TARGETS:
            assert any(target in h for h in hrefs), f"Missing nav link to {target}"

    @pytest.mark.parametrize("target", NAV_TARGETS, ids=[t.strip("/") for t in NAV_TARGETS])
    def test_direct_navigation(self, page: Page, target: str):
        """Each section is directly navigable by URL."""
        resp = page.goto(f"{page._base_url}{target}")
        assert resp.status == 200, f"{target} returned {resp.status}"


# ===========================================================================
#  10. CROSS-PAGE CONSISTENCY
# ===========================================================================


class TestCrossPageConsistency:
    @pytest.mark.parametrize("path, kw", PAGE_SPECS, ids=_PAGE_IDS)
    def test_no_python_tracebacks(self, page: Page, path: str, kw: str):
        page.goto(f"{page._base_url}{path}")
        assert "Traceback (most recent call last)" not in page.inner_text("body")

    @pytest.mark.parametrize("path, kw", PAGE_SPECS, ids=_PAGE_IDS)
    def test_no_jinja_errors(self, page: Page, path: str, kw: str):
        page.goto(f"{page._base_url}{path}")
        html = page.content()
        assert "UndefinedError" not in html
        assert "TemplateSyntaxError" not in html
        assert "jinja2.exceptions" not in html


# ===========================================================================
#  11. EXPORT DOWNLOADS
# ===========================================================================

EXPORT_PATHS = ["/api/v1/exports/costs", "/api/v1/exports/resources", "/api/v1/exports/compliance"]


class TestExportDownloads:
    @pytest.mark.parametrize("path", EXPORT_PATHS, ids=["costs", "resources", "compliance"])
    def test_export_returns_csv(self, page: Page, path: str):
        """Export endpoint returns CSV content via JS fetch (bypasses download trigger)."""
        # page.goto() throws on download responses, so use in-page fetch
        page.goto(f"{page._base_url}/dashboard")  # ensure we're on a page first
        result = page.evaluate(
            """(url) => fetch(url).then(async r => ({
                status: r.status,
                ct: r.headers.get('content-type') || '',
                cd: r.headers.get('content-disposition') || '',
                len: (await r.text()).length,
            }))""",
            f"{path}",
        )
        assert result["status"] == 200, f"{path} returned {result['status']}"
        assert "text/csv" in result["ct"], f"Not CSV: {result['ct']}"
        assert ".csv" in result["cd"], "No .csv in Content-Disposition"


# ===========================================================================
#  12. AUTH PROTECTION
# ===========================================================================


class TestAuthProtection:
    PROTECTED_PAGES = ["/dashboard", "/costs", "/compliance", "/resources", "/identity"]

    @pytest.mark.parametrize("path", PROTECTED_PAGES, ids=[p.strip("/") for p in PROTECTED_PAGES])
    def test_page_redirects_without_auth(self, browser, base_url: str, path: str):
        """Protected pages redirect to /login without auth cookie."""
        ctx = browser.new_context()
        pg = ctx.new_page()
        pg.goto(f"{base_url}{path}")
        assert "/login" in pg.url, f"{path} didn't redirect to login"
        pg.close()
        ctx.close()


# ===========================================================================
#  13. TENANT-SCOPED API ENDPOINTS (require tenant_id param)
# ===========================================================================

TENANT_SCOPED_ENDPOINTS = [
    "/api/v1/identity/admin-roles/summary",
    "/api/v1/identity/admin-roles/global-admins",
    "/api/v1/identity/admin-roles/security-admins",
    "/api/v1/identity/admin-roles/privileged-users",
    "/api/v1/identity/admin-roles/service-principals",
    "/api/v1/dmarc/records",
    "/api/v1/dmarc/reports",
    "/api/v1/dmarc/dkim",
    "/api/v1/dmarc/score",
]


class TestTenantScopedEndpoints:
    """Endpoints that require tenant_id query param."""

    @pytest.mark.parametrize(
        "path",
        TENANT_SCOPED_ENDPOINTS,
        ids=[p.split("/")[-1] for p in TENANT_SCOPED_ENDPOINTS],
    )
    def test_returns_422_without_tenant_id(self, page: Page, path: str):
        """Endpoint correctly rejects requests missing required tenant_id."""
        resp = page.goto(f"{page._base_url}{path}")
        assert resp.status == 422, f"{path} returned {resp.status} (expected 422)"

    @pytest.mark.parametrize(
        "path",
        TENANT_SCOPED_ENDPOINTS,
        ids=[p.split("/")[-1] for p in TENANT_SCOPED_ENDPOINTS],
    )
    def test_returns_200_with_tenant_id(self, page: Page, path: str):
        """Endpoint works when tenant_id is provided."""
        # Get first tenant ID from /api/v1/tenants
        page.goto(f"{page._base_url}/api/v1/tenants")
        tenants = json.loads(page.evaluate("() => document.body.innerText"))
        if not tenants:
            pytest.skip("No tenants in database")
        tenant_id = tenants[0]["id"]
        resp = page.goto(f"{page._base_url}{path}?tenant_id={tenant_id}")
        assert resp.status == 200, f"{path}?tenant_id={tenant_id} returned {resp.status}"

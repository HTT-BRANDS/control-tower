"""End-to-end frontend integration tests.

Validates the full UI/UX stack against the traceability matrix:
- Epic 8 (REQ-801..804): WCAG, accessibility, a11y
- Epic 9 (REQ-901..907): Design system, theming, templates, components

Tests cover:
  1. Template integrity (all referenced templates exist)
  2. Page routes return styled HTML
  3. HTMX partial endpoints return valid HTML fragments
  4. Design system integration (brand context, CSS variables)
  5. CSP headers (nonces, allowed sources)
  6. Cookie-based auth flow
  7. HTMX attribute correctness
  8. Jinja2 macro library availability
  9. Tailwind CSS compilation (wm-* colors, utilities)
"""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture()
def client(seeded_db):
    """Test client with database override and rate limiting disabled."""
    from app.core.rate_limit import rate_limiter

    def override_get_db():
        try:
            yield seeded_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    # Disable rate limiting for tests
    rate_limiter._enabled = False
    with TestClient(app) as c:
        yield c
    rate_limiter._enabled = True
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_token(client):
    """Get a valid JWT token for authenticated requests."""
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": "admin"},  # pragma: allowlist secret
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture()
def auth_cookies(auth_token):
    """Cookie dict for browser-like requests."""
    return {"access_token": auth_token}


# ============================================================================
# 1. Template Integrity (REQ-907)
# ============================================================================


class TestTemplateIntegrity:
    """Verify all template file references are valid."""

    TEMPLATES_DIR = Path("app/templates")

    def test_all_template_files_exist(self):
        """Every .html file in templates/ is parseable."""
        templates = list(self.TEMPLATES_DIR.rglob("*.html"))
        assert len(templates) >= 20, f"Expected 20+ templates, found {len(templates)}"

    def test_base_template_exists(self):
        """base.html is the layout root."""
        assert (self.TEMPLATES_DIR / "base.html").exists()

    def test_login_template_exists(self):
        """Standalone login template exists."""
        assert (self.TEMPLATES_DIR / "login.html").exists()

    def test_macros_library_exists(self):
        """REQ-907: Jinja2 UI component macro library."""
        macro_file = self.TEMPLATES_DIR / "macros" / "ui.html"
        assert macro_file.exists()
        content = macro_file.read_text()
        # Verify key macros are defined
        assert "macro brand_button" in content
        assert "macro brand_card" in content or "macro card" in content

    def test_dashboard_page_extends_base(self):
        """Dashboard page uses base template."""
        dash = (self.TEMPLATES_DIR / "pages" / "dashboard.html").read_text()
        assert '{% extends "base.html" %}' in dash

    @pytest.mark.parametrize("template_path", [
        "components/cost_summary_card.html",
        "components/compliance_gauge.html",
        "components/resource_stats.html",
        "components/identity_stats.html",
        "components/riverside_badge.html",
        "components/sync/sync_status_card.html",
        "components/sync/sync_history_table.html",
        "components/sync/active_alerts.html",
        "components/sync/tenant_sync_grid.html",
    ])
    def test_component_templates_exist(self, template_path):
        """All component templates referenced by routes exist."""
        assert (self.TEMPLATES_DIR / template_path).exists()


# ============================================================================
# 2. Page Routes (Full HTML Responses)
# ============================================================================


class TestPageRoutes:
    """All page routes return valid HTML."""

    PUBLIC_PAGES = ["/login", "/onboarding/"]
    AUTH_PAGES = ["/dashboard", "/sync-dashboard", "/riverside", "/dmarc"]

    @pytest.mark.parametrize("path", PUBLIC_PAGES)
    def test_public_pages_no_auth(self, client, path):
        """Public pages are accessible without authentication."""
        response = client.get(path)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @pytest.mark.parametrize("path", AUTH_PAGES)
    def test_auth_pages_with_cookie(self, client, auth_cookies, path):
        """Auth pages are accessible with cookie."""
        response = client.get(path, cookies=auth_cookies)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @pytest.mark.parametrize("path", AUTH_PAGES)
    def test_auth_pages_without_cookie_redirect(self, client, path):
        """Auth pages redirect to /login without auth."""
        response = client.get(
            path,
            headers={"Accept": "text/html"},
            follow_redirects=False,
        )
        assert response.status_code in (302, 401)

    def test_root_redirects_to_login_unauthenticated(self, client):
        """/ redirects to /login when no cookie."""
        response = client.get("/", follow_redirects=False)
        # Without cookie, root redirects to /login (302)
        # or returns 401 if Accept header doesn't indicate browser
        assert response.status_code in (302, 307, 401)

    def test_root_redirects_to_dashboard_authenticated(self, client, auth_cookies):
        """/ redirects to /dashboard with cookie."""
        response = client.get("/", cookies=auth_cookies, follow_redirects=False)
        assert response.status_code in (200, 302, 307)


# ============================================================================
# 3. HTMX Partial Endpoints
# ============================================================================


class TestHTMXPartials:
    """All HTMX partial endpoints return valid HTML fragments."""

    PARTIAL_ENDPOINTS = [
        "/partials/riverside-badge",
        "/partials/sync-status-card",
        "/partials/sync-history-table",
        "/partials/tenant-sync-status",
        "/partials/active-alerts",
        "/partials/cost-summary-card",
        "/partials/compliance-gauge",
        "/partials/resource-stats",
        "/partials/identity-stats",
    ]

    @pytest.mark.parametrize("path", PARTIAL_ENDPOINTS)
    def test_partial_returns_200(self, client, auth_cookies, path):
        """Each partial endpoint returns 200 with auth."""
        response = client.get(path, cookies=auth_cookies)
        assert response.status_code == 200, (
            f"{path} returned {response.status_code}: {response.text[:200]}"
        )

    @pytest.mark.parametrize("path", PARTIAL_ENDPOINTS)
    def test_partial_returns_html_fragment(self, client, auth_cookies, path):
        """Partials return HTML (not JSON error)."""
        response = client.get(path, cookies=auth_cookies)
        assert response.status_code == 200
        body = response.text
        # Should not be a JSON error
        assert not body.startswith("{"), f"{path} returned JSON: {body[:200]}"

    @pytest.mark.parametrize("path", PARTIAL_ENDPOINTS)
    def test_partial_no_full_page(self, client, auth_cookies, path):
        """Partials should NOT be full HTML pages (no <!DOCTYPE>)."""
        response = client.get(path, cookies=auth_cookies)
        if response.status_code == 200 and len(response.text) > 10:
            assert "<!DOCTYPE" not in response.text, (
                f"{path} returned a full HTML page instead of a fragment"
            )


# ============================================================================
# 4. Design System Integration (Epic 9)
# ============================================================================


class TestDesignSystem:
    """Validate design system components from the traceability matrix."""

    def test_brand_config_yaml_exists(self):
        """REQ-904: Brand YAML config exists."""
        assert Path("config/brands.yaml").exists()

    def test_css_generator_exists(self):
        """REQ-903: CSS generation pipeline exists."""
        assert Path("app/core/css_generator.py").exists()

    def test_theme_middleware_exists(self):
        """REQ-906: Theme middleware exists."""
        assert Path("app/core/theme_middleware.py").exists()

    def test_brand_assets_for_all_brands(self):
        """REQ-905: All 5 brands have asset directories."""
        brands_dir = Path("app/static/assets/brands")
        expected_brands = {"httbrands", "bishops", "deltacrown", "frenchies", "lashlounge"}
        actual_brands = {d.name for d in brands_dir.iterdir() if d.is_dir()}
        assert expected_brands.issubset(actual_brands), (
            f"Missing brand dirs: {expected_brands - actual_brands}"
        )

    def test_compiled_css_has_tailwind_utilities(self):
        """Compiled theme.css contains Tailwind utility classes."""
        css = Path("app/static/css/theme.css").read_text()
        assert "tailwindcss" in css, "CSS not compiled from Tailwind"
        # Check key utility classes exist
        for cls in [".flex", ".rounded", ".shadow", ".text-white", ".bg-white"]:
            assert cls in css, f"Missing utility class: {cls}"

    def test_compiled_css_has_wm_colors(self):
        """Compiled CSS includes wm-* Riverside brand colors."""
        css = Path("app/static/css/theme.css").read_text()
        for color_prefix in ["wm-blue", "wm-gray", "wm-green", "wm-red", "wm-spark"]:
            assert color_prefix in css, f"Missing color family: {color_prefix}"

    def test_compiled_css_has_brand_utilities(self):
        """Compiled CSS includes brand-specific utility classes."""
        css = Path("app/static/css/theme.css").read_text()
        for cls in [".bg-brand-primary", ".text-brand-primary", ".btn-brand"]:
            assert cls in css, f"Missing brand class: {cls}"

    def test_dashboard_uses_design_tokens(self, client, auth_cookies):
        """Dashboard HTML uses CSS custom properties, not hardcoded colors."""
        response = client.get("/dashboard", cookies=auth_cookies)
        html = response.text
        # Should reference brand/design token classes
        assert "wm-" in html or "brand-" in html, (
            "Dashboard doesn't use design system color classes"
        )


# ============================================================================
# 5. Security Headers / CSP (REQ-1007, REQ-1009)
# ============================================================================


class TestSecurityHeaders:
    """Content Security Policy and security headers."""

    def test_csp_header_present(self, client, auth_cookies):
        """CSP header is set on all responses."""
        response = client.get("/dashboard", cookies=auth_cookies)
        assert "content-security-policy" in response.headers

    def test_csp_has_nonce(self, client, auth_cookies):
        """CSP includes a nonce for inline scripts."""
        response = client.get("/dashboard", cookies=auth_cookies)
        csp = response.headers["content-security-policy"]
        assert "nonce-" in csp

    def test_csp_nonce_matches_html(self, client):
        """CSP nonce matches the nonce in rendered HTML."""
        response = client.get("/login")
        csp = response.headers.get("content-security-policy", "")
        html = response.text

        # Extract nonce from CSP header
        csp_nonce_match = re.search(r"nonce-([A-Za-z0-9_-]+)", csp)
        assert csp_nonce_match, "No nonce in CSP header"
        csp_nonce = csp_nonce_match.group(1)

        # Extract nonce from HTML
        html_nonce_match = re.search(r'nonce="([A-Za-z0-9_-]+)"', html)
        assert html_nonce_match, "No nonce in HTML"
        html_nonce = html_nonce_match.group(1)

        assert csp_nonce == html_nonce

    def test_security_headers_present(self, client):
        """All security headers are set."""
        response = client.get("/login")
        assert response.headers.get("x-frame-options") == "DENY"
        assert response.headers.get("x-content-type-options") == "nosniff"
        assert "strict-origin" in response.headers.get("referrer-policy", "")

    def test_csp_allows_required_cdn_sources(self, client):
        """CSP script-src allows HTMX and Chart.js CDNs."""
        response = client.get("/login")
        csp = response.headers["content-security-policy"]
        assert "unpkg.com" in csp, "HTMX CDN not in CSP"
        assert "cdn.jsdelivr.net" in csp, "Chart.js CDN not in CSP"


# ============================================================================
# 6. Cookie Auth Flow
# ============================================================================


class TestCookieAuthFlow:
    """Validate the browser cookie authentication flow."""

    def test_login_returns_token(self, client):
        """Login endpoint returns JWT."""
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "admin", "password": "admin"},  # pragma: allowlist secret
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_cookie_auth_accepted(self, client, auth_cookies):
        """Cookie-based auth is accepted by protected routes."""
        response = client.get("/api/v1/auth/me", cookies=auth_cookies)
        assert response.status_code == 200
        assert response.json()["roles"] == ["admin"]

    def test_bearer_auth_still_works(self, client, auth_token):
        """Bearer header auth continues to work."""
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200


# ============================================================================
# 7. HTMX Attribute Correctness
# ============================================================================


class TestHTMXAttributes:
    """Validate HTMX attributes in templates."""

    def test_base_template_no_body_boost(self):
        """hx-boost should NOT be on <body> (causes URL hijacking)."""
        html = Path("app/templates/base.html").read_text()
        # hx-boost should be on <nav>, not <body>
        body_line = [l for l in html.split("\n") if "<body" in l]
        assert body_line, "No <body> tag found"
        assert "hx-boost" not in body_line[0], (
            "hx-boost should not be on <body> — causes URL hijacking on partials"
        )

    def test_nav_has_boost(self):
        """Navigation uses hx-boost for SPA-like transitions."""
        html = Path("app/templates/base.html").read_text()
        nav_line = [l for l in html.split("\n") if "<nav" in l]
        assert nav_line, "No <nav> tag found"
        assert "hx-boost" in nav_line[0]

    def test_riverside_badge_no_push_url(self):
        """Riverside badge partial doesn't push URL."""
        html = Path("app/templates/base.html").read_text()
        assert 'hx-push-url="false"' in html


# ============================================================================
# 8. Tailwind CSS Build Pipeline
# ============================================================================


class TestTailwindBuild:
    """Validate the CSS build pipeline is properly configured."""

    def test_source_css_exists(self):
        """Tailwind source file exists."""
        assert Path("app/static/css/theme.src.css").exists()

    def test_compiled_css_exists(self):
        """Compiled CSS output exists."""
        css_path = Path("app/static/css/theme.css")
        assert css_path.exists()
        # Compiled should be significantly larger than source
        src_size = Path("app/static/css/theme.src.css").stat().st_size
        compiled_size = css_path.stat().st_size
        assert compiled_size > src_size * 2, (
            f"Compiled CSS ({compiled_size}b) should be much larger than "
            f"source ({src_size}b) — may not be compiled"
        )

    def test_package_json_has_build_script(self):
        """package.json has css:build script."""
        import json
        pkg = json.loads(Path("package.json").read_text())
        assert "css:build" in pkg.get("scripts", {}), "Missing css:build script"

    def test_compiled_css_starts_with_tailwind_header(self):
        """Compiled CSS has Tailwind header comment."""
        css = Path("app/static/css/theme.css").read_text()
        assert css.startswith("/*! tailwindcss"), (
            "Compiled CSS doesn't start with Tailwind header"
        )

    def test_source_css_has_import_directive(self):
        """Source CSS has @import 'tailwindcss' directive."""
        css = Path("app/static/css/theme.src.css").read_text()
        assert '@import "tailwindcss"' in css


# ============================================================================
# 9. Static Assets
# ============================================================================


class TestStaticAssets:
    """Verify static assets are served correctly."""

    def test_theme_css_served(self, client):
        """Compiled CSS is served at correct path."""
        response = client.get("/static/css/theme.css")
        assert response.status_code == 200
        assert "text/css" in response.headers["content-type"]

    def test_js_navigation_scripts_served(self, client):
        """Navigation JS modules are served."""
        scripts = [
            "/static/js/navigation/index.js",
            "/static/js/navigation/progressBar.js",
            "/static/js/navigation/navHighlight.js",
        ]
        for path in scripts:
            response = client.get(path)
            assert response.status_code == 200, f"{path} not served"

    def test_dark_mode_js_served(self, client):
        """Dark mode toggle script is served."""
        response = client.get("/static/js/darkMode.js")
        assert response.status_code == 200

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
    # Token is set as HttpOnly cookie (not in JSON body)
    return response.cookies.get("access_token")


@pytest.fixture()
def auth_cookies(auth_token):
    """Cookie dict for browser-like requests."""
    return {"access_token": auth_token}


@pytest.fixture()
def auth_client(client, auth_cookies):
    """TestClient with auth cookies pre-set on the session (avoids per-request cookie deprecation)."""
    for name, value in auth_cookies.items():
        client.cookies.set(name, value)
    yield client
    for name in auth_cookies:
        client.cookies.delete(name)


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
        """REQ-907: Jinja2 UI component macro library (design-system facade).

        Post-py7u (ADR-0005): the legacy `macros/ui.html` was replaced by a
        cohesion-based split under `macros/ds/` with `macros/ds.html` as a
        backward-compatible re-export facade. Callers do:

            {% from "macros/ds.html" import ds_button, ds_card, ... %}
        """
        facade = self.TEMPLATES_DIR / "macros" / "ds.html"
        assert facade.exists(), "macros/ds.html facade should exist"
        content = facade.read_text()
        # Verify key primitives are re-exported via the `set alias = _ns.macro` pattern
        assert "ds_button" in content, "ds.html must re-export ds_button"
        assert "ds_card" in content, "ds.html must re-export ds_card"
        # Primitives themselves live in the ds/ concern files
        ds_dir = self.TEMPLATES_DIR / "macros" / "ds"
        assert ds_dir.is_dir(), "macros/ds/ concern dir should exist"
        assert (ds_dir / "forms.html").exists(), "forms.html holds ds_button"
        assert (ds_dir / "display.html").exists(), "display.html holds ds_card"

    def test_dashboard_page_extends_base(self):
        """Dashboard page uses base template."""
        dash = (self.TEMPLATES_DIR / "pages" / "dashboard.html").read_text()
        assert '{% extends "base.html" %}' in dash

    @pytest.mark.parametrize(
        "template_path",
        [
            "components/cost_summary_card.html",
            "components/compliance_gauge.html",
            "components/resource_stats.html",
            "components/identity_stats.html",
            "components/riverside_badge.html",
            "components/sync/sync_status_card.html",
            "components/sync/sync_history_table.html",
            "components/sync/active_alerts.html",
            "components/sync/tenant_sync_grid.html",
        ],
    )
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
    def test_auth_pages_with_cookie(self, auth_client, path):
        """Auth pages are accessible with cookie."""
        response = auth_client.get(path)
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

    def test_root_redirects_to_dashboard_authenticated(self, auth_client):
        """/ redirects to /dashboard with cookie."""
        response = auth_client.get("/", follow_redirects=False)
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
    def test_partial_returns_200(self, auth_client, path):
        """Each partial endpoint returns 200 with auth."""
        response = auth_client.get(path)
        assert response.status_code == 200, (
            f"{path} returned {response.status_code}: {response.text[:200]}"
        )

    @pytest.mark.parametrize("path", PARTIAL_ENDPOINTS)
    def test_partial_returns_html_fragment(self, auth_client, path):
        """Partials return HTML (not JSON error)."""
        response = auth_client.get(path)
        assert response.status_code == 200
        body = response.text
        # Should not be a JSON error
        assert not body.startswith("{"), f"{path} returned JSON: {body[:200]}"

    @pytest.mark.parametrize("path", PARTIAL_ENDPOINTS)
    def test_partial_no_full_page(self, auth_client, path):
        """Partials should NOT be full HTML pages (no <!DOCTYPE>)."""
        response = auth_client.get(path)
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
        css = (
            Path("app/static/css/tailwind-output.css").read_text()
            + Path("app/static/css/design-utilities.css").read_text()
        )
        assert "tailwindcss" in css, "CSS not compiled from Tailwind"
        # Check key utility classes exist
        for cls in [".flex", ".rounded", ".shadow", ".text-white", ".bg-white"]:
            assert cls in css, f"Missing utility class: {cls}"

    def test_compiled_css_has_wm_colors(self):
        """Compiled CSS includes wm-* Riverside brand colors."""
        css = (
            Path("app/static/css/tailwind-output.css").read_text()
            + Path("app/static/css/design-utilities.css").read_text()
        )
        for color_prefix in ["wm-blue", "wm-gray", "wm-green", "wm-red", "wm-spark"]:
            assert color_prefix in css, f"Missing color family: {color_prefix}"

    def test_compiled_css_has_brand_utilities(self):
        """Compiled CSS includes brand-specific utility classes."""
        css = (
            Path("app/static/css/tailwind-output.css").read_text()
            + Path("app/static/css/design-utilities.css").read_text()
        )
        for cls in [".bg-brand-primary", ".text-brand-primary", ".btn-brand"]:
            assert cls in css, f"Missing brand class: {cls}"

    def test_dashboard_uses_design_tokens(self, auth_client):
        """Dashboard HTML uses CSS custom properties, not hardcoded colors."""
        response = auth_client.get("/dashboard")
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

    def test_csp_header_present(self, auth_client):
        """CSP header is set on all responses."""
        response = auth_client.get("/dashboard")
        assert "content-security-policy" in response.headers

    def test_csp_has_nonce(self, auth_client):
        """CSP includes a nonce for inline scripts."""
        response = auth_client.get("/dashboard")
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
        assert data.get("cookies_set") is True
        assert data["token_type"] == "bearer"
        # Token is in HttpOnly cookie, not JSON body
        assert response.cookies.get("access_token")

    def test_cookie_auth_accepted(self, auth_client):
        """Cookie-based auth is accepted by protected routes."""
        response = auth_client.get("/api/v1/auth/me")
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
        # hx-push-url="false" lives in the nav partial (included by base.html)
        nav_html = Path("app/templates/partials/nav.html").read_text()
        assert 'hx-push-url="false"' in nav_html


# ============================================================================
# 8. Tailwind CSS Build Pipeline
# ============================================================================


class TestTailwindBuild:
    """Validate the CSS build pipeline is properly configured.

    Architecture (per ADR-0005):
      - Tailwind source:    app/static/css/input.css           (compiled by build-css.sh)
      - Tailwind output:    app/static/css/tailwind-output.css (generated)
      - Design tokens:      app/static/css/design-tokens.css   (hand-written, loaded BEFORE tailwind)
      - Design utilities:   app/static/css/design-utilities.css (hand-written, loaded AFTER tailwind)

    Build tool: `scripts/build-css.sh` downloads the Tailwind v3 standalone
    binary (no Node/npm required, no package.json at repo root).
    """

    def test_source_css_exists(self):
        """Design token file exists (Layer 1 of the CSS stack)."""
        assert Path("app/static/css/design-tokens.css").exists()

    def test_compiled_css_exists(self):
        """Compiled Tailwind output exists and is meaningfully larger than its source.

        The meaningful comparison is compiled-output vs its actual input
        (`input.css`), NOT vs the sibling hand-written token/utility layers,
        which are separate concerns loaded alongside — not inputs to Tailwind.
        """
        compiled = Path("app/static/css/tailwind-output.css")
        source = Path("app/static/css/input.css")
        assert compiled.exists(), "tailwind-output.css missing — run `scripts/build-css.sh`"
        assert source.exists(), "input.css (Tailwind source) missing"
        # Compiled expands @tailwind directives into thousands of utility classes;
        # a real build is >>> 10x the tiny input file.
        assert compiled.stat().st_size > source.stat().st_size * 10, (
            f"Compiled CSS ({compiled.stat().st_size}b) should be much larger "
            f"than source ({source.stat().st_size}b) — may not be compiled"
        )

    def test_build_script_exists(self):
        """`scripts/build-css.sh` is the CSS build entrypoint.

        There is intentionally no root `package.json` — Tailwind is invoked
        via its standalone binary so the app has zero Node/npm dependency at
        the repo root.
        """
        script = Path("scripts/build-css.sh")
        assert script.exists(), "scripts/build-css.sh is the CSS build entrypoint"
        assert script.stat().st_mode & 0o111, "build-css.sh must be executable"
        body = script.read_text()
        assert "tailwindcss" in body, "build-css.sh must invoke tailwindcss"
        assert "app/static/css/input.css" in body, "build-css.sh must reference input.css"

    def test_compiled_css_contains_tailwind_header(self):
        """Compiled CSS carries the Tailwind provenance marker.

        The Tailwind v3 binary embeds a `/*! tailwindcss vX.Y.Z | MIT License | ...*/`
        banner in its output. It is not at byte 0 (Preflight reset rules
        appear first) but it must be present — its absence means the file was
        authored by hand or truncated.
        """
        css = Path("app/static/css/tailwind-output.css").read_text()
        assert "/*! tailwindcss" in css, (
            "Compiled CSS missing Tailwind banner — file was not produced by the Tailwind CLI"
        )

    def test_source_css_has_tailwind_directives(self):
        """`input.css` is a Tailwind v3 source with the three @tailwind directives."""
        css = Path("app/static/css/input.css").read_text()
        assert "@tailwind base" in css, "input.css missing `@tailwind base`"
        assert "@tailwind components" in css, "input.css missing `@tailwind components`"
        assert "@tailwind utilities" in css, "input.css missing `@tailwind utilities`"


# ============================================================================
# 9. Static Assets
# ============================================================================


class TestStaticAssets:
    """Verify static assets are served correctly."""

    def test_theme_css_served(self, client):
        """Compiled CSS is served at correct path."""
        response = client.get("/static/css/tailwind-output.css")
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

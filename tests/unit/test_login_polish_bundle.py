"""Regression tests for ct-tdu (login polish bundle).

Items covered (in order from the bug):
  1. Login card centered (already fixed pre-bundle; verified static)
  2. Favicon link present in head
  3. Semantic landmarks (<main>, <footer>) — WCAG 1.3.1, 2.4.1
  4. Meta theme-color + OG + Twitter cards
  5. Branded 404 HTML for browsers, JSON for API clients
  6. Meta description present
  7. MS button has a visible focus ring (amber, not the same as bg)
  8. /login 301-redirects to canonical /auth/login (query string preserved)
  9. Version stamp wrapped in <footer>
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

LOGIN_HTML = (Path(__file__).resolve().parents[2] / "app" / "templates" / "login.html").read_text()

BASE_HTML = (Path(__file__).resolve().parents[2] / "app" / "templates" / "base.html").read_text()


# ── Static template assertions ────────────────────────────────────────


def test_login_has_main_landmark():
    """Item 3: WCAG 1.3.1 / 2.4.1 — must have a <main> landmark."""
    assert "<main" in LOGIN_HTML and "</main>" in LOGIN_HTML


def test_login_has_footer_for_version_stamp():
    """Item 9: version stamp must be in <footer>, not loose <p>."""
    assert "<footer" in LOGIN_HTML and "HTT Control Tower v" in LOGIN_HTML
    # And the version stamp must be INSIDE the footer.
    footer_block = LOGIN_HTML.split("<footer", 1)[1].split("</footer>", 1)[0]
    assert "HTT Control Tower v" in footer_block


def test_login_has_favicon_link():
    """Item 2: favicon ref in head (no more blank tab icon, no /favicon.ico 404)."""
    assert "favicon.svg" in LOGIN_HTML


def test_login_has_theme_color_and_og_tags():
    """Item 4: meta theme-color + Open Graph + Twitter card for social previews."""
    for needle in (
        'name="theme-color"',
        'property="og:title"',
        'property="og:description"',
        'property="og:type"',
        'name="twitter:card"',
    ):
        assert needle in LOGIN_HTML, f"ct-tdu: missing {needle!r} in login.html"


def test_login_has_meta_description():
    """Item 6: meta description must be present."""
    assert 'name="description"' in LOGIN_HTML


def test_login_title_uses_platform_name_not_wrong_brand():
    """Title used to say 'Login - Riverside Capital PE Governance' — wrong brand
    for the HTT Control Tower deployment. ct-tdu fixed it.
    """
    assert "<title>Sign in — HTT Control Tower</title>" in LOGIN_HTML
    assert "Riverside Capital PE Governance" not in LOGIN_HTML


def test_ms_button_has_visible_focus_ring():
    """Item 7: focus ring must be a contrasting color (amber), not same as bg."""
    # We look for the focus-visible:ring-amber-* utility on the button.
    btn_block = LOGIN_HTML.split('id="azure-login-btn"', 1)[1].split("</button>", 1)[0]
    assert "focus-visible:ring" in btn_block, "ct-tdu: MS button must have a focus-visible ring"
    assert "amber" in btn_block, (
        "ct-tdu: focus ring color must be amber (high contrast vs both the dark "
        "button background AND the white card behind it)"
    )


def test_base_html_has_favicon_for_all_pages():
    """ct-tdu: every page rendered through base.html should also get the favicon."""
    assert "favicon.svg" in BASE_HTML
    assert 'name="theme-color"' in BASE_HTML


# ── Runtime behavior assertions ──────────────────────────────────────


def test_legacy_login_301_redirects_to_canonical():
    """Item 8: /login → 301 → /auth/login (single canonical URL)."""
    client = TestClient(app, follow_redirects=False)
    r = client.get("/login")
    assert r.status_code == 301, f"ct-tdu: /login must be a permanent redirect; got {r.status_code}"
    assert r.headers["location"].endswith("/auth/login")


def test_legacy_login_preserves_query_string_through_redirect():
    """The ?next= param must survive the 301 hop or post-login redirect breaks."""
    client = TestClient(app, follow_redirects=False)
    r = client.get("/login?next=/costs")
    assert r.status_code == 301
    assert "next=/costs" in r.headers["location"], (
        f"ct-tdu: query string must be preserved through 301; "
        f"location was {r.headers['location']!r}"
    )


def test_canonical_login_returns_html_with_landmarks():
    """/auth/login renders the polished template."""
    client = TestClient(app)
    r = client.get("/auth/login")
    assert r.status_code == 200
    assert "<main" in r.text and "</main>" in r.text
    assert "<footer" in r.text


def test_404_html_for_browser_clients():
    """Item 5: browsers (text/html accept) get a branded HTML 404, not raw JSON."""
    client = TestClient(app)
    r = client.get("/this-path-does-not-exist", headers={"Accept": "text/html"})
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("text/html"), (
        f"ct-tdu: browser 404 must serve HTML, got {r.headers['content-type']}"
    )
    assert "HTT Control Tower" in r.text
    assert "<main" in r.text  # branded 404 has its own landmark too
    assert 'href="/"' in r.text  # back-to-dashboard CTA


def test_404_json_for_api_clients():
    """API clients (JSON accept) keep the existing {'detail': ...} shape."""
    client = TestClient(app)
    r = client.get("/this-path-does-not-exist", headers={"Accept": "application/json"})
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")
    assert r.json() == {"detail": "Not Found"}


def test_favicon_svg_is_served():
    """Favicon must actually be reachable, not just linked in HTML."""
    client = TestClient(app)
    r = client.get("/static/favicon.svg")
    assert r.status_code == 200
    assert r.headers["content-type"] in (
        "image/svg+xml",
        "image/svg+xml; charset=utf-8",
    )
    assert r.text.startswith("<?xml") or r.text.lstrip().startswith("<svg") or "<svg" in r.text

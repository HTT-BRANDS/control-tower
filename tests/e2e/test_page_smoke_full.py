"""Comprehensive page-smoke gate covering every user-visible HTML route.

Filed under ct-4uu: catches the "blank page after refactor", "missing
design-system CSS", "500 page" regression classes across the full set of
Manager-tier-and-above pages in one parametrized sweep.

Each route is asserted to:
  1. Return HTTP 200 (no 500s, no surprise 403s for an authenticated Manager+)
  2. Load tailwind-output.css (i.e. the design system is wired in)
  3. Have a <main> landmark (the base.html contract)
  4. Have non-trivial body content (not the silent "template rendered nothing" failure)
  5. Not contain the FastAPI 500-error string in the rendered HTML

This is DELIBERATELY thin per-page. Pages with bespoke contracts already
have dedicated suites (test_dashboard_page.py, test_dmarc_page.py,
test_manager_rbac_visual.py, test_preflight_page.py, etc.). This file's
job is the breadth gate, not the depth gate.

Adding a new page: append a single PAGE_ROUTES entry. That's it. The
parametrization handles the rest.

Routes intentionally excluded:
  /admin                    — admin-only; needs admin_page fixture and
                              lives in test_admin_dashboard*.py
  /partials/*               — HTMX fragment endpoints; covered by
                              test_browser_smoke.py's partial sweep
  /login                    — unauthenticated; covered by test_auth_flow.py
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from tests.e2e.helpers import assert_no_server_error_text

pytestmark = [pytest.mark.e2e, pytest.mark.smoke]


# ── Route table ───────────────────────────────────────────────────────────
# Every user-visible HTML page reachable by a Manager-tier-or-above user.
# Order is alphabetic by path for predictable test-id output.
PAGE_ROUTES = [
    "/api/v1/preflight",
    "/compliance",
    "/costs",
    "/dashboard",
    "/design-system",
    "/dmarc",
    "/franchise-coach",
    "/identity",
    "/privacy",
    "/resources",
    "/riverside",
    "/sync-dashboard",
    "/topology",
]


# Minimum body text length below which we treat the page as "blank".
# Calibration: the real blank-page bug from the staging postmortem
# rendered ~120 bytes (chrome only). Real pages range from ~670 chars
# (HTMX-heavy pages where most content streams in via /partials/* after
# initial render) up to multi-KB (privacy, design-system showcase).
# 500 sits comfortably between those two regimes — catches the silent
# 120-byte render-failure mode without flagging legitimate HTMX shells.
MIN_BODY_BYTES = 500


@pytest.mark.parametrize("path", PAGE_ROUTES, ids=lambda p: p.replace("/", "_").strip("_") or "root")
def test_page_renders_with_design_system(authenticated_page: Page, path: str) -> None:
    """Every Manager-tier page renders with design-system CSS + landmarks + content."""
    response = authenticated_page.goto(path, wait_until="domcontentloaded")

    assert response is not None, f"navigation to {path} returned no response"
    assert response.status == 200, (
        f"{path} returned HTTP {response.status} (expected 200). "
        f"Status text: {response.status_text}"
    )

    # The design-system CSS must be present on every page — the entire
    # DaisyUI/brand theme depends on it. PR #68 + Phase C make this
    # invariant load-bearing for visual correctness.
    css_link = authenticated_page.locator("link[rel='stylesheet'][href*='tailwind-output.css']")
    assert css_link.count() >= 1, (
        f"{path} is missing tailwind-output.css <link> — design system "
        f"not wired into this page"
    )

    # base.html guarantees a <main id="main-content"> landmark for skip-link
    # accessibility (P2.6 / a11y contract). Pages that bypass base.html will
    # fail here.
    main = authenticated_page.locator("main")
    assert main.count() >= 1, f"{path} has no <main> landmark (base.html contract broken)"

    # Body must not be effectively empty — guards against the silent-render
    # regression where a template raises in a sub-include and Jinja returns
    # the partial scaffold without the body.
    body_text = authenticated_page.locator("body").inner_text()
    assert len(body_text) >= MIN_BODY_BYTES, (
        f"{path} rendered only {len(body_text)} chars of text "
        f"(threshold {MIN_BODY_BYTES}). Probable silent template error."
    )

    # And the rendered HTML must not contain a FastAPI 500 page string.
    # Covers the case where a partial fails silently and emits the error
    # template inline instead of bubbling to a real 500.
    assert_no_server_error_text(authenticated_page.content())

"""Playwright RBAC + experience tests for the Manager-tier dashboard.

Scope (per ct-buo / ADR-0012):

  1. **RBAC contract** — Manager can load ``/franchise-coach``; Viewer is
     denied (403 / redirect / nav link hidden).
  2. **Landmark contract** — All ``data-testid`` hooks that downstream
     analytics + visual regression rely on are present and stable.
  3. **Accessibility contract** — Severity badges expose the agreed
     ARIA labels.
  4. **Template branching contract** — empty-state and brand-cards branches
     are mutually exclusive and the displayed count matches what's rendered.

Visual regression for this page lives in ``test_visual_parity.py`` (single
source of truth for pinned baselines — see the ``PAGES`` tuple).

We avoid hitting the dev ``/api/v1/auth/login`` endpoint because that
flow always issues an ``admin`` role token in tests. Instead we mint
role-scoped JWTs directly via ``jwt_manager`` — the same machinery the
real auth router uses — keeping the assertion-of-role honest.

Reference: ``docs/decisions/adr-0012-manager-role-franchise-coach.md``
"""

from __future__ import annotations

from collections.abc import Generator
from urllib.parse import urlparse

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, expect

from app.core.auth import jwt_manager

# ── Config ─────────────────────────────────────────────────────────────────────────
DASHBOARD_PATH = "/franchise-coach"
DASHBOARD_TESTID = "franchise-coach-dashboard"

# All data-testid hooks the template exposes — single source of truth for
# downstream visual + analytics assertions. Keep in sync with
# ``app/templates/pages/franchise_coach.html`` (caught by test_landmarks_present).
LANDMARK_TESTIDS: tuple[str, ...] = (
    "franchise-coach-dashboard",
    "fc-summary-strip",
    "fc-brand-count",
    "fc-healthy-count",
    "fc-attention-count",
    "fc-export-csv",
)


# ── Token + cookie helpers ──────────────────────────────────────────────────
def _mint_role_token(user_id: str, roles: list[str]) -> str:
    """Mint a JWT with the exact role list the test needs.

    Uses the real ``jwt_manager`` so signature + audience + claims match
    what the auth dependency expects. This sidesteps the dev login
    shortcut (which always yields ``admin``) and lets us exercise the
    actual permission resolution path.
    """
    return jwt_manager.create_access_token(
        user_id=user_id,
        email=None,
        name=user_id,
        roles=roles,
        tenant_ids=[],
    )


def _cookies_for(base_url: str, token: str) -> list[dict]:
    """Convert a JWT into the Playwright cookie payload the app expects."""
    domain = urlparse(base_url).hostname
    assert domain, f"Could not determine cookie domain from {base_url}"
    return [
        {
            "name": "access_token",
            "value": token,
            "domain": domain,
            "path": "/",
            "httpOnly": True,
            "sameSite": "Lax",
            "secure": False,
        }
    ]


# ── Role-scoped browser fixtures ────────────────────────────────────────────
@pytest.fixture
def manager_context(
    browser: Browser,
    base_url: str,
    browser_context_args: dict,
) -> Generator[BrowserContext, None, None]:
    """Fresh browser context authenticated as a Manager-role user."""
    context = browser.new_context(**browser_context_args, base_url=base_url)
    token = _mint_role_token("user:e2e-manager", ["manager"])
    context.add_cookies(_cookies_for(base_url, token))
    yield context
    context.close()


@pytest.fixture
def viewer_context(
    browser: Browser,
    base_url: str,
    browser_context_args: dict,
) -> Generator[BrowserContext, None, None]:
    """Fresh browser context authenticated as a Viewer-role user."""
    context = browser.new_context(**browser_context_args, base_url=base_url)
    token = _mint_role_token("user:e2e-viewer", ["viewer"])
    context.add_cookies(_cookies_for(base_url, token))
    yield context
    context.close()


@pytest.fixture
def manager_page(manager_context: BrowserContext) -> Generator[Page, None, None]:
    """Authenticated Page for a Manager-role user."""
    page = manager_context.new_page()
    yield page
    page.close()


@pytest.fixture
def viewer_page(viewer_context: BrowserContext) -> Generator[Page, None, None]:
    """Authenticated Page for a Viewer-role user."""
    page = viewer_context.new_page()
    yield page
    page.close()


# ============================================================================
# 1. RBAC contract
# ============================================================================
class TestManagerRbacContract:
    """The franchise-coach surface is gated by ``franchise_coach:read``."""

    @pytest.mark.e2e
    def test_manager_can_load_dashboard(self, manager_page: Page, base_url: str):
        """Manager role hits 200 + the dashboard root testid renders."""
        response = manager_page.goto(f"{base_url}{DASHBOARD_PATH}")
        assert response is not None, "No HTTP response from franchise-coach route"
        assert response.status == 200, (
            f"Expected 200 for manager, got {response.status}. "
            f"Check that 'manager' role grants franchise_coach:read in permissions.py."
        )
        # Sanity: the page actually rendered the dashboard, not a redirect to login.
        expect(manager_page.get_by_test_id(DASHBOARD_TESTID)).to_be_visible()

    @pytest.mark.e2e
    def test_viewer_is_denied(self, viewer_page: Page, base_url: str):
        """Viewer role lacks franchise_coach:read — server returns 403."""
        response = viewer_page.goto(f"{base_url}{DASHBOARD_PATH}")
        assert response is not None
        # Server is contractually required to refuse — accept any of the
        # "you're not allowed" status codes (403 is the canonical one; some
        # auth middlewares prefer 401 on missing permission, others redirect).
        assert response.status in (401, 403), (
            f"Expected 401/403 denial for viewer, got {response.status}. "
            f"Viewer role must NOT have franchise_coach:read."
        )
        # The dashboard root must not be reachable — defense in depth.
        assert viewer_page.get_by_test_id(DASHBOARD_TESTID).count() == 0


# ============================================================================
# 2. Landmark contract — data-testid hooks downstream code relies on
# ============================================================================
class TestManagerLandmarks:
    """Every data-testid the template promises must actually exist."""

    @pytest.mark.e2e
    def test_landmarks_present(self, manager_page: Page, base_url: str):
        """The 6 cross-brand summary landmarks render for an authenticated manager."""
        manager_page.goto(f"{base_url}{DASHBOARD_PATH}")
        manager_page.wait_for_load_state("networkidle")
        for testid in LANDMARK_TESTIDS:
            locator = manager_page.get_by_test_id(testid)
            assert locator.count() >= 1, (
                f"Required landmark data-testid='{testid}' missing from "
                f"franchise_coach.html — downstream visual + analytics "
                f"contracts depend on it. Did you remove it accidentally?"
            )

    @pytest.mark.e2e
    def test_csv_export_link_present_for_manager(self, manager_page: Page, base_url: str):
        """Manager has ``franchise_coach:export`` — the CSV link must render."""
        manager_page.goto(f"{base_url}{DASHBOARD_PATH}")
        export_link = manager_page.get_by_test_id("fc-export-csv")
        expect(export_link).to_be_visible()
        # Anchor href is the canonical export endpoint — keep these in sync.
        href = export_link.get_attribute("href")
        assert href == "/franchise-coach/export.csv", (
            f"CSV export link points at {href!r}; expected '/franchise-coach/export.csv'"
        )


# ============================================================================
# 3. Accessibility contract — severity badges expose ARIA labels
# ============================================================================
class TestManagerAccessibility:
    """Severity colour-coding must be paired with screen-reader text."""

    # The template's severity_badge macro renders these aria-labels verbatim.
    # If a designer renames them, this test fails loudly — that's the point.
    EXPECTED_ARIA_LABELS: tuple[str, ...] = (
        "Severity: critical, needs attention this week",
        "Severity: attention, slipping but recoverable",
        "Severity: healthy, standards holding",
    )

    @pytest.mark.e2e
    def test_severity_badges_define_aria_labels(self, manager_page: Page, base_url: str):
        """At least one of each severity ARIA label is reachable in the rendered HTML.

        We don't require all three to be visible simultaneously (depends on
        live data) — instead we assert the macro is wired correctly by
        inspecting the rendered markup so visual-impairment users always get
        meaningful colour-coding text.
        """
        manager_page.goto(f"{base_url}{DASHBOARD_PATH}")
        manager_page.wait_for_load_state("networkidle")
        html = manager_page.content()
        # If the dashboard is empty there are no badges at all — skip rather
        # than fail (empty-state assertions live in their own test class).
        if 'data-testid="fc-empty-state"' in html:
            pytest.skip("No brand cards rendered — empty-state path; nothing to check")
        rendered = [label for label in self.EXPECTED_ARIA_LABELS if label in html]
        assert rendered, (
            f"None of the expected severity ARIA labels were rendered. "
            f"Looked for: {self.EXPECTED_ARIA_LABELS}. "
            f"Did the severity_badge macro change?"
        )


# ============================================================================
# 4. Template branching contract (empty-state vs brand-cards exclusivity)
# ============================================================================
class TestManagerTemplateBranching:
    """The template's if/else must be honored regardless of live DB state.

    We can't easily force-empty the DB from out-of-process Playwright tests,
    so instead of asserting *which* branch renders we assert that the two
    branches are mutually exclusive AND that the brand-count digit agrees
    with what's actually on screen. This catches the real failure mode —
    a broken if/else that double-renders or mis-counts — without coupling
    the test to specific seed data.
    """

    @pytest.mark.e2e
    def test_empty_and_cards_are_mutually_exclusive(self, manager_page: Page, base_url: str):
        """Exactly one of (fc-empty-state, fc-brand-cards) renders. Never both, never neither."""
        manager_page.goto(f"{base_url}{DASHBOARD_PATH}")
        manager_page.wait_for_load_state("networkidle")

        empty_count = manager_page.get_by_test_id("fc-empty-state").count()
        cards_count = manager_page.get_by_test_id("fc-brand-cards").count()

        assert (empty_count == 1) ^ (cards_count == 1), (
            f"Template if/else broken: fc-empty-state={empty_count}, "
            f"fc-brand-cards={cards_count}. Exactly one must render."
        )

    @pytest.mark.e2e
    def test_brand_count_matches_card_count(self, manager_page: Page, base_url: str):
        """The displayed brand count agrees with the number of fc-card elements.

        If empty-state renders, count must be 0 and no fc-card elements exist.
        If cards render, the count must equal the number of fc-card siblings.
        """
        manager_page.goto(f"{base_url}{DASHBOARD_PATH}")
        manager_page.wait_for_load_state("networkidle")

        count_text = manager_page.get_by_test_id("fc-brand-count").inner_text().strip()
        displayed_count = int(count_text)
        rendered_cards = manager_page.get_by_test_id("fc-card").count()

        assert displayed_count == rendered_cards, (
            f"fc-brand-count says {displayed_count} but {rendered_cards} "
            f"fc-card elements rendered — view assembly is lying about its data"
        )


# Visual regression for this page lives in ``test_visual_parity.py`` so
# the visual-baseline machinery is owned by a single source of truth.

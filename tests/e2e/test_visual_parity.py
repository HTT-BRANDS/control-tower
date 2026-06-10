"""Visual parity tests for the 5 design-system-migrated pages (py7u.4).

Compares current Playwright screenshots against pinned PNG baselines in
``tests/e2e/baselines/``. Baselines must be captured first — either from a
reference project (Domain-Intelligence) or from a known-good state of this
app via ``python scripts/capture_visual_baselines.py``.

OPT-IN: these tests only run when the ``visual`` marker is selected::

    uv run pytest -m visual

In default test runs they are deselected, so a missing Pillow wheel or
missing browsers won't break CI. When baselines are missing, each test
skips with a hint pointing at the capture script.

FAILURE ARTIFACTS: when a page exceeds the tolerance threshold, three
PNGs are written to ``tests/e2e/visual_diffs/`` (git-ignored):

  - ``{page}.current.png`` — what Playwright rendered this run
  - ``{page}.baseline.png`` — the pinned reference
  - ``{page}.diff.png``     — pixel-wise difference, for visual review

TOLERANCE: controlled via ``VISUAL_TOLERANCE_PCT`` env var (default 0.5%
of pixels may differ). Small differences routinely occur from font
anti-aliasing, cursor blink, and sub-pixel layout. The default is tuned
to catch real regressions without being chatty.
"""

from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import pytest

# Pillow is only required for visual tests — import lazily so the rest of
# the e2e suite does not pay for it if the user isn't running -m visual.
PIL = pytest.importorskip("PIL", reason="Pillow not installed (install pillow to run visual tests)")
from PIL import Image, ImageChops  # noqa: E402  (import after importorskip)

# ── Config ──────────────────────────────────────────────────────────────────
BASELINE_DIR = Path(__file__).parent / "baselines"
DIFF_DIR = Path(__file__).parent / "visual_diffs"
TOLERANCE_PCT = float(os.getenv("VISUAL_TOLERANCE_PCT", "0.5"))

# Design-system-migrated pages with pinned visual baselines.
# Tuple shape: (baseline-name, url-path, wait-selector)
# The wait-selector is an element guaranteed to exist after HTMX hydration;
# it stabilizes the screenshot (no layout shift mid-capture).
#
# franchise-coach is the Manager-tier surface (ADR-0012). Admin role used
# by ``authenticated_page`` has wildcard permissions so the capture works
# the same way as for the read-only pages; the Manager-specific access
# contract is enforced by ``tests/e2e/test_manager_rbac_visual.py``.
PAGES: list[tuple[str, str, str]] = [
    ("dashboard", "/dashboard", "main"),
    ("costs", "/costs", "main"),
    ("compliance", "/compliance", "main"),
    ("resources", "/resources", "main"),
    ("identity", "/identity", "main"),
    ("franchise-coach", "/franchise-coach", "[data-testid='franchise-coach-dashboard']"),
]


# ── Helpers ─────────────────────────────────────────────────────────────────
def _count_diff_pixels(diff: Image.Image) -> int:
    """Count non-zero pixels in a difference image.

    ImageChops.difference returns per-channel deltas; a pixel is "different"
    if any channel is non-zero. Works for RGB and RGBA.
    """
    # Collapse the per-channel delta into a single band holding the per-pixel
    # MAX across channels (ImageChops.lighter = pixel-wise max). A pixel is
    # "different" iff that max is > 0 — identical semantics to the old
    # any-channel-nonzero check, but vectorised and without the deprecated
    # per-pixel getdata() walk (removed in Pillow 14).
    bands = diff.split()
    combined = bands[0]
    for band in bands[1:]:
        combined = ImageChops.lighter(combined, band)
    histogram = combined.histogram()
    # histogram[0] = pixels with zero delta; everything above is a difference.
    return sum(histogram[1:])


def _save_artifacts(
    page_name: str,
    current: Image.Image,
    baseline: Image.Image,
    diff: Image.Image | None,
) -> Path:
    """Persist before/after/diff PNGs for the failing page. Returns the dir."""
    DIFF_DIR.mkdir(parents=True, exist_ok=True)
    current.save(DIFF_DIR / f"{page_name}.current.png")
    baseline.save(DIFF_DIR / f"{page_name}.baseline.png")
    if diff is not None:
        # Amplify the diff so visual review is easier (subtle differences
        # are otherwise invisible to the human eye).
        amplified = diff.point(lambda x: min(255, x * 10))
        amplified.save(DIFF_DIR / f"{page_name}.diff.png")
    return DIFF_DIR


# ── Tests ───────────────────────────────────────────────────────────────────
@pytest.mark.visual
@pytest.mark.e2e
@pytest.mark.parametrize(
    ("page_name", "path", "wait_selector"),
    PAGES,
    ids=[p[0] for p in PAGES],
)
def test_page_matches_visual_baseline(
    authenticated_page,
    page_name: str,
    path: str,
    wait_selector: str,
) -> None:
    """Each migrated page should match its pinned visual baseline.

    Baseline lifecycle:
      * VISUAL_UPDATE=1 -> this test writes the current screenshot AS the
        baseline and passes (the "blessing" path). Capturing through the exact
        same browser context that does the comparison is essential: a baseline
        captured by a *different* context (e.g. a standalone script) drifts at
        the sub-pixel level (font hinting / deviceScaleFactor), producing a
        uniform text-ghosting diff on every run. This is the same pattern as
        Playwright's --update-snapshots.
      * No baseline present and VISUAL_UPDATE unset -> skip with a hint.
      * Baseline present -> compare within VISUAL_TOLERANCE_PCT.
    """
    baseline_path = BASELINE_DIR / f"{page_name}.png"
    update_mode = os.getenv("VISUAL_UPDATE") == "1"
    if not baseline_path.exists() and not update_mode:
        pytest.skip(
            f"No baseline for {page_name!r} at {baseline_path.relative_to(Path.cwd())}. "
            f"Bless baselines via: VISUAL_UPDATE=1 pytest -m visual"
        )

    # --- suppress the GDPR/CCPA consent banner ---
    # The banner renders only when the 'consent_preferences' cookie is absent,
    # and when shown it pushes all page content down by 5-20px — corrupting the
    # full-page baseline (height mismatch + cascading text ghosting). Seeding a
    # dismissed-consent cookie keeps the layout deterministic. This MUST match
    # the suppression in scripts/capture_visual_baselines.py.
    _host = urlparse(authenticated_page._base_url).hostname or "127.0.0.1"  # type: ignore[attr-defined]
    authenticated_page.context.add_cookies(
        [{"name": "consent_preferences", "value": "all", "domain": _host, "path": "/"}]
    )

    # --- navigate and stabilize the page ---
    authenticated_page.goto(path)
    authenticated_page.wait_for_selector(wait_selector, timeout=10_000)
    # NB: we wait for 'load', not 'networkidle'. These dashboards use HTMX
    # background polling, so the network never goes idle and 'networkidle'
    # would hang until timeout. The readiness selector above already proves
    # the page hydrated; the fixed buffer covers CSS transitions / font swaps.
    # This MUST match the wait strategy in scripts/capture_visual_baselines.py
    # or the screenshots will differ from the baselines.
    authenticated_page.wait_for_load_state("load")
    authenticated_page.wait_for_timeout(1_000)

    # --- capture current state ---
    current_bytes = authenticated_page.screenshot(full_page=True)
    current_img = Image.open(BytesIO(current_bytes)).convert("RGB")

    # --- blessing path: write the baseline and pass ---
    if update_mode:
        BASELINE_DIR.mkdir(parents=True, exist_ok=True)
        current_img.save(baseline_path)
        size_kb = baseline_path.stat().st_size // 1024
        print(f"\n  blessed baseline: {baseline_path.name} ({size_kb} KB)")
        return

    baseline_img = Image.open(baseline_path).convert("RGB")

    # --- size check first (cheap, fails fast on layout changes) ---
    if current_img.size != baseline_img.size:
        _save_artifacts(page_name, current_img, baseline_img, None)
        pytest.fail(
            f"{page_name}: viewport size mismatch — "
            f"current {current_img.size} vs baseline {baseline_img.size}. "
            f"Artifacts saved to {DIFF_DIR.relative_to(Path.cwd())}/"
        )

    # --- pixel diff ---
    diff_img = ImageChops.difference(current_img, baseline_img)
    if diff_img.getbbox() is None:
        return  # pixel-perfect match — the happy path

    diff_pixels = _count_diff_pixels(diff_img)
    total_pixels = current_img.size[0] * current_img.size[1]
    diff_pct = 100.0 * diff_pixels / total_pixels

    if diff_pct > TOLERANCE_PCT:
        _save_artifacts(page_name, current_img, baseline_img, diff_img)
        pytest.fail(
            f"{page_name}: {diff_pct:.3f}% of pixels differ "
            f"(tolerance {TOLERANCE_PCT}%, {diff_pixels:,}/{total_pixels:,} pixels). "
            f"Artifacts saved to {DIFF_DIR.relative_to(Path.cwd())}/ — "
            f"inspect {page_name}.diff.png to review."
        )

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
    return sum(
        1 for px in diff.getdata() if any(c > 0 for c in (px if isinstance(px, tuple) else (px,)))
    )


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

    If no baseline exists for a page, the test skips with a hint. The first
    time you run this suite, every page will skip — that is expected.
    Populate baselines via ``scripts/capture_visual_baselines.py``.
    """
    baseline_path = BASELINE_DIR / f"{page_name}.png"
    if not baseline_path.exists():
        pytest.skip(
            f"No baseline for {page_name!r} at {baseline_path.relative_to(Path.cwd())}. "
            f"Run: python scripts/capture_visual_baselines.py"
        )

    # --- navigate and stabilize the page ---
    authenticated_page.goto(path)
    authenticated_page.wait_for_selector(wait_selector, timeout=10_000)
    # networkidle catches HTMX fetches; 500ms buffer lets CSS transitions settle.
    authenticated_page.wait_for_load_state("networkidle")
    authenticated_page.wait_for_timeout(500)

    # --- capture current state ---
    current_bytes = authenticated_page.screenshot(full_page=True)
    current_img = Image.open(BytesIO(current_bytes)).convert("RGB")
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

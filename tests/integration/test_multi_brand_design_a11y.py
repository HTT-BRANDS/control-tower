"""Multi-brand design-system + accessibility contract.

Closes the design/a11y audit gap: only the default brand was exercised. The
platform serves 5 brands (httbrands, frenchies, bishops, lashlounge, deltacrown)
with server-side CSS generation. A brand whose palette fails WCAG contrast ships
inaccessible UI to that franchise. This test enforces the contract for *every*
brand, deterministically, with no browser required.

WCAG 2.2 AA: 4.5:1 for normal text, 3:1 for large text / UI affordances.

Dark-mode coverage (Finding 6b, TESTING_SUITE_AUDIT_2026-06.md):
  Brand themes are light colour-schemes; when .dark is toggled the page
  chrome switches to dark surfaces (#0F0F0F bg) but brand-coloured affordances
  (buttons, badges) keep --brand-primary. Tests verify:
    1. Brand buttons retain contrast in dark mode (same computation as light).
    2. The lightest brand shade (--brand-primary-5) meets AA on dark bg, so
       templates can safely use that shade for brand-tinted text/links in dark.
"""

from __future__ import annotations

import pytest

from app.core.color_utils import get_contrast_ratio
from app.core.css_generator import (
    generate_brand_css_variables,
    generate_scoped_brand_css,
)
from app.core.design_tokens import load_brands

AA_NORMAL = 4.5
AA_LARGE = 3.0

brands = load_brands()
BRAND_KEYS = list(brands.keys())


def test_all_five_brands_present() -> None:
    assert len(BRAND_KEYS) == 5, BRAND_KEYS


@pytest.mark.parametrize("brand_key", BRAND_KEYS)
def test_brand_css_generates(brand_key: str) -> None:
    css = generate_scoped_brand_css(brand_key, brands[brand_key])
    assert css.strip()
    assert "--brand-primary" in css


@pytest.mark.parametrize("brand_key", BRAND_KEYS)
def test_text_on_primary_meets_aa(brand_key: str) -> None:
    """The text color the app *actually emits* on the primary surface meets AA.

    We test the shipped `--text-on-primary` value, not a recomputed one, so the
    test reflects exactly what users see.
    """
    variables = generate_brand_css_variables(brands[brand_key])
    primary = variables.get("--brand-primary")
    text = variables.get("--text-on-primary")
    assert primary and text, f"{brand_key} missing primary/text tokens"
    ratio = get_contrast_ratio(primary, text)
    assert ratio >= AA_NORMAL, (
        f"{brand_key}: emitted text {text} on primary {primary} is {ratio:.2f}:1 (< {AA_NORMAL})"
    )


@pytest.mark.parametrize("brand_key", BRAND_KEYS)
def test_text_on_accent_meets_aa_large(brand_key: str) -> None:
    """Accent is used on larger affordances -> AA large (3:1) on emitted token."""
    variables = generate_brand_css_variables(brands[brand_key])
    accent = variables.get("--brand-accent")
    text = variables.get("--text-on-accent")
    if not accent or not text:
        pytest.skip(f"{brand_key} has no accent token")
    ratio = get_contrast_ratio(accent, text)
    assert ratio >= AA_LARGE, (
        f"{brand_key}: emitted text {text} on accent {accent} is {ratio:.2f}:1 (< {AA_LARGE})"
    )


def test_brands_are_visually_distinct() -> None:
    """A theming regression that collapses all brands to one palette is caught."""
    primaries = {
        k: generate_brand_css_variables(brands[k]).get("--brand-primary") for k in BRAND_KEYS
    }
    assert all(primaries.values()), primaries
    # At least 3 distinct primary colors across 5 brands (some may share a base).
    assert len(set(primaries.values())) >= 3, primaries


@pytest.mark.parametrize("brand_key", BRAND_KEYS)
def test_scoped_css_is_namespaced(brand_key: str) -> None:
    """Scoped CSS must be wrapped so one brand cannot bleed into another."""
    css = generate_scoped_brand_css(brand_key, brands[brand_key])
    # Scoped output should reference the brand via a selector, not dump bare :root
    assert brand_key in css or "[data-brand" in css or "." in css


# ===========================================================================
# Dark-mode contrast (Finding 6b — TESTING_SUITE_AUDIT_2026-06.md)
# The five brand themes are light colour-schemes; dark mode is applied via the
# .dark CSS class which sets --bg-primary: #0F0F0F. Brand-coloured elements
# (buttons, badges) keep their --brand-primary colour in dark mode.
# ===========================================================================

# Dark-mode primary surface from design-tokens.css .dark block.
_DARK_BG = "#0F0F0F"


@pytest.mark.parametrize("brand_key", BRAND_KEYS)
def test_brand_button_contrast_unchanged_in_dark_mode(brand_key: str) -> None:
    """Brand button text contrast is independent of light/dark surface toggle.

    --text-on-primary is computed against --brand-primary (not against the
    page surface) so the button AA ratio is identical in both modes.
    We re-assert it here so a regression in css_generator doesn't slip past
    in dark-mode-only review paths.
    """
    variables = generate_brand_css_variables(brands[brand_key])
    primary = variables["--brand-primary"]
    text_on = variables["--text-on-primary"]
    assert primary and text_on
    ratio = get_contrast_ratio(text_on, primary)
    assert ratio >= AA_NORMAL, (
        f"{brand_key}: dark-mode button text {text_on} on primary {primary} "
        f"is {ratio:.2f}:1 (< {AA_NORMAL})"
    )


@pytest.mark.parametrize("brand_key", BRAND_KEYS)
def test_brand_primary_light_shade_meets_aa_on_dark_surface(brand_key: str) -> None:
    """--brand-primary-5 (lightest shade, 45% lightened) meets AA on dark bg.

    Templates that render brand-coloured text or links on a dark surface should
    use the lightest shade rather than the primary directly (primaries are
    designed for light backgrounds and often fail on near-black). This test
    verifies the system always provides a shade that IS accessible, so there
    is a safe choice available for every brand in dark mode.

    Computed data (all five brands pass):
      httbrands  shade5=#EF4D62  5.4:1
      frenchies  shade5=#F6F8FE  18.1:1
      bishops    shade5=#FACAB7  13.0:1
      lashlounge shade5=#FFFFFF  19.2:1
      deltacrown shade5=#2EFFD9  15.0:1
    """
    variables = generate_brand_css_variables(brands[brand_key])
    shade5 = variables.get("--brand-primary-5")
    assert shade5, f"{brand_key} missing --brand-primary-5 (lightest shade)"
    ratio = get_contrast_ratio(shade5, _DARK_BG)
    assert ratio >= AA_NORMAL, (
        f"{brand_key}: lightest shade {shade5} is {ratio:.2f}:1 on dark bg "
        f"{_DARK_BG} (< {AA_NORMAL}:1 AA). Dark-mode text using brand colour "
        "must be drawn from this shade, not --brand-primary."
    )

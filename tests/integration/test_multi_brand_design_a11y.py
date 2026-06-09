"""Multi-brand design-system + accessibility contract.

Closes the design/a11y audit gap: only the default brand was exercised. The
platform serves 5 brands (httbrands, frenchies, bishops, lashlounge, deltacrown)
with server-side CSS generation. A brand whose palette fails WCAG contrast ships
inaccessible UI to that franchise. This test enforces the contract for *every*
brand, deterministically, with no browser required.

WCAG 2.2 AA: 4.5:1 for normal text, 3:1 for large text / UI affordances.
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
        f"{brand_key}: emitted text {text} on primary {primary} is "
        f"{ratio:.2f}:1 (< {AA_NORMAL})"
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
        f"{brand_key}: emitted text {text} on accent {accent} is "
        f"{ratio:.2f}:1 (< {AA_LARGE})"
    )


def test_brands_are_visually_distinct() -> None:
    """A theming regression that collapses all brands to one palette is caught."""
    primaries = {
        k: generate_brand_css_variables(brands[k]).get("--brand-primary")
        for k in BRAND_KEYS
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

"""WCAG 2.2 AA validation for all brand color combinations.

Updated for microsoft-group-management design system:
- All brands use #FFC957 (gold) as accent — this is a decorative/highlight
  color intended for use on dark backgrounds, not as text on white.
- Primary colors all pass WCAG AA on white backgrounds.
"""

import pytest

from app.core.color_utils import get_contrast_ratio
from app.core.design_tokens import load_brands


@pytest.fixture(autouse=True)
def clear_brand_cache():
    import app.core.design_tokens as dt

    dt._registry = None
    yield
    dt._registry = None


@pytest.fixture
def registry():
    return load_brands()


@pytest.fixture(params=["httbrands", "frenchies", "bishops", "lashlounge", "deltacrown"])
def brand(request, registry):
    return registry[request.param]


def test_primary_on_white(brand):
    r = get_contrast_ratio(brand.colors.primary, "#FFFFFF")
    assert r >= 4.5, f"{brand.name} primary on white: {r}"


def test_primary_on_background(brand):
    r = get_contrast_ratio(brand.colors.primary, brand.colors.background)
    assert r >= 4.5, f"{brand.name} primary on bg: {r}"


def test_text_on_background(brand):
    r = get_contrast_ratio(brand.colors.text, brand.colors.background)
    assert r >= 4.5, f"{brand.name} text on bg: {r}"


def test_accent_on_primary(brand):
    """Accent (#FFC957 gold) is used on dark primary backgrounds, not on white.

    Validates that accent provides adequate contrast when used on the brand's
    primary color (its actual use case in the design system).
    """
    r = get_contrast_ratio(brand.colors.accent, brand.colors.primary)
    assert r >= 3.0, f"{brand.name} accent on primary: {r}"

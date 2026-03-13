"""Integration tests for brand theme rendering pipeline.

Updated for microsoft-group-management design system.
"""

import pytest

from app.core.color_utils import get_contrast_ratio
from app.core.css_generator import generate_brand_css_variables, generate_scoped_brand_css
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


def test_all_brands_generate_css(registry):
    for key in registry:
        brand = registry[key]
        v = generate_brand_css_variables(brand)
        assert len(v) >= 40, f"{key} has only {len(v)} vars"
        assert "--brand-primary" in v


def test_all_brands_valid_hex(registry):
    import re

    hex_re = re.compile(r"^#[0-9A-Fa-f]{6}$")
    for key in registry:
        brand = registry[key]
        assert hex_re.match(brand.colors.primary), f"{key} primary invalid"
        assert hex_re.match(brand.colors.accent), f"{key} accent invalid"


def test_all_brands_scoped_css(registry):
    for key in registry:
        css = generate_scoped_brand_css(key, registry[key])
        assert f'[data-brand="{key}"]' in css
        assert css.count("{") == css.count("}")


def test_all_brands_text_contrast(registry):
    for key in registry:
        brand = registry[key]
        v = generate_brand_css_variables(brand)
        text_on_primary = v["--text-on-primary"]
        ratio = get_contrast_ratio(brand.colors.primary, text_on_primary)
        assert ratio >= 3.0, f"{key}: contrast {ratio} < 3.0"


def test_five_brands_loaded(registry):
    assert len(registry) == 5


def test_all_brands_have_semantic_vars(registry):
    """All brands should include semantic color variables."""
    for key in registry:
        brand = registry[key]
        v = generate_brand_css_variables(brand)
        assert "--color-success" in v, f"{key} missing --color-success"
        assert "--color-error" in v, f"{key} missing --color-error"


def test_all_brands_have_theme_vars(registry):
    """All brands should include theme surface/text variables."""
    for key in registry:
        brand = registry[key]
        v = generate_brand_css_variables(brand)
        assert "--bg-primary" in v, f"{key} missing --bg-primary"
        assert "--text-primary" in v, f"{key} missing --text-primary"


def test_all_brands_use_inter(registry):
    """All brands should use Inter font."""
    for key in registry:
        brand = registry[key]
        assert brand.typography.headingFont == "Inter", f"{key} heading not Inter"
        assert brand.typography.bodyFont == "Inter", f"{key} body not Inter"

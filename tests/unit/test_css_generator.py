"""Tests for css_generator.

Updated for microsoft-group-management design system:
- HTT primary: #500711 (burgundy)
- Font: Inter
- Includes semantic and theme variable generation
"""

import pytest

from app.core.css_generator import (
    SHADOW_PRESETS,
    generate_brand_css_variables,
    generate_color_variables,
    generate_dark_mode_css,
    generate_design_system_variables,
    generate_inline_style,
    generate_scoped_brand_css,
    generate_semantic_variables,
    generate_theme_variables,
    generate_typography_variables,
)
from app.core.design_tokens import (
    DARK_THEME_TOKENS,
    BrandColors,
    BrandConfig,
    BrandDesignSystem,
    BrandLogo,
    BrandTypography,
    SemanticColors,
    ShadowStyle,
)


@pytest.fixture
def b():
    return BrandConfig(
        name="T",
        logo=BrandLogo(primary="/l.svg"),
        colors=BrandColors(
            primary="#500711",
            accent="#FFC957",
            background="#FFFFFF",
            text="#111827",
            secondary="#BB86FC",
        ),
        typography=BrandTypography(headingFont="Inter", bodyFont="Inter"),
        designSystem=BrandDesignSystem(borderRadius="8px", shadowStyle=ShadowStyle.SOFT),
    )


def test_primary(b):
    assert generate_color_variables(b)["--brand-primary"] == "#500711"


def test_shades(b):
    v = generate_color_variables(b)
    assert "--brand-primary-5" in v and "--brand-primary-180" in v


def test_base(b):
    assert generate_color_variables(b)["--brand-primary-100"] == "#500711"


def test_secondary(b):
    assert "--brand-secondary" in generate_color_variables(b)


def test_contrast(b):
    assert generate_color_variables(b)["--text-on-primary"] in ("#FFFFFF", "#000000")


def test_gradient(b):
    assert "--brand-gradient" in generate_color_variables(b)


def test_heading(b):
    assert "Inter" in generate_typography_variables(b)["--brand-font-heading"]


def test_body(b):
    assert "Inter" in generate_typography_variables(b)["--brand-font-body"]


def test_radius(b):
    assert generate_design_system_variables(b)["--brand-radius"] == "8px"


def test_shadow(b):
    assert generate_design_system_variables(b)["--brand-shadow-style"] == SHADOW_PRESETS["soft"]


def test_count(b):
    # Now includes semantic (4) + theme (9) variables = 13 more
    assert len(generate_brand_css_variables(b)) >= 40


def test_scoped(b):
    assert '[data-brand="x"]' in generate_scoped_brand_css("x", b)


def test_balanced(b):
    c = generate_scoped_brand_css("x", b)
    assert c.count("{") == c.count("}")


def test_inline(b):
    i = generate_inline_style(b)
    assert "{" not in i and "--brand-primary:" in i


# ---------------------------------------------------------------------------
# Semantic & Theme variable tests (microsoft-group-management)
# ---------------------------------------------------------------------------


def test_semantic_variables_defaults():
    v = generate_semantic_variables()
    assert v["--color-success"] == "#10B981"
    assert v["--color-warning"] == "#F59E0B"
    assert v["--color-error"] == "#EF4444"
    assert v["--color-info"] == "#3B82F6"


def test_semantic_variables_custom():
    sc = SemanticColors(success="#00FF00", warning="#FFFF00", error="#FF0000", info="#0000FF")
    v = generate_semantic_variables(sc)
    assert v["--color-success"] == "#00FF00"


def test_theme_variables_light():
    v = generate_theme_variables()
    assert v["--bg-primary"] == "#FFFFFF"
    assert v["--text-primary"] == "#111827"


def test_theme_variables_dark():
    v = generate_theme_variables(DARK_THEME_TOKENS)
    assert v["--bg-primary"] == "#0F0F0F"
    assert v["--text-primary"] == "#F9FAFB"


def test_dark_mode_css():
    css = generate_dark_mode_css()
    assert ".dark {" in css
    assert "--bg-primary: #0F0F0F;" in css
    assert "--text-primary: #F9FAFB;" in css


def test_brand_css_includes_semantic(b):
    v = generate_brand_css_variables(b)
    assert "--color-success" in v
    assert "--color-info" in v


def test_brand_css_includes_theme(b):
    v = generate_brand_css_variables(b)
    assert "--bg-primary" in v
    assert "--text-primary" in v
    assert "--border-color" in v

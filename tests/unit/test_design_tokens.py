"""Tests for design_tokens module.

Covers both existing functionality and security validators added for bd:3t8
(CSS injection prevention on gradient, borderRadius, headingFont, bodyFont).
"""

import pytest
from app.core.design_tokens import (
    BrandColors,
    BrandDesignSystem,
    BrandTypography,
    BrandRegistry,
    ShadowStyle,
    load_brands,
    get_brand,
    get_google_fonts_url,
)


# ---------------------------------------------------------------------------
# Existing regression tests
# ---------------------------------------------------------------------------


def test_load_brands():
    r = load_brands()
    assert len(r) == 5


def test_brand_keys():
    r = load_brands()
    assert set(r.keys()) == {"httbrands", "frenchies", "bishops", "lashlounge", "deltacrown"}


def test_get_brand_valid():
    b = get_brand("httbrands")
    assert b.name == "Head to Toe Brands"


def test_get_brand_invalid():
    with pytest.raises(KeyError):
        get_brand("nonexistent")


def test_brand_colors_valid():
    b = get_brand("httbrands")
    assert b.colors.primary.startswith("#")
    assert b.colors.background.startswith("#")


def test_brand_typography():
    b = get_brand("httbrands")
    assert b.typography.headingFont == "Montserrat"


def test_brand_design_system():
    b = get_brand("httbrands")
    assert b.designSystem.shadowStyle == ShadowStyle.SHARP


def test_google_fonts_url():
    b = get_brand("httbrands")
    url = get_google_fonts_url(b)
    assert "fonts.googleapis.com" in url
    assert "Montserrat" in url


def test_hex_color_validation():
    with pytest.raises(Exception):
        BrandColors(primary="invalid", accent="#FFFFFF", background="#FFFFFF", text="#000000")


def test_registry_getitem():
    r = load_brands()
    b = r["frenchies"]
    assert b.name == "Frenchies Modern Nail Care"


def test_registry_iteration():
    r = load_brands()
    keys = list(r)
    assert len(keys) == 5


def test_shadow_style_enum():
    assert ShadowStyle.SOFT.value == "soft"
    assert ShadowStyle.SHARP.value == "sharp"
    assert ShadowStyle.NONE.value == "none"


# ---------------------------------------------------------------------------
# Gradient validator tests (BrandColors.gradient)  — bd:3t8 / M-1
# ---------------------------------------------------------------------------

def _make_colors(**overrides):
    """Helper to build a BrandColors with valid defaults, overriding as needed."""
    defaults = dict(
        primary="#000000",
        accent="#007CBA",
        background="#FFFFFF",
        text="#000000",
    )
    defaults.update(overrides)
    return BrandColors(**defaults)


class TestGradientValidator:
    """Validate that the gradient field rejects CSS injection payloads."""

    # --- valid ---

    def test_none_gradient_allowed(self):
        c = _make_colors(gradient=None)
        assert c.gradient is None

    def test_linear_gradient_valid(self):
        c = _make_colors(gradient="linear-gradient(135deg, #000 0%, #fff 100%)")
        assert c.gradient.startswith("linear-gradient")

    def test_radial_gradient_valid(self):
        c = _make_colors(gradient="radial-gradient(circle, #000 0%, #fff 100%)")
        assert c.gradient.startswith("radial-gradient")

    def test_gradient_case_insensitive(self):
        c = _make_colors(gradient="Linear-Gradient(135deg, #000 0%, #fff 100%)")
        assert "Linear-Gradient" in c.gradient

    # --- injection attacks ---

    def test_gradient_rejects_curly_braces(self):
        with pytest.raises(Exception, match="gradient"):
            _make_colors(gradient="linear-gradient(red)} body { background: red")

    def test_gradient_rejects_semicolon(self):
        with pytest.raises(Exception, match="gradient"):
            _make_colors(gradient="linear-gradient(red); color: red")

    def test_gradient_rejects_angle_brackets(self):
        with pytest.raises(Exception, match="gradient"):
            _make_colors(gradient="linear-gradient(red)<script>alert(1)</script>")

    def test_gradient_rejects_expression(self):
        with pytest.raises(Exception, match="[Uu]nsafe"):
            _make_colors(gradient="linear-gradient(expression(alert(1)))")

    def test_gradient_rejects_javascript(self):
        with pytest.raises(Exception, match="[Uu]nsafe"):
            _make_colors(gradient="linear-gradient(javascript:alert(1))")

    def test_gradient_rejects_url(self):
        with pytest.raises(Exception, match="[Uu]nsafe"):
            _make_colors(gradient="linear-gradient(url(http://evil.com))")

    def test_gradient_rejects_import(self):
        with pytest.raises(Exception, match="[Uu]nsafe"):
            _make_colors(gradient="@import url(evil.css)")

    def test_gradient_rejects_plain_string(self):
        with pytest.raises(Exception, match="gradient"):
            _make_colors(gradient="red")

    def test_gradient_rejects_empty_string(self):
        with pytest.raises(Exception, match="gradient"):
            _make_colors(gradient="")


# ---------------------------------------------------------------------------
# Font name validator tests (BrandTypography)  — bd:3t8 / M-1
# ---------------------------------------------------------------------------

class TestFontNameValidator:
    """Validate that font name fields reject CSS-unsafe characters."""

    # --- valid ---

    def test_simple_font_name(self):
        t = BrandTypography(headingFont="Montserrat", bodyFont="Lato")
        assert t.headingFont == "Montserrat"
        assert t.bodyFont == "Lato"

    def test_font_name_with_spaces(self):
        t = BrandTypography(headingFont="Open Sans", bodyFont="Source Sans 3")
        assert t.headingFont == "Open Sans"

    def test_font_name_with_hyphens(self):
        t = BrandTypography(headingFont="Noto-Sans", bodyFont="PT-Serif")
        assert t.headingFont == "Noto-Sans"

    def test_font_name_with_digits(self):
        t = BrandTypography(headingFont="Source Sans 3", bodyFont="Source Sans 3")
        assert t.headingFont == "Source Sans 3"

    # --- injection attacks ---

    def test_heading_font_rejects_semicolon(self):
        with pytest.raises(Exception, match="font"):
            BrandTypography(headingFont="Montserrat; } body { color: red", bodyFont="Lato")

    def test_body_font_rejects_semicolon(self):
        with pytest.raises(Exception, match="font"):
            BrandTypography(headingFont="Montserrat", bodyFont="Lato; } body { color: red")

    def test_font_rejects_curly_braces(self):
        with pytest.raises(Exception, match="font"):
            BrandTypography(headingFont="Montserrat}", bodyFont="Lato")

    def test_font_rejects_angle_brackets(self):
        with pytest.raises(Exception, match="font"):
            BrandTypography(headingFont="<script>", bodyFont="Lato")

    def test_font_rejects_parentheses(self):
        with pytest.raises(Exception, match="font"):
            BrandTypography(headingFont="expression(alert(1))", bodyFont="Lato")

    def test_font_rejects_quotes(self):
        with pytest.raises(Exception, match="font"):
            BrandTypography(headingFont="'Montserrat'", bodyFont="Lato")

    def test_font_rejects_colon(self):
        with pytest.raises(Exception, match="font"):
            BrandTypography(headingFont="javascript:alert(1)", bodyFont="Lato")

    def test_font_rejects_at_sign(self):
        with pytest.raises(Exception, match="font"):
            BrandTypography(headingFont="@import", bodyFont="Lato")

    def test_font_rejects_backslash(self):
        with pytest.raises(Exception, match="font"):
            BrandTypography(headingFont="Mont\\serrat", bodyFont="Lato")


# ---------------------------------------------------------------------------
# Border-radius validator tests (BrandDesignSystem)  — bd:3t8 / M-1
# ---------------------------------------------------------------------------

class TestBorderRadiusValidator:
    """Validate that borderRadius only accepts safe CSS size values."""

    # --- valid ---

    def test_px_value(self):
        ds = BrandDesignSystem(borderRadius="8px", shadowStyle="soft")
        assert ds.borderRadius == "8px"

    def test_zero_px(self):
        ds = BrandDesignSystem(borderRadius="0px", shadowStyle="sharp")
        assert ds.borderRadius == "0px"

    def test_rem_value(self):
        ds = BrandDesignSystem(borderRadius="0.5rem", shadowStyle="soft")
        assert ds.borderRadius == "0.5rem"

    def test_em_value(self):
        ds = BrandDesignSystem(borderRadius="1em", shadowStyle="soft")
        assert ds.borderRadius == "1em"

    def test_percent_value(self):
        ds = BrandDesignSystem(borderRadius="50%", shadowStyle="soft")
        assert ds.borderRadius == "50%"

    def test_decimal_px(self):
        ds = BrandDesignSystem(borderRadius="4.5px", shadowStyle="soft")
        assert ds.borderRadius == "4.5px"

    # --- injection attacks ---

    def test_rejects_css_injection(self):
        """Classic CSS breakout: '8px; } body { background: red'."""
        with pytest.raises(Exception, match="borderRadius"):
            BrandDesignSystem(
                borderRadius="8px; } body { background: red",
                shadowStyle="soft",
            )

    def test_rejects_bare_number(self):
        with pytest.raises(Exception, match="borderRadius"):
            BrandDesignSystem(borderRadius="8", shadowStyle="soft")

    def test_rejects_multiple_values(self):
        with pytest.raises(Exception, match="borderRadius"):
            BrandDesignSystem(borderRadius="8px 4px", shadowStyle="soft")

    def test_rejects_expression(self):
        with pytest.raises(Exception, match="borderRadius"):
            BrandDesignSystem(
                borderRadius="expression(alert(1))",
                shadowStyle="soft",
            )

    def test_rejects_negative_value(self):
        with pytest.raises(Exception, match="borderRadius"):
            BrandDesignSystem(borderRadius="-8px", shadowStyle="soft")

    def test_rejects_empty_string(self):
        with pytest.raises(Exception, match="borderRadius"):
            BrandDesignSystem(borderRadius="", shadowStyle="soft")

    def test_rejects_url_function(self):
        with pytest.raises(Exception, match="borderRadius"):
            BrandDesignSystem(
                borderRadius="url(http://evil.com)",
                shadowStyle="soft",
            )

    def test_rejects_unsupported_unit(self):
        with pytest.raises(Exception, match="borderRadius"):
            BrandDesignSystem(borderRadius="8vw", shadowStyle="soft")

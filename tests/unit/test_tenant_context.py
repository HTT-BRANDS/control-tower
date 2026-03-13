"""Unit tests for tenant context module.

Tests brand color data structures, palette lookups, and context generation.
"""

from unittest.mock import Mock

import pytest
from fastapi import Request

from app.core.tenant_context import (
    BRAND_PALETTES,
    DEFAULT_BRAND,
    BrandColors,
    get_brand_colors_by_code,
    get_brand_css_variables,
    get_template_context,
    get_tenant_brand_from_request,
)


class TestBrandColors:
    """Test BrandColors dataclass methods."""

    def test_to_css_variables_returns_dict_with_correct_keys(self):
        """Test to_css_variables() returns dict with --brand-* keys."""
        brand = BrandColors(
            primary="#ff0000", secondary="#00ff00", accent="#0000ff", theme_name="test"
        )

        css_vars = brand.to_css_variables()

        assert isinstance(css_vars, dict)
        assert "--brand-primary" in css_vars
        assert "--brand-secondary" in css_vars
        assert "--brand-accent" in css_vars
        assert css_vars["--brand-primary"] == "#ff0000"
        assert css_vars["--brand-secondary"] == "#00ff00"
        assert css_vars["--brand-accent"] == "#0000ff"

    def test_to_inline_style_returns_valid_css_string(self):
        """Test to_inline_style() returns valid CSS variable string."""
        brand = BrandColors(
            primary="#500711", secondary="#d1bdbf", accent="#ffc957", theme_name="htt"
        )

        inline_style = brand.to_inline_style()

        # Should be CSS variable format: "--var: value; --var2: value2"
        assert isinstance(inline_style, str)
        assert "--brand-primary: #500711" in inline_style
        assert "--brand-secondary: #d1bdbf" in inline_style
        assert "--brand-accent: #ffc957" in inline_style
        # Verify semicolon separator
        assert "; " in inline_style

    def test_to_inline_style_format_is_parseable(self):
        """Test inline style string has valid CSS format."""
        brand = BrandColors(
            primary="#123456", secondary="#abcdef", accent="#fedcba", theme_name="test"
        )

        inline_style = brand.to_inline_style()

        # Split and verify format: "key: value"
        parts = [p.strip() for p in inline_style.split(";") if p.strip()]
        assert len(parts) == 3
        for part in parts:
            assert ": " in part
            key, value = part.split(": ", 1)
            assert key.startswith("--brand-")
            assert value.startswith("#")

    def test_brand_colors_is_frozen_dataclass(self):
        """Test that BrandColors is immutable (frozen)."""
        brand = BrandColors(
            primary="#ff0000", secondary="#00ff00", accent="#0000ff", theme_name="test"
        )

        # Should raise FrozenInstanceError when trying to modify
        import dataclasses

        with pytest.raises(dataclasses.FrozenInstanceError):
            brand.primary = "#000000"


class TestBrandPalettes:
    """Test BRAND_PALETTES dictionary."""

    def test_has_all_five_tenant_codes(self):
        """Test BRAND_PALETTES contains all 5 tenant codes."""
        expected_codes = {"HTT", "FN", "BCC", "TLL", "DCE"}
        actual_codes = set(BRAND_PALETTES.keys())

        assert actual_codes == expected_codes, (
            f"Expected tenant codes {expected_codes}, got {actual_codes}"
        )

    @pytest.mark.parametrize("tenant_code", ["HTT", "FN", "BCC", "TLL", "DCE"])
    def test_each_palette_has_non_empty_colors(self, tenant_code):
        """Test each palette has non-empty primary, secondary, accent."""
        palette = BRAND_PALETTES[tenant_code]

        assert isinstance(palette, BrandColors)
        assert palette.primary, f"{tenant_code} missing primary color"
        assert palette.secondary, f"{tenant_code} missing secondary color"
        assert palette.accent, f"{tenant_code} missing accent color"
        assert palette.theme_name, f"{tenant_code} missing theme_name"

        # Verify colors are valid hex codes
        assert palette.primary.startswith("#")
        assert palette.secondary.startswith("#")
        assert palette.accent.startswith("#")

    def test_htt_palette_has_correct_colors(self):
        """Test HTT (Head-to-Toe) has burgundy/mauve/gold palette."""
        htt = BRAND_PALETTES["HTT"]

        assert htt.primary == "#500711"  # Burgundy
        assert htt.secondary == "#d1bdbf"  # Mauve
        assert htt.accent == "#ffc957"  # Gold
        assert htt.theme_name == "htt"

    def test_fn_palette_has_correct_colors(self):
        """Test FN (Frenchies) has navy/peach palette."""
        fn = BRAND_PALETTES["FN"]

        assert fn.primary == "#052b48"  # Navy
        assert fn.secondary == "#faaca8"  # Peach
        assert fn.accent == "#ffc957"  # Gold
        assert fn.theme_name == "frenchies"

    def test_bcc_palette_has_correct_colors(self):
        """Test BCC (Bishops) has orange/tan palette."""
        bcc = BRAND_PALETTES["BCC"]

        assert bcc.primary == "#EB631B"  # Orange
        assert bcc.secondary == "#CE9F7C"  # Tan
        assert bcc.accent == "#ffc957"  # Gold
        assert bcc.theme_name == "bishops"


class TestGetBrandColorsByCode:
    """Test get_brand_colors_by_code function."""

    @pytest.mark.parametrize("tenant_code", ["HTT", "FN", "BCC", "TLL", "DCE"])
    def test_with_valid_code_returns_correct_palette(self, tenant_code):
        """Test valid tenant code returns matching palette."""
        result = get_brand_colors_by_code(tenant_code)

        assert result == BRAND_PALETTES[tenant_code]
        assert isinstance(result, BrandColors)

    def test_with_lowercase_code_returns_correct_palette(self):
        """Test lowercase tenant code is handled correctly."""
        result = get_brand_colors_by_code("htt")

        assert result == BRAND_PALETTES["HTT"]

    def test_with_mixed_case_returns_correct_palette(self):
        """Test mixed-case tenant code is normalized."""
        result = get_brand_colors_by_code("HtT")

        assert result == BRAND_PALETTES["HTT"]

    def test_with_invalid_code_returns_default(self):
        """Test invalid tenant code returns DEFAULT_BRAND."""
        result = get_brand_colors_by_code("INVALID")

        assert result == DEFAULT_BRAND

    def test_with_empty_code_returns_default(self):
        """Test empty string returns DEFAULT_BRAND."""
        result = get_brand_colors_by_code("")

        assert result == DEFAULT_BRAND


class TestDefaultBrandColors:
    """Test DEFAULT_BRAND constant."""

    def test_default_brand_exists(self):
        """Test DEFAULT_BRAND is defined."""
        assert DEFAULT_BRAND is not None
        assert isinstance(DEFAULT_BRAND, BrandColors)

    def test_default_brand_has_valid_colors(self):
        """Test DEFAULT_BRAND has all required colors."""
        assert DEFAULT_BRAND.primary
        assert DEFAULT_BRAND.secondary
        assert DEFAULT_BRAND.accent
        assert DEFAULT_BRAND.theme_name

        # Verify hex format
        assert DEFAULT_BRAND.primary.startswith("#")
        assert DEFAULT_BRAND.secondary.startswith("#")
        assert DEFAULT_BRAND.accent.startswith("#")

    def test_default_brand_uses_walmart_blue_theme(self):
        """Test DEFAULT_BRAND uses Walmart blue as primary."""
        # Should be Walmart blue (0053e2)
        assert DEFAULT_BRAND.primary == "#0053e2"
        assert DEFAULT_BRAND.theme_name == "default"


class TestGetTenantBrandFromRequest:
    """Test get_tenant_brand_from_request function."""

    def test_extracts_brand_from_path_params(self):
        """Test extracting tenant from request path parameters."""
        # Create mock request with path params
        request = Mock(spec=Request)
        request.path_params = {"tenant_id": "test-tenant-123"}
        request.query_params = {}
        request.headers = {}
        request.state = Mock(spec=[])

        # Note: This will return DEFAULT_BRAND since tenant_id won't match
        # any in RIVERSIDE_TENANTS, but it tests the function flow
        result = get_tenant_brand_from_request(request)

        assert isinstance(result, BrandColors)
        assert result == DEFAULT_BRAND  # No matching tenant in config

    def test_extracts_brand_from_query_params(self):
        """Test extracting tenant from query parameters."""
        request = Mock(spec=Request)
        request.path_params = {}
        request.query_params = {"tenant_id": "test-tenant-456"}
        request.headers = {}
        request.state = Mock(spec=[])

        result = get_tenant_brand_from_request(request)

        assert isinstance(result, BrandColors)

    def test_extracts_brand_from_headers(self):
        """Test extracting tenant from request headers."""
        request = Mock(spec=Request)
        request.path_params = {}
        request.query_params = {}
        request.headers = {"X-Tenant-ID": "test-tenant-789"}
        request.state = Mock(spec=[])

        result = get_tenant_brand_from_request(request)

        assert isinstance(result, BrandColors)

    def test_returns_default_when_no_tenant_found(self):
        """Test returns DEFAULT_BRAND when no tenant info in request."""
        request = Mock(spec=Request)
        request.path_params = {}
        request.query_params = {}
        request.headers = {}
        request.state = Mock(spec=[])

        result = get_tenant_brand_from_request(request)

        assert result == DEFAULT_BRAND


class TestGetTemplateContext:
    """Test get_template_context function."""

    def test_returns_dict_with_brand_and_tenant_keys(self):
        """Test context dict has expected structure."""
        context = get_template_context()

        assert isinstance(context, dict)
        assert "brand" in context
        assert "tenant" in context

    def test_brand_dict_has_all_required_keys(self):
        """Test brand section has all color and theme keys."""
        context = get_template_context()

        brand = context["brand"]
        assert "primary" in brand
        assert "secondary" in brand
        assert "accent" in brand
        assert "theme_name" in brand
        assert "css_variables" in brand
        assert "inline_style" in brand

    def test_css_variables_is_dict(self):
        """Test css_variables is a dictionary."""
        context = get_template_context()

        css_vars = context["brand"]["css_variables"]
        assert isinstance(css_vars, dict)
        assert "--brand-primary" in css_vars

    def test_inline_style_is_string(self):
        """Test inline_style is a CSS string."""
        context = get_template_context()

        inline_style = context["brand"]["inline_style"]
        assert isinstance(inline_style, str)
        assert "--brand-primary" in inline_style

    def test_without_tenant_id_uses_default_brand(self):
        """Test calling without tenant_id uses DEFAULT_BRAND."""
        context = get_template_context()

        assert context["brand"]["primary"] == DEFAULT_BRAND.primary
        assert context["brand"]["secondary"] == DEFAULT_BRAND.secondary
        assert context["brand"]["accent"] == DEFAULT_BRAND.accent
        assert context["tenant"] is None


class TestGetBrandCssVariables:
    """Test get_brand_css_variables function."""

    def test_returns_css_string(self):
        """Test returns valid CSS variable string."""
        result = get_brand_css_variables()

        assert isinstance(result, str)
        assert "--brand-primary" in result
        assert "--brand-secondary" in result
        assert "--brand-accent" in result

    def test_without_tenant_uses_default_brand(self):
        """Test without tenant_id uses DEFAULT_BRAND."""
        result = get_brand_css_variables()

        # Should contain DEFAULT_BRAND colors
        assert DEFAULT_BRAND.primary in result

    def test_format_is_valid_inline_style(self):
        """Test format can be used as inline style attribute."""
        result = get_brand_css_variables()

        # Should be in format: "--var: value; --var2: value2"
        assert ": " in result
        assert "; " in result or result.endswith("")


class TestBrandColorIntegration:
    """Integration tests for brand color workflow."""

    def test_full_workflow_code_to_css(self):
        """Test complete workflow from tenant code to CSS variables."""
        # Get brand colors by code
        brand = get_brand_colors_by_code("HTT")

        # Convert to CSS variables
        css_vars = brand.to_css_variables()
        inline_style = brand.to_inline_style()

        # Verify output
        assert css_vars["--brand-primary"] == "#500711"
        assert "--brand-primary: #500711" in inline_style

    def test_template_context_provides_complete_data(self):
        """Test template context has everything needed for rendering."""
        context = get_template_context()

        # Can access colors directly
        assert context["brand"]["primary"]

        # Can get CSS variables dict
        css_vars = context["brand"]["css_variables"]
        assert isinstance(css_vars, dict)

        # Can get inline style string
        inline_style = context["brand"]["inline_style"]
        assert isinstance(inline_style, str)

        # Both should represent same colors
        assert css_vars["--brand-primary"] in inline_style

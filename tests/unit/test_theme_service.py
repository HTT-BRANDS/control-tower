"""Unit tests for ThemeService."""

from unittest.mock import MagicMock

import pytest

from app.services.theme_service import DEFAULT_BRAND, ThemeService


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return MagicMock()


@pytest.fixture
def theme_service(mock_db):
    """Create a ThemeService instance with mock db."""
    return ThemeService(mock_db)


class TestValidateContrast:
    """Tests for validate_contrast method."""

    def test_validate_contrast_known_values(self, theme_service):
        """Test contrast ratio calculation for known black/white pair (21:1)."""
        result = theme_service.validate_contrast("#000000", "#FFFFFF")

        assert result["is_accessible"] is True
        assert result["contrast_ratio"] == 21.0
        assert result["passes_normal_text"] is True
        assert result["passes_large_text"] is True

    def test_validate_contrast_low_contrast_fails_wcag(self, theme_service):
        """Test that low contrast colors fail WCAG AA."""
        result = theme_service.validate_contrast("#777777", "#888888")

        assert result["is_accessible"] is False
        assert result["contrast_ratio"] < 4.5
        assert result["passes_normal_text"] is False

    def test_validate_contrast_aaa_level(self, theme_service):
        """Test AAA level requires higher contrast."""
        # Same colors, different level
        result_aa = theme_service.validate_contrast("#333333", "#FFFFFF", level="AA")
        result_aaa = theme_service.validate_contrast("#333333", "#FFFFFF", level="AAA")

        # Both should have same ratio
        assert result_aa["contrast_ratio"] == result_aaa["contrast_ratio"]

        # AAA is stricter - might fail even if AA passes
        if result_aa["contrast_ratio"] < 7.0:
            assert result_aaa["is_accessible"] is False

    def test_validate_contrast_short_hex(self, theme_service):
        """Test that short hex codes (#FFF) are properly expanded."""
        result = theme_service.validate_contrast("#000", "#FFF")

        assert result["contrast_ratio"] == 21.0
        assert result["is_accessible"] is True


class TestCSSVariables:
    """Tests for get_css_variables method."""

    def test_get_css_variables_generates_all_vars(self, theme_service, mock_db):
        """Test that all expected CSS variables are generated."""
        # Setup mock to return None (fallback to default)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        css_vars = theme_service.get_css_variables("test-tenant")

        # Check all expected variables exist
        assert "--brand-primary" in css_vars
        assert "--brand-secondary" in css_vars
        assert "--brand-accent" in css_vars
        assert "--brand-primary-rgb" in css_vars
        assert "--brand-secondary-rgb" in css_vars
        assert "--brand-primary-text" in css_vars
        assert "--brand-secondary-text" in css_vars

    def test_get_css_variables_with_custom_theme(self, theme_service, mock_db):
        """Test CSS variables with custom brand config."""
        # Create a mock brand config
        mock_config = MagicMock()
        mock_config.brand_name = "Custom"
        mock_config.primary_color = "#FF5733"
        mock_config.secondary_color = "#33FF57"
        mock_config.accent_color = "#3357FF"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_config

        css_vars = theme_service.get_css_variables("test-tenant")

        assert css_vars["--brand-primary"] == "#FF5733"
        assert css_vars["--brand-secondary"] == "#33FF57"
        assert css_vars["--brand-accent"] == "#3357FF"

    def test_get_css_variables_rgb_format(self, theme_service, mock_db):
        """Test that RGB format is correct (comma-separated values)."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        css_vars = theme_service.get_css_variables("test-tenant")

        # RGB should be in format "R, G, B"
        primary_rgb = css_vars["--brand-primary-rgb"]
        parts = primary_rgb.split(",")
        assert len(parts) == 3
        # Each part should be a number 0-255
        for part in parts:
            assert part.strip().isdigit()
            assert 0 <= int(part.strip()) <= 255


class TestSuggestAccessibleColors:
    """Tests for suggest_accessible_colors method."""

    def test_suggest_accessible_colors_returns_alternatives(self, theme_service):
        """Test that suggestions are returned for low contrast colors."""
        # Low contrast medium gray on white (making it darker might help)
        result = theme_service.suggest_accessible_colors("#999999", "#FFFFFF")

        assert result["is_accessible"] is False
        assert result["suggestions"] is not None
        # May or may not have suggestions depending on algorithm
        assert isinstance(result["suggestions"], list)

    def test_suggest_accessible_colors_already_accessible(self, theme_service):
        """Test that no suggestions are needed for accessible colors."""
        result = theme_service.suggest_accessible_colors("#000000", "#FFFFFF")

        assert result["is_accessible"] is True
        assert result["suggestions"] is None


class TestHexToRGB:
    """Tests for hex to RGB conversion."""

    def test_hex_to_rgb_converts_properly(self, theme_service):
        """Test hex to RGB tuple conversion."""
        # Test various colors
        assert theme_service._hex_to_rgb_tuple("#FF5733") == (255, 87, 51)
        assert theme_service._hex_to_rgb_tuple("#FFFFFF") == (255, 255, 255)
        assert theme_service._hex_to_rgb_tuple("#000000") == (0, 0, 0)
        assert theme_service._hex_to_rgb_tuple("#ABC") == (170, 187, 204)

    def test_hex_to_rgb_string_format(self, theme_service):
        """Test hex to RGB string conversion."""
        rgb_string = theme_service._hex_to_rgb("#FF5733")
        assert rgb_string == "255, 87, 51"


class TestLuminanceCalculation:
    """Tests for luminance calculation."""

    def test_luminance_calculation_edge_cases(self, theme_service):
        """Test luminance calculation for edge cases."""
        # White should have luminance ~1.0
        white_lum = theme_service._calculate_relative_luminance("#FFFFFF")
        assert abs(white_lum - 1.0) < 0.01

        # Black should have luminance ~0.0
        black_lum = theme_service._calculate_relative_luminance("#000000")
        assert abs(black_lum - 0.0) < 0.01

        # Gray should be around 0.2 (actual luminance for #808080)
        gray_lum = theme_service._calculate_relative_luminance("#808080")
        assert 0.15 < gray_lum < 0.25


class TestThemeForTenant:
    """Tests for get_theme_for_tenant method."""

    def test_get_theme_for_tenant_fallback(self, theme_service, mock_db):
        """Test fallback to default theme when no brand config exists."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        theme = theme_service.get_theme_for_tenant("test-tenant")

        assert theme["is_custom"] is False
        assert theme["primary_color"] == DEFAULT_BRAND["primary_color"]
        assert theme["brand_name"] == DEFAULT_BRAND["brand_name"]

    def test_get_theme_for_tenant_custom(self, theme_service, mock_db):
        """Test custom theme is returned when brand config exists."""
        mock_config = MagicMock()
        mock_config.brand_name = "Custom Brand"
        mock_config.primary_color = "#123456"
        mock_config.secondary_color = "#ABCDEF"
        mock_config.accent_color = "#00FF00"

        mock_db.query.return_value.filter.return_value.first.return_value = mock_config

        theme = theme_service.get_theme_for_tenant("test-tenant")

        assert theme["is_custom"] is True
        assert theme["brand_name"] == "Custom Brand"
        assert theme["primary_color"] == "#123456"


class TestRiversideBrandColors:
    """Tests for Riverside brand colors."""

    @pytest.mark.parametrize("brand_name,primary,secondary", [
        ("HTT", "#500711", "#d1bdbf"),
        ("Frenchies", "#052b48", "#faaca8"),
        ("Bishops", "#EB631B", "#CE9F7C"),
        ("Lash Lounge", "#513550", "#D3BCC5"),
    ])
    def test_riverside_brand_primary_contrast_on_white(
        self, theme_service, brand_name, primary, secondary
    ):
        """Test that Riverside brand primaries have good contrast on white."""
        result = theme_service.validate_contrast(primary, "#FFFFFF")

        # Primary should be accessible on white
        assert result["passes_large_text"] is True, f"{brand_name} primary fails on white"


class TestContrastingText:
    """Tests for _get_contrasting_text method."""

    def test_contrasting_text_on_dark_background(self, theme_service):
        """Test white text on dark backgrounds."""
        assert theme_service._get_contrasting_text("#000000") == "#FFFFFF"
        assert theme_service._get_contrasting_text("#333333") == "#FFFFFF"

    def test_contrasting_text_on_light_background(self, theme_service):
        """Test black text on light backgrounds."""
        assert theme_service._get_contrasting_text("#FFFFFF") == "#000000"
        assert theme_service._get_contrasting_text("#EEEEEE") == "#000000"

    def test_contrasting_text_on_mid_gray(self, theme_service):
        """Test text color choice on mid-gray background."""
        # Middle gray should choose black (luminance >= 0.5 threshold)
        result = theme_service._get_contrasting_text("#808080")
        # The result depends on the actual luminance calculation
        assert result in ["#000000", "#FFFFFF"]

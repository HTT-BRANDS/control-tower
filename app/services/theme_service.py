"""Multi-tenant theme service for brand color management.

Provides brand color retrieval, CSS variable generation, and WCAG contrast
validation for accessible color combinations.
"""

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.css_generator import generate_brand_css_variables
from app.core.design_tokens import BrandConfigFull, get_brand, load_brands
from app.models.brand_config import BrandConfig

logger = logging.getLogger(__name__)

# Default brand colors (fallback)
DEFAULT_BRAND = {
    "brand_name": "Default",
    "primary_color": "#1a73e8",
    "secondary_color": "#5f6368",
    "accent_color": "#fbbc04",
}

# Riverside brand configurations
RIVERSIDE_BRANDS = {
    "HTT": {
        "primary_color": "#500711",
        "secondary_color": "#d1bdbf",
        "accent_color": "#ffc957",
        "brand_name": "HTT",
    },
    "Frenchies": {
        "primary_color": "#052b48",
        "secondary_color": "#faaca8",
        "accent_color": None,
        "brand_name": "Frenchies",
    },
    "Bishops": {
        "primary_color": "#EB631B",
        "secondary_color": "#CE9F7C",
        "accent_color": None,
        "brand_name": "Bishops",
    },
    "Lash Lounge": {
        "primary_color": "#513550",
        "secondary_color": "#D3BCC5",
        "accent_color": None,
        "brand_name": "Lash Lounge",
    },
}


class ThemeService:
    """Service for managing tenant brand themes and color accessibility."""

    def __init__(self, db: Session):
        self.db = db

    def get_brand_config(self, brand_key: str) -> BrandConfigFull:
        """Get brand config from YAML registry."""
        return get_brand(brand_key)

    def get_full_css_variables(self, brand_key: str) -> dict[str, str]:
        """Generate full 47+ CSS variables for a brand using design tokens."""
        brand = get_brand(brand_key)
        return generate_brand_css_variables(brand)

    def get_all_brands(self) -> dict[str, BrandConfigFull]:
        """Load all brands from YAML registry."""
        registry = load_brands()
        return dict(registry.brands)

    def get_theme_for_tenant(self, tenant_id: str) -> dict[str, Any]:
        """Get brand theme configuration for a tenant.

        Returns the tenant's brand config if found, otherwise falls back
        to default colors.

        Args:
            tenant_id: The tenant ID to look up

        Returns:
            Dictionary containing brand colors and metadata
        """
        brand_config = self.db.query(BrandConfig).filter(BrandConfig.tenant_id == tenant_id).first()

        if brand_config:
            return {
                "tenant_id": tenant_id,
                "brand_name": brand_config.brand_name,
                "primary_color": brand_config.primary_color,
                "secondary_color": brand_config.secondary_color,
                "accent_color": brand_config.accent_color,
                "is_custom": True,
            }

        # Fallback to default theme
        return {
            "tenant_id": tenant_id,
            **DEFAULT_BRAND,
            "is_custom": False,
        }

    def get_css_variables(self, tenant_id: str) -> dict[str, str]:
        """Generate CSS custom properties for tenant theme.

        Creates CSS variable mappings that can be injected into stylesheets.
        Includes RGB versions for use with alpha transparency.

        Args:
            tenant_id: The tenant ID to generate CSS variables for

        Returns:
            Dictionary of CSS variable names to values
        """
        theme = self.get_theme_for_tenant(tenant_id)

        css_vars = {
            "--brand-primary": theme["primary_color"],
            "--brand-secondary": theme["secondary_color"],
            "--brand-primary-rgb": self._hex_to_rgb(theme["primary_color"]),
            "--brand-secondary-rgb": self._hex_to_rgb(theme["secondary_color"]),
        }

        if theme.get("accent_color"):
            css_vars["--brand-accent"] = theme["accent_color"]
            css_vars["--brand-accent-rgb"] = self._hex_to_rgb(theme["accent_color"])
        else:
            # Use primary as accent fallback
            css_vars["--brand-accent"] = theme["primary_color"]
            css_vars["--brand-accent-rgb"] = css_vars["--brand-primary-rgb"]

        # Generate text colors based on contrast
        css_vars["--brand-primary-text"] = self._get_contrasting_text(theme["primary_color"])
        css_vars["--brand-secondary-text"] = self._get_contrasting_text(theme["secondary_color"])

        if theme.get("accent_color"):
            css_vars["--brand-accent-text"] = self._get_contrasting_text(theme["accent_color"])
        else:
            css_vars["--brand-accent-text"] = css_vars["--brand-primary-text"]

        return css_vars

    def validate_contrast(
        self,
        foreground_color: str,
        background_color: str,
        level: str = "AA",
    ) -> dict[str, Any]:
        """Validate WCAG contrast ratio between two colors.

        Checks if the contrast ratio meets WCAG 2.1 accessibility standards.

        Args:
            foreground_color: Foreground color in hex format (#RRGGBB)
            background_color: Background color in hex format (#RRGGBB)
            level: WCAG level to check ("AA" or "AAA"). Default is "AA".

        Returns:
            Dictionary with contrast ratio, compliance status, and recommendations
        """
        # Normalize hex colors
        fg_hex = self._normalize_hex(foreground_color)
        bg_hex = self._normalize_hex(background_color)

        # Calculate luminance for each color
        fg_luminance = self._calculate_relative_luminance(fg_hex)
        bg_luminance = self._calculate_relative_luminance(bg_hex)

        # Calculate contrast ratio
        lighter = max(fg_luminance, bg_luminance)
        darker = min(fg_luminance, bg_luminance)
        contrast_ratio = (lighter + 0.05) / (darker + 0.05)

        # WCAG thresholds
        if level == "AAA":
            normal_text_threshold = 7.0
            large_text_threshold = 4.5
        else:  # AA
            normal_text_threshold = 4.5
            large_text_threshold = 3.0

        return {
            "contrast_ratio": round(contrast_ratio, 2),
            "foreground": foreground_color,
            "background": background_color,
            "level": level,
            "passes_normal_text": contrast_ratio >= normal_text_threshold,
            "passes_large_text": contrast_ratio >= large_text_threshold,
            "passes_ui_components": contrast_ratio >= 3.0,
            "is_accessible": contrast_ratio >= normal_text_threshold,
        }

    def validate_brand_accessibility(self, tenant_id: str) -> dict[str, Any]:
        """Validate all brand color combinations for accessibility.

        Checks primary/secondary/accent colors against common background
        colors (white, black, gray).

        Args:
            tenant_id: The tenant ID to validate

        Returns:
            Dictionary with validation results for each color combination
        """
        theme = self.get_theme_for_tenant(tenant_id)

        backgrounds = ["#FFFFFF", "#000000", "#F3F4F6", "#1F2937"]
        colors = {
            "primary": theme["primary_color"],
            "secondary": theme["secondary_color"],
        }

        if theme.get("accent_color"):
            colors["accent"] = theme["accent_color"]

        results = {}
        issues = []

        for color_name, color_value in colors.items():
            results[color_name] = {}
            for bg in backgrounds:
                validation = self.validate_contrast(color_value, bg, level="AA")
                results[color_name][bg] = validation

                if not validation["passes_normal_text"]:
                    issues.append(
                        {
                            "color": color_name,
                            "color_value": color_value,
                            "background": bg,
                            "contrast_ratio": validation["contrast_ratio"],
                            "recommendation": f"Consider adjusting {color_name} color or using a different background",
                        }
                    )

        return {
            "tenant_id": tenant_id,
            "brand_name": theme["brand_name"],
            "results": results,
            "issues": issues,
            "has_issues": len(issues) > 0,
        }

    def suggest_accessible_colors(
        self,
        base_color: str,
        background_color: str = "#FFFFFF",
        level: str = "AA",
    ) -> dict[str, Any]:
        """Suggest accessible color alternatives if contrast is insufficient.

        Args:
            base_color: The color to make accessible
            background_color: The background color to check against
            level: WCAG level ("AA" or "AAA")

        Returns:
            Dictionary with suggested lighter and darker alternatives
        """
        validation = self.validate_contrast(base_color, background_color, level)

        if validation["is_accessible"]:
            return {
                "original_color": base_color,
                "is_accessible": True,
                "suggestions": None,
            }

        # Generate lighter and darker variants
        rgb = self._hex_to_rgb_tuple(base_color)

        # Suggest lighter version
        lighter_rgb = tuple(min(255, int(c + (255 - c) * 0.3)) for c in rgb)
        lighter_hex = self._rgb_to_hex(lighter_rgb)
        lighter_validation = self.validate_contrast(lighter_hex, background_color, level)

        # Suggest darker version
        darker_rgb = tuple(int(c * 0.7) for c in rgb)
        darker_hex = self._rgb_to_hex(darker_rgb)
        darker_validation = self.validate_contrast(darker_hex, background_color, level)

        suggestions = []
        if lighter_validation["is_accessible"]:
            suggestions.append(
                {
                    "color": lighter_hex,
                    "type": "lighter",
                    "contrast_ratio": lighter_validation["contrast_ratio"],
                }
            )
        if darker_validation["is_accessible"]:
            suggestions.append(
                {
                    "color": darker_hex,
                    "type": "darker",
                    "contrast_ratio": darker_validation["contrast_ratio"],
                }
            )

        return {
            "original_color": base_color,
            "is_accessible": False,
            "current_contrast": validation["contrast_ratio"],
            "suggestions": suggestions,
        }

    def _normalize_hex(self, color: str) -> str:
        """Normalize hex color to 6-digit format."""
        color = color.strip().lstrip("#")
        if len(color) == 3:
            color = "".join(c * 2 for c in color)
        return color.lower()

    def _hex_to_rgb(self, hex_color: str) -> str:
        """Convert hex color to RGB string format (e.g., '255, 255, 255')."""
        rgb = self._hex_to_rgb_tuple(hex_color)
        return f"{rgb[0]}, {rgb[1]}, {rgb[2]}"

    def _hex_to_rgb_tuple(self, hex_color: str) -> tuple[int, int, int]:
        """Convert hex color to RGB tuple."""
        hex_color = self._normalize_hex(hex_color)
        return (
            int(hex_color[0:2], 16),
            int(hex_color[2:4], 16),
            int(hex_color[4:6], 16),
        )

    def _rgb_to_hex(self, rgb: tuple[int, int, int]) -> str:
        """Convert RGB tuple to hex color."""
        return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

    def _calculate_relative_luminance(self, hex_color: str) -> float:
        """Calculate relative luminance per WCAG 2.1.

        Uses the sRGB color space conversion formula.
        """
        rgb = self._hex_to_rgb_tuple(hex_color)

        # Convert to sRGB
        def channel_luminance(c: int) -> float:
            c_srgb = c / 255.0
            if c_srgb <= 0.03928:
                return c_srgb / 12.92
            return ((c_srgb + 0.055) / 1.055) ** 2.4

        r, g, b = rgb
        return (
            0.2126 * channel_luminance(r)
            + 0.7152 * channel_luminance(g)
            + 0.0722 * channel_luminance(b)
        )

    def _get_contrasting_text(self, background_color: str) -> str:
        """Determine whether black or white text provides better contrast.

        Args:
            background_color: Background color in hex format

        Returns:
            "#000000" for black text or "#FFFFFF" for white text
        """
        luminance = self._calculate_relative_luminance(background_color)
        # Use white text on dark backgrounds, black text on light
        return "#FFFFFF" if luminance < 0.5 else "#000000"

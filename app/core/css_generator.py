"""Server-side CSS custom property generator for brand theming.

Sourced from ~/dev/microsoft-group-management design system.
Generates CSS variable strings for injection into Jinja2 templates.
Includes semantic colors, theme tokens, and dark mode CSS generation.
"""

from __future__ import annotations

from app.core.color_utils import (
    generate_10_shade_scale,
    generate_color_variants,
    get_contrasting_text_color,
)
from app.core.design_tokens import (
    DARK_THEME_TOKENS,
    BrandConfig,
    SemanticColors,
    ThemeTokens,
)

__all__ = [
    "generate_color_variables",
    "generate_typography_variables",
    "generate_design_system_variables",
    "generate_brand_css_variables",
    "generate_scoped_brand_css",
    "generate_all_brands_css",
    "generate_inline_style",
    "generate_semantic_variables",
    "generate_theme_variables",
    "generate_dark_mode_css",
    "SHADOW_PRESETS",
]

SHADOW_PRESETS = {
    "soft": "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",
    "sharp": "0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)",
    "none": "none",
}


def generate_color_variables(colors_model: BrandConfig) -> dict[str, str]:
    """Generate CSS variables for brand colors including shade scales.

    Returns dict of CSS variable name -> value, e.g.:
        {"--brand-primary": "#500711", "--brand-primary-5": "#F9E3E6", ...}
    """
    colors = colors_model.colors
    variables: dict[str, str] = {}

    # Primary color + shade scale
    variables["--brand-primary"] = colors.primary
    for shade, value in generate_10_shade_scale(colors.primary).items():
        variables[f"--brand-primary-{shade}"] = value

    # Secondary color + shade scale
    if colors.secondary:
        variables["--brand-secondary"] = colors.secondary
        for shade, value in generate_10_shade_scale(colors.secondary).items():
            variables[f"--brand-secondary-{shade}"] = value

    # Accent color + shade scale
    variables["--brand-accent"] = colors.accent
    for shade, value in generate_10_shade_scale(colors.accent).items():
        variables[f"--brand-accent-{shade}"] = value

    # Direct colors
    variables["--brand-background"] = colors.background
    variables["--brand-text"] = colors.text

    # Computed variants (lighter/darker)
    for prefix, hex_color in [("primary", colors.primary), ("accent", colors.accent)]:
        variants = generate_color_variants(hex_color)
        variables[f"--brand-{prefix}-light"] = variants["light"]
        variables[f"--brand-{prefix}-lighter"] = variants["lighter"]
        variables[f"--brand-{prefix}-dark"] = variants["dark"]
        variables[f"--brand-{prefix}-darker"] = variants["darker"]

    # Text-on colors (auto contrast)
    variables["--text-on-primary"] = get_contrasting_text_color(colors.primary)
    variables["--text-on-accent"] = get_contrasting_text_color(colors.accent)

    # Gradient
    if colors.gradient:
        variables["--brand-gradient"] = colors.gradient
    else:
        variables["--brand-gradient"] = (
            f"linear-gradient(135deg, {colors.primary}, {colors.accent})"
        )

    return variables


def generate_typography_variables(brand: BrandConfig) -> dict[str, str]:
    """Generate CSS variables for brand typography."""
    typo = brand.typography
    return {
        "--brand-font-heading": f'"{typo.headingFont}", sans-serif',
        "--brand-font-body": f'"{typo.bodyFont}", sans-serif',
    }


def generate_design_system_variables(brand: BrandConfig) -> dict[str, str]:
    """Generate CSS variables for design system tokens."""
    ds = brand.designSystem
    return {
        "--brand-radius": ds.borderRadius,
        "--brand-shadow-style": SHADOW_PRESETS.get(ds.shadowStyle.value, SHADOW_PRESETS["soft"]),
    }


def generate_semantic_variables(
    semantic: SemanticColors | None = None,
) -> dict[str, str]:
    """Generate CSS variables for semantic colors (success, warning, error, info).

    Uses defaults from microsoft-group-management design system if no
    SemanticColors instance is provided.
    """
    sc = semantic or SemanticColors()
    return {
        "--color-success": sc.success,
        "--color-warning": sc.warning,
        "--color-error": sc.error,
        "--color-info": sc.info,
    }


def generate_theme_variables(
    theme_tokens: ThemeTokens | None = None,
) -> dict[str, str]:
    """Generate CSS variables for surface/text theme tokens.

    Uses light-mode defaults from microsoft-group-management if no
    ThemeTokens instance is provided.
    """
    tt = theme_tokens or ThemeTokens()
    return {
        "--bg-primary": tt.bg_primary,
        "--bg-secondary": tt.bg_secondary,
        "--bg-tertiary": tt.bg_tertiary,
        "--text-primary": tt.text_primary,
        "--text-secondary": tt.text_secondary,
        "--text-muted": tt.text_muted,
        "--border-color": tt.border_color,
        "--sidebar-bg": tt.sidebar_bg,
        "--sidebar-border": tt.sidebar_border,
    }


def generate_dark_mode_css() -> str:
    """Generate the .dark { ... } CSS block for dark mode overrides.

    Uses DARK_THEME_TOKENS from microsoft-group-management design system.
    """
    dark_vars = generate_theme_variables(DARK_THEME_TOKENS)
    lines = [".dark {"]
    for name, value in dark_vars.items():
        lines.append(f"  {name}: {value};")
    lines.append("}")
    return "\n".join(lines)


def generate_brand_css_variables(brand: BrandConfig) -> dict[str, str]:
    """Generate ALL CSS variables for a brand (colors + typography + design system + semantic + theme)."""
    variables: dict[str, str] = {}
    variables.update(generate_color_variables(brand))
    variables.update(generate_typography_variables(brand))
    variables.update(generate_design_system_variables(brand))
    variables.update(generate_semantic_variables())
    variables.update(generate_theme_variables())
    return variables


def generate_scoped_brand_css(brand_key: str, brand: BrandConfig) -> str:
    """Generate CSS block scoped to a [data-brand] selector.

    Returns:
        CSS string like:
        [data-brand="frenchies"] {
          --brand-primary: #2563EB;
          ...
        }
    """
    variables = generate_brand_css_variables(brand)
    lines = [f'[data-brand="{brand_key}"] {{']
    for name, value in variables.items():
        lines.append(f"  {name}: {value};")
    lines.append("}")
    return "\n".join(lines)


def generate_all_brands_css(brands: dict[str, BrandConfig]) -> str:
    """Generate CSS for all brands at once."""
    blocks = [generate_scoped_brand_css(key, brand) for key, brand in brands.items()]
    return "\n\n".join(blocks)


def generate_inline_style(brand: BrandConfig) -> str:
    """Generate inline style string for direct injection.

    Useful for: <html style="{{ brand_inline_style }}">
    """
    variables = generate_brand_css_variables(brand)
    return "; ".join(f"{name}: {value}" for name, value in variables.items())

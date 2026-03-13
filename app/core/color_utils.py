"""Color manipulation and WCAG accessibility utilities.

Color utilities adapted from ~/dev/microsoft-group-management design system.
Provides hex/RGB/HSL conversions, WCAG contrast validation, and color variants.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = [
    "RGB",
    "HSL",
    "hex_to_rgb",
    "rgb_to_hex",
    "hex_to_hsl",
    "hsl_to_hex",
    "get_luminance",
    "get_contrast_ratio",
    "is_color_dark",
    "get_contrasting_text_color",
    "validate_wcag_aa",
    "validate_wcag_aa_large",
    "lighten_color",
    "darken_color",
    "generate_color_variants",
    "hex_to_rgba",
    "generate_10_shade_scale",
]

_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


@dataclass(frozen=True, slots=True)
class RGB:
    """Red-Green-Blue color (0-255 per channel)."""

    r: int
    g: int
    b: int


@dataclass(frozen=True, slots=True)
class HSL:
    """Hue-Saturation-Lightness color."""

    h: int  # 0-360
    s: int  # 0-100
    l: int  # 0-100


def hex_to_rgb(hex_color: str) -> RGB | None:
    """Convert hex color to RGB. Supports #RGB and #RRGGBB.

    >>> hex_to_rgb("#FF0000")
    RGB(r=255, g=0, b=0)
    >>> hex_to_rgb("#F00")
    RGB(r=255, g=0, b=0)
    >>> hex_to_rgb("invalid")
    """
    if not hex_color or not isinstance(hex_color, str):
        return None
    m = _HEX_RE.match(hex_color.strip())
    if not m:
        return None
    raw = m.group(1)
    if len(raw) == 3:
        raw = raw[0] * 2 + raw[1] * 2 + raw[2] * 2
    return RGB(r=int(raw[0:2], 16), g=int(raw[2:4], 16), b=int(raw[4:6], 16))


def rgb_to_hex(rgb: RGB) -> str:
    """Convert RGB to uppercase hex string.

    >>> rgb_to_hex(RGB(233, 30, 99))
    '#E91E63'
    """
    r = max(0, min(255, rgb.r))
    g = max(0, min(255, rgb.g))
    b = max(0, min(255, rgb.b))
    return f"#{r:02X}{g:02X}{b:02X}"


def hex_to_hsl(hex_color: str) -> HSL | None:
    """Convert hex color to HSL.

    >>> hex_to_hsl("#FF0000")
    HSL(h=0, s=100, l=50)
    """
    rgb = hex_to_rgb(hex_color)
    if rgb is None:
        return None
    r, g, b = rgb.r / 255, rgb.g / 255, rgb.b / 255
    mx, mn = max(r, g, b), min(r, g, b)
    l = (mx + mn) / 2
    if mx == mn:
        return HSL(h=0, s=0, l=round(l * 100))
    d = mx - mn
    s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
    if mx == r:
        h = ((g - b) / d + (6 if g < b else 0)) / 6
    elif mx == g:
        h = ((b - r) / d + 2) / 6
    else:
        h = ((r - g) / d + 4) / 6
    return HSL(h=round(h * 360), s=round(s * 100), l=round(l * 100))


def hsl_to_hex(hsl: HSL) -> str:
    """Convert HSL to hex string.

    >>> hsl_to_hex(HSL(0, 100, 50))
    '#FF0000'
    """
    h, s, l = hsl.h / 360, hsl.s / 100, hsl.l / 100
    if s == 0:
        v = round(l * 255)
        return rgb_to_hex(RGB(v, v, v))

    def _hue2rgb(p: float, q: float, t: float) -> float:
        if t < 0:
            t += 1
        if t > 1:
            t -= 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    return rgb_to_hex(
        RGB(
            r=round(_hue2rgb(p, q, h + 1 / 3) * 255),
            g=round(_hue2rgb(p, q, h) * 255),
            b=round(_hue2rgb(p, q, h - 1 / 3) * 255),
        )
    )


# --- WCAG Accessibility ---


def get_luminance(hex_color: str) -> float:
    """WCAG 2.1 relative luminance (0.0-1.0).

    >>> round(get_luminance("#FFFFFF"), 2)
    1.0
    >>> round(get_luminance("#000000"), 2)
    0.0
    """
    rgb = hex_to_rgb(hex_color)
    if rgb is None:
        return 0.0
    channels = []
    for v in (rgb.r, rgb.g, rgb.b):
        c = v / 255
        channels.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def get_contrast_ratio(color1: str, color2: str) -> float:
    """WCAG contrast ratio between two colors (1.0-21.0).

    >>> get_contrast_ratio("#000000", "#FFFFFF")
    21.0
    """
    l1, l2 = get_luminance(color1), get_luminance(color2)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def is_color_dark(hex_color: str, threshold: float = 0.179) -> bool:
    """Check if a color is considered dark (WCAG threshold)."""
    return get_luminance(hex_color) < threshold


def get_contrasting_text_color(background_hex: str) -> str:
    """Get black or white text color for maximum contrast.

    >>> get_contrasting_text_color("#000000")
    '#FFFFFF'
    >>> get_contrasting_text_color("#FFFFFF")
    '#000000'
    """
    return "#FFFFFF" if is_color_dark(background_hex) else "#000000"


def validate_wcag_aa(foreground: str, background: str) -> bool:
    """True if contrast ratio >= 4.5:1 (WCAG AA normal text)."""
    return get_contrast_ratio(foreground, background) >= 4.5


def validate_wcag_aa_large(foreground: str, background: str) -> bool:
    """True if contrast ratio >= 3:1 (WCAG AA large text)."""
    return get_contrast_ratio(foreground, background) >= 3.0


# --- Color Manipulation ---


def lighten_color(hex_color: str, percent: int) -> str:
    """Lighten a color by increasing HSL lightness."""
    hsl = hex_to_hsl(hex_color)
    if hsl is None:
        return hex_color
    new_l = min(100, hsl.l + percent)
    return hsl_to_hex(HSL(hsl.h, hsl.s, new_l))


def darken_color(hex_color: str, percent: int) -> str:
    """Darken a color by decreasing HSL lightness."""
    hsl = hex_to_hsl(hex_color)
    if hsl is None:
        return hex_color
    new_l = max(0, hsl.l - percent)
    return hsl_to_hex(HSL(hsl.h, hsl.s, new_l))


def generate_color_variants(hex_color: str) -> dict[str, str]:
    """Generate lighter/darker variants of a color."""
    return {
        "base": hex_color.upper() if hex_color.startswith("#") else f"#{hex_color}".upper(),
        "light": lighten_color(hex_color, 10),
        "lighter": lighten_color(hex_color, 20),
        "dark": darken_color(hex_color, 10),
        "darker": darken_color(hex_color, 20),
    }


def hex_to_rgba(hex_color: str, alpha: float) -> str:
    """Convert hex to CSS rgba() string.

    >>> hex_to_rgba("#E91E63", 0.5)
    'rgba(233, 30, 99, 0.5)'
    """
    rgb = hex_to_rgb(hex_color)
    if rgb is None:
        return f"rgba(0, 0, 0, {alpha})"
    return f"rgba({rgb.r}, {rgb.g}, {rgb.b}, {alpha})"


def generate_10_shade_scale(hex_color: str) -> dict[str, str]:
    """Generate a 10-shade scale matching the CSS theme.css convention."""
    return {
        "5": lighten_color(hex_color, 45),
        "10": lighten_color(hex_color, 40),
        "50": lighten_color(hex_color, 20),
        "100": hex_color.upper() if hex_color.startswith("#") else f"#{hex_color}".upper(),
        "110": darken_color(hex_color, 5),
        "130": darken_color(hex_color, 15),
        "140": darken_color(hex_color, 20),
        "160": darken_color(hex_color, 30),
        "180": darken_color(hex_color, 40),
    }

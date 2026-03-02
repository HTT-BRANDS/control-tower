"""Tenant Context Module - Brand Color Support.

This module provides tenant-aware context injection for templates,
enabling dynamic brand color theming per tenant.

Brand Colors:
- HTT: #500711 (Burgundy/Primary), #d1bdbf (Mauve/Secondary), #ffc957 (Gold/Accent)
- Frenchies: #052b48 (Navy/Primary), #faaca8 (Peach/Secondary)
- Bishops: #EB631B (Orange/Primary), #CE9F7C (Tan/Secondary)
- Lash Lounge: #513550 (Purple/Primary), #D3BCC5 (Lavender/Secondary)
"""

from dataclasses import dataclass
from typing import Any

from fastapi import Request

from app.core.tenants_config import RIVERSIDE_TENANTS


@dataclass(frozen=True)
class BrandColors:
    """Brand color palette for a tenant.

    Attributes:
        primary: Main brand color (for nav, buttons, primary actions)
        secondary: Supporting brand color (for backgrounds, accents)
        accent: Highlight/accent color (for warnings, highlights)
        theme_name: CSS theme identifier for data-theme attribute
    """
    primary: str
    secondary: str
    accent: str
    theme_name: str

    def to_css_variables(self) -> dict[str, str]:
        """Convert brand colors to CSS custom properties."""
        return {
            "--brand-primary": self.primary,
            "--brand-secondary": self.secondary,
            "--brand-accent": self.accent,
        }

    def to_inline_style(self) -> str:
        """Generate inline style attribute for CSS variables."""
        css_vars = self.to_css_variables()
        return "; ".join(f"{k}: {v}" for k, v in css_vars.items())


# ============================================================================
# BRAND COLOR DEFINITIONS
# ============================================================================

BRAND_PALETTES: dict[str, BrandColors] = {
    "HTT": BrandColors(
        primary="#500711",      # Burgundy
        secondary="#d1bdbf",    # Mauve
        accent="#ffc957",       # Gold
        theme_name="htt",
    ),
    "FN": BrandColors(
        primary="#052b48",      # Navy
        secondary="#faaca8",    # Peach
        accent="#ffc957",       # Gold (shared)
        theme_name="frenchies",
    ),
    "BCC": BrandColors(
        primary="#EB631B",      # Orange
        secondary="#CE9F7C",    # Tan
        accent="#ffc957",       # Gold (shared)
        theme_name="bishops",
    ),
    "TLL": BrandColors(
        primary="#513550",      # Purple
        secondary="#D3BCC5",    # Lavender
        accent="#ffc957",       # Gold (shared)
        theme_name="lash-lounge",
    ),
    "DCE": BrandColors(
        primary="#0053e2",      # Walmart Blue
        secondary="#9e9e9e",    # Gray
        accent="#ffc220",       # Walmart Spark Yellow
        theme_name="delta-crown",
    ),
}

# Default brand colors (Walmart blue theme as fallback)
DEFAULT_BRAND = BrandColors(
    primary="#0053e2",
    secondary="#ffc220",
    accent="#2a8703",
    theme_name="default",
)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_brand_colors(tenant_id: str) -> BrandColors:
    """Get brand colors for a tenant by tenant ID.

    Args:
        tenant_id: Azure AD tenant ID (GUID)

    Returns:
        BrandColors for the tenant, or DEFAULT_BRAND if not found
    """
    # Find tenant by ID
    for code, config in RIVERSIDE_TENANTS.items():
        if config.tenant_id == tenant_id and config.is_active:
            return BRAND_PALETTES.get(code, DEFAULT_BRAND)

    return DEFAULT_BRAND


def get_brand_colors_by_code(tenant_code: str) -> BrandColors:
    """Get brand colors for a tenant by short code.

    Args:
        tenant_code: Short tenant code (e.g., 'HTT', 'BCC', 'FN', 'TLL')

    Returns:
        BrandColors for the tenant, or DEFAULT_BRAND if not found
    """
    return BRAND_PALETTES.get(tenant_code.upper(), DEFAULT_BRAND)


def get_tenant_brand_from_request(request: Request) -> BrandColors:
    """Extract tenant and return brand colors from request context.

    This function looks for tenant information in:
    1. Request path parameters (e.g., /tenant/{tenant_id}/...)
    2. Query parameters (?tenant_id=...)
    3. Request headers (X-Tenant-ID)
    4. Session/cookie data

    Args:
        request: FastAPI Request object

    Returns:
        BrandColors for the detected tenant, or DEFAULT_BRAND
    """
    # Try path parameters
    tenant_id = request.path_params.get("tenant_id")
    if tenant_id:
        return get_brand_colors(tenant_id)

    # Try query parameters
    tenant_id = request.query_params.get("tenant_id")
    if tenant_id:
        return get_brand_colors(tenant_id)

    # Try headers
    tenant_id = request.headers.get("X-Tenant-ID")
    if tenant_id:
        return get_brand_colors(tenant_id)

    # Try session (if using session middleware)
    if hasattr(request.state, "tenant_id"):
        return get_brand_colors(request.state.tenant_id)

    return DEFAULT_BRAND


def get_all_brand_palettes() -> dict[str, BrandColors]:
    """Return all brand palettes for active tenants."""
    return {
        code: BRAND_PALETTES.get(code, DEFAULT_BRAND)
        for code, config in RIVERSIDE_TENANTS.items()
        if config.is_active and code in BRAND_PALETTES
    }


def get_brand_css_variables(tenant_id: str | None = None) -> str:
    """Generate CSS variable string for inline style.

    Args:
        tenant_id: Optional tenant ID to get specific brand colors

    Returns:
        CSS variable string for inline style attribute
    """
    if tenant_id:
        brand = get_brand_colors(tenant_id)
    else:
        brand = DEFAULT_BRAND

    return brand.to_inline_style()


# ============================================================================
# TEMPLATE CONTEXT PROVIDERS
# ============================================================================

def get_template_context(tenant_id: str | None = None) -> dict[str, Any]:
    """Generate template context with brand colors.

    This function returns a dictionary suitable for passing to Jinja2 templates.
    It includes all necessary brand color information for dynamic theming.

    Args:
        tenant_id: Optional tenant ID to get specific brand colors

    Returns:
        Dictionary with brand colors and theme information
    """
    if tenant_id:
        brand = get_brand_colors(tenant_id)
        tenant_config = None
        for _code, config in RIVERSIDE_TENANTS.items():
            if config.tenant_id == tenant_id:
                tenant_config = config
                break
    else:
        brand = DEFAULT_BRAND
        tenant_config = None

    return {
        "brand": {
            "primary": brand.primary,
            "secondary": brand.secondary,
            "accent": brand.accent,
            "theme_name": brand.theme_name,
            "css_variables": brand.to_css_variables(),
            "inline_style": brand.to_inline_style(),
        },
        "tenant": {
            "id": tenant_config.tenant_id if tenant_config else None,
            "name": tenant_config.name if tenant_config else "Default",
            "code": tenant_config.code if tenant_config else None,
        } if tenant_config else None,
    }


def get_brand_context_for_request(request: Request) -> dict[str, Any]:
    """Get brand context for a request.

    This is a convenience function that combines tenant detection from
    the request with template context generation.

    Args:
        request: FastAPI Request object

    Returns:
        Template context dictionary with brand information
    """
    brand = get_tenant_brand_from_request(request)

    # Also try to get tenant config
    tenant_id = (
        request.path_params.get("tenant_id") or
        request.query_params.get("tenant_id") or
        request.headers.get("X-Tenant-ID")
    )

    tenant_config = None
    if tenant_id:
        for config in RIVERSIDE_TENANTS.values():
            if config.tenant_id == tenant_id:
                tenant_config = config
                break

    return {
        "brand": {
            "primary": brand.primary,
            "secondary": brand.secondary,
            "accent": brand.accent,
            "theme_name": brand.theme_name,
            "css_variables": brand.to_css_variables(),
            "inline_style": brand.to_inline_style(),
        },
        "tenant": {
            "id": tenant_config.tenant_id if tenant_config else None,
            "name": tenant_config.name if tenant_config else "Azure Governance",
            "code": tenant_config.code if tenant_config else None,
        } if tenant_config else {
            "name": "Azure Governance",
            "code": None,
        },
    }


# ============================================================================
# MIDDLEWARE SUPPORT
# ============================================================================

class TenantContextMiddleware:
    """ASGI middleware to inject tenant context into requests.

    Usage:
        from app.core.tenant_context import TenantContextMiddleware

        app.add_middleware(TenantContextMiddleware)
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        """Process the request and inject tenant context."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Create request object to access parameters
        request = Request(scope, receive)

        # Detect tenant and store in scope
        tenant_id = (
            request.path_params.get("tenant_id") or
            request.query_params.get("tenant_id") or
            request.headers.get("X-Tenant-ID")
        )

        scope["tenant_id"] = tenant_id
        scope["brand_colors"] = get_brand_colors(tenant_id) if tenant_id else DEFAULT_BRAND

        await self.app(scope, receive, send)


# ============================================================================
# TEMPLATE FILTERS
# ============================================================================

def brand_color_filter(color_type: str, tenant_code: str | None = None) -> str:
    """Jinja2 filter to get brand colors.

    Usage in templates:
        {{ 'primary' | brand_color }}
        {{ 'secondary' | brand_color('HTT') }}

    Args:
        color_type: 'primary', 'secondary', or 'accent'
        tenant_code: Optional tenant code (uses current context if not provided)

    Returns:
        Hex color code
    """
    if tenant_code:
        brand = get_brand_colors_by_code(tenant_code)
    else:
        brand = DEFAULT_BRAND

    return getattr(brand, color_type, brand.primary)


def brand_style_filter(tenant_code: str | None = None) -> str:
    """Jinja2 filter to generate CSS variable style string.

    Usage in templates:
        <div style="{{ None | brand_style }}">
        <div style="{{ None | brand_style('HTT') }}">

    Args:
        tenant_code: Optional tenant code

    Returns:
        CSS variable string for inline style
    """
    if tenant_code:
        brand = get_brand_colors_by_code(tenant_code)
    else:
        brand = DEFAULT_BRAND

    return brand.to_inline_style()


def register_template_filters(env):
    """Register tenant context filters with Jinja2 environment.

    Args:
        env: Jinja2 Environment instance
    """
    env.filters["brand_color"] = brand_color_filter
    env.filters["brand_style"] = brand_style_filter

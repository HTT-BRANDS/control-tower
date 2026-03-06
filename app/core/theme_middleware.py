"""Theme middleware - resolves tenant to brand and injects design tokens.

Integrates with:
  - app.core.design_tokens (brand registry from config/brands.yaml)
  - app.core.css_generator (47+ CSS variable generation)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.css_generator import generate_brand_css_variables, generate_inline_style
from app.core.design_tokens import (
    BrandConfigFull,
    BrandRegistry,
    get_google_fonts_url,
    load_brands,
)

logger = logging.getLogger(__name__)

__all__ = ["ThemeMiddleware", "ThemeContext", "get_theme_context"]

TENANT_CODE_TO_BRAND: dict[str, str] = {
    "HTT": "httbrands",
    "FN": "frenchies",
    "BCC": "bishops",
    "TLL": "lashlounge",
    "DCE": "deltacrown",
}

DEFAULT_BRAND_KEY = "httbrands"


@dataclass(frozen=True)
class ThemeContext:
    """Immutable theme context attached to each request."""

    brand_key: str
    brand_config: BrandConfigFull
    css_variables: dict[str, str]
    inline_style: str
    google_fonts_url: str

    @property
    def brand_name(self) -> str:
        return self.brand_config.name

    @property
    def logo_primary(self) -> str:
        return self.brand_config.logo.primary

    @property
    def logo_white(self) -> str | None:
        return self.brand_config.logo.white

    @property
    def logo_icon(self) -> str | None:
        return self.brand_config.logo.icon

    def to_template_context(self) -> dict[str, Any]:
        """Convert to dict for Jinja2 template rendering."""
        return {
            "brand": {
                "key": self.brand_key,
                "name": self.brand_name,
                "primary": self.brand_config.colors.primary,
                "secondary": self.brand_config.colors.secondary or self.brand_config.colors.primary,
                "accent": self.brand_config.colors.accent,
                "theme_name": self.brand_key,
                "css_variables": self.css_variables,
                "inline_style": self.inline_style,
                "logo": {
                    "primary": self.logo_primary,
                    "white": self.logo_white,
                    "icon": self.logo_icon,
                },
                "typography": {
                    "heading_font": self.brand_config.typography.headingFont,
                    "body_font": self.brand_config.typography.bodyFont,
                },
                "google_fonts_url": self.google_fonts_url,
            },
        }


class ThemeMiddleware(BaseHTTPMiddleware):
    """Starlette middleware resolving tenant -> brand -> theme context."""

    def __init__(self, app, default_brand_key: str = DEFAULT_BRAND_KEY):
        super().__init__(app)
        self.default_brand_key = default_brand_key
        self._registry: BrandRegistry | None = None
        self._cache: dict[str, ThemeContext] = {}

    def _get_registry(self) -> BrandRegistry:
        if self._registry is None:
            self._registry = load_brands()
        return self._registry

    def _resolve_brand_key(self, request: Request) -> str:
        brand_key = request.query_params.get("brand")
        if brand_key and self._get_registry().get(brand_key):
            return brand_key
        brand_key = request.headers.get("X-Brand-Key")
        if brand_key and self._get_registry().get(brand_key):
            return brand_key
        tenant_code = getattr(request.state, "tenant_code", None)
        if tenant_code and tenant_code in TENANT_CODE_TO_BRAND:
            return TENANT_CODE_TO_BRAND[tenant_code]
        tenant_code = request.headers.get("X-Tenant-Code")
        if tenant_code and tenant_code in TENANT_CODE_TO_BRAND:
            return TENANT_CODE_TO_BRAND[tenant_code]
        return self.default_brand_key

    def _build_theme_context(self, brand_key: str) -> ThemeContext:
        if brand_key in self._cache:
            return self._cache[brand_key]
        registry = self._get_registry()
        brand_config = registry.get(brand_key)
        if brand_config is None:
            brand_key = self.default_brand_key
            brand_config = registry[brand_key]
        ctx = ThemeContext(
            brand_key=brand_key,
            brand_config=brand_config,
            css_variables=generate_brand_css_variables(brand_config),
            inline_style=generate_inline_style(brand_config),
            google_fonts_url=get_google_fonts_url(brand_config),
        )
        self._cache[brand_key] = ctx
        return ctx

    async def dispatch(self, request: Request, call_next) -> Response:
        brand_key = self._resolve_brand_key(request)
        theme_ctx = self._build_theme_context(brand_key)
        request.state.theme = theme_ctx
        return await call_next(request)


def get_theme_context(request: Request) -> ThemeContext:
    """Extract ThemeContext from request. Falls back to default."""
    theme = getattr(request.state, "theme", None)
    if theme is not None:
        return theme
    registry = load_brands()
    brand = registry[DEFAULT_BRAND_KEY]
    return ThemeContext(
        brand_key=DEFAULT_BRAND_KEY,
        brand_config=brand,
        css_variables=generate_brand_css_variables(brand),
        inline_style=generate_inline_style(brand),
        google_fonts_url=get_google_fonts_url(brand),
    )

"""Shared Jinja2 templates instance — single source of truth.

All route modules that render templates should import `templates` from here
instead of creating their own Jinja2Templates instance. This ensures all
custom filters, globals, and environment configuration are consistent.
"""

from datetime import UTC

from fastapi.templating import Jinja2Templates

from app import __version__
from app.core.tenant_context import register_template_filters

# Single shared instance
templates = Jinja2Templates(directory="app/templates")

# Register brand color filters (brand_color, brand_style)
register_template_filters(templates.env)

# Global template variables
templates.env.globals["app_version"] = __version__


# ── Custom Filters ──────────────────────────────────────────────


def _timeago(dt) -> str:
    """Jinja2 filter: convert datetime to relative 'time ago' string."""
    if dt is None:
        return "never"
    from datetime import datetime

    now = datetime.now(UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


templates.env.filters["timeago"] = _timeago


# ── Global helpers ──────────────────────────────────────────────


def _active_tenant_count() -> int:
    """Jinja global: count of active tenants for the header badge.

    Used by ``app/templates/base.html`` to render the "N Tenants" badge.
    Previously the badge was a hardcoded string literal ("4 Tenants") —
    which silently lied as soon as the tenant set changed (bd ct-yju).

    Returns 0 on any error so a transient DB hiccup never blanks the nav.
    """
    try:
        from app.core.database import SessionLocal
        from app.models.tenant import Tenant

        with SessionLocal() as db:
            return db.query(Tenant).filter(Tenant.is_active.is_(True)).count()
    except Exception:  # noqa: BLE001 — nav must never crash a page render
        return 0


templates.env.globals["active_tenant_count"] = _active_tenant_count

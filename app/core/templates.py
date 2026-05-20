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
    except Exception:
        return 0


templates.env.globals["active_tenant_count"] = _active_tenant_count


def _latest_sync_at():
    """Jinja global: timestamp of the most recent successful sync, or None.

    Used by ``app/templates/base.html`` to render the footer's
    "Last sync: <timestamp>" line. Previously the footer hardcoded the
    literal string "Never" with no JS or server binding behind it, so
    every page on every load reported "Never" even while the same page
    rendered live data sourced from successful syncs (bd ct-gql).

    Returns the most recent ``SyncJobLog.started_at`` where status is
    ``"completed"`` (the canonical success status — see ct-zNN), or
    ``None`` if no sync has ever completed. ``None`` is honest; the
    template skips the line entirely rather than lying with "Never".

    Returns None on any error so a transient DB hiccup never crashes
    the footer on every single page.
    """
    try:
        from app.core.database import SessionLocal
        from app.models.monitoring import SyncJobLog

        with SessionLocal() as db:
            row = (
                db.query(SyncJobLog.started_at)
                .filter(SyncJobLog.status == "completed")
                .order_by(SyncJobLog.started_at.desc())
                .first()
            )
            return row[0] if row else None
    except Exception:
        return None


templates.env.globals["latest_sync_at"] = _latest_sync_at

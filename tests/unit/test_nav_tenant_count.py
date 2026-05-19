"""Regression tests for ct-yju: header tenant badge off-by-one.

Bug: ``app/templates/base.html`` previously rendered the right-side
header badge as a hardcoded string literal — ``<span>4 Tenants</span>``.
The number was set in April 2026 when there were 4 tenants and never
updated; by May the tenant set was 5 and the badge silently lied on
every page. /admin's "5/5 Active Tenants" tile, the dashboard tenant
dropdown, /sync-dashboard, and /healthz/data all agreed it was 5.

Fix: ``app/core/templates.py`` now registers an ``active_tenant_count``
Jinja global that returns ``count(*) FROM tenants WHERE is_active=1``.
base.html renders ``{{ active_tenant_count() }} Tenant{{s}}`` with a
``data-testid="nav-tenant-count"`` anchor for tests.

These tests assert the badge reflects the actual DB count, including
the singular/plural toggle.
"""

from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

import pytest

from app.core.templates import templates


def _render_badge(count: int) -> str:
    """Render base.html with active_tenant_count() stubbed to ``count``."""
    env = templates.env
    tpl = env.get_template("base.html")
    request = MagicMock()
    request.url.path = "/dashboard"
    request.state = MagicMock(brand="htt")
    with patch.dict(env.globals, {"active_tenant_count": lambda: count}):
        return tpl.render(
            request=request,
            brand={
                "primary": "#1B365D",
                "secondary": "#0A1E3C",
                "accent": "#FFC72C",
                "theme_name": "htt",
                "primary_text": "#fff",
            },
            is_auth_page=False,
        )


def _extract_badge(html: str) -> str:
    match = re.search(
        r'data-testid="nav-tenant-count"[^>]*>([^<]+)<', html, re.DOTALL
    )
    assert match, "nav-tenant-count badge missing from base.html"
    return match.group(1).strip()


@pytest.mark.parametrize(
    "count,expected",
    [
        (0, "0 Tenants"),
        (1, "1 Tenant"),
        (2, "2 Tenants"),
        (5, "5 Tenants"),
        (47, "47 Tenants"),
    ],
)
def test_badge_reflects_count_and_pluralizes(count, expected):
    """ct-yju: badge must use the live count, with correct plural form."""
    html = _render_badge(count)
    assert _extract_badge(html) == expected


def test_badge_aria_label_is_descriptive():
    """A screen reader should hear '5 active tenants', not '5 Tenants' as alphanumeric soup."""
    html = _render_badge(5)
    assert 'aria-label="5 active tenants"' in html
    html = _render_badge(1)
    assert 'aria-label="1 active tenant"' in html


def test_global_is_registered_on_env():
    """The Jinja global must be wired up by app.core.templates module load."""
    assert "active_tenant_count" in templates.env.globals
    assert callable(templates.env.globals["active_tenant_count"])


def test_global_returns_zero_on_db_error():
    """Nav must never crash a page render — a DB hiccup returns 0, not 500."""
    with patch("app.core.database.SessionLocal", side_effect=RuntimeError("db down")):
        assert templates.env.globals["active_tenant_count"]() == 0

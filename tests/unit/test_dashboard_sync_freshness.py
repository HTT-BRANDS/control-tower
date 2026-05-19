"""Regression tests for ct-zNN + ct-gql: dashboard misreported sync state.

Two bugs, same root cause family:

ct-zNN: /dashboard rendered every per-domain summary card with the footer
text "Synced never" — alongside KPI values populated from those very
syncs. The route filtered ``SyncJobLog.status == "success"`` but the
canonical success status in this codebase is ``"completed"`` (see
``app/api/services/monitoring_service.py`` which uses ``"completed"``
in 3 places, plus every job-runner write site). The dashboard route
was the only consumer of the non-existent ``"success"`` status, so
every lookup returned None and ``last_synced[stype]`` was always None
→ ``timeago(None)`` → ``"never"``.

ct-gql: ``app/templates/base.html`` rendered a static footer
``<span id="last-sync">Never</span>`` with no JS or server binding
behind it. The span ALWAYS read "Never" on every page, on every load,
forever. We added a ``latest_sync_at()`` Jinja global that returns
the most recent successful ``SyncJobLog.started_at`` (or None when no
sync has ever completed) and wired the footer to it via the
``timeago`` filter.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch


# ── ct-zNN ────────────────────────────────────────────────────────────


def test_dashboard_route_uses_completed_not_success_for_sync_status():
    """The dashboard data route must filter on the real success status.

    Sanity-check via static analysis: there should be exactly zero
    occurrences of ``status == "success"`` paired with ``SyncJobLog``
    anywhere in the app. Every consumer should use ``"completed"``.
    """
    from pathlib import Path

    bad = []
    app_dir = Path(__file__).resolve().parents[2] / "app"
    for py_file in app_dir.rglob("*.py"):
        text = py_file.read_text()
        # Only flag lines that look like a SyncJobLog status comparison.
        for lineno, line in enumerate(text.splitlines(), 1):
            if (
                "SyncJobLog.status" in line
                and '"success"' in line
                and "==" in line
            ):
                bad.append(f"{py_file}:{lineno}: {line.strip()}")
    assert not bad, (
        "ct-zNN regression: SyncJobLog.status == 'success' will always match "
        "zero rows. Use 'completed' instead.\n" + "\n".join(bad)
    )


def test_dashboard_route_filters_on_completed_status():
    """Belt-and-suspenders: the actual route source uses 'completed'."""
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "api"
        / "routes"
        / "dashboard.py"
    ).read_text()
    assert 'SyncJobLog.status == "completed"' in src, (
        "ct-zNN: dashboard route must filter on 'completed' status"
    )
    assert 'SyncJobLog.status == "success"' not in src, (
        "ct-zNN: 'success' status doesn't exist in SyncJobLog data"
    )


# ── ct-gql ────────────────────────────────────────────────────────────


def test_latest_sync_at_returns_most_recent_completed_started_at():
    """The Jinja global returns the timestamp of the latest completed sync."""
    fake_now = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)

    from app.core.templates import _latest_sync_at

    with patch("app.core.database.SessionLocal") as mock_sessionmaker:
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_sessionmaker.return_value = mock_session

        query = MagicMock()
        query.filter.return_value = query
        query.order_by.return_value = query
        query.first.return_value = (fake_now,)
        mock_session.query.return_value = query

        result = _latest_sync_at()
        assert result == fake_now


def test_latest_sync_at_returns_none_when_no_completed_syncs():
    """When no sync has ever completed, return None (don't lie with 'Never')."""
    from app.core.templates import _latest_sync_at

    with patch("app.core.database.SessionLocal") as mock_sessionmaker:
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_sessionmaker.return_value = mock_session

        query = MagicMock()
        query.filter.return_value = query
        query.order_by.return_value = query
        query.first.return_value = None
        mock_session.query.return_value = query

        assert _latest_sync_at() is None


def test_latest_sync_at_swallows_db_errors():
    """Footer must never crash the page render on a transient DB hiccup."""
    from app.core.templates import _latest_sync_at

    with patch("app.core.database.SessionLocal") as mock_sessionmaker:
        mock_sessionmaker.side_effect = RuntimeError("db is sad")
        assert _latest_sync_at() is None


def test_base_template_footer_no_longer_hardcodes_never():
    """Static check: base.html must not contain the literal 'Never' fallback."""
    from pathlib import Path

    base_html = (
        Path(__file__).resolve().parents[2] / "app" / "templates" / "base.html"
    ).read_text()
    # The new footer reads from latest_sync_at() and shows 'no sync data'
    # when the value is None — explicitly NOT the misleading 'Never'.
    assert "latest_sync_at" in base_html, (
        "ct-gql: footer must reference latest_sync_at() Jinja global"
    )
    assert ">Never<" not in base_html, (
        "ct-gql: footer must not hardcode 'Never' — that's the bug we fixed"
    )


def test_base_template_footer_renders_timeago_with_real_timestamp():
    """End-to-end render: passing a real timestamp produces a relative string."""
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    from pathlib import Path
    from types import SimpleNamespace

    templates_dir = (
        Path(__file__).resolve().parents[2] / "app" / "templates"
    )

    # Build an env that mimics the real one's relevant features.
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )

    # Wire the same filters & globals the app registers.
    from app.core.templates import _timeago

    env.filters["timeago"] = _timeago
    five_min_ago = datetime.now(UTC) - timedelta(minutes=5)
    env.globals["latest_sync_at"] = lambda: five_min_ago
    env.globals["active_tenant_count"] = lambda: 5

    class _S:
        csp_nonce = "n"
        gpc_enabled = False

    class _R:
        state = _S()

    rendered = env.get_template("base.html").render(
        request=_R(),
        brand=SimpleNamespace(
            key="httbrands",
            inline_style="",
            google_fonts_url="https://fonts.googleapis.com/css2?family=Inter&display=swap",
            css_variables={},
        ),
    )

    assert "5m ago" in rendered, (
        "ct-gql: footer should render the timeago string for a real timestamp"
    )
    assert ">Never<" not in rendered, (
        "ct-gql: footer must not fall through to the old hardcoded 'Never'"
    )

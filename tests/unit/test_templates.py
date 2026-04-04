"""Tests for app/core/templates.py — Jinja2 template helpers.

Covers:
- _timeago filter: None, just now, minutes, hours, days
- templates instance: globals, filter registration

Phase B.5 of the test coverage sprint.
"""

from datetime import UTC, datetime, timedelta

# ---------------------------------------------------------------------------
# _timeago filter
# ---------------------------------------------------------------------------


class TestTimeagoFilter:
    """The _timeago filter converts datetimes to human-readable relative strings."""

    def _get_filter(self):
        from app.core.templates import _timeago

        return _timeago

    def test_none_returns_never(self):
        assert self._get_filter()(None) == "never"

    def test_just_now(self):
        now = datetime.now(UTC)
        assert self._get_filter()(now) == "just now"

    def test_seconds_ago_still_just_now(self):
        dt = datetime.now(UTC) - timedelta(seconds=30)
        assert self._get_filter()(dt) == "just now"

    def test_minutes_ago(self):
        dt = datetime.now(UTC) - timedelta(minutes=5)
        assert self._get_filter()(dt) == "5m ago"

    def test_one_minute_ago(self):
        dt = datetime.now(UTC) - timedelta(minutes=1, seconds=10)
        assert self._get_filter()(dt) == "1m ago"

    def test_59_minutes_ago(self):
        dt = datetime.now(UTC) - timedelta(minutes=59)
        assert self._get_filter()(dt) == "59m ago"

    def test_hours_ago(self):
        dt = datetime.now(UTC) - timedelta(hours=3)
        assert self._get_filter()(dt) == "3h ago"

    def test_one_hour_ago(self):
        dt = datetime.now(UTC) - timedelta(hours=1, minutes=30)
        assert self._get_filter()(dt) == "1h ago"

    def test_23_hours_ago(self):
        dt = datetime.now(UTC) - timedelta(hours=23)
        assert self._get_filter()(dt) == "23h ago"

    def test_days_ago(self):
        dt = datetime.now(UTC) - timedelta(days=7)
        assert self._get_filter()(dt) == "7d ago"

    def test_one_day_ago(self):
        dt = datetime.now(UTC) - timedelta(days=1)
        assert self._get_filter()(dt) == "1d ago"

    def test_naive_datetime_treated_as_utc(self):
        """Naive datetimes get UTC tzinfo attached before comparison."""
        dt = datetime.now(UTC) - timedelta(hours=2)
        naive = dt.replace(tzinfo=None)
        assert self._get_filter()(naive) == "2h ago"


# ---------------------------------------------------------------------------
# templates instance
# ---------------------------------------------------------------------------


class TestTemplatesInstance:
    """The shared templates instance has expected globals and filters."""

    def test_has_app_version_global(self):
        from app.core.templates import templates

        assert "app_version" in templates.env.globals

    def test_has_timeago_filter(self):
        from app.core.templates import templates

        assert "timeago" in templates.env.filters

    def test_timeago_filter_is_callable(self):
        from app.core.templates import templates

        assert callable(templates.env.filters["timeago"])

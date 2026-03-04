"""Tests for the data retention service (6ty)."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.services.retention_service import (
    DEFAULT_RETENTION,
    RetentionService,
    _TABLE_CONFIG,
    run_retention_cleanup,
)


class TestRetentionService:
    """Unit tests for RetentionService."""

    def _make_service(self, db=None, overrides=None):
        db = db or MagicMock()
        return RetentionService(db, overrides)

    def test_default_retention_periods(self):
        """Service should use DEFAULT_RETENTION when no overrides given."""
        service = self._make_service()
        assert service.retention == DEFAULT_RETENTION

    def test_override_retention_periods(self):
        """Overrides should merge with defaults."""
        service = self._make_service(overrides={"sync_job_logs": 7})
        assert service.retention["sync_job_logs"] == 7
        # Other defaults remain
        assert service.retention["cost_snapshots"] == 365

    def test_cleanup_table_deletes_old_records(self):
        """cleanup_table should delete rows older than retention period."""
        db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.delete.return_value = 42
        mock_query.filter.return_value = mock_filter
        db.query.return_value = mock_query

        service = self._make_service(db)
        model = MagicMock()
        # Use a MagicMock that supports < via __lt__ (like a SA column)
        date_col = MagicMock()
        date_col.__lt__ = MagicMock(return_value="filter_expr")

        count = service.cleanup_table(model, date_col, "cost_snapshots")

        assert count == 42
        db.query.assert_called_once_with(model)
        date_col.__lt__.assert_called_once()  # cutoff datetime passed
        mock_filter.delete.assert_called_once_with(synchronize_session=False)
        db.commit.assert_called_once()

    def test_run_all_processes_all_tables(self):
        """run_all should process every table in _TABLE_CONFIG."""
        db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.delete.return_value = 5
        mock_query.filter.return_value = mock_filter
        db.query.return_value = mock_query

        service = self._make_service(db)
        results = service.run_all()

        assert len(results) == len(_TABLE_CONFIG)
        assert all(v == 5 for v in results.values())

    def test_table_config_uses_correct_columns(self):
        """Verify _TABLE_CONFIG references real model attributes."""
        for table_name, model, date_col in _TABLE_CONFIG:
            assert table_name in DEFAULT_RETENTION, f"{table_name} not in DEFAULT_RETENTION"
            # date_col should be an InstrumentedAttribute with a key
            assert hasattr(date_col, "key"), (
                f"{table_name} date_col is not a valid column attribute"
            )


class TestRunRetentionCleanup:
    """Tests for the convenience wrapper."""

    @patch("app.services.retention_service.get_db_context")
    def test_uses_context_manager(self, mock_ctx):
        """run_retention_cleanup should use get_db_context."""
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.delete.return_value = 0
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

        results = run_retention_cleanup()

        mock_ctx.assert_called_once()
        assert isinstance(results, dict)

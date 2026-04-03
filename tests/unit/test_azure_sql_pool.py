"""Unit tests for app/core/azure_sql_pool.py.

Tests transient error codes, is_azure_sql detection, engine arg
configuration, retry decorator, pool stats, and reset logic.
"""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.pool import NullPool, QueuePool

# Test-only fake connection strings (not real credentials)
_MSSQL_PYODBC_URL = "mssql+pyodbc://user:pass@server/db"  # pragma: allowlist secret
_AZURE_SQL_URL = (
    "mssql+pyodbc://user:pass@server.database.windows.net/db"  # pragma: allowlist secret
)
_AZURE_SQL_URL2 = (
    "mssql+pyodbc://user:pass@myserver.database.windows.net/mydb"  # pragma: allowlist secret
)
_PLAIN_MSSQL_URL = "mssql://user:pass@server/db"  # pragma: allowlist secret
_POSTGRES_URL = "postgresql://user:pass@localhost/db"  # pragma: allowlist secret

# ---------------------------------------------------------------------------
# Transient error code constants
# ---------------------------------------------------------------------------


class TestAzureSqlTransientErrors:
    """Verify AZURE_SQL_TRANSIENT_ERRORS contains expected codes."""

    def test_contains_communication_link_failure(self):
        from app.core.azure_sql_pool import AZURE_SQL_TRANSIENT_ERRORS

        assert "08S01" in AZURE_SQL_TRANSIENT_ERRORS

    def test_contains_deadlock_codes(self):
        from app.core.azure_sql_pool import AZURE_SQL_TRANSIENT_ERRORS

        assert "40001" in AZURE_SQL_TRANSIENT_ERRORS  # Deadlock victim
        assert "40020" in AZURE_SQL_TRANSIENT_ERRORS  # Deadlock

    def test_contains_failover_code(self):
        from app.core.azure_sql_pool import AZURE_SQL_TRANSIENT_ERRORS

        assert "40613" in AZURE_SQL_TRANSIENT_ERRORS

    def test_contains_throttling_codes(self):
        from app.core.azure_sql_pool import AZURE_SQL_TRANSIENT_ERRORS

        for code in ("49918", "49919", "49920"):
            assert code in AZURE_SQL_TRANSIENT_ERRORS

    def test_contains_service_busy_codes(self):
        from app.core.azure_sql_pool import AZURE_SQL_TRANSIENT_ERRORS

        assert "40143" in AZURE_SQL_TRANSIENT_ERRORS  # Service is too busy
        assert "40501" in AZURE_SQL_TRANSIENT_ERRORS  # Service is busy

    def test_is_frozenset(self):
        from app.core.azure_sql_pool import AZURE_SQL_TRANSIENT_ERRORS

        assert isinstance(AZURE_SQL_TRANSIENT_ERRORS, frozenset)

    def test_has_expected_minimum_count(self):
        """At least 14 known error codes should be present."""
        from app.core.azure_sql_pool import AZURE_SQL_TRANSIENT_ERRORS

        assert len(AZURE_SQL_TRANSIENT_ERRORS) >= 14


# ---------------------------------------------------------------------------
# is_azure_sql()
# ---------------------------------------------------------------------------


class TestIsAzureSql:
    """Test is_azure_sql() with various database_url values."""

    def _call(self, database_url: str) -> bool:
        mock_settings = MagicMock()
        mock_settings.database_url = database_url
        with patch("app.core.azure_sql_pool.settings", mock_settings):
            from app.core.azure_sql_pool import is_azure_sql

            return is_azure_sql()

    def test_sqlite_returns_false(self):
        assert self._call("sqlite:///./data/governance.db") is False

    def test_mssql_pyodbc_returns_true(self):
        assert self._call(_MSSQL_PYODBC_URL) is True

    def test_azure_sql_windows_net_returns_true(self):
        assert self._call(_AZURE_SQL_URL2) is True

    def test_plain_mssql_returns_true(self):
        assert self._call(_PLAIN_MSSQL_URL) is True

    def test_postgresql_returns_false(self):
        assert self._call(_POSTGRES_URL) is False

    def test_sqlite_with_mssql_in_path_returns_false(self):
        """sqlite:// prefix should short-circuit even if 'mssql' appears later."""
        assert self._call("sqlite:///mssql_backup.db") is False


# ---------------------------------------------------------------------------
# get_azure_sql_engine_args()
# ---------------------------------------------------------------------------


class TestGetAzureSqlEngineArgs:
    """Test engine argument construction for various environments."""

    def _make_settings(self, **overrides):
        s = MagicMock()
        s.database_url = overrides.pop("database_url", "sqlite:///./data/governance.db")
        s.is_azure_functions = overrides.pop("is_azure_functions", False)
        s.azure_sql_use_null_pool = overrides.pop("azure_sql_use_null_pool", False)
        s.azure_sql_pool_size = overrides.pop("azure_sql_pool_size", 5)
        s.azure_sql_max_overflow = overrides.pop("azure_sql_max_overflow", 10)
        s.azure_sql_pool_timeout = overrides.pop("azure_sql_pool_timeout", 30)
        s.azure_sql_pool_pre_ping = overrides.pop("azure_sql_pool_pre_ping", True)
        s.azure_sql_pool_recycle = overrides.pop("azure_sql_pool_recycle", 1800)
        return s

    def test_sqlite_returns_base_args_unchanged(self):
        mock_settings = self._make_settings(database_url="sqlite:///test.db")
        with patch("app.core.azure_sql_pool.settings", mock_settings):
            from app.core.azure_sql_pool import get_azure_sql_engine_args

            base = {"echo": False}
            result = get_azure_sql_engine_args(dict(base))
            assert result == base

    def test_azure_sql_returns_queue_pool_args(self):
        mock_settings = self._make_settings(database_url=_AZURE_SQL_URL)
        with patch("app.core.azure_sql_pool.settings", mock_settings):
            from app.core.azure_sql_pool import get_azure_sql_engine_args

            result = get_azure_sql_engine_args({})
            assert result["poolclass"] is QueuePool
            assert result["pool_size"] == 5
            assert result["max_overflow"] == 10
            assert result["pool_timeout"] == 30
            assert result["pool_pre_ping"] is True
            assert result["pool_recycle"] == 1800

    def test_azure_functions_returns_null_pool(self):
        mock_settings = self._make_settings(
            database_url=_AZURE_SQL_URL,
            is_azure_functions=True,
        )
        with patch("app.core.azure_sql_pool.settings", mock_settings):
            from app.core.azure_sql_pool import get_azure_sql_engine_args

            result = get_azure_sql_engine_args({})
            assert result["poolclass"] is NullPool
            # NullPool branch should NOT include QueuePool keys
            assert "pool_size" not in result

    def test_null_pool_flag_returns_null_pool(self):
        mock_settings = self._make_settings(
            database_url=_AZURE_SQL_URL,
            azure_sql_use_null_pool=True,
        )
        with patch("app.core.azure_sql_pool.settings", mock_settings):
            from app.core.azure_sql_pool import get_azure_sql_engine_args

            result = get_azure_sql_engine_args({})
            assert result["poolclass"] is NullPool

    def test_custom_pool_settings_are_honoured(self):
        mock_settings = self._make_settings(
            database_url=_AZURE_SQL_URL,
            azure_sql_pool_size=20,
            azure_sql_max_overflow=40,
            azure_sql_pool_recycle=900,
        )
        with patch("app.core.azure_sql_pool.settings", mock_settings):
            from app.core.azure_sql_pool import get_azure_sql_engine_args

            result = get_azure_sql_engine_args({})
            assert result["pool_size"] == 20
            assert result["max_overflow"] == 40
            assert result["pool_recycle"] == 900


# ---------------------------------------------------------------------------
# is_transient_error()
# ---------------------------------------------------------------------------


class TestIsTransientError:
    """Test transient error detection logic."""

    def test_known_sql_code_detected(self):
        from app.core.azure_sql_pool import is_transient_error

        err = Exception("SQLSTATE 40613: Database is not currently available")
        assert is_transient_error(err) is True

    def test_pattern_match_deadlock(self):
        from app.core.azure_sql_pool import is_transient_error

        err = Exception("Transaction was deadlock victim")
        assert is_transient_error(err) is True

    def test_pattern_match_service_busy(self):
        from app.core.azure_sql_pool import is_transient_error

        err = Exception("Service is busy, please retry later")
        assert is_transient_error(err) is True

    def test_non_transient_error_returns_false(self):
        from app.core.azure_sql_pool import is_transient_error

        err = Exception("Invalid column name 'foo'")
        assert is_transient_error(err) is False

    def test_timeout_pattern_detected(self):
        from app.core.azure_sql_pool import is_transient_error

        err = Exception("Connection timeout expired")
        assert is_transient_error(err) is True


# ---------------------------------------------------------------------------
# with_azure_sql_retry() decorator
# ---------------------------------------------------------------------------


class TestWithAzureSqlRetry:
    """Test the retry decorator for transient fault handling."""

    def _make_retry_settings(self):
        s = MagicMock()
        s.azure_sql_connection_retry_attempts = 3
        s.azure_sql_connection_retry_delay = 0.01  # fast for tests
        return s

    @patch("app.core.azure_sql_pool.time.sleep")
    def test_retries_on_transient_error_then_succeeds(self, mock_sleep):
        mock_settings = self._make_retry_settings()
        with patch("app.core.azure_sql_pool.settings", mock_settings):
            from app.core.azure_sql_pool import with_azure_sql_retry

            call_count = 0

            @with_azure_sql_retry()
            def flaky():
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    raise Exception("SQLSTATE 40613: Database failover")
                return "ok"

            assert flaky() == "ok"
            assert call_count == 3
            assert mock_sleep.call_count == 2  # slept twice before attempt 3

    @patch("app.core.azure_sql_pool.time.sleep")
    def test_raises_immediately_on_non_transient_error(self, mock_sleep):
        mock_settings = self._make_retry_settings()
        with patch("app.core.azure_sql_pool.settings", mock_settings):
            from app.core.azure_sql_pool import with_azure_sql_retry

            @with_azure_sql_retry()
            def bad_query():
                raise Exception("Invalid column name 'foo'")

            with pytest.raises(Exception, match="Invalid column"):
                bad_query()

            mock_sleep.assert_not_called()

    @patch("app.core.azure_sql_pool.time.sleep")
    def test_raises_after_all_attempts_exhausted(self, mock_sleep):
        mock_settings = self._make_retry_settings()
        with patch("app.core.azure_sql_pool.settings", mock_settings):
            from app.core.azure_sql_pool import with_azure_sql_retry

            @with_azure_sql_retry()
            def always_fails():
                raise Exception("SQLSTATE 40613: always failing")

            with pytest.raises(Exception, match="40613"):
                always_fails()

    @patch("app.core.azure_sql_pool.time.sleep")
    def test_no_retry_needed_when_no_error(self, mock_sleep):
        mock_settings = self._make_retry_settings()
        with patch("app.core.azure_sql_pool.settings", mock_settings):
            from app.core.azure_sql_pool import with_azure_sql_retry

            @with_azure_sql_retry()
            def healthy():
                return 42

            assert healthy() == 42
            mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# get_pool_stats()
# ---------------------------------------------------------------------------


class TestGetPoolStats:
    """Test pool statistics reporting."""

    def test_returns_error_when_engine_is_none(self):
        from app.core.azure_sql_pool import get_pool_stats

        result = get_pool_stats(None)
        assert result == {"error": "Engine not initialized"}

    def test_returns_null_pool_info(self):
        from app.core.azure_sql_pool import get_pool_stats

        engine = MagicMock()
        engine.pool = NullPool(creator=lambda: None)

        result = get_pool_stats(engine)
        assert result["pool_type"] == "NullPool"
        assert "Serverless" in result.get("note", "")

    def test_returns_queue_pool_metrics(self):
        mock_settings = MagicMock()
        mock_settings.azure_sql_max_overflow = 10
        mock_settings.azure_sql_pool_size = 5
        with patch("app.core.azure_sql_pool.settings", mock_settings):
            from app.core.azure_sql_pool import get_pool_stats

            pool = MagicMock()
            pool.size.return_value = 5
            pool.checkedin.return_value = 3
            pool.checkedout.return_value = 2
            pool.overflow.return_value = 0

            engine = MagicMock()
            engine.pool = pool

            result = get_pool_stats(engine)

            assert result["pool_type"] == "QueuePool"
            assert result["size"] == 5
            assert result["checked_in"] == 3
            assert result["checked_out"] == 2
            assert result["overflow"] == 0
            assert result["utilization_percent"] == pytest.approx(40.0)


# ---------------------------------------------------------------------------
# reset_pool()
# ---------------------------------------------------------------------------


class TestResetPool:
    """Test connection pool reset."""

    def test_disposes_engine_when_not_none(self):
        from app.core.azure_sql_pool import reset_pool

        engine = MagicMock()
        reset_pool(engine)
        engine.dispose.assert_called_once()

    def test_noop_when_engine_is_none(self):
        from app.core.azure_sql_pool import reset_pool

        # Should not raise
        reset_pool(None)

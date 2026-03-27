"""Unit tests for the Redis-backed TokenBlacklist with in-memory fallback.

Tests cover:
- In-memory fallback when Redis is not configured
- add / contains / size / clear operations
- TTL calculation from JWT expiration claims
- Module-level convenience functions (blacklist_token, is_token_blacklisted, etc.)
- Redis failure graceful degradation
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import jwt

from app.core.token_blacklist import (
    TokenBlacklist,
    _token_blacklist,
    blacklist_token,
    get_blacklist_backend,
    get_blacklist_size,
    is_token_blacklisted,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_blacklist():
    """Ensure a clean blacklist state for every test."""
    _token_blacklist.clear()
    yield
    _token_blacklist.clear()


@pytest.fixture
def mock_settings_no_redis():
    """Settings with no Redis URL configured."""
    settings = MagicMock()
    settings.redis_url = None
    return settings


@pytest.fixture
def mock_settings_with_redis():
    """Settings with a Redis URL configured."""
    settings = MagicMock()
    settings.redis_url = "redis://localhost:6379/0"
    return settings


def _make_token(
    secret: str = "test-secret",
    exp_delta: timedelta | None = None,
) -> str:
    """Helper to create a minimal JWT for testing."""
    payload: dict = {
        "sub": "user-1",
        "iss": "azure-governance-platform",
        "aud": "azure-governance-api",
        "type": "access",
        "iat": datetime.now(UTC),
    }
    if exp_delta is not None:
        payload["exp"] = datetime.now(UTC) + exp_delta
    return jwt.encode(payload, secret, algorithm="HS256")


# ---------------------------------------------------------------------------
# TokenBlacklist class - in-memory fallback
# ---------------------------------------------------------------------------


class TestTokenBlacklistInMemory:
    """Tests for TokenBlacklist operating in pure in-memory mode."""

    @patch("app.core.token_blacklist.get_settings")
    def test_backend_is_memory_when_no_redis_url(self, mock_get_settings, mock_settings_no_redis):
        """Backend reports 'memory' when Redis URL is not configured."""
        mock_get_settings.return_value = mock_settings_no_redis
        bl = TokenBlacklist()
        assert bl.backend == "memory"

    @patch("app.core.token_blacklist.get_settings")
    def test_add_and_contains(self, mock_get_settings, mock_settings_no_redis):
        """add() stores a token and contains() finds it."""
        mock_get_settings.return_value = mock_settings_no_redis
        bl = TokenBlacklist()

        bl.add("tok-abc")
        assert bl.contains("tok-abc") is True

    @patch("app.core.token_blacklist.get_settings")
    def test_contains_returns_false_for_unknown_token(
        self, mock_get_settings, mock_settings_no_redis
    ):
        """contains() returns False for tokens never added."""
        mock_get_settings.return_value = mock_settings_no_redis
        bl = TokenBlacklist()

        assert bl.contains("tok-unknown") is False

    @patch("app.core.token_blacklist.get_settings")
    def test_size_reflects_added_tokens(self, mock_get_settings, mock_settings_no_redis):
        """size() returns the count of blacklisted tokens."""
        mock_get_settings.return_value = mock_settings_no_redis
        bl = TokenBlacklist()

        assert bl.size() == 0
        bl.add("tok-1")
        bl.add("tok-2")
        assert bl.size() == 2

    @patch("app.core.token_blacklist.get_settings")
    def test_clear_removes_all_tokens(self, mock_get_settings, mock_settings_no_redis):
        """clear() empties the in-memory set."""
        mock_get_settings.return_value = mock_settings_no_redis
        bl = TokenBlacklist()

        bl.add("tok-1")
        bl.add("tok-2")
        bl.clear()
        assert bl.size() == 0
        assert bl.contains("tok-1") is False

    @patch("app.core.token_blacklist.get_settings")
    def test_add_duplicate_is_idempotent(self, mock_get_settings, mock_settings_no_redis):
        """Adding the same token twice doesn't increase size."""
        mock_get_settings.return_value = mock_settings_no_redis
        bl = TokenBlacklist()

        bl.add("tok-dup")
        bl.add("tok-dup")
        assert bl.size() == 1


# ---------------------------------------------------------------------------
# TokenBlacklist class - Redis backend (mocked)
# ---------------------------------------------------------------------------


class TestTokenBlacklistRedis:
    """Tests for TokenBlacklist with a mocked Redis connection."""

    def _make_bl_with_mock_redis(self, mock_redis=None):
        """Create a TokenBlacklist wired to a mock Redis."""
        bl = TokenBlacklist.__new__(TokenBlacklist)
        bl._memory_fallback = set()
        bl._redis = mock_redis or MagicMock()
        bl._backend = "redis"
        return bl

    def test_backend_is_redis_when_connected(self):
        """Backend reports 'redis' when Redis connects successfully."""
        bl = self._make_bl_with_mock_redis()
        assert bl.backend == "redis"

    def test_add_calls_redis_setex(self):
        """add() uses Redis setex when Redis is available."""
        bl = self._make_bl_with_mock_redis()

        bl.add("tok-redis", ttl_seconds=3600)

        bl._redis.setex.assert_called_once_with("blacklist:tok-redis", 3600, "1")

    def test_contains_checks_redis_exists(self):
        """contains() queries Redis exists when Redis is available."""
        mock_redis = MagicMock()
        mock_redis.exists.return_value = 1
        bl = self._make_bl_with_mock_redis(mock_redis)

        assert bl.contains("tok-redis") is True
        bl._redis.exists.assert_called_once_with("blacklist:tok-redis")

    def test_contains_returns_false_when_redis_key_missing(self):
        """contains() returns False when Redis key does not exist."""
        mock_redis = MagicMock()
        mock_redis.exists.return_value = 0
        bl = self._make_bl_with_mock_redis(mock_redis)

        assert bl.contains("tok-missing") is False

    def test_redis_failure_falls_back_to_memory_on_add(self):
        """When Redis setex fails, token is stored in memory fallback."""
        mock_redis = MagicMock()
        mock_redis.setex.side_effect = ConnectionError("Redis down")
        bl = self._make_bl_with_mock_redis(mock_redis)

        bl.add("tok-fallback")
        assert "tok-fallback" in bl._memory_fallback

    def test_redis_failure_falls_back_to_memory_on_contains(self):
        """When Redis exists fails, falls back to in-memory check."""
        mock_redis = MagicMock()
        mock_redis.exists.side_effect = ConnectionError("Redis down")
        bl = self._make_bl_with_mock_redis(mock_redis)
        bl._memory_fallback = {"tok-mem"}

        assert bl.contains("tok-mem") is True
        assert bl.contains("tok-missing") is False

    def test_size_with_redis_scans_keys(self):
        """size() scans Redis keys when Redis is available."""
        mock_redis = MagicMock()
        mock_redis.scan_iter.return_value = iter(
            [
                "blacklist:tok-1",
                "blacklist:tok-2",
                "blacklist:tok-3",
            ]
        )
        bl = self._make_bl_with_mock_redis(mock_redis)

        assert bl.size() == 3


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------


class TestModuleLevelFunctions:
    """Tests for the module-level blacklist_token / is_token_blacklisted / etc."""

    def test_blacklist_and_check(self):
        """blacklist_token() + is_token_blacklisted() round-trip works."""
        token = _make_token(exp_delta=timedelta(hours=1))

        assert is_token_blacklisted(token) is False
        blacklist_token(token)
        assert is_token_blacklisted(token) is True

    def test_get_blacklist_size(self):
        """get_blacklist_size() reflects the current count."""
        assert get_blacklist_size() == 0

        token1 = _make_token(exp_delta=timedelta(hours=1))
        token2 = _make_token(exp_delta=timedelta(hours=2))
        blacklist_token(token1)
        blacklist_token(token2)

        assert get_blacklist_size() == 2

    def test_get_blacklist_backend(self):
        """get_blacklist_backend() returns the singleton's backend."""
        # Without Redis installed, should be 'memory'
        backend = get_blacklist_backend()
        assert backend in ("memory", "redis")

    def test_blacklist_token_with_exp_calculates_ttl(self):
        """blacklist_token() extracts exp claim for TTL calculation."""
        token = _make_token(exp_delta=timedelta(hours=2))

        with patch.object(_token_blacklist, "add") as mock_add:
            blacklist_token(token)
            mock_add.assert_called_once()
            ttl = mock_add.call_args.kwargs["ttl_seconds"]
            # TTL should be approximately 7200 seconds (2 hours)
            assert 7100 <= ttl <= 7300

    def test_blacklist_token_without_exp_uses_default_ttl(self):
        """blacklist_token() uses 24h default when token has no exp claim."""
        payload = {
            "sub": "user-no-exp",
            "iss": "azure-governance-platform",
            "aud": "azure-governance-api",
            "type": "access",
        }
        token = jwt.encode(payload, "test-secret", algorithm="HS256")

        with patch.object(_token_blacklist, "add") as mock_add:
            blacklist_token(token)
            mock_add.assert_called_once()
            ttl = mock_add.call_args.kwargs["ttl_seconds"]
            assert ttl == 86400  # 24 hours default

    def test_blacklist_token_with_expired_token_uses_zero_ttl(self):
        """blacklist_token() sets TTL to 0 for already-expired tokens."""
        token = _make_token(exp_delta=timedelta(hours=-1))

        with patch.object(_token_blacklist, "add") as mock_add:
            blacklist_token(token)
            mock_add.assert_called_once()
            ttl = mock_add.call_args.kwargs["ttl_seconds"]
            assert ttl == 0

    def test_blacklist_token_with_malformed_token_uses_default_ttl(self):
        """blacklist_token() uses default TTL for un-decodable tokens."""
        with patch.object(_token_blacklist, "add") as mock_add:
            blacklist_token("not-a-jwt-at-all")
            mock_add.assert_called_once()
            ttl = mock_add.call_args.kwargs["ttl_seconds"]
            assert ttl == 86400

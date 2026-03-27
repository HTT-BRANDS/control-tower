"""Redis-backed token blacklist with in-memory fallback.

Provides a production-ready token blacklist for JWT logout/revocation:
- Uses Redis when available (shared across instances, survives restarts)
- Falls back to in-memory set for development (no Redis needed)
- Tokens auto-expire based on JWT expiration time (TTL)
- Graceful degradation: Redis failures fall back to memory silently
"""

import logging
from datetime import UTC, datetime
from typing import Any

import jwt

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class TokenBlacklist:
    """Token blacklist with Redis backend and in-memory fallback.

    Uses Redis when available for production (shared across instances,
    survives restarts). Falls back to in-memory set for development.
    Tokens auto-expire based on JWT expiration time.
    """

    REDIS_KEY_PREFIX = "blacklist:"
    DEFAULT_TTL_SECONDS = 86400  # 24 hours = max token lifetime

    def __init__(self) -> None:
        self._memory_fallback: set[str] = set()
        self._redis: Any = None
        self._backend: str = "memory"
        self._init_redis()

    def _init_redis(self) -> None:
        """Attempt to connect to Redis for token blacklist storage."""
        settings = get_settings()
        if not settings.redis_url:
            logger.info("Token blacklist using in-memory storage (no Redis URL configured)")
            return
        try:
            import redis as redis_lib

            self._redis = redis_lib.from_url(
                settings.redis_url,
                decode_responses=True,
            )
            self._redis.ping()
            self._backend = "redis"
            logger.info("Token blacklist using Redis backend")
        except ImportError:
            logger.warning("redis package not installed, token blacklist using in-memory fallback")
            self._redis = None
        except Exception as e:
            logger.warning(f"Redis unavailable for token blacklist: {e}, using in-memory fallback")
            self._redis = None

    def add(self, token: str, ttl_seconds: int | None = None) -> None:
        """Blacklist a token with an optional TTL.

        Args:
            token: JWT token string to blacklist.
            ttl_seconds: Time-to-live in seconds. Defaults to 24 h.
        """
        if ttl_seconds is None:
            ttl_seconds = self.DEFAULT_TTL_SECONDS

        if self._redis is not None:
            try:
                self._redis.setex(
                    f"{self.REDIS_KEY_PREFIX}{token}",
                    ttl_seconds,
                    "1",
                )
                return
            except Exception as exc:
                logger.warning(f"Redis setex failed, falling back to memory: {exc}")
        self._memory_fallback.add(token)

    def contains(self, token: str) -> bool:
        """Check whether a token has been blacklisted.

        Args:
            token: JWT token string to check.

        Returns:
            True if the token is blacklisted.
        """
        if self._redis is not None:
            try:
                return bool(self._redis.exists(f"{self.REDIS_KEY_PREFIX}{token}"))
            except Exception as exc:
                logger.warning(f"Redis exists check failed, falling back to memory: {exc}")
        return token in self._memory_fallback

    def size(self) -> int:
        """Return approximate number of blacklisted tokens.

        For Redis this performs a SCAN over the key prefix.
        """
        if self._redis is not None:
            try:
                count = 0
                for _ in self._redis.scan_iter(f"{self.REDIS_KEY_PREFIX}*", count=1000):
                    count += 1
                return count
            except Exception as exc:
                logger.warning(f"Redis scan failed, falling back to memory: {exc}")
        return len(self._memory_fallback)

    @property
    def backend(self) -> str:
        """Return the active backend name ('redis' or 'memory')."""
        return self._backend

    def clear(self) -> None:
        """Clear all blacklisted tokens (used in tests)."""
        self._memory_fallback.clear()
        if self._redis is not None:
            try:
                for key in self._redis.scan_iter(f"{self.REDIS_KEY_PREFIX}*", count=1000):
                    self._redis.delete(key)
            except Exception:
                pass


# Module-level singleton
_token_blacklist = TokenBlacklist()


def is_token_blacklisted(token: str) -> bool:
    """Check if a token has been blacklisted.

    Args:
        token: JWT token to check

    Returns:
        True if token is blacklisted
    """
    return _token_blacklist.contains(token)


def blacklist_token(token: str) -> None:
    """Add a token to the blacklist with automatic TTL from JWT expiration.

    Extracts the ``exp`` claim from the token to set a precise TTL so
    that blacklist entries are automatically cleaned up once the token
    would have expired anyway.

    Args:
        token: JWT token to blacklist
    """
    ttl = TokenBlacklist.DEFAULT_TTL_SECONDS
    try:
        payload = jwt.decode(token, options={"verify_signature": False}, algorithms=["HS256", "RS256"])
        exp = payload.get("exp")
        if exp is not None:
            remaining = int(exp - datetime.now(UTC).timestamp())
            ttl = max(remaining, 0)
    except Exception:
        pass  # Fall back to default TTL
    _token_blacklist.add(token, ttl_seconds=ttl)


def get_blacklist_size() -> int:
    """Get the number of blacklisted tokens.

    Returns:
        Count of blacklisted tokens
    """
    return _token_blacklist.size()


def get_blacklist_backend() -> str:
    """Return the active blacklist backend name ('redis' or 'memory').

    Useful for health check endpoints.
    """
    return _token_blacklist.backend

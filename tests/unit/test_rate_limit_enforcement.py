"""Rate-limit enforcement tests.

Closes the audit gap: `app.core.rate_limit` had zero behavioural tests. The
HTTP middleware bypasses rate limiting in dev/e2e, so the durable place to test
the *enforcement logic* is the limiter itself. These tests are deterministic
(in-memory backend, no Redis, no real clock dependence within a window).

STRIDE coverage: D1 (HTTP flood / brute force), and the login/auth tightening
that protects S1 (credential stuffing).
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.core.rate_limit import (
    DEFAULT_LIMITS,
    RateLimitConfig,
    RateLimiter,
)


class _FakeClient:
    host = "203.0.113.7"


class _FakeState:
    pass


class _FakeRequest:
    """Minimal stand-in for starlette Request used by the limiter."""

    def __init__(
        self,
        ip: str = "203.0.113.7",
        user_id: str | None = None,
        path: str = "/api/v1/costs/summary",
    ):
        self._ip = ip
        self.client = type("C", (), {"host": ip})()
        self.headers: dict[str, str] = {}
        self.url = type("U", (), {"path": path})()
        self.state = _FakeState()
        if user_id:
            self.state.user_id = user_id


@pytest.fixture
def limiter() -> RateLimiter:
    rl = RateLimiter()
    rl._redis = None  # force in-memory path
    rl._enabled = True
    rl._memory_cache.clear()
    return rl


async def test_allows_up_to_limit_then_blocks(limiter: RateLimiter) -> None:
    cfg = RateLimitConfig(requests=3, window_seconds=60)
    req = _FakeRequest()
    results = [(await limiter.is_allowed(req, cfg))[0] for _ in range(4)]
    assert results == [True, True, True, False], results


async def test_remaining_header_decrements(limiter: RateLimiter) -> None:
    cfg = RateLimitConfig(requests=5, window_seconds=60)
    req = _FakeRequest()
    _, h1 = await limiter.is_allowed(req, cfg)
    _, h2 = await limiter.is_allowed(req, cfg)
    assert int(h1["X-RateLimit-Remaining"]) > int(h2["X-RateLimit-Remaining"])
    assert h1["X-RateLimit-Limit"] == "5"


async def test_check_rate_limit_raises_429(limiter: RateLimiter) -> None:
    cfg = RateLimitConfig(requests=1, window_seconds=60)
    req = _FakeRequest()
    await limiter.check_rate_limit(req, custom_config=cfg)  # 1st ok
    with pytest.raises(HTTPException) as exc:
        await limiter.check_rate_limit(req, custom_config=cfg)  # 2nd blocked
    assert exc.value.status_code == 429
    assert "Retry-After" in exc.value.headers


async def test_distinct_clients_have_independent_budgets(limiter: RateLimiter) -> None:
    cfg = RateLimitConfig(requests=1, window_seconds=60)
    a = _FakeRequest(ip="198.51.100.1")
    b = _FakeRequest(ip="198.51.100.2")
    assert (await limiter.is_allowed(a, cfg))[0] is True
    assert (await limiter.is_allowed(a, cfg))[0] is False  # a exhausted
    assert (await limiter.is_allowed(b, cfg))[0] is True  # b unaffected


async def test_xforwarded_for_spoofing_does_not_share_one_bucket(
    limiter: RateLimiter,
) -> None:
    """An attacker rotating X-Forwarded-For gets *separate* (not shared) buckets.

    This documents current behaviour: the limiter keys on the first XFF hop.
    Behind a trusted proxy that overwrites XFF this is correct; this test pins
    the behaviour so a regression that collapses all clients into one bucket
    (DoS amplification) is caught.
    """
    cfg = RateLimitConfig(requests=1, window_seconds=60)
    req1 = _FakeRequest()
    req1.headers = {"X-Forwarded-For": "10.0.0.1"}
    req2 = _FakeRequest()
    req2.headers = {"X-Forwarded-For": "10.0.0.2"}
    assert (await limiter.is_allowed(req1, cfg))[0] is True
    assert (await limiter.is_allowed(req2, cfg))[0] is True


def test_login_endpoint_is_strictly_limited() -> None:
    """Login/token must be far tighter than default to resist brute force."""
    login = DEFAULT_LIMITS["login"]
    default = DEFAULT_LIMITS["default"]
    assert login.requests <= 5
    assert login.window_seconds >= 60
    assert login.requests < default.requests


@pytest.mark.parametrize(
    "path,expected_key",
    [
        ("/api/v1/auth/login", "login"),
        ("/api/v1/auth/token", "login"),
        ("/api/v1/auth/me", "auth"),
        ("/api/v1/admin/users", "admin"),
        ("/api/v1/sync/status", "sync"),
        ("/api/v1/bulk/tag", "bulk"),
        ("/api/v1/exports/costs", "exports"),
        ("/api/v1/costs/summary", "default"),
    ],
)
def test_endpoint_config_routing(path: str, expected_key: str) -> None:
    rl = RateLimiter()
    assert rl.get_limit_config(path) is DEFAULT_LIMITS[expected_key]


async def test_disabled_limiter_fails_open(limiter: RateLimiter) -> None:
    """When disabled, requests pass (availability over throttling)."""
    limiter._enabled = False
    cfg = RateLimitConfig(requests=1, window_seconds=60)
    req = _FakeRequest()
    for _ in range(10):
        allowed, _ = await limiter.is_allowed(req, cfg)
        assert allowed is True

"""Regression tests for ct-wvn: /api/v1/auth/staging-token always 404'd.

Pre-fix signature::

    async def staging_test_token(
        x_staging_admin_key: str | None = None,
        request: Request = None,   # ← FastAPI may not inject this
    ) -> dict:

FastAPI interpreted ``x_staging_admin_key`` as a query parameter (no
``Header()`` annotation) and ``request: Request = None`` as an unusual
nullable body argument rather than an injected ``Request`` object. The
header value never reached the code, so the constant-time comparison
always failed and every call 404'd — including from properly authorized
E2E test runners.

Post-fix signature::

    async def staging_test_token(
        x_staging_admin_key: str = Header(default="", alias="X-Staging-Admin-Key"),
    ) -> dict:

The ``default=""`` keeps the endpoint defensively 404-shaped: a missing
header returns 404 (not 422) so unauthorized probes can't even tell
the endpoint exists.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client_with_staging_key(monkeypatch):
    """A TestClient where ENVIRONMENT=development and STAGING_ADMIN_KEY is set."""
    monkeypatch.setenv("STAGING_ADMIN_KEY", "test-key-abc123")
    # The endpoint allows 'development' or 'staging' — settings.environment
    # in tests is typically 'development'.
    from app.main import app

    return TestClient(app)


def test_correct_key_returns_200_with_jwt(client_with_staging_key):
    """ct-wvn: matching key in the header should return 200 + JWT."""
    r = client_with_staging_key.post(
        "/api/v1/auth/staging-token",
        headers={"X-Staging-Admin-Key": "test-key-abc123"},
    )
    assert r.status_code == 200, (
        f"ct-wvn: matching key must return 200; got {r.status_code}: {r.text}"
    )
    body = r.json()
    assert "access_token" in body, "ct-wvn: response must contain access_token"
    assert body["access_token"].startswith("eyJ"), "looks like a JWT"


def test_wrong_key_returns_404(client_with_staging_key):
    """Wrong key returns 404 (NOT 401) to avoid leaking endpoint existence."""
    r = client_with_staging_key.post(
        "/api/v1/auth/staging-token",
        headers={"X-Staging-Admin-Key": "WRONG-KEY"},
    )
    assert r.status_code == 404
    assert r.json() == {"detail": "Not found"}


def test_missing_header_returns_404_not_422(client_with_staging_key):
    """ct-wvn: missing header must 404, not 422.

    The pre-fix bug aside, a 422 would betray that the endpoint exists
    and expects a specific header. With ``Header(default="")`` we get
    a clean 404 for missing headers, matching the wrong-key behavior.
    """
    r = client_with_staging_key.post("/api/v1/auth/staging-token")
    assert r.status_code == 404, (
        f"ct-wvn: missing header must 404 (security: don't leak endpoint); "
        f"got {r.status_code}: {r.text}"
    )


def test_no_staging_admin_key_env_returns_404(monkeypatch):
    """When STAGING_ADMIN_KEY env is unset, the endpoint must 404 hard."""
    monkeypatch.delenv("STAGING_ADMIN_KEY", raising=False)
    from app.main import app

    client = TestClient(app)
    r = client.post(
        "/api/v1/auth/staging-token",
        headers={"X-Staging-Admin-Key": "anything"},
    )
    assert r.status_code == 404, (
        "ct-wvn: when STAGING_ADMIN_KEY isn't configured, endpoint must 404 "
        "regardless of what the caller provides"
    )


def test_production_environment_always_404s(monkeypatch):
    """Hard block: production never issues staging tokens, ever."""
    monkeypatch.setenv("STAGING_ADMIN_KEY", "test-key-abc123")
    # Patch settings.environment lookup to simulate production.
    from app.core.config import get_settings

    settings = get_settings()
    with patch.object(settings, "environment", "production"):
        from app.main import app

        client = TestClient(app)
        r = client.post(
            "/api/v1/auth/staging-token",
            headers={"X-Staging-Admin-Key": "test-key-abc123"},
        )
        assert r.status_code == 404, (
            "ct-wvn: production must always 404, even with correct key"
        )

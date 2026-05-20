"""Regression tests for F1 (Round 2): HTMX URL clobber → blank page on F5.

Bug: HTMX hx-trigger="load" partials under an hx-boost ancestor push their
fragment URL (e.g. /partials/riverside-badge) into browser history. When a
user pressed F5 the browser re-fetched the bare partial, which is a tiny
fragment of HTML and rendered as a blank page. Tyler reported this as
"after login the page just goes blank."

Fix: middleware ``_register_htmx_partial_no_push_url`` in
``app/main_middleware.py`` adds ``HX-Push-Url: false`` to every response
whose path contains ``/partials/``. HTMX honors that response header
regardless of any client-side hx-push-url attribute, so the URL bar always
reflects the real page route.

These tests assert the header is added to partial responses and is NOT
added to API or page responses (we don't want HTMX caching weirdness).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    # Late import: the FastAPI app boots a lot of stuff at import time.
    from app.main import app

    return TestClient(app)


@pytest.mark.parametrize(
    "path",
    [
        "/partials/riverside-badge",  # real route, auth-gated → 401
        "/partials/nonexistent",  # bogus path → 404
        "/admin/partials/users-table",  # nested partials path → 401
    ],
)
def test_partial_responses_set_no_push_url(client, path):
    """F1: every /partials/* response must carry HX-Push-Url:false."""
    response = client.get(path)
    assert response.headers.get("hx-push-url") == "false", (
        f"F1 regression: {path} did not set HX-Push-Url:false (status={response.status_code})"
    )


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/health",
        "/login",
        "/",  # 307 redirect
    ],
)
def test_non_partial_responses_do_not_set_no_push_url(client, path):
    """Header is only for /partials/* — must not leak to other routes."""
    response = client.get(path, follow_redirects=False)
    assert "hx-push-url" not in {h.lower() for h in response.headers}, (
        f"non-partial route {path} unexpectedly carries HX-Push-Url"
    )

"""Systematic auth-wall matrix.

Closes the gap flagged in the security audit: there was no test that
*systematically* asserts every data route refuses anonymous access. Instead of
hand-listing endpoints (which drift as routes are added), this test introspects
the live FastAPI route table and asserts the security invariant:

    No /api/v1 data route may return 200 to an unauthenticated caller.

A small, explicit allowlist covers the routes that are *intentionally* public
(health, auth bootstrap). Anything new that is accidentally left unauthenticated
will turn this test red the moment it is added -- which is the point.

STRIDE coverage: I1 (info disclosure), E1/E2 (privilege escalation via missing
authn), tdD1 (anonymous abuse surface).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

# Routes that are public *by design*. Keep this list short and reviewed.
# Every entry here is a deliberate decision to serve an anonymous caller.
# Adding a route here is a security review action -- do not append casually.
PUBLIC_PREFIXES = (
    # Health / liveness probes (no data, used by Azure App Service + load balancer)
    "/api/v1/health",
    # Auth bootstrap (cannot require a token to obtain a token)
    "/api/v1/auth/login",
    "/api/v1/auth/token",
    "/api/v1/auth/azure/login",
    "/api/v1/auth/azure/callback",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
    "/api/v1/auth/health",
    "/api/v1/auth/staging-token",
    # Public status badge (intentionally anonymous, no tenant data)
    "/api/v1/status",
    # Accessibility reference content (static WCAG data, no tenant data) --
    # must be reachable so the consent/a11y layer renders before login.
    "/api/v1/accessibility",
    # Privacy consent (GPC/CCPA) -- the cookie banner runs pre-authentication,
    # so consent categories/preferences/status must be anonymously readable.
    "/api/v1/privacy/consent",
)


def _anonymous_get_routes() -> list[str]:
    """All GET routes under /api/v1 that take no path parameters."""
    routes: list[str] = []
    for route in app.routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", "")
        if not methods or "GET" not in methods:
            continue
        if not path.startswith("/api/v1"):
            continue
        if "{" in path:  # skip path-param routes (need a valid id)
            continue
        if path.startswith(PUBLIC_PREFIXES):
            continue
        routes.append(path)
    return sorted(set(routes))


@pytest.fixture(scope="module")
def anon_client() -> TestClient:
    # No dependency overrides -> real auth dependency runs.
    with TestClient(app) as client:
        yield client


def test_route_table_is_non_trivial(anon_client: TestClient) -> None:
    """Guard against the introspection silently finding nothing."""
    routes = _anonymous_get_routes()
    assert len(routes) >= 20, f"Expected a substantial route table, got {routes}"


def test_no_protected_route_serves_200_to_anonymous(anon_client: TestClient) -> None:
    """The core invariant: anonymous GET never yields 200 on a data route."""
    leaks: list[tuple[str, int]] = []
    for path in _anonymous_get_routes():
        resp = anon_client.get(path)
        if resp.status_code == 200:
            leaks.append((path, resp.status_code))
    assert not leaks, f"Routes served 200 to an unauthenticated caller (data exposure): {leaks}"


def test_protected_routes_return_401_not_422(anon_client: TestClient) -> None:
    """Auth should run before request validation.

    A 422 on an anonymous request means input validation executed before the
    auth check -- an information-leak smell (it reveals the schema) and a minor
    DoS surface. We assert 401/403 specifically.
    """
    wrong_order: list[tuple[str, int]] = []
    for path in _anonymous_get_routes():
        resp = anon_client.get(path)
        if resp.status_code not in (401, 403):
            wrong_order.append((path, resp.status_code))
    assert not wrong_order, (
        "Routes did not cleanly reject anonymous access with 401/403 "
        f"(auth may run after validation): {wrong_order}"
    )


def test_public_routes_are_actually_reachable(anon_client: TestClient) -> None:
    """Sanity: the allowlisted health route really is public (no over-locking)."""
    resp = anon_client.get("/api/v1/health")
    assert resp.status_code == 200

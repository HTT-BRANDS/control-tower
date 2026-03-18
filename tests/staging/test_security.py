"""Staging security tests — auth wall must hold for all protected endpoints.

If any of these endpoints return 200 without a token, something is very wrong.
All assertions expect exactly 401 (not 403, not 200, definitely not 500).
"""

import pytest
import requests


PROTECTED_GET_ENDPOINTS = [
    "/api/v1/costs/summary",
    "/api/v1/costs/anomalies",
    "/api/v1/compliance/summary",
    "/api/v1/identity/summary",
    "/api/v1/identity/privileged",
    "/api/v1/resources",
    "/api/v1/sync/status",
    "/api/v1/sync/history",
    "/api/v1/sync/metrics",
    "/api/v1/sync/alerts",
    "/api/v1/recommendations",
    "/api/v1/preflight/status",
    "/api/v1/riverside/summary",
    "/api/v1/riverside/mfa-status",
    "/api/v1/riverside/maturity-scores",
    "/api/v1/riverside/compliance",
    "/monitoring/performance",
    "/monitoring/cache",
]

PROTECTED_POST_ENDPOINTS = [
    "/api/v1/preflight/run",
    "/api/v1/sync/costs",
    "/api/v1/auth/logout",
]


class TestAuthWall:
    """Every protected endpoint must reject unauthenticated requests with 401."""

    @pytest.mark.parametrize("path", PROTECTED_GET_ENDPOINTS)
    def test_get_endpoint_requires_auth(
        self, client: requests.Session, staging_url: str, path: str
    ) -> None:
        """GET {path} without token must return 401."""
        resp = client.get(f"{staging_url}{path}", timeout=10)
        assert resp.status_code == 401, (
            f"GET {path} returned {resp.status_code} — expected 401. "
            "Auth wall may be broken."
        )

    @pytest.mark.parametrize("path", PROTECTED_POST_ENDPOINTS)
    def test_post_endpoint_requires_auth(
        self, client: requests.Session, staging_url: str, path: str
    ) -> None:
        """POST {path} without token must return 401."""
        resp = client.post(f"{staging_url}{path}", json={}, timeout=10)
        assert resp.status_code == 401, (
            f"POST {path} returned {resp.status_code} — expected 401."
        )

    def test_invalid_bearer_token_rejected(
        self, client: requests.Session, staging_url: str
    ) -> None:
        """A garbage Bearer token must return 401, not 500."""
        resp = client.get(
            f"{staging_url}/api/v1/costs/summary",
            headers={"Authorization": "Bearer this-is-not-a-real-jwt"},
            timeout=10,
        )
        assert resp.status_code == 401, (
            f"Invalid token returned {resp.status_code} — expected 401"
        )

    def test_401_includes_www_authenticate_header(
        self, client: requests.Session, staging_url: str
    ) -> None:
        """401 responses must include WWW-Authenticate per RFC 7235."""
        resp = client.get(f"{staging_url}/api/v1/riverside/summary", timeout=10)
        assert resp.status_code == 401
        assert "WWW-Authenticate" in resp.headers, (
            "401 response missing WWW-Authenticate header"
        )

    def test_no_protected_endpoint_returns_500(
        self, client: requests.Session, staging_url: str
    ) -> None:
        """Unauthenticated requests must not cause server errors.

        A 500 here means the app crashed before it even got to auth checking —
        that's worse than a 401.
        """
        errors = []
        for path in PROTECTED_GET_ENDPOINTS[:5]:  # sample first 5
            resp = client.get(f"{staging_url}{path}", timeout=10)
            if resp.status_code >= 500:
                errors.append(f"{path} → {resp.status_code}")
        assert not errors, f"Server errors on unauthenticated requests: {errors}"


class TestSecurityHeaders:
    """Basic security headers must be present."""

    def test_x_content_type_options_present(
        self, client: requests.Session, staging_url: str
    ) -> None:
        resp = client.get(f"{staging_url}/health", timeout=10)
        assert "X-Content-Type-Options" in resp.headers, (
            "Missing X-Content-Type-Options header"
        )

    def test_no_server_header_leaking_version(
        self, client: requests.Session, staging_url: str
    ) -> None:
        """Server header should not expose exact server version."""
        resp = client.get(f"{staging_url}/health", timeout=10)
        server = resp.headers.get("Server", "")
        # Acceptable: missing, or generic. Not acceptable: "uvicorn/0.x.x"
        assert "/" not in server or "nginx" in server.lower(), (
            f"Server header leaks version info: '{server}'"
        )

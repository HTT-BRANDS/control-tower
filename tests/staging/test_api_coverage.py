"""Staging API coverage tests.

Verifies that every major API surface is mounted and reachable.
Tests do NOT authenticate — they only confirm the route exists
(returns 401, not 404 or 500).

A 404 here means a router wasn't mounted.
A 500 here means startup or import failed for that module.
"""

import pytest
import requests

# All known API route prefixes grouped by feature area.
# Each entry is (path, allowed_unauthenticated_statuses).
# 401 = route exists, auth wall working
# 400 = route exists, missing required input (e.g. POST without body)
# 405 = route exists, wrong method — still confirms mount
API_ROUTES = [
    # ── Core ────────────────────────────────────────────────────────────────
    ("/health", [200]),
    ("/api/v1/auth/health", [200]),
    ("/openapi.json", [200]),
    ("/docs", [200]),
    # ── Costs ───────────────────────────────────────────────────────────────
    ("/api/v1/costs/summary", [401]),
    ("/api/v1/costs/anomalies", [401]),
    ("/api/v1/costs/trends", [401]),
    # ── Compliance ──────────────────────────────────────────────────────────
    ("/api/v1/compliance/summary", [401]),
    ("/api/v1/compliance/status", [401]),
    # ── Identity ────────────────────────────────────────────────────────────
    ("/api/v1/identity/summary", [401]),
    ("/api/v1/identity/privileged", [401]),
    ("/api/v1/identity/stale", [401]),
    # ── Resources ───────────────────────────────────────────────────────────
    ("/api/v1/resources", [401]),
    # ── Sync ────────────────────────────────────────────────────────────────
    ("/api/v1/sync/status", [401]),
    ("/api/v1/sync/history", [401]),
    ("/api/v1/sync/metrics", [401]),
    ("/api/v1/sync/alerts", [401]),
    # ── Preflight ───────────────────────────────────────────────────────────
    ("/api/v1/preflight/status", [401]),
    # ── Recommendations ─────────────────────────────────────────────────────
    ("/api/v1/recommendations", [401]),
    # ── Riverside ───────────────────────────────────────────────────────────
    ("/api/v1/riverside/summary", [401]),
    ("/api/v1/riverside/mfa-status", [401]),
    ("/api/v1/riverside/maturity-scores", [401]),
    # ── Monitoring (internal) ───────────────────────────────────────────────
    ("/monitoring/performance", [401]),
    ("/monitoring/cache", [401]),
]


class TestAPIRouteMounting:
    """Every route must be mounted — 404 means a router is missing."""

    @pytest.mark.parametrize("path,expected_statuses", API_ROUTES)
    def test_route_is_mounted(
        self,
        client: requests.Session,
        staging_url: str,
        path: str,
        expected_statuses: list[int],
    ) -> None:
        """GET {path} must return one of {expected_statuses}, never 404."""
        # openapi.json can be large; use 30s for schema endpoints
        # Swagger/OpenAPI endpoints are slow on cold start (schema generation)
        slow_paths = {"/openapi.json", "/docs", "/redoc"}
        timeout = 30 if path in slow_paths else 10
        resp = client.get(f"{staging_url}{path}", timeout=timeout)
        assert resp.status_code in expected_statuses, (
            f"GET {path} → {resp.status_code} "
            f"(expected one of {expected_statuses}). "
            "404 = router not mounted; 500 = startup crash for that module."
        )


class TestAPISchemaCompleteness:
    """OpenAPI schema must document all expected route groups."""

    @pytest.fixture(scope="class")
    def openapi_paths(self, client: requests.Session, staging_url: str) -> set[str]:
        resp = client.get(f"{staging_url}/openapi.json", timeout=30)
        return set(resp.json().get("paths", {}).keys())

    EXPECTED_PATH_PREFIXES = [
        "/api/v1/costs",
        "/api/v1/compliance",
        "/api/v1/identity",
        "/api/v1/resources",
        "/api/v1/sync",
        "/api/v1/preflight",
        "/api/v1/recommendations",
        "/api/v1/riverside",
        "/api/v1/auth",
    ]

    @pytest.mark.parametrize("prefix", EXPECTED_PATH_PREFIXES)
    def test_openapi_documents_prefix(self, openapi_paths: set[str], prefix: str) -> None:
        """At least one path starting with {prefix} must appear in openapi.json."""
        matching = [p for p in openapi_paths if p.startswith(prefix)]
        assert matching, (
            f"No paths with prefix '{prefix}' in OpenAPI schema. Router may not be mounted."
        )

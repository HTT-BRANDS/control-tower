"""Staging deployment validation tests.

Verifies that the deployed build is the right one — not stale,
not a placeholder, not a broken partial deploy.
"""

import re

import pytest
import requests


# Minimum acceptable version — increment this when we cut releases.
# Anything below this means staging hasn't been updated in a while.
MINIMUM_VERSION = (1, 4, 0)


class TestVersionFreshness:
    """The deployed version must meet the minimum bar."""

    def test_version_meets_minimum(self, health_data: dict) -> None:
        """Deployed version must be >= MINIMUM_VERSION."""
        version_str = health_data.get("version", "0.0.0")
        try:
            parts = tuple(int(x) for x in version_str.split(".")[:3])
        except ValueError:
            pytest.fail(f"Cannot parse version '{version_str}'")

        assert parts >= MINIMUM_VERSION, (
            f"Staging is running v{version_str} but minimum is "
            f"v{'.'.join(str(x) for x in MINIMUM_VERSION)}. "
            "Redeploy with current code."
        )

    def test_version_is_semver(self, health_data: dict) -> None:
        """Version string must follow semver (X.Y.Z) format."""
        version = health_data.get("version", "")
        assert re.match(r"^\d+\.\d+\.\d+$", version), (
            f"Version '{version}' is not valid semver (expected X.Y.Z)"
        )


class TestStartupHealth:
    """The app must have completed startup without errors."""

    def test_health_status_is_healthy(self, health_data: dict) -> None:
        """status field must be 'healthy', not 'degraded' or 'starting'."""
        status = health_data.get("status")
        assert status == "healthy", (
            f"App reports status='{status}' — may still be starting or degraded"
        )

    def test_repeated_health_checks_stable(
        self, client: requests.Session, staging_url: str
    ) -> None:
        """Five consecutive health checks must all return 200.

        A flapping health check indicates the app is crash-looping or
        the container is being repeatedly restarted.
        """
        failures = []
        for i in range(5):
            resp = client.get(f"{staging_url}/health", timeout=10)
            if resp.status_code != 200:
                failures.append(f"Check {i+1}: HTTP {resp.status_code}")
        assert not failures, (
            f"Health check unstable — {len(failures)}/5 checks failed: {failures}"
        )

    def test_api_v1_status_reachable(
        self, client: requests.Session, staging_url: str
    ) -> None:
        """GET /api/v1/status must exist (not 404).

        404 here means the API v1 prefix isn't mounted at all.
        """
        resp = client.get(f"{staging_url}/api/v1/status", timeout=10)
        # 401 = mounted + auth working, 200 = public status endpoint
        assert resp.status_code in (200, 401), (
            f"/api/v1/status returned {resp.status_code} — "
            "404 means the API router isn't mounted."
        )


class TestPerformanceBaseline:
    """Response times must be acceptable for a warmed-up staging app."""

    def test_health_responds_under_2_seconds(
        self, client: requests.Session, staging_url: str
    ) -> None:
        """Health endpoint must respond in < 2 seconds on a warm instance."""
        resp = client.get(f"{staging_url}/health", timeout=10)
        assert resp.elapsed.total_seconds() < 2.0, (
            f"Health check took {resp.elapsed.total_seconds():.2f}s — "
            "app may be overloaded or cold-starting"
        )

    def test_auth_health_responds_under_3_seconds(
        self, client: requests.Session, staging_url: str
    ) -> None:
        resp = client.get(f"{staging_url}/api/v1/auth/health", timeout=10)
        assert resp.elapsed.total_seconds() < 3.0, (
            f"Auth health took {resp.elapsed.total_seconds():.2f}s"
        )

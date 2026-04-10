"""Staging smoke tests — public endpoints, no authentication required.

These are the first tests that should pass after any deployment.
If any of these fail the deployment is broken.
"""

import requests


class TestPublicEndpoints:
    """Public endpoints must respond without authentication."""

    def test_health_returns_200(self, client: requests.Session, staging_url: str) -> None:
        """GET /health must return 200 with status=healthy."""
        resp = client.get(f"{staging_url}/health", timeout=10)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data.get("status") == "healthy", f"Expected status=healthy, got: {data}"

    def test_health_reports_version(self, health_data: dict) -> None:
        """Health response must include a non-empty version string."""
        version = health_data.get("version", "")
        assert version, "Health response missing 'version' field"
        # Sanity: looks like semver (at least major.minor)
        parts = version.split(".")
        assert len(parts) >= 2, f"Version '{version}' doesn't look like semver"

    def test_health_version_is_current(self, health_data: dict) -> None:
        """Staging must not be running prehistoric code.

        v0.x means the initial placeholder deploy is still live — someone
        forgot to redeploy. This test enforces a minimum version bar.
        """
        version = health_data.get("version", "0.0.0")
        major = int(version.split(".")[0])
        assert major >= 1, (
            f"Staging is running v{version} — looks like a stale placeholder deploy. "
            "Redeploy with current code."
        )

    def test_auth_health_endpoint_is_public(
        self, client: requests.Session, staging_url: str
    ) -> None:
        """GET /api/v1/auth/health must be accessible without credentials."""
        resp = client.get(f"{staging_url}/api/v1/auth/health", timeout=10)
        assert resp.status_code == 200, (
            f"/api/v1/auth/health returned {resp.status_code} — should be public"
        )
        data = resp.json()
        assert "jwt_configured" in data, f"Missing jwt_configured in: {data}"

    def test_openapi_schema_is_public(self, client: requests.Session, staging_url: str) -> None:
        """GET /openapi.json must be accessible (powers /docs)."""
        resp = client.get(f"{staging_url}/openapi.json", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert "paths" in data, "openapi.json missing 'paths'"
        assert "info" in data, "openapi.json missing 'info'"

    def test_docs_ui_responds_correctly(
        self, client: requests.Session, staging_url: str, is_production: bool
    ) -> None:
        """GET /docs — 200 in dev/staging, 401 in production (auth-gated)."""
        resp = client.get(f"{staging_url}/docs", timeout=10)
        if is_production:
            assert resp.status_code == 401, (
                f"/docs returned {resp.status_code} in production — expected 401"
            )
        else:
            assert resp.status_code == 200, f"/docs returned {resp.status_code} — expected 200"
            assert "text/html" in resp.headers.get("content-type", "")

    def test_app_not_returning_500(self, client: requests.Session, staging_url: str) -> None:
        """The app must not be in a crash loop — health must never return 5xx."""
        for _ in range(3):
            resp = client.get(f"{staging_url}/health", timeout=10)
            assert resp.status_code < 500, (
                f"App is returning {resp.status_code} — possible crash loop"
            )


class TestResponseShape:
    """Health response must have the right JSON shape."""

    def test_health_response_is_json(self, client: requests.Session, staging_url: str) -> None:
        resp = client.get(f"{staging_url}/health", timeout=10)
        assert resp.headers.get("content-type", "").startswith("application/json")

    def test_health_has_no_debug_info_leaked(self, health_data: dict) -> None:
        """Health endpoint must not leak stack traces or internal paths."""
        serialised = str(health_data).lower()
        for leak in ("traceback", "/home/", "secret", "password", "client_secret"):
            assert leak not in serialised, (
                f"Potential sensitive data '{leak}' found in health response"
            )

"""E2E tests for health, metrics, and status endpoints.

These tests run against a live FastAPI server (spun up via the ``base_url``
session fixture in conftest.py) and exercise the full HTTP stack including
middleware, serialisation, and Prometheus instrumentation.
"""

import httpx
import pytest

# ---------------------------------------------------------------------------
# Shared fixture – thin httpx client scoped to the module
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client(base_url: str) -> httpx.Client:
    """Yield an httpx Client pointed at the running test server."""
    with httpx.Client(base_url=base_url, timeout=10) as c:
        yield c


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """Basic health-check endpoint."""

    def test_returns_200(self, client: httpx.Client) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_body_contains_status_healthy(self, client: httpx.Client) -> None:
        data = client.get("/health").json()
        assert data["status"] == "healthy"

    def test_body_contains_version_string(self, client: httpx.Client) -> None:
        data = client.get("/health").json()
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0

    def test_content_type_is_json(self, client: httpx.Client) -> None:
        resp = client.get("/health")
        assert "application/json" in resp.headers.get("content-type", "")

    def test_not_rate_limited_on_burst(self, client: httpx.Client) -> None:
        """Health endpoint is explicitly excluded from rate-limiting middleware."""
        statuses = [client.get("/health").status_code for _ in range(20)]
        assert all(s == 200 for s in statuses)


# ---------------------------------------------------------------------------
# GET /health/detailed
# ---------------------------------------------------------------------------


class TestHealthDetailedEndpoint:
    """Detailed health-check with per-component status."""

    def test_returns_200(self, client: httpx.Client) -> None:
        resp = client.get("/health/detailed")
        assert resp.status_code == 200

    def test_body_contains_status(self, client: httpx.Client) -> None:
        data = client.get("/health/detailed").json()
        assert data["status"] in {"healthy", "degraded"}

    def test_body_contains_version(self, client: httpx.Client) -> None:
        data = client.get("/health/detailed").json()
        assert "version" in data
        assert isinstance(data["version"], str)

    def test_components_is_dict(self, client: httpx.Client) -> None:
        data = client.get("/health/detailed").json()
        assert isinstance(data["components"], dict)

    def test_components_include_database(self, client: httpx.Client) -> None:
        components = client.get("/health/detailed").json()["components"]
        assert "database" in components

    def test_components_include_scheduler(self, client: httpx.Client) -> None:
        components = client.get("/health/detailed").json()["components"]
        assert "scheduler" in components

    def test_components_include_cache(self, client: httpx.Client) -> None:
        components = client.get("/health/detailed").json()["components"]
        assert "cache" in components

    def test_components_include_azure_configured(self, client: httpx.Client) -> None:
        components = client.get("/health/detailed").json()["components"]
        assert "azure_configured" in components

    def test_cache_metrics_present(self, client: httpx.Client) -> None:
        data = client.get("/health/detailed").json()
        assert "cache_metrics" in data
        assert isinstance(data["cache_metrics"], dict)

    def test_not_rate_limited_on_burst(self, client: httpx.Client) -> None:
        """Detailed health endpoint is also excluded from rate-limiting."""
        statuses = [client.get("/health/detailed").status_code for _ in range(20)]
        assert all(s == 200 for s in statuses)


# ---------------------------------------------------------------------------
# GET /metrics  (Prometheus)
# ---------------------------------------------------------------------------


class TestMetricsEndpoint:
    """Prometheus metrics exposition."""

    def test_returns_200(self, client: httpx.Client) -> None:
        resp = client.get("/metrics")
        assert resp.status_code == 200

    def test_content_type_is_text_plain(self, client: httpx.Client) -> None:
        resp = client.get("/metrics")
        ct = resp.headers.get("content-type", "")
        # Prometheus client may use text/plain or the OpenMetrics type
        assert "text/plain" in ct or "openmetrics" in ct

    def test_body_contains_help_or_type_comments(self, client: httpx.Client) -> None:
        body = client.get("/metrics").text
        assert "# HELP" in body or "# TYPE" in body

    def test_body_contains_http_request_metrics(self, client: httpx.Client) -> None:
        """The Prometheus instrumentator should emit http_request_* metrics."""
        body = client.get("/metrics").text
        assert "http_request" in body

    def test_body_is_non_empty(self, client: httpx.Client) -> None:
        body = client.get("/metrics").text
        assert len(body.strip()) > 0


# ---------------------------------------------------------------------------
# GET /api/v1/status
# ---------------------------------------------------------------------------


class TestApiV1StatusEndpoint:
    """System-wide status endpoint with rich telemetry."""

    def test_returns_200(self, client: httpx.Client) -> None:
        resp = client.get("/api/v1/status")
        assert resp.status_code == 200

    def test_body_contains_status(self, client: httpx.Client) -> None:
        data = client.get("/api/v1/status").json()
        assert data["status"] in {"healthy", "degraded"}

    def test_body_contains_version(self, client: httpx.Client) -> None:
        data = client.get("/api/v1/status").json()
        assert "version" in data
        assert isinstance(data["version"], str)

    def test_body_contains_iso_timestamp(self, client: httpx.Client) -> None:
        data = client.get("/api/v1/status").json()
        ts = data["timestamp"]
        assert isinstance(ts, str)
        # ISO-8601 timestamps contain 'T' and end with timezone info
        assert "T" in ts

    def test_components_dict_present(self, client: httpx.Client) -> None:
        data = client.get("/api/v1/status").json()
        assert isinstance(data["components"], dict)

    def test_components_include_database(self, client: httpx.Client) -> None:
        components = client.get("/api/v1/status").json()["components"]
        assert "database" in components

    def test_components_include_scheduler(self, client: httpx.Client) -> None:
        components = client.get("/api/v1/status").json()["components"]
        assert "scheduler" in components

    def test_components_include_cache(self, client: httpx.Client) -> None:
        components = client.get("/api/v1/status").json()["components"]
        assert "cache" in components

    def test_sync_jobs_section_present(self, client: httpx.Client) -> None:
        data = client.get("/api/v1/status").json()
        assert "sync_jobs" in data
        assert isinstance(data["sync_jobs"], dict)

    def test_alerts_section_present(self, client: httpx.Client) -> None:
        data = client.get("/api/v1/status").json()
        assert "alerts" in data
        assert isinstance(data["alerts"], dict)

    def test_performance_section_present(self, client: httpx.Client) -> None:
        data = client.get("/api/v1/status").json()
        assert "performance" in data
        assert isinstance(data["performance"], dict)

    def test_cache_section_present(self, client: httpx.Client) -> None:
        data = client.get("/api/v1/status").json()
        assert "cache" in data
        assert isinstance(data["cache"], dict)

    def test_content_type_is_json(self, client: httpx.Client) -> None:
        resp = client.get("/api/v1/status")
        assert "application/json" in resp.headers.get("content-type", "")

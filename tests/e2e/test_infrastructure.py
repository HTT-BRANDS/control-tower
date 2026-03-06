"""E2E tests for health, metrics, and status endpoints."""

from playwright.sync_api import APIRequestContext


class TestHealthEndpoint:
    """GET /health — basic health check."""

    def test_returns_200(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/health")
        assert resp.status == 200

    def test_status_is_healthy(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/health")
        data = resp.json()
        assert data["status"] == "healthy"

    def test_version_present(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/health")
        data = resp.json()
        assert "version" in data
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0

    def test_content_type_json(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/health")
        assert "application/json" in resp.headers.get("content-type", "")

    def test_not_rate_limited_on_burst(self, unauth_api_context: APIRequestContext):
        """Health is excluded from rate limiting."""
        statuses = [unauth_api_context.get("/health").status for _ in range(20)]
        assert all(s == 200 for s in statuses)


class TestHealthDetailed:
    """GET /health/detailed — component-level health."""

    def test_returns_200(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/health/detailed")
        assert resp.status == 200

    def test_has_components(self, unauth_api_context: APIRequestContext):
        data = unauth_api_context.get("/health/detailed").json()
        assert isinstance(data["components"], dict)
        assert "database" in data["components"]
        assert "scheduler" in data["components"]
        assert "cache" in data["components"]

    def test_has_cache_metrics(self, unauth_api_context: APIRequestContext):
        data = unauth_api_context.get("/health/detailed").json()
        assert "cache_metrics" in data
        assert isinstance(data["cache_metrics"], dict)


class TestMetrics:
    """GET /metrics — Prometheus exposition."""

    def test_returns_200(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/metrics")
        assert resp.status == 200

    def test_prometheus_format(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/metrics")
        ct = resp.headers.get("content-type", "")
        assert "text/plain" in ct or "openmetrics" in ct

    def test_contains_http_metrics(self, unauth_api_context: APIRequestContext):
        body = unauth_api_context.get("/metrics").text()
        assert "http_request" in body

    def test_contains_help_comments(self, unauth_api_context: APIRequestContext):
        body = unauth_api_context.get("/metrics").text()
        assert "# HELP" in body or "# TYPE" in body


class TestSystemStatus:
    """GET /api/v1/status — system-wide telemetry."""

    def test_returns_200(self, unauth_api_context: APIRequestContext):
        resp = unauth_api_context.get("/api/v1/status")
        assert resp.status == 200

    def test_has_all_sections(self, unauth_api_context: APIRequestContext):
        data = unauth_api_context.get("/api/v1/status").json()
        for key in (
            "status",
            "version",
            "timestamp",
            "components",
            "sync_jobs",
            "alerts",
            "performance",
            "cache",
        ):
            assert key in data, f"Missing section: {key}"

    def test_timestamp_is_iso(self, unauth_api_context: APIRequestContext):
        data = unauth_api_context.get("/api/v1/status").json()
        assert "T" in data["timestamp"]

    def test_components_include_database(self, unauth_api_context: APIRequestContext):
        data = unauth_api_context.get("/api/v1/status").json()
        assert "database" in data["components"]

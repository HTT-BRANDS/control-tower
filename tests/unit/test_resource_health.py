"""Unit tests for monitoring health endpoint aggregation."""


class TestMonitoringHealthEndpoint:
    """Tests for the monitoring /health endpoint — performance health aggregation."""

    def test_monitoring_health_route_registered(self, client):
        """GET /monitoring/health must be registered (not 404) even when auth fails."""
        response = client.get("/monitoring/health")
        assert response.status_code != 404, "/monitoring/health route not mounted"

    def test_monitoring_performance_route_registered(self, client):
        """GET /monitoring/performance must be registered (not 404) when auth fails."""
        response = client.get("/monitoring/performance")
        assert response.status_code != 404

    def test_monitoring_cache_route_registered(self, client):
        """GET /monitoring/cache must be registered (not 404) when auth fails."""
        response = client.get("/monitoring/cache")
        assert response.status_code != 404

    def test_monitoring_health_authenticated(self, authed_client):
        """Authenticated GET /monitoring/health returns valid health payload."""
        response = authed_client.get("/monitoring/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"
        assert "cache_health" in data
        assert "cache_hit_rate" in data
        assert "total_sync_jobs" in data

    def test_monitoring_performance_authenticated(self, authed_client):
        """Authenticated GET /monitoring/performance returns metrics dict."""
        response = authed_client.get("/monitoring/performance")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_monitoring_cache_authenticated(self, authed_client):
        """Authenticated GET /monitoring/cache returns cache statistics."""
        response = authed_client.get("/monitoring/cache")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

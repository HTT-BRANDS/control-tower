"""Tests for RM-006: Resource health aggregation.

Covers the get_health_status() path in LighthouseAzureClient, which was
flagged as having ZERO test coverage in the traceability matrix.
"""
from unittest.mock import MagicMock


class TestLighthouseHealthStatus:
    """Unit tests for LighthouseAzureClient.get_health_status() — RM-006."""

    def _make_client(self):
        """Build a LighthouseAzureClient with all Azure calls mocked out.

        Uses __new__ to bypass __init__ entirely — no Azure SDK calls made.
        """
        from app.services.lighthouse_client import LighthouseAzureClient
        client = LighthouseAzureClient.__new__(LighthouseAzureClient)
        # Inject mock resilience objects directly
        client._arm_resilience = MagicMock()
        client._arm_resilience.get_state.return_value = {"status": "closed", "failure_count": 0}
        client._cost_resilience = MagicMock()
        client._cost_resilience.get_state.return_value = {"status": "closed", "failure_count": 0}
        client._security_resilience = MagicMock()
        client._security_resilience.get_state.return_value = {"status": "closed", "failure_count": 0}
        client.credential = MagicMock()
        return client

    def test_get_health_status_returns_healthy(self):
        """get_health_status() should return status=healthy under normal conditions."""
        client = self._make_client()
        result = client.get_health_status()
        assert result["status"] == "healthy"

    def test_get_health_status_includes_resilience_state(self):
        """get_health_status() should report state for all three circuit breakers."""
        client = self._make_client()
        result = client.get_health_status()
        assert "resilience_state" in result
        assert "arm" in result["resilience_state"]
        assert "cost" in result["resilience_state"]
        assert "security" in result["resilience_state"]

    def test_get_health_status_arm_state_structure(self):
        """ARM resilience state should expose circuit breaker details."""
        client = self._make_client()
        result = client.get_health_status()
        arm_state = result["resilience_state"]["arm"]
        assert isinstance(arm_state, dict)
        assert "status" in arm_state

    def test_get_health_status_includes_credential_type(self):
        """get_health_status() should report the credential type in use."""
        client = self._make_client()
        result = client.get_health_status()
        assert "credential_type" in result
        assert isinstance(result["credential_type"], str)

    def test_get_health_status_open_circuit_breaker(self):
        """get_health_status() should reflect open circuit breaker state."""
        client = self._make_client()
        client._arm_resilience.get_state.return_value = {
            "status": "open",
            "failure_count": 5,
        }
        result = client.get_health_status()
        assert result["resilience_state"]["arm"]["status"] == "open"

    def test_get_health_status_all_circuit_breakers_open(self):
        """get_health_status() is callable even when all circuit breakers are open."""
        client = self._make_client()
        for resilience in (
            client._arm_resilience,
            client._cost_resilience,
            client._security_resilience,
        ):
            resilience.get_state.return_value = {"status": "open", "failure_count": 5}
        result = client.get_health_status()
        # Still returns a valid dict — caller decides how to interpret state
        assert result["status"] == "healthy"
        assert result["resilience_state"]["arm"]["status"] == "open"
        assert result["resilience_state"]["cost"]["status"] == "open"
        assert result["resilience_state"]["security"]["status"] == "open"

    def test_reset_lighthouse_client(self):
        """reset_lighthouse_client() should clear the singleton."""
        from app.services.lighthouse_client import reset_lighthouse_client
        # Should not raise
        reset_lighthouse_client()
        from app.services.lighthouse_client import _lighthouse_client
        assert _lighthouse_client is None


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

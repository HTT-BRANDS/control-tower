"""Comprehensive tests for app/api/routes/health.py.

Covers:
- GET /api/v1/health — basic health check
- GET /api/v1/health/detailed — detailed health check with component metrics
- Database, cache, scheduler, and Azure config checks
- Healthy, degraded, and error states
- Authenticated vs unauthenticated response differences

Phase 2.2 of the test coverage sprint.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

HEALTH_URL = "/api/v1/health"
DETAILED_URL = "/api/v1/health/detailed"


def _mock_cache_healthy():
    """Return patchers for a healthy cache_manager."""
    mock = MagicMock()
    mock.set = AsyncMock()
    mock.get = AsyncMock(return_value="ok")
    mock.get_metrics = MagicMock(
        return_value={
            "backend": "memory",
            "hit_rate_percent": 85.0,
            "hits": 100,
            "misses": 18,
            "sets": 50,
            "deletes": 5,
            "avg_get_time_ms": 0.12,
        }
    )
    return mock


def _mock_scheduler_running(num_jobs: int = 3):
    """Return a mock scheduler that reports as running with N jobs."""
    scheduler = MagicMock()
    scheduler.running = True
    jobs = []
    for i in range(num_jobs):
        job = MagicMock()
        job.id = f"job_{i}"
        job.name = f"Job {i}"
        job.next_run_time = datetime(2025, 1, 1, tzinfo=UTC)
        jobs.append(job)
    scheduler.get_jobs.return_value = jobs
    return scheduler


def _mock_scheduler_stopped():
    """Return a mock scheduler that is NOT running."""
    scheduler = MagicMock()
    scheduler.running = False
    return scheduler


# ===========================================================================
# GET /api/v1/health — Basic Health Check
# ===========================================================================


class TestHealthEndpoint:
    """Tests for the basic /api/v1/health endpoint."""

    @patch("app.api.routes.health.cache_manager")
    @patch("app.api.routes.health.get_scheduler")
    def test_health_returns_required_fields(
        self,
        mock_get_sched,
        mock_cache,
        client,
    ):
        """Response must include status, version, and checks."""
        mock_cache.set = AsyncMock()
        mock_cache.get = AsyncMock(return_value="ok")
        mock_cache.get_metrics = MagicMock(
            return_value={"backend": "memory", "hit_rate_percent": 0}
        )
        mock_get_sched.return_value = _mock_scheduler_running()

        resp = client.get(HEALTH_URL)
        assert resp.status_code == 200
        data = resp.json()

        assert "status" in data
        assert "version" in data
        assert "checks" in data
        assert "timestamp" in data
        assert "environment" in data

    @patch("app.api.routes.health.cache_manager")
    @patch("app.api.routes.health.get_scheduler")
    def test_health_all_healthy(self, mock_get_sched, mock_cache, client):
        """When all components are healthy, overall status is 'healthy'."""
        mock_cache.set = AsyncMock()
        mock_cache.get = AsyncMock(return_value="ok")
        mock_cache.get_metrics = MagicMock(
            return_value={"backend": "memory", "hit_rate_percent": 90}
        )
        mock_get_sched.return_value = _mock_scheduler_running()
        client.app.state.scheduler_status = None

        resp = client.get(HEALTH_URL)
        data = resp.json()

        assert data["status"] == "healthy"
        assert data["checks"]["database"]["status"] == "healthy"
        assert data["checks"]["cache"]["status"] == "healthy"
        assert data["checks"]["scheduler"]["status"] == "healthy"

    @patch("app.api.routes.health.cache_manager")
    @patch("app.api.routes.health.get_scheduler")
    def test_health_database_check_includes_response_time(
        self,
        mock_get_sched,
        mock_cache,
        client,
    ):
        """Database check must report response_time_ms."""
        mock_cache.set = AsyncMock()
        mock_cache.get = AsyncMock(return_value="ok")
        mock_cache.get_metrics = MagicMock(
            return_value={"backend": "memory", "hit_rate_percent": 0}
        )
        mock_get_sched.return_value = _mock_scheduler_running()

        resp = client.get(HEALTH_URL)
        db_check = resp.json()["checks"]["database"]

        assert db_check["status"] == "healthy"
        assert "response_time_ms" in db_check
        assert isinstance(db_check["response_time_ms"], int | float)

    @patch("app.api.routes.health.cache_manager")
    @patch("app.api.routes.health.get_scheduler")
    def test_health_degraded_when_db_fails(
        self,
        mock_get_sched,
        mock_cache,
        client,
        db_session,
    ):
        """Overall status degrades when the database check throws."""
        mock_cache.set = AsyncMock()
        mock_cache.get = AsyncMock(return_value="ok")
        mock_cache.get_metrics = MagicMock(
            return_value={"backend": "memory", "hit_rate_percent": 0}
        )
        mock_get_sched.return_value = _mock_scheduler_running()

        # Make the db.execute raise to simulate DB failure
        with patch.object(db_session, "execute", side_effect=Exception("connection lost")):
            resp = client.get(HEALTH_URL)

        data = resp.json()
        assert data["status"] == "degraded"
        assert data["checks"]["database"]["status"] == "unhealthy"
        assert "connection lost" in data["checks"]["database"]["error"]

    @patch("app.api.routes.health.cache_manager")
    @patch("app.api.routes.health.get_scheduler")
    def test_health_cache_mismatch_causes_degraded(
        self,
        mock_get_sched,
        mock_cache,
        client,
    ):
        """If cache read-back doesn't match, status should be degraded."""
        mock_cache.set = AsyncMock()
        mock_cache.get = AsyncMock(return_value="NOT_OK")  # mismatch
        mock_cache.get_metrics = MagicMock(
            return_value={"backend": "memory", "hit_rate_percent": 0}
        )
        mock_get_sched.return_value = _mock_scheduler_running()

        resp = client.get(HEALTH_URL)
        data = resp.json()

        assert data["checks"]["cache"]["status"] == "degraded"
        assert "mismatch" in data["checks"]["cache"]["error"].lower()

    @patch("app.api.routes.health.cache_manager")
    @patch("app.api.routes.health.get_scheduler")
    def test_health_cache_exception_causes_degraded(
        self,
        mock_get_sched,
        mock_cache,
        client,
    ):
        """If cache throws, status should degrade gracefully."""
        mock_cache.set = AsyncMock(side_effect=Exception("Redis down"))
        mock_get_sched.return_value = _mock_scheduler_running()

        resp = client.get(HEALTH_URL)
        data = resp.json()

        assert data["status"] == "degraded"
        assert data["checks"]["cache"]["status"] == "unhealthy"
        assert "Redis down" in data["checks"]["cache"]["error"]

    @patch("app.api.routes.health.cache_manager")
    @patch("app.api.routes.health.get_scheduler")
    def test_health_scheduler_not_running(
        self,
        mock_get_sched,
        mock_cache,
        client,
    ):
        """Scheduler not running should report degraded."""
        mock_cache.set = AsyncMock()
        mock_cache.get = AsyncMock(return_value="ok")
        mock_cache.get_metrics = MagicMock(
            return_value={"backend": "memory", "hit_rate_percent": 0}
        )
        mock_get_sched.return_value = _mock_scheduler_stopped()
        client.app.state.scheduler_status = None

        resp = client.get(HEALTH_URL)
        data = resp.json()

        assert data["checks"]["scheduler"]["status"] == "degraded"
        assert "not running" in data["checks"]["scheduler"]["error"].lower()

    @patch("app.api.routes.health.cache_manager")
    @patch("app.api.routes.health.get_scheduler")
    def test_health_scheduler_none(
        self,
        mock_get_sched,
        mock_cache,
        client,
    ):
        """When get_scheduler() returns None, should be degraded."""
        mock_cache.set = AsyncMock()
        mock_cache.get = AsyncMock(return_value="ok")
        mock_cache.get_metrics = MagicMock(
            return_value={"backend": "memory", "hit_rate_percent": 0}
        )
        mock_get_sched.return_value = None
        client.app.state.scheduler_status = None

        resp = client.get(HEALTH_URL)
        data = resp.json()

        assert data["checks"]["scheduler"]["status"] == "degraded"

    @patch("app.api.routes.health.cache_manager")
    @patch("app.api.routes.health.get_scheduler")
    def test_health_scheduler_exception(
        self,
        mock_get_sched,
        mock_cache,
        client,
    ):
        """If get_scheduler raises, scheduler check degrades gracefully."""
        mock_cache.set = AsyncMock()
        mock_cache.get = AsyncMock(return_value="ok")
        mock_cache.get_metrics = MagicMock(
            return_value={"backend": "memory", "hit_rate_percent": 0}
        )
        mock_get_sched.side_effect = RuntimeError("scheduler init failed")
        client.app.state.scheduler_status = None

        resp = client.get(HEALTH_URL)
        data = resp.json()

        assert data["checks"]["scheduler"]["status"] == "degraded"
        assert "scheduler init failed" in data["checks"]["scheduler"]["error"]

    @patch("app.api.routes.health.cache_manager")
    @patch("app.api.routes.health.get_scheduler")
    def test_health_scheduler_disabled_for_test_is_distinct_from_degraded(
        self,
        mock_get_sched,
        mock_cache,
        client,
    ):
        """Browser-test disabled scheduler state should not be reported as degraded."""
        mock_cache.set = AsyncMock()
        mock_cache.get = AsyncMock(return_value="ok")
        mock_cache.get_metrics = MagicMock(
            return_value={"backend": "memory", "hit_rate_percent": 0}
        )
        mock_get_sched.return_value = None
        client.app.state.scheduler_status = "disabled_for_test"

        try:
            resp = client.get(HEALTH_URL)
        finally:
            client.app.state.scheduler_status = None

        data = resp.json()
        assert data["status"] == "healthy"
        assert data["checks"]["scheduler"]["status"] == "disabled_for_test"
        assert data["checks"]["scheduler"]["active_jobs"] == 0

    @patch("app.api.routes.health.get_settings")
    @patch("app.api.routes.health.cache_manager")
    @patch("app.api.routes.health.get_scheduler")
    def test_health_azure_configured_true(
        self,
        mock_get_sched,
        mock_cache,
        mock_settings,
        client,
    ):
        """Azure config check should be True when all 3 values set."""
        settings = MagicMock()
        settings.azure_ad_tenant_id = "tenant-id"
        settings.azure_ad_client_id = "client-id"
        settings.azure_ad_client_secret = "secret"  # pragma: allowlist secret
        settings.app_version = "1.0.0"
        settings.environment = "development"
        mock_settings.return_value = settings

        mock_cache.set = AsyncMock()
        mock_cache.get = AsyncMock(return_value="ok")
        mock_cache.get_metrics = MagicMock(
            return_value={"backend": "memory", "hit_rate_percent": 0}
        )
        mock_get_sched.return_value = _mock_scheduler_running()

        resp = client.get(HEALTH_URL)
        assert resp.json()["checks"]["azure_configured"] is True

    @patch("app.api.routes.health.get_settings")
    @patch("app.api.routes.health.cache_manager")
    @patch("app.api.routes.health.get_scheduler")
    def test_health_azure_configured_false(
        self,
        mock_get_sched,
        mock_cache,
        mock_settings,
        client,
    ):
        """Azure config check should be False when a value is missing."""
        settings = MagicMock()
        settings.azure_ad_tenant_id = "tenant-id"
        settings.azure_ad_client_id = None  # missing!
        settings.azure_ad_client_secret = "secret"  # pragma: allowlist secret
        settings.app_version = "1.0.0"
        settings.environment = "development"
        mock_settings.return_value = settings

        mock_cache.set = AsyncMock()
        mock_cache.get = AsyncMock(return_value="ok")
        mock_cache.get_metrics = MagicMock(
            return_value={"backend": "memory", "hit_rate_percent": 0}
        )
        mock_get_sched.return_value = _mock_scheduler_running()

        resp = client.get(HEALTH_URL)
        assert resp.json()["checks"]["azure_configured"] is False

    @patch("app.api.routes.health.cache_manager")
    @patch("app.api.routes.health.get_scheduler")
    def test_health_unauthenticated_no_authenticated_field(
        self,
        mock_get_sched,
        mock_cache,
        client,
    ):
        """Unauthenticated requests should NOT get 'authenticated' key."""
        mock_cache.set = AsyncMock()
        mock_cache.get = AsyncMock(return_value="ok")
        mock_cache.get_metrics = MagicMock(
            return_value={"backend": "memory", "hit_rate_percent": 0}
        )
        mock_get_sched.return_value = _mock_scheduler_running()

        resp = client.get(HEALTH_URL)
        assert "authenticated" not in resp.json()

    @patch("app.api.routes.health.cache_manager")
    @patch("app.api.routes.health.get_scheduler")
    def test_health_authenticated_includes_field(
        self,
        mock_get_sched,
        mock_cache,
        client,
    ):
        """Authenticated requests (Bearer token) should get 'authenticated': True."""
        mock_cache.set = AsyncMock()
        mock_cache.get = AsyncMock(return_value="ok")
        mock_cache.get_metrics = MagicMock(
            return_value={"backend": "memory", "hit_rate_percent": 0}
        )
        mock_get_sched.return_value = _mock_scheduler_running()

        resp = client.get(HEALTH_URL, headers={"Authorization": "Bearer fake-token"})
        data = resp.json()
        assert data.get("authenticated") is True


# ===========================================================================
# GET /api/v1/health/detailed — Detailed Health Check
# ===========================================================================


class TestHealthDetailedEndpoint:
    """Tests for the /api/v1/health/detailed endpoint."""

    @patch("app.core.database.get_db_stats", return_value={"tenants_count": 5})
    @patch("app.api.routes.health.cache_manager")
    @patch("app.api.routes.health.get_scheduler")
    def test_detailed_returns_all_checks(
        self,
        mock_get_sched,
        mock_cache,
        mock_db_stats,
        client,
    ):
        """Detailed endpoint must include all check categories."""
        mock_cache.set = AsyncMock()
        mock_cache.get = AsyncMock(return_value="ok")
        mock_cache.get_metrics = MagicMock(
            return_value={
                "backend": "memory",
                "hit_rate_percent": 80,
                "hits": 50,
                "misses": 10,
                "sets": 30,
                "deletes": 2,
                "avg_get_time_ms": 0.1,
            }
        )
        mock_get_sched.return_value = _mock_scheduler_running()

        resp = client.get(DETAILED_URL)
        assert resp.status_code == 200
        data = resp.json()
        checks = data["checks"]

        assert "database" in checks
        assert "cache" in checks
        assert "scheduler" in checks
        assert "azure_configured" in checks
        assert "jwt_configured" in checks

    @patch("app.core.database.get_db_stats", return_value={"tenants_count": 2})
    @patch("app.api.routes.health.cache_manager")
    @patch("app.api.routes.health.get_scheduler")
    def test_detailed_cache_includes_extended_metrics(
        self,
        mock_get_sched,
        mock_cache,
        mock_db_stats,
        client,
    ):
        """Detailed cache check should include hits, misses, sets, deletes."""
        mock_cache.set = AsyncMock()
        mock_cache.get = AsyncMock(return_value="ok")
        mock_cache.get_metrics = MagicMock(
            return_value={
                "backend": "redis",
                "hit_rate_percent": 92.5,
                "hits": 200,
                "misses": 17,
                "sets": 100,
                "deletes": 8,
                "avg_get_time_ms": 0.45,
            }
        )
        mock_get_sched.return_value = _mock_scheduler_running()

        resp = client.get(DETAILED_URL)
        cache_check = resp.json()["checks"]["cache"]

        assert cache_check["status"] == "healthy"
        assert cache_check["backend"] == "redis"
        assert cache_check["hits"] == 200
        assert cache_check["misses"] == 17
        assert cache_check["sets"] == 100
        assert cache_check["deletes"] == 8
        assert cache_check["avg_get_time_ms"] == 0.45

    @patch("app.core.database.get_db_stats", return_value={"tenants_count": 1})
    @patch("app.api.routes.health.cache_manager")
    @patch("app.api.routes.health.get_scheduler")
    def test_detailed_unauthed_redacts_db_stats(
        self,
        mock_get_sched,
        mock_cache,
        mock_db_stats,
        client,
    ):
        """Without auth, db stats should be redacted."""
        mock_cache.set = AsyncMock()
        mock_cache.get = AsyncMock(return_value="ok")
        mock_cache.get_metrics = MagicMock(
            return_value={
                "backend": "memory",
                "hit_rate_percent": 0,
                "hits": 0,
                "misses": 0,
                "sets": 0,
                "deletes": 0,
                "avg_get_time_ms": 0,
            }
        )
        mock_get_sched.return_value = _mock_scheduler_running()

        resp = client.get(DETAILED_URL)  # no Authorization header
        db_check = resp.json()["checks"]["database"]

        assert db_check["stats"] == "redacted (auth required)"

    @patch("app.core.database.get_db_stats", return_value={"tenants_count": 3})
    @patch("app.api.routes.health.cache_manager")
    @patch("app.api.routes.health.get_scheduler")
    def test_detailed_authed_shows_db_stats(
        self,
        mock_get_sched,
        mock_cache,
        mock_db_stats,
        client,
    ):
        """With Bearer auth, db stats should be visible."""
        mock_cache.set = AsyncMock()
        mock_cache.get = AsyncMock(return_value="ok")
        mock_cache.get_metrics = MagicMock(
            return_value={
                "backend": "memory",
                "hit_rate_percent": 0,
                "hits": 0,
                "misses": 0,
                "sets": 0,
                "deletes": 0,
                "avg_get_time_ms": 0,
            }
        )
        mock_get_sched.return_value = _mock_scheduler_running()

        resp = client.get(DETAILED_URL, headers={"Authorization": "Bearer tok123"})
        db_check = resp.json()["checks"]["database"]

        assert db_check["stats"] == {"tenants_count": 3}

    @patch("app.core.database.get_db_stats", return_value={})
    @patch("app.api.routes.health.cache_manager")
    @patch("app.api.routes.health.get_scheduler")
    def test_detailed_authed_shows_scheduler_jobs(
        self,
        mock_get_sched,
        mock_cache,
        mock_db_stats,
        client,
    ):
        """Authed request should see scheduler job details."""
        mock_cache.set = AsyncMock()
        mock_cache.get = AsyncMock(return_value="ok")
        mock_cache.get_metrics = MagicMock(
            return_value={
                "backend": "memory",
                "hit_rate_percent": 0,
                "hits": 0,
                "misses": 0,
                "sets": 0,
                "deletes": 0,
                "avg_get_time_ms": 0,
            }
        )
        mock_get_sched.return_value = _mock_scheduler_running(num_jobs=2)
        client.app.state.scheduler_status = None

        resp = client.get(DETAILED_URL, headers={"Authorization": "Bearer tok123"})
        sched_check = resp.json()["checks"]["scheduler"]

        assert sched_check["status"] == "healthy"
        assert sched_check["active_jobs"] == 2
        # Authed: jobs should be a list with job details
        assert isinstance(sched_check["jobs"], list)
        assert len(sched_check["jobs"]) == 2
        assert sched_check["jobs"][0]["id"] == "job_0"

    @patch("app.core.database.get_db_stats", return_value={})
    @patch("app.api.routes.health.cache_manager")
    @patch("app.api.routes.health.get_scheduler")
    def test_detailed_unauthed_redacts_scheduler_jobs(
        self,
        mock_get_sched,
        mock_cache,
        mock_db_stats,
        client,
    ):
        """Unauthed request should see scheduler jobs redacted."""
        mock_cache.set = AsyncMock()
        mock_cache.get = AsyncMock(return_value="ok")
        mock_cache.get_metrics = MagicMock(
            return_value={
                "backend": "memory",
                "hit_rate_percent": 0,
                "hits": 0,
                "misses": 0,
                "sets": 0,
                "deletes": 0,
                "avg_get_time_ms": 0,
            }
        )
        mock_get_sched.return_value = _mock_scheduler_running(num_jobs=2)
        client.app.state.scheduler_status = None

        resp = client.get(DETAILED_URL)  # no auth
        sched_check = resp.json()["checks"]["scheduler"]

        assert sched_check["status"] == "healthy"
        assert sched_check["active_jobs"] == 2
        assert sched_check["jobs"] == "redacted (auth required)"

    @patch("app.core.database.get_db_stats", return_value={})
    @patch("app.api.routes.health.cache_manager")
    @patch("app.api.routes.health.get_scheduler")
    def test_detailed_degraded_when_db_fails(
        self,
        mock_get_sched,
        mock_cache,
        mock_db_stats,
        client,
        db_session,
    ):
        """Detailed endpoint should degrade when DB check fails."""
        mock_cache.set = AsyncMock()
        mock_cache.get = AsyncMock(return_value="ok")
        mock_cache.get_metrics = MagicMock(
            return_value={
                "backend": "memory",
                "hit_rate_percent": 0,
                "hits": 0,
                "misses": 0,
                "sets": 0,
                "deletes": 0,
                "avg_get_time_ms": 0,
            }
        )
        mock_get_sched.return_value = _mock_scheduler_running()

        with patch.object(db_session, "execute", side_effect=Exception("db timeout")):
            resp = client.get(DETAILED_URL)

        data = resp.json()
        assert data["status"] == "degraded"
        assert data["checks"]["database"]["status"] == "unhealthy"

    @patch("app.core.database.get_db_stats", return_value={})
    @patch("app.api.routes.health.cache_manager")
    @patch("app.api.routes.health.get_scheduler")
    def test_detailed_scheduler_disabled_for_test_reports_distinct_status(
        self,
        mock_get_sched,
        mock_cache,
        mock_db_stats,
        client,
    ):
        """Detailed endpoint should surface disabled_for_test instead of degraded."""
        mock_cache.set = AsyncMock()
        mock_cache.get = AsyncMock(return_value="ok")
        mock_cache.get_metrics = MagicMock(
            return_value={
                "backend": "memory",
                "hit_rate_percent": 0,
                "hits": 0,
                "misses": 0,
                "sets": 0,
                "deletes": 0,
                "avg_get_time_ms": 0,
            }
        )
        mock_get_sched.return_value = None
        client.app.state.scheduler_status = "disabled_for_test"

        try:
            resp = client.get(DETAILED_URL, headers={"Authorization": "Bearer tok123"})
        finally:
            client.app.state.scheduler_status = None

        sched_check = resp.json()["checks"]["scheduler"]
        assert sched_check["status"] == "disabled_for_test"
        assert sched_check["active_jobs"] == 0
        assert sched_check["jobs"] == []

    @patch("app.api.routes.health.get_settings")
    @patch("app.core.database.get_db_stats", return_value={})
    @patch("app.api.routes.health.cache_manager")
    @patch("app.api.routes.health.get_scheduler")
    def test_detailed_jwt_configured(
        self,
        mock_get_sched,
        mock_cache,
        mock_db_stats,
        mock_settings,
        client,
    ):
        """Detailed endpoint should report jwt_configured status."""
        settings = MagicMock()
        settings.azure_ad_tenant_id = "tid"
        settings.azure_ad_client_id = "cid"
        settings.azure_ad_client_secret = "csec"  # pragma: allowlist secret
        settings.jwt_secret_key = "super-secret"  # pragma: allowlist secret
        settings.app_version = "2.0.0"
        settings.environment = "staging"
        mock_settings.return_value = settings

        mock_cache.set = AsyncMock()
        mock_cache.get = AsyncMock(return_value="ok")
        mock_cache.get_metrics = MagicMock(
            return_value={
                "backend": "memory",
                "hit_rate_percent": 0,
                "hits": 0,
                "misses": 0,
                "sets": 0,
                "deletes": 0,
                "avg_get_time_ms": 0,
            }
        )
        mock_get_sched.return_value = _mock_scheduler_running()

        resp = client.get(DETAILED_URL)
        data = resp.json()

        assert data["checks"]["jwt_configured"] is True
        assert data["version"] == "2.0.0"
        assert data["environment"] == "staging"

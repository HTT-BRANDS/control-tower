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


# Default healthy payload returned by cache_manager.check_health() — matches
# what the real CacheManager produces for an in-memory backend in tests.
_HEALTHY_CACHE_PROBE: dict = {
    "status": "healthy",
    "backend": "memory",
    "hit_rate_percent": 85.0,
    "hits": 100,
    "misses": 18,
    "sets": 50,
    "deletes": 5,
    "avg_get_time_ms": 0.12,
}


def _stub_cache(mock_cache, *, check_health_return=None, check_health_side_effect=None):
    """Wire up the minimum cache_manager surface area each health endpoint uses.

    The route code consolidates cache liveness into a single bounded probe
    (``cache_manager.check_health``) — see app/core/cache/manager.py and ct-czv.
    Tests can pass a custom ``check_health_return`` payload (e.g. degraded /
    unhealthy) or a ``check_health_side_effect`` (e.g. raise) to drive the
    desired branch. The legacy set/get/get_metrics mocks are still set so any
    older test that asserts on them keeps working without churn.
    """
    mock_cache.set = AsyncMock()
    mock_cache.get = AsyncMock(return_value="ok")
    mock_cache.get_metrics = MagicMock(
        return_value={
            "backend": _HEALTHY_CACHE_PROBE["backend"],
            "hit_rate_percent": _HEALTHY_CACHE_PROBE["hit_rate_percent"],
            "hits": _HEALTHY_CACHE_PROBE["hits"],
            "misses": _HEALTHY_CACHE_PROBE["misses"],
            "sets": _HEALTHY_CACHE_PROBE["sets"],
            "deletes": _HEALTHY_CACHE_PROBE["deletes"],
            "avg_get_time_ms": _HEALTHY_CACHE_PROBE["avg_get_time_ms"],
        }
    )
    if check_health_side_effect is not None:
        mock_cache.check_health = AsyncMock(side_effect=check_health_side_effect)
    else:
        mock_cache.check_health = AsyncMock(
            return_value=check_health_return
            if check_health_return is not None
            else dict(_HEALTHY_CACHE_PROBE)
        )
    return mock_cache


def _mock_cache_healthy():
    """Return patchers for a healthy cache_manager (kept for backwards-compat)."""
    return _stub_cache(MagicMock())


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
        _stub_cache(mock_cache)
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
        _stub_cache(
            mock_cache,
            check_health_return={
                **_HEALTHY_CACHE_PROBE,
                "hit_rate_percent": 90,
            },
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
        _stub_cache(mock_cache)
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
        _stub_cache(mock_cache)
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
        _stub_cache(
            mock_cache,
            check_health_return={
                "status": "degraded",
                "backend": "memory",
                "error": "cache read/write mismatch",
            },
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
        _stub_cache(
            mock_cache,
            check_health_return={
                "status": "unhealthy",
                "backend": "memory",
                "error": "Redis down",
            },
        )
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
        _stub_cache(mock_cache)
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
        _stub_cache(mock_cache)
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
        _stub_cache(mock_cache)
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
        _stub_cache(mock_cache)
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

        _stub_cache(mock_cache)
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

        _stub_cache(mock_cache)
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
        _stub_cache(mock_cache)
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
        _stub_cache(mock_cache)
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
        _stub_cache(mock_cache)
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
        _stub_cache(
            mock_cache,
            check_health_return={
                "status": "healthy",
                "backend": "redis",
                "hit_rate_percent": 92.0,
                "hits": 200,
                "misses": 17,
                "sets": 100,
                "deletes": 8,
                "avg_get_time_ms": 0.45,
            },
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
        _stub_cache(mock_cache)
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
        _stub_cache(mock_cache)
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
        _stub_cache(mock_cache)
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
        _stub_cache(mock_cache)
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
        _stub_cache(mock_cache)
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
        _stub_cache(mock_cache)
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

        _stub_cache(mock_cache)
        mock_get_sched.return_value = _mock_scheduler_running()

        resp = client.get(DETAILED_URL)
        data = resp.json()

        assert data["checks"]["jwt_configured"] is True
        assert data["version"] == "2.0.0"
        assert data["environment"] == "staging"


# ===========================================================================
# Azure configuration tri-state — ct-czv AC #2
# ===========================================================================
#
# The detailed health endpoint must NOT report overall ``degraded`` just
# because a non-production environment intentionally lacks Azure AD creds.
# Only a *production* environment missing creds is a real fault.


class TestAzureConfigTriState:
    """Tests for the staging-friendly Azure configuration rollup."""

    @patch("app.api.routes.health.get_settings")
    @patch("app.api.routes.health.cache_manager")
    @patch("app.api.routes.health.get_scheduler")
    def test_staging_without_azure_creds_is_not_degraded(
        self,
        mock_get_sched,
        mock_cache,
        mock_settings,
        client,
    ):
        """Staging (non-prod) missing Azure creds: azure_configured=not_required, overall=healthy."""
        settings = MagicMock()
        settings.azure_ad_tenant_id = None
        settings.azure_ad_client_id = None
        settings.azure_ad_client_secret = None
        settings.jwt_secret_key = "jwt"  # pragma: allowlist secret
        settings.app_version = "2.0.0"
        settings.environment = "staging"
        settings.is_production = False
        mock_settings.return_value = settings

        _stub_cache(mock_cache)
        mock_get_sched.return_value = _mock_scheduler_running()

        resp = client.get(DETAILED_URL)
        data = resp.json()

        assert data["checks"]["azure_configured"]["status"] == "not_required"
        assert data["checks"]["azure_configured"]["environment"] == "staging"
        assert data["status"] == "healthy", (
            "Non-production missing Azure creds must NOT degrade overall status (ct-czv AC #2)"
        )

    @patch("app.api.routes.health.get_settings")
    @patch("app.api.routes.health.cache_manager")
    @patch("app.api.routes.health.get_scheduler")
    def test_production_without_azure_creds_is_degraded(
        self,
        mock_get_sched,
        mock_cache,
        mock_settings,
        client,
    ):
        """Production missing Azure creds: azure_configured=missing, overall=degraded."""
        settings = MagicMock()
        settings.azure_ad_tenant_id = None
        settings.azure_ad_client_id = None
        settings.azure_ad_client_secret = None
        settings.jwt_secret_key = "jwt"  # pragma: allowlist secret
        settings.app_version = "2.0.0"
        settings.environment = "production"
        settings.is_production = True
        mock_settings.return_value = settings

        _stub_cache(mock_cache)
        mock_get_sched.return_value = _mock_scheduler_running()

        resp = client.get(DETAILED_URL)
        data = resp.json()

        assert data["checks"]["azure_configured"]["status"] == "missing"
        assert data["status"] == "degraded"

    @patch("app.api.routes.health.get_settings")
    @patch("app.api.routes.health.cache_manager")
    @patch("app.api.routes.health.get_scheduler")
    def test_fully_configured_azure_reports_configured(
        self,
        mock_get_sched,
        mock_cache,
        mock_settings,
        client,
    ):
        """With all three creds present AND Azure returning 200 on the
        client-credentials probe, azure_configured=configured.

        ct-jxe note: pre-fix, this test asserted on shape-only behaviour
        (any time creds were set, status was 'configured'). That's exactly
        what let the 2026-04-29 secret expiry sit undetected for 20 days.
        The probe is now part of the contract — so tests that want to
        assert 'configured' must also stub the probe to return a 200.
        """
        settings = MagicMock()
        settings.azure_ad_tenant_id = "tid"
        settings.azure_ad_client_id = "cid"
        settings.azure_ad_client_secret = "csec"  # pragma: allowlist secret
        settings.azure_ad_token_endpoint = (
            "https://login.microsoftonline.com/tid/oauth2/v2.0/token"
        )
        settings.jwt_secret_key = "jwt"  # pragma: allowlist secret
        settings.app_version = "2.0.0"
        settings.environment = "production"
        settings.is_production = True
        mock_settings.return_value = settings

        _stub_cache(mock_cache)
        mock_get_sched.return_value = _mock_scheduler_running()

        # Stub the probe to return "configured" (the green path). We patch
        # at the source module so any future caller picks up the stub too.
        from app.core import azure_credential_probe as probe_mod

        with patch.object(
            probe_mod,
            "probe_client_credential",
            AsyncMock(return_value=probe_mod.ProbeResult(status="configured", http_status=200)),
        ):
            resp = client.get(DETAILED_URL)
        data = resp.json()

        assert data["checks"]["azure_configured"]["status"] == "configured"

    @patch("app.api.routes.health.get_settings")
    @patch("app.api.routes.health.cache_manager")
    @patch("app.api.routes.health.get_scheduler")
    def test_expired_secret_reports_unauthenticated_and_degraded(
        self,
        mock_get_sched,
        mock_cache,
        mock_settings,
        client,
    ):
        """ct-jxe regression: an expired client secret (AADSTS7000215) must
        flip azure_configured -> 'unauthenticated' AND promote overall
        status to 'degraded' so monitoring dashboards see the outage
        within ~5 min (the probe cache TTL), not 20 days."""
        settings = MagicMock()
        settings.azure_ad_tenant_id = "tid"
        settings.azure_ad_client_id = "cid"
        settings.azure_ad_client_secret = "expired-secret"  # pragma: allowlist secret
        settings.azure_ad_token_endpoint = (
            "https://login.microsoftonline.com/tid/oauth2/v2.0/token"
        )
        settings.jwt_secret_key = "jwt"  # pragma: allowlist secret
        settings.app_version = "2.0.0"
        settings.environment = "production"
        settings.is_production = True
        mock_settings.return_value = settings

        _stub_cache(mock_cache)
        mock_get_sched.return_value = _mock_scheduler_running()

        from app.core import azure_credential_probe as probe_mod

        unauth = probe_mod.ProbeResult(
            status="unauthenticated",
            detail="AADSTS7000215: Invalid client secret",
            azure_error_code="AADSTS7000215",
            http_status=401,
        )
        with patch.object(
            probe_mod, "probe_client_credential", AsyncMock(return_value=unauth)
        ):
            resp = client.get(DETAILED_URL)
        data = resp.json()

        assert data["checks"]["azure_configured"]["status"] == "unauthenticated"
        assert data["checks"]["azure_configured"]["azure_error_code"] == "AADSTS7000215"
        assert data["status"] == "degraded", (
            "ct-jxe: an unauthenticated probe result MUST promote overall "
            "status to 'degraded' so the dashboard alerts within the probe "
            "cache TTL — that's the whole point of the post-mortem fix."
        )

    @patch("app.api.routes.health.get_settings")
    @patch("app.api.routes.health.cache_manager")
    @patch("app.api.routes.health.get_scheduler")
    def test_unreachable_probe_does_NOT_promote_to_degraded(
        self,
        mock_get_sched,
        mock_cache,
        mock_settings,
        client,
    ):
        """ct-jxe: when the probe can't even reach login.microsoftonline.com
        (network blip, Azure outage, DNS hiccup), we can't tell whether the
        secret works or not. Don't poison overall health on this — flapping
        the dashboard red on every Azure network hiccup defeats the
        purpose of a probe that's supposed to surface OUR config bugs."""
        settings = MagicMock()
        settings.azure_ad_tenant_id = "tid"
        settings.azure_ad_client_id = "cid"
        settings.azure_ad_client_secret = "csec"  # pragma: allowlist secret
        settings.azure_ad_token_endpoint = (
            "https://login.microsoftonline.com/tid/oauth2/v2.0/token"
        )
        settings.jwt_secret_key = "jwt"  # pragma: allowlist secret
        settings.app_version = "2.0.0"
        settings.environment = "production"
        settings.is_production = True
        mock_settings.return_value = settings

        _stub_cache(mock_cache)
        mock_get_sched.return_value = _mock_scheduler_running()

        from app.core import azure_credential_probe as probe_mod

        unreachable = probe_mod.ProbeResult(
            status="unreachable",
            detail="Token endpoint timed out after 5.0s",
        )
        with patch.object(
            probe_mod, "probe_client_credential", AsyncMock(return_value=unreachable)
        ):
            resp = client.get(DETAILED_URL)
        data = resp.json()

        assert data["checks"]["azure_configured"]["status"] == "unreachable"
        assert data["status"] == "healthy", (
            "ct-jxe: an 'unreachable' probe is ambiguous (could be Azure-side"
            " hiccup or our config). Do NOT promote to degraded — only"
            " 'missing' and 'unauthenticated' (which are definitively OUR"
            " problem) should poison the rollup."
        )

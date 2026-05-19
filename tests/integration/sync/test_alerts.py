"""Tests for sync alerts and alert resolution endpoints.

Split off from the former monolithic `tests/integration/test_sync_api.py`
(issue 6oj7, 2026-04-22). Shared fixtures live in `./conftest.py`.
"""

from datetime import UTC, datetime, timedelta

from app.api.services.monitoring_service import MonitoringService
from app.core.database import get_db
from app.main import app
from app.models.monitoring import Alert, SyncJobLog

# ============================================================================


class TestSyncAlertsEndpoint:
    """Integration tests for GET /api/v1/sync/alerts."""

    def test_get_alerts_success(self, sync_client):
        """Sync alerts returns list of active alerts."""
        # Add an alert to the database
        db = next(app.dependency_overrides[get_db]())

        alert = Alert(
            alert_type="high_failure_rate",
            severity="warning",
            job_type="costs_sync",
            tenant_id="test-tenant-123",
            title="High Failure Rate",
            message="Sync job failure rate exceeded threshold",
            is_resolved=False,
            created_at=datetime.now(UTC) - timedelta(hours=2),
        )
        db.add(alert)
        db.commit()

        response = sync_client.get("/api/v1/sync/alerts")

        assert response.status_code == 200
        data = response.json()

        # Validate structure
        assert "alerts" in data
        assert "stats" in data
        assert isinstance(data["alerts"], list)

        # Validate alert structure if we have data
        if len(data["alerts"]) > 0:
            alert_entry = data["alerts"][0]
            assert "id" in alert_entry
            assert "alert_type" in alert_entry
            assert "severity" in alert_entry
            assert "job_type" in alert_entry
            assert "tenant_id" in alert_entry
            assert "title" in alert_entry
            assert "message" in alert_entry
            assert "is_resolved" in alert_entry
            assert "created_at" in alert_entry
            assert "resolved_at" in alert_entry
            assert "resolved_by" in alert_entry

            # Validate types
            assert isinstance(alert_entry["severity"], str)
            assert alert_entry["severity"] in ["info", "warning", "error", "critical"]
            assert isinstance(alert_entry["is_resolved"], bool)

    def test_get_alerts_job_type_filter(self, sync_client):
        """Sync alerts can be filtered by job_type."""
        # Add alerts for different job types
        db = next(app.dependency_overrides[get_db]())

        alert1 = Alert(
            alert_type="high_failure_rate",
            severity="warning",
            job_type="costs_sync",
            tenant_id="test-tenant-123",
            title="Costs Alert",
            message="Test alert",
            is_resolved=False,
            created_at=datetime.now(UTC),
        )
        alert2 = Alert(
            alert_type="long_duration",
            severity="info",
            job_type="compliance_sync",
            tenant_id="test-tenant-123",
            title="Compliance Alert",
            message="Test alert",
            is_resolved=False,
            created_at=datetime.now(UTC),
        )
        db.add_all([alert1, alert2])
        db.commit()

        response = sync_client.get("/api/v1/sync/alerts?job_type=costs_sync")

        assert response.status_code == 200
        data = response.json()

        # All alerts should match the filter
        for alert in data["alerts"]:
            assert alert["job_type"] == "costs_sync"

    def test_get_alerts_severity_filter(self, sync_client):
        """Sync alerts can be filtered by severity."""
        # Add alerts with different severities
        db = next(app.dependency_overrides[get_db]())

        alert1 = Alert(
            alert_type="high_failure_rate",
            severity="critical",
            job_type="costs_sync",
            tenant_id="test-tenant-123",
            title="Critical Alert",
            message="Test alert",
            is_resolved=False,
            created_at=datetime.now(UTC),
        )
        alert2 = Alert(
            alert_type="long_duration",
            severity="warning",
            job_type="costs_sync",
            tenant_id="test-tenant-123",
            title="Warning Alert",
            message="Test alert",
            is_resolved=False,
            created_at=datetime.now(UTC),
        )
        db.add_all([alert1, alert2])
        db.commit()

        response = sync_client.get("/api/v1/sync/alerts?severity=critical")

        assert response.status_code == 200
        data = response.json()

        # All alerts should match the filter
        for alert in data["alerts"]:
            assert alert["severity"] == "critical"

    def test_get_alerts_severity_validation(self, sync_client):
        """Sync alerts validates severity parameter."""
        # Invalid severity
        response = sync_client.get("/api/v1/sync/alerts?severity=invalid")
        assert response.status_code == 422  # Validation error

    def test_get_alerts_include_resolved(self, sync_client):
        """Sync alerts can include resolved alerts."""
        # Add both resolved and unresolved alerts
        db = next(app.dependency_overrides[get_db]())

        alert1 = Alert(
            alert_type="high_failure_rate",
            severity="warning",
            job_type="costs_sync",
            tenant_id="test-tenant-123",
            title="Active Alert",
            message="Test alert",
            is_resolved=False,
            created_at=datetime.now(UTC),
        )
        alert2 = Alert(
            alert_type="long_duration",
            severity="info",
            job_type="costs_sync",
            tenant_id="test-tenant-123",
            title="Resolved Alert",
            message="Test alert",
            is_resolved=True,
            created_at=datetime.now(UTC) - timedelta(hours=5),
            resolved_at=datetime.now(UTC) - timedelta(hours=1),
            resolved_by="user-123",
        )
        db.add_all([alert1, alert2])
        db.commit()

        # Get only active alerts (default)
        response_active = sync_client.get("/api/v1/sync/alerts")
        assert response_active.status_code == 200
        data_active = response_active.json()

        # Get all alerts including resolved
        response_all = sync_client.get("/api/v1/sync/alerts?include_resolved=true")
        assert response_all.status_code == 200
        data_all = response_all.json()

        # All alerts response should have more or equal alerts
        assert len(data_all["alerts"]) >= len(data_active["alerts"])

    def test_get_alerts_tenant_isolation(self, sync_client, test_tenant_id):
        """Sync alerts only returns alerts for accessible tenants."""
        # Add alerts for different tenants
        db = next(app.dependency_overrides[get_db]())

        alert1 = Alert(
            alert_type="high_failure_rate",
            severity="warning",
            job_type="costs_sync",
            tenant_id=test_tenant_id,
            title="Accessible Alert",
            message="Test alert",
            is_resolved=False,
            created_at=datetime.now(UTC),
        )
        alert2 = Alert(
            alert_type="long_duration",
            severity="info",
            job_type="costs_sync",
            tenant_id="other-tenant-999",
            title="Inaccessible Alert",
            message="Test alert",
            is_resolved=False,
            created_at=datetime.now(UTC),
        )
        db.add_all([alert1, alert2])
        db.commit()

        response = sync_client.get("/api/v1/sync/alerts")

        assert response.status_code == 200
        data = response.json()

        # Should only return alerts for accessible tenants
        for alert in data["alerts"]:
            if alert["tenant_id"]:  # Some alerts might not have tenant_id
                assert alert["tenant_id"] in [test_tenant_id, "test-tenant-456"]

    def test_get_alerts_requires_auth(self, sync_unauth_client):
        """Sync alerts endpoint requires authentication."""
        response = sync_unauth_client.get("/api/v1/sync/alerts")
        assert response.status_code == 401


# ============================================================================
# POST /api/v1/sync/alerts/{alert_id}/resolve Tests
# ============================================================================


class TestResolveAlertEndpoint:
    """Integration tests for POST /api/v1/sync/alerts/{alert_id}/resolve."""

    def test_resolve_alert_success(self, sync_client):
        """Resolve alert successfully updates alert status."""
        # Add an unresolved alert
        db = next(app.dependency_overrides[get_db]())

        alert = Alert(
            alert_type="high_failure_rate",
            severity="warning",
            job_type="costs_sync",
            tenant_id="test-tenant-123",
            title="Test Alert",
            message="Test alert message",
            is_resolved=False,
            created_at=datetime.now(UTC),
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        alert_id = alert.id

        response = sync_client.post(f"/api/v1/sync/alerts/{alert_id}/resolve?resolved_by=test-user")

        assert response.status_code == 200
        data = response.json()

        # Validate response
        assert "id" in data
        assert "alert_type" in data
        assert "is_resolved" in data
        assert "resolved_at" in data
        assert "resolved_by" in data

        assert data["id"] == alert_id
        assert data["is_resolved"] is True
        assert data["resolved_by"] == "test-user"
        assert data["resolved_at"] is not None

        # Verify alert is marked resolved in database
        db.refresh(alert)
        assert alert.is_resolved == 1  # SQLite stores as integer
        assert alert.resolved_by == "test-user"
        assert alert.resolved_at is not None

    def test_resolve_alert_not_found(self, sync_client):
        """Resolve alert returns 404 for non-existent alert."""
        response = sync_client.post("/api/v1/sync/alerts/99999/resolve")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_resolve_alert_invalid_id(self, sync_client):
        """Resolve alert validates alert_id parameter."""
        # Test invalid ID (negative)
        response = sync_client.post("/api/v1/sync/alerts/-1/resolve")
        assert response.status_code == 422  # Validation error

        # Test invalid ID (zero)
        response = sync_client.post("/api/v1/sync/alerts/0/resolve")
        assert response.status_code == 422

    def test_resolve_alert_validates_resolved_by(self, sync_client):
        """Resolve alert validates resolved_by parameter."""
        # Add an unresolved alert
        db = next(app.dependency_overrides[get_db]())

        alert = Alert(
            alert_type="high_failure_rate",
            severity="warning",
            job_type="costs_sync",
            tenant_id="test-tenant-123",
            title="Test Alert",
            message="Test alert message",
            is_resolved=False,
            created_at=datetime.now(UTC),
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        alert_id = alert.id

        # Test resolved_by too long (> 100 chars)
        long_string = "x" * 101
        response = sync_client.post(
            f"/api/v1/sync/alerts/{alert_id}/resolve?resolved_by={long_string}"
        )
        assert response.status_code == 422  # Validation error

    def test_resolve_alert_requires_auth(self, sync_unauth_client):
        """Resolve alert endpoint requires authentication."""
        response = sync_unauth_client.post("/api/v1/sync/alerts/1/resolve")
        assert response.status_code == 401


# ============================================================================
# Tenant Isolation Tests


# ============================================================================
# Alert Dedup + Auto-Resolve (ct-l2j)
# ============================================================================
#
# Production hit 1,489 active `no_records` alerts because the alert-creation
# path inside MonitoringService._check_for_alerts_after_completion was creating
# a fresh alert on every sync run that produced zero records. There was no
# dedup against existing unresolved alerts of the same (type, job, tenant),
# and no auto-resolution when a sync subsequently recovered with real data.
#
# These tests use a real in-memory SQLite via the integration `db_session`
# fixture — query-shape assertions on MagicMock chains would prove nothing.


class TestAlertDeduplication:
    """An unresolved alert of the same (type, job, tenant) must short-circuit."""

    def _make_log(
        self,
        db_session,
        *,
        job_type: str,
        tenant_id: str | None,
        status: str,
        records: int,
        errors: int = 0,
    ) -> SyncJobLog:
        """Persist and return a SyncJobLog row to drive the alert path."""
        log = SyncJobLog(
            job_type=job_type,
            tenant_id=tenant_id,
            status=status,
            started_at=datetime.now(UTC) - timedelta(seconds=30),
            ended_at=datetime.now(UTC),
            duration_ms=30000,
            records_processed=records,
            errors_count=errors,
        )
        db_session.add(log)
        db_session.commit()
        db_session.refresh(log)
        return log

    def test_no_records_alert_does_not_duplicate_on_repeat_runs(self, db_session):
        """ct-l2j: same (job, tenant) zero-record run must not stack alerts."""
        svc = MonitoringService(db=db_session)
        # Seed three prior zero-record completed runs so the threshold gate trips.
        for _ in range(3):
            self._make_log(
                db_session,
                job_type="costs",
                tenant_id="tenant-bcc",
                status="completed",
                records=0,
            )

        # First completion → creates one alert.
        log1 = self._make_log(
            db_session, job_type="costs", tenant_id="tenant-bcc", status="completed", records=0
        )
        created_first = svc._check_for_alerts_after_completion(log1)
        assert len(created_first) == 1
        assert created_first[0].alert_type == "no_records"

        # Second identical completion → must NOT create a second alert.
        log2 = self._make_log(
            db_session, job_type="costs", tenant_id="tenant-bcc", status="completed", records=0
        )
        created_second = svc._check_for_alerts_after_completion(log2)
        assert created_second == [], (
            "Dedup failed: second zero-record run created a duplicate `no_records` alert. "
            "This is the exact bug behind ct-l2j (1,489 active alerts in prod)."
        )

        # Exactly one unresolved no_records alert exists for this (job, tenant).
        active = (
            db_session.query(Alert)
            .filter(
                Alert.alert_type == "no_records",
                Alert.job_type == "costs",
                Alert.tenant_id == "tenant-bcc",
                Alert.is_resolved == 0,
            )
            .count()
        )
        assert active == 1

    def test_sync_failure_alert_dedups_across_repeat_failures(self, db_session):
        """ct-l2j: repeated failures of the same (job, tenant) → one alert."""
        svc = MonitoringService(db=db_session)
        log1 = self._make_log(
            db_session,
            job_type="identity",
            tenant_id="tenant-fn",
            status="failed",
            records=0,
        )
        svc._check_for_alerts_after_completion(log1)
        log2 = self._make_log(
            db_session,
            job_type="identity",
            tenant_id="tenant-fn",
            status="failed",
            records=0,
        )
        created = svc._check_for_alerts_after_completion(log2)
        assert created == [], "Repeated failures must dedup into one sync_failure alert"

        unresolved = (
            db_session.query(Alert)
            .filter(
                Alert.alert_type == "sync_failure",
                Alert.job_type == "identity",
                Alert.tenant_id == "tenant-fn",
                Alert.is_resolved == 0,
            )
            .count()
        )
        assert unresolved == 1

    def test_different_tenants_get_independent_alerts(self, db_session):
        """Dedup is scoped to (alert_type, job_type, tenant_id) — independent tenants stay independent."""
        svc = MonitoringService(db=db_session)
        # Seed enough zero-record runs to trip the threshold for both tenants.
        for tenant in ("tenant-bcc", "tenant-fn"):
            for _ in range(4):
                self._make_log(
                    db_session,
                    job_type="costs",
                    tenant_id=tenant,
                    status="completed",
                    records=0,
                )
                svc._check_for_alerts_after_completion(
                    db_session.query(SyncJobLog)
                    .filter(SyncJobLog.tenant_id == tenant)
                    .order_by(SyncJobLog.id.desc())
                    .first()
                )

        per_tenant = (
            db_session.query(Alert.tenant_id)
            .filter(Alert.alert_type == "no_records", Alert.is_resolved == 0)
            .all()
        )
        tenant_ids = sorted(t[0] for t in per_tenant)
        assert tenant_ids == ["tenant-bcc", "tenant-fn"], (
            f"Expected one alert per tenant after dedup; got {tenant_ids}"
        )


class TestAlertAutoResolution:
    """A successful sync must clear stale alerts for the same (job, tenant)."""

    def _make_log(
        self,
        db_session,
        *,
        job_type: str,
        tenant_id: str | None,
        status: str,
        records: int,
    ) -> SyncJobLog:
        log = SyncJobLog(
            job_type=job_type,
            tenant_id=tenant_id,
            status=status,
            started_at=datetime.now(UTC) - timedelta(seconds=30),
            ended_at=datetime.now(UTC),
            duration_ms=30000,
            records_processed=records,
            errors_count=0,
        )
        db_session.add(log)
        db_session.commit()
        db_session.refresh(log)
        return log

    def _seed_alert(
        self,
        db_session,
        *,
        alert_type: str,
        job_type: str,
        tenant_id: str | None,
    ) -> Alert:
        alert = Alert(
            alert_type=alert_type,
            severity="warning",
            job_type=job_type,
            tenant_id=tenant_id,
            title=f"seed {alert_type}",
            message="seeded by test",
            is_resolved=False,
            created_at=datetime.now(UTC),
        )
        db_session.add(alert)
        db_session.commit()
        db_session.refresh(alert)
        return alert

    def test_no_records_alert_auto_resolves_when_records_flow_again(self, db_session):
        """ct-l2j AC #4: once a sync produces records, the prior no_records alert clears."""
        svc = MonitoringService(db=db_session)
        seeded = self._seed_alert(
            db_session,
            alert_type="no_records",
            job_type="costs",
            tenant_id="tenant-bcc",
        )
        # Sync recovers and processes 42 records.
        log = self._make_log(
            db_session,
            job_type="costs",
            tenant_id="tenant-bcc",
            status="completed",
            records=42,
        )

        svc._check_for_alerts_after_completion(log)

        db_session.refresh(seeded)
        assert seeded.is_resolved, (
            "Recovered sync must auto-resolve the prior no_records alert (ct-l2j AC #4)"
        )
        assert seeded.resolved_by == "auto:sync_recovered"
        assert seeded.resolved_at is not None

    def test_sync_failure_alert_auto_resolves_on_next_success(self, db_session):
        """A subsequent successful run resolves a prior sync_failure alert."""
        svc = MonitoringService(db=db_session)
        seeded = self._seed_alert(
            db_session,
            alert_type="sync_failure",
            job_type="resources",
            tenant_id="tenant-htt",
        )
        log = self._make_log(
            db_session,
            job_type="resources",
            tenant_id="tenant-htt",
            status="completed",
            records=100,
        )

        svc._check_for_alerts_after_completion(log)

        db_session.refresh(seeded)
        assert seeded.is_resolved
        assert seeded.resolved_by == "auto:sync_recovered"

    def test_no_records_alert_does_not_resolve_on_another_zero_record_run(self, db_session):
        """Auto-resolve must require *real* recovery — zero records means still broken."""
        svc = MonitoringService(db=db_session)
        seeded = self._seed_alert(
            db_session,
            alert_type="no_records",
            job_type="costs",
            tenant_id="tenant-bcc",
        )
        log = self._make_log(
            db_session,
            job_type="costs",
            tenant_id="tenant-bcc",
            status="completed",
            records=0,
        )

        svc._check_for_alerts_after_completion(log)

        db_session.refresh(seeded)
        assert not seeded.is_resolved, (
            "no_records alert must NOT auto-resolve when the new run also produced zero records"
        )

    def test_auto_resolve_is_scoped_to_job_and_tenant(self, db_session):
        """A successful run for tenant A must not touch tenant B's alerts."""
        svc = MonitoringService(db=db_session)
        alert_bcc = self._seed_alert(
            db_session,
            alert_type="no_records",
            job_type="costs",
            tenant_id="tenant-bcc",
        )
        alert_fn = self._seed_alert(
            db_session,
            alert_type="no_records",
            job_type="costs",
            tenant_id="tenant-fn",
        )

        # Only tenant-bcc's sync recovers.
        log = self._make_log(
            db_session,
            job_type="costs",
            tenant_id="tenant-bcc",
            status="completed",
            records=10,
        )
        svc._check_for_alerts_after_completion(log)

        db_session.refresh(alert_bcc)
        db_session.refresh(alert_fn)
        assert alert_bcc.is_resolved
        assert not alert_fn.is_resolved, (
            "Auto-resolve must NOT cross tenant boundaries (cross-contamination bug)"
        )

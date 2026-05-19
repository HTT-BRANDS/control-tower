"""Regression tests for ct-l2j / F-2: the zero-records alert had three SQL bugs.

The pre-fix query::

    recent_zeros = (
        self.db.query(SyncJobLog)
        .filter(
            SyncJobLog.job_type == log_entry.job_type,
            SyncJobLog.status == \"completed\",
            SyncJobLog.records_processed == 0,
        )
        .order_by(SyncJobLog.started_at.desc())
        .limit(ALERT_THRESHOLDS[\"zero_records_threshold\"])
        .count()
    )

was broken in three ways:

  1. ``.limit(N).count()`` — on MSSQL (production) the LIMIT was
     ignored and ``count()`` returned the **total** row count, so the
     alert would fire as soon as any 3+ historical zero-runs existed
     anywhere in the table.
  2. Not tenant-scoped — three zero runs across three different tenants
     could trip a single alert tagged with the most-recent tenant.
  3. "Consecutive" was a lie — the filter included
     ``records_processed == 0``, so a single zero run scattered among
     100 successes would still match.

Post-fix the query materializes the most recent N runs (any
records_processed value) for the specific (job_type, tenant_id) and
checks the consecutive-zero condition in Python.

These tests use the real in-memory SQLite ``db_session`` fixture so
they exercise the actual SQL — that's the whole point: the bug was
in the query, not in the Python logic.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.api.services.monitoring_service import (
    ALERT_THRESHOLDS,
    MonitoringService,
)
from app.models.monitoring import Alert, SyncJobLog
from app.models.tenant import Tenant


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def tenant_a(db_session):
    t = Tenant(
        id="tenant-a-id",
        name="Tenant A",
        tenant_id="00000000-0000-0000-0000-aaaaaaaaaaaa",
        is_active=True,
    )
    db_session.add(t)
    db_session.commit()
    return t


@pytest.fixture
def tenant_b(db_session):
    t = Tenant(
        id="tenant-b-id",
        name="Tenant B",
        tenant_id="00000000-0000-0000-0000-bbbbbbbbbbbb",
        is_active=True,
    )
    db_session.add(t)
    db_session.commit()
    return t


def _seed_log(
    db,
    *,
    tenant_id: str,
    job_type: str,
    records: int,
    minutes_ago: int,
    status: str = "completed",
) -> SyncJobLog:
    """Create + insert a SyncJobLog row. Returns the log without committing,
    so caller can decide commit timing for transaction-scope tests."""
    started = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    log = SyncJobLog(
        job_type=job_type,
        tenant_id=tenant_id,
        status=status,
        started_at=started,
        ended_at=started + timedelta(seconds=1),
        duration_ms=1000,
        records_processed=records,
        records_created=0,
        records_updated=0,
        errors_count=0,
    )
    db.add(log)
    return log


# ── F-2 bug-#3: "consecutive" must actually mean consecutive ─────────


def test_single_zero_among_successes_does_NOT_trigger_alert(
    db_session, tenant_a
):
    """One zero scattered among non-zero runs must NOT fire the alert.

    Pre-fix this DID fire because the filter included
    ``records_processed == 0`` directly, so non-zero runs were never
    even considered.
    """
    threshold = ALERT_THRESHOLDS["zero_records_threshold"]  # 3
    # Seed lots of successful non-zero runs, with ONE zero scattered in.
    for i in range(10):
        _seed_log(
            db_session,
            tenant_id=tenant_a.id,
            job_type="costs",
            records=100 if i != 5 else 0,
            minutes_ago=60 - i,  # oldest first → newest last
        )
    # The "current run" we're evaluating: latest run is 100 records,
    # so we don't even enter the zero-records branch. Use a separate
    # zero-records run as the trigger to mimic the production path.
    trigger = _seed_log(
        db_session,
        tenant_id=tenant_a.id,
        job_type="costs",
        records=0,
        minutes_ago=0,  # most recent
    )
    db_session.commit()

    svc = MonitoringService(db=db_session)
    alerts = svc._check_for_alerts_after_completion(trigger)

    no_record_alerts = [a for a in alerts if a.alert_type == "no_records"]
    assert not no_record_alerts, (
        f"ct-l2j: a single zero among non-zero runs must NOT trigger "
        f"a no_records alert (got {len(no_record_alerts)})"
    )


def test_three_consecutive_zeros_DOES_trigger_alert(db_session, tenant_a):
    """Three consecutive zero-record runs SHOULD trigger the alert."""
    threshold = ALERT_THRESHOLDS["zero_records_threshold"]  # 3
    # Seed N-1 zero runs from older history, then the trigger is the Nth zero.
    for i in range(threshold - 1):
        _seed_log(
            db_session,
            tenant_id=tenant_a.id,
            job_type="costs",
            records=0,
            minutes_ago=60 - i,
        )
    trigger = _seed_log(
        db_session,
        tenant_id=tenant_a.id,
        job_type="costs",
        records=0,
        minutes_ago=0,
    )
    db_session.commit()

    svc = MonitoringService(db=db_session)
    alerts = svc._check_for_alerts_after_completion(trigger)

    no_record_alerts = [a for a in alerts if a.alert_type == "no_records"]
    assert len(no_record_alerts) == 1, (
        f"ct-l2j: 3 consecutive zeros must fire the alert; "
        f"got {len(no_record_alerts)}"
    )


# ── F-2 bug-#2: tenant scoping ────────────────────────────────────────


def test_zeros_from_other_tenants_do_NOT_count(db_session, tenant_a, tenant_b):
    """Audit's recommended test: 3 zero runs for tenant A + 1 success for
    tenant B must NOT fire an alert for tenant B.
    """
    threshold = ALERT_THRESHOLDS["zero_records_threshold"]  # 3
    # Tenant A: full streak of zeros — would trip an alert FOR TENANT A.
    for i in range(threshold):
        _seed_log(
            db_session,
            tenant_id=tenant_a.id,
            job_type="resources",
            records=0,
            minutes_ago=120 - i,
        )
    # Tenant B: ONE successful non-zero run, then a single zero now.
    _seed_log(
        db_session,
        tenant_id=tenant_b.id,
        job_type="resources",
        records=500,
        minutes_ago=30,
    )
    trigger_b = _seed_log(
        db_session,
        tenant_id=tenant_b.id,
        job_type="resources",
        records=0,
        minutes_ago=0,
    )
    db_session.commit()

    svc = MonitoringService(db=db_session)
    alerts = svc._check_for_alerts_after_completion(trigger_b)

    no_record_alerts_for_b = [
        a for a in alerts
        if a.alert_type == "no_records" and a.tenant_id == tenant_b.id
    ]
    assert not no_record_alerts_for_b, (
        "ct-l2j: tenant B has only 1 zero run (with a 500-record success "
        "right before it). Tenant A's separate streak must NOT bleed into "
        "tenant B's alerting."
    )


def test_each_tenant_alerts_independently(db_session, tenant_a, tenant_b):
    """Both tenants having full streaks should produce alerts for EACH,
    not just one. Sanity check that tenant scoping isn't too aggressive.
    """
    threshold = ALERT_THRESHOLDS["zero_records_threshold"]  # 3

    # Tenant A: full streak.
    for i in range(threshold - 1):
        _seed_log(
            db_session,
            tenant_id=tenant_a.id,
            job_type="identity",
            records=0,
            minutes_ago=120 - i,
        )
    trigger_a = _seed_log(
        db_session,
        tenant_id=tenant_a.id,
        job_type="identity",
        records=0,
        minutes_ago=10,
    )

    # Tenant B: full streak.
    for i in range(threshold - 1):
        _seed_log(
            db_session,
            tenant_id=tenant_b.id,
            job_type="identity",
            records=0,
            minutes_ago=120 - i,
        )
    trigger_b = _seed_log(
        db_session,
        tenant_id=tenant_b.id,
        job_type="identity",
        records=0,
        minutes_ago=5,
    )
    db_session.commit()

    svc = MonitoringService(db=db_session)
    alerts_a = svc._check_for_alerts_after_completion(trigger_a)
    alerts_b = svc._check_for_alerts_after_completion(trigger_b)

    a_alerts = [a for a in alerts_a if a.alert_type == "no_records"]
    b_alerts = [a for a in alerts_b if a.alert_type == "no_records"]

    assert len(a_alerts) == 1 and a_alerts[0].tenant_id == tenant_a.id
    assert len(b_alerts) == 1 and b_alerts[0].tenant_id == tenant_b.id


# ── F-2 bug-#1: dialect portability (count() on a limited query) ──────


def test_threshold_check_does_NOT_fire_with_only_two_zeros(
    db_session, tenant_a
):
    """Pre-fix on MSSQL: any 3+ historical zeros tripped the alert because
    ``.limit(3).count()`` returned the total count, not 3.

    Post-fix: 2 zero runs (threshold-1) must NOT fire the alert, even if
    there are dozens of unrelated zero runs in old history.
    """
    threshold = ALERT_THRESHOLDS["zero_records_threshold"]  # 3
    # Seed 50 ancient zero runs — pre-fix this would have made
    # .count() return >= threshold immediately.
    for i in range(50):
        _seed_log(
            db_session,
            tenant_id=tenant_a.id,
            job_type="compliance",
            records=0,
            minutes_ago=10_000 + i,  # very old
        )
    # Then a single non-zero success that breaks the streak.
    _seed_log(
        db_session,
        tenant_id=tenant_a.id,
        job_type="compliance",
        records=200,
        minutes_ago=60,
    )
    # Then 2 zeros now (below threshold of 3).
    _seed_log(
        db_session,
        tenant_id=tenant_a.id,
        job_type="compliance",
        records=0,
        minutes_ago=10,
    )
    trigger = _seed_log(
        db_session,
        tenant_id=tenant_a.id,
        job_type="compliance",
        records=0,
        minutes_ago=0,
    )
    db_session.commit()

    svc = MonitoringService(db=db_session)
    alerts = svc._check_for_alerts_after_completion(trigger)
    no_record_alerts = [a for a in alerts if a.alert_type == "no_records"]
    assert not no_record_alerts, (
        f"ct-l2j: only 2 recent consecutive zeros (threshold is 3) — "
        f"must NOT fire even with 50 ancient zero runs in history; "
        f"got {len(no_record_alerts)} alerts. This is the exact dialect "
        f"portability bug that hit MSSQL prod."
    )


def test_streak_broken_by_recent_success_resets(db_session, tenant_a):
    """If the most recent successful run was non-zero, the streak isn't
    consecutive — even if older history is all zeros."""
    threshold = ALERT_THRESHOLDS["zero_records_threshold"]  # 3
    # Old: zeros.
    for i in range(5):
        _seed_log(
            db_session,
            tenant_id=tenant_a.id,
            job_type="resources",
            records=0,
            minutes_ago=500 - i,
        )
    # Middle: a non-zero success that BREAKS the streak.
    _seed_log(
        db_session,
        tenant_id=tenant_a.id,
        job_type="resources",
        records=300,
        minutes_ago=30,
    )
    # Recent: a single zero (the trigger). With threshold=3, the most-recent
    # 3 runs are (zero, success, zero) — NOT all zeros, so no alert.
    _seed_log(
        db_session,
        tenant_id=tenant_a.id,
        job_type="resources",
        records=0,
        minutes_ago=15,
    )
    trigger = _seed_log(
        db_session,
        tenant_id=tenant_a.id,
        job_type="resources",
        records=0,
        minutes_ago=0,
    )
    db_session.commit()

    svc = MonitoringService(db=db_session)
    alerts = svc._check_for_alerts_after_completion(trigger)
    no_record_alerts = [a for a in alerts if a.alert_type == "no_records"]
    assert not no_record_alerts, (
        "ct-l2j: a non-zero success between zeros must break the 'consecutive' "
        "streak. The last 3 runs are (zero, success, zero) which is NOT a "
        "consecutive-zero streak."
    )

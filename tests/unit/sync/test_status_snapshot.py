"""Unit tests for the real-time sync status snapshot + SSE stream (bd ct-7d6)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.core.sync.status_snapshot import (
    SYNC_TYPES,
    build_sync_snapshot,
)
from app.models.monitoring import SyncJobLog


def _add_log(db, job_type, status, started_at, ended_at=None, error=None):
    log = SyncJobLog(
        job_type=job_type,
        status=status,
        started_at=started_at,
        ended_at=ended_at,
        error_message=error,
    )
    db.add(log)
    db.commit()
    return log


class TestBuildSyncSnapshot:
    def test_empty_db_all_idle(self, db_session):
        snap = build_sync_snapshot(db_session)
        assert snap["running"] == 0
        assert snap["last_sync_at"] is None
        assert {j["type"] for j in snap["jobs"]} == set(SYNC_TYPES)
        assert all(j["status"] == "idle" for j in snap["jobs"])
        # ts is always present and ISO-ish.
        assert snap["ts"] and "T" in snap["ts"]

    def test_completed_sets_last_sync_at(self, db_session):
        t = datetime.now(UTC) - timedelta(minutes=5)
        _add_log(db_session, "costs", "completed", t, ended_at=t)
        snap = build_sync_snapshot(db_session)
        costs = next(j for j in snap["jobs"] if j["type"] == "costs")
        assert costs["status"] == "completed"
        assert snap["last_sync_at"] is not None
        assert snap["running"] == 0

    def test_running_increments_count(self, db_session):
        now = datetime.now(UTC)
        _add_log(db_session, "compliance", "running", now)
        snap = build_sync_snapshot(db_session)
        comp = next(j for j in snap["jobs"] if j["type"] == "compliance")
        assert comp["status"] == "running"
        assert snap["running"] == 1

    def test_failed_surfaces_error(self, db_session):
        now = datetime.now(UTC)
        _add_log(db_session, "resources", "failed", now, ended_at=now, error="boom")
        snap = build_sync_snapshot(db_session)
        res = next(j for j in snap["jobs"] if j["type"] == "resources")
        assert res["status"] == "failed"
        assert res["error"] == "boom"

    def test_latest_log_wins_per_type(self, db_session):
        old = datetime.now(UTC) - timedelta(hours=2)
        new = datetime.now(UTC) - timedelta(minutes=1)
        _add_log(db_session, "identity", "failed", old, ended_at=old, error="old")
        _add_log(db_session, "identity", "completed", new, ended_at=new)
        snap = build_sync_snapshot(db_session)
        ident = next(j for j in snap["jobs"] if j["type"] == "identity")
        # Most recent (completed) must win over the older failed run.
        assert ident["status"] == "completed"
        assert ident["error"] is None

    def test_naive_datetime_coerced_to_utc_iso(self, db_session):
        # DB rows can be tz-naive (SQLite); snapshot must still emit ISO strings.
        naive = datetime.now()
        _add_log(db_session, "costs", "completed", naive, ended_at=naive)
        snap = build_sync_snapshot(db_session)
        costs = next(j for j in snap["jobs"] if j["type"] == "costs")
        assert costs["last_run_at"] is not None
        # ISO 8601 with timezone offset.
        assert "+00:00" in costs["last_run_at"] or costs["last_run_at"].endswith("Z")


class TestSyncStreamEndpoint:
    def test_stream_requires_auth(self, client):
        # Auth runs before the StreamingResponse is created, so this returns
        # immediately (no hanging stream) when unauthenticated.
        resp = client.get("/api/v1/sync/stream")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_event_stream_first_frame(self, db_session, monkeypatch):
        # Drive the async generator directly: the first frame is yielded before
        # any sleep, so we avoid the infinite-stream / TestClient buffering trap.
        import contextlib

        from app.api.routes import sync as sync_routes

        @contextlib.contextmanager
        def fake_db_context():
            yield db_session

        monkeypatch.setattr(sync_routes, "get_db_context", fake_db_context)

        now = datetime.now(UTC)
        _add_log(db_session, "costs", "completed", now, ended_at=now)

        class _FakeRequest:
            async def is_disconnected(self):
                return False

        gen = sync_routes._sync_event_stream(_FakeRequest())
        try:
            frame = await gen.__anext__()
        finally:
            await gen.aclose()

        assert frame.startswith("event: sync")
        assert '"jobs"' in frame
        assert '"type":"costs"' in frame


@pytest.mark.parametrize("sync_type", SYNC_TYPES)
def test_every_sync_type_present_in_snapshot(db_session, sync_type):
    snap = build_sync_snapshot(db_session)
    assert any(j["type"] == sync_type for j in snap["jobs"])

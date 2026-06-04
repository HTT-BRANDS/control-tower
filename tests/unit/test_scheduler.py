"""Tests for app/core/scheduler.py — background job scheduler.

Covers:
- init_scheduler: creates scheduler with expected jobs
- get_scheduler: returns global instance
- Riverside wrapper functions (hourly_mfa_sync, daily_full_sync, etc.)
- trigger_manual_sync: valid/invalid sync types

Phase B.3 of the test coverage sprint.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# init_scheduler
# ---------------------------------------------------------------------------


class TestInitScheduler:
    """init_scheduler creates an AsyncIOScheduler with all expected jobs."""

    @patch("app.core.scheduler._get_sync_functions")
    @patch("app.core.scheduler.AsyncIOScheduler")
    def test_creates_scheduler(self, mock_cls, mock_sync_fns):
        mock_sync_fns.return_value = {
            "costs": MagicMock(),
            "compliance": MagicMock(),
            "resources": MagicMock(),
            "identity": MagicMock(),
            "riverside": MagicMock(),
            "dmarc": MagicMock(),
        }
        mock_sched = MagicMock()
        mock_cls.return_value = mock_sched

        from app.core.scheduler import init_scheduler

        result = init_scheduler()

        assert result is mock_sched
        # 6 core syncs + 4 riverside wrappers = 10 jobs
        assert mock_sched.add_job.call_count == 10

    @patch("app.core.scheduler._get_sync_functions")
    @patch("app.core.scheduler.AsyncIOScheduler")
    def test_job_ids_are_unique(self, mock_cls, mock_sync_fns):
        mock_sync_fns.return_value = {
            "costs": MagicMock(),
            "compliance": MagicMock(),
            "resources": MagicMock(),
            "identity": MagicMock(),
            "riverside": MagicMock(),
            "dmarc": MagicMock(),
        }
        mock_sched = MagicMock()
        mock_cls.return_value = mock_sched

        from app.core.scheduler import init_scheduler

        init_scheduler()

        job_ids = [call.kwargs["id"] for call in mock_sched.add_job.call_args_list]
        assert len(job_ids) == len(set(job_ids)), f"Duplicate job IDs: {job_ids}"

    @patch("app.core.scheduler._get_sync_functions")
    @patch("app.core.scheduler.AsyncIOScheduler")
    def test_all_jobs_use_replace_existing(self, mock_cls, mock_sync_fns):
        mock_sync_fns.return_value = {
            "costs": MagicMock(),
            "compliance": MagicMock(),
            "resources": MagicMock(),
            "identity": MagicMock(),
            "riverside": MagicMock(),
            "dmarc": MagicMock(),
        }
        mock_sched = MagicMock()
        mock_cls.return_value = mock_sched

        from app.core.scheduler import init_scheduler

        init_scheduler()

        for call in mock_sched.add_job.call_args_list:
            assert call.kwargs.get("replace_existing") is True, (
                f"Job {call.kwargs.get('id')} missing replace_existing=True"
            )


# ---------------------------------------------------------------------------
# get_scheduler
# ---------------------------------------------------------------------------


class TestGetScheduler:
    def test_returns_none_when_not_initialized(self):
        import app.core.scheduler as mod

        original = mod.scheduler
        try:
            mod.scheduler = None
            assert mod.get_scheduler() is None
        finally:
            mod.scheduler = original

    def test_returns_scheduler_when_set(self):
        import app.core.scheduler as mod

        original = mod.scheduler
        sentinel = MagicMock()
        try:
            mod.scheduler = sentinel
            assert mod.get_scheduler() is sentinel
        finally:
            mod.scheduler = original


# ---------------------------------------------------------------------------
# Riverside wrapper functions
# ---------------------------------------------------------------------------


class TestHourlyMfaSync:
    @patch("app.services.riverside_sync.sync_all_tenants", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_calls_sync_with_mfa_only(self, mock_sync):
        mock_sync.return_value = {"tenants_processed": 3}
        from app.core.scheduler import hourly_mfa_sync

        await hourly_mfa_sync()

        mock_sync.assert_awaited_once_with(
            skip_failed=True,
            include_mfa=True,
            include_devices=False,
            include_requirements=False,
            include_maturity=False,
        )

    @patch("app.services.riverside_sync.sync_all_tenants", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_handles_exception_gracefully(self, mock_sync):
        mock_sync.side_effect = Exception("boom")
        from app.core.scheduler import hourly_mfa_sync

        # Should not raise — just logs
        await hourly_mfa_sync()


class TestDailyFullSync:
    @patch("app.services.riverside_sync.sync_all_tenants", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_calls_sync_with_all_flags(self, mock_sync):
        mock_sync.return_value = {"tenants_processed": 5, "tenants_failed": 0}
        from app.core.scheduler import daily_full_sync

        await daily_full_sync()

        mock_sync.assert_awaited_once_with(
            skip_failed=True,
            include_mfa=True,
            include_devices=True,
            include_requirements=True,
            include_maturity=True,
        )


class TestWeeklyThreatSync:
    @patch("app.services.riverside_sync.sync_all_tenants", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_calls_sync_with_threat_flags(self, mock_sync):
        mock_sync.return_value = {"tenants_processed": 2}
        from app.core.scheduler import weekly_threat_sync

        await weekly_threat_sync()

        mock_sync.assert_awaited_once_with(
            skip_failed=True,
            include_mfa=False,
            include_devices=True,
            include_requirements=True,
            include_maturity=False,
        )


class TestMonthlyReportSync:
    @patch("app.services.riverside_sync.sync_all_tenants", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_calls_sync_with_all_flags(self, mock_sync):
        mock_sync.return_value = {"tenants_processed": 5, "status": "ok"}
        from app.core.scheduler import monthly_report_sync

        await monthly_report_sync()

        mock_sync.assert_awaited_once()


# ---------------------------------------------------------------------------
# trigger_manual_sync
# ---------------------------------------------------------------------------


class TestTriggerManualSync:
    @patch("app.core.scheduler._get_sync_functions")
    @pytest.mark.asyncio
    async def test_valid_sync_type(self, mock_fns):
        mock_fn = AsyncMock()
        mock_fns.return_value = {"costs": mock_fn}
        from app.core.scheduler import trigger_manual_sync

        result = await trigger_manual_sync("costs")

        assert result is True
        mock_fn.assert_awaited_once()

    @patch("app.core.scheduler._get_sync_functions")
    @pytest.mark.asyncio
    async def test_invalid_sync_type(self, mock_fns):
        mock_fns.return_value = {"costs": AsyncMock()}
        from app.core.scheduler import trigger_manual_sync

        result = await trigger_manual_sync("nonexistent")

        assert result is False

    @patch("app.core.scheduler._get_sync_functions")
    @pytest.mark.asyncio
    async def test_riverside_wrapper_types(self, mock_fns):
        mock_fns.return_value = {"costs": AsyncMock()}
        from app.core.scheduler import trigger_manual_sync

        with patch("app.core.scheduler.hourly_mfa_sync", new_callable=AsyncMock) as mock_mfa:
            result = await trigger_manual_sync("hourly_mfa")

        assert result is True
        mock_mfa.assert_awaited_once()


# ---------------------------------------------------------------------------
# Heartbeat / observability (ct-ar3): _record_job_event + get_scheduler_health
# ---------------------------------------------------------------------------

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, EVENT_JOB_MISSED


@pytest.fixture
def _clean_job_events():
    """Isolate the module-level heartbeat dict per test."""
    import app.core.scheduler as sched_mod

    saved = dict(sched_mod._job_events)
    sched_mod._job_events.clear()
    yield sched_mod
    sched_mod._job_events.clear()
    sched_mod._job_events.update(saved)


class TestRecordJobEvent:
    def test_executed_sets_last_success_and_clears_error(self, _clean_job_events):
        m = _clean_job_events
        m._record_job_event(SimpleNamespace(job_id="sync_costs", code=EVENT_JOB_EXECUTED))
        rec = m._job_events["sync_costs"]
        assert rec["last_success"] is not None
        assert rec["last_error"] is None

    def test_error_records_timestamp_and_truncated_exception(self, _clean_job_events):
        m = _clean_job_events
        m._record_job_event(
            SimpleNamespace(
                job_id="sync_costs", code=EVENT_JOB_ERROR, exception=Exception("boom" * 500)
            )
        )
        rec = m._job_events["sync_costs"]
        assert rec["last_error"] is not None
        assert len(rec["last_exception"]) <= 500

    def test_missed_records_timestamp(self, _clean_job_events):
        m = _clean_job_events
        m._record_job_event(SimpleNamespace(job_id="sync_costs", code=EVENT_JOB_MISSED))
        assert m._job_events["sync_costs"]["last_missed"] is not None


class TestGetSchedulerHealth:
    def test_none_scheduler_reports_not_running(self, _clean_job_events):
        m = _clean_job_events
        with patch.object(m, "scheduler", None):
            health = m.get_scheduler_health()
        assert health["running"] is False
        assert health["jobs"] == []
        assert health["any_overdue"] is False
        assert health["job_count"] == 0

    def test_overdue_job_flagged(self, _clean_job_events):
        m = _clean_job_events
        past = datetime.now(UTC) - timedelta(seconds=m._OVERDUE_SECONDS + 60)
        fake_job = SimpleNamespace(id="sync_costs", name="Sync Cost Data", next_run_time=past)
        fake_sched = SimpleNamespace(running=True, get_jobs=lambda: [fake_job])
        with patch.object(m, "scheduler", fake_sched):
            health = m.get_scheduler_health()
        assert health["running"] is True
        assert health["any_overdue"] is True
        assert health["jobs"][0]["overdue"] is True
        assert health["jobs"][0]["id"] == "sync_costs"

    def test_future_job_not_overdue_and_surfaces_last_success(self, _clean_job_events):
        m = _clean_job_events
        m._record_job_event(SimpleNamespace(job_id="sync_costs", code=EVENT_JOB_EXECUTED))
        future = datetime.now(UTC) + timedelta(hours=1)
        fake_job = SimpleNamespace(id="sync_costs", name="Sync Cost Data", next_run_time=future)
        fake_sched = SimpleNamespace(running=True, get_jobs=lambda: [fake_job])
        with patch.object(m, "scheduler", fake_sched):
            health = m.get_scheduler_health()
        assert health["any_overdue"] is False
        assert health["jobs"][0]["overdue"] is False
        assert health["jobs"][0]["last_success"] is not None

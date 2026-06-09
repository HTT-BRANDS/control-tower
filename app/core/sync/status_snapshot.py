"""Sync status snapshot builder.

Produces a small, JSON-serializable view of "where are the sync jobs right
now?" for the real-time SSE stream (bd ct-7d6) and any other consumer that
wants a single, cheap status object.

Kept deliberately separate from the route layer so it can be unit-tested
without spinning up FastAPI, and from the scheduler so it has no import-time
side effects.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.monitoring import SyncJobLog

SYNC_TYPES: tuple[str, ...] = ("costs", "compliance", "resources", "identity")

# Statuses we treat as "the job is currently working".
_RUNNING_STATES = {"running", "in_progress", "started"}


def _iso(value: datetime | None) -> str | None:
    """Render a datetime as a UTC-aware ISO 8601 string (or None)."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _latest_log_per_type(db: Session) -> dict[str, SyncJobLog]:
    """Return the most recent SyncJobLog for each sync type.

    One grouped subquery (max started_at per job_type) joined back to the rows
    keeps this to a single round trip instead of N queries.
    """
    subq = (
        db.query(
            SyncJobLog.job_type.label("job_type"),
            func.max(SyncJobLog.started_at).label("max_started"),
        )
        .group_by(SyncJobLog.job_type)
        .subquery()
    )

    rows = (
        db.query(SyncJobLog)
        .join(
            subq,
            (SyncJobLog.job_type == subq.c.job_type)
            & (SyncJobLog.started_at == subq.c.max_started),
        )
        .all()
    )

    latest: dict[str, SyncJobLog] = {}
    for row in rows:
        # Defensive against duplicate started_at ties: keep the highest id.
        existing = latest.get(row.job_type)
        if existing is None or row.id > existing.id:
            latest[row.job_type] = row
    return latest


def _scheduler_next_runs() -> dict[str, str | None]:
    """Map sync type -> next scheduled run ISO string, best-effort.

    Never raises: if the scheduler isn't initialized (tests, import order) we
    simply report no next-run times.
    """
    next_runs: dict[str, str | None] = {}
    try:
        from app.core.scheduler import get_scheduler

        scheduler = get_scheduler()
        if not scheduler:
            return next_runs
        for job in scheduler.get_jobs():
            blob = f"{job.id} {job.name}".lower()
            for sync_type in SYNC_TYPES:
                if sync_type in blob and sync_type not in next_runs:
                    next_runs[sync_type] = _iso(job.next_run_time)
    except Exception:  # pragma: no cover - scheduler is optional
        return next_runs
    return next_runs


def build_sync_snapshot(db: Session) -> dict[str, Any]:
    """Build the real-time sync status snapshot.

    Shape (see realtimeSync.js):
        {
          "ts": "<now iso>",
          "last_sync_at": "<most recent completed start>" | null,
          "running": <int>,
          "jobs": [
            {"type": "costs", "status": "...", "last_run_at": "...",
             "ended_at": "...", "next_run_at": "...", "error": "..." | null},
            ...
          ],
        }
    """
    latest = _latest_log_per_type(db)
    next_runs = _scheduler_next_runs()

    jobs: list[dict[str, Any]] = []
    running = 0
    last_sync_candidates: list[datetime] = []

    for sync_type in SYNC_TYPES:
        log = latest.get(sync_type)
        if log is None:
            jobs.append(
                {
                    "type": sync_type,
                    "status": "idle",
                    "last_run_at": None,
                    "ended_at": None,
                    "next_run_at": next_runs.get(sync_type),
                    "error": None,
                }
            )
            continue

        status = (log.status or "idle").lower()
        if status in _RUNNING_STATES:
            running += 1
            status = "running"

        if status == "completed" and log.started_at is not None:
            last_sync_candidates.append(log.started_at)

        jobs.append(
            {
                "type": sync_type,
                "status": status,
                "last_run_at": _iso(log.started_at),
                "ended_at": _iso(log.ended_at),
                "next_run_at": next_runs.get(sync_type),
                "error": log.error_message if status == "failed" else None,
            }
        )

    last_sync_at = max(last_sync_candidates) if last_sync_candidates else None

    return {
        "ts": _iso(datetime.now(UTC)),
        "last_sync_at": _iso(last_sync_at),
        "running": running,
        "jobs": jobs,
    }

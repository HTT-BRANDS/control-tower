"""MFA alert job helpers for the Riverside scheduler."""

import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


async def schedule_mfa_alert_checks_on_scheduler(
    scheduler: AsyncIOScheduler | None,
    interval_minutes: int = 60,
    job_id: str = "mfa_gap_alerts",
) -> dict[str, Any]:
    """Schedule MFA gap alert checks on an initialized scheduler."""
    if scheduler is None:
        raise RuntimeError(
            "Riverside scheduler not initialized. Call init_riverside_scheduler() first."
        )

    from app.alerts.mfa_alerts import MFAGapDetector

    async def _mfa_alert_job() -> dict[str, Any]:
        logger.info(f"Running scheduled MFA alert check (job_id: {job_id})")
        detector = MFAGapDetector()
        return await detector.check_and_alert()

    scheduler.add_job(
        _mfa_alert_job,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id=job_id,
        name="MFA Gap Alert Check",
        replace_existing=True,
    )

    logger.info(f"Scheduled MFA alert checks: interval={interval_minutes}min, job_id={job_id}")
    return {
        "success": True,
        "job_id": job_id,
        "interval_minutes": interval_minutes,
        "scheduler_active": scheduler.state == "started" if hasattr(scheduler, "state") else True,
    }


async def remove_mfa_alert_checks_from_scheduler(
    scheduler: AsyncIOScheduler | None,
    job_id: str = "mfa_gap_alerts",
) -> dict[str, Any]:
    """Remove scheduled MFA gap alert checks from an initialized scheduler."""
    if scheduler is None:
        return {"success": False, "error": "Scheduler not initialized"}

    try:
        scheduler.remove_job(job_id)
        logger.info(f"Removed MFA alert checks job: {job_id}")
        return {
            "success": True,
            "job_id": job_id,
            "message": "Job removed successfully",
        }
    except Exception as exc:
        logger.warning(f"Could not remove MFA alert job {job_id}: {exc}")
        return {"success": False, "job_id": job_id, "error": str(exc)}

"""DeadlineTracker scheduler jobs for Riverside compliance monitoring."""

import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.alerts.deadline_alerts import DeadlineTracker

logger = logging.getLogger(__name__)


async def schedule_deadline_checks() -> dict[str, Any]:
    """Run scheduled deadline monitoring using the DeadlineTracker.

    This is the scheduled job wrapper for deadline monitoring using
    the new DeadlineTracker class with granular alert levels.

    Queries riverside_requirements and sends notifications at:
    - INFO: 90 days before deadline
    - WARNING: 60 days before deadline
    - HIGH: 30 days before deadline
    - CRITICAL: 14, 7, 1 days before and overdue

    Returns:
        Dict with check results and notification status.

    Example:
        >>> result = await schedule_deadline_checks()
        >>> print(f"Sent {result['notifications_sent']} notifications")
    """
    logger.info("Starting scheduled deadline check with DeadlineTracker")

    try:
        tracker = DeadlineTracker()
        result = await tracker.track_requirement_deadlines()

        # Send notifications for all alerts
        notifications = await tracker.send_deadline_notifications(result.alerts)

        successful_notifications = len([n for n in notifications if n.get("success")])

        return {
            "success": True,
            "alerts_found": len(result.alerts),
            "info_count": result.info_count,
            "warning_count": result.warning_count,
            "high_count": result.high_count,
            "critical_count": result.critical_count,
            "overdue_count": result.overdue_count,
            "notifications_sent": successful_notifications,
            "notifications_failed": len(notifications) - successful_notifications,
            "checked_at": result.checked_at.isoformat(),
            "alert_details": [
                {
                    "requirement_id": a.requirement_id,
                    "tenant_id": a.tenant_id,
                    "days_until": a.days_until_deadline,
                    "level": a.alert_level.value,
                    "is_overdue": a.is_overdue,
                }
                for a in result.alerts
            ],
        }

    except Exception as e:
        logger.error(f"Scheduled deadline check failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "alerts_found": 0,
            "notifications_sent": 0,
        }


def add_deadline_tracker_jobs(scheduler: AsyncIOScheduler) -> None:
    """Add DeadlineTracker-based deadline monitoring jobs to scheduler.

    Args:
        scheduler: The APScheduler instance to add jobs to
    """
    # Daily deadline check at 9 AM using DeadlineTracker
    scheduler.add_job(
        schedule_deadline_checks,
        trigger=CronTrigger(hour=9, minute=0),
        id="riverside_deadline_tracker",
        name="Riverside Deadline Tracker Check",
        replace_existing=True,
    )

    # Additional check at 2 PM for critical deadlines
    scheduler.add_job(
        schedule_deadline_checks,
        trigger=CronTrigger(hour=14, minute=0),
        id="riverside_deadline_tracker_afternoon",
        name="Riverside Deadline Tracker Afternoon Check",
        replace_existing=True,
    )

    logger.info("Added DeadlineTracker deadline monitoring jobs to scheduler")

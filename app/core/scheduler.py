"""Background job scheduler for data synchronization."""

import logging
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import get_settings

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)
settings = get_settings()

# Global scheduler instance
scheduler: AsyncIOScheduler | None = None


def _get_sync_functions() -> dict:
    """Lazy-import sync functions to avoid circular imports.

    The sync modules import from app.api.services which import from
    app.core (circuit_breaker, etc.), creating a cycle when
    app.core.__init__.py eagerly imports this module.
    """
    from app.core.sync.compliance import sync_compliance
    from app.core.sync.costs import sync_costs
    from app.core.sync.dmarc import sync_dmarc_dkim
    from app.core.sync.identity import sync_identity
    from app.core.sync.resources import sync_resources
    from app.core.sync.riverside import sync_riverside

    return {
        "costs": sync_costs,
        "compliance": sync_compliance,
        "resources": sync_resources,
        "identity": sync_identity,
        "riverside": sync_riverside,
        "dmarc": sync_dmarc_dkim,
    }


def init_scheduler() -> AsyncIOScheduler:
    """Initialize and configure the background scheduler."""
    global scheduler

    scheduler = AsyncIOScheduler()

    # Lazy-import sync functions to break circular import chain
    sync_fns = _get_sync_functions()

    # Cost sync job
    scheduler.add_job(
        sync_fns["costs"],
        trigger=IntervalTrigger(hours=settings.cost_sync_interval_hours),
        id="sync_costs",
        name="Sync Cost Data",
        replace_existing=True,
    )

    # Compliance sync job
    scheduler.add_job(
        sync_fns["compliance"],
        trigger=IntervalTrigger(hours=settings.compliance_sync_interval_hours),
        id="sync_compliance",
        name="Sync Compliance Data",
        replace_existing=True,
    )

    # Resource sync job
    scheduler.add_job(
        sync_fns["resources"],
        trigger=IntervalTrigger(hours=settings.resource_sync_interval_hours),
        id="sync_resources",
        name="Sync Resource Inventory",
        replace_existing=True,
    )

    # Identity sync job
    scheduler.add_job(
        sync_fns["identity"],
        trigger=IntervalTrigger(hours=settings.identity_sync_interval_hours),
        id="sync_identity",
        name="Sync Identity Data",
        replace_existing=True,
    )

    # Riverside compliance sync job (every 4 hours)
    scheduler.add_job(
        sync_fns["riverside"],
        trigger=IntervalTrigger(hours=4),
        id="sync_riverside",
        name="Sync Riverside Compliance Data",
        replace_existing=True,
    )

    # DMARC/DKIM sync job (daily at 2 AM)
    scheduler.add_job(
        sync_fns["dmarc"],
        trigger=CronTrigger(hour=2, minute=0),
        id="sync_dmarc",
        name="Sync DMARC/DKIM Data",
        replace_existing=True,
    )

    # Riverside hourly MFA sync (every hour)
    scheduler.add_job(
        hourly_mfa_sync,
        trigger=CronTrigger(minute=0),
        id="riverside_hourly_mfa_sync",
        name="Riverside Hourly MFA Sync",
        replace_existing=True,
    )

    # Riverside daily full sync (1 AM)
    scheduler.add_job(
        daily_full_sync,
        trigger=CronTrigger(hour=1, minute=0),
        id="riverside_daily_full_sync",
        name="Riverside Daily Full Sync",
        replace_existing=True,
    )

    # Riverside weekly threat sync (Sundays at 3 AM)
    scheduler.add_job(
        weekly_threat_sync,
        trigger=CronTrigger(day_of_week="sun", hour=3, minute=0),
        id="riverside_weekly_threat_sync",
        name="Riverside Weekly Threat Sync",
        replace_existing=True,
    )

    # Riverside monthly report sync (1st of month at 4 AM)
    scheduler.add_job(
        monthly_report_sync,
        trigger=CronTrigger(day=1, hour=4, minute=0),
        id="riverside_monthly_report_sync",
        name="Riverside Monthly Report Sync",
        replace_existing=True,
    )

    logger.info("Scheduler initialized with sync jobs")
    return scheduler


def get_scheduler() -> AsyncIOScheduler | None:
    """Get the scheduler instance."""
    return scheduler


# Riverside scheduled sync wrapper functions


async def hourly_mfa_sync() -> None:
    """Hourly MFA data refresh for all tenants."""
    from app.services.riverside_sync import sync_all_tenants

    logger.info("Starting hourly MFA sync job")
    try:
        result = await sync_all_tenants(
            skip_failed=True,
            include_mfa=True,
            include_devices=False,
            include_requirements=False,
            include_maturity=False,
        )
        logger.info(
            "Hourly MFA sync completed: %d tenants processed",
            result.get("tenants_processed", 0),
        )
    except Exception:
        logger.exception("Hourly MFA sync failed")


async def daily_full_sync() -> None:
    """Daily full compliance sync at 1 AM -- MFA, devices, requirements, maturity."""
    from app.services.riverside_sync import sync_all_tenants

    logger.info("Starting daily full compliance sync job")
    try:
        result = await sync_all_tenants(
            skip_failed=True,
            include_mfa=True,
            include_devices=True,
            include_requirements=True,
            include_maturity=True,
        )
        logger.info(
            "Daily full sync completed: %d tenants, %d failed",
            result.get("tenants_processed", 0),
            result.get("tenants_failed", 0),
        )
    except Exception:
        logger.exception("Daily full sync failed")


async def weekly_threat_sync() -> None:
    """Weekly threat data sync -- devices, requirements. Sundays at 3 AM."""
    from app.services.riverside_sync import sync_all_tenants

    logger.info("Starting weekly threat data sync job")
    try:
        result = await sync_all_tenants(
            skip_failed=True,
            include_mfa=False,
            include_devices=True,
            include_requirements=True,
            include_maturity=False,
        )
        logger.info(
            "Weekly threat sync completed: %d tenants processed",
            result.get("tenants_processed", 0),
        )
    except Exception:
        logger.exception("Weekly threat sync failed")


async def monthly_report_sync() -> None:
    """Monthly report sync on the 1st at 4 AM -- full data for month-end reports."""
    from app.services.riverside_sync import sync_all_tenants

    logger.info("Starting monthly report sync job")
    try:
        result = await sync_all_tenants(
            skip_failed=True,
            include_mfa=True,
            include_devices=True,
            include_requirements=True,
            include_maturity=True,
        )
        logger.info(
            "Monthly report sync completed: %d tenants, status: %s",
            result.get("tenants_processed", 0),
            result.get("status", "unknown"),
        )
    except Exception:
        logger.exception("Monthly report sync failed")


async def trigger_manual_sync(sync_type: str) -> bool:
    """Trigger a manual sync job."""
    sync_functions = _get_sync_functions()

    # Add riverside wrapper functions
    sync_functions.update(
        {
            "hourly_mfa": hourly_mfa_sync,
            "daily_full": daily_full_sync,
            "weekly_threat": weekly_threat_sync,
            "monthly_report": monthly_report_sync,
        }
    )

    if sync_type not in sync_functions:
        return False

    await sync_functions[sync_type]()
    return True

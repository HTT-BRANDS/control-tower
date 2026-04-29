"""Riverside compliance monitoring scheduler for automated monitoring and alerting.

Compatibility module preserving the historical ``app.core.riverside_scheduler``
import surface while delegating check implementations and scheduler helpers to
focused modules.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.alerts.deadline_alerts import DeadlineAlert
from app.core.config import get_settings
from app.core.notifications import (
    Notification,
    Severity,
    create_dashboard_url,
    record_notification_sent,
    send_notification,
    should_notify,
)
from app.core.riverside_scheduler_checks import (
    check_maturity_regressions as _check_maturity_regressions,
)
from app.core.riverside_scheduler_checks import (
    check_mfa_compliance as _check_mfa_compliance,
)
from app.core.riverside_scheduler_checks import (
    check_requirement_deadlines as _check_requirement_deadlines,
)
from app.core.riverside_scheduler_checks import (
    check_threat_escalations as _check_threat_escalations,
)
from app.core.riverside_scheduler_deadlines import (
    add_deadline_tracker_jobs,
)
from app.core.riverside_scheduler_mfa_alerts import (
    remove_mfa_alert_checks_from_scheduler,
    schedule_mfa_alert_checks_on_scheduler,
)
from app.core.riverside_scheduler_models import (
    DEADLINE_ALERT_INTERVALS as _DEADLINE_ALERT_INTERVALS,
)
from app.core.riverside_scheduler_models import (
    MFA_ADMIN_TARGET_PERCENTAGE as _MFA_ADMIN_TARGET_PERCENTAGE,
)
from app.core.riverside_scheduler_models import (
    MFA_USER_TARGET_PERCENTAGE as _MFA_USER_TARGET_PERCENTAGE,
)
from app.core.riverside_scheduler_models import (
    THREAT_SCORE_CRITICAL_THRESHOLD as _THREAT_SCORE_CRITICAL_THRESHOLD,
)
from app.core.riverside_scheduler_models import (
    THREAT_SCORE_HIGH_THRESHOLD as _THREAT_SCORE_HIGH_THRESHOLD,
)
from app.core.riverside_scheduler_models import (
    MaturityRegression,
    MFAComplianceResult,
    ThreatEscalation,
)

logger = logging.getLogger(__name__)
settings = get_settings()
_riverside_scheduler: AsyncIOScheduler | None = None
DEADLINE_ALERT_INTERVALS = _DEADLINE_ALERT_INTERVALS
MFA_ADMIN_TARGET_PERCENTAGE = _MFA_ADMIN_TARGET_PERCENTAGE
MFA_USER_TARGET_PERCENTAGE = _MFA_USER_TARGET_PERCENTAGE
THREAT_SCORE_CRITICAL_THRESHOLD = _THREAT_SCORE_CRITICAL_THRESHOLD
THREAT_SCORE_HIGH_THRESHOLD = _THREAT_SCORE_HIGH_THRESHOLD


async def check_mfa_compliance(db=None) -> list[MFAComplianceResult]:
    """Monitor MFA enrollment across tenants."""
    return await _check_mfa_compliance(db)


async def check_requirement_deadlines(db=None) -> tuple[list[DeadlineAlert], list[DeadlineAlert]]:
    """Track upcoming requirement due dates and overdue items."""
    return await _check_requirement_deadlines(db)


async def check_maturity_regressions(db=None) -> list[MaturityRegression]:
    """Detect maturity score drops across tenants."""
    return await _check_maturity_regressions(db)


async def check_threat_escalations(
    db=None,
    previous_check_time: datetime | None = None,
) -> list[ThreatEscalation]:
    """Monitor threat level changes and detect high/critical threats."""
    return await _check_threat_escalations(db, previous_check_time)


async def send_mfa_compliance_alerts(
    non_compliant: list[MFAComplianceResult],
) -> list[dict[str, Any]]:
    """Send notifications for MFA compliance violations."""
    results: list[dict[str, Any]] = []

    for result in non_compliant:
        alert_key = f"mfa_compliance_{result.tenant_id}"

        if not should_notify(alert_key, job_type="riverside_mfa"):
            continue

        # Build message
        issues = []
        if not result.user_target_met:
            issues.append(
                f"User MFA: {result.user_mfa_percentage:.1f}% "
                f"(target: {MFA_USER_TARGET_PERCENTAGE}%)"
            )
        if not result.admin_target_met:
            issues.append(
                f"Admin MFA: {result.admin_mfa_percentage:.1f}% "
                f"(target: {MFA_ADMIN_TARGET_PERCENTAGE}%)"
            )

        notification = Notification(
            title=f"MFA Compliance Alert: {result.tenant_id}",
            message=(
                f"Tenant {result.tenant_id} is below MFA compliance thresholds:\n"
                + "\n".join(f"  • {issue}" for issue in issues)
            ),
            severity=Severity.WARNING,
            job_type="riverside_mfa",
            tenant_id=result.tenant_id,
            dashboard_url=create_dashboard_url("riverside"),
        )

        result_dict = await send_notification(notification)
        results.append(result_dict)

        if result_dict.get("success"):
            record_notification_sent(alert_key, job_type="riverside_mfa")

    return results


async def send_deadline_alerts(
    overdue: list[DeadlineAlert],
    approaching: list[DeadlineAlert],
) -> list[dict[str, Any]]:
    """Send notifications for requirement deadline alerts."""
    results: list[dict[str, Any]] = []

    # Send overdue alerts
    for alert in overdue:
        alert_key = f"deadline_overdue_{alert.requirement_id}_{alert.tenant_id}"

        if not should_notify(alert_key, job_type="riverside_deadlines"):
            continue

        notification = Notification(
            title=f"Overdue Requirement: {alert.requirement_id}",
            message=(
                f"Requirement '{alert.title}' is {abs(alert.days_until_deadline)} "
                f"days overdue for tenant {alert.tenant_id}."
            ),
            severity=Severity.ERROR,
            job_type="riverside_deadlines",
            tenant_id=alert.tenant_id,
            dashboard_url=create_dashboard_url("riverside"),
        )

        result_dict = await send_notification(notification)
        results.append(result_dict)

        if result_dict.get("success"):
            record_notification_sent(alert_key, job_type="riverside_deadlines")

    # Send approaching deadline alerts
    for alert in approaching:
        alert_key = (
            f"deadline_approaching_{alert.requirement_id}_{alert.tenant_id}_{alert.alert_stage}"
        )

        if not should_notify(alert_key, job_type="riverside_deadlines"):
            continue

        notification = Notification(
            title=f"Deadline Approaching: {alert.requirement_id}",
            message=(
                f"Requirement '{alert.title}' is due in {alert.days_until_deadline} "
                f"days for tenant {alert.tenant_id}."
            ),
            severity=Severity.WARNING if alert.days_until_deadline > 7 else Severity.ERROR,
            job_type="riverside_deadlines",
            tenant_id=alert.tenant_id,
            dashboard_url=create_dashboard_url("riverside"),
        )

        result_dict = await send_notification(notification)
        results.append(result_dict)

        if result_dict.get("success"):
            record_notification_sent(alert_key, job_type="riverside_deadlines")

    return results


async def send_maturity_regression_alerts(
    regressions: list[MaturityRegression],
) -> list[dict[str, Any]]:
    """Send notifications for maturity score regressions."""
    results: list[dict[str, Any]] = []

    for regression in regressions:
        alert_key = f"maturity_regression_{regression.tenant_id}"

        if not should_notify(alert_key, job_type="riverside_maturity"):
            continue

        notification = Notification(
            title=f"Maturity Score Regression: {regression.tenant_id}",
            message=(
                f"Tenant {regression.tenant_id} maturity score dropped by "
                f"{regression.score_drop:.1f} points: "
                f"{regression.previous_score:.1f} → {regression.current_score:.1f}"
            ),
            severity=Severity.ERROR,
            job_type="riverside_maturity",
            tenant_id=regression.tenant_id,
            dashboard_url=create_dashboard_url("riverside"),
        )

        result_dict = await send_notification(notification)
        results.append(result_dict)

        if result_dict.get("success"):
            record_notification_sent(alert_key, job_type="riverside_maturity")

    return results


async def send_threat_escalation_alerts(
    escalations: list[ThreatEscalation],
) -> list[dict[str, Any]]:
    """Send notifications for threat escalations."""
    results: list[dict[str, Any]] = []

    for escalation in escalations:
        alert_key = (
            f"threat_escalation_{escalation.tenant_id}_{escalation.snapshot_date.isoformat()}"
        )

        if not should_notify(alert_key, job_type="riverside_threats"):
            continue

        severity = Severity.CRITICAL if escalation.is_critical else Severity.ERROR

        notification = Notification(
            title=f"{'Critical' if escalation.is_critical else 'High'} Threat Detected: {escalation.tenant_id}",
            message=(
                f"Tenant {escalation.tenant_id} has elevated threat score: "
                f"{escalation.threat_score:.1f}\n"
                f"  • Vulnerabilities: {escalation.vulnerability_count}\n"
                f"  • Malicious domain alerts: {escalation.malicious_domain_alerts}"
            ),
            severity=severity,
            job_type="riverside_threats",
            tenant_id=escalation.tenant_id,
            dashboard_url=create_dashboard_url("riverside"),
        )

        result_dict = await send_notification(notification)
        results.append(result_dict)

        if result_dict.get("success"):
            record_notification_sent(alert_key, job_type="riverside_threats")

    return results


async def run_mfa_compliance_check() -> dict[str, Any]:
    """Run MFA compliance check and send alerts."""
    logger.info("Starting scheduled MFA compliance check")

    try:
        non_compliant = await check_mfa_compliance()
        notifications = await send_mfa_compliance_alerts(non_compliant)

        return {
            "success": True,
            "violations_found": len(non_compliant),
            "notifications_sent": len([n for n in notifications if n.get("success")]),
            "tenants": [r.tenant_id for r in non_compliant],
        }

    except Exception as e:
        logger.error(f"MFA compliance check failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "violations_found": 0,
            "notifications_sent": 0,
        }


async def run_deadline_check() -> dict[str, Any]:
    """Run requirement deadline check and send alerts."""
    logger.info("Starting scheduled deadline check")

    try:
        overdue, approaching = await check_requirement_deadlines()
        notifications = await send_deadline_alerts(overdue, approaching)

        return {
            "success": True,
            "overdue_count": len(overdue),
            "approaching_count": len(approaching),
            "notifications_sent": len([n for n in notifications if n.get("success")]),
            "overdue_requirements": [a.requirement_id for a in overdue],
            "approaching_requirements": [
                f"{a.requirement_id} ({a.days_until_deadline}d)" for a in approaching
            ],
        }

    except Exception as e:
        logger.error(f"Deadline check failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "overdue_count": 0,
            "approaching_count": 0,
            "notifications_sent": 0,
        }


async def run_maturity_regression_check() -> dict[str, Any]:
    """Run maturity regression check and send alerts."""
    logger.info("Starting scheduled maturity regression check")

    try:
        regressions = await check_maturity_regressions()
        notifications = await send_maturity_regression_alerts(regressions)

        return {
            "success": True,
            "regressions_found": len(regressions),
            "notifications_sent": len([n for n in notifications if n.get("success")]),
            "regressed_tenants": [r.tenant_id for r in regressions],
        }

    except Exception as e:
        logger.error(f"Maturity regression check failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "regressions_found": 0,
            "notifications_sent": 0,
        }


async def run_threat_escalation_check() -> dict[str, Any]:
    """Run threat escalation check and send alerts."""
    logger.info("Starting scheduled threat escalation check")

    try:
        escalations = await check_threat_escalations()
        notifications = await send_threat_escalation_alerts(escalations)

        return {
            "success": True,
            "escalations_found": len(escalations),
            "notifications_sent": len([n for n in notifications if n.get("success")]),
            "threats": [
                {
                    "tenant_id": e.tenant_id,
                    "score": e.threat_score,
                    "critical": e.is_critical,
                }
                for e in escalations
            ],
        }

    except Exception as e:
        logger.error(f"Threat escalation check failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "escalations_found": 0,
            "notifications_sent": 0,
        }


async def run_daily_compliance_report() -> dict[str, Any]:
    """Generate daily compliance report with all checks."""
    logger.info("Starting daily compliance report")

    mfa_result = await run_mfa_compliance_check()
    deadline_result = await run_deadline_check()
    maturity_result = await run_maturity_regression_check()
    threat_result = await run_threat_escalation_check()

    results: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "mfa_check": mfa_result,
        "deadline_check": deadline_result,
        "maturity_check": maturity_result,
        "threat_check": threat_result,
    }

    total_issues = (
        mfa_result.get("violations_found", 0)
        + deadline_result.get("overdue_count", 0)
        + deadline_result.get("approaching_count", 0)
        + maturity_result.get("regressions_found", 0)
        + threat_result.get("escalations_found", 0)
    )

    results["total_issues"] = total_issues
    results["success"] = all(
        r.get("success", False)
        for r in [
            mfa_result,
            deadline_result,
            maturity_result,
            threat_result,
        ]
    )

    logger.info(f"Daily compliance report completed: {total_issues} total issues found")
    return results


def init_riverside_scheduler() -> AsyncIOScheduler:
    """Initialize and configure the Riverside compliance scheduler."""
    global _riverside_scheduler

    _riverside_scheduler = AsyncIOScheduler()

    # Hourly MFA compliance check
    _riverside_scheduler.add_job(
        run_mfa_compliance_check,
        trigger=IntervalTrigger(hours=1),
        id="riverside_mfa_check",
        name="Riverside MFA Compliance Check",
        replace_existing=True,
    )

    # Daily comprehensive compliance report (8 AM)
    _riverside_scheduler.add_job(
        run_daily_compliance_report,
        trigger=CronTrigger(hour=8, minute=0),
        id="riverside_daily_report",
        name="Riverside Daily Compliance Report",
        replace_existing=True,
    )

    # Add DeadlineTracker-based deadline monitoring jobs
    add_deadline_tracker_jobs(_riverside_scheduler)

    # Weekly deadline review (Monday 9 AM) - legacy backup
    _riverside_scheduler.add_job(
        run_deadline_check,
        trigger=CronTrigger(day_of_week="mon", hour=9, minute=0),
        id="riverside_weekly_deadlines",
        name="Riverside Weekly Deadline Review",
        replace_existing=True,
    )

    # Weekly maturity regression check (Monday 10 AM)
    _riverside_scheduler.add_job(
        run_maturity_regression_check,
        trigger=CronTrigger(day_of_week="mon", hour=10, minute=0),
        id="riverside_weekly_maturity",
        name="Riverside Weekly Maturity Check",
        replace_existing=True,
    )

    # Weekly threat escalation check (Monday 11 AM)
    _riverside_scheduler.add_job(
        run_threat_escalation_check,
        trigger=CronTrigger(day_of_week="mon", hour=11, minute=0),
        id="riverside_weekly_threats",
        name="Riverside Weekly Threat Check",
        replace_existing=True,
    )

    logger.info("Riverside scheduler initialized with compliance monitoring jobs")
    return _riverside_scheduler


def get_riverside_scheduler() -> AsyncIOScheduler | None:
    """Get the Riverside scheduler instance.

    Returns:
        The scheduler instance or None if not initialized.
    """
    return _riverside_scheduler


async def trigger_manual_check(check_type: str) -> dict[str, Any]:
    """Trigger a manual compliance check."""
    check_functions = {
        "mfa": run_mfa_compliance_check,
        "deadlines": run_deadline_check,
        "maturity": run_maturity_regression_check,
        "threats": run_threat_escalation_check,
        "daily": run_daily_compliance_report,
    }

    if check_type not in check_functions:
        return {
            "success": False,
            "error": f"Unknown check type: {check_type}",
            "valid_types": list(check_functions.keys()),
        }

    return await check_functions[check_type]()


async def schedule_mfa_alert_checks(
    interval_minutes: int = 60,
    job_id: str = "mfa_gap_alerts",
) -> dict[str, Any]:
    """Schedule MFA gap alert checks using the Riverside scheduler."""
    return await schedule_mfa_alert_checks_on_scheduler(
        _riverside_scheduler,
        interval_minutes=interval_minutes,
        job_id=job_id,
    )


async def remove_mfa_alert_checks(job_id: str = "mfa_gap_alerts") -> dict[str, Any]:
    """Remove scheduled MFA gap alert checks."""
    return await remove_mfa_alert_checks_from_scheduler(_riverside_scheduler, job_id=job_id)

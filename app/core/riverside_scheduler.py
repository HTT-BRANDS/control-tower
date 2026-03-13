"""Riverside compliance monitoring scheduler for automated monitoring and alerting.

Uses APScheduler for scheduling compliance checks including MFA coverage,
requirement deadlines, maturity regressions, and threat escalations.
Integrates with the notification system for alerting.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.alerts.deadline_alerts import (
    AlertLevel,
    DeadlineAlert,
    DeadlineTracker,
)
from app.core.config import get_settings
from app.core.database import get_db_context
from app.core.notifications import (
    Notification,
    Severity,
    create_dashboard_url,
    record_notification_sent,
    send_notification,
    should_notify,
)
from app.models.riverside import (
    RequirementStatus,
    RiversideCompliance,
    RiversideMFA,
    RiversideRequirement,
    RiversideThreatData,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Global scheduler instance
_riverside_scheduler: AsyncIOScheduler | None = None

# Constants for compliance thresholds
MFA_USER_TARGET_PERCENTAGE = 95.0
MFA_ADMIN_TARGET_PERCENTAGE = 100.0
THREAT_SCORE_HIGH_THRESHOLD = 7.0
THREAT_SCORE_CRITICAL_THRESHOLD = 9.0

# Alert intervals for deadline tracking (days before deadline)
DEADLINE_ALERT_INTERVALS = [90, 60, 30, 14, 7, 1]


@dataclass
class MFAComplianceResult:
    """Result of MFA compliance check for a tenant."""

    tenant_id: str
    user_mfa_percentage: float
    admin_mfa_percentage: float
    user_target_met: bool
    admin_target_met: bool
    total_users: int
    mfa_enrolled_users: int
    admin_accounts_total: int
    admin_accounts_mfa: int


@dataclass
class MaturityRegression:
    """Detected maturity score regression for a tenant."""

    tenant_id: str
    previous_score: float
    current_score: float
    score_drop: float
    last_assessment_date: datetime | None


@dataclass
class ThreatEscalation:
    """Detected threat escalation for a tenant."""

    tenant_id: str
    threat_score: float
    vulnerability_count: int
    malicious_domain_alerts: int
    is_critical: bool
    snapshot_date: datetime


async def check_mfa_compliance(
    db: Session | None = None,
) -> list[MFAComplianceResult]:
    """Monitor MFA enrollment across tenants.

    Queries the riverside_mfa table for all tenants and checks if
    MFA coverage meets targets (95% for users, 100% for admins).

    Args:
        db: Optional database session. If not provided, a new session
            will be created using get_db_context().

    Returns:
        List of MFAComplianceResult for tenants below threshold.

    Raises:
        Exception: If database query fails.
    """
    results: list[MFAComplianceResult] = []

    try:
        if db is None:
            with get_db_context() as db_session:
                return await check_mfa_compliance(db_session)

        # Get the latest MFA snapshot for each tenant
        latest_snapshots = (
            db.query(
                RiversideMFA.tenant_id,
                func.max(RiversideMFA.snapshot_date).label("max_date"),
            )
            .group_by(RiversideMFA.tenant_id)
            .subquery()
        )

        mfa_records = (
            db.query(RiversideMFA)
            .join(
                latest_snapshots,
                (RiversideMFA.tenant_id == latest_snapshots.c.tenant_id)
                & (RiversideMFA.snapshot_date == latest_snapshots.c.max_date),
            )
            .all()
        )

        for record in mfa_records:
            user_target_met = record.mfa_coverage_percentage >= MFA_USER_TARGET_PERCENTAGE
            admin_target_met = record.admin_mfa_percentage >= MFA_ADMIN_TARGET_PERCENTAGE

            # Only include tenants below threshold
            if not user_target_met or not admin_target_met:
                result = MFAComplianceResult(
                    tenant_id=record.tenant_id,
                    user_mfa_percentage=record.mfa_coverage_percentage,
                    admin_mfa_percentage=record.admin_mfa_percentage,
                    user_target_met=user_target_met,
                    admin_target_met=admin_target_met,
                    total_users=record.total_users,
                    mfa_enrolled_users=record.mfa_enrolled_users,
                    admin_accounts_total=record.admin_accounts_total,
                    admin_accounts_mfa=record.admin_accounts_mfa,
                )
                results.append(result)

                logger.warning(
                    f"MFA compliance below threshold for tenant {record.tenant_id}: "
                    f"users={record.mfa_coverage_percentage:.1f}% "
                    f"(target={MFA_USER_TARGET_PERCENTAGE}%), "
                    f"admins={record.admin_mfa_percentage:.1f}% "
                    f"(target={MFA_ADMIN_TARGET_PERCENTAGE}%)"
                )

        logger.info(f"MFA compliance check completed: {len(results)} tenants below threshold")
        return results

    except Exception as e:
        logger.error(f"Error checking MFA compliance: {e}", exc_info=True)
        raise


async def check_requirement_deadlines(
    db: Session | None = None,
) -> tuple[list[DeadlineAlert], list[DeadlineAlert]]:
    """Track upcoming requirement due dates and overdue items.

    Queries the riverside_requirements table for incomplete requirements,
    calculates days until deadline, and generates alerts at configured
    intervals (90, 60, 30, 14, 7, 1 days before deadline).

    Args:
        db: Optional database session. If not provided, a new session
            will be created using get_db_context().

    Returns:
        Tuple of (overdue_alerts, approaching_deadline_alerts).

    Raises:
        Exception: If database query fails.
    """
    overdue: list[DeadlineAlert] = []
    approaching: list[DeadlineAlert] = []
    today = date.today()

    try:
        if db is None:
            with get_db_context() as db_session:
                return await check_requirement_deadlines(db_session)

        # Get incomplete requirements with due dates
        requirements = (
            db.query(RiversideRequirement)
            .filter(
                RiversideRequirement.status != RequirementStatus.COMPLETED.value,
                RiversideRequirement.due_date.isnot(None),
            )
            .all()
        )

        for req in requirements:
            if req.due_date is None:
                continue

            days_until = (req.due_date - today).days

            if days_until < 0:
                # Overdue
                alert = DeadlineAlert(
                    requirement_id=req.requirement_id,
                    tenant_id=req.tenant_id,
                    title=req.title,
                    days_until_deadline=days_until,
                    alert_level=AlertLevel.CRITICAL,
                    is_overdue=True,
                    alert_stage=None,
                )
                overdue.append(alert)
                logger.warning(
                    f"Overdue requirement: {req.requirement_id} for tenant "
                    f"{req.tenant_id} ({abs(days_until)} days overdue)"
                )
            elif days_until in DEADLINE_ALERT_INTERVALS:
                # Approaching deadline at alert interval
                # Map days to alert level
                if days_until == 90:
                    alert_level = AlertLevel.INFO
                elif days_until == 60:
                    alert_level = AlertLevel.WARNING
                elif days_until == 30:
                    alert_level = AlertLevel.HIGH
                else:  # 14, 7, 1
                    alert_level = AlertLevel.CRITICAL
                alert = DeadlineAlert(
                    requirement_id=req.requirement_id,
                    tenant_id=req.tenant_id,
                    title=req.title,
                    days_until_deadline=days_until,
                    alert_level=alert_level,
                    is_overdue=False,
                    alert_stage=days_until,
                )
                approaching.append(alert)
                logger.info(
                    f"Deadline approaching: {req.requirement_id} for tenant "
                    f"{req.tenant_id} ({days_until} days remaining)"
                )

        logger.info(
            f"Deadline check completed: {len(overdue)} overdue, {len(approaching)} approaching"
        )
        return overdue, approaching

    except Exception as e:
        logger.error(f"Error checking requirement deadlines: {e}", exc_info=True)
        raise


async def check_maturity_regressions(
    db: Session | None = None,
) -> list[MaturityRegression]:
    """Detect maturity score drops across tenants.

    Compares current vs previous maturity scores from riverside_compliance
    to detect any decreases in compliance maturity.

    Args:
        db: Optional database session. If not provided, a new session
            will be created using get_db_context().

    Returns:
        List of MaturityRegression for tenants with score drops.

    Raises:
        Exception: If database query fails.
    """
    regressions: list[MaturityRegression] = []

    try:
        if db is None:
            with get_db_context() as db_session:
                return await check_maturity_regressions(db_session)

        # Get all compliance records ordered by tenant and date
        compliance_records = (
            db.query(RiversideCompliance)
            .order_by(
                RiversideCompliance.tenant_id,
                RiversideCompliance.last_assessment_date.desc(),
            )
            .all()
        )

        # Group by tenant and compare latest with previous
        tenant_records: dict[str, list[RiversideCompliance]] = {}
        for record in compliance_records:
            if record.tenant_id not in tenant_records:
                tenant_records[record.tenant_id] = []
            tenant_records[record.tenant_id].append(record)

        for tenant_id, records in tenant_records.items():
            if len(records) >= 2:
                current = records[0]
                previous = records[1]

                if current.overall_maturity_score < previous.overall_maturity_score:
                    score_drop = previous.overall_maturity_score - current.overall_maturity_score
                    regression = MaturityRegression(
                        tenant_id=tenant_id,
                        previous_score=previous.overall_maturity_score,
                        current_score=current.overall_maturity_score,
                        score_drop=score_drop,
                        last_assessment_date=current.last_assessment_date,
                    )
                    regressions.append(regression)
                    logger.warning(
                        f"Maturity regression detected for tenant {tenant_id}: "
                        f"dropped from {previous.overall_maturity_score:.1f} to "
                        f"{current.overall_maturity_score:.1f} (-{score_drop:.1f})"
                    )

        logger.info(f"Maturity regression check completed: {len(regressions)} regressions detected")
        return regressions

    except Exception as e:
        logger.error(f"Error checking maturity regressions: {e}", exc_info=True)
        raise


async def check_threat_escalations(
    db: Session | None = None,
    previous_check_time: datetime | None = None,
) -> list[ThreatEscalation]:
    """Monitor threat level changes and detect new high/critical threats.

    Queries riverside_threat_data for high threat scores and detects
    new high/critical threats since the last check.

    Args:
        db: Optional database session. If not provided, a new session
            will be created using get_db_context().
        previous_check_time: Optional datetime of last check to identify
            new threats. If None, considers all high threats.

    Returns:
        List of ThreatEscalation for high/critical threats.

    Raises:
        Exception: If database query fails.
    """
    escalations: list[ThreatEscalation] = []

    try:
        if db is None:
            with get_db_context() as db_session:
                return await check_threat_escalations(db_session, previous_check_time)

        # Get the latest threat snapshot for each tenant
        latest_snapshots = (
            db.query(
                RiversideThreatData.tenant_id,
                func.max(RiversideThreatData.snapshot_date).label("max_date"),
            )
            .group_by(RiversideThreatData.tenant_id)
            .subquery()
        )

        # Query for high threat scores
        threat_query = (
            db.query(RiversideThreatData)
            .join(
                latest_snapshots,
                (RiversideThreatData.tenant_id == latest_snapshots.c.tenant_id)
                & (RiversideThreatData.snapshot_date == latest_snapshots.c.max_date),
            )
            .filter(RiversideThreatData.threat_score >= THREAT_SCORE_HIGH_THRESHOLD)
        )

        # If previous check time provided, only get new records
        if previous_check_time:
            threat_query = threat_query.filter(
                RiversideThreatData.snapshot_date > previous_check_time
            )

        threat_records = threat_query.all()

        for record in threat_records:
            if record.threat_score is None:
                continue
            is_critical = record.threat_score >= THREAT_SCORE_CRITICAL_THRESHOLD
            escalation = ThreatEscalation(
                tenant_id=record.tenant_id,
                threat_score=record.threat_score,
                vulnerability_count=record.vulnerability_count,
                malicious_domain_alerts=record.malicious_domain_alerts,
                is_critical=is_critical,
                snapshot_date=record.snapshot_date,
            )
            escalations.append(escalation)

            severity_str = "CRITICAL" if is_critical else "HIGH"
            logger.warning(
                f"Threat escalation detected for tenant {record.tenant_id}: "
                f"{severity_str} threat score {record.threat_score:.1f}, "
                f"{record.vulnerability_count} vulnerabilities, "
                f"{record.malicious_domain_alerts} malicious domain alerts"
            )

        logger.info(f"Threat escalation check completed: {len(escalations)} escalations detected")
        return escalations

    except Exception as e:
        logger.error(f"Error checking threat escalations: {e}", exc_info=True)
        raise


async def send_mfa_compliance_alerts(
    non_compliant: list[MFAComplianceResult],
) -> list[dict[str, Any]]:
    """Send notifications for MFA compliance violations.

    Args:
        non_compliant: List of MFA compliance violations.

    Returns:
        List of notification results.
    """
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
    """Send notifications for requirement deadline alerts.

    Args:
        overdue: List of overdue requirement alerts.
        approaching: List of approaching deadline alerts.

    Returns:
        List of notification results.
    """
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
    """Send notifications for maturity score regressions.

    Args:
        regressions: List of maturity regressions.

    Returns:
        List of notification results.
    """
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
    """Send notifications for threat escalations.

    Args:
        escalations: List of threat escalations.

    Returns:
        List of notification results.
    """
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
    """Run MFA compliance check and send alerts.

    This is the scheduled job wrapper for MFA compliance monitoring.

    Returns:
        Dict with check results and notification status.
    """
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
    """Run requirement deadline check and send alerts.

    This is the scheduled job wrapper for deadline monitoring.

    Returns:
        Dict with check results and notification status.
    """
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
    """Run maturity regression check and send alerts.

    This is the scheduled job wrapper for maturity monitoring.

    Returns:
        Dict with check results and notification status.
    """
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
    """Run threat escalation check and send alerts.

    This is the scheduled job wrapper for threat monitoring.

    Returns:
        Dict with check results and notification status.
    """
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
    """Generate daily compliance report with all checks.

    This is the main daily job that runs all compliance checks.

    Returns:
        Dict with all check results.
    """
    logger.info("Starting daily compliance report")

    mfa_result = await run_mfa_compliance_check()
    deadline_result = await run_deadline_check()
    maturity_result = await run_maturity_regression_check()
    threat_result = await run_threat_escalation_check()

    results: dict[str, Any] = {
        "timestamp": datetime.utcnow().isoformat(),
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
    """Initialize and configure the Riverside compliance scheduler.

    Sets up scheduled jobs for:
    - Hourly MFA compliance checks
    - Daily compliance reports (8 AM)
    - Daily deadline tracking with DeadlineTracker (9 AM, 2 PM)
    - Weekly deadline reviews (Monday 9 AM)
    - Weekly maturity and threat checks

    Returns:
        Configured AsyncIOScheduler instance.
    """
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
    """Trigger a manual compliance check.

    Args:
        check_type: Type of check to run. One of:
            - 'mfa': MFA compliance check
            - 'deadlines': Deadline check
            - 'maturity': Maturity regression check
            - 'threats': Threat escalation check
            - 'daily': Full daily report

    Returns:
        Dict with check results.
    """
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
    """Schedule MFA gap alert checks using the Riverside scheduler.

    Creates a scheduled job that runs MFA gap detection and alerting
    at the specified interval. Integrates with the existing notification
    system from #ryi.

    Args:
        interval_minutes: Interval between checks in minutes. Default 60.
        job_id: Unique identifier for the scheduled job.

    Returns:
        Dict with job configuration details.

    Raises:
        RuntimeError: If scheduler is not initialized.
    """
    global _riverside_scheduler

    if _riverside_scheduler is None:
        raise RuntimeError(
            "Riverside scheduler not initialized. Call init_riverside_scheduler() first."
        )

    # Import here to avoid circular dependencies
    from app.alerts.mfa_alerts import MFAGapDetector

    async def _mfa_alert_job() -> dict[str, Any]:
        """Scheduled job wrapper for MFA alerts."""
        logger.info(f"Running scheduled MFA alert check (job_id: {job_id})")
        detector = MFAGapDetector()
        return await detector.check_and_alert()

    # Add job to scheduler
    _riverside_scheduler.add_job(
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
        "scheduler_active": _riverside_scheduler.state == "started"
        if hasattr(_riverside_scheduler, "state")
        else True,
    }


async def remove_mfa_alert_checks(job_id: str = "mfa_gap_alerts") -> dict[str, Any]:
    """Remove scheduled MFA gap alert checks.

    Args:
        job_id: The job ID to remove. Default 'mfa_gap_alerts'.

    Returns:
        Dict with removal status.
    """
    global _riverside_scheduler

    if _riverside_scheduler is None:
        return {
            "success": False,
            "error": "Scheduler not initialized",
        }

    try:
        _riverside_scheduler.remove_job(job_id)
        logger.info(f"Removed MFA alert checks job: {job_id}")
        return {
            "success": True,
            "job_id": job_id,
            "message": "Job removed successfully",
        }
    except Exception as e:
        logger.warning(f"Could not remove MFA alert job {job_id}: {e}")
        return {
            "success": False,
            "job_id": job_id,
            "error": str(e),
        }


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

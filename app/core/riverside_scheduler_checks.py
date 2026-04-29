"""Database-backed Riverside compliance check implementations."""

import logging
from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.alerts.deadline_alerts import AlertLevel, DeadlineAlert
from app.core.database import get_db_context
from app.core.riverside_scheduler_models import (
    DEADLINE_ALERT_INTERVALS,
    MFA_ADMIN_TARGET_PERCENTAGE,
    MFA_USER_TARGET_PERCENTAGE,
    THREAT_SCORE_CRITICAL_THRESHOLD,
    THREAT_SCORE_HIGH_THRESHOLD,
    MaturityRegression,
    MFAComplianceResult,
    ThreatEscalation,
)
from app.models.riverside import (
    RequirementStatus,
    RiversideCompliance,
    RiversideMFA,
    RiversideRequirement,
    RiversideThreatData,
)

logger = logging.getLogger(__name__)


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

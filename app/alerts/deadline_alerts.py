"""Deadline tracking alert system for Riverside compliance requirements.

Provides automated deadline monitoring with escalating alert levels:
- INFO: 90 days before deadline
- WARNING: 60 days before deadline
- HIGH: 30 days before deadline
- CRITICAL: 14, 7, 1 days before deadline and overdue

Integrates with the notification system and queries riverside_requirements
to track requirement statuses across tenants.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy.orm import Session

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
from app.models.riverside import RequirementStatus, RiversideRequirement

logger = logging.getLogger(__name__)
settings = get_settings()


class AlertLevel(StrEnum):
    """Alert severity levels for deadline tracking.

    Escalating levels based on days until deadline:
    - INFO: Early warning (90 days)
    - WARNING: Approaching deadline (60 days)
    - HIGH: Near deadline (30 days)
    - CRITICAL: Imminent/overdue (14, 7, 1 days, overdue)
    """
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


# Alert schedule mapping days before deadline to alert level
ALERT_SCHEDULE: dict[int, AlertLevel] = {
    90: AlertLevel.INFO,
    60: AlertLevel.WARNING,
    30: AlertLevel.HIGH,
    14: AlertLevel.CRITICAL,
    7: AlertLevel.CRITICAL,
    1: AlertLevel.CRITICAL,
}

# Map AlertLevel to notification Severity
ALERT_TO_SEVERITY: dict[AlertLevel, Severity] = {
    AlertLevel.INFO: Severity.INFO,
    AlertLevel.WARNING: Severity.WARNING,
    AlertLevel.HIGH: Severity.ERROR,
    AlertLevel.CRITICAL: Severity.CRITICAL,
}

# Default deadline for July 8, 2026 compliance
DEFAULT_DEADLINE = date(2026, 7, 8)


@dataclass
class DeadlineAlert:
    """Alert for an approaching or overdue requirement deadline.

    Attributes:
        requirement_id: Unique identifier for the requirement
        tenant_id: Tenant identifier
        title: Human-readable requirement title
        days_until_deadline: Number of days until/since deadline (negative = overdue)
        alert_level: Severity level of the alert
        is_overdue: True if deadline has passed
        alert_stage: Which threshold triggered this alert (90, 60, 30, 14, 7, 1)
        status: Current requirement status
    """
    requirement_id: str
    tenant_id: str
    title: str
    days_until_deadline: int
    alert_level: AlertLevel
    is_overdue: bool
    alert_stage: int | None
    status: RequirementStatus = field(default=RequirementStatus.NOT_STARTED)


@dataclass
class DeadlineTrackingResult:
    """Result of deadline tracking check.

    Attributes:
        alerts: List of deadline alerts generated
        info_count: Number of INFO level alerts
        warning_count: Number of WARNING level alerts
        high_count: Number of HIGH level alerts
        critical_count: Number of CRITICAL level alerts
        overdue_count: Number of overdue items
        checked_at: Timestamp when check was performed
    """
    alerts: list[DeadlineAlert] = field(default_factory=list)
    info_count: int = 0
    warning_count: int = 0
    high_count: int = 0
    critical_count: int = 0
    overdue_count: int = 0
    checked_at: datetime = field(default_factory=datetime.utcnow)


class DeadlineTracker:
    """Tracks Riverside compliance requirement deadlines and generates alerts.

    Monitors requirements across tenants and generates escalating alerts as
    deadlines approach. Supports configurable deadline dates and alert
    schedules with notification integration.

    Example:
        >>> tracker = DeadlineTracker()
        >>> result = await tracker.track_requirement_deadlines()
        >>> print(f"Found {len(result.alerts)} deadline alerts")
    """

    def __init__(
        self,
        target_deadline: date | None = None,
        alert_schedule: dict[int, AlertLevel] | None = None,
    ):
        """Initialize deadline tracker.

        Args:
            target_deadline: Target deadline date (defaults to July 8, 2026)
            alert_schedule: Custom alert schedule mapping days to alert levels
        """
        self.target_deadline = target_deadline or DEFAULT_DEADLINE
        self.alert_schedule = alert_schedule or ALERT_SCHEDULE.copy()
        self._logger = logging.getLogger(f"{__name__}.DeadlineTracker")

    async def track_requirement_deadlines(
        self,
        db: Session | None = None,
    ) -> DeadlineTrackingResult:
        """Query riverside_requirements and track deadlines.

        Queries incomplete requirements with due dates and generates
        alerts based on days until deadline using the configured
        alert schedule.

        Args:
            db: Optional database session. If not provided, a new session
                will be created using get_db_context().

        Returns:
            DeadlineTrackingResult containing all generated alerts.

        Raises:
            Exception: If database query fails.
        """
        result = DeadlineTrackingResult()
        today = date.today()

        try:
            if db is None:
                with get_db_context() as db_session:
                    return await self.track_requirement_deadlines(db_session)

            # Get incomplete requirements with due dates
            requirements = (
                db.query(RiversideRequirement)
                .filter(
                    RiversideRequirement.status.in_([
                        RequirementStatus.NOT_STARTED,
                        RequirementStatus.IN_PROGRESS,
                    ]),
                    RiversideRequirement.due_date.isnot(None),
                )
                .all()
            )

            self._logger.info(
                f"Checking {len(requirements)} incomplete requirements for deadline alerts"
            )

            for req in requirements:
                if req.due_date is None:
                    continue

                alert = self._evaluate_requirement(req, today)
                if alert:
                    result.alerts.append(alert)
                    self._update_counts(result, alert)

            self._logger.info(
                f"Deadline check complete: {result.info_count} INFO, "
                f"{result.warning_count} WARNING, {result.high_count} HIGH, "
                f"{result.critical_count} CRITICAL, {result.overdue_count} OVERDUE"
            )

            return result

        except Exception as e:
            self._logger.error(f"Error tracking requirement deadlines: {e}", exc_info=True)
            raise

    def _evaluate_requirement(
        self,
        req: RiversideRequirement,
        today: date,
    ) -> DeadlineAlert | None:
        """Evaluate a single requirement for deadline alerts.

        Args:
            req: The requirement to evaluate
            today: Current date for comparison

        Returns:
            DeadlineAlert if an alert should be generated, None otherwise
        """
        if req.due_date is None:
            return None

        days_until = (req.due_date - today).days

        # Check for overdue
        if days_until < 0:
            return DeadlineAlert(
                requirement_id=req.requirement_id,
                tenant_id=req.tenant_id,
                title=req.title,
                days_until_deadline=days_until,
                alert_level=AlertLevel.CRITICAL,
                is_overdue=True,
                alert_stage=None,
                status=req.status,
            )

        # Check if current days_until matches an alert threshold
        if days_until in self.alert_schedule:
            return DeadlineAlert(
                requirement_id=req.requirement_id,
                tenant_id=req.tenant_id,
                title=req.title,
                days_until_deadline=days_until,
                alert_level=self.alert_schedule[days_until],
                is_overdue=False,
                alert_stage=days_until,
                status=req.status,
            )

        return None

    def _update_counts(self, result: DeadlineTrackingResult, alert: DeadlineAlert) -> None:
        """Update alert counts based on alert level.

        Args:
            result: Result object to update
            alert: Alert that was generated
        """
        if alert.is_overdue:
            result.overdue_count += 1
            result.critical_count += 1
        elif alert.alert_level == AlertLevel.INFO:
            result.info_count += 1
        elif alert.alert_level == AlertLevel.WARNING:
            result.warning_count += 1
        elif alert.alert_level == AlertLevel.HIGH:
            result.high_count += 1
        elif alert.alert_level == AlertLevel.CRITICAL:
            result.critical_count += 1

    def calculate_deadline_warnings(
        self,
        requirements: list[RiversideRequirement],
        today: date | None = None,
    ) -> list[DeadlineAlert]:
        """Calculate WARNING level alerts (60 days) for requirements.

        Filters requirements that are at the warning threshold.

        Args:
            requirements: List of requirements to check
            today: Optional date to use (defaults to today)

        Returns:
            List of WARNING level deadline alerts
        """
        today = today or date.today()
        warnings: list[DeadlineAlert] = []

        for req in requirements:
            if req.due_date is None:
                continue

            days_until = (req.due_date - today).days
            if days_until == 60:  # WARNING threshold
                warnings.append(DeadlineAlert(
                    requirement_id=req.requirement_id,
                    tenant_id=req.tenant_id,
                    title=req.title,
                    days_until_deadline=days_until,
                    alert_level=AlertLevel.WARNING,
                    is_overdue=False,
                    alert_stage=60,
                    status=req.status,
                ))

        return warnings

    def calculate_critical_alerts(
        self,
        requirements: list[RiversideRequirement],
        today: date | None = None,
    ) -> list[DeadlineAlert]:
        """Calculate CRITICAL level alerts (14, 7, 1 days, overdue) for requirements.

        Args:
            requirements: List of requirements to check
            today: Optional date to use (defaults to today)

        Returns:
            List of CRITICAL level deadline alerts
        """
        today = today or date.today()
        critical: list[DeadlineAlert] = []
        critical_days = {14, 7, 1}

        for req in requirements:
            if req.due_date is None:
                continue

            days_until = (req.due_date - today).days

            # Check for overdue
            if days_until < 0:
                critical.append(DeadlineAlert(
                    requirement_id=req.requirement_id,
                    tenant_id=req.tenant_id,
                    title=req.title,
                    days_until_deadline=days_until,
                    alert_level=AlertLevel.CRITICAL,
                    is_overdue=True,
                    alert_stage=None,
                    status=req.status,
                ))
            # Check critical thresholds
            elif days_until in critical_days:
                critical.append(DeadlineAlert(
                    requirement_id=req.requirement_id,
                    tenant_id=req.tenant_id,
                    title=req.title,
                    days_until_deadline=days_until,
                    alert_level=AlertLevel.CRITICAL,
                    is_overdue=False,
                    alert_stage=days_until,
                    status=req.status,
                ))

        return critical

    async def trigger_deadline_alert(
        self,
        alert: DeadlineAlert,
    ) -> dict[str, Any]:
        """Send deadline notification for a single alert.

        Creates and sends a notification for the given deadline alert,
        respecting deduplication rules.

        Args:
            alert: The deadline alert to notify about

        Returns:
            Dict with notification result details
        """
        alert_key = self._build_alert_key(alert)

        if not should_notify(alert_key, job_type="riverside_deadlines"):
            self._logger.debug(f"Skipping notification for {alert_key}: in cooldown")
            return {
                "success": False,
                "error": "In cooldown period",
                "alert_key": alert_key,
            }

        severity = ALERT_TO_SEVERITY.get(alert.alert_level, Severity.WARNING)

        # Build message based on alert type
        if alert.is_overdue:
            message = (
                f"Requirement '{alert.title}' ({alert.requirement_id}) is "
                f"{abs(alert.days_until_deadline)} days OVERDUE for tenant "
                f"{alert.tenant_id}.\n\n"
                f"Status: {alert.status.value}\n"
                f"Immediate action required to meet compliance obligations."
            )
        else:
            message = (
                f"Requirement '{alert.title}' ({alert.requirement_id}) is due in "
                f"{alert.days_until_deadline} days for tenant {alert.tenant_id}.\n\n"
                f"Status: {alert.status.value}\n"
                f"Target deadline: {self.target_deadline.isoformat()}"
            )

        notification = Notification(
            title=f"Deadline {alert.alert_level.upper()}: {alert.requirement_id}",
            message=message,
            severity=severity,
            job_type="riverside_deadlines",
            tenant_id=alert.tenant_id,
            dashboard_url=create_dashboard_url("riverside"),
        )

        try:
            result = await send_notification(notification)

            if result.get("success"):
                record_notification_sent(alert_key, job_type="riverside_deadlines")
                self._logger.info(
                    f"Sent {alert.alert_level} deadline alert for {alert.requirement_id}"
                )
            else:
                self._logger.warning(
                    f"Failed to send deadline alert for {alert.requirement_id}: "
                    f"{result.get('error')}"
                )

            return result

        except Exception as e:
            self._logger.error(
                f"Exception sending deadline alert for {alert.requirement_id}: {e}",
                exc_info=True
            )
            return {
                "success": False,
                "error": str(e),
                "alert_key": alert_key,
            }

    async def send_deadline_notifications(
        self,
        alerts: list[DeadlineAlert],
    ) -> list[dict[str, Any]]:
        """Send notifications for multiple deadline alerts.

        Args:
            alerts: List of deadline alerts to notify about

        Returns:
            List of notification results
        """
        results: list[dict[str, Any]] = []

        for alert in alerts:
            result = await self.trigger_deadline_alert(alert)
            results.append(result)

        self._logger.info(
            f"Sent {len([r for r in results if r.get('success')])} deadline notifications "
            f"out of {len(alerts)} alerts"
        )

        return results

    def _build_alert_key(self, alert: DeadlineAlert) -> str:
        """Build unique key for alert deduplication.

        Args:
            alert: The alert to build key for

        Returns:
            Unique alert key string
        """
        if alert.is_overdue:
            return f"deadline_overdue_{alert.requirement_id}_{alert.tenant_id}"
        elif alert.alert_stage:
            return f"deadline_{alert.alert_stage}d_{alert.requirement_id}_{alert.tenant_id}"
        else:
            return f"deadline_{alert.alert_level}_{alert.requirement_id}_{alert.tenant_id}"


async def check_deadlines_with_tracker(
    db: Session | None = None,
) -> DeadlineTrackingResult:
    """Convenience function to check deadlines using DeadlineTracker.

    Args:
        db: Optional database session

    Returns:
        DeadlineTrackingResult with all alerts
    """
    tracker = DeadlineTracker()
    return await tracker.track_requirement_deadlines(db)


async def send_deadline_alerts_from_tracker(
    alerts: list[DeadlineAlert],
) -> list[dict[str, Any]]:
    """Convenience function to send alerts using DeadlineTracker.

    Args:
        alerts: List of alerts to send

    Returns:
        List of notification results
    """
    tracker = DeadlineTracker()
    return await tracker.send_deadline_notifications(alerts)


async def track_requirement_deadlines(
    db: Session | None = None,
) -> DeadlineTrackingResult:
    """Convenience function to track deadlines.

    Args:
        db: Optional database session

    Returns:
        DeadlineTrackingResult with all alerts
    """
    tracker = DeadlineTracker()
    return await tracker.track_requirement_deadlines(db)


async def trigger_deadline_alert(
    alert: DeadlineAlert,
) -> dict[str, Any]:
    """Convenience function to trigger a single deadline alert.

    Args:
        alert: The deadline alert to trigger

    Returns:
        Notification result dict
    """
    tracker = DeadlineTracker()
    return await tracker.trigger_deadline_alert(alert)


def calculate_deadline_warnings(
    requirements: list[RiversideRequirement],
    today: date | None = None,
) -> list[DeadlineAlert]:
    """Convenience function to calculate warning alerts.

    Args:
        requirements: List of requirements to check
        today: Optional date (defaults to today)

    Returns:
        List of WARNING level deadline alerts
    """
    tracker = DeadlineTracker()
    return tracker.calculate_deadline_warnings(requirements, today)


def calculate_critical_alerts(
    requirements: list[RiversideRequirement],
    today: date | None = None,
) -> list[DeadlineAlert]:
    """Convenience function to calculate critical alerts.

    Args:
        requirements: List of requirements to check
        today: Optional date (defaults to today)

    Returns:
        List of CRITICAL level deadline alerts
    """
    tracker = DeadlineTracker()
    return tracker.calculate_critical_alerts(requirements, today)

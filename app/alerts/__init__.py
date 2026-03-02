"""Alert system for Azure Governance Platform.

Provides deadline tracking and compliance alerting for Riverside
requirements with escalating alert levels.
"""

from app.alerts.deadline_alerts import (
    ALERT_SCHEDULE,
    ALERT_TO_SEVERITY,
    AlertLevel,
    DeadlineAlert,
    DeadlineTracker,
    DeadlineTrackingResult,
    calculate_deadline_warnings,
    calculate_critical_alerts,
    check_deadlines_with_tracker,
    send_deadline_alerts_from_tracker,
    trigger_deadline_alert,
    track_requirement_deadlines,
)

__all__ = [
    # Enums
    "AlertLevel",
    # Dataclasses
    "DeadlineAlert",
    "DeadlineTrackingResult",
    # Main class
    "DeadlineTracker",
    # Constants
    "ALERT_SCHEDULE",
    "ALERT_TO_SEVERITY",
    # Functions
    "calculate_deadline_warnings",
    "calculate_critical_alerts",
    "check_deadlines_with_tracker",
    "send_deadline_alerts_from_tracker",
    "trigger_deadline_alert",
    "track_requirement_deadlines",
]

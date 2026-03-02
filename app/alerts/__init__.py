"""Alert system for Azure Governance Platform.

Provides MFA gap detection and deadline tracking for compliance alerting
across Riverside tenants.
"""

# MFA Alerts
from app.alerts.mfa_alerts import (
    MFAGapDetector,
    MFAComplianceStatus,
    detect_mfa_gaps,
    check_admin_mfa_compliance,
    check_user_mfa_compliance,
    trigger_mfa_alert,
)

# Deadline Alerts
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
    # MFA Alert exports
    "MFAGapDetector",
    "MFAComplianceStatus",
    "detect_mfa_gaps",
    "check_admin_mfa_compliance",
    "check_user_mfa_compliance",
    "trigger_mfa_alert",
    # Deadline Alert exports
    "AlertLevel",
    "DeadlineAlert",
    "DeadlineTracker",
    "DeadlineTrackingResult",
    "ALERT_SCHEDULE",
    "ALERT_TO_SEVERITY",
    "calculate_deadline_warnings",
    "calculate_critical_alerts",
    "check_deadlines_with_tracker",
    "send_deadline_alerts_from_tracker",
    "trigger_deadline_alert",
    "track_requirement_deadlines",
]

"""MFA Alert module for detecting and notifying on MFA enrollment gaps.

Provides the MFAGapDetector class and related utilities for monitoring
MFA compliance across Riverside tenants.
"""

from app.alerts.mfa_alerts import (
    MFAGapDetector,
    MFAComplianceStatus,
    detect_mfa_gaps,
    check_admin_mfa_compliance,
    check_user_mfa_compliance,
    trigger_mfa_alert,
)

__all__ = [
    "MFAGapDetector",
    "MFAComplianceStatus",
    "detect_mfa_gaps",
    "check_admin_mfa_compliance",
    "check_user_mfa_compliance",
    "trigger_mfa_alert",
]

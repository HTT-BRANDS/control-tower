"""Riverside scheduler DTOs and threshold constants."""

from dataclasses import dataclass
from datetime import datetime

MFA_USER_TARGET_PERCENTAGE = 95.0
MFA_ADMIN_TARGET_PERCENTAGE = 100.0
THREAT_SCORE_HIGH_THRESHOLD = 7.0
THREAT_SCORE_CRITICAL_THRESHOLD = 9.0
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

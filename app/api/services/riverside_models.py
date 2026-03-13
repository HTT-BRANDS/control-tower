"""
Riverside governance models for Microsoft 365 security posture.

This module contains all data models, enums, and constants for the Riverside
compliance framework focused on 72 security requirements across MFA,
conditional access, privileged identity, device compliance, and threat management.
"""

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


# Enums


class RequirementLevel(Enum):
    """Maturity levels for security requirements."""

    EMERGING = "Emerging"
    DEVELOPING = "Developing"
    MATURE = "Mature"
    LEADING = "Leading"


class MFAStatus(Enum):
    """MFA enforcement status for users."""

    ENFORCED = "Enforced"
    AVAILABLE = "Available"
    PENDING = "Pending"
    NOT_CONFIGURED = "Not Configured"


class RequirementStatus(Enum):
    """Implementation status of security requirements."""

    NOT_STARTED = "Not Started"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    AT_RISK = "At Risk"


class DeadlinePhase(Enum):
    """Implementation phases for Riverside requirements."""

    PHASE_1_Q3_2025 = "Phase 1: Q3 2025"
    PHASE_2_Q4_2025 = "Phase 2: Q4 2025"
    PHASE_3_Q1_2026 = "Phase 3: Q1 2026"


class RiversideRequirementCategory(Enum):
    """Categories of Riverside security requirements."""

    MFA_ENFORCEMENT = "MFA Enforcement"
    CONDITIONAL_ACCESS = "Conditional Access"
    PRIVILEGED_ACCESS = "Privileged Access"
    DEVICE_COMPLIANCE = "Device Compliance"
    THREAT_MANAGEMENT = "Threat Management"
    DATA_LOSS_PREVENTION = "Data Loss Prevention"
    LOGGING_MONITORING = "Logging & Monitoring"
    INCIDENT_RESPONSE = "Incident Response"


# Data Models


@dataclass
class RiversideRequirement:
    """Individual Riverside security requirement."""

    id: str
    category: RiversideRequirementCategory
    title: str
    description: str
    control_source: str
    control_reference: str
    maturity_level: RequirementLevel
    phase: DeadlinePhase
    target_date: date | None
    status: RequirementStatus = RequirementStatus.NOT_STARTED
    evidence_count: int = 0
    approval_status: str | None = None


@dataclass
class TenantRequirementTracker:
    """Tracks requirement status per tenant."""

    tenant_id: str
    tenant_name: str
    requirement: RiversideRequirement
    status: RequirementStatus
    evidence_submitted: int = 0
    last_updated: datetime | None = None
    compliance_notes: str | None = None


@dataclass
class RiversideComplianceSummary:
    """Overall compliance summary across all tenants."""

    overall_compliance_pct: float
    target_compliance_pct: float
    completed_requirements_count: int
    total_requirements_count: int


@dataclass
class MFAMaturityScore:
    """MFA maturity metrics."""

    overall_maturity: RequirementLevel
    enrollment_rate_pct: float
    admin_enforcement_pct: float
    privileged_user_enrollment_pct: float
    gap_count: int


@dataclass
class RiversideThreatMetrics:
    """Security threat metrics and trends."""

    phishing_attempts_30d: int
    malware_detected_30d: int
    spam_filtered_30d: int
    risk_score: float
    trend_direction: str


@dataclass
class TenantRiversideSummary:
    """Compliance summary for individual tenant."""

    tenant_id: str
    tenant_name: str
    overall_compliance_pct: float
    phase_1_completion_pct: float
    phase_2_completion_pct: float
    phase_3_completion_pct: float
    mfa_maturity: MFAMaturityScore
    threat_metrics: RiversideThreatMetrics
    critical_issues_count: int


@dataclass
class RiversideExecutiveSummary:
    """Executive-level summary across all tenants."""

    overall_compliance_pct: float
    phases_complete: list[str]
    completion_by_tenant: list[TenantRiversideSummary]
    mfa_maturity: MFAMaturityScore
    key_gaps: list[str]
    critical_alerts: list[str]
    last_updated: datetime


@dataclass
class AggregateMFAStatus:
    """Aggregated MFA status across environment."""

    total_users: int
    mfa_enforced_users: int
    mfa_available_users: int
    mfa_pending_users: int
    mfa_not_configured_users: int
    enforced_rate_pct: float
    admin_mfa_status: dict[str, MFAStatus]


# Constants


PHASE_1_TARGET_DATE = date(2025, 9, 30)
PHASE_2_TARGET_DATE = date(2025, 12, 31)
PHASE_3_TARGET_DATE = date(2026, 3, 31)

MFA_THRESHOLD_PERCENTAGES = {
    "Emerging": 25,
    "Developing": 50,
    "Mature": 75,
    "Leading": 95,
}


TENANTS: dict[str, str] = {
    "htt": "Health Technology Trust",
    "bcc": "Bio-Care Corporation",
    "fn": "Future Nations",
    "tll": "Tech Lab Logistics",
    "dce": "Digital Cloud Enterprises",
}

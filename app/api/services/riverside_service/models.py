"""Riverside Service - Data models and dataclasses."""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import TYPE_CHECKING

from app.api.services.riverside_service.constants import (
    DeadlinePhase,
    MFAStatus,
    RequirementLevel,
    RequirementStatus,
    RiversideRequirementCategory,
)

if TYPE_CHECKING:
    pass


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
    status: RequirementStatus = field(default=RequirementStatus.NOT_STARTED)
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
    admin_mfa_status: dict[str, "MFAStatus"] = field(default_factory=dict)


@dataclass
class GapAnalysis:
    """Individual gap analysis result."""

    requirement_id: str
    title: str
    category: str
    priority: str
    status: str
    tenant_id: str
    tenant_code: str
    due_date: str | None
    is_overdue: bool
    days_overdue: int
    risk_level: str
    description: str


@dataclass
class TenantMFAStatus:
    """MFA status for a single tenant."""

    tenant_id: str
    tenant_code: str
    tenant_name: str
    total_users: int
    mfa_enrolled: int
    mfa_coverage_pct: float
    admin_accounts: int
    admin_mfa: int
    admin_mfa_pct: float
    unprotected_users: int
    snapshot_date: str | None


@dataclass
class TenantMaturityScore:
    """Maturity scores for a single tenant."""

    tenant_id: str
    tenant_code: str
    tenant_name: str
    overall_maturity: float
    target_maturity: float
    domain_scores: dict[str, float]
    critical_gaps: int
    last_assessment: str | None


@dataclass
class RequirementListItem:
    """Requirement item for list views."""

    id: int
    requirement_id: str
    title: str
    description: str
    category: str
    priority: str
    status: str
    tenant_id: str
    tenant_code: str
    due_date: str | None
    completed_date: str | None
    owner: str
    evidence_url: str | None
    evidence_notes: str | None
    created_at: str | None
    updated_at: str | None

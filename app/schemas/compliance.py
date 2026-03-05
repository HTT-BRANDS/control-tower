"""Compliance-related Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class ComplianceScore(BaseModel):
    """Compliance score for a tenant/subscription."""

    tenant_id: str
    tenant_name: str
    subscription_id: str | None = None
    subscription_name: str | None = None
    overall_compliance_percent: float = Field(..., ge=0, le=100)
    secure_score: float | None = Field(None, ge=0, le=100)
    compliant_resources: int
    non_compliant_resources: int
    exempt_resources: int
    last_updated: datetime


class ComplianceSummary(BaseModel):
    """Aggregated compliance summary."""

    average_compliance_percent: float
    total_compliant_resources: int
    total_non_compliant_resources: int
    total_exempt_resources: int
    scores_by_tenant: list[ComplianceScore] = Field(default_factory=list)
    top_violations: list["PolicyViolation"] = Field(default_factory=list)


class PolicyViolation(BaseModel):
    """Top policy violations."""

    policy_name: str
    policy_category: str | None
    violation_count: int
    affected_tenants: int
    severity: str = "Medium"  # Low, Medium, High, Critical


class PolicyStatus(BaseModel):
    """Individual policy status."""

    policy_definition_id: str
    policy_name: str
    policy_category: str | None
    compliance_state: str
    non_compliant_count: int
    tenant_id: str
    subscription_id: str
    severity: str = "Medium"  # Low, Medium, High, Critical
    recommendation: str | None = None


# Update forward references
ComplianceSummary.model_rebuild()

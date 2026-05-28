"""Pydantic schemas for the franchise-coach dashboard.

The franchise-coach view is read-only insight for Manager-tier users.
It surfaces identity gaps + compliance gaps + sync freshness per brand,
phrased in the HTT brand voice (franchisee-first, operationally exact,
warm but disciplined).

See:
    - ADR-0012 — Manager role rationale
    - app/api/services/franchise_coach_service.py — data assembly
    - ~/code_puppy/docs/htt_brand_voice_framework.html — voice charter
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

InsightSeverity = Literal["critical", "attention", "healthy"]


class IdentityInsight(BaseModel):
    """Identity-domain insight for a single brand."""

    mfa_enabled_count: int = Field(ge=0)
    mfa_disabled_count: int = Field(ge=0)
    mfa_coverage_percent: float = Field(ge=0.0, le=100.0)
    privileged_users_total: int = Field(ge=0)
    stale_accounts_30d: int = Field(ge=0)
    stale_accounts_90d: int = Field(ge=0)
    has_premium_p1: bool = Field(
        default=True,
        description="False for tenants lacking Entra ID P1 (e.g. DCE) where "
        "MFA reporting via signInActivity returns 403.",
    )
    severity: InsightSeverity
    coaching_message: str = Field(
        description="Brand-voice phrasing: objective → reality → action → outcome.",
    )


class ComplianceInsight(BaseModel):
    """Compliance-domain insight for a single brand."""

    secure_score: float | None = Field(default=None, ge=0.0, le=100.0)
    overall_compliance_percent: float = Field(ge=0.0, le=100.0)
    non_compliant_resource_count: int = Field(ge=0)
    top_failing_categories: list[str] = Field(default_factory=list, max_length=5)
    severity: InsightSeverity
    coaching_message: str


class SyncFreshness(BaseModel):
    """Per-domain sync timestamps + staleness flags."""

    costs_synced_at: datetime | None = None
    identity_synced_at: datetime | None = None
    resources_synced_at: datetime | None = None
    compliance_synced_at: datetime | None = None
    any_stale: bool = False
    stale_domains: list[str] = Field(default_factory=list)


class BrandCoachCard(BaseModel):
    """A single brand's at-a-glance coaching card.

    Designed so a franchise executive can scan one card and have a
    structured conversation with the brand operator. Each card answers:
    'What's the business objective, what's the reality, what's the
    recommended action, what's the expected outcome?'
    """

    tenant_id: str
    brand_name: str = Field(description="Display name, e.g. 'Bishops Cuts & Color'")
    brand_short_code: str = Field(description="Short code, e.g. 'BCC'")
    identity: IdentityInsight | None = None
    compliance: ComplianceInsight | None = None
    sync_freshness: SyncFreshness
    headline: str = Field(
        description="One-line, brand-voice summary suitable for the dashboard card."
    )
    overall_severity: InsightSeverity


class FranchiseCoachView(BaseModel):
    """Top-level response for the Manager dashboard."""

    generated_at: datetime
    brand_count: int
    brands_needing_attention: int
    healthy_brands: int
    cards: list[BrandCoachCard]

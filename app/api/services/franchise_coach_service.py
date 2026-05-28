"""Franchise-coach service: aggregate cross-brand insights for Manager tier.

Pure functions over the database. No HTTP layer — that lives in the
route. No write paths — Managers are coaches, not operators.

Brand-voice copy follows the HTT 4-step pattern:
    1. Business objective
    2. Operational reality / risk
    3. Recommended action
    4. Expected outcome

See:
    - ADR-0012 — Manager role rationale
    - app/schemas/franchise_coach.py — response models
    - ~/code_puppy/docs/htt_brand_voice_framework.html — voice charter
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.compliance import ComplianceSnapshot, PolicyState
from app.models.identity import IdentitySnapshot
from app.models.tenant import Tenant
from app.schemas.franchise_coach import (
    BrandCoachCard,
    ComplianceInsight,
    FranchiseCoachView,
    IdentityInsight,
    InsightSeverity,
    SyncFreshness,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Severity thresholds (tunable, but currently conservative)
# ============================================================================

_MFA_HEALTHY_PERCENT = 95.0
_MFA_ATTENTION_PERCENT = 80.0

_COMPLIANCE_HEALTHY_PERCENT = 90.0
_COMPLIANCE_ATTENTION_PERCENT = 70.0

_SECURE_SCORE_HEALTHY = 70.0
_SECURE_SCORE_ATTENTION = 50.0

_STALE_AFTER = timedelta(hours=25)


# ============================================================================
# Severity classifiers
# ============================================================================


def _identity_severity(
    mfa_coverage_percent: float,
    stale_30d: int,
    has_premium_p1: bool,
) -> InsightSeverity:
    """Return overall identity severity for a brand."""
    if not has_premium_p1:
        # Missing P1 means we can't even SEE the gaps — that itself is a
        # critical conversation to have.
        return "attention"
    if mfa_coverage_percent >= _MFA_HEALTHY_PERCENT and stale_30d == 0:
        return "healthy"
    if mfa_coverage_percent < _MFA_ATTENTION_PERCENT or stale_30d > 5:
        return "critical"
    return "attention"


def _compliance_severity(
    overall_percent: float,
    secure_score: float | None,
) -> InsightSeverity:
    if overall_percent >= _COMPLIANCE_HEALTHY_PERCENT and (
        secure_score is None or secure_score >= _SECURE_SCORE_HEALTHY
    ):
        return "healthy"
    if overall_percent < _COMPLIANCE_ATTENTION_PERCENT or (
        secure_score is not None and secure_score < _SECURE_SCORE_ATTENTION
    ):
        return "critical"
    return "attention"


_SHORT_CODE_RE = re.compile(r"\(([A-Z]{2,8})\)\s*$")


def _extract_short_code(name: str) -> str:
    """Extract '(BCC)'-style short code from a tenant display name."""
    if not name:
        return ""
    match = _SHORT_CODE_RE.search(name)
    if match:
        return match.group(1)
    # Fall back to first 3 uppercase letters in the name
    upper = "".join(c for c in name if c.isupper())
    return upper[:4] or name[:4]


def _roll_up_severity(parts: list[InsightSeverity]) -> InsightSeverity:
    """Worst-wins roll-up across all insight pillars for a brand."""
    if "critical" in parts:
        return "critical"
    if "attention" in parts:
        return "attention"
    return "healthy"


# ============================================================================
# Brand-voice coaching messages (4-step pattern)
# ============================================================================


def _identity_coaching(insight: IdentityInsight, brand_name: str) -> str:
    """Brand-voice phrasing for the identity card.

    Pattern: objective → reality → action → outcome.
    """
    if not insight.has_premium_p1:
        return (
            f"To protect {brand_name}'s users and the wider system, we need clear "
            f"visibility into MFA registration. Right now the tenant lacks Entra ID P1, "
            f"so sign-in activity and MFA reports come back as 403. The next step is to "
            f"add P1 for the active accounts. With that in place, we can coach the team "
            f"on closing real gaps instead of guessing."
        )
    if insight.severity == "healthy":
        return (
            f"{brand_name} is in strong shape on identity — MFA coverage at "
            f"{insight.mfa_coverage_percent:.1f}% and zero stale accounts. Keep "
            f"reinforcing the standard at onboarding so the next operator promotion "
            f"doesn't slip."
        )
    if insight.severity == "critical":
        return (
            f"To protect {brand_name} from account takeover, MFA coverage needs to "
            f"come up — currently {insight.mfa_coverage_percent:.1f}% with "
            f"{insight.stale_accounts_30d} accounts inactive 30+ days. Coach the brand "
            f"lead to enroll the remaining users this week and offboard the stale "
            f"accounts. Expected outcome: fewer support tickets, no surprise breach "
            f"reports, audit story stays clean."
        )
    # attention
    return (
        f"{brand_name} is close on identity but not quite there — MFA at "
        f"{insight.mfa_coverage_percent:.1f}%, "
        f"{insight.stale_accounts_30d} stale accounts in the last 30 days. A short "
        f"weekly review with the brand lead will close the gap and protect the "
        f"system going forward."
    )


def _compliance_coaching(insight: ComplianceInsight, brand_name: str) -> str:
    if insight.severity == "healthy":
        return (
            f"{brand_name}'s compliance posture is solid at "
            f"{insight.overall_compliance_percent:.1f}%. Keep the standard visible to "
            f"the operator so the next change doesn't introduce drift."
        )
    if insight.severity == "critical":
        return (
            f"To protect {brand_name} and the wider HTT brand, compliance needs to "
            f"come up — currently {insight.overall_compliance_percent:.1f}% with "
            f"{insight.non_compliant_resource_count} resources out of policy. Coach "
            f"the team to focus on the top failing categories first and close those "
            f"in this sprint. Expected outcome: audit-ready posture, fewer fire drills, "
            f"and a brand operator who knows the standard."
        )
    return (
        f"{brand_name}'s compliance is in the middle band — "
        f"{insight.overall_compliance_percent:.1f}%. The recommended action is a "
        f"15-minute review with the brand lead on the failing categories so the "
        f"next sync moves the number in the right direction."
    )


def _brand_headline(card: BrandCoachCard) -> str:
    """One-line, scannable, brand-voice headline for the card."""
    name = card.brand_name
    if card.overall_severity == "healthy":
        return f"{name}: standards holding — keep coaching the daily rhythm."
    if card.overall_severity == "critical":
        return f"{name}: real gaps — have the conversation this week."
    return f"{name}: close but slipping — a short coaching check-in will reset it."


# ============================================================================
# Per-domain insight builders
# ============================================================================


def _latest(session: Session, model, tenant_id: str):
    """Return the most-recent row of *model* for *tenant_id* or None."""
    return (
        session.query(model)
        .filter(model.tenant_id == tenant_id)
        .order_by(model.synced_at.desc())
        .first()
    )


def _build_identity_insight(
    session: Session,
    tenant_id: str,
    brand_name: str,
    has_premium_p1: bool,
) -> IdentityInsight | None:
    snap: IdentitySnapshot | None = _latest(session, IdentitySnapshot, tenant_id)
    if snap is None:
        return None
    total = snap.mfa_enabled_users + snap.mfa_disabled_users
    coverage = (snap.mfa_enabled_users / total * 100.0) if total else 0.0
    severity = _identity_severity(coverage, snap.stale_accounts_30d, has_premium_p1)
    insight = IdentityInsight(
        mfa_enabled_count=snap.mfa_enabled_users,
        mfa_disabled_count=snap.mfa_disabled_users,
        mfa_coverage_percent=round(coverage, 1),
        privileged_users_total=snap.privileged_users,
        stale_accounts_30d=snap.stale_accounts_30d,
        stale_accounts_90d=snap.stale_accounts_90d,
        has_premium_p1=has_premium_p1,
        severity=severity,
        coaching_message="",  # filled below — needs brand_name
    )
    insight.coaching_message = _identity_coaching(insight, brand_name)
    return insight


def _build_compliance_insight(
    session: Session, tenant_id: str, brand_name: str
) -> ComplianceInsight | None:
    snap: ComplianceSnapshot | None = _latest(session, ComplianceSnapshot, tenant_id)
    if snap is None:
        return None
    top_failing = (
        session.query(PolicyState.policy_category)
        .filter(
            PolicyState.tenant_id == tenant_id,
            PolicyState.compliance_state == "NonCompliant",
            PolicyState.policy_category.isnot(None),
        )
        .distinct()
        .limit(5)
        .all()
    )
    categories = [row[0] for row in top_failing if row[0]]
    severity = _compliance_severity(snap.overall_compliance_percent, snap.secure_score)
    insight = ComplianceInsight(
        secure_score=snap.secure_score,
        overall_compliance_percent=round(snap.overall_compliance_percent, 1),
        non_compliant_resource_count=snap.non_compliant_resources,
        top_failing_categories=categories,
        severity=severity,
        coaching_message="",
    )
    insight.coaching_message = _compliance_coaching(insight, brand_name)
    return insight


def _build_sync_freshness(session: Session, tenant_id: str, now: datetime) -> SyncFreshness:
    """Look at the most-recent rows in each domain to assess staleness."""

    def latest_synced_at(model) -> datetime | None:
        row = _latest(session, model, tenant_id)
        return row.synced_at if row else None

    from app.models.cost import CostSnapshot  # local import to avoid cycles
    from app.models.resource import Resource

    domain_to_ts = {
        "costs": latest_synced_at(CostSnapshot) if "CostSnapshot" in globals() else None,
        "identity": latest_synced_at(IdentitySnapshot),
        "resources": latest_synced_at(Resource) if "Resource" in globals() else None,
        "compliance": latest_synced_at(ComplianceSnapshot),
    }
    # Re-resolve with the actual imported classes (the dict comp above was a guard)
    domain_to_ts["costs"] = latest_synced_at(CostSnapshot)
    domain_to_ts["resources"] = latest_synced_at(Resource)

    def _is_stale(ts: datetime | None) -> bool:
        if ts is None:
            return True
        # SQLite (and some MSSQL columns) hand back naive datetimes — normalize.
        ts_utc = ts if ts.tzinfo else ts.replace(tzinfo=UTC)
        return (now - ts_utc) > _STALE_AFTER

    stale_domains = [domain for domain, ts in domain_to_ts.items() if _is_stale(ts)]
    return SyncFreshness(
        costs_synced_at=domain_to_ts["costs"],
        identity_synced_at=domain_to_ts["identity"],
        resources_synced_at=domain_to_ts["resources"],
        compliance_synced_at=domain_to_ts["compliance"],
        any_stale=bool(stale_domains),
        stale_domains=stale_domains,
    )


# ============================================================================
# Top-level entrypoint
# ============================================================================


def build_franchise_coach_view(
    session: Session,
    *,
    now: datetime | None = None,
) -> FranchiseCoachView:
    """Assemble the Manager-tier coach dashboard for every active tenant.

    Args:
        session: SQLAlchemy session
        now: Override for clock (test seam). Defaults to ``datetime.now(UTC)``.

    Returns:
        A fully-populated :class:`FranchiseCoachView`.
    """
    now = now or datetime.now(UTC)
    tenants: list[Tenant] = session.query(Tenant).filter(Tenant.is_active.is_(True)).all()
    cards: list[BrandCoachCard] = []
    needing_attention = 0
    healthy = 0

    for tenant in tenants:
        short_code = _extract_short_code(tenant.name)
        # DCE is the documented Entra-P1 exception (STAGING_DEPLOYMENT.md).
        has_p1 = short_code.upper() != "DCE"
        identity = _build_identity_insight(session, tenant.id, tenant.name, has_p1)
        compliance = _build_compliance_insight(session, tenant.id, tenant.name)
        freshness = _build_sync_freshness(session, tenant.id, now)

        sev_parts: list[InsightSeverity] = []
        if identity:
            sev_parts.append(identity.severity)
        if compliance:
            sev_parts.append(compliance.severity)
        if freshness.any_stale:
            sev_parts.append("attention")
        overall = _roll_up_severity(sev_parts) if sev_parts else "attention"

        card = BrandCoachCard(
            tenant_id=tenant.id,
            brand_name=tenant.name,
            brand_short_code=short_code or tenant.name[:8],
            identity=identity,
            compliance=compliance,
            sync_freshness=freshness,
            headline="",  # set below
            overall_severity=overall,
        )
        card.headline = _brand_headline(card)
        cards.append(card)

        if overall == "healthy":
            healthy += 1
        else:
            needing_attention += 1

    return FranchiseCoachView(
        generated_at=now,
        brand_count=len(cards),
        brands_needing_attention=needing_attention,
        healthy_brands=healthy,
        cards=cards,
    )

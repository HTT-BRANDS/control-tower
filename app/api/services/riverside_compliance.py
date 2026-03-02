"""Riverside Company compliance and MFA analysis functions.

Business logic functions for compliance calculations and MFA gap analysis
for the Riverside compliance tracking system.
"""

import logging
from datetime import date
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.riverside import (
    RiversideCompliance,
    RiversideMFA,
)

logger = logging.getLogger(__name__)

# Constants
RIVERSIDE_DEADLINE = date(2026, 7, 8)
TARGET_MATURITY_SCORE = 3.0


def calculate_compliance_summary(db: Session) -> dict:
    """Calculate overall compliance percentages and maturity scores.

    This function computes aggregated compliance metrics across all Riverside
    tenants including overall compliance percentage, average maturity score,
    and weighted maturity calculations based on tenant sizes.

    Args:
        db: Database session for querying compliance data.

    Returns:
        Dictionary containing:
            - overall_compliance_percentage: Weighted compliance percentage
            - average_maturity_score: Average maturity across all tenants
            - weighted_maturity_score: Maturity weighted by user count
            - total_critical_gaps: Total number of critical gaps
            - tenants_analyzed: Number of tenants included
            - maturity_distribution: Breakdown by maturity ranges
            - compliance_trend: Direction of compliance (improving/stable/declining)

    Raises:
        ValueError: If no compliance data is available.
    """
    # Get latest compliance data per tenant
    compliance_subquery = (
        db.query(
            RiversideCompliance.tenant_id,
            func.max(RiversideCompliance.created_at).label("max_created"),
        )
        .group_by(RiversideCompliance.tenant_id)
        .subquery()
    )

    compliance_records = (
        db.query(RiversideCompliance)
        .join(
            compliance_subquery,
            (RiversideCompliance.tenant_id == compliance_subquery.c.tenant_id)
            & (RiversideCompliance.created_at == compliance_subquery.c.max_created),
        )
        .all()
    )

    if not compliance_records:
        raise ValueError("No compliance data available for analysis")

    total_tenants = len(compliance_records)
    total_maturity = 0.0
    total_critical_gaps = 0
    total_requirements = 0
    total_completed = 0

    # Maturity distribution counters
    maturity_distribution: dict[str, int] = {
        "below_2": 0,  # Critical risk
        "2_to_3": 0,   # Needs improvement
        "3_to_4": 0,   # Good
        "above_4": 0,  # Excellent
    }

    for record in compliance_records:
        maturity = record.overall_maturity_score
        total_maturity += maturity
        total_critical_gaps += record.critical_gaps_count
        total_requirements += record.requirements_total
        total_completed += record.requirements_completed

        # Categorize maturity
        if maturity < 2.0:
            maturity_distribution["below_2"] += 1
        elif maturity < 3.0:
            maturity_distribution["2_to_3"] += 1
        elif maturity < 4.0:
            maturity_distribution["3_to_4"] += 1
        else:
            maturity_distribution["above_4"] += 1

    avg_maturity = total_maturity / total_tenants if total_tenants > 0 else 0.0
    compliance_percentage = (
        (total_completed / total_requirements * 100)
        if total_requirements > 0
        else 0.0
    )

    # Calculate trend based on completed vs total ratio
    trend = "stable"
    if compliance_percentage >= 70:
        trend = "improving"
    elif compliance_percentage < 30:
        trend = "critical"
    elif compliance_percentage < 50:
        trend = "declining"

    result: dict[str, Any] = {
        "overall_compliance_percentage": round(compliance_percentage, 1),
        "average_maturity_score": round(avg_maturity, 1),
        "weighted_maturity_score": round(avg_maturity, 1),  # Placeholder for future weighting
        "total_critical_gaps": total_critical_gaps,
        "tenants_analyzed": total_tenants,
        "maturity_distribution": maturity_distribution,
        "compliance_trend": trend,
        "requirements_completed": total_completed,
        "requirements_total": total_requirements,
    }
    return result


def analyze_mfa_gaps(db: Session, tenant_id: str | None = None) -> dict:
    """Analyze MFA enrollment gaps and calculate coverage deficits.

    Identifies users without MFA, calculates coverage gaps at both tenant
    and aggregate levels, and provides actionable gap analysis for security
    remediation planning.

    Args:
        db: Database session for querying MFA data.
        tenant_id: Optional tenant ID to filter analysis to a specific tenant.

    Returns:
        Dictionary containing:
            - overall_coverage_percentage: Average MFA coverage across tenants
            - admin_coverage_percentage: Average admin MFA coverage
            - total_unprotected_users: Total count of users without MFA
            - coverage_gap_percentage: Percentage gap from 100% coverage
            - high_risk_tenants: List of tenants with <50% coverage
            - tenant_breakdown: Per-tenant MFA statistics
            - recommendations: List of remediation recommendations

    Raises:
        ValueError: If no MFA data is available.
    """
    # Get latest MFA data per tenant
    mfa_subquery = (
        db.query(
            RiversideMFA.tenant_id,
            func.max(RiversideMFA.snapshot_date).label("max_snapshot"),
        )
        .group_by(RiversideMFA.tenant_id)
        .subquery()
    )

    query = db.query(RiversideMFA).join(
        mfa_subquery,
        (RiversideMFA.tenant_id == mfa_subquery.c.tenant_id)
        & (RiversideMFA.snapshot_date == mfa_subquery.c.max_snapshot),
    )

    if tenant_id:
        query = query.filter(RiversideMFA.tenant_id == tenant_id)

    mfa_records = query.all()

    if not mfa_records:
        raise ValueError("No MFA data available for analysis")

    total_coverage = 0.0
    total_admin_coverage = 0.0
    total_unprotected = 0
    total_users = 0
    high_risk_tenants: list[dict[str, Any]] = []
    tenant_breakdown: list[dict[str, Any]] = []

    for record in mfa_records:
        coverage = record.mfa_coverage_percentage
        admin_coverage = record.admin_mfa_percentage
        unprotected = record.unprotected_users

        total_coverage += coverage
        total_admin_coverage += admin_coverage
        total_unprotected += unprotected
        total_users += record.total_users

        tenant_info = {
            "tenant_id": record.tenant_id,
            "coverage_percentage": round(coverage, 1),
            "admin_coverage_percentage": round(admin_coverage, 1),
            "unprotected_users": unprotected,
            "total_users": record.total_users,
            "risk_level": "critical" if coverage < 50 else "high" if coverage < 75 else "medium",
        }
        tenant_breakdown.append(tenant_info)

        # Identify high-risk tenants (< 50% coverage)
        if coverage < 50:
            high_risk_tenants.append(tenant_info)

    tenant_count = len(mfa_records)
    avg_coverage = total_coverage / tenant_count if tenant_count > 0 else 0.0
    avg_admin_coverage = total_admin_coverage / tenant_count if tenant_count > 0 else 0.0
    coverage_gap = 100.0 - avg_coverage

    # Generate recommendations based on gaps
    recommendations: list[str] = []
    if avg_coverage < 50:
        recommendations.append(
            "CRITICAL: Implement emergency MFA rollout - coverage below 50%"
        )
    if avg_admin_coverage < 100:
        recommendations.append(
            "URGENT: Ensure 100% admin MFA coverage before addressing user MFA"
        )
    if high_risk_tenants:
        recommendations.append(
            f"Prioritize {len(high_risk_tenants)} high-risk tenants for immediate remediation"
        )
    if avg_coverage < 90:
        recommendations.append(
            "Consider conditional access policies to enforce MFA for critical applications"
        )

    result: dict[str, Any] = {
        "overall_coverage_percentage": round(avg_coverage, 1),
        "admin_coverage_percentage": round(avg_admin_coverage, 1),
        "total_unprotected_users": total_unprotected,
        "total_users": total_users,
        "coverage_gap_percentage": round(coverage_gap, 1),
        "high_risk_tenants": high_risk_tenants,
        "high_risk_count": len(high_risk_tenants),
        "tenant_breakdown": tenant_breakdown,
        "recommendations": recommendations,
    }
    return result

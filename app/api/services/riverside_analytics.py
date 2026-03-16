"""Riverside Company analytics and calculation functions.

Business logic functions for aggregated analysis and calculations for the
Riverside compliance tracking system. These functions provide comprehensive
metrics, requirement progress tracking, deadline monitoring, and executive summaries.
"""

import logging
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.riverside import (
    RequirementStatus,
    RiversideCompliance,
    RiversideDeviceCompliance,
    RiversideMFA,
    RiversideRequirement,
    RiversideThreatData,
)
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)

# Constants
RIVERSIDE_DEADLINE = date(2026, 7, 8)
TARGET_MATURITY_SCORE = 3.0


def track_requirement_progress(db: Session, requirement_id: int) -> dict:
    """Track completion status of a specific requirement over time.

    Analyzes the historical progress of a requirement including status
    changes, completion timeline, and velocity metrics.

    Args:
        db: Database session for querying requirement data.
        requirement_id: The unique identifier of the requirement to track.

    Returns:
        Dictionary containing:
            - requirement_id: The tracked requirement ID
            - current_status: Current status of the requirement
            - progress_percentage: Estimated progress percentage
            - days_in_current_status: Days spent in current status
            - estimated_completion: Estimated completion date
            - velocity: Progress velocity (requirements per week)
            - blockers: List of identified blockers
            - related_requirements: IDs of related requirements in same category

    Raises:
        ValueError: If the requirement is not found.
    """
    requirement = (
        db.query(RiversideRequirement).filter(RiversideRequirement.id == requirement_id).first()
    )

    if not requirement:
        raise ValueError(f"Requirement with ID {requirement_id} not found")

    # Calculate progress percentage based on status
    status_progress_map = {
        RequirementStatus.NOT_STARTED: 0,
        RequirementStatus.BLOCKED: 0,
        RequirementStatus.IN_PROGRESS: 50,
        RequirementStatus.COMPLETED: 100,
    }
    progress_percentage = status_progress_map.get(requirement.status, 0)

    # Calculate days in current status
    today = date.today()
    days_in_status = 0
    if requirement.updated_at:
        days_in_status = (today - requirement.updated_at.date()).days

    # Estimate completion based on due date and progress
    estimated_completion = None
    if requirement.due_date:
        if requirement.status == RequirementStatus.COMPLETED:
            estimated_completion = requirement.completed_date
        elif progress_percentage > 0 and requirement.due_date >= today:
            estimated_completion = requirement.due_date

    # Find related requirements in same category
    related = (
        db.query(RiversideRequirement)
        .filter(
            RiversideRequirement.category == requirement.category,
            RiversideRequirement.id != requirement_id,
            RiversideRequirement.tenant_id == requirement.tenant_id,
        )
        .limit(5)
        .all()
    )

    related_ids = [r.id for r in related]

    # Calculate velocity based on tenant's overall completion rate
    tenant_completed = (
        db.query(func.count(RiversideRequirement.id))
        .filter(
            RiversideRequirement.tenant_id == requirement.tenant_id,
            RiversideRequirement.status == RequirementStatus.COMPLETED.value,
        )
        .scalar()
        or 0
    )

    tenant_total = (
        db.query(func.count(RiversideRequirement.id))
        .filter(RiversideRequirement.tenant_id == requirement.tenant_id)
        .scalar()
        or 1
    )

    velocity = (tenant_completed / tenant_total) * 10  # Rough velocity metric

    # Identify blockers
    blockers: list[str] = []
    if requirement.status == RequirementStatus.BLOCKED:
        blockers.append("Requirement explicitly marked as blocked")
    if days_in_status > 30 and requirement.status != RequirementStatus.COMPLETED:
        blockers.append(f"Stalled for {days_in_status} days without progress")
    if requirement.due_date and requirement.due_date < today:
        blockers.append("Past due date")

    result: dict[str, Any] = {
        "requirement_id": requirement_id,
        "requirement_identifier": requirement.requirement_id,
        "title": requirement.title,
        "current_status": requirement.status.value,
        "category": requirement.category.value,
        "priority": requirement.priority.value,
        "progress_percentage": progress_percentage,
        "days_in_current_status": days_in_status,
        "due_date": requirement.due_date.isoformat() if requirement.due_date else None,
        "completed_date": (
            requirement.completed_date.isoformat() if requirement.completed_date else None
        ),
        "estimated_completion": (
            estimated_completion.isoformat() if estimated_completion else None
        ),
        "velocity": round(velocity, 2),
        "blockers": blockers,
        "related_requirements": related_ids,
        "owner": requirement.owner,
        "has_evidence": bool(requirement.evidence_url),
    }
    return result


def get_deadline_status(db: Session, days_window: int = 30) -> dict:
    """Calculate days until deadline and identify overdue items.

    Monitors the July 8, 2026 Riverside compliance deadline, calculating
    time remaining and identifying requirements that are overdue or at risk.

    Args:
        db: Database session for querying deadline data.
        days_window: Number of days to look ahead for upcoming deadlines.

    Returns:
        Dictionary containing:
            - deadline_date: The compliance deadline (2026-07-08)
            - days_until_deadline: Days remaining until deadline
            - deadline_status: Status category (at_risk, approaching, on_track)
            - overdue_count: Number of overdue requirements
            - at_risk_count: Requirements due within days_window
            - upcoming_deadlines: List of requirements due soon
            - urgency_score: Calculated urgency metric (0-100)
            - risk_assessment: Overall risk level

    Raises:
        ValueError: If days_window is negative.
    """
    if days_window < 0:
        raise ValueError("days_window must be non-negative")

    today = date.today()
    days_until = (RIVERSIDE_DEADLINE - today).days

    # Determine deadline status
    if days_until < 0:
        deadline_status = "overdue"
    elif days_until < days_window:
        deadline_status = "at_risk"
    elif days_until < 180:  # Less than 6 months
        deadline_status = "approaching"
    else:
        deadline_status = "on_track"

    # Get overdue requirements
    overdue_requirements = (
        db.query(RiversideRequirement)
        .filter(
            RiversideRequirement.due_date < today,
            RiversideRequirement.status != RequirementStatus.COMPLETED.value,
        )
        .all()
    )

    overdue_count = len(overdue_requirements)

    # Get requirements at risk (due within window)
    cutoff_date = today + timedelta(days=days_window)
    at_risk_requirements = (
        db.query(RiversideRequirement)
        .filter(
            RiversideRequirement.due_date >= today,
            RiversideRequirement.due_date <= cutoff_date,
            RiversideRequirement.status != RequirementStatus.COMPLETED.value,
        )
        .order_by(RiversideRequirement.due_date)
        .all()
    )

    at_risk_count = len(at_risk_requirements)

    # Format upcoming deadlines
    upcoming_deadlines = [
        {
            "id": req.id,
            "requirement_id": req.requirement_id,
            "title": req.title,
            "due_date": req.due_date.isoformat() if req.due_date else None,
            "days_remaining": (req.due_date - today).days if req.due_date else None,
            "priority": req.priority.value,
            "owner": req.owner,
        }
        for req in at_risk_requirements
    ]

    # Calculate urgency score (0-100)
    total_requirements = db.query(func.count(RiversideRequirement.id)).scalar() or 1
    completed_requirements = (
        db.query(func.count(RiversideRequirement.id))
        .filter(RiversideRequirement.status == RequirementStatus.COMPLETED.value)
        .scalar()
        or 0
    )

    completion_rate = completed_requirements / total_requirements
    time_remaining_ratio = max(0, days_until) / 365  # Normalize to year

    # Urgency increases as deadline approaches and completion is low
    urgency_score = min(100, max(0, (1 - completion_rate) * 100 + (1 - time_remaining_ratio) * 50))

    # Determine risk assessment
    if overdue_count > 10 or urgency_score > 80:
        risk_assessment = "critical"
    elif overdue_count > 5 or urgency_score > 60:
        risk_assessment = "high"
    elif overdue_count > 0 or urgency_score > 40:
        risk_assessment = "medium"
    else:
        risk_assessment = "low"

    result: dict[str, Any] = {
        "deadline_date": RIVERSIDE_DEADLINE.isoformat(),
        "days_until_deadline": days_until,
        "deadline_status": deadline_status,
        "overdue_count": overdue_count,
        "at_risk_count": at_risk_count,
        "upcoming_deadlines": upcoming_deadlines,
        "urgency_score": round(urgency_score, 1),
        "risk_assessment": risk_assessment,
        "total_requirements": total_requirements,
        "completed_requirements": completed_requirements,
        "completion_rate": round(completion_rate * 100, 1),
    }
    return result


def get_riverside_metrics(db: Session) -> dict:
    """Calculate Riverside-specific tenant-level aggregations and metrics.

    Provides comprehensive metrics tailored for Riverside Company's
    compliance tracking needs, including cross-tenant aggregations,
    security posture scoring, and executive summary data.

    Args:
        db: Database session for querying metrics data.

    Returns:
        Dictionary containing:
            - tenant_count: Number of active Riverside tenants
            - security_posture_score: Overall security posture (0-100)
            - maturity_metrics: Aggregated maturity statistics
            - mfa_summary: MFA coverage summary
            - device_summary: Device compliance summary
            - threat_summary: Threat data summary
            - financial_exposure: Calculated risk exposure
            - executive_summary: High-level status summary

    Raises:
        ValueError: If no tenant data is available.
    """
    # Get all active tenants
    tenants = db.query(Tenant).filter(Tenant.is_active.is_(True)).all()

    if not tenants:
        raise ValueError("No tenant data available for metrics calculation")

    tenant_count = len(tenants)
    tenant_ids = [t.id for t in tenants]

    # Get latest compliance data
    compliance_subquery = (
        db.query(
            RiversideCompliance.tenant_id,
            func.max(RiversideCompliance.created_at).label("max_created"),
        )
        .filter(RiversideCompliance.tenant_id.in_(tenant_ids))
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

    # Get latest MFA data
    mfa_subquery = (
        db.query(
            RiversideMFA.tenant_id,
            func.max(RiversideMFA.snapshot_date).label("max_snapshot"),
        )
        .filter(RiversideMFA.tenant_id.in_(tenant_ids))
        .group_by(RiversideMFA.tenant_id)
        .subquery()
    )

    mfa_records = (
        db.query(RiversideMFA)
        .join(
            mfa_subquery,
            (RiversideMFA.tenant_id == mfa_subquery.c.tenant_id)
            & (RiversideMFA.snapshot_date == mfa_subquery.c.max_snapshot),
        )
        .all()
    )

    # Get latest device compliance data
    device_subquery = (
        db.query(
            RiversideDeviceCompliance.tenant_id,
            func.max(RiversideDeviceCompliance.snapshot_date).label("max_snapshot"),
        )
        .filter(RiversideDeviceCompliance.tenant_id.in_(tenant_ids))
        .group_by(RiversideDeviceCompliance.tenant_id)
        .subquery()
    )

    device_records = (
        db.query(RiversideDeviceCompliance)
        .join(
            device_subquery,
            (RiversideDeviceCompliance.tenant_id == device_subquery.c.tenant_id)
            & (RiversideDeviceCompliance.snapshot_date == device_subquery.c.max_snapshot),
        )
        .all()
    )

    # Get threat data
    threat_subquery = (
        db.query(
            RiversideThreatData.tenant_id,
            func.max(RiversideThreatData.snapshot_date).label("max_snapshot"),
        )
        .filter(RiversideThreatData.tenant_id.in_(tenant_ids))
        .group_by(RiversideThreatData.tenant_id)
        .subquery()
    )

    threat_records = (
        db.query(RiversideThreatData)
        .join(
            threat_subquery,
            (RiversideThreatData.tenant_id == threat_subquery.c.tenant_id)
            & (RiversideThreatData.snapshot_date == threat_subquery.c.max_snapshot),
        )
        .all()
    )

    # Calculate maturity metrics
    total_maturity = 0.0
    total_gaps = 0
    for record in compliance_records:
        total_maturity += record.overall_maturity_score
        total_gaps += record.critical_gaps_count

    avg_maturity = total_maturity / len(compliance_records) if compliance_records else 0.0

    # Calculate MFA summary
    total_mfa_coverage = 0.0
    total_admin_mfa = 0.0
    total_unprotected = 0
    for record in mfa_records:
        total_mfa_coverage += record.mfa_coverage_percentage
        total_admin_mfa += record.admin_mfa_percentage
        total_unprotected += record.unprotected_users

    avg_mfa_coverage = total_mfa_coverage / len(mfa_records) if mfa_records else 0.0
    avg_admin_mfa = total_admin_mfa / len(mfa_records) if mfa_records else 0.0

    # Calculate device summary
    total_device_compliance = 0.0
    total_devices = 0
    total_compliant_devices = 0
    for record in device_records:
        total_device_compliance += record.compliance_percentage
        total_devices += record.total_devices
        total_compliant_devices += record.compliant_devices

    avg_device_compliance = total_device_compliance / len(device_records) if device_records else 0.0

    # Calculate threat summary
    total_vulnerabilities = 0
    total_threat_score = 0.0
    for record in threat_records:
        total_vulnerabilities += record.vulnerability_count
        if record.threat_score:
            total_threat_score += record.threat_score

    avg_threat_score = total_threat_score / len(threat_records) if threat_records else 0.0

    # Calculate security posture score (0-100)
    # Weight factors: MFA (30%), Device (25%), Maturity (25%), Threat (20%)
    posture_score = (
        (avg_mfa_coverage * 0.30)
        + (avg_device_compliance * 0.25)
        + (avg_maturity / 5 * 100 * 0.25)  # Normalize maturity to 0-100
        + (max(0, 100 - avg_threat_score) * 0.20)  # Invert threat score
    )

    # Get requirements summary
    total_requirements = (
        db.query(func.count(RiversideRequirement.id))
        .filter(RiversideRequirement.tenant_id.in_(tenant_ids))
        .scalar()
        or 0
    )

    completed_requirements = (
        db.query(func.count(RiversideRequirement.id))
        .filter(
            RiversideRequirement.tenant_id.in_(tenant_ids),
            RiversideRequirement.status == RequirementStatus.COMPLETED.value,
        )
        .scalar()
        or 0
    )

    completion_rate = (
        (completed_requirements / total_requirements * 100) if total_requirements > 0 else 0.0
    )

    # Calculate financial exposure based on gaps and posture
    base_exposure = 20_000_000  # $20M base
    risk_multiplier = max(0.5, 1 - (posture_score / 100))  # Higher posture = lower exposure
    financial_exposure = base_exposure * risk_multiplier

    # Generate executive summary
    days_until = (RIVERSIDE_DEADLINE - date.today()).days

    if posture_score >= 80:
        overall_status = "strong"
    elif posture_score >= 60:
        overall_status = "moderate"
    elif posture_score >= 40:
        overall_status = "weak"
    else:
        overall_status = "critical"

    executive_summary: dict[str, Any] = {
        "overall_status": overall_status,
        "deadline_days_remaining": days_until,
        "key_strengths": [],
        "key_concerns": [],
    }

    if avg_admin_mfa >= 95:
        executive_summary["key_strengths"].append("Strong admin MFA coverage")
    if avg_maturity >= 3.0:
        executive_summary["key_strengths"].append("Meeting maturity targets")
    if completion_rate >= 70:
        executive_summary["key_strengths"].append("Good requirements completion rate")

    if avg_mfa_coverage < 75:
        executive_summary["key_concerns"].append("Low MFA user coverage")
    if total_gaps > 10:
        executive_summary["key_concerns"].append(f"{total_gaps} critical gaps remain")
    if days_until < 180 and completion_rate < 50:
        executive_summary["key_concerns"].append("At risk of missing deadline")

    result: dict[str, Any] = {
        "tenant_count": tenant_count,
        "security_posture_score": round(posture_score, 1),
        "maturity_metrics": {
            "average_maturity": round(avg_maturity, 1),
            "target_maturity": TARGET_MATURITY_SCORE,
            "maturity_gap": round(TARGET_MATURITY_SCORE - avg_maturity, 1),
            "total_critical_gaps": total_gaps,
        },
        "mfa_summary": {
            "average_coverage": round(avg_mfa_coverage, 1),
            "admin_coverage": round(avg_admin_mfa, 1),
            "total_unprotected_users": total_unprotected,
            "coverage_grade": "A"
            if avg_mfa_coverage >= 90
            else "B"
            if avg_mfa_coverage >= 75
            else "C"
            if avg_mfa_coverage >= 50
            else "F",
        },
        "device_summary": {
            "average_compliance": round(avg_device_compliance, 1),
            "total_devices": total_devices,
            "compliant_devices": total_compliant_devices,
            "device_compliance_rate": (
                round(total_compliant_devices / total_devices * 100, 1)
                if total_devices > 0
                else 0.0
            ),
        },
        "threat_summary": {
            "average_threat_score": round(avg_threat_score, 1),
            "total_vulnerabilities": total_vulnerabilities,
            "risk_level": "low"
            if avg_threat_score < 30
            else "medium"
            if avg_threat_score < 60
            else "high",
        },
        "requirements_summary": {
            "total": total_requirements,
            "completed": completed_requirements,
            "completion_rate": round(completion_rate, 1),
        },
        "financial_exposure": {
            "estimated_value": f"${financial_exposure:,.0f}",
            "currency": "USD",
            "base_exposure": f"${base_exposure:,.0f}",
        },
        "executive_summary": executive_summary,
    }
    return result

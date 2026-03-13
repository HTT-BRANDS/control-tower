"""Riverside Service - Query and reporting functions."""

from datetime import date, datetime

from app.api.services.riverside_service.constants import (
    ALL_TENANTS,
    RIVERSIDE_DEADLINE,
)
from app.api.services.riverside_service.models import (
    GapAnalysis,
)
from app.models.riverside import (
    RequirementCategory,
    RequirementPriority,
    RiversideCompliance,
    RiversideMFA,
    RiversideRequirement,
)
from app.models.tenant import Tenant


def _resolve_tenant_code(tenant) -> str:
    """Resolve the short code for a Tenant model.

    The Tenant SQLAlchemy model doesn't have a .code column.
    We match by tenant name against the known ALL_TENANTS config
    (a {CODE: display_name} dict with uppercase keys).

    Returns:
        Uppercase brand code (e.g. "HTT", "BCC").
    """
    # ALL_TENANTS is {CODE: name}. Reverse-lookup by exact name match.
    for code, name in ALL_TENANTS.items():
        if name == tenant.name:
            return code.upper()
    # Fallback: check if any code appears in the tenant name
    tenant_name_upper = tenant.name.upper() if tenant.name else ""
    for code in ALL_TENANTS:
        if code.upper() in tenant_name_upper:
            return code.upper()
    # Final fallback: use first 4 chars of tenant_id
    return tenant.tenant_id[:4].upper()



def get_riverside_summary(db) -> dict:
    """Get executive summary for Riverside compliance dashboard.

    Args:
        db: Database session

    Returns:
        Dict with comprehensive executive summary.
    """
    today = date.today()
    days_to_deadline = (RIVERSIDE_DEADLINE - today).days

    tenants = db.query(Tenant).filter(Tenant.is_active.is_(True)).all()

    tenant_summaries = []
    total_maturity = 0.0
    total_mfa = 0.0

    total_requirements_completed = 0
    total_requirements = 0
    total_critical_gaps = 0

    for tenant in tenants:
        compliance = db.query(RiversideCompliance).filter(
            RiversideCompliance.tenant_id == tenant.tenant_id
        ).order_by(RiversideCompliance.updated_at.desc()).first()

        mfa = db.query(RiversideMFA).filter(
            RiversideMFA.tenant_id == tenant.tenant_id
        ).order_by(RiversideMFA.snapshot_date.desc()).first()

        # NOTE: Device compliance disabled - Sui Generis MSP integration coming in Phase 2 (Q3 2025)
        # device = db.query(RiversideDeviceCompliance).filter(
        #     RiversideDeviceCompliance.tenant_id == tenant.tenant_id
        # ).order_by(RiversideDeviceCompliance.snapshot_date.desc()).first()

        maturity_score = compliance.overall_maturity_score if compliance else 0.0
        mfa_coverage = mfa.mfa_coverage_percentage if mfa else 0.0
        # device_compliance = device.compliance_percentage if device else 0.0
        reqs_completed = compliance.requirements_completed if compliance else 0
        reqs_total = compliance.requirements_total if compliance else 0
        gaps = compliance.critical_gaps_count if compliance else 0

        tenant_code = _resolve_tenant_code(tenant)
        tenant_name = ALL_TENANTS.get(tenant_code, tenant.name)

        tenant_summaries.append({
            "tenant_id": tenant.tenant_id,
            "tenant_code": tenant_code,
            "tenant_name": tenant_name,
            "maturity_score": maturity_score,
            "mfa_coverage": mfa_coverage,
            "admin_mfa_pct": mfa.admin_mfa_percentage if mfa else 0.0,
            "device_compliance": {
                "status": "coming_soon",
                "message": "Device compliance via Sui Generis MSP (Phase 2, Q3 2025)",
                "enabled": False,
            },
            "requirements_completed": reqs_completed,
            "requirements_total": reqs_total,
            "critical_gaps": gaps,
        })

        total_maturity += maturity_score
        total_mfa += mfa_coverage
        # total_device += device_compliance  # Disabled - Sui Generis Phase 2
        total_requirements_completed += reqs_completed
        total_requirements += reqs_total
        total_critical_gaps += gaps

    num_tenants = len(tenants) if tenants else 1

    # Calculate requirements by status
    requirements_by_status = {
        "not_started": db.query(RiversideRequirement).filter(
            RiversideRequirement.status == "not_started"
        ).count(),
        "in_progress": db.query(RiversideRequirement).filter(
            RiversideRequirement.status == "in_progress"
        ).count(),
        "completed": db.query(RiversideRequirement).filter(
            RiversideRequirement.status == "completed"
        ).count(),
        "blocked": db.query(RiversideRequirement).filter(
            RiversideRequirement.status == "blocked"
        ).count(),
    }

    # Calculate requirements by category
    requirements_by_category = {}
    for category in RequirementCategory:
        cat_reqs = db.query(RiversideRequirement).filter(
            RiversideRequirement.category == category.value
        )
        requirements_by_category[category.value] = {
            "total": cat_reqs.count(),
            "completed": cat_reqs.filter(RiversideRequirement.status == "completed").count(),
        }

    # Calculate requirements by priority
    requirements_by_priority = {}
    for priority in RequirementPriority:
        pri_reqs = db.query(RiversideRequirement).filter(
            RiversideRequirement.priority == priority.value
        )
        requirements_by_priority[priority.value] = {
            "total": pri_reqs.count(),
            "completed": pri_reqs.filter(RiversideRequirement.status == "completed").count(),
        }

    critical_gaps = _get_critical_gaps(db)

    return {
        "deadline_date": RIVERSIDE_DEADLINE.isoformat(),
        "days_until_deadline": days_to_deadline,
        "financial_risk": "$4M",
        "target_maturity": 3.0,
        "overall_maturity": round(total_maturity / num_tenants, 2),
        "overall_mfa_coverage": round(total_mfa / num_tenants, 1),
        "overall_device_compliance": {
            "status": "coming_soon",
            "message": "Device compliance monitoring via Sui Generis MSP integration (Phase 2, Q3 2025)",
            "enabled": False,
        },
        "total_requirements_completed": total_requirements_completed,
        "total_requirements": total_requirements,
        "overall_completion_pct": round(
            (total_requirements_completed / total_requirements * 100), 1
        ) if total_requirements > 0 else 0,
        "total_critical_gaps": total_critical_gaps,
        "tenant_count": len(tenants),
        "tenant_summaries": tenant_summaries,
        "requirements_by_status": requirements_by_status,
        "requirements_by_category": requirements_by_category,
        "requirements_by_priority": requirements_by_priority,
        "critical_gaps": [g.__dict__ for g in critical_gaps],
        "last_updated": datetime.utcnow().isoformat(),
    }


def get_mfa_status(db) -> dict:
    """Get detailed MFA status for all tenants.

    Args:
        db: Database session

    Returns:
        Dict with MFA metrics.
    """
    tenants = db.query(Tenant).filter(Tenant.is_active.is_(True)).all()

    tenant_mfa = []
    total_users = 0
    total_mfa_enrolled = 0
    total_admin_accounts = 0
    total_admin_mfa = 0

    for tenant in tenants:
        mfa = db.query(RiversideMFA).filter(
            RiversideMFA.tenant_id == tenant.tenant_id
        ).order_by(RiversideMFA.snapshot_date.desc()).first()

        if mfa:
            total_users += mfa.total_users
            total_mfa_enrolled += mfa.mfa_enrolled_users
            total_admin_accounts += mfa.admin_accounts_total
            total_admin_mfa += mfa.admin_accounts_mfa

            tenant_code = _resolve_tenant_code(tenant)
            tenant_name = ALL_TENANTS.get(tenant_code, tenant.name)

            tenant_mfa.append({
                "tenant_id": tenant.tenant_id,
                "tenant_code": tenant_code,
                "tenant_name": tenant_name,
                "total_users": mfa.total_users,
                "mfa_enrolled": mfa.mfa_enrolled_users,
                "mfa_coverage_pct": mfa.mfa_coverage_percentage,
                "admin_accounts": mfa.admin_accounts_total,
                "admin_mfa": mfa.admin_accounts_mfa,
                "admin_mfa_pct": mfa.admin_mfa_percentage,
                "unprotected_users": mfa.unprotected_users,
                "snapshot_date": mfa.snapshot_date.isoformat() if mfa.snapshot_date else None,
            })

    return {
        "summary": {
            "total_users": total_users,
            "mfa_enrolled": total_mfa_enrolled,
            "overall_coverage_pct": round(
                (total_mfa_enrolled / total_users * 100), 1
            ) if total_users > 0 else 0,
            "admin_accounts": total_admin_accounts,
            "admin_mfa": total_admin_mfa,
            "admin_mfa_pct": round(
                (total_admin_mfa / total_admin_accounts * 100), 1
            ) if total_admin_accounts > 0 else 0,
        },
        "tenants": tenant_mfa,
        "target": 100,
        "last_updated": datetime.utcnow().isoformat(),
    }


def get_maturity_scores(db) -> dict:
    """Get maturity scores for all domains and tenants.

    Args:
        db: Database session

    Returns:
        Dict with maturity scores.
    """
    tenants = db.query(Tenant).filter(Tenant.is_active.is_(True)).all()

    tenant_scores = []
    domain_scores = {
        "IAM": [],
        "GS": [],
        "DS": [],
    }

    for tenant in tenants:
        compliance = db.query(RiversideCompliance).filter(
            RiversideCompliance.tenant_id == tenant.tenant_id
        ).order_by(RiversideCompliance.updated_at.desc()).first()

        if compliance:
            tenant_code = _resolve_tenant_code(tenant)
            tenant_name = ALL_TENANTS.get(tenant_code, tenant.name)

            # Calculate domain scores based on requirements
            iam_reqs = db.query(RiversideRequirement).filter(
                RiversideRequirement.tenant_id == tenant.tenant_id,
                RiversideRequirement.category == "IAM"
            )
            gs_reqs = db.query(RiversideRequirement).filter(
                RiversideRequirement.tenant_id == tenant.tenant_id,
                RiversideRequirement.category == "GS"
            )
            ds_reqs = db.query(RiversideRequirement).filter(
                RiversideRequirement.tenant_id == tenant.tenant_id,
                RiversideRequirement.category == "DS"
            )

            iam_total = iam_reqs.count()
            iam_completed = iam_reqs.filter(RiversideRequirement.status == "completed").count()
            iam_score = (iam_completed / iam_total * 5) if iam_total > 0 else 0

            gs_total = gs_reqs.count()
            gs_completed = gs_reqs.filter(RiversideRequirement.status == "completed").count()
            gs_score = (gs_completed / gs_total * 5) if gs_total > 0 else 0

            ds_total = ds_reqs.count()
            ds_completed = ds_reqs.filter(RiversideRequirement.status == "completed").count()
            ds_score = (ds_completed / ds_total * 5) if ds_total > 0 else 0

            domain_scores["IAM"].append(iam_score)
            domain_scores["GS"].append(gs_score)
            domain_scores["DS"].append(ds_score)

            tenant_scores.append({
                "tenant_id": tenant.tenant_id,
                "tenant_code": tenant_code,
                "tenant_name": tenant_name,
                "overall_maturity": compliance.overall_maturity_score,
                "target_maturity": compliance.target_maturity_score,
                "domain_scores": {
                    "IAM": round(iam_score, 2),
                    "GS": round(gs_score, 2),
                    "DS": round(ds_score, 2),
                },
                "critical_gaps": compliance.critical_gaps_count,
                "last_assessment": compliance.last_assessment_date.isoformat() if compliance.last_assessment_date else None,
            })

    return {
        "summary": {
            "overall_average": round(
                sum(t["overall_maturity"] for t in tenant_scores) / len(tenant_scores), 2
            ) if tenant_scores else 0,
            "target": 3.0,
            "iam_average": round(sum(domain_scores["IAM"]) / len(domain_scores["IAM"]), 2) if domain_scores["IAM"] else 0,
            "gs_average": round(sum(domain_scores["GS"]) / len(domain_scores["GS"]), 2) if domain_scores["GS"] else 0,
            "ds_average": round(sum(domain_scores["DS"]) / len(domain_scores["DS"]), 2) if domain_scores["DS"] else 0,
        },
        "tenants": tenant_scores,
        "deadline": RIVERSIDE_DEADLINE.isoformat(),
        "days_remaining": (RIVERSIDE_DEADLINE - date.today()).days,
    }


def get_requirements(db, category: str | None = None, priority: str | None = None, status: str | None = None) -> dict:
    """Get requirements list with optional filtering.

    Args:
        db: Database session
        category: Filter by category (IAM, GS, DS)
        priority: Filter by priority (P0, P1, P2)
        status: Filter by status (not_started, in_progress, completed, blocked)

    Returns:
        Dict with filtered requirements.
    """
    query = db.query(RiversideRequirement)

    if category:
        query = query.filter(RiversideRequirement.category == category)
    if priority:
        query = query.filter(RiversideRequirement.priority == priority)
    if status:
        query = query.filter(RiversideRequirement.status == status)

    requirements = query.all()

    results = []
    for req in requirements:
        tenant = db.query(Tenant).filter(Tenant.tenant_id == req.tenant_id).first()
        tenant_code = _resolve_tenant_code(tenant) if tenant else "N/A"

        results.append({
            "id": req.id,
            "requirement_id": req.requirement_id,
            "title": req.title,
            "description": req.description,
            "category": req.category,
            "priority": req.priority,
            "status": req.status,
            "tenant_id": req.tenant_id,
            "tenant_code": tenant_code,
            "due_date": req.due_date.isoformat() if req.due_date else None,
            "completed_date": req.completed_date.isoformat() if req.completed_date else None,
            "owner": req.owner,
            "evidence_url": req.evidence_url,
            "evidence_notes": req.evidence_notes,
            "created_at": req.created_at.isoformat() if req.created_at else None,
            "updated_at": req.updated_at.isoformat() if req.updated_at else None,
        })

    stats = {
        "total": len(results),
        "by_status": {
            "not_started": sum(1 for r in results if r["status"] == "not_started"),
            "in_progress": sum(1 for r in results if r["status"] == "in_progress"),
            "completed": sum(1 for r in results if r["status"] == "completed"),
            "blocked": sum(1 for r in results if r["status"] == "blocked"),
        },
        "by_priority": {
            "P0": sum(1 for r in results if r["priority"] == "P0"),
            "P1": sum(1 for r in results if r["priority"] == "P1"),
            "P2": sum(1 for r in results if r["priority"] == "P2"),
        },
    }

    return {
        "requirements": results,
        "stats": stats,
        "filters": {
            "category": category,
            "priority": priority,
            "status": status,
        },
    }


def get_gaps(db) -> dict:
    """Get critical gaps analysis.

    Args:
        db: Database session

    Returns:
        Dict with critical gaps identified.
    """
    gaps = _get_critical_gaps(db)

    immediate_action = []
    high_priority = []
    medium_priority = []

    today = date.today()

    for gap in gaps:
        priority = gap.priority
        due_date = gap.due_date

        is_overdue = False
        if due_date:
            try:
                due = date.fromisoformat(due_date) if isinstance(due_date, str) else due_date
                is_overdue = due < today
            except (ValueError, TypeError):
                pass

        if priority == "P0" or is_overdue:
            immediate_action.append(gap.__dict__)
        elif priority == "P1":
            high_priority.append(gap.__dict__)
        else:
            medium_priority.append(gap.__dict__)

    return {
        "summary": {
            "total_gaps": len(gaps),
            "immediate_action": len(immediate_action),
            "high_priority": len(high_priority),
            "medium_priority": len(medium_priority),
        },
        "immediate_action": immediate_action[:10],
        "high_priority": high_priority[:10],
        "medium_priority": medium_priority[:10],
        "deadline": RIVERSIDE_DEADLINE.isoformat(),
        "days_remaining": (RIVERSIDE_DEADLINE - today).days,
        "financial_risk": "$4M",
    }


def _get_critical_gaps(db) -> list[GapAnalysis]:
    """Get list of critical compliance gaps.

    Args:
        db: Database session

    Returns:
        List of gap analysis objects.
    """
    gaps = []
    today = date.today()

    # Get all incomplete P0 requirements
    p0_requirements = db.query(RiversideRequirement).filter(
        RiversideRequirement.priority == "P0",
        RiversideRequirement.status != "completed"
    ).all()

    for req in p0_requirements:
        tenant = db.query(Tenant).filter(Tenant.tenant_id == req.tenant_id).first()
        tenant_code = _resolve_tenant_code(tenant) if tenant else "N/A"

        is_overdue = False
        days_overdue = 0
        if req.due_date:
            days_overdue = (today - req.due_date).days
            is_overdue = days_overdue > 0

        gaps.append(GapAnalysis(
            requirement_id=req.requirement_id,
            title=req.title,
            category=req.category,
            priority=req.priority,
            status=req.status,
            tenant_id=req.tenant_id,
            tenant_code=tenant_code,
            due_date=req.due_date.isoformat() if req.due_date else None,
            is_overdue=is_overdue,
            days_overdue=days_overdue if is_overdue else 0,
            risk_level="Critical" if is_overdue else "High",
            description=req.description,
        ))

    # Get P1 requirements that are overdue
    overdue_p1 = db.query(RiversideRequirement).filter(
        RiversideRequirement.priority == "P1",
        RiversideRequirement.status != "completed",
        RiversideRequirement.due_date < today
    ).all()

    for req in overdue_p1:
        tenant = db.query(Tenant).filter(Tenant.tenant_id == req.tenant_id).first()
        tenant_code = _resolve_tenant_code(tenant) if tenant else "N/A"

        days_overdue = (today - req.due_date).days if req.due_date else 0

        gaps.append(GapAnalysis(
            requirement_id=req.requirement_id,
            title=req.title,
            category=req.category,
            priority=req.priority,
            status=req.status,
            tenant_id=req.tenant_id,
            tenant_code=tenant_code,
            due_date=req.due_date.isoformat() if req.due_date else None,
            is_overdue=True,
            days_overdue=days_overdue,
            risk_level="High",
            description=req.description,
        ))

    return gaps

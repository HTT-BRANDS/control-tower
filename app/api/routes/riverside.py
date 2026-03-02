"""Riverside compliance API routes.

REST API endpoints for Riverside Company compliance tracking
with the July 8, 2026 deadline across HTT, BCC, FN, TLL tenants.
"""

from datetime import date, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.identity import IdentitySnapshot, PrivilegedUser
from app.models.riverside import (
    RequirementStatus,
    RiversideCompliance,
    RiversideMFA,
    RiversideRequirement,
)
from app.schemas.riverside import (
    RequirementCategory,
    RequirementPriority,
    RiversideComplianceResponse,
    RiversideDashboardSummary,
    RiversideMFAResponse,
    RiversideRequirementResponse,
    RiversideRequirementUpdate,
    RiversideTenantSummary,
)
from app.schemas.riverside import (
    RequirementStatus as RequirementStatusEnum,
)

router = APIRouter(prefix="/api/v1/riverside", tags=["riverside"])


@router.get("/compliance", response_model=list[RiversideComplianceResponse])
async def list_compliance_records(
    db: Annotated[Session, Depends(get_db)],
    tenant_id: Annotated[str | None, Query(description="Filter by tenant ID")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Number of results to return")] = 50,
    offset: Annotated[int, Query(ge=0, description="Number of results to skip")] = 0,
) -> list[RiversideComplianceResponse]:
    """List Riverside compliance records.

    Returns compliance tracking data across all Riverside tenants
    or filtered by a specific tenant.
    """
    query = db.query(RiversideCompliance)

    if tenant_id:
        query = query.filter(RiversideCompliance.tenant_id == tenant_id)

    records = query.offset(offset).limit(limit).all()
    return records  # type: ignore[return-value]


@router.get("/compliance/{id}", response_model=RiversideComplianceResponse)
async def get_compliance_record(
    id: int,
    db: Annotated[Session, Depends(get_db)],
) -> RiversideComplianceResponse:
    """Get a single compliance record by ID."""
    record = (
        db.query(RiversideCompliance)
        .filter(RiversideCompliance.id == id)
        .first()
    )

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Compliance record {id} not found",
        )

    return record


@router.get("/mfa", response_model=list[RiversideMFAResponse])
async def list_mfa_data(
    db: Annotated[Session, Depends(get_db)],
    tenant_id: Annotated[str | None, Query(description="Filter by tenant ID")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Number of results to return")] = 50,
    offset: Annotated[int, Query(ge=0, description="Number of results to skip")] = 0,
) -> list[RiversideMFAResponse]:
    """List MFA enrollment data.

    Returns multi-factor authentication coverage metrics including
    admin account protection status for Riverside tenants.
    """
    query = db.query(RiversideMFA)

    if tenant_id:
        query = query.filter(RiversideMFA.tenant_id == tenant_id)

    records = query.offset(offset).limit(limit).all()
    return records  # type: ignore


@router.get("/mfa/users")
async def list_mfa_users(
    db: Annotated[Session, Depends(get_db)],
    tenant_id: Annotated[str | None, Query(description="Filter by tenant ID")] = None,
    mfa_status: Annotated[str | None, Query(description="Filter by MFA status (enabled/disabled)")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Number of results to return")] = 50,
    offset: Annotated[int, Query(ge=0, description="Number of results to skip")] = 0,
) -> list[dict[str, Any]]:
    """List user-level MFA status.

    Returns users and their MFA enrollment status, including
    privileged users with their MFA protection status for each
    Riverside tenant.
    """
    users = []

    # Get privileged users (they have mfa_enabled field)
    privileged_query = db.query(PrivilegedUser)
    if tenant_id:
        privileged_query = privileged_query.filter(PrivilegedUser.tenant_id == tenant_id)

    # Get identity snapshots for MFA stats
    snapshot_query = db.query(IdentitySnapshot)
    if tenant_id:
        snapshot_query = snapshot_query.filter(IdentitySnapshot.tenant_id == tenant_id)

    # Get MFA enrollment data by tenant
    snapshots = snapshot_query.all()

    for snapshot in snapshots:
        # Build user data for this tenant
        tenant_users = []

        # Get privileged users for this tenant
        tenant_privileged = privileged_query.filter(
            PrivilegedUser.tenant_id == snapshot.tenant_id
        ).all()

        # Create user entries from privileged users
        for pu in tenant_privileged:
            user_entry = {
                "tenant_id": snapshot.tenant_id,
                "user_principal_name": pu.user_principal_name,
                "display_name": pu.display_name,
                "user_type": pu.user_type or "Member",
                "mfa_enabled": bool(pu.mfa_enabled),
                "is_privileged": True,
                "role_name": pu.role_name,
                "last_sign_in": pu.last_sign_in.isoformat() if pu.last_sign_in else None,
            }

            # Apply MFA status filter if provided
            if mfa_status:
                if mfa_status.lower() == "enabled" and not user_entry["mfa_enabled"]:
                    continue
                if mfa_status.lower() == "disabled" and user_entry["mfa_enabled"]:
                    continue

            tenant_users.append(user_entry)

        # Add summary record for non-privileged users
        total_users = snapshot.total_users
        privileged_count = len(tenant_privileged)
        non_privileged_count = total_users - privileged_count
        mfa_enabled_users = snapshot.mfa_enabled_users

        # Calculate non-privileged MFA status distribution
        if non_privileged_count > 0:
            # Estimate based on overall MFA stats
            privileged_with_mfa = sum(1 for u in tenant_privileged if u.mfa_enabled)
            non_privileged_mfa = max(0, mfa_enabled_users - privileged_with_mfa)

            tenant_users.append({
                "tenant_id": snapshot.tenant_id,
                "user_principal_name": f"non_privileged_users@{snapshot.tenant_id[:8]}.local",
                "display_name": f"Non-Privileged Users ({non_privileged_count} total)",
                "user_type": "Summary",
                "mfa_enabled": non_privileged_mfa > 0,
                "is_privileged": False,
                "role_name": "N/A",
                "last_sign_in": None,
                "mfa_enrolled_count": non_privileged_mfa,
                "mfa_disabled_count": non_privileged_count - non_privileged_mfa,
            })

        users.extend(tenant_users)

    # Apply pagination
    return users[offset : offset + limit]


@router.get("/deadlines")
async def list_deadlines(
    db: Annotated[Session, Depends(get_db)],
    tenant_id: Annotated[str | None, Query(description="Filter by tenant ID")] = None,
    days_ahead: Annotated[int, Query(ge=0, le=365, description="Number of days ahead to look")] = 90,
    status: Annotated[RequirementStatusEnum | None, Query(description="Filter by requirement status")] = None,
    priority: Annotated[RequirementPriority | None, Query(description="Filter by priority")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Number of results to return")] = 50,
    offset: Annotated[int, Query(ge=0, description="Number of results to skip")] = 0,
) -> list[dict[str, Any]]:
    """List requirements with upcoming deadlines.

    Returns compliance requirements with upcoming deadlines,
    filtered by due date range, status, and priority.
    """
    today = date.today()
    future_date = today + timedelta(days=days_ahead)

    query = db.query(RiversideRequirement)

    if tenant_id:
        query = query.filter(RiversideRequirement.tenant_id == tenant_id)

    # Filter for upcoming deadlines
    query = query.filter(
        RiversideRequirement.due_date >= today,
        RiversideRequirement.due_date <= future_date,
    )

    if status:
        query = query.filter(RiversideRequirement.status == status)
    else:
        # Default: exclude completed requirements
        query = query.filter(RiversideRequirement.status != RequirementStatus.COMPLETED)

    if priority:
        query = query.filter(RiversideRequirement.priority == priority)

    # Order by due date (closest first)
    query = query.order_by(RiversideRequirement.due_date)

    records = query.offset(offset).limit(limit).all()

    # Calculate days until deadline for each
    result = []
    for req in records:
        days_until = (req.due_date - today).days if req.due_date else None
        result.append({
            "id": req.id,
            "tenant_id": req.tenant_id,
            "requirement_id": req.requirement_id,
            "title": req.title,
            "description": req.description,
            "category": req.category.value if req.category else None,
            "priority": req.priority.value if req.priority else None,
            "status": req.status.value if req.status else None,
            "due_date": req.due_date.isoformat() if req.due_date else None,
            "days_until_deadline": days_until,
            "owner": req.owner,
            "evidence_url": req.evidence_url,
            "evidence_notes": req.evidence_notes,
        })

    return result


@router.get("/requirements", response_model=list[RiversideRequirementResponse])
async def list_requirements(
    db: Annotated[Session, Depends(get_db)],
    tenant_id: Annotated[str | None, Query(description="Filter by tenant ID")] = None,
    status: Annotated[RequirementStatusEnum | None, Query(description="Filter by status")] = None,
    category: Annotated[RequirementCategory | None, Query(description="Filter by category")] = None,
    priority: Annotated[RequirementPriority | None, Query(description="Filter by priority")] = None,
    due_date_from: Annotated[date | None, Query(description="Filter by due date (start)")] = None,
    due_date_to: Annotated[date | None, Query(description="Filter by due date (end)")] = None,
    owner: Annotated[str | None, Query(description="Filter by owner")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Number of results to return")] = 50,
    offset: Annotated[int, Query(ge=0, description="Number of results to skip")] = 0,
) -> list[RiversideRequirementResponse]:
    """List compliance requirements.

    Returns Riverside compliance requirements with optional filtering
    by status, category, priority, due date range, or owner.
    """
    query = db.query(RiversideRequirement)

    if tenant_id:
        query = query.filter(RiversideRequirement.tenant_id == tenant_id)

    if status:
        query = query.filter(RiversideRequirement.status == status)

    if category:
        query = query.filter(RiversideRequirement.category == category)

    if priority:
        query = query.filter(RiversideRequirement.priority == priority)

    if due_date_from:
        query = query.filter(RiversideRequirement.due_date >= due_date_from)

    if due_date_to:
        query = query.filter(RiversideRequirement.due_date <= due_date_to)

    if owner:
        query = query.filter(RiversideRequirement.owner.ilike(f"%{owner}%"))

    records = query.offset(offset).limit(limit).all()
    return records  # type: ignore[return-value]


@router.patch("/requirements/{id}", response_model=RiversideRequirementResponse)
async def update_requirement(
    id: int,
    update_data: RiversideRequirementUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> RiversideRequirementResponse:
    """Update a requirement.

    Partial update for modifying requirement status, ownership,
    due dates, evidence, and other fields.
    """
    requirement = (
        db.query(RiversideRequirement)
        .filter(RiversideRequirement.id == id)
        .first()
    )

    if not requirement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requirement {id} not found",
        )

    # Apply updates
    update_dict = update_data.model_dump(exclude_unset=True)

    # Handle status change and completed_date
    if "status" in update_dict:
        new_status = update_dict["status"]
        if new_status == RequirementStatus.COMPLETED and requirement.status != RequirementStatus.COMPLETED:
            update_dict["completed_date"] = date.today()
        elif new_status != RequirementStatus.COMPLETED:
            update_dict["completed_date"] = None

    for field, value in update_dict.items():
        setattr(requirement, field, value)

    db.commit()
    db.refresh(requirement)

    return requirement


@router.get("/dashboard", response_model=RiversideDashboardSummary)
async def get_dashboard_summary(
    db: Annotated[Session, Depends(get_db)],
) -> RiversideDashboardSummary:
    """Get executive dashboard summary.

    Returns aggregated compliance metrics across all Riverside tenants
    including maturity scores, requirement completion, MFA coverage,
    device compliance, and risk exposure data.
    """
    # Get all compliance records
    compliance_records = db.query(RiversideCompliance).all()
    mfa_records = db.query(RiversideMFA).all()
    requirements = db.query(RiversideRequirement).all()

    if not compliance_records:
        # Return empty dashboard if no data
        return RiversideDashboardSummary(
            total_tenants=0,
            deadline_date=date(2026, 7, 8),
            days_until_deadline=(date(2026, 7, 8) - date.today()).days,
            overall_maturity_average=0.0,
            overall_maturity_target=3.0,
            total_requirements_completed=0,
            total_requirements=0,
            overall_completion_percentage=0.0,
            total_critical_gaps=0,
            average_mfa_coverage=0.0,
            average_device_compliance=0.0,
            financial_risk_exposure="$0",
            tenant_summaries=[],
            requirements_by_category={},
            requirements_by_priority={},
            requirements_by_status={},
        )

    # Calculate aggregate metrics
    total_tenants = len(compliance_records)
    total_maturity = sum(r.overall_maturity_score for r in compliance_records)
    avg_maturity = total_maturity / total_tenants if total_tenants > 0 else 0.0

    total_requirements_completed = sum(r.requirements_completed for r in compliance_records)
    total_requirements = sum(r.requirements_total for r in compliance_records)
    completion_pct = (
        (total_requirements_completed / total_requirements * 100)
        if total_requirements > 0 else 0.0
    )

    total_critical_gaps = sum(r.critical_gaps_count for r in compliance_records)

    # MFA coverage average
    avg_mfa = (
        sum(m.mfa_coverage_percentage for m in mfa_records) / len(mfa_records)
        if mfa_records else 0.0
    )

    # Build tenant summaries
    tenant_summaries = []
    for record in compliance_records:
        # Find matching MFA record
        mfa_record = next(
            (m for m in mfa_records if m.tenant_id == record.tenant_id),
            None,
        )

        completion = (
            (record.requirements_completed / record.requirements_total * 100)
            if record.requirements_total > 0 else 0.0
        )

        tenant_summaries.append(
            RiversideTenantSummary(
                tenant_id=record.tenant_id,
                tenant_name=record.tenant_id[:8],  # Placeholder, should look up actual name
                overall_maturity_score=record.overall_maturity_score,
                requirements_completed=record.requirements_completed,
                requirements_total=record.requirements_total,
                completion_percentage=round(completion, 1),
                mfa_coverage_percentage=mfa_record.mfa_coverage_percentage if mfa_record else 0.0,
                admin_mfa_percentage=mfa_record.admin_mfa_percentage if mfa_record else 0.0,
                device_compliance_percentage=0.0,  # Would need device compliance data
                critical_gaps_count=record.critical_gaps_count,
                days_until_deadline=(record.deadline_date - date.today()).days,
            )
        )

    # Requirements by category
    category_stats = {}
    for cat in RequirementCategory:
        cat_reqs = [r for r in requirements if r.category.value == cat.value]
        completed = len([r for r in cat_reqs if r.status == RequirementStatus.COMPLETED])
        category_stats[cat.value] = {"completed": completed, "total": len(cat_reqs)}

    # Requirements by priority
    priority_stats = {}
    for pri in RequirementPriority:
        pri_reqs = [r for r in requirements if r.priority.value == pri.value]
        completed = len([r for r in pri_reqs if r.status == RequirementStatus.COMPLETED])
        priority_stats[pri.value] = {"completed": completed, "total": len(pri_reqs)}

    # Requirements by status
    status_stats = {}
    for req_status in RequirementStatus:
        count = len([r for r in requirements if r.status == req_status])
        status_stats[req_status.value] = count

    # Calculate financial risk exposure
    # Assuming $4M per tenant based on model default
    total_financial_risk = f"${total_tenants * 4}M"

    deadline = compliance_records[0].deadline_date if compliance_records else date(2026, 7, 8)
    days_until = (deadline - date.today()).days

    return RiversideDashboardSummary(
        total_tenants=total_tenants,
        deadline_date=deadline,
        days_until_deadline=days_until,
        overall_maturity_average=round(avg_maturity, 1),
        overall_maturity_target=3.0,
        total_requirements_completed=total_requirements_completed,
        total_requirements=total_requirements,
        overall_completion_percentage=round(completion_pct, 1),
        total_critical_gaps=total_critical_gaps,
        average_mfa_coverage=round(avg_mfa, 1),
        average_device_compliance=0.0,  # Would need device compliance data
        financial_risk_exposure=total_financial_risk,
        tenant_summaries=tenant_summaries,
        requirements_by_category=category_stats,
        requirements_by_priority=priority_stats,
        requirements_by_status=status_stats,
    )

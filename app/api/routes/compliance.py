"""Compliance monitoring API routes."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.services.compliance_service import ComplianceService
from app.core.auth import User, get_current_user
from app.core.authorization import (
    TenantAuthorization,
    get_tenant_authorization,
    validate_tenant_access,
    validate_tenants_access,
)
from app.core.database import get_db
from app.models.compliance import PolicyState
from app.schemas.compliance import ComplianceScore, ComplianceSummary, PolicyStatus

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/v1/compliance",
    tags=["compliance"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/summary", response_model=ComplianceSummary)
async def get_compliance_summary(
    tenant_ids: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get aggregated compliance summary across all tenants.

    Args:
        tenant_ids: Filter by specific tenants
    """
    authz.ensure_at_least_one_tenant()

    # Filter tenant_ids to only accessible ones
    filtered_tenant_ids = authz.filter_tenant_ids(tenant_ids)

    service = ComplianceService(db)
    # TODO: Filter by accessible tenants
    return await service.get_compliance_summary()


@router.get("/scores", response_model=list[ComplianceScore])
async def get_compliance_scores(
    tenant_id: str | None = Query(default=None),
    tenant_ids: list[str] | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get compliance scores, optionally filtered by tenant.

    Args:
        tenant_id: Single tenant filter (deprecated, use tenant_ids)
        tenant_ids: Filter by specific tenants
        limit: Maximum results to return
        offset: Pagination offset
    """
    authz.ensure_at_least_one_tenant()

    # Validate and filter tenant access
    if tenant_id:
        authz.validate_access(tenant_id)

    filtered_tenant_ids = authz.filter_tenant_ids(tenant_ids)

    service = ComplianceService(db)
    scores = await service.get_scores_by_tenant(tenant_id=tenant_id)

    # Apply tenant isolation
    accessible_tenants = authz.accessible_tenant_ids
    # Empty accessible_tenants means admin can see all
    if accessible_tenants:
        scores = [
            s for s in scores
            if s.tenant_id in accessible_tenants and (not filtered_tenant_ids or s.tenant_id in filtered_tenant_ids)
        ]
    elif filtered_tenant_ids:
        # Admin with specific filter
        scores = [s for s in scores if s.tenant_id in filtered_tenant_ids]

    return scores[offset : offset + limit]


@router.get("/non-compliant", response_model=list[PolicyStatus])
async def get_non_compliant_policies(
    tenant_id: str | None = Query(default=None),
    tenant_ids: list[str] | None = Query(default=None),
    severity: str | None = Query(default=None, pattern="^(High|Medium|Low)$"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="non_compliant_count"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get non-compliant policy details.

    Args:
        tenant_id: Single tenant filter (deprecated, use tenant_ids)
        tenant_ids: Filter by specific tenants
        severity: Filter by severity level
        limit: Maximum results to return
        offset: Pagination offset
        sort_by: Field to sort by
        sort_order: Sort direction (asc or desc)
    """
    authz.ensure_at_least_one_tenant()

    # Validate and filter tenant access
    if tenant_id:
        authz.validate_access(tenant_id)

    filtered_tenant_ids = authz.filter_tenant_ids(tenant_ids)

    service = ComplianceService(db)
    policies = service.get_non_compliant_policies(tenant_id=tenant_id)

    # Apply tenant isolation
    accessible_tenants = authz.accessible_tenant_ids
    # Empty accessible_tenants means admin can see all
    if accessible_tenants:
        policies = [
            p for p in policies
            if p.tenant_id in accessible_tenants and (not filtered_tenant_ids or p.tenant_id in filtered_tenant_ids)
        ]
    elif filtered_tenant_ids:
        # Admin with specific filter
        policies = [p for p in policies if p.tenant_id in filtered_tenant_ids]

    if severity:
        policies = [p for p in policies if p.severity == severity]

    return policies[offset : offset + limit]


@router.get("/trends")
async def get_compliance_trends(
    tenant_ids: list[str] | None = Query(default=None),
    days: int = Query(default=30, ge=7, le=365),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get compliance score trends over time.

    Args:
        tenant_ids: Filter by specific tenants
        days: Number of days of history to analyze
    """
    authz.ensure_at_least_one_tenant()

    # Filter tenant_ids to only accessible ones
    filtered_tenant_ids = authz.filter_tenant_ids(tenant_ids)

    service = ComplianceService(db)
    return await service.get_compliance_trends(tenant_ids=filtered_tenant_ids, days=days)


@router.get("/status")
async def compliance_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
) -> dict:
    """Get compliance synchronization status.

    Returns:
        Dictionary with compliance status metrics
    """
    try:
        authz.ensure_at_least_one_tenant()
        accessible_tenant_ids = authz.accessible_tenant_ids

        # Get total policy states for accessible tenants
        total_states = (
            db.query(PolicyState)
            .filter(PolicyState.tenant_id.in_(accessible_tenant_ids))
            .count()
        )

        # Get non-compliant policy states
        non_compliant_states = (
            db.query(PolicyState)
            .filter(
                PolicyState.tenant_id.in_(accessible_tenant_ids),
                PolicyState.compliance_state == "NonCompliant",
            )
            .count()
        )

        # Get last sync time across accessible tenants
        last_sync_result = (
            db.query(func.max(PolicyState.synced_at))
            .filter(PolicyState.tenant_id.in_(accessible_tenant_ids))
            .scalar()
        )

        # Calculate compliance score
        compliance_score = 0.0
        if total_states > 0:
            compliant_states = total_states - non_compliant_states
            compliance_score = round((compliant_states / total_states) * 100, 2)

        status = "healthy"
        if total_states == 0:
            status = "initializing"
        elif non_compliant_states > total_states * 0.1:  # >10% non-compliant
            status = "warning"

        return {
            "status": status,
            "total_findings": total_states,
            "open_findings": non_compliant_states,
            "last_sync": last_sync_result.isoformat() if last_sync_result else None,
            "compliance_score": compliance_score,
        }
    except Exception as e:
        logger.error(f"Error getting compliance status: {e}")
        return {"status": "error", "message": str(e)}

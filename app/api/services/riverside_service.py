"""Riverside Company compliance tracking service.

Business logic service for Riverside operations including compliance calculations,
MFA enrollment tracking, requirement management, and dashboard data aggregation.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any, cast

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models.riverside import (
    RequirementCategory,
    RequirementPriority,
    RequirementStatus,
    RiversideCompliance,
    RiversideDeviceCompliance,
    RiversideMFA,
    RiversideRequirement,
)
from app.models.tenant import Tenant
from app.schemas.riverside import (
    BulkUpdateItem,
    BulkUpdateResponse,
    RiversideComplianceResponse,
    RiversideDashboardSummary,
    RiversideMFAResponse,
    RiversideRequirementResponse,
    RiversideTenantSummary,
)

logger = logging.getLogger(__name__)

# Constants
RIVERSIDE_DEADLINE = date(2026, 7, 8)
TARGET_MATURITY_SCORE = 3.0


class RiversideService:
    """Service for Riverside compliance tracking operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_compliance_summary(
        self, tenant_id: str | None = None
    ) -> list[RiversideComplianceResponse]:
        """Get compliance summary, optionally filtered by tenant.

        Args:
            tenant_id: Optional tenant ID to filter by

        Returns:
            List of compliance summary records
        """
        query = self.db.query(RiversideCompliance)

        if tenant_id:
            query = query.filter(RiversideCompliance.tenant_id == tenant_id)

        records = query.order_by(RiversideCompliance.tenant_id).all()
        return [RiversideComplianceResponse.model_validate(r) for r in records]

    def get_mfa_stats(
        self, tenant_id: str | None = None
    ) -> list[RiversideMFAResponse]:
        """Get MFA enrollment statistics, optionally filtered by tenant.

        Calculates MFA coverage percentages per tenant including admin MFA stats.

        Args:
            tenant_id: Optional tenant ID to filter by

        Returns:
            List of MFA statistics records
        """
        query = self.db.query(RiversideMFA)

        if tenant_id:
            query = query.filter(RiversideMFA.tenant_id == tenant_id)

        # Get the latest snapshot per tenant
        subquery = (
            self.db.query(
                RiversideMFA.tenant_id,
                func.max(RiversideMFA.snapshot_date).label("max_snapshot"),
            )
            .group_by(RiversideMFA.tenant_id)
            .subquery()
        )

        query = (
            self.db.query(RiversideMFA)
            .join(
                subquery,
                (RiversideMFA.tenant_id == subquery.c.tenant_id)
                & (RiversideMFA.snapshot_date == subquery.c.max_snapshot),
            )
            .order_by(RiversideMFA.tenant_id)
        )

        if tenant_id:
            query = query.filter(RiversideMFA.tenant_id == tenant_id)

        records = query.all()
        return [RiversideMFAResponse.model_validate(r) for r in records]

    def get_requirements_by_status(
        self,
        status: RequirementStatus | None = None,
        tenant_id: str | None = None,
        category: RequirementCategory | None = None,
        priority: RequirementPriority | None = None,
    ) -> list[RiversideRequirementResponse]:
        """Get requirements filtered by status and other criteria.

        Args:
            status: Filter by requirement status
            tenant_id: Optional tenant ID to filter by
            category: Optional category filter
            priority: Optional priority filter

        Returns:
            List of requirement records matching criteria
        """
        query = self.db.query(RiversideRequirement)

        if status:
            query = query.filter(RiversideRequirement.status == status)
        if tenant_id:
            query = query.filter(RiversideRequirement.tenant_id == tenant_id)
        if category:
            query = query.filter(RiversideRequirement.category == category)
        if priority:
            query = query.filter(RiversideRequirement.priority == priority)

        records = query.order_by(
            RiversideRequirement.priority,
            RiversideRequirement.due_date,
            RiversideRequirement.requirement_id,
        ).all()

        return [RiversideRequirementResponse.model_validate(r) for r in records]

    def update_requirement_status(
        self,
        requirement_id: int,
        status: RequirementStatus,
        notes: str | None = None,
        evidence_url: str | None = None,
    ) -> RiversideRequirementResponse:
        """Update the status of a requirement.

        Args:
            requirement_id: ID of the requirement to update
            status: New status value
            notes: Optional notes about the update
            evidence_url: Optional evidence URL

        Returns:
            Updated requirement record

        Raises:
            ValueError: If requirement not found
        """
        requirement = (
            self.db.query(RiversideRequirement)
            .filter(RiversideRequirement.id == requirement_id)
            .first()
        )

        if not requirement:
            raise ValueError(f"Requirement with ID {requirement_id} not found")

        requirement.status = status
        requirement.updated_at = datetime.utcnow()

        if status == RequirementStatus.COMPLETED and not requirement.completed_date:
            requirement.completed_date = date.today()

        if notes:
            if requirement.evidence_notes:
                requirement.evidence_notes = f"{requirement.evidence_notes}\n\n{notes}"
            else:
                requirement.evidence_notes = notes

        if evidence_url:
            requirement.evidence_url = evidence_url

        self.db.commit()
        self.db.refresh(requirement)

        return RiversideRequirementResponse.model_validate(requirement)

    def get_dashboard_data(self) -> RiversideDashboardSummary:
        """Get aggregated dashboard data for all Riverside tenants.

        Calculates:
        - Overall maturity averages
        - Requirements completion statistics
        - MFA coverage averages
        - Device compliance averages
        - Requirements grouped by category, priority, and status
        - Days until deadline

        Returns:
            Dashboard summary with aggregated data
        """
        # Get all Riverside tenants
        tenants = self.db.query(Tenant).filter(Tenant.is_active.is_(True)).all()

        # Get latest compliance data per tenant
        compliance_subquery = (
            self.db.query(
                RiversideCompliance.tenant_id,
                func.max(RiversideCompliance.created_at).label("max_created"),
            )
            .group_by(RiversideCompliance.tenant_id)
            .subquery()
        )

        compliance_records = {
            c.tenant_id: c
            for c in self.db.query(RiversideCompliance)
            .join(
                compliance_subquery,
                (RiversideCompliance.tenant_id == compliance_subquery.c.tenant_id)
                & (RiversideCompliance.created_at == compliance_subquery.c.max_created),
            )
            .all()
        }

        # Get latest MFA data per tenant
        mfa_subquery = (
            self.db.query(
                RiversideMFA.tenant_id,
                func.max(RiversideMFA.snapshot_date).label("max_snapshot"),
            )
            .group_by(RiversideMFA.tenant_id)
            .subquery()
        )

        mfa_records = {
            m.tenant_id: m
            for m in self.db.query(RiversideMFA)
            .join(
                mfa_subquery,
                (RiversideMFA.tenant_id == mfa_subquery.c.tenant_id)
                & (RiversideMFA.snapshot_date == mfa_subquery.c.max_snapshot),
            )
            .all()
        }

        # Get latest device compliance per tenant
        device_subquery = (
            self.db.query(
                RiversideDeviceCompliance.tenant_id,
                func.max(RiversideDeviceCompliance.snapshot_date).label("max_snapshot"),
            )
            .group_by(RiversideDeviceCompliance.tenant_id)
            .subquery()
        )

        device_records = {
            d.tenant_id: d
            for d in self.db.query(RiversideDeviceCompliance)
            .join(
                device_subquery,
                (RiversideDeviceCompliance.tenant_id == device_subquery.c.tenant_id)
                & (
                    RiversideDeviceCompliance.snapshot_date
                    == device_subquery.c.max_snapshot
                ),
            )
            .all()
        }

        # Get requirements counts per tenant
        requirements_stats = (
            self.db.query(
                RiversideRequirement.tenant_id,
                func.count(RiversideRequirement.id).label("total"),
                func.sum(
                    case(
                        (RiversideRequirement.status == RequirementStatus.COMPLETED, 1),
                        else_=0,
                    )
                ).label("completed"),
            )
            .group_by(RiversideRequirement.tenant_id)
            .all()
        )

        req_stats_by_tenant = {
            r.tenant_id: {"total": r.total, "completed": r.completed or 0}
            for r in requirements_stats
        }

        # Calculate days until deadline
        today = date.today()
        days_until = (RIVERSIDE_DEADLINE - today).days

        # Build tenant summaries
        tenant_summaries: list[RiversideTenantSummary] = []
        total_maturity = 0.0
        total_requirements = 0
        total_completed = 0
        total_mfa_coverage = 0.0
        total_device_compliance = 0.0
        total_critical_gaps = 0

        for tenant in tenants:
            comp = compliance_records.get(tenant.id)
            mfa = mfa_records.get(tenant.id)
            device = device_records.get(tenant.id)
            req_stats = req_stats_by_tenant.get(tenant.id, {"total": 0, "completed": 0})

            maturity_score = (
                comp.overall_maturity_score if comp else 0.0
            )
            mfa_coverage = mfa.mfa_coverage_percentage if mfa else 0.0
            admin_mfa = mfa.admin_mfa_percentage if mfa else 0.0
            device_compliance = device.compliance_percentage if device else 0.0
            critical_gaps = comp.critical_gaps_count if comp else 0

            req_total = req_stats["total"]
            req_completed = req_stats["completed"]
            completion_pct = (
                (req_completed / req_total * 100) if req_total > 0 else 0.0
            )

            tenant_summaries.append(
                RiversideTenantSummary(
                    tenant_id=tenant.id,
                    tenant_name=tenant.name,
                    overall_maturity_score=maturity_score,
                    requirements_completed=req_completed,
                    requirements_total=req_total,
                    completion_percentage=round(completion_pct, 1),
                    mfa_coverage_percentage=round(mfa_coverage, 1),
                    admin_mfa_percentage=round(admin_mfa, 1),
                    device_compliance_percentage=round(device_compliance, 1),
                    critical_gaps_count=critical_gaps,
                    days_until_deadline=days_until,
                )
            )

            total_maturity += maturity_score
            total_requirements += req_total
            total_completed += req_completed
            total_mfa_coverage += mfa_coverage
            total_device_compliance += device_compliance
            total_critical_gaps += critical_gaps

        # Calculate aggregates
        tenant_count = len(tenant_summaries)
        avg_maturity = (
            round(total_maturity / tenant_count, 1) if tenant_count > 0 else 0.0
        )
        avg_mfa = (
            round(total_mfa_coverage / tenant_count, 1) if tenant_count > 0 else 0.0
        )
        avg_device = (
            round(total_device_compliance / tenant_count, 1)
            if tenant_count > 0
            else 0.0
        )
        overall_completion = (
            round(total_completed / total_requirements * 100, 1)
            if total_requirements > 0
            else 0.0
        )

        # Get requirements grouped by category
        category_stats = (
            self.db.query(
                RiversideRequirement.category,
                func.count(RiversideRequirement.id).label("total"),
                func.sum(
                    case(
                        (RiversideRequirement.status == RequirementStatus.COMPLETED, 1),
                        else_=0,
                    )
                ).label("completed"),
            )
            .group_by(RiversideRequirement.category)
            .all()
        )

        requirements_by_category: dict[str, dict[str, int]] = {
            c.category.value: {"completed": c.completed or 0, "total": c.total}
            for c in category_stats
        }

        # Get requirements grouped by priority
        priority_stats = (
            self.db.query(
                RiversideRequirement.priority,
                func.count(RiversideRequirement.id).label("total"),
                func.sum(
                    case(
                        (RiversideRequirement.status == RequirementStatus.COMPLETED, 1),
                        else_=0,
                    )
                ).label("completed"),
            )
            .group_by(RiversideRequirement.priority)
            .all()
        )

        requirements_by_priority: dict[str, dict[str, int]] = {
            p.priority.value: {"completed": p.completed or 0, "total": p.total}
            for p in priority_stats
        }

        # Get requirements grouped by status
        status_stats = (
            self.db.query(
                RiversideRequirement.status,
                func.count(RiversideRequirement.id).label("count"),
            )
            .group_by(RiversideRequirement.status)
            .all()
        )

        requirements_by_status: dict[str, int] = {
            s.status.value: cast(int, s.count) for s in status_stats
        }

        return RiversideDashboardSummary(
            total_tenants=tenant_count,
            deadline_date=RIVERSIDE_DEADLINE,
            days_until_deadline=days_until,
            overall_maturity_average=avg_maturity,
            overall_maturity_target=TARGET_MATURITY_SCORE,
            total_requirements_completed=total_completed,
            total_requirements=total_requirements,
            overall_completion_percentage=overall_completion,
            total_critical_gaps=total_critical_gaps,
            average_mfa_coverage=avg_mfa,
            average_device_compliance=avg_device,
            financial_risk_exposure="$20M",
            tenant_summaries=tenant_summaries,
            requirements_by_category=requirements_by_category,
            requirements_by_priority=requirements_by_priority,
            requirements_by_status=requirements_by_status,
        )

    def bulk_update_requirements(
        self, updates: list[BulkUpdateItem]
    ) -> BulkUpdateResponse:
        """Perform bulk update operations on requirements.

        Args:
            updates: List of bulk update items containing requirement IDs
                    and field updates

        Returns:
            Bulk update response with success/failure counts
        """
        processed = 0
        succeeded = 0
        failed = 0
        errors: list[dict[str, Any]] = []

        for item in updates:
            processed += 1
            try:
                requirement = (
                    self.db.query(RiversideRequirement)
                    .filter(RiversideRequirement.id == item.id)
                    .first()
                )

                if not requirement:
                    failed += 1
                    errors.append(
                        {"id": item.id, "error": f"Requirement {item.id} not found"}
                    )
                    continue

                # Validate and apply updates
                valid_fields = {
                    "status",
                    "evidence_url",
                    "evidence_notes",
                    "due_date",
                    "owner",
                }

                for field, value in item.updates.items():
                    if field not in valid_fields:
                        continue

                    if field == "status":
                        # Validate status value
                        try:
                            requirement.status = RequirementStatus(value)
                        except ValueError:
                            failed += 1
                            errors.append(
                                {
                                    "id": item.id,
                                    "error": f"Invalid status value: {value}",
                                }
                            )
                            continue
                    elif field == "due_date" and value:
                        # Parse date string to date object
                        if isinstance(value, str):
                            requirement.due_date = date.fromisoformat(value)
                        else:
                            requirement.due_date = value
                    else:
                        setattr(requirement, field, value)

                # Update completed_date if status changed to completed
                if (
                    requirement.status == RequirementStatus.COMPLETED
                    and not requirement.completed_date
                ):
                    requirement.completed_date = date.today()

                requirement.updated_at = datetime.utcnow()
                succeeded += 1

            except Exception as e:
                failed += 1
                errors.append({"id": item.id, "error": str(e)})

        self.db.commit()

        return BulkUpdateResponse(
            processed=processed,
            succeeded=succeeded,
            failed=failed,
            errors=errors,
        )

    def get_upcoming_deadlines(
        self, days: int = 30, tenant_id: str | None = None
    ) -> list[RiversideRequirementResponse]:
        """Get requirements with upcoming deadlines.

        Args:
            days: Number of days to look ahead
            tenant_id: Optional tenant ID to filter by

        Returns:
            List of requirements with deadlines within the specified days
        """
        cutoff_date = date.today() + timedelta(days=days)

        query = self.db.query(RiversideRequirement).filter(
            RiversideRequirement.due_date <= cutoff_date,
            RiversideRequirement.due_date >= date.today(),
            RiversideRequirement.status != RequirementStatus.COMPLETED,
        )

        if tenant_id:
            query = query.filter(RiversideRequirement.tenant_id == tenant_id)

        records = query.order_by(RiversideRequirement.due_date).all()
        return [RiversideRequirementResponse.model_validate(r) for r in records]

    def get_critical_gaps(
        self, tenant_id: str | None = None
    ) -> list[RiversideRequirementResponse]:
        """Get P0 (critical) requirements that are not completed.

        Args:
            tenant_id: Optional tenant ID to filter by

        Returns:
            List of critical requirements requiring attention
        """
        query = self.db.query(RiversideRequirement).filter(
            RiversideRequirement.priority == RequirementPriority.P0,
            RiversideRequirement.status != RequirementStatus.COMPLETED,
        )

        if tenant_id:
            query = query.filter(RiversideRequirement.tenant_id == tenant_id)

        records = query.order_by(RiversideRequirement.due_date).all()
        return [RiversideRequirementResponse.model_validate(r) for r in records]

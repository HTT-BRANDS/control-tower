"""Exports API routes for CSV export functionality."""

import csv
import io
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.services.compliance_service import ComplianceService
from app.api.services.cost_service import CostService
from app.api.services.resource_service import ResourceService
from app.core.auth import get_current_user
from app.core.authorization import (
    TenantAuthorization,
    get_tenant_authorization,
)
from app.core.database import get_db

router = APIRouter(
    prefix="/api/v1/exports",
    tags=["exports"],
    dependencies=[Depends(get_current_user)],
)


def _generate_csv(data: list[dict[str, Any]], filename: str) -> StreamingResponse:
    """Generate CSV streaming response from data."""
    output = io.StringIO()
    if data:
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/costs")
async def export_costs(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    tenant_ids: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Export costs to CSV.

    Args:
        start_date: Start date for cost data (defaults to 30 days ago)
        end_date: End date for cost data (defaults to today)
        tenant_ids: Filter by specific tenants
    """
    authz.ensure_at_least_one_tenant()

    # Filter tenant_ids to only accessible ones
    filtered_tenant_ids = authz.filter_tenant_ids(tenant_ids)

    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - date.resolution * 30

    # Get cost trends for the period
    service = CostService(db)
    trends = await service.get_cost_trends(days=(end_date - start_date).days)

    # Get cost by tenant (filtered by access)
    costs_by_tenant = await service.get_costs_by_tenant(period_days=(end_date - start_date).days)

    # Build export data
    export_data = []

    # Add cost trends
    for trend in trends:
        export_data.append(
            {
                "type": "daily_cost",
                "date": trend.date.isoformat(),
                "tenant_id": "",
                "tenant_name": "",
                "cost": trend.cost,
                "currency": "USD",
            }
        )

    # Add tenant costs (filtered by tenant access)
    accessible_tenants = authz.accessible_tenant_ids
    for tenant_cost in costs_by_tenant:
        if tenant_cost.tenant_id not in accessible_tenants:
            continue
        if filtered_tenant_ids and tenant_cost.tenant_id not in filtered_tenant_ids:
            continue
        export_data.append(
            {
                "type": "tenant_summary",
                "date": end_date.isoformat(),
                "tenant_id": tenant_cost.tenant_id,
                "tenant_name": tenant_cost.tenant_name,
                "cost": tenant_cost.total_cost,
                "currency": tenant_cost.currency,
            }
        )

    filename = f"costs_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return _generate_csv(export_data, filename)


@router.get("/resources")
async def export_resources(
    tenant_ids: list[str] | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    include_orphaned: bool = Query(default=True),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Export resource inventory to CSV.

    Args:
        tenant_ids: Filter by specific tenants
        resource_type: Filter by resource type
        include_orphaned: Include orphaned resources flag
    """
    authz.ensure_at_least_one_tenant()

    # Filter tenant_ids to only accessible ones
    filtered_tenant_ids = authz.filter_tenant_ids(tenant_ids)

    service = ResourceService(db)
    inventory = await service.get_resource_inventory(
        tenant_id=filtered_tenant_ids[0]
        if filtered_tenant_ids and len(filtered_tenant_ids) == 1
        else None,
        resource_type=resource_type,
        limit=1000,
    )

    # Build export data
    export_data = []

    # Apply tenant isolation
    accessible_tenants = authz.accessible_tenant_ids
    for resource in inventory.resources:
        if resource.tenant_id not in accessible_tenants:
            continue
        if filtered_tenant_ids and resource.tenant_id not in filtered_tenant_ids:
            continue
        if not include_orphaned and resource.is_orphaned:
            continue

        export_data.append(
            {
                "resource_id": resource.id,
                "name": resource.name,
                "resource_type": resource.resource_type,
                "tenant_id": resource.tenant_id,
                "tenant_name": resource.tenant_name,
                "subscription_id": resource.subscription_id,
                "subscription_name": resource.subscription_name,
                "resource_group": resource.resource_group,
                "location": resource.location,
                "provisioning_state": resource.provisioning_state or "",
                "sku": resource.sku or "",
                "is_orphaned": "Yes" if resource.is_orphaned else "No",
                "estimated_monthly_cost": resource.estimated_monthly_cost or 0,
                "tags": ",".join(f"{k}={v}" for k, v in resource.tags.items()),
                "last_synced": resource.last_synced.isoformat() if resource.last_synced else "",
            }
        )

    filename = f"resources_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return _generate_csv(export_data, filename)


@router.get("/compliance")
async def export_compliance(
    tenant_ids: list[str] | None = Query(default=None),
    include_non_compliant: bool = Query(default=True),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Export compliance report to CSV.

    Args:
        tenant_ids: Filter by specific tenants
        include_non_compliant: Include non-compliant policies
    """
    authz.ensure_at_least_one_tenant()

    # Filter tenant_ids to only accessible ones
    filtered_tenant_ids = authz.filter_tenant_ids(tenant_ids)

    service = ComplianceService(db)

    # Get compliance summary
    summary = await service.get_compliance_summary()

    # Get non-compliant policies if requested
    non_compliant = []
    if include_non_compliant:
        non_compliant = service.get_non_compliant_policies()

    # Build export data
    export_data = []

    # Add compliance scores by tenant (filtered by access)
    accessible_tenants = authz.accessible_tenant_ids
    for score in summary.scores_by_tenant:
        if score.tenant_id not in accessible_tenants:
            continue
        if filtered_tenant_ids and score.tenant_id not in filtered_tenant_ids:
            continue
        export_data.append(
            {
                "type": "tenant_score",
                "tenant_id": score.tenant_id,
                "tenant_name": score.tenant_name,
                "subscription_id": score.subscription_id or "",
                "overall_compliance_percent": score.overall_compliance_percent,
                "secure_score": score.secure_score or 0,
                "compliant_resources": score.compliant_resources,
                "non_compliant_resources": score.non_compliant_resources,
                "exempt_resources": score.exempt_resources,
            }
        )

    # Add non-compliant policies
    for policy in non_compliant:
        if tenant_ids and policy.tenant_id not in tenant_ids:
            continue
        export_data.append(
            {
                "type": "non_compliant_policy",
                "tenant_id": policy.tenant_id,
                "policy_definition_id": policy.policy_definition_id,
                "policy_name": policy.policy_name,
                "policy_category": policy.policy_category or "",
                "compliance_state": policy.compliance_state,
                "non_compliant_count": policy.non_compliant_count,
                "subscription_id": policy.subscription_id or "",
                "recommendation": policy.recommendation or "",
            }
        )

    filename = f"compliance_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return _generate_csv(export_data, filename)

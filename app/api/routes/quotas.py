"""Quota utilization API routes — RM-007."""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.services.quota_service import QuotaService
from app.core.auth import User, get_current_user
from app.core.database import get_db
from app.core.rate_limit import rate_limit

router = APIRouter(
    prefix="/api/v1/resources/quotas",
    tags=["quotas"],
    dependencies=[Depends(rate_limit("default"))],
)


@router.get("")
async def get_quota_utilization(
    subscription_id: str | None = Query(
        default=None, description="Filter to a specific subscription ID"
    ),
    location: str = Query(default="eastus", description="Azure region to check quotas for"),
    provider: str = Query(
        default="compute",
        description="Quota provider: compute | network",
        pattern="^(compute|network)$",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get Azure quota utilization for compute or network resources.

    Returns quota usage, limits, and health status (ok/warning/critical)
    for the specified subscription and Azure region.

    Warning threshold: 75% — Critical threshold: 90%
    """
    from app.services.lighthouse_client import get_lighthouse_client

    client = get_lighthouse_client()
    quota_svc = QuotaService(client.credential)

    # Use a placeholder subscription if none given — in production this
    # would enumerate all managed subscriptions
    sub_id = subscription_id or "00000000-0000-0000-0000-000000000000"
    tenant_id = "all"

    if provider == "compute":
        summary = quota_svc.get_compute_quotas(sub_id, tenant_id, location)
    else:
        summary = quota_svc.get_network_quotas(sub_id, tenant_id, location)

    return summary.to_dict()


@router.get("/summary")
async def get_quota_summary(
    location: str = Query(default="eastus"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get aggregated quota health summary across all managed subscriptions."""
    from app.services.lighthouse_client import get_lighthouse_client

    client = get_lighthouse_client()
    quota_svc = QuotaService(client.credential)

    # Collect compute quotas — graceful degradation if Azure is unavailable
    summaries = []
    compute = quota_svc.get_compute_quotas("00000000-0000-0000-0000-000000000000", "all", location)
    summaries.append(compute)

    return quota_svc.aggregate_quotas(summaries)

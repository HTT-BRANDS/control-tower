"""Bulk operation API routes.

SECURITY FEATURES:
- Strict rate limiting on bulk operations (prevents abuse)
- Role-based access control
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.services.bulk_service import BulkService
from app.core.auth import User, get_current_user
from app.core.authorization import (
    TenantAuthorization,
    get_tenant_authorization,
)
from app.core.database import get_db
from app.core.rate_limit import rate_limit
from app.schemas.resource import (
    BulkAnomalyAcknowledgeRequest,
    BulkIdleResourceReviewRequest,
    BulkRecommendationDismissRequest,
    BulkTagOperation,
    BulkTagResponse,
)

router = APIRouter(
    prefix="/bulk",
    tags=["bulk"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "/tags/apply",
    response_model=BulkTagResponse,
    dependencies=[Depends(rate_limit("bulk"))],
)
async def bulk_apply_tags(
    operation: BulkTagOperation,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
) -> BulkTagResponse:
    """Apply tags to multiple resources.

    Supports both specific resource IDs and filter-based selection.
    Requires operator or admin role.
    """
    # Check user has appropriate role
    if not any(role in current_user.roles for role in ["admin", "operator"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bulk tag operations require operator or admin role",
        )

    authz.ensure_at_least_one_tenant()
    service = BulkService(db)
    return await service.bulk_tag_resources(operation, current_user.id)


@router.post(
    "/tags/remove",
    response_model=BulkTagResponse,
    dependencies=[Depends(rate_limit("bulk"))],
)
async def bulk_remove_tags(
    resource_ids: list[str],
    tag_names: list[str],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
) -> BulkTagResponse:
    """Remove tags from multiple resources.

    Requires operator or admin role.
    """
    # Check user has appropriate role
    if not any(role in current_user.roles for role in ["admin", "operator"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bulk tag operations require operator or admin role",
        )

    authz.ensure_at_least_one_tenant()
    service = BulkService(db)
    return await service.bulk_remove_tags(resource_ids, tag_names, current_user.id)


@router.post(
    "/anomalies/acknowledge",
    dependencies=[Depends(rate_limit("bulk"))],
)
async def bulk_acknowledge_anomalies(
    request: BulkAnomalyAcknowledgeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
) -> dict[str, Any]:
    """Acknowledge multiple cost anomalies at once."""
    authz.ensure_at_least_one_tenant()
    # Validate user has access to all anomaly tenants
    from app.models.cost import CostAnomaly

    anomalies = db.query(CostAnomaly).filter(CostAnomaly.id.in_(request.anomaly_ids)).all()
    anomaly_tenant_ids = list({a.tenant_id for a in anomalies})
    authz.validate_tenants_access(anomaly_tenant_ids)

    service = BulkService(db)
    result = await service.bulk_acknowledge_anomalies(
        request.anomaly_ids, current_user.id, request.notes
    )
    return result


@router.post(
    "/recommendations/dismiss",
    dependencies=[Depends(rate_limit("bulk"))],
)
async def bulk_dismiss_recommendations(
    request: BulkRecommendationDismissRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
) -> dict[str, Any]:
    """Dismiss multiple recommendations at once."""
    authz.ensure_at_least_one_tenant()
    # Validate user has access to all recommendation tenants
    from app.models.recommendation import Recommendation

    recommendations = (
        db.query(Recommendation).filter(Recommendation.id.in_(request.recommendation_ids)).all()
    )
    recommendation_tenant_ids = list({r.tenant_id for r in recommendations if r.tenant_id})
    authz.validate_tenants_access(recommendation_tenant_ids)

    service = BulkService(db)
    result = await service.bulk_dismiss_recommendations(
        request.recommendation_ids, current_user.id, request.reason
    )
    return result


@router.post(
    "/idle-resources/review",
    dependencies=[Depends(rate_limit("bulk"))],
)
async def bulk_review_idle_resources(
    request: BulkIdleResourceReviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
) -> dict[str, Any]:
    """Mark multiple idle resources as reviewed."""
    authz.ensure_at_least_one_tenant()
    # Validate user has access to all resource tenants
    from app.models.resource import IdleResource

    idle_resources = (
        db.query(IdleResource).filter(IdleResource.id.in_(request.idle_resource_ids)).all()
    )
    resource_tenant_ids = list({r.tenant_id for r in idle_resources})
    authz.validate_tenants_access(resource_tenant_ids)

    service = BulkService(db)
    result = await service.bulk_review_idle_resources(
        request.idle_resource_ids, current_user.id, request.notes
    )
    return result

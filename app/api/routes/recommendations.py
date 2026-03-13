"""Recommendations API routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.services.recommendation_service import RecommendationService
from app.core.auth import User, get_current_user
from app.core.authorization import (
    TenantAuthorization,
    get_tenant_authorization,
)
from app.core.database import get_db
from app.schemas.recommendation import (
    DismissRecommendationRequest,
    DismissRecommendationResponse,
    Recommendation,
    RecommendationCategory,
    RecommendationsByCategory,
    RecommendationSummary,
    SavingsPotential,
)

router = APIRouter(
    prefix="/api/v1/recommendations",
    tags=["recommendations"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[Recommendation])
async def get_recommendations(
    category: RecommendationCategory | None = Query(default=None),
    tenant_ids: list[str] | None = Query(default=None),
    impact: str | None = Query(default=None, pattern="^(Low|Medium|High|Critical)$"),
    dismissed: bool | None = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get all recommendations with optional filtering.

    Args:
        category: Filter by recommendation category
        tenant_ids: Filter by specific tenants
        impact: Filter by impact level (Low, Medium, High, Critical)
        dismissed: Include dismissed recommendations
        limit: Maximum results to return
        offset: Pagination offset
        sort_by: Field to sort by
        sort_order: Sort direction (asc or desc)
    """
    authz.ensure_at_least_one_tenant()

    # Filter tenant_ids to only accessible ones
    filtered_tenant_ids = authz.filter_tenant_ids(tenant_ids)

    service = RecommendationService(db)
    recommendations = service.get_recommendations(
        category=category,
        tenant_ids=filtered_tenant_ids,
        impact=impact,
        dismissed=dismissed,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    # Apply tenant isolation
    accessible_tenants = authz.accessible_tenant_ids
    recommendations = [r for r in recommendations if r.tenant_id in accessible_tenants]

    return recommendations


@router.get("/by-category", response_model=list[RecommendationsByCategory])
async def get_recommendations_by_category(
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get recommendations grouped by category (cost, security, performance, reliability)."""
    authz.ensure_at_least_one_tenant()
    service = RecommendationService(db)
    accessible_tenants = authz.accessible_tenant_ids
    return service.get_recommendations_by_category(tenant_ids=accessible_tenants)


@router.get("/by-tenant")
async def get_recommendations_by_tenant(
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get recommendations grouped by tenant."""
    authz.ensure_at_least_one_tenant()
    service = RecommendationService(db)
    accessible_tenants = authz.accessible_tenant_ids
    return service.get_recommendations_by_tenant(tenant_ids=accessible_tenants)


@router.get("/savings-potential", response_model=SavingsPotential)
async def get_savings_potential(
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get total potential savings across all recommendations."""
    authz.ensure_at_least_one_tenant()
    service = RecommendationService(db)
    accessible_tenants = authz.accessible_tenant_ids
    return service.get_savings_potential(tenant_ids=accessible_tenants)


@router.get("/summary", response_model=list[RecommendationSummary])
async def get_recommendation_summary(
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Get summary statistics by category."""
    authz.ensure_at_least_one_tenant()
    service = RecommendationService(db)
    accessible_tenants = authz.accessible_tenant_ids
    return service.get_recommendation_summary(tenant_ids=accessible_tenants)


@router.post("/{recommendation_id}/dismiss", response_model=DismissRecommendationResponse)
async def dismiss_recommendation(
    recommendation_id: int,
    request_data: DismissRecommendationRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
):
    """Dismiss a recommendation.

    Args:
        recommendation_id: ID of the recommendation to dismiss
        request_data: Optional dismissal reason
        current_user: User performing the dismissal
    """
    authz.ensure_at_least_one_tenant()
    # Validate user has access to recommendation's tenant
    from app.models.recommendation import Recommendation as RecommendationModel

    recommendation = (
        db.query(RecommendationModel).filter(RecommendationModel.id == recommendation_id).first()
    )
    if recommendation and recommendation.tenant_id:
        authz.validate_access(recommendation.tenant_id)

    service = RecommendationService(db)
    return service.dismiss_recommendation(
        recommendation_id=recommendation_id,
        user=current_user.id,
        reason=request_data.reason if request_data else None,
    )

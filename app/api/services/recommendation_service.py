"""Recommendations management service."""

import json
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.recommendation import Recommendation as RecommendationModel
from app.models.tenant import Tenant
from app.schemas.recommendation import (
    DismissRecommendationResponse,
    Recommendation,
    RecommendationCategory,
    RecommendationsByCategory,
    RecommendationSummary,
    SavingsPotential,
)

logger = logging.getLogger(__name__)


class RecommendationService:
    """Service for managing recommendations."""

    def __init__(self, db: Session):
        self.db = db

    def get_recommendations(
        self,
        category: RecommendationCategory | None = None,
        tenant_ids: list[str] | None = None,
        impact: str | None = None,
        dismissed: bool | None = False,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> list[Recommendation]:
        """Get recommendations with filtering and pagination."""
        query = self.db.query(RecommendationModel)

        # Apply filters
        if category:
            query = query.filter(RecommendationModel.category == category.value)
        if tenant_ids:
            query = query.filter(RecommendationModel.tenant_id.in_(tenant_ids))
        if impact:
            query = query.filter(RecommendationModel.impact == impact)
        if dismissed is not None:
            query = query.filter(RecommendationModel.is_dismissed == (1 if dismissed else 0))

        # Apply sorting
        sort_column = getattr(RecommendationModel, sort_by, RecommendationModel.created_at)
        if sort_order.lower() == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Apply pagination
        recommendations = query.offset(offset).limit(limit).all()

        # Get tenant names for display
        tenant_names = {t.id: t.name for t in self.db.query(Tenant).all()}

        return [
            Recommendation(
                id=r.id,
                tenant_id=r.tenant_id,
                tenant_name=tenant_names.get(r.tenant_id, "Unknown")
                if r.tenant_id
                else "All Tenants",
                subscription_id=r.subscription_id,
                category=RecommendationCategory(r.category),
                recommendation_type=r.recommendation_type,
                title=r.title,
                description=r.description,
                impact=r.impact,
                potential_savings_monthly=r.potential_savings_monthly,
                potential_savings_annual=r.potential_savings_annual,
                resource_id=r.resource_id,
                resource_name=r.resource_name,
                resource_type=r.resource_type,
                current_state=json.loads(r.current_state) if r.current_state else None,
                recommended_state=json.loads(r.recommended_state) if r.recommended_state else None,
                implementation_effort=r.implementation_effort,
                is_dismissed=bool(r.is_dismissed),
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in recommendations
        ]

    def get_recommendations_by_category(
        self, tenant_ids: list[str] | None = None
    ) -> list[RecommendationsByCategory]:
        """Get recommendations grouped by category.

        Args:
            tenant_ids: Optional list of tenant IDs to filter by
        """
        recommendations = self.get_recommendations(
            dismissed=False, limit=500, tenant_ids=tenant_ids
        )

        # Group by category
        by_category: dict[RecommendationCategory, list[Recommendation]] = {}
        for r in recommendations:
            if r.category not in by_category:
                by_category[r.category] = []
            by_category[r.category].append(r)

        result = []
        for category, recs in by_category.items():
            total_savings = sum((r.potential_savings_monthly or 0) for r in recs)
            result.append(
                RecommendationsByCategory(
                    category=category,
                    recommendations=recs[:50],  # Limit per category
                    count=len(recs),
                    total_potential_savings_monthly=total_savings,
                )
            )

        # Sort by potential savings
        return sorted(result, key=lambda x: x.total_potential_savings_monthly, reverse=True)

    def get_recommendations_by_tenant(
        self, tenant_ids: list[str] | None = None
    ) -> dict[str, list[Recommendation]]:
        """Get recommendations grouped by tenant.

        Args:
            tenant_ids: Optional list of tenant IDs to filter by
        """
        recommendations = self.get_recommendations(
            dismissed=False, limit=500, tenant_ids=tenant_ids
        )

        # Group by tenant
        by_tenant: dict[str, list[Recommendation]] = {}
        for r in recommendations:
            tenant_key = r.tenant_name or "Unknown"
            if tenant_key not in by_tenant:
                by_tenant[tenant_key] = []
            by_tenant[tenant_key].append(r)

        return by_tenant

    def get_savings_potential(self, tenant_ids: list[str] | None = None) -> SavingsPotential:
        """Get total potential savings across all recommendations.

        Args:
            tenant_ids: Optional list of tenant IDs to filter by
        """
        recommendations = self.get_recommendations(
            dismissed=False, limit=1000, tenant_ids=tenant_ids
        )

        total_monthly = sum((r.potential_savings_monthly or 0) for r in recommendations)
        total_annual = sum((r.potential_savings_annual or 0) for r in recommendations)

        # By category
        by_category: dict[str, float] = {}
        for r in recommendations:
            category = r.category.value
            by_category[category] = by_category.get(category, 0) + (
                r.potential_savings_monthly or 0
            )

        # By tenant
        by_tenant: dict[str, float] = {}
        for r in recommendations:
            tenant = r.tenant_name or "Unknown"
            by_tenant[tenant] = by_tenant.get(tenant, 0) + (r.potential_savings_monthly or 0)

        return SavingsPotential(
            total_potential_savings_monthly=total_monthly,
            total_potential_savings_annual=total_annual,
            by_category=by_category,
            by_tenant=by_tenant,
        )

    def get_recommendation_summary(
        self, tenant_ids: list[str] | None = None
    ) -> list[RecommendationSummary]:
        """Get summary statistics by category.

        Args:
            tenant_ids: Optional list of tenant IDs to filter by
        """
        recommendations = self.get_recommendations(
            dismissed=False, limit=1000, tenant_ids=tenant_ids
        )

        # Group by category
        by_category: dict[RecommendationCategory, list[Recommendation]] = {}
        for r in recommendations:
            if r.category not in by_category:
                by_category[r.category] = []
            by_category[r.category].append(r)

        result = []
        for category, recs in by_category.items():
            monthly_savings = sum((r.potential_savings_monthly or 0) for r in recs)
            annual_savings = sum((r.potential_savings_annual or 0) for r in recs)

            # Count by impact
            by_impact: dict[str, int] = {}
            for r in recs:
                impact = r.impact.value if hasattr(r.impact, "value") else str(r.impact)
                by_impact[impact] = by_impact.get(impact, 0) + 1

            result.append(
                RecommendationSummary(
                    category=category,
                    count=len(recs),
                    potential_savings_monthly=monthly_savings,
                    potential_savings_annual=annual_savings,
                    by_impact=by_impact,
                )
            )

        return sorted(result, key=lambda x: x.potential_savings_monthly, reverse=True)

    def dismiss_recommendation(
        self, recommendation_id: int, user: str, reason: str | None = None
    ) -> DismissRecommendationResponse:
        """Dismiss a recommendation."""
        recommendation = (
            self.db.query(RecommendationModel)
            .filter(RecommendationModel.id == recommendation_id)
            .first()
        )

        if not recommendation:
            return DismissRecommendationResponse(
                success=False,
                recommendation_id=recommendation_id,
                dismissed_at=datetime.utcnow(),
            )

        recommendation.is_dismissed = True
        recommendation.dismissed_by = user
        recommendation.dismissed_at = datetime.utcnow()
        recommendation.dismiss_reason = reason

        self.db.commit()

        return DismissRecommendationResponse(
            success=True,
            recommendation_id=recommendation_id,
            dismissed_at=datetime.utcnow(),
        )

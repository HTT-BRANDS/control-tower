"""Unit tests for RecommendationService.

Tests for recommendation management operations including:
- get_recommendations (with filtering and pagination)
- get_recommendations_by_category (grouped by category)
- get_savings_potential (total savings calculation)
- dismiss_recommendation (dismissing recommendations)

Minimum 8 tests covering all public methods and edge cases.
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from app.api.services.recommendation_service import RecommendationService
from app.models.recommendation import Recommendation as RecommendationModel
from app.models.tenant import Tenant
from app.schemas.recommendation import (
    RecommendationCategory,
    RecommendationImpact,
    ImplementationEffort,
)


class TestRecommendationService:
    """Test suite for RecommendationService."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def recommendation_service(self, mock_db):
        """Create RecommendationService instance."""
        return RecommendationService(db=mock_db)

    @pytest.fixture
    def sample_tenants(self):
        """Create sample tenants."""
        tenants = []
        for i in range(3):
            tenant = MagicMock(spec=Tenant)
            tenant.id = f"tenant-{i+1}"
            tenant.name = f"Tenant {i+1}"
            tenants.append(tenant)
        return tenants

    @pytest.fixture
    def sample_recommendations(self):
        """Create sample recommendations."""
        recommendations = []
        categories = [
            RecommendationCategory.COST_OPTIMIZATION.value,
            RecommendationCategory.SECURITY.value,
            RecommendationCategory.PERFORMANCE.value,
            RecommendationCategory.RELIABILITY.value,
        ]
        impacts = ["Low", "Medium", "High", "Critical"]
        
        for i in range(12):
            rec = MagicMock(spec=RecommendationModel)
            rec.id = i + 1
            rec.tenant_id = f"tenant-{(i % 3) + 1}"
            rec.subscription_id = f"sub-{(i % 2) + 1}"
            rec.category = categories[i % 4]
            rec.recommendation_type = f"type_{i % 4}"
            rec.title = f"Recommendation {i + 1}"
            rec.description = f"Description for recommendation {i + 1}"
            rec.impact = impacts[i % 4]
            rec.potential_savings_monthly = (i + 1) * 100.0
            rec.potential_savings_annual = (i + 1) * 1200.0
            rec.resource_id = f"/resource/{i + 1}"
            rec.resource_name = f"Resource {i + 1}"
            rec.resource_type = f"Microsoft.Compute/virtualMachines"
            rec.current_state = json.dumps({"size": "Standard_D4s_v3"})
            rec.recommended_state = json.dumps({"size": "Standard_D2s_v3"})
            rec.implementation_effort = "Medium"
            rec.is_dismissed = 0 if i < 10 else 1  # Last 2 are dismissed
            rec.created_at = datetime.utcnow() - timedelta(days=i)
            rec.updated_at = datetime.utcnow() - timedelta(days=i)
            recommendations.append(rec)
        
        return recommendations

    def test_get_recommendations_no_filters(self, recommendation_service, mock_db, sample_recommendations, sample_tenants):
        """Test get_recommendations returns all non-dismissed recommendations by default."""
        # Setup mock query chain
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [r for r in sample_recommendations if r.is_dismissed == 0]
        
        # Setup tenant query
        tenant_query = MagicMock()
        tenant_query.all.return_value = sample_tenants
        
        # Configure db.query to return appropriate mocks
        mock_db.query.side_effect = [mock_query, tenant_query]
        
        # Execute
        result = recommendation_service.get_recommendations()
        
        # Verify
        assert len(result) == 10  # 10 non-dismissed recommendations
        assert all(not r.is_dismissed for r in result)
        assert all(r.tenant_name in ["Tenant 1", "Tenant 2", "Tenant 3"] for r in result)

    def test_get_recommendations_filter_by_category(self, recommendation_service, mock_db, sample_recommendations, sample_tenants):
        """Test get_recommendations filters by category correctly."""
        # Setup filtered recommendations (only cost optimization)
        filtered_recs = [
            r for r in sample_recommendations 
            if r.category == RecommendationCategory.COST_OPTIMIZATION.value and r.is_dismissed == 0
        ]
        
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = filtered_recs
        
        tenant_query = MagicMock()
        tenant_query.all.return_value = sample_tenants
        
        mock_db.query.side_effect = [mock_query, tenant_query]
        
        # Execute
        result = recommendation_service.get_recommendations(
            category=RecommendationCategory.COST_OPTIMIZATION
        )
        
        # Verify
        assert all(r.category == RecommendationCategory.COST_OPTIMIZATION for r in result)
        assert len(result) == len(filtered_recs)

    def test_get_recommendations_filter_by_impact(self, recommendation_service, mock_db, sample_recommendations, sample_tenants):
        """Test get_recommendations filters by impact level."""
        # Setup filtered recommendations (only high impact)
        filtered_recs = [
            r for r in sample_recommendations 
            if r.impact == "High" and r.is_dismissed == 0
        ]
        
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = filtered_recs
        
        tenant_query = MagicMock()
        tenant_query.all.return_value = sample_tenants
        
        mock_db.query.side_effect = [mock_query, tenant_query]
        
        # Execute
        result = recommendation_service.get_recommendations(impact="High")
        
        # Verify
        assert all(r.impact.value == "High" for r in result)
        assert len(result) > 0

    def test_get_recommendations_filter_by_tenant_ids(self, recommendation_service, mock_db, sample_recommendations, sample_tenants):
        """Test get_recommendations filters by tenant IDs."""
        # Setup filtered recommendations (only tenant-1)
        filtered_recs = [
            r for r in sample_recommendations 
            if r.tenant_id == "tenant-1" and r.is_dismissed == 0
        ]
        
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = filtered_recs
        
        tenant_query = MagicMock()
        tenant_query.all.return_value = sample_tenants
        
        mock_db.query.side_effect = [mock_query, tenant_query]
        
        # Execute
        result = recommendation_service.get_recommendations(tenant_ids=["tenant-1"])
        
        # Verify
        assert all(r.tenant_id == "tenant-1" for r in result)
        assert len(result) == len(filtered_recs)

    def test_get_recommendations_by_category(self, recommendation_service, mock_db, sample_recommendations, sample_tenants):
        """Test get_recommendations_by_category groups and aggregates correctly."""
        # Setup non-dismissed recommendations
        active_recs = [r for r in sample_recommendations if r.is_dismissed == 0]
        
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = active_recs
        
        tenant_query = MagicMock()
        tenant_query.all.return_value = sample_tenants
        
        mock_db.query.side_effect = [mock_query, tenant_query]
        
        # Execute
        result = recommendation_service.get_recommendations_by_category()
        
        # Verify
        assert len(result) > 0
        assert all(hasattr(r, 'category') for r in result)
        assert all(hasattr(r, 'count') for r in result)
        assert all(hasattr(r, 'total_potential_savings_monthly') for r in result)
        
        # Verify sorted by savings (descending)
        savings = [r.total_potential_savings_monthly for r in result]
        assert savings == sorted(savings, reverse=True)

    def test_get_savings_potential(self, recommendation_service, mock_db, sample_recommendations, sample_tenants):
        """Test get_savings_potential calculates totals correctly."""
        # Setup non-dismissed recommendations
        active_recs = [r for r in sample_recommendations if r.is_dismissed == 0]
        
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = active_recs
        
        tenant_query = MagicMock()
        tenant_query.all.return_value = sample_tenants
        
        mock_db.query.side_effect = [mock_query, tenant_query]
        
        # Execute
        result = recommendation_service.get_savings_potential()
        
        # Verify structure
        assert hasattr(result, 'total_potential_savings_monthly')
        assert hasattr(result, 'total_potential_savings_annual')
        assert hasattr(result, 'by_category')
        assert hasattr(result, 'by_tenant')
        
        # Calculate expected monthly total (sum of first 10: 100+200+...+1000 = 5500)
        expected_monthly = sum(r.potential_savings_monthly for r in active_recs)
        assert result.total_potential_savings_monthly == expected_monthly
        
        # Verify annual is calculated
        expected_annual = sum(r.potential_savings_annual for r in active_recs)
        assert result.total_potential_savings_annual == expected_annual
        
        # Verify by_category and by_tenant dicts are populated
        assert len(result.by_category) > 0
        assert len(result.by_tenant) > 0

    def test_dismiss_recommendation_success(self, recommendation_service, mock_db):
        """Test dismiss_recommendation successfully dismisses a recommendation."""
        # Setup mock recommendation
        mock_rec = MagicMock(spec=RecommendationModel)
        mock_rec.id = 1
        mock_rec.is_dismissed = False
        
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_rec
        
        mock_db.query.return_value = mock_query
        
        # Execute
        result = recommendation_service.dismiss_recommendation(
            recommendation_id=1,
            user="test@example.com",
            reason="Not applicable"
        )
        
        # Verify
        assert result.success is True
        assert result.recommendation_id == 1
        assert result.dismissed_at is not None
        
        # Verify recommendation was updated
        assert mock_rec.is_dismissed is True
        assert mock_rec.dismissed_by == "test@example.com"
        assert mock_rec.dismiss_reason == "Not applicable"
        assert mock_rec.dismissed_at is not None
        
        # Verify commit was called
        mock_db.commit.assert_called_once()

    def test_dismiss_recommendation_not_found(self, recommendation_service, mock_db):
        """Test dismiss_recommendation returns failure when recommendation not found."""
        # Setup mock query to return None (not found)
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        
        mock_db.query.return_value = mock_query
        
        # Execute
        result = recommendation_service.dismiss_recommendation(
            recommendation_id=999,
            user="test@example.com",
            reason="Test"
        )
        
        # Verify
        assert result.success is False
        assert result.recommendation_id == 999
        assert result.dismissed_at is not None
        
        # Verify commit was NOT called
        mock_db.commit.assert_not_called()

    def test_get_recommendations_pagination(self, recommendation_service, mock_db, sample_recommendations, sample_tenants):
        """Test get_recommendations pagination parameters work correctly."""
        # Setup paginated results (offset 5, limit 3)
        paginated_recs = sample_recommendations[5:8]
        
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = paginated_recs
        
        tenant_query = MagicMock()
        tenant_query.all.return_value = sample_tenants
        
        mock_db.query.side_effect = [mock_query, tenant_query]
        
        # Execute
        result = recommendation_service.get_recommendations(
            limit=3,
            offset=5
        )
        
        # Verify
        assert len(result) == 3
        # Verify offset and limit were called
        mock_query.offset.assert_called_once_with(5)
        mock_query.limit.assert_called_once_with(3)

    def test_get_recommendations_sorting(self, recommendation_service, mock_db, sample_recommendations, sample_tenants):
        """Test get_recommendations sorting works correctly."""
        # Setup sorted results
        sorted_recs = sorted(sample_recommendations[:10], key=lambda r: r.created_at, reverse=False)
        
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = sorted_recs
        
        tenant_query = MagicMock()
        tenant_query.all.return_value = sample_tenants
        
        mock_db.query.side_effect = [mock_query, tenant_query]
        
        # Execute
        result = recommendation_service.get_recommendations(
            sort_by="created_at",
            sort_order="asc"
        )
        
        # Verify
        assert len(result) > 0
        # Verify order_by was called
        mock_query.order_by.assert_called()

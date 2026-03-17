"""Unit tests for recommendations API routes.

Tests recommendation endpoints:
- GET /api/v1/recommendations
- GET /api/v1/recommendations/by-category
- GET /api/v1/recommendations/by-tenant
- GET /api/v1/recommendations/savings-potential
- GET /api/v1/recommendations/summary
- POST /api/v1/recommendations/{id}/dismiss
"""

import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.auth import User
from app.core.database import get_db
from app.main import app
from app.models.tenant import Tenant, UserTenant
from app.schemas.recommendation import (
    DismissRecommendationResponse,
    ImplementationEffort,
    Recommendation,
    RecommendationCategory,
    RecommendationImpact,
    RecommendationsByCategory,
    RecommendationSummary,
    SavingsPotential,
)


@pytest.fixture
def test_db_session(db_session):
    """Database session with test data."""
    tenant = Tenant(
        id=str(uuid.uuid4()),
        tenant_id="rec-tenant-123",
        name="Recommendations Test Tenant",
        is_active=True,
    )
    db_session.add(tenant)

    user_tenant = UserTenant(
        id=str(uuid.uuid4()),
        user_id="user:rec-admin",
        tenant_id=tenant.id,
        role="admin",
        is_active=True,
        can_view_costs=True,
        can_manage_resources=True,
        can_manage_compliance=True,
        granted_by="test",
        granted_at=datetime.utcnow(),
    )
    db_session.add(user_tenant)

    db_session.commit()
    return db_session


@pytest.fixture
def client_with_db(test_db_session):
    """Test client with database override."""

    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_user():
    """Mock authenticated admin user."""
    return User(
        id="user-rec-admin",
        email="admin@rec.test",
        name="Recommendations Admin",
        roles=["admin"],
        tenant_ids=["rec-tenant-123"],
        is_active=True,
        auth_provider="azure_ad",
    )


@pytest.fixture
def mock_recommendations():
    """Mock recommendation data using real Pydantic models.

    The route has response_model=list[Recommendation], so mock data
    MUST match the schema — MagicMock attributes won't cut it.
    """
    now = datetime.utcnow()
    return [
        Recommendation(
            id=1,
            tenant_id="test-tenant-123",
            tenant_name="Test Tenant",
            subscription_id="sub-123",
            category=RecommendationCategory.COST_OPTIMIZATION,
            recommendation_type="rightsizing",
            title="Resize underutilized VM",
            description="VM-Prod-01 is consistently underutilized",
            impact=RecommendationImpact.HIGH,
            potential_savings_monthly=250.00,
            potential_savings_annual=3000.00,
            resource_id="vm-prod-01",
            resource_name="VM-Prod-01",
            resource_type="Microsoft.Compute/virtualMachines",
            current_state={"sku": "Standard_D4s_v3"},
            recommended_state={"sku": "Standard_D2s_v3"},
            implementation_effort=ImplementationEffort.LOW,
            is_dismissed=False,
            created_at=now,
            updated_at=now,
        ),
        Recommendation(
            id=2,
            tenant_id="test-tenant-123",
            tenant_name="Test Tenant",
            subscription_id="sub-123",
            category=RecommendationCategory.SECURITY,
            recommendation_type="encryption",
            title="Enable disk encryption",
            description="VM-Prod-02 does not have disk encryption enabled",
            impact=RecommendationImpact.CRITICAL,
            potential_savings_monthly=0,
            potential_savings_annual=0,
            resource_id="vm-prod-02",
            resource_name="VM-Prod-02",
            resource_type="Microsoft.Compute/virtualMachines",
            current_state={"encryption": "disabled"},
            recommended_state={"encryption": "enabled"},
            implementation_effort=ImplementationEffort.MEDIUM,
            is_dismissed=False,
            created_at=now,
            updated_at=now,
        ),
    ]


def test_get_recommendations_success(authed_client, mock_recommendations):
    """Test successful retrieval of recommendations.

    NOTE: Service methods are SYNC (routes don't await them).
    """
    with patch("app.api.routes.recommendations.RecommendationService") as MockService:
        mock_service = MockService.return_value
        mock_service.get_recommendations = MagicMock(return_value=mock_recommendations)

        response = authed_client.get("/api/v1/recommendations")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["title"] == "Resize underutilized VM"
    assert data[1]["impact"] == "Critical"


def test_get_recommendations_with_filters(authed_client, mock_recommendations):
    """Test recommendations with category and impact filters."""
    cost_recs = [r for r in mock_recommendations if r.category == RecommendationCategory.COST_OPTIMIZATION]

    with patch("app.api.routes.recommendations.RecommendationService") as MockService:
        mock_service = MockService.return_value
        mock_service.get_recommendations = MagicMock(return_value=cost_recs)

        response = authed_client.get(
            "/api/v1/recommendations?category=cost_optimization&impact=High"
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    mock_service.get_recommendations.assert_called_once()
    call_kwargs = mock_service.get_recommendations.call_args[1]
    assert call_kwargs["category"] == RecommendationCategory.COST_OPTIMIZATION
    assert call_kwargs["impact"] == "High"


def test_get_recommendations_by_category(authed_client):
    """Test recommendations grouped by category.

    NOTE: get_recommendations_by_category is SYNC (route does NOT await it).
    """
    datetime.utcnow()
    mock_by_category = [
        RecommendationsByCategory(
            category=RecommendationCategory.COST_OPTIMIZATION,
            recommendations=[],
            count=15,
            total_potential_savings_monthly=5000.00,
        ),
        RecommendationsByCategory(
            category=RecommendationCategory.SECURITY,
            recommendations=[],
            count=8,
            total_potential_savings_monthly=0,
        ),
    ]

    with patch("app.api.routes.recommendations.RecommendationService") as MockService:
        mock_service = MockService.return_value
        mock_service.get_recommendations_by_category = MagicMock(return_value=mock_by_category)

        response = authed_client.get("/api/v1/recommendations/by-category")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["count"] == 15


def test_get_savings_potential(authed_client):
    """Test total savings potential calculation.

    NOTE: get_savings_potential is SYNC (route does NOT await it).
    """
    mock_savings = SavingsPotential(
        total_potential_savings_monthly=12500.00,
        total_potential_savings_annual=150000.00,
        by_category={"cost_optimization": 12500.00},
        by_tenant={"test-tenant-123": 12500.00},
    )

    with patch("app.api.routes.recommendations.RecommendationService") as MockService:
        mock_service = MockService.return_value
        mock_service.get_savings_potential = MagicMock(return_value=mock_savings)

        response = authed_client.get("/api/v1/recommendations/savings-potential")

    assert response.status_code == 200
    data = response.json()
    assert data["total_potential_savings_monthly"] == 12500.00


def test_get_recommendation_summary(authed_client):
    """Test recommendation summary statistics.

    NOTE: get_recommendation_summary is SYNC (route does NOT await it).
    """
    mock_summary = [
        RecommendationSummary(
            category=RecommendationCategory.COST_OPTIMIZATION,
            count=20,
            potential_savings_monthly=7000.00,
            potential_savings_annual=84000.00,
            by_impact={"High": 8, "Medium": 7, "Low": 5},
        ),
        RecommendationSummary(
            category=RecommendationCategory.PERFORMANCE,
            count=12,
            potential_savings_monthly=0,
            potential_savings_annual=0,
            by_impact={"High": 3, "Medium": 5, "Low": 4},
        ),
    ]

    with patch("app.api.routes.recommendations.RecommendationService") as MockService:
        mock_service = MockService.return_value
        mock_service.get_recommendation_summary = MagicMock(return_value=mock_summary)

        response = authed_client.get("/api/v1/recommendations/summary")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["count"] == 20


def test_dismiss_recommendation_success(authed_client):
    """Test successful recommendation dismissal.

    NOTE: dismiss_recommendation is SYNC (route does NOT await it).
    """
    recommendation_id = 1
    request_data = {"reason": "Not applicable for our use case"}

    mock_response = DismissRecommendationResponse(
        success=True,
        recommendation_id=recommendation_id,
        dismissed_at=datetime.utcnow(),
    )

    with patch("app.api.routes.recommendations.RecommendationService") as MockService:
        mock_service = MockService.return_value
        mock_service.dismiss_recommendation = MagicMock(return_value=mock_response)

        response = authed_client.post(
            f"/api/v1/recommendations/{recommendation_id}/dismiss",
            json=request_data,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["recommendation_id"] == recommendation_id

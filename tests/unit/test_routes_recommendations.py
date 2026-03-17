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
from app.schemas.recommendation import RecommendationCategory




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
    """Mock recommendation data."""
    return [
        MagicMock(
            id=1,
            tenant_id="test-tenant-123",
            tenant_name="Test Tenant",
            category=RecommendationCategory.COST_OPTIMIZATION,
            title="Resize underutilized VM",
            description="VM-Prod-01 is consistently underutilized",
            impact="High",
            estimated_monthly_savings=250.00,
            resource_id="vm-prod-01",
            resource_name="VM-Prod-01",
            dismissed=False,
            created_at=datetime.utcnow(),
        ),
        MagicMock(
            id=2,
            tenant_id="test-tenant-123",
            tenant_name="Test Tenant",
            category=RecommendationCategory.SECURITY,
            title="Enable disk encryption",
            description="VM-Prod-02 does not have disk encryption enabled",
            impact="Critical",
            estimated_monthly_savings=0,
            resource_id="vm-prod-02",
            resource_name="VM-Prod-02",
            dismissed=False,
            created_at=datetime.utcnow(),
        ),
    ]


def test_get_recommendations_success(authed_client, mock_recommendations):
    """Test successful retrieval of recommendations."""
    with patch("app.api.routes.recommendations.RecommendationService") as MockService:
        mock_service = MockService.return_value
        mock_service.get_recommendations.return_value = mock_recommendations

        response = authed_client.get("/api/v1/recommendations")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["title"] == "Resize underutilized VM"
    assert data[1]["impact"] == "Critical"


def test_get_recommendations_with_filters(authed_client, mock_recommendations):
    """Test recommendations with category and impact filters."""
    cost_recommendations = [
        r for r in mock_recommendations if r.category == RecommendationCategory.COST_OPTIMIZATION
    ]

    with patch("app.api.routes.recommendations.RecommendationService") as MockService:
        mock_service = MockService.return_value
        mock_service.get_recommendations.return_value = cost_recommendations

        response = authed_client.get("/api/v1/recommendations?category=cost_optimization&impact=High")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    mock_service.get_recommendations.assert_called_once()
    call_kwargs = mock_service.get_recommendations.call_args[1]
    assert call_kwargs["category"] == RecommendationCategory.COST_OPTIMIZATION
    assert call_kwargs["impact"] == "High"


def test_get_recommendations_by_category(authed_client):
    """Test recommendations grouped by category."""
    mock_by_category = [
        MagicMock(
            category=RecommendationCategory.COST_OPTIMIZATION,
            count=15,
            total_savings=5000.00,
        ),
        MagicMock(
            category=RecommendationCategory.SECURITY,
            count=8,
            total_savings=0,
        ),
    ]

    with patch("app.api.routes.recommendations.RecommendationService") as MockService:
        mock_service = MockService.return_value
        mock_service.get_recommendations_by_category.return_value = mock_by_category

        response = authed_client.get("/api/v1/recommendations/by-category")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["count"] == 15


def test_get_savings_potential(authed_client):
    """Test total savings potential calculation."""
    mock_savings = MagicMock(
        total_monthly_savings=12500.00,
        total_annual_savings=150000.00,
        recommendations_count=42,
        high_impact_count=15,
    )

    with patch("app.api.routes.recommendations.RecommendationService") as MockService:
        mock_service = MockService.return_value
        mock_service.get_savings_potential.return_value = mock_savings

        response = authed_client.get("/api/v1/recommendations/savings-potential")

    assert response.status_code == 200
    data = response.json()
    assert data["total_monthly_savings"] == 12500.00
    assert data["recommendations_count"] == 42


def test_get_recommendation_summary(authed_client):
    """Test recommendation summary statistics."""
    mock_summary = [
        MagicMock(
            category=RecommendationCategory.COST_OPTIMIZATION,
            total_count=20,
            high_impact_count=8,
            dismissed_count=2,
            avg_estimated_savings=350.00,
        ),
        MagicMock(
            category=RecommendationCategory.PERFORMANCE,
            total_count=12,
            high_impact_count=3,
            dismissed_count=1,
            avg_estimated_savings=0,
        ),
    ]

    with patch("app.api.routes.recommendations.RecommendationService") as MockService:
        mock_service = MockService.return_value
        mock_service.get_recommendation_summary.return_value = mock_summary

        response = authed_client.get("/api/v1/recommendations/summary")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["total_count"] == 20


def test_dismiss_recommendation_success(authed_client):
    """Test successful recommendation dismissal."""
    recommendation_id = 1
    request_data = {"reason": "Not applicable for our use case"}

    mock_response = MagicMock(
        success=True,
        recommendation_id=recommendation_id,
        dismissed_at=datetime.utcnow(),
        dismissed_by="user-123",
    )

    with patch("app.api.routes.recommendations.RecommendationService") as MockService:
        mock_service = MockService.return_value
        mock_service.dismiss_recommendation.return_value = mock_response

        response = authed_client.post(
            f"/api/v1/recommendations/{recommendation_id}/dismiss",
            json=request_data,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["recommendation_id"] == recommendation_id
    mock_service.dismiss_recommendation.assert_called_once_with(
        recommendation_id=recommendation_id,
        user="user-123",
        reason=request_data["reason"],
    )

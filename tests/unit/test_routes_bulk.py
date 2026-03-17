"""Unit tests for bulk operations API routes.

Tests bulk operation endpoints:
- POST /bulk/tags/apply
- POST /bulk/tags/remove
- POST /bulk/anomalies/acknowledge
- POST /bulk/recommendations/dismiss
- POST /bulk/idle-resources/review
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.auth import User
from app.core.database import get_db
from app.main import app
from app.models.tenant import Tenant, UserTenant
from app.schemas.resource import BulkTagResponse, TagOperationResult


@pytest.fixture
def test_db_session(db_session):
    """Database session with test data."""
    tenant = Tenant(
        id=str(uuid.uuid4()),
        tenant_id="bulk-tenant-123",
        name="Bulk Test Tenant",
        is_active=True,
    )
    db_session.add(tenant)

    user_tenant = UserTenant(
        id=str(uuid.uuid4()),
        user_id="user:bulk-admin",
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
def mock_viewer_user():
    """Mock authenticated viewer user (no bulk permissions)."""
    return User(
        id="user-bulk-viewer",
        email="viewer@bulk.test",
        name="Bulk Viewer",
        roles=["viewer"],
        tenant_ids=["bulk-tenant-123"],
        is_active=True,
        auth_provider="azure_ad",
    )


# ---------------------------------------------------------------------------
# Helper: Build a BulkTagResponse-compatible return value
# ---------------------------------------------------------------------------

def _tag_response(resource_ids: list[str], *, success: bool = True) -> BulkTagResponse:
    """Create a BulkTagResponse that passes Pydantic validation."""
    results = [
        TagOperationResult(
            resource_id=rid,
            resource_name=f"Resource-{rid}",
            success=success,
            message="OK" if success else "Failed",
        )
        for rid in resource_ids
    ]
    return BulkTagResponse(
        success=True,
        message="Bulk operation completed",
        total_processed=len(resource_ids),
        success_count=len(resource_ids) if success else 0,
        failed_count=0 if success else len(resource_ids),
        results=results,
    )


# ============================================================================
# POST /bulk/tags/apply
# ============================================================================


def test_bulk_apply_tags_success(authed_client):
    """Test successful bulk tag application.

    NOTE: bulk_tag_resources is ASYNC (route uses await).
    """
    request_data = {
        "resource_ids": ["res-1", "res-2", "res-3"],
        "tags": {"Environment": "Production", "Owner": "DevOps"},
    }

    mock_response = _tag_response(["res-1", "res-2", "res-3"])

    with patch("app.api.routes.bulk.BulkService") as MockBulkService:
        mock_service = MockBulkService.return_value
        mock_service.bulk_tag_resources = AsyncMock(return_value=mock_response)

        response = authed_client.post("/bulk/tags/apply", json=request_data)

    assert response.status_code == 200
    data = response.json()
    assert data["success_count"] == 3
    assert data["failed_count"] == 0


def test_bulk_apply_tags_requires_operator_role(db_session, mock_viewer_user):
    """Test that bulk tag operations require operator or admin role."""
    from unittest.mock import MagicMock

    from app.core.auth import get_current_user
    from app.core.authorization import TenantAuthorization, get_tenant_authorization

    authz = MagicMock(spec=TenantAuthorization)
    authz.user = mock_viewer_user
    authz.accessible_tenant_ids = ["bulk-tenant-123"]
    authz.ensure_at_least_one_tenant = MagicMock()

    tenant = Tenant(
        id="bulk-tenant-123",
        tenant_id="bulk-tenant-123",
        name="Bulk Test Tenant",
        is_active=True,
    )
    db_session.add(tenant)
    db_session.commit()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: mock_viewer_user
    app.dependency_overrides[get_tenant_authorization] = lambda: authz

    try:
        with patch("app.core.rate_limit.rate_limiter.check_rate_limit", new_callable=AsyncMock):
            with TestClient(app) as test_client:
                response = test_client.post(
                    "/bulk/tags/apply",
                    json={"resource_ids": ["res-1"], "tags": {"Test": "Value"}},
                )
        assert response.status_code == 403
        assert "operator or admin role" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


# ============================================================================
# POST /bulk/tags/remove
# ============================================================================


def test_bulk_remove_tags_success(authed_client):
    """Test successful bulk tag removal.

    NOTE: bulk_remove_tags is ASYNC (route uses await).
    """
    mock_response = _tag_response(["res-1", "res-2"])

    with patch("app.api.routes.bulk.BulkService") as MockBulkService:
        mock_service = MockBulkService.return_value
        mock_service.bulk_remove_tags = AsyncMock(return_value=mock_response)

        response = authed_client.post(
            "/bulk/tags/remove",
            json={
                "resource_ids": ["res-1", "res-2"],
                "tag_names": ["OldTag", "DeprecatedTag"],
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success_count"] == 2


# ============================================================================
# POST /bulk/anomalies/acknowledge
# ============================================================================


def test_bulk_acknowledge_anomalies_success(authed_client):
    """Test successful bulk anomaly acknowledgment."""
    request_data = {
        "anomaly_ids": [1, 2, 3],
        "notes": "Reviewed and acknowledged as expected spikes",
    }

    mock_response = {
        "acknowledged_count": 3,
        "failed_count": 0,
        "anomaly_ids": [1, 2, 3],
    }

    with patch("app.api.routes.bulk.BulkService") as MockBulkService:
        mock_service = MockBulkService.return_value
        mock_service.bulk_acknowledge_anomalies = AsyncMock(return_value=mock_response)

        response = authed_client.post("/bulk/anomalies/acknowledge", json=request_data)

    assert response.status_code == 200
    data = response.json()
    assert data["acknowledged_count"] == 3
    assert data["failed_count"] == 0


# ============================================================================
# POST /bulk/recommendations/dismiss
# ============================================================================


def test_bulk_dismiss_recommendations_success(authed_client):
    """Test successful bulk recommendation dismissal."""
    request_data = {
        "recommendation_ids": [10, 20, 30],
        "reason": "Not applicable for our use case",
    }

    mock_response = {
        "dismissed_count": 3,
        "failed_count": 0,
        "recommendation_ids": [10, 20, 30],
    }

    with patch("app.api.routes.bulk.BulkService") as MockBulkService:
        mock_service = MockBulkService.return_value
        mock_service.bulk_dismiss_recommendations = AsyncMock(return_value=mock_response)

        response = authed_client.post("/bulk/recommendations/dismiss", json=request_data)

    assert response.status_code == 200
    data = response.json()
    assert data["dismissed_count"] == 3


# ============================================================================
# POST /bulk/idle-resources/review
# ============================================================================


def test_bulk_review_idle_resources_success(authed_client):
    """Test successful bulk idle resource review."""
    request_data = {
        "idle_resource_ids": [1, 2, 3],
        "notes": "Resources are idle but needed for seasonal workloads",
    }

    mock_response = {
        "reviewed_count": 3,
        "failed_count": 0,
        "idle_resource_ids": [1, 2, 3],
    }

    with patch("app.api.routes.bulk.BulkService") as MockBulkService:
        mock_service = MockBulkService.return_value
        mock_service.bulk_review_idle_resources = AsyncMock(return_value=mock_response)

        response = authed_client.post("/bulk/idle-resources/review", json=request_data)

    assert response.status_code == 200
    data = response.json()
    assert data["reviewed_count"] == 3
    assert data["failed_count"] == 0

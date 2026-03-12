"""Unit tests for resource management API routes.

Tests all resource endpoints with FastAPI TestClient:
- GET /api/v1/resources
- GET /api/v1/resources/orphaned
- GET /api/v1/resources/idle
- GET /api/v1/resources/idle/summary
- POST /api/v1/resources/idle/{idle_resource_id}/tag
- GET /api/v1/resources/tagging
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.resource import (
    IdleResourceSummary,
    OrphanedResource,
    ResourceInventory,
    ResourceItem,
    TaggingCompliance,
    TagResourceResponse,
)

# ============================================================================
# GET /api/v1/resources Tests
# ============================================================================


class TestResourcesEndpoint:
    """Tests for GET /api/v1/resources endpoint."""

    @patch("app.api.routes.resources.ResourceService")
    def test_get_resources_success(self, mock_service_cls, authed_client):
        """Resources endpoint returns inventory data."""
        now = datetime.now(UTC)
        mock_svc = MagicMock()
        mock_svc.get_resource_inventory = AsyncMock(
            return_value=ResourceInventory(
                total_resources=1,
                orphaned_resources=0,
                orphaned_estimated_cost=0.0,
                resources=[
                    ResourceItem(
                        id="res-1",
                        tenant_id="test-tenant-123",
                        tenant_name="Test Tenant",
                        subscription_id="sub-123",
                        subscription_name="Sub",
                        resource_group="rg-test",
                        resource_type="Microsoft.Compute/virtualMachines",
                        name="test-vm",
                        location="eastus",
                        last_synced=now,
                    ),
                ],
            )
        )
        mock_service_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/resources")

        assert response.status_code == 200
        data = response.json()
        assert "resources" in data
        assert data["total_resources"] >= 0

    def test_get_resources_requires_auth(self, client):
        """Resources endpoint returns 401 without authentication."""
        response = client.get("/api/v1/resources")
        assert response.status_code == 401

    @patch("app.api.routes.resources.ResourceService")
    def test_get_resources_with_filters(self, mock_service_cls, authed_client):
        """Resources endpoint supports filtering."""
        mock_svc = MagicMock()
        mock_svc.get_resource_inventory = AsyncMock(
            return_value=ResourceInventory(
                total_resources=0,
                orphaned_resources=0,
                orphaned_estimated_cost=0.0,
                resources=[],
            )
        )
        mock_service_cls.return_value = mock_svc

        response = authed_client.get(
            "/api/v1/resources?resource_type=VirtualMachine&limit=100"
        )
        assert response.status_code == 200


# ============================================================================
# GET /api/v1/resources/orphaned Tests
# ============================================================================


class TestOrphanedResourcesEndpoint:
    """Tests for GET /api/v1/resources/orphaned endpoint."""

    @patch("app.api.routes.resources.ResourceService")
    def test_get_orphaned_resources_success(self, mock_service_cls, authed_client):
        """Orphaned resources endpoint returns orphaned resource list."""
        mock_svc = MagicMock()
        mock_svc.get_orphaned_resources = AsyncMock(
            return_value=[
                OrphanedResource(
                    resource_id="res-orphan-1",
                    resource_name="orphaned-disk",
                    resource_type="Microsoft.Compute/disks",
                    tenant_name="test-tenant-123",
                    subscription_name="Sub",
                    estimated_monthly_cost=10.0,
                    days_inactive=60,
                    reason="no_dependencies",
                ),
            ]
        )
        mock_service_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/resources/orphaned")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_orphaned_resources_requires_auth(self, client):
        """Orphaned resources endpoint returns 401 without authentication."""
        response = client.get("/api/v1/resources/orphaned")
        assert response.status_code == 401


# ============================================================================
# GET /api/v1/resources/idle Tests
# ============================================================================


class TestIdleResourcesEndpoint:
    """Tests for GET /api/v1/resources/idle endpoint."""

    @patch("app.api.routes.resources.ResourceService")
    def test_get_idle_resources_success(self, mock_service_cls, authed_client):
        """Idle resources endpoint returns idle resource list."""
        mock_svc = MagicMock()
        mock_svc.get_idle_resources.return_value = []  # sync in route
        mock_service_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/resources/idle")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_idle_resources_requires_auth(self, client):
        """Idle resources endpoint returns 401 without authentication."""
        response = client.get("/api/v1/resources/idle")
        assert response.status_code == 401

    @patch("app.api.routes.resources.ResourceService")
    def test_get_idle_resources_with_filters(self, mock_service_cls, authed_client):
        """Idle resources endpoint supports filtering."""
        mock_svc = MagicMock()
        mock_svc.get_idle_resources.return_value = []  # sync in route
        mock_service_cls.return_value = mock_svc

        response = authed_client.get(
            "/api/v1/resources/idle?idle_type=low_cpu&is_reviewed=false&limit=50"
        )

        assert response.status_code == 200
        mock_svc.get_idle_resources.assert_called_once()


# ============================================================================
# GET /api/v1/resources/idle/summary Tests
# ============================================================================


class TestIdleResourcesSummaryEndpoint:
    """Tests for GET /api/v1/resources/idle/summary endpoint."""

    @patch("app.api.routes.resources.ResourceService")
    def test_get_idle_summary_success(self, mock_service_cls, authed_client):
        """Idle resources summary endpoint returns summary data."""
        mock_svc = MagicMock()
        mock_svc.get_idle_resources_summary = AsyncMock(
            return_value=IdleResourceSummary(
                total_count=10,
                total_potential_savings_monthly=500.0,
                total_potential_savings_annual=6000.0,
                by_type={"VirtualMachine": 7, "Disk": 3},
            )
        )
        mock_service_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/resources/idle/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 10
        assert data["total_potential_savings_monthly"] == 500.0

    def test_get_idle_summary_requires_auth(self, client):
        """Idle resources summary endpoint returns 401 without authentication."""
        response = client.get("/api/v1/resources/idle/summary")
        assert response.status_code == 401


# ============================================================================
# POST /api/v1/resources/idle/{idle_resource_id}/tag Tests
# ============================================================================


class TestTagIdleResourceEndpoint:
    """Tests for POST /api/v1/resources/idle/{idle_resource_id}/tag."""

    @patch("app.api.routes.resources.ResourceService")
    def test_tag_idle_resource_success(self, mock_service_cls, authed_client):
        """Tag idle resource endpoint succeeds."""
        mock_svc = MagicMock()
        mock_svc.tag_idle_resource_as_reviewed = AsyncMock(
            return_value=TagResourceResponse(
                success=True,
                resource_id="resource-123",
                tagged_at=datetime.now(UTC),
            )
        )
        mock_service_cls.return_value = mock_svc

        response = authed_client.post(
            "/api/v1/resources/idle/1/tag",
            json={"notes": "Reviewed - intentionally idle"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_tag_idle_resource_requires_auth(self, client):
        """Tag idle resource endpoint returns 401 without authentication."""
        response = client.post("/api/v1/resources/idle/1/tag")
        assert response.status_code == 401


# ============================================================================
# GET /api/v1/resources/tagging Tests
# ============================================================================


class TestTaggingComplianceEndpoint:
    """Tests for GET /api/v1/resources/tagging endpoint."""

    @patch("app.api.routes.resources.ResourceService")
    def test_get_tagging_compliance_success(self, mock_service_cls, authed_client):
        """Tagging compliance endpoint returns compliance data."""
        mock_svc = MagicMock()
        mock_svc.get_tagging_compliance = AsyncMock(
            return_value=TaggingCompliance(
                total_resources=100,
                fully_tagged=80,
                partially_tagged=15,
                untagged=5,
                compliance_percent=80.0,
            )
        )
        mock_service_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/resources/tagging")

        assert response.status_code == 200
        data = response.json()
        assert data["compliance_percent"] == 80.0

    def test_get_tagging_compliance_requires_auth(self, client):
        """Tagging compliance endpoint returns 401 without authentication."""
        response = client.get("/api/v1/resources/tagging")
        assert response.status_code == 401

    @patch("app.api.routes.resources.ResourceService")
    def test_get_tagging_compliance_with_required_tags(
        self, mock_service_cls, authed_client
    ):
        """Tagging compliance endpoint accepts required tags parameter."""
        mock_svc = MagicMock()
        mock_svc.get_tagging_compliance = AsyncMock(
            return_value=TaggingCompliance(
                total_resources=100,
                fully_tagged=80,
                partially_tagged=15,
                untagged=5,
                compliance_percent=80.0,
            )
        )
        mock_service_cls.return_value = mock_svc

        response = authed_client.get(
            "/api/v1/resources/tagging?required_tags=Environment&required_tags=CostCenter"
        )
        assert response.status_code == 200

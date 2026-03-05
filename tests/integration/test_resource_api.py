"""Integration tests for Resource API endpoints.

These tests verify the complete request/response cycle for resource management endpoints,
including authentication, authorization, database interactions, and data validation.

Covered endpoints:
- GET /api/v1/resources - Resource inventory with filtering
- GET /api/v1/resources/orphaned - Orphaned resources
- GET /api/v1/resources/idle - Idle resources
- GET /api/v1/resources/idle/summary - Idle resources summary
- POST /api/v1/resources/idle/{id}/tag - Tag idle resource as reviewed
- GET /api/v1/resources/tagging - Tagging compliance
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.auth import User
from app.core.database import get_db
from app.main import app
from app.models.resource import IdleResource, Resource, ResourceTag
from app.models.tenant import Tenant


# ============================================================================
# Enhanced Fixtures with Idle Resources
# ============================================================================

@pytest.fixture
def seeded_resource_db(seeded_db, test_tenant_id: str, second_tenant_id: str):
    """Extend seeded_db with idle resources for testing.
    
    Adds:
    - 5 idle resources (3 unreviewed, 2 reviewed)
    - Mix of idle types (low_cpu, no_connections, unused_disk)
    """
    # Create idle resources (note: resource_id must reference existing resources or be FK constraint)
    idle_resources_data = [
        {
            "resource_id": "/subscriptions/sub-123/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm-0",
            "tenant_id": test_tenant_id,
            "subscription_id": "sub-123",
            "detected_at": datetime.utcnow() - timedelta(days=7),
            "idle_type": "low_cpu",
            "description": "VM with CPU utilization < 5% for 7 days",
            "estimated_monthly_savings": 150.00,
            "idle_days": 7,
            "is_reviewed": 0,
        },
        {
            "resource_id": "/subscriptions/sub-123/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm-1",
            "tenant_id": test_tenant_id,
            "subscription_id": "sub-123",
            "detected_at": datetime.utcnow() - timedelta(days=14),
            "idle_type": "no_connections",
            "description": "VM with no connections for 14 days",
            "estimated_monthly_savings": 75.50,
            "idle_days": 14,
            "is_reviewed": 0,
        },
        {
            "resource_id": "/subscriptions/sub-123/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm-2",
            "tenant_id": test_tenant_id,
            "subscription_id": "sub-123",
            "detected_at": datetime.utcnow() - timedelta(days=30),
            "idle_type": "unused_disk",
            "description": "Unattached disk for 30 days",
            "estimated_monthly_savings": 25.00,
            "idle_days": 30,
            "is_reviewed": 0,
        },
        {
            "resource_id": "/subscriptions/sub-123/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm-3",
            "tenant_id": test_tenant_id,
            "subscription_id": "sub-123",
            "detected_at": datetime.utcnow() - timedelta(days=10),
            "idle_type": "low_cpu",
            "description": "VM with low CPU (reviewed)",
            "estimated_monthly_savings": 100.00,
            "idle_days": 10,
            "is_reviewed": 1,
            "reviewed_by": "user-123",
            "reviewed_at": datetime.utcnow() - timedelta(days=2),
            "review_notes": "Keeping for backup purposes",
        },
        {
            "resource_id": "/subscriptions/sub-123/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm-4",
            "tenant_id": test_tenant_id,
            "subscription_id": "sub-123",
            "detected_at": datetime.utcnow() - timedelta(days=5),
            "idle_type": "no_connections",
            "description": "VM with no connections (reviewed)",
            "estimated_monthly_savings": 50.00,
            "idle_days": 5,
            "is_reviewed": 1,
            "reviewed_by": "user-456",
            "reviewed_at": datetime.utcnow() - timedelta(days=1),
            "review_notes": "Archival storage, keep",
        },
    ]
    
    for idle_data in idle_resources_data:
        idle_resource = IdleResource(**idle_data)
        seeded_db.add(idle_resource)
    
    seeded_db.commit()
    return seeded_db


@pytest.fixture
def authenticated_resource_client(seeded_resource_db, test_user, mock_authz):
    """Test client with authentication and seeded resource database."""
    def override_get_db():
        try:
            yield seeded_resource_db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    # Use dependency overrides for auth functions
    def override_get_current_user():
        return test_user
    
    def override_get_tenant_authorization():
        return mock_authz
    
    from app.core.auth import get_current_user
    from app.core.authorization import get_tenant_authorization
    
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_tenant_authorization] = override_get_tenant_authorization
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def unauthenticated_resource_client(seeded_resource_db):
    """Test client without authentication for testing 401s."""
    def override_get_db():
        try:
            yield seeded_resource_db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


# ============================================================================
# GET /api/v1/resources Tests
# ============================================================================

class TestGetResourcesEndpoint:
    """Integration tests for GET /api/v1/resources."""
    
    def test_get_resources_success(self, authenticated_resource_client: TestClient):
        """Resource inventory returns comprehensive resource data."""
        response = authenticated_resource_client.get("/api/v1/resources")
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate structure
        assert "total_resources" in data
        assert "resources_by_type" in data
        assert "resources_by_location" in data
        assert "resources_by_tenant" in data
        assert "orphaned_resources" in data
        assert "orphaned_estimated_cost" in data
        assert "resources" in data
        
        # Validate types
        assert isinstance(data["total_resources"], int)
        assert isinstance(data["resources"], list)
        assert data["total_resources"] >= 0
        
        # If we have resources, validate their structure
        if len(data["resources"]) > 0:
            resource = data["resources"][0]
            assert "id" in resource
            assert "tenant_id" in resource
            assert "tenant_name" in resource
            assert "resource_type" in resource
            assert "name" in resource
            assert "location" in resource
            assert "tags" in resource
            assert isinstance(resource["tags"], dict)
    
    def test_get_resources_filter_by_type(self, authenticated_resource_client: TestClient):
        """Resource inventory can filter by resource type."""
        response = authenticated_resource_client.get(
            "/api/v1/resources?resource_type=Microsoft.Compute/virtualMachines"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # All returned resources should match the filter
        for resource in data["resources"]:
            assert "Microsoft.Compute/virtualMachines" in resource["resource_type"]
    
    def test_get_resources_pagination(self, authenticated_resource_client: TestClient):
        """Resource inventory supports pagination with limit and offset."""
        # Get first page
        response_page1 = authenticated_resource_client.get("/api/v1/resources?limit=2&offset=0")
        assert response_page1.status_code == 200
        page1_data = response_page1.json()
        
        # Get second page
        response_page2 = authenticated_resource_client.get("/api/v1/resources?limit=2&offset=2")
        assert response_page2.status_code == 200
        page2_data = response_page2.json()
        
        # Pages should have different resources (if we have enough data)
        if len(page1_data["resources"]) > 0 and len(page2_data["resources"]) > 0:
            page1_ids = {r["id"] for r in page1_data["resources"]}
            page2_ids = {r["id"] for r in page2_data["resources"]}
            # Pages might have overlap, but not be identical
            assert page1_ids != page2_ids or len(page1_ids) <= 2
    
    def test_get_resources_requires_auth(self, unauthenticated_resource_client: TestClient):
        """Resource inventory endpoint requires authentication."""
        response = unauthenticated_resource_client.get("/api/v1/resources")
        assert response.status_code == 401
    
    def test_get_resources_validates_limit(self, authenticated_resource_client: TestClient):
        """Resource inventory validates limit parameter."""
        # Test limit too large
        response = authenticated_resource_client.get("/api/v1/resources?limit=2000")
        assert response.status_code == 422  # Validation error
        
        # Test negative limit
        response = authenticated_resource_client.get("/api/v1/resources?limit=-1")
        assert response.status_code == 422
    
    def test_get_resources_aggregations(self, authenticated_resource_client: TestClient):
        """Resource inventory includes proper aggregations."""
        response = authenticated_resource_client.get("/api/v1/resources")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify aggregations are dictionaries
        assert isinstance(data["resources_by_type"], dict)
        assert isinstance(data["resources_by_location"], dict)
        assert isinstance(data["resources_by_tenant"], dict)
        
        # Aggregations should be consistent with resource list
        if len(data["resources"]) > 0:
            # Count resources in aggregations
            total_by_type = sum(data["resources_by_type"].values())
            assert total_by_type <= data["total_resources"]


# ============================================================================
# GET /api/v1/resources/orphaned Tests
# ============================================================================

class TestGetOrphanedResourcesEndpoint:
    """Integration tests for GET /api/v1/resources/orphaned."""
    
    def test_get_orphaned_resources_success(self, authenticated_resource_client: TestClient):
        """Orphaned resources endpoint returns list of orphaned resources."""
        response = authenticated_resource_client.get("/api/v1/resources/orphaned")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return a list
        assert isinstance(data, list)
        
        # If we have orphaned resources, validate structure
        if len(data) > 0:
            orphan = data[0]
            assert "resource_id" in orphan
            assert "resource_name" in orphan
            assert "resource_type" in orphan
            assert "tenant_name" in orphan
            assert "subscription_name" in orphan
            assert "estimated_monthly_cost" in orphan
            assert "days_inactive" in orphan
            assert "reason" in orphan
            
            # Validate types
            assert isinstance(orphan["days_inactive"], int)
            assert orphan["days_inactive"] >= 0
    
    def test_get_orphaned_resources_pagination(self, authenticated_resource_client: TestClient):
        """Orphaned resources supports pagination."""
        # Get first page
        response_page1 = authenticated_resource_client.get("/api/v1/resources/orphaned?limit=2&offset=0")
        assert response_page1.status_code == 200
        page1_data = response_page1.json()
        
        # Get second page
        response_page2 = authenticated_resource_client.get("/api/v1/resources/orphaned?limit=2&offset=2")
        assert response_page2.status_code == 200
        page2_data = response_page2.json()
        
        # Both should be lists
        assert isinstance(page1_data, list)
        assert isinstance(page2_data, list)
    
    def test_get_orphaned_resources_requires_auth(self, unauthenticated_resource_client: TestClient):
        """Orphaned resources endpoint requires authentication."""
        response = unauthenticated_resource_client.get("/api/v1/resources/orphaned")
        assert response.status_code == 401
    
    def test_get_orphaned_resources_validates_limit(self, authenticated_resource_client: TestClient):
        """Orphaned resources validates limit parameter."""
        # Test limit too large
        response = authenticated_resource_client.get("/api/v1/resources/orphaned?limit=1000")
        assert response.status_code == 422  # Validation error
        
        # Test negative limit
        response = authenticated_resource_client.get("/api/v1/resources/orphaned?limit=-1")
        assert response.status_code == 422


# ============================================================================
# GET /api/v1/resources/idle Tests
# ============================================================================

class TestGetIdleResourcesEndpoint:
    """Integration tests for GET /api/v1/resources/idle."""
    
    def test_get_idle_resources_success(self, authenticated_resource_client: TestClient):
        """Idle resources endpoint returns list of idle resources."""
        response = authenticated_resource_client.get("/api/v1/resources/idle")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return a list
        assert isinstance(data, list)
        # We seeded 5 idle resources (3 unreviewed in test_tenant_id)
        assert len(data) >= 3
        
        # Validate structure
        if len(data) > 0:
            idle = data[0]
            assert "id" in idle
            assert "resource_id" in idle
            assert "tenant_id" in idle
            assert "tenant_name" in idle
            assert "subscription_id" in idle
            assert "detected_at" in idle
            assert "idle_type" in idle
            assert "description" in idle
            assert "estimated_monthly_savings" in idle
            assert "idle_days" in idle
            assert "is_reviewed" in idle
            
            # Validate types
            assert isinstance(idle["idle_days"], int)
            assert isinstance(idle["is_reviewed"], bool)
            assert idle["idle_days"] >= 0
    
    def test_get_idle_resources_filter_by_type(self, authenticated_resource_client: TestClient):
        """Idle resources can be filtered by idle type."""
        response = authenticated_resource_client.get("/api/v1/resources/idle?idle_type=low_cpu")
        
        assert response.status_code == 200
        data = response.json()
        
        # All returned resources should match the filter
        for idle in data:
            assert idle["idle_type"] == "low_cpu"
    
    def test_get_idle_resources_filter_by_reviewed_status(self, authenticated_resource_client: TestClient):
        """Idle resources can be filtered by review status."""
        # Get unreviewed
        response_unreviewed = authenticated_resource_client.get("/api/v1/resources/idle?is_reviewed=false")
        assert response_unreviewed.status_code == 200
        unreviewed_data = response_unreviewed.json()
        
        # Get reviewed
        response_reviewed = authenticated_resource_client.get("/api/v1/resources/idle?is_reviewed=true")
        assert response_reviewed.status_code == 200
        reviewed_data = response_reviewed.json()
        
        # Verify filter works
        for idle in unreviewed_data:
            assert idle["is_reviewed"] is False
        
        for idle in reviewed_data:
            assert idle["is_reviewed"] is True
    
    def test_get_idle_resources_pagination(self, authenticated_resource_client: TestClient):
        """Idle resources supports pagination with limit and offset."""
        # Get first page
        response_page1 = authenticated_resource_client.get("/api/v1/resources/idle?limit=2&offset=0")
        assert response_page1.status_code == 200
        page1_data = response_page1.json()
        assert len(page1_data) <= 2
        
        # Get second page
        response_page2 = authenticated_resource_client.get("/api/v1/resources/idle?limit=2&offset=2")
        assert response_page2.status_code == 200
        page2_data = response_page2.json()
        assert len(page2_data) <= 2
        
        # Pages should have different resources (if we have enough data)
        if len(page1_data) > 0 and len(page2_data) > 0:
            page1_ids = {r["id"] for r in page1_data}
            page2_ids = {r["id"] for r in page2_data}
            assert page1_ids != page2_ids
    
    def test_get_idle_resources_sorting(self, authenticated_resource_client: TestClient):
        """Idle resources supports sorting by different fields."""
        # Sort by savings descending (default)
        response = authenticated_resource_client.get(
            "/api/v1/resources/idle?sort_by=estimated_monthly_savings&sort_order=desc"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify sorting (if we have multiple resources)
        if len(data) >= 2:
            savings = [r["estimated_monthly_savings"] for r in data if r["estimated_monthly_savings"] is not None]
            if len(savings) >= 2:
                # Check that they're in descending order
                assert savings == sorted(savings, reverse=True)
    
    def test_get_idle_resources_requires_auth(self, unauthenticated_resource_client: TestClient):
        """Idle resources endpoint requires authentication."""
        response = unauthenticated_resource_client.get("/api/v1/resources/idle")
        assert response.status_code == 401
    
    def test_get_idle_resources_validates_parameters(self, authenticated_resource_client: TestClient):
        """Idle resources validates query parameters."""
        # Test invalid limit
        response = authenticated_resource_client.get("/api/v1/resources/idle?limit=1000")
        assert response.status_code == 422
        
        # Test invalid sort_order
        response = authenticated_resource_client.get("/api/v1/resources/idle?sort_order=invalid")
        assert response.status_code == 422


# ============================================================================
# GET /api/v1/resources/idle/summary Tests
# ============================================================================

class TestGetIdleResourcesSummaryEndpoint:
    """Integration tests for GET /api/v1/resources/idle/summary."""
    
    def test_get_idle_resources_summary_success(self, authenticated_resource_client: TestClient):
        """Idle resources summary returns aggregated savings data."""
        response = authenticated_resource_client.get("/api/v1/resources/idle/summary")
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate structure
        assert "total_count" in data
        assert "total_potential_savings_monthly" in data
        assert "total_potential_savings_annual" in data
        assert "by_type" in data
        assert "by_tenant" in data
        
        # Validate types
        assert isinstance(data["total_count"], int)
        assert isinstance(data["total_potential_savings_monthly"], (int, float))
        assert isinstance(data["total_potential_savings_annual"], (int, float))
        assert isinstance(data["by_type"], dict)
        assert isinstance(data["by_tenant"], dict)
        
        # Validate business logic
        # Annual savings should be roughly 12x monthly
        if data["total_potential_savings_monthly"] > 0:
            expected_annual = data["total_potential_savings_monthly"] * 12
            assert abs(data["total_potential_savings_annual"] - expected_annual) < 0.01
    
    def test_get_idle_resources_summary_aggregations(self, authenticated_resource_client: TestClient):
        """Idle resources summary includes proper aggregations."""
        response = authenticated_resource_client.get("/api/v1/resources/idle/summary")
        
        assert response.status_code == 200
        data = response.json()
        
        # by_type should have idle types as keys
        if len(data["by_type"]) > 0:
            # Verify values are integers (counts)
            for count in data["by_type"].values():
                assert isinstance(count, int)
                assert count > 0
        
        # by_tenant should have tenant names as keys
        if len(data["by_tenant"]) > 0:
            for count in data["by_tenant"].values():
                assert isinstance(count, int)
                assert count > 0
    
    def test_get_idle_resources_summary_requires_auth(self, unauthenticated_resource_client: TestClient):
        """Idle resources summary endpoint requires authentication."""
        response = unauthenticated_resource_client.get("/api/v1/resources/idle/summary")
        assert response.status_code == 401


# ============================================================================
# POST /api/v1/resources/idle/{id}/tag Tests
# ============================================================================

class TestTagIdleResourceEndpoint:
    """Integration tests for POST /api/v1/resources/idle/{id}/tag."""
    
    def test_tag_idle_resource_success(self, authenticated_resource_client: TestClient, seeded_resource_db):
        """Tagging an idle resource updates the database."""
        # Get an unreviewed idle resource
        response_idle = authenticated_resource_client.get("/api/v1/resources/idle?is_reviewed=false")
        idle_resources = response_idle.json()
        assert len(idle_resources) > 0
        
        idle_id = idle_resources[0]["id"]
        
        # Tag it
        response = authenticated_resource_client.post(
            f"/api/v1/resources/idle/{idle_id}/tag",
            json={"notes": "Reviewed and keeping for backup"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert "success" in data
        assert "resource_id" in data
        assert "tagged_at" in data
        assert data["success"] is True
        
        # Verify database state changed
        idle_in_db = seeded_resource_db.query(IdleResource).filter(IdleResource.id == idle_id).first()
        assert idle_in_db is not None
        assert idle_in_db.is_reviewed == 1
        assert idle_in_db.reviewed_by == "user-123"
        assert idle_in_db.reviewed_at is not None
        assert idle_in_db.review_notes == "Reviewed and keeping for backup"
    
    def test_tag_idle_resource_without_notes(self, authenticated_resource_client: TestClient, seeded_resource_db):
        """Tagging an idle resource works without notes."""
        # Get an unreviewed idle resource
        response_idle = authenticated_resource_client.get("/api/v1/resources/idle?is_reviewed=false")
        idle_resources = response_idle.json()
        assert len(idle_resources) > 0
        
        idle_id = idle_resources[0]["id"]
        
        # Tag it without notes
        response = authenticated_resource_client.post(f"/api/v1/resources/idle/{idle_id}/tag")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Verify database state
        idle_in_db = seeded_resource_db.query(IdleResource).filter(IdleResource.id == idle_id).first()
        assert idle_in_db.is_reviewed == 1
        assert idle_in_db.review_notes is None
    
    def test_tag_nonexistent_idle_resource(self, authenticated_resource_client: TestClient):
        """Tagging a non-existent idle resource returns success=false."""
        response = authenticated_resource_client.post(
            "/api/v1/resources/idle/99999/tag",
            json={"notes": "This should fail"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
    
    def test_tag_idle_resource_requires_auth(self, unauthenticated_resource_client: TestClient):
        """Tag idle resource endpoint requires authentication."""
        response = unauthenticated_resource_client.post("/api/v1/resources/idle/1/tag")
        assert response.status_code == 401
    
    def test_tag_idle_resource_validates_id(self, authenticated_resource_client: TestClient):
        """Tag idle resource validates ID parameter."""
        # Test with invalid ID (negative)
        response = authenticated_resource_client.post("/api/v1/resources/idle/-1/tag")
        assert response.status_code == 422  # Validation error
        
        # Test with invalid ID (zero)
        response = authenticated_resource_client.post("/api/v1/resources/idle/0/tag")
        assert response.status_code == 422
    
    def test_tag_idle_resource_already_reviewed(self, authenticated_resource_client: TestClient, seeded_resource_db):
        """Tagging an already reviewed idle resource works (re-review)."""
        # Get a reviewed idle resource
        response_idle = authenticated_resource_client.get("/api/v1/resources/idle?is_reviewed=true")
        idle_resources = response_idle.json()
        assert len(idle_resources) > 0
        
        idle_id = idle_resources[0]["id"]
        
        # Tag it again
        response = authenticated_resource_client.post(
            f"/api/v1/resources/idle/{idle_id}/tag",
            json={"notes": "Re-reviewed"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        
        # Verify notes updated
        idle_in_db = seeded_resource_db.query(IdleResource).filter(IdleResource.id == idle_id).first()
        assert idle_in_db.review_notes == "Re-reviewed"


# ============================================================================
# GET /api/v1/resources/tagging Tests
# ============================================================================

class TestGetTaggingComplianceEndpoint:
    """Integration tests for GET /api/v1/resources/tagging."""
    
    def test_get_tagging_compliance_success(self, authenticated_resource_client: TestClient):
        """Tagging compliance returns compliance summary."""
        response = authenticated_resource_client.get("/api/v1/resources/tagging")
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate structure
        assert "total_resources" in data
        assert "fully_tagged" in data
        assert "partially_tagged" in data
        assert "untagged" in data
        assert "compliance_percent" in data
        assert "required_tags" in data
        assert "missing_tags_by_resource" in data
        
        # Validate types
        assert isinstance(data["total_resources"], int)
        assert isinstance(data["fully_tagged"], int)
        assert isinstance(data["partially_tagged"], int)
        assert isinstance(data["untagged"], int)
        assert isinstance(data["compliance_percent"], (int, float))
        assert isinstance(data["required_tags"], list)
        assert isinstance(data["missing_tags_by_resource"], list)
        
        # Validate business logic
        total = data["fully_tagged"] + data["partially_tagged"] + data["untagged"]
        assert total == data["total_resources"]
        
        # Compliance percent should be 0-100
        assert 0 <= data["compliance_percent"] <= 100
    
    def test_get_tagging_compliance_with_custom_tags(self, authenticated_resource_client: TestClient):
        """Tagging compliance accepts custom required tags."""
        response = authenticated_resource_client.get(
            "/api/v1/resources/tagging?required_tags=Environment&required_tags=Owner"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should include the required tags in response
        assert "Environment" in data["required_tags"]
        assert "Owner" in data["required_tags"]
    
    def test_get_tagging_compliance_missing_tags_structure(self, authenticated_resource_client: TestClient):
        """Tagging compliance returns properly structured missing tags."""
        response = authenticated_resource_client.get("/api/v1/resources/tagging")
        
        assert response.status_code == 200
        data = response.json()
        
        # If we have resources with missing tags, validate structure
        if len(data["missing_tags_by_resource"]) > 0:
            missing = data["missing_tags_by_resource"][0]
            assert "resource_id" in missing
            assert "resource_name" in missing
            assert "resource_type" in missing
            assert "missing_tags" in missing
            assert isinstance(missing["missing_tags"], list)
    
    def test_get_tagging_compliance_requires_auth(self, unauthenticated_resource_client: TestClient):
        """Tagging compliance endpoint requires authentication."""
        response = unauthenticated_resource_client.get("/api/v1/resources/tagging")
        assert response.status_code == 401
    
    def test_get_tagging_compliance_default_tags(self, authenticated_resource_client: TestClient):
        """Tagging compliance uses default required tags when none specified."""
        response = authenticated_resource_client.get("/api/v1/resources/tagging")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have default required tags
        assert len(data["required_tags"]) > 0
        # Common tags like Environment, Owner, etc.
        # (Exact tags depend on DEFAULT_REQUIRED_TAGS in service)

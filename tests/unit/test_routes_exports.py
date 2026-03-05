"""Unit tests for exports API routes.

Tests CSV export endpoints:
- GET /api/v1/exports/costs
- GET /api/v1/exports/resources
- GET /api/v1/exports/compliance
"""

import uuid
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.auth import User
from app.core.database import get_db
from app.main import app
from app.models.tenant import Tenant, UserTenant


@pytest.fixture
def test_db_session(db_session):
    """Database session with test data."""
    tenant = Tenant(
        id=str(uuid.uuid4()),
        tenant_id="exports-tenant-123",
        name="Exports Test Tenant",
        subscription_id="sub-exports-123",
        is_active=True,
    )
    db_session.add(tenant)
    
    user_tenant = UserTenant(
        id=str(uuid.uuid4()),
        user_id="user:exports-admin",
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
        id="user-exports-admin",
        email="admin@exports.test",
        name="Exports Admin",
        roles=["admin"],
        tenant_ids=["exports-tenant-123"],
        is_active=True,
        auth_provider="azure_ad",
    )


def test_export_costs_success(client_with_db, mock_user):
    """Test successful cost export to CSV."""
    mock_trends = [
        MagicMock(date=date.today() - timedelta(days=i), cost=1000 + i * 100)
        for i in range(5)
    ]
    
    mock_tenant_costs = [
        MagicMock(
            tenant_id="exports-tenant-123",
            tenant_name="Exports Test Tenant",
            total_cost=5000.50,
            currency="USD",
        )
    ]
    
    with patch("app.api.routes.exports.get_current_user", return_value=mock_user):
        with patch("app.api.routes.exports.CostService") as MockCostService:
            mock_service = MockCostService.return_value
            mock_service.get_cost_trends.return_value = mock_trends
            mock_service.get_costs_by_tenant.return_value = mock_tenant_costs
            
            response = client_with_db.get("/api/v1/exports/costs")
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "attachment; filename=costs_export_" in response.headers["content-disposition"]
    
    # Verify CSV content
    csv_content = response.text
    assert "type,date,tenant_id,tenant_name,cost,currency" in csv_content
    assert "daily_cost" in csv_content
    assert "tenant_summary" in csv_content


def test_export_costs_with_date_range(client_with_db, mock_user):
    """Test cost export with specific date range."""
    start_date = date.today() - timedelta(days=7)
    end_date = date.today()
    
    mock_trends = []
    mock_tenant_costs = []
    
    with patch("app.api.routes.exports.get_current_user", return_value=mock_user):
        with patch("app.api.routes.exports.CostService") as MockCostService:
            mock_service = MockCostService.return_value
            mock_service.get_cost_trends.return_value = mock_trends
            mock_service.get_costs_by_tenant.return_value = mock_tenant_costs
            
            response = client_with_db.get(
                f"/api/v1/exports/costs?start_date={start_date}&end_date={end_date}"
            )
    
    assert response.status_code == 200
    mock_service.get_cost_trends.assert_called_once()


def test_export_resources_success(client_with_db, mock_user):
    """Test successful resource export to CSV."""
    mock_inventory = MagicMock()
    mock_inventory.resources = [
        MagicMock(
            id="res-1",
            name="VM-Prod-01",
            resource_type="Microsoft.Compute/virtualMachines",
            tenant_id="exports-tenant-123",
            tenant_name="Exports Test Tenant",
            subscription_id="sub-exports-123",
            subscription_name="Production Sub",
            resource_group="rg-prod",
            location="eastus",
            provisioning_state="Succeeded",
            sku="Standard_D2s_v3",
            is_orphaned=False,
            estimated_monthly_cost=150.00,
            tags={"Environment": "Production", "Owner": "DevOps"},
            last_synced=datetime.utcnow(),
        ),
        MagicMock(
            id="res-2",
            name="SQL-Prod-01",
            resource_type="Microsoft.Sql/servers",
            tenant_id="exports-tenant-123",
            tenant_name="Exports Test Tenant",
            subscription_id="sub-exports-123",
            subscription_name="Production Sub",
            resource_group="rg-prod",
            location="eastus",
            provisioning_state="Succeeded",
            sku=None,
            is_orphaned=False,
            estimated_monthly_cost=500.00,
            tags={},
            last_synced=datetime.utcnow(),
        ),
    ]
    
    with patch("app.api.routes.exports.get_current_user", return_value=mock_user):
        with patch("app.api.routes.exports.ResourceService") as MockResourceService:
            mock_service = MockResourceService.return_value
            mock_service.get_resource_inventory.return_value = mock_inventory
            
            response = client_with_db.get("/api/v1/exports/resources")
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    
    # Verify CSV content
    csv_content = response.text
    assert "resource_id,name,resource_type" in csv_content
    assert "VM-Prod-01" in csv_content
    assert "SQL-Prod-01" in csv_content


def test_export_resources_filter_by_type(client_with_db, mock_user):
    """Test resource export with resource type filter."""
    mock_inventory = MagicMock()
    mock_inventory.resources = []
    
    with patch("app.api.routes.exports.get_current_user", return_value=mock_user):
        with patch("app.api.routes.exports.ResourceService") as MockResourceService:
            mock_service = MockResourceService.return_value
            mock_service.get_resource_inventory.return_value = mock_inventory
            
            response = client_with_db.get(
                "/api/v1/exports/resources?resource_type=Microsoft.Compute/virtualMachines"
            )
    
    assert response.status_code == 200
    mock_service.get_resource_inventory.assert_called_once()
    call_kwargs = mock_service.get_resource_inventory.call_args[1]
    assert call_kwargs["resource_type"] == "Microsoft.Compute/virtualMachines"


def test_export_compliance_success(client_with_db, mock_user):
    """Test successful compliance export to CSV."""
    mock_summary = MagicMock()
    mock_summary.scores_by_tenant = [
        MagicMock(
            tenant_id="exports-tenant-123",
            tenant_name="Exports Test Tenant",
            subscription_id="sub-exports-123",
            overall_compliance_percent=85.5,
            secure_score=650,
            compliant_resources=85,
            non_compliant_resources=15,
            exempt_resources=0,
        )
    ]
    
    mock_non_compliant = [
        MagicMock(
            tenant_id="exports-tenant-123",
            policy_definition_id="pol-123",
            policy_name="Require HTTPS for storage accounts",
            policy_category="Security",
            compliance_state="NonCompliant",
            non_compliant_count=3,
            subscription_id="sub-exports-123",
            recommendation="Enable HTTPS-only traffic",
        )
    ]
    
    with patch("app.api.routes.exports.get_current_user", return_value=mock_user):
        with patch("app.api.routes.exports.ComplianceService") as MockComplianceService:
            mock_service = MockComplianceService.return_value
            mock_service.get_compliance_summary.return_value = mock_summary
            mock_service.get_non_compliant_policies.return_value = mock_non_compliant
            
            response = client_with_db.get("/api/v1/exports/compliance")
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    
    # Verify CSV content
    csv_content = response.text
    assert "type,tenant_id" in csv_content
    assert "tenant_score" in csv_content
    assert "non_compliant_policy" in csv_content


def test_export_compliance_exclude_non_compliant(client_with_db, mock_user):
    """Test compliance export excluding non-compliant policies."""
    mock_summary = MagicMock()
    mock_summary.scores_by_tenant = []
    
    with patch("app.api.routes.exports.get_current_user", return_value=mock_user):
        with patch("app.api.routes.exports.ComplianceService") as MockComplianceService:
            mock_service = MockComplianceService.return_value
            mock_service.get_compliance_summary.return_value = mock_summary
            
            response = client_with_db.get(
                "/api/v1/exports/compliance?include_non_compliant=false"
            )
    
    assert response.status_code == 200
    # Should only call get_compliance_summary, not get_non_compliant_policies
    mock_service.get_compliance_summary.assert_called_once()
    mock_service.get_non_compliant_policies.assert_not_called()

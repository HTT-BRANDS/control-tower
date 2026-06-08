"""Unit tests for tenant strip and new dashboard layout."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.auth import User, get_current_user
from app.core.authorization import TenantAuthorization, get_tenant_authorization
from app.core.database import get_db, Base
from app.models.tenant import Tenant
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture(scope="module")
def client():
    """Test client with in-memory DB and mocked auth."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Seed test tenants
    db.add(Tenant(id="tenant-htt", tenant_id="tenant-htt", name="Head-To-Toe (HTT)", is_active=True))
    db.add(Tenant(id="tenant-bcc", tenant_id="tenant-bcc", name="Bishops (BCC)", is_active=True))
    db.commit()

    mock_user = User(
        id="user-123", email="test@example.com", name="Test User",
        roles=["admin"], tenant_ids=["tenant-htt", "tenant-bcc"], is_active=True, auth_provider="internal",
    )
    from unittest.mock import MagicMock
    mock_authz = MagicMock(spec=TenantAuthorization)
    mock_authz.user = mock_user
    mock_authz.accessible_tenant_ids = {"tenant-htt", "tenant-bcc"}
    mock_authz.ensure_at_least_one_tenant = MagicMock()
    mock_authz.filter_tenant_ids = MagicMock(return_value={"tenant-htt", "tenant-bcc"})

    def override_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_tenant_authorization] = lambda: mock_authz

    with TestClient(app) as tc:
        yield tc

    app.dependency_overrides.clear()


class TestTenantStrip:
    """Tenant health strip renders on all pages."""

    def test_strip_on_dashboard(self, client):
        r = client.get("/dashboard")
        assert r.status_code == 200
        assert "tenant-health-strip" in r.text
        assert "Head-To-Toe" in r.text or "HTT" in r.text
        assert "Bishops" in r.text or "BCC" in r.text

    def test_strip_on_costs(self, client):
        r = client.get("/costs")
        assert r.status_code == 200
        assert "tenant-health-strip" in r.text

    def test_strip_on_compliance(self, client):
        r = client.get("/compliance")
        assert r.status_code == 200
        assert "tenant-health-strip" in r.text

    def test_strip_on_resources(self, client):
        r = client.get("/resources")
        assert r.status_code == 200
        assert "tenant-health-strip" in r.text

    def test_strip_on_identity(self, client):
        r = client.get("/identity")
        assert r.status_code == 200
        assert "tenant-health-strip" in r.text


class TestDashboardRedesign:
    """Mission control dashboard layout."""

    def test_platform_health_card(self, client):
        r = client.get("/dashboard")
        assert r.status_code == 200
        assert "Platform Health" in r.text
        assert "ct-card" in r.text

    def test_tenant_status_grid(self, client):
        r = client.get("/dashboard")
        assert r.status_code == 200
        assert "Tenant Status" in r.text
        assert "dashboard-tenant-grid" in r.text

    def test_domain_overview_cards(self, client):
        r = client.get("/dashboard")
        assert r.status_code == 200
        assert "Domain Overview" in r.text
        assert "Costs" in r.text
        assert "Compliance" in r.text
        assert "Resources" in r.text
        assert "Identity" in r.text

    def test_charts_section(self, client):
        r = client.get("/dashboard")
        assert r.status_code == 200
        assert "Trends & Analysis" in r.text
        assert "costTrendChart" in r.text
        assert "complianceChart" in r.text

    def test_h1_present(self, client):
        r = client.get("/dashboard")
        assert r.status_code == 200
        assert "<h1" in r.text


class TestDataPageOverhauls:
    """Data pages have tenant tabs, compact tables, and mission-control cards."""

    def test_costs_tenant_tabs(self, client):
        r = client.get("/costs")
        assert r.status_code == 200
        assert "tenant-tabs" in r.text
        assert "tenant-tab" in r.text
        assert "ct-card" in r.text
        assert "kpi-value" in r.text
        assert "table-compact" in r.text

    def test_compliance_tenant_tabs(self, client):
        r = client.get("/compliance")
        assert r.status_code == 200
        assert "tenant-tabs" in r.text
        assert "table-compact" in r.text
        assert "ct-card" in r.text

    def test_resources_tenant_tabs(self, client):
        r = client.get("/resources")
        assert r.status_code == 200
        assert "tenant-tabs" in r.text
        assert "table-compact" in r.text
        assert "ct-card" in r.text

    def test_identity_tenant_tabs(self, client):
        r = client.get("/identity")
        assert r.status_code == 200
        assert "tenant-tabs" in r.text
        assert "table-compact" in r.text
        assert "ct-card" in r.text


class TestApiContractFixes:
    """API field names match frontend expectations."""

    def test_compliance_fields(self, client):
        r = client.get("/compliance")
        assert r.status_code == 200
        text = r.text
        assert "average_compliance_percent" in text or "compliance-percent" in text
        assert "total_compliant_resources" in text or "compliant-count" in text

    def test_costs_fields(self, client):
        r = client.get("/costs")
        assert r.status_code == 200
        text = r.text
        assert "total_cost" in text or "total-cost" in text
        assert "tenant_count" in text or "tenant-count" in text

    def test_resources_fields(self, client):
        r = client.get("/resources")
        assert r.status_code == 200
        text = r.text
        assert "resource_id" in text or "resource-id" in text
        assert "compliance_percent" in text or "compliance-percent" in text

    def test_identity_fields(self, client):
        r = client.get("/identity")
        assert r.status_code == 200
        text = r.text
        assert "role_name" in text or "role-name" in text

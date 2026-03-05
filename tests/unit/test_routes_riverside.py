"""Unit tests for Riverside compliance API routes.

Tests all Riverside endpoints with FastAPI TestClient:
- GET /riverside (dashboard page)
- GET /partials/riverside-badge
- GET /api/v1/riverside/summary
- GET /api/v1/riverside/mfa-status
- GET /api/v1/riverside/maturity-scores
- GET /api/v1/riverside/requirements
- GET /api/v1/riverside/gaps
- POST /api/v1/riverside/sync
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


@pytest.fixture
def test_db_session(db_session):
    """Database session with test data."""
    tenant = Tenant(
        id=str(uuid.uuid4()),
        tenant_id="riverside-tenant-123",
        name="Riverside Test Tenant",
        subscription_id="sub-riverside-123",
        is_active=True,
    )
    db_session.add(tenant)
    db_session.commit()
    
    user_tenant = UserTenant(
        id=str(uuid.uuid4()),
        user_id="user:admin",
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
    """Mock authenticated user with admin role."""
    return User(
        id="user-riverside-123",
        email="admin@riverside.test",
        name="Riverside Admin",
        roles=["admin", "operator"],
        tenant_ids=["riverside-tenant-123"],
        is_active=True,
        auth_provider="azure_ad",
    )


@pytest.fixture
def mock_riverside_service():
    """Mock RiversideService with common responses."""
    service = MagicMock()
    service.get_riverside_summary.return_value = {
        "total_critical_gaps": 12,
        "days_remaining": 425,
        "deadline": "2026-07-08",
        "financial_risk": 4000000,
        "overall_maturity": 65.5,
        "requirements_total": 45,
        "requirements_completed": 28,
        "requirements_in_progress": 12,
        "requirements_not_started": 5,
    }
    service.get_mfa_status.return_value = {
        "total_users": 250,
        "mfa_enabled": 180,
        "mfa_disabled": 70,
        "mfa_percentage": 72.0,
        "target_percentage": 100.0,
        "gap": 70,
    }
    service.get_maturity_scores.return_value = {
        "iam": {"score": 75.5, "max": 100, "grade": "B"},
        "governance": {"score": 62.0, "max": 100, "grade": "C"},
        "data_security": {"score": 58.5, "max": 100, "grade": "C"},
        "overall": {"score": 65.3, "max": 100, "grade": "C"},
    }
    service.get_requirements.return_value = {
        "requirements": [
            {"id": "IAM-001", "title": "MFA Enforcement", "category": "IAM", "priority": "P0", "status": "in_progress"},
            {"id": "GS-002", "title": "Conditional Access", "category": "GS", "priority": "P1", "status": "not_started"},
        ],
        "total": 2,
    }
    service.get_gaps.return_value = {
        "critical_gaps": [
            {"id": "GAP-001", "title": "MFA Gap", "severity": "critical", "affected_users": 70},
            {"id": "GAP-002", "title": "Legacy Auth", "severity": "high", "affected_users": 25},
        ],
        "total": 2,
    }
    service.sync_all.return_value = {
        "mfa": {"synced": 250, "errors": 0},
        "compliance": {"synced": 45, "errors": 0},
    }
    return service


# ============================================================================
# GET /riverside Tests
# ============================================================================

class TestRiversideDashboardPage:
    """Tests for GET /riverside dashboard page."""
    
    @patch("app.api.routes.riverside.get_current_user")
    def test_riverside_dashboard_renders_successfully(self, mock_get_user, client_with_db, mock_user):
        """Riverside dashboard page renders for authenticated users."""
        mock_get_user.return_value = mock_user
        
        response = client_with_db.get(
            "/riverside",
            headers={"Authorization": "Bearer fake-token"},
        )
        
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert b"riverside" in response.content.lower()
    
    def test_riverside_dashboard_requires_authentication(self, client_with_db):
        """Riverside dashboard returns 401 without authentication."""
        response = client_with_db.get("/riverside")
        
        assert response.status_code == 401


# ============================================================================
# GET /partials/riverside-badge Tests
# ============================================================================

class TestRiversideBadgePartial:
    """Tests for GET /partials/riverside-badge HTMX partial."""
    
    @patch("app.api.routes.riverside.get_current_user")
    @patch("app.api.routes.riverside.get_tenant_authorization")
    @patch("app.api.routes.riverside.RiversideService")
    def test_riverside_badge_returns_critical_gaps_count(self, mock_service_cls, mock_authz, mock_get_user, client_with_db, mock_user, mock_riverside_service):
        """Riverside badge partial returns critical gaps count."""
        mock_get_user.return_value = mock_user
        mock_authz.return_value.ensure_at_least_one_tenant.return_value = None
        mock_service_cls.return_value = mock_riverside_service
        
        response = client_with_db.get(
            "/partials/riverside-badge",
            headers={"Authorization": "Bearer fake-token"},
        )
        
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        # Should contain critical gaps count
        assert b"12" in response.content or b"critical" in response.content.lower()


# ============================================================================
# GET /api/v1/riverside/summary Tests
# ============================================================================

class TestRiversideSummaryEndpoint:
    """Tests for GET /api/v1/riverside/summary endpoint."""
    
    @patch("app.api.routes.riverside.get_current_user")
    @patch("app.api.routes.riverside.get_tenant_authorization")
    @patch("app.api.routes.riverside.RiversideService")
    def test_summary_returns_executive_overview(self, mock_service_cls, mock_authz, mock_get_user, client_with_db, mock_user, mock_riverside_service):
        """Summary endpoint returns executive compliance overview."""
        mock_get_user.return_value = mock_user
        mock_authz.return_value.ensure_at_least_one_tenant.return_value = None
        mock_service_cls.return_value = mock_riverside_service
        
        response = client_with_db.get(
            "/api/v1/riverside/summary",
            headers={"Authorization": "Bearer fake-token"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_critical_gaps"] == 12
        assert data["days_remaining"] == 425
        assert data["financial_risk"] == 4000000
        assert data["overall_maturity"] == 65.5
    
    def test_summary_requires_authentication(self, client_with_db):
        """Summary endpoint returns 401 without authentication."""
        response = client_with_db.get("/api/v1/riverside/summary")
        
        assert response.status_code == 401


# ============================================================================
# GET /api/v1/riverside/mfa-status Tests
# ============================================================================

class TestRiversideMFAStatusEndpoint:
    """Tests for GET /api/v1/riverside/mfa-status endpoint."""
    
    @patch("app.api.routes.riverside.get_current_user")
    @patch("app.api.routes.riverside.get_tenant_authorization")
    @patch("app.api.routes.riverside.RiversideService")
    def test_mfa_status_returns_tenant_mfa_metrics(self, mock_service_cls, mock_authz, mock_get_user, client_with_db, mock_user, mock_riverside_service):
        """MFA status endpoint returns tenant-wide MFA metrics."""
        mock_get_user.return_value = mock_user
        mock_authz.return_value.ensure_at_least_one_tenant.return_value = None
        mock_service_cls.return_value = mock_riverside_service
        
        response = client_with_db.get(
            "/api/v1/riverside/mfa-status",
            headers={"Authorization": "Bearer fake-token"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_users"] == 250
        assert data["mfa_enabled"] == 180
        assert data["mfa_percentage"] == 72.0
        assert data["gap"] == 70


# ============================================================================
# GET /api/v1/riverside/maturity-scores Tests
# ============================================================================

class TestRiversideMaturityScoresEndpoint:
    """Tests for GET /api/v1/riverside/maturity-scores endpoint."""
    
    @patch("app.api.routes.riverside.get_current_user")
    @patch("app.api.routes.riverside.get_tenant_authorization")
    @patch("app.api.routes.riverside.RiversideService")
    def test_maturity_scores_returns_domain_grades(self, mock_service_cls, mock_authz, mock_get_user, client_with_db, mock_user, mock_riverside_service):
        """Maturity scores endpoint returns scores per security domain."""
        mock_get_user.return_value = mock_user
        mock_authz.return_value.ensure_at_least_one_tenant.return_value = None
        mock_service_cls.return_value = mock_riverside_service
        
        response = client_with_db.get(
            "/api/v1/riverside/maturity-scores",
            headers={"Authorization": "Bearer fake-token"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "iam" in data
        assert "governance" in data
        assert "data_security" in data
        assert data["iam"]["grade"] == "B"
        assert data["overall"]["score"] == 65.3


# ============================================================================
# GET /api/v1/riverside/requirements Tests
# ============================================================================

class TestRiversideRequirementsEndpoint:
    """Tests for GET /api/v1/riverside/requirements endpoint."""
    
    @patch("app.api.routes.riverside.get_current_user")
    @patch("app.api.routes.riverside.get_tenant_authorization")
    @patch("app.api.routes.riverside.RiversideService")
    def test_requirements_returns_filtered_list(self, mock_service_cls, mock_authz, mock_get_user, client_with_db, mock_user, mock_riverside_service):
        """Requirements endpoint returns list with optional filtering."""
        mock_get_user.return_value = mock_user
        mock_authz.return_value.ensure_at_least_one_tenant.return_value = None
        mock_service_cls.return_value = mock_riverside_service
        
        response = client_with_db.get(
            "/api/v1/riverside/requirements?category=IAM&priority=P0",
            headers={"Authorization": "Bearer fake-token"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "requirements" in data
        assert data["total"] == 2
        assert len(data["requirements"]) == 2
    
    @patch("app.api.routes.riverside.get_current_user")
    @patch("app.api.routes.riverside.get_tenant_authorization")
    @patch("app.api.routes.riverside.RiversideService")
    def test_requirements_accepts_status_filter(self, mock_service_cls, mock_authz, mock_get_user, client_with_db, mock_user, mock_riverside_service):
        """Requirements endpoint accepts status filter parameter."""
        mock_get_user.return_value = mock_user
        mock_authz.return_value.ensure_at_least_one_tenant.return_value = None
        mock_service_cls.return_value = mock_riverside_service
        
        response = client_with_db.get(
            "/api/v1/riverside/requirements?status=in_progress",
            headers={"Authorization": "Bearer fake-token"},
        )
        
        assert response.status_code == 200
        # Service should have been called with status filter
        mock_riverside_service.get_requirements.assert_called_once()


# ============================================================================
# GET /api/v1/riverside/gaps Tests
# ============================================================================

class TestRiversideGapsEndpoint:
    """Tests for GET /api/v1/riverside/gaps endpoint."""
    
    @patch("app.api.routes.riverside.get_current_user")
    @patch("app.api.routes.riverside.get_tenant_authorization")
    @patch("app.api.routes.riverside.RiversideService")
    def test_gaps_returns_critical_security_gaps(self, mock_service_cls, mock_authz, mock_get_user, client_with_db, mock_user, mock_riverside_service):
        """Gaps endpoint returns critical security gaps analysis."""
        mock_get_user.return_value = mock_user
        mock_authz.return_value.ensure_at_least_one_tenant.return_value = None
        mock_service_cls.return_value = mock_riverside_service
        
        response = client_with_db.get(
            "/api/v1/riverside/gaps",
            headers={"Authorization": "Bearer fake-token"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "critical_gaps" in data
        assert data["total"] == 2
        assert data["critical_gaps"][0]["severity"] == "critical"


# ============================================================================
# POST /api/v1/riverside/sync Tests
# ============================================================================

class TestRiversideSyncEndpoint:
    """Tests for POST /api/v1/riverside/sync endpoint."""
    
    @patch("app.api.routes.riverside.get_current_user")
    @patch("app.api.routes.riverside.get_tenant_authorization")
    @patch("app.api.routes.riverside.RiversideService")
    def test_sync_succeeds_for_admin_users(self, mock_service_cls, mock_authz, mock_get_user, client_with_db, mock_user, mock_riverside_service):
        """Sync endpoint succeeds for users with admin/operator role."""
        mock_get_user.return_value = mock_user
        mock_authz.return_value.ensure_at_least_one_tenant.return_value = None
        mock_service_cls.return_value = mock_riverside_service
        
        response = client_with_db.post(
            "/api/v1/riverside/sync",
            headers={"Authorization": "Bearer fake-token"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "results" in data
        assert data["results"]["mfa"]["synced"] == 250
    
    @patch("app.api.routes.riverside.get_current_user")
    @patch("app.api.routes.riverside.get_tenant_authorization")
    def test_sync_forbidden_for_regular_users(self, mock_authz, mock_get_user, client_with_db):
        """Sync endpoint returns 403 for users without admin/operator role."""
        regular_user = User(
            id="user-regular",
            email="user@example.com",
            name="Regular User",
            roles=["user"],
            tenant_ids=["riverside-tenant-123"],
            is_active=True,
            auth_provider="azure_ad",
        )
        mock_get_user.return_value = regular_user
        mock_authz.return_value.ensure_at_least_one_tenant.return_value = None
        
        response = client_with_db.post(
            "/api/v1/riverside/sync",
            headers={"Authorization": "Bearer fake-token"},
        )
        
        assert response.status_code == 403
        assert "operator or admin role" in response.json()["detail"]

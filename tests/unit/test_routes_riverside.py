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
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.auth import User, get_current_user
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
    """Mock RiversideService with common async responses using AsyncMock.

    NOTE: get_requirements is synchronous because the route doesn't await it.
    All other methods are async because their routes use 'await'.
    """
    service = MagicMock()

    # Async methods (routes use 'await service.method()')
    service.get_riverside_summary = AsyncMock(
        return_value={
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
    )
    service.get_mfa_status = AsyncMock(
        return_value={
            "total_users": 250,
            "mfa_enabled": 180,
            "mfa_disabled": 70,
            "mfa_percentage": 72.0,
            "target_percentage": 100.0,
            "gap": 70,
        }
    )
    service.get_maturity_scores = AsyncMock(
        return_value={
            "iam": {"score": 75.5, "max": 100, "grade": "B"},
            "governance": {"score": 62.0, "max": 100, "grade": "C"},
            "data_security": {"score": 58.5, "max": 100, "grade": "C"},
            "overall": {"score": 65.3, "max": 100, "grade": "C"},
        }
    )
    service.get_gaps = AsyncMock(
        return_value={
            "critical_gaps": [
                {"id": "GAP-001", "title": "MFA Gap", "severity": "critical", "affected_users": 70},
                {"id": "GAP-002", "title": "Legacy Auth", "severity": "high", "affected_users": 25},
            ],
            "total": 2,
        }
    )
    service.sync_all = AsyncMock(
        return_value={
            "mfa": {"synced": 250, "errors": 0},
            "compliance": {"synced": 45, "errors": 0},
        }
    )

    # SYNC method (route does NOT await: 'return service.get_requirements(...)')
    service.get_requirements = MagicMock(
        return_value={
            "requirements": [
                {
                    "id": "IAM-001",
                    "title": "MFA Enforcement",
                    "category": "IAM",
                    "priority": "P0",
                    "status": "in_progress",
                },
                {
                    "id": "GS-002",
                    "title": "Conditional Access",
                    "category": "GS",
                    "priority": "P1",
                    "status": "not_started",
                },
            ],
            "total": 2,
        }
    )

    return service


# ============================================================================
# GET /riverside Tests
# ============================================================================


class TestRiversideDashboardPage:
    """Tests for GET /riverside dashboard page."""

    def test_riverside_dashboard_renders_successfully(self, authed_client):
        """Riverside dashboard page renders for authenticated users."""
        response = authed_client.get("/riverside")

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

    @patch("app.api.routes.riverside.RiversideService")
    def test_riverside_badge_returns_critical_gaps_count(
        self,
        mock_service_cls,
        authed_client,
        mock_riverside_service,
    ):
        """Riverside badge partial returns critical gaps count."""
        mock_service_cls.return_value = mock_riverside_service

        response = authed_client.get("/partials/riverside-badge")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        # Should contain critical gaps count
        assert b"12" in response.content or b"critical" in response.content.lower()


# ============================================================================
# GET /api/v1/riverside/summary Tests
# ============================================================================


class TestRiversideSummaryEndpoint:
    """Tests for GET /api/v1/riverside/summary endpoint."""

    @patch("app.api.routes.riverside.RiversideService")
    def test_summary_returns_executive_overview(
        self,
        mock_service_cls,
        authed_client,
        mock_riverside_service,
    ):
        """Summary endpoint returns executive compliance overview."""
        mock_service_cls.return_value = mock_riverside_service

        response = authed_client.get("/api/v1/riverside/summary")

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

    @patch("app.api.routes.riverside.RiversideService")
    def test_mfa_status_returns_tenant_mfa_metrics(
        self,
        mock_service_cls,
        authed_client,
        mock_riverside_service,
    ):
        """MFA status endpoint returns tenant-wide MFA metrics."""
        mock_service_cls.return_value = mock_riverside_service

        response = authed_client.get("/api/v1/riverside/mfa-status")

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

    @patch("app.api.routes.riverside.RiversideService")
    def test_maturity_scores_returns_domain_grades(
        self,
        mock_service_cls,
        authed_client,
        mock_riverside_service,
    ):
        """Maturity scores endpoint returns scores per security domain."""
        mock_service_cls.return_value = mock_riverside_service

        response = authed_client.get("/api/v1/riverside/maturity-scores")

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

    @patch("app.api.routes.riverside.RiversideService")
    def test_requirements_returns_filtered_list(
        self,
        mock_service_cls,
        authed_client,
        mock_riverside_service,
    ):
        """Requirements endpoint returns list with optional filtering."""
        mock_service_cls.return_value = mock_riverside_service

        response = authed_client.get("/api/v1/riverside/requirements?category=IAM&priority=P0")

        assert response.status_code == 200
        data = response.json()
        assert "requirements" in data
        assert data["total"] == 2
        assert len(data["requirements"]) == 2

    @patch("app.api.routes.riverside.RiversideService")
    def test_requirements_accepts_status_filter(
        self,
        mock_service_cls,
        authed_client,
        mock_riverside_service,
    ):
        """Requirements endpoint accepts status filter parameter."""
        mock_service_cls.return_value = mock_riverside_service

        response = authed_client.get("/api/v1/riverside/requirements?status=in_progress")

        assert response.status_code == 200
        # Service should have been called with status filter
        mock_riverside_service.get_requirements.assert_called_once()

    @patch("app.api.routes.riverside.RiversideService")
    def test_requirements_returns_html_partial_for_htmx_request(
        self,
        mock_service_cls,
        authed_client,
        mock_riverside_service,
    ):
        """HX-Request header → partial HTML (f8f2 content negotiation).

        Pages/riverside.html uses HTMX to fetch this endpoint with hx-get.
        HTMX always sends `HX-Request: true`. The route must detect that
        and render partials/riverside_requirements_list.html directly so
        no inline JS string-template rendering is needed in the page.
        """
        mock_service_cls.return_value = mock_riverside_service

        response = authed_client.get(
            "/api/v1/riverside/requirements",
            headers={"HX-Request": "true"},
        )

        assert response.status_code == 200
        # Content-type is HTML, not JSON
        assert "text/html" in response.headers["content-type"], (
            f"expected text/html, got {response.headers.get('content-type')}"
        )
        body = response.text
        # Partial root element is rendered
        assert 'id="riverside-requirements-list"' in body, (
            "partial root div missing — TemplateResponse likely failed"
        )
        # Mock requirements flow through to the table
        assert "IAM-001" in body and "GS-002" in body
        assert "MFA Enforcement" in body

    @patch("app.api.routes.riverside.RiversideService")
    def test_requirements_returns_json_without_htmx_header(
        self,
        mock_service_cls,
        authed_client,
        mock_riverside_service,
    ):
        """Absence of HX-Request header → JSON (API-consumer path unchanged).

        Programmatic consumers (preflight checks, staging e2e) don't send
        HX-Request, so they still get the original JSON response.
        """
        mock_service_cls.return_value = mock_riverside_service

        response = authed_client.get("/api/v1/riverside/requirements")

        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]
        data = response.json()
        assert "requirements" in data
        assert data["total"] == 2


# ============================================================================
# GET /api/v1/riverside/gaps Tests
# ============================================================================


class TestRiversideGapsEndpoint:
    """Tests for GET /api/v1/riverside/gaps endpoint."""

    @patch("app.api.routes.riverside.RiversideService")
    def test_gaps_returns_critical_security_gaps(
        self,
        mock_service_cls,
        authed_client,
        mock_riverside_service,
    ):
        """Gaps endpoint returns critical security gaps analysis."""
        mock_service_cls.return_value = mock_riverside_service

        response = authed_client.get("/api/v1/riverside/gaps")

        assert response.status_code == 200
        data = response.json()
        assert "critical_gaps" in data
        assert data["total"] == 2
        assert data["critical_gaps"][0]["severity"] == "critical"

    @patch("app.api.routes.riverside.RiversideService")
    def test_gaps_returns_html_partial_for_htmx_request(
        self,
        mock_service_cls,
        authed_client,
        mock_riverside_service,
    ):
        """HX-Request header → renders partials/riverside_alerts_panel.html (f8f2)."""
        mock_service_cls.return_value = mock_riverside_service

        response = authed_client.get(
            "/api/v1/riverside/gaps",
            headers={"HX-Request": "true"},
        )

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        body = response.text
        # Partial root element is rendered
        assert 'id="riverside-alerts-panel"' in body, "alerts panel partial root div missing"
        # Mock gap titles flow through
        assert "MFA Gap" in body and "Legacy Auth" in body


# ============================================================================
# POST /api/v1/riverside/sync Tests
# ============================================================================


class TestRiversideSyncEndpoint:
    """Tests for POST /api/v1/riverside/sync endpoint."""

    @patch("app.api.routes.riverside.RiversideService")
    def test_sync_succeeds_for_admin_users(
        self,
        mock_service_cls,
        authed_client,
        mock_riverside_service,
    ):
        """Sync endpoint succeeds for users with admin/operator role."""
        mock_service_cls.return_value = mock_riverside_service

        response = authed_client.post("/api/v1/riverside/sync")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "results" in data
        assert data["results"]["mfa"]["synced"] == 250

    @patch("app.api.routes.riverside.get_current_user")
    @patch("app.api.routes.riverside.get_tenant_authorization")
    def test_sync_forbidden_for_regular_users(self, mock_authz, mock_get_user, client_with_db):
        """Sync endpoint returns 403 for users without admin/operator role."""
        # Create user without admin/operator role
        regular_user = User(
            id="user-regular-123",
            email="user@riverside.test",
            name="Regular User",
            roles=["viewer"],  # No admin or operator
            tenant_ids=["riverside-tenant-123"],
            is_active=True,
            auth_provider="azure_ad",
        )
        mock_get_user.return_value = regular_user
        mock_authz.return_value.ensure_at_least_one_tenant.return_value = None

        # Apply the override
        from app.main import app

        app.dependency_overrides[get_current_user] = lambda: regular_user

        try:
            response = client_with_db.post(
                "/api/v1/riverside/sync",
                headers={"Authorization": "Bearer fake-token"},
            )

            assert response.status_code == 403
            assert "operator or admin role" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_current_user, None)

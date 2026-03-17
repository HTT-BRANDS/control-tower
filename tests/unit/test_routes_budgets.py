"""Unit tests for budget management API routes.

Tests all budget endpoints with FastAPI TestClient:
- GET /api/v1/budgets - List budgets
- POST /api/v1/budgets - Create budget
- GET /api/v1/budgets/summary - Budget summary
- GET /api/v1/budgets/{id} - Get budget details
- PATCH /api/v1/budgets/{id} - Update budget
- DELETE /api/v1/budgets/{id} - Delete budget
- GET /api/v1/budgets/{id}/alerts - Get budget alerts
- POST /api/v1/budgets/{id}/sync - Sync from Azure
"""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.budget import (
    BudgetAlertResponse,
    BudgetListItem,
    BudgetResponse,
    BudgetSummary,
    BudgetSyncResultResponse,
)


# =============================================================================
# GET /api/v1/budgets Tests
# =============================================================================


class TestListBudgetsEndpoint:
    """Tests for GET /api/v1/budgets endpoint."""

    @patch("app.api.routes.budgets.BudgetService")
    def test_list_budgets_success(self, mock_service_cls, authed_client):
        """List budgets endpoint returns filtered budgets."""
        mock_svc = MagicMock()
        mock_svc.get_budgets = AsyncMock(
            return_value=[
                BudgetListItem(
                    id="budget-123",
                    name="Test Budget",
                    amount=1000.0,
                    current_spend=500.0,
                    utilization_percentage=50.0,
                    status="active",
                    time_grain="Monthly",
                    currency="USD",
                    start_date=date.today(),
                    end_date=date.today() + timedelta(days=30),
                    subscription_id="sub-123",
                    resource_group=None,
                    alert_count=0,
                    last_synced_at=None,
                )
            ]
        )
        mock_service_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/budgets?status=active&limit=10")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "Test Budget"
        assert data[0]["status"] == "active"

    def test_list_budgets_requires_auth(self, client):
        """List budgets endpoint returns 401 without authentication."""
        response = client.get("/api/v1/budgets")
        assert response.status_code == 401

    @patch("app.api.routes.budgets.BudgetService")
    def test_list_budgets_with_filters(self, mock_service_cls, authed_client):
        """List budgets supports filtering by tenant and subscription."""
        mock_svc = MagicMock()
        mock_svc.get_budgets = AsyncMock(return_value=[])
        mock_service_cls.return_value = mock_svc

        response = authed_client.get(
            "/api/v1/budgets?tenant_ids=tenant-1&subscription_ids=sub-1&status=warning"
        )

        assert response.status_code == 200
        mock_svc.get_budgets.assert_called_once()


# =============================================================================
# GET /api/v1/budgets/summary Tests
# =============================================================================


class TestBudgetSummaryEndpoint:
    """Tests for GET /api/v1/budgets/summary endpoint."""

    @patch("app.api.routes.budgets.BudgetService")
    def test_get_summary_success(self, mock_service_cls, authed_client):
        """Budget summary endpoint returns aggregated data."""
        mock_svc = MagicMock()
        mock_svc.get_budget_summary = AsyncMock(
            return_value=BudgetSummary(
                total_budgets=5,
                total_budget_amount=50000.0,
                total_current_spend=25000.0,
                overall_utilization=50.0,
                active_count=3,
                warning_count=1,
                critical_count=1,
                exceeded_count=0,
                pending_alerts=2,
                acknowledged_alerts=3,
                by_tenant=[],
            )
        )
        mock_service_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/budgets/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["total_budgets"] == 5
        assert data["overall_utilization"] == 50.0
        assert data["active_count"] == 3

    def test_get_summary_requires_auth(self, client):
        """Budget summary endpoint returns 401 without authentication."""
        response = client.get("/api/v1/budgets/summary")
        assert response.status_code == 401


# =============================================================================
# POST /api/v1/budgets Tests
# =============================================================================


class TestCreateBudgetEndpoint:
    """Tests for POST /api/v1/budgets endpoint."""

    @patch("app.api.routes.budgets.BudgetService")
    def test_create_budget_success(self, mock_service_cls, authed_client, db_session):
        """Create budget endpoint succeeds with valid data."""
        from app.models.tenant import Tenant

        # Ensure the test tenant exists
        tenant = db_session.query(Tenant).filter(Tenant.id == "test-tenant-123").first()
        if not tenant:
            tenant = Tenant(
                id="test-tenant-123",
                tenant_id="test-tenant-123",
                name="Test Tenant",
                is_active=True,
            )
            db_session.add(tenant)
            db_session.commit()

        mock_svc = MagicMock()
        mock_svc.create_budget = AsyncMock(
            return_value=BudgetResponse(
                id="new-budget-123",
                tenant_id="test-tenant-123",
                subscription_id="sub-123",
                name="New Budget",
                amount=10000.0,
                time_grain="Monthly",
                category="Cost",
                start_date=date.today(),
                end_date=date.today() + timedelta(days=30),
                currency="USD",
                current_spend=0.0,
                utilization_percentage=0.0,
                status="active",
                thresholds=[],
                recent_alerts=[],
                remaining_amount=10000.0,
                is_exceeded=False,
                days_remaining=30,
                created_at="2024-01-01T00:00:00",
                updated_at="2024-01-01T00:00:00",
            )
        )
        mock_service_cls.return_value = mock_svc

        budget_data = {
            "tenant_id": "test-tenant-123",
            "subscription_id": "sub-123",
            "name": "New Budget",
            "amount": 10000.0,
            "time_grain": "Monthly",
            "category": "Cost",
            "start_date": date.today().isoformat(),
            "thresholds": [{"percentage": 80.0, "alert_type": "warning"}],
        }

        response = authed_client.post("/api/v1/budgets", json=budget_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Budget"
        assert data["amount"] == 10000.0

    def test_create_budget_requires_auth(self, client):
        """Create budget endpoint returns 401 without authentication."""
        response = client.post("/api/v1/budgets", json={})
        assert response.status_code == 401


# =============================================================================
# GET /api/v1/budgets/{id} Tests
# =============================================================================


class TestGetBudgetEndpoint:
    """Tests for GET /api/v1/budgets/{id} endpoint."""

    @patch("app.api.routes.budgets.BudgetService")
    def test_get_budget_success(self, mock_service_cls, authed_client, db_session):
        """Get budget endpoint returns budget details."""
        from app.models.budget import Budget

        # Create budget in DB for tenant check
        budget = Budget(
            id="budget-123",
            tenant_id="test-tenant-123",
            subscription_id="sub-123",
            name="Test Budget",
            amount=5000.0,
            time_grain="Monthly",
            category="Cost",
            start_date=date.today(),
            current_spend=2000.0,
            utilization_percentage=40.0,
            status="active",
        )
        db_session.add(budget)
        db_session.commit()

        mock_svc = MagicMock()
        mock_svc.get_budget = AsyncMock(
            return_value=BudgetResponse(
                id="budget-123",
                tenant_id="test-tenant-123",
                subscription_id="sub-123",
                name="Test Budget",
                amount=5000.0,
                time_grain="Monthly",
                category="Cost",
                start_date=date.today(),
                currency="USD",
                current_spend=2000.0,
                utilization_percentage=40.0,
                status="active",
                thresholds=[],
                recent_alerts=[],
                remaining_amount=3000.0,
                is_exceeded=False,
                days_remaining=25,
                created_at="2024-01-01T00:00:00",
                updated_at="2024-01-01T00:00:00",
            )
        )
        mock_service_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/budgets/budget-123")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "budget-123"
        assert data["name"] == "Test Budget"

    def test_get_budget_not_found(self, authed_client):
        """Get budget returns 404 for non-existent budget."""
        response = authed_client.get("/api/v1/budgets/non-existent-id")
        assert response.status_code == 404

    def test_get_budget_requires_auth(self, client):
        """Get budget endpoint returns 401 without authentication."""
        response = client.get("/api/v1/budgets/some-id")
        assert response.status_code == 401


# =============================================================================
# PATCH /api/v1/budgets/{id} Tests
# =============================================================================


class TestUpdateBudgetEndpoint:
    """Tests for PATCH /api/v1/budgets/{id} endpoint."""

    @patch("app.api.routes.budgets.BudgetService")
    def test_update_budget_success(self, mock_service_cls, authed_client, db_session):
        """Update budget endpoint modifies budget."""
        from app.models.budget import Budget

        budget = Budget(
            id="budget-123",
            tenant_id="test-tenant-123",
            subscription_id="sub-123",
            name="Old Name",
            amount=1000.0,
            time_grain="Monthly",
            category="Cost",
            start_date=date.today(),
            current_spend=500.0,
            utilization_percentage=50.0,
            status="active",
        )
        db_session.add(budget)
        db_session.commit()

        mock_svc = MagicMock()
        mock_svc.update_budget = AsyncMock(
            return_value=BudgetResponse(
                id="budget-123",
                tenant_id="test-tenant-123",
                subscription_id="sub-123",
                name="Updated Name",
                amount=2000.0,
                time_grain="Monthly",
                category="Cost",
                start_date=date.today(),
                currency="USD",
                current_spend=500.0,
                utilization_percentage=25.0,
                status="active",
                thresholds=[],
                recent_alerts=[],
                remaining_amount=1500.0,
                is_exceeded=False,
                days_remaining=30,
                created_at="2024-01-01T00:00:00",
                updated_at="2024-01-02T00:00:00",
            )
        )
        mock_service_cls.return_value = mock_svc

        update_data = {"name": "Updated Name", "amount": 2000.0}
        response = authed_client.patch("/api/v1/budgets/budget-123", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["amount"] == 2000.0

    def test_update_budget_not_found(self, authed_client):
        """Update budget returns 404 for non-existent budget."""
        response = authed_client.patch(
            "/api/v1/budgets/non-existent", json={"name": "Updated"}
        )
        assert response.status_code == 404


# =============================================================================
# DELETE /api/v1/budgets/{id} Tests
# =============================================================================


class TestDeleteBudgetEndpoint:
    """Tests for DELETE /api/v1/budgets/{id} endpoint."""

    @patch("app.api.routes.budgets.BudgetService")
    def test_delete_budget_success(self, mock_service_cls, authed_client, db_session):
        """Delete budget endpoint removes budget."""
        from app.models.budget import Budget

        budget = Budget(
            id="budget-123",
            tenant_id="test-tenant-123",
            subscription_id="sub-123",
            name="Budget to Delete",
            amount=1000.0,
            time_grain="Monthly",
            category="Cost",
            start_date=date.today(),
            current_spend=0.0,
            utilization_percentage=0.0,
            status="active",
        )
        db_session.add(budget)
        db_session.commit()

        mock_svc = MagicMock()
        mock_svc.delete_budget = AsyncMock(return_value=True)
        mock_service_cls.return_value = mock_svc

        response = authed_client.delete("/api/v1/budgets/budget-123")

        assert response.status_code == 204

    def test_delete_budget_not_found(self, authed_client):
        """Delete budget returns 404 for non-existent budget."""
        response = authed_client.delete("/api/v1/budgets/non-existent")
        assert response.status_code == 404


# =============================================================================
# GET /api/v1/budgets/{id}/alerts Tests
# =============================================================================


class TestGetBudgetAlertsEndpoint:
    """Tests for GET /api/v1/budgets/{id}/alerts endpoint."""

    @patch("app.api.routes.budgets.BudgetService")
    def test_get_budget_alerts_success(self, mock_service_cls, authed_client, db_session):
        """Get budget alerts endpoint returns alerts."""
        from app.models.budget import Budget

        budget = Budget(
            id="budget-123",
            tenant_id="test-tenant-123",
            subscription_id="sub-123",
            name="Test Budget",
            amount=1000.0,
            time_grain="Monthly",
            category="Cost",
            start_date=date.today(),
            current_spend=900.0,
            utilization_percentage=90.0,
            status="warning",
        )
        db_session.add(budget)
        db_session.commit()

        mock_svc = MagicMock()
        mock_svc.get_budget_alerts = AsyncMock(
            return_value=[
                BudgetAlertResponse(
                    id=1,
                    budget_id="budget-123",
                    budget_name="Test Budget",
                    tenant_id="test-tenant-123",
                    subscription_id="sub-123",
                    threshold_id=1,
                    alert_type="warning",
                    status="pending",
                    threshold_percentage=80.0,
                    threshold_amount=800.0,
                    current_spend=900.0,
                    forecasted_spend=None,
                    utilization_percentage=90.0,
                    triggered_at="2024-01-01T00:00:00",
                    acknowledged_at=None,
                    acknowledged_by=None,
                    resolved_at=None,
                    resolution_note=None,
                    notification_sent=False,
                    notification_sent_at=None,
                )
            ]
        )
        mock_service_cls.return_value = mock_svc

        response = authed_client.get("/api/v1/budgets/budget-123/alerts")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["alert_type"] == "warning"


# =============================================================================
# POST /api/v1/budgets/alerts/{id}/acknowledge Tests
# =============================================================================


class TestAcknowledgeAlertEndpoint:
    """Tests for POST /api/v1/budgets/alerts/{id}/acknowledge endpoint."""

    @patch("app.api.routes.budgets.BudgetService")
    def test_acknowledge_alert_success(self, mock_service_cls, authed_client, db_session):
        """Acknowledge alert endpoint succeeds."""
        from app.models.budget import Budget, BudgetAlert

        budget = Budget(
            id="budget-123",
            tenant_id="test-tenant-123",
            subscription_id="sub-123",
            name="Test Budget",
            amount=1000.0,
            time_grain="Monthly",
            category="Cost",
            start_date=date.today(),
            current_spend=900.0,
            utilization_percentage=90.0,
            status="warning",
        )
        db_session.add(budget)
        db_session.flush()

        alert = BudgetAlert(
            budget_id="budget-123",
            alert_type="warning",
            status="pending",
            threshold_percentage=80.0,
            threshold_amount=800.0,
            current_spend=900.0,
            utilization_percentage=90.0,
        )
        db_session.add(alert)
        db_session.commit()

        mock_svc = MagicMock()
        mock_svc.acknowledge_alert = AsyncMock(return_value=True)
        mock_service_cls.return_value = mock_svc

        response = authed_client.post(f"/api/v1/budgets/alerts/{alert.id}/acknowledge")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


# =============================================================================
# POST /api/v1/budgets/{id}/sync Tests
# =============================================================================


class TestSyncBudgetEndpoint:
    """Tests for POST /api/v1/budgets/{id}/sync endpoint."""

    @patch("app.api.routes.budgets.BudgetService")
    def test_sync_budget_success(self, mock_service_cls, authed_client, db_session):
        """Sync budget endpoint triggers Azure sync."""
        from app.models.budget import Budget

        budget = Budget(
            id="budget-123",
            tenant_id="test-tenant-123",
            subscription_id="sub-123",
            name="Test Budget",
            amount=1000.0,
            time_grain="Monthly",
            category="Cost",
            start_date=date.today(),
            current_spend=500.0,
            utilization_percentage=50.0,
            status="active",
        )
        db_session.add(budget)
        db_session.commit()

        mock_svc = MagicMock()
        mock_svc.sync_budgets_from_azure = AsyncMock(
            return_value=BudgetSyncResultResponse(
                id=1,
                tenant_id="test-tenant-123",
                sync_type="incremental",
                status="completed",
                budgets_synced=5,
                budgets_created=0,
                budgets_updated=5,
                budgets_deleted=0,
                alerts_triggered=1,
                errors_count=0,
                error_message=None,
                error_details=None,
                started_at="2024-01-01T00:00:00",
                completed_at="2024-01-01T00:01:00",
                duration_seconds=60.0,
            )
        )
        mock_service_cls.return_value = mock_svc

        response = authed_client.post("/api/v1/budgets/budget-123/sync")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["budgets_synced"] == 5


# =============================================================================
# POST /api/v1/budgets/sync/all Tests
# =============================================================================


class TestSyncAllBudgetsEndpoint:
    """Tests for POST /api/v1/budgets/sync/all endpoint."""

    @patch("app.api.routes.budgets.BudgetService")
    def test_sync_all_budgets_success(self, mock_service_cls, authed_client):
        """Sync all budgets endpoint triggers sync for accessible tenants."""
        mock_svc = MagicMock()
        mock_svc.sync_budgets_from_azure = AsyncMock(
            return_value=BudgetSyncResultResponse(
                id=1,
                tenant_id="test-tenant-123",
                sync_type="incremental",
                status="completed",
                budgets_synced=10,
                budgets_created=1,
                budgets_updated=9,
                budgets_deleted=0,
                alerts_triggered=2,
                errors_count=0,
                error_message=None,
                error_details=None,
                started_at="2024-01-01T00:00:00",
                completed_at="2024-01-01T00:05:00",
                duration_seconds=300.0,
            )
        )
        mock_service_cls.return_value = mock_svc

        response = authed_client.post("/api/v1/budgets/sync/all")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["budgets_synced"] == 10

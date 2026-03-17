"""Unit tests for BudgetService.

Tests budget CRUD operations, Azure sync, threshold checking, and alert management.
"""

import sys
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock the cache decorator BEFORE importing the service

def no_op_cache(cache_key):
    """Decorator that does nothing - bypasses caching."""
    def decorator(func):
        return func
    return decorator


# Patch the cache module before importing budget_service
with patch("app.core.cache.cached", no_op_cache):
    # Remove from cache if already imported
    if "app.api.services.budget_service" in sys.modules:
        del sys.modules["app.api.services.budget_service"]
    from app.api.services.budget_service import BudgetService

from app.models.budget import (
    AlertStatus,
    AlertType,
    Budget,
    BudgetAlert,
    BudgetStatus,
)
from app.models.tenant import Tenant
from app.schemas.budget import (
    BudgetCreate,
    BudgetThresholdConfig,
    BudgetUpdate,
)


class TestBudgetServiceCRUD:
    """Test suite for BudgetService CRUD operations."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def budget_service(self, mock_db):
        """Create BudgetService instance."""
        return BudgetService(db=mock_db)

    @pytest.fixture
    def sample_budget(self):
        """Create sample budget model."""
        budget = MagicMock(spec=Budget)
        budget.id = "test-budget-123"
        budget.tenant_id = "tenant-123"
        budget.subscription_id = "sub-123"
        budget.name = "Test Budget"
        budget.amount = 1000.0
        budget.current_spend = 500.0
        budget.utilization_percentage = 50.0
        budget.status = BudgetStatus.ACTIVE
        budget.time_grain = "Monthly"
        budget.category = "Cost"
        budget.currency = "USD"
        budget.start_date = date.today()
        budget.end_date = date.today() + timedelta(days=30)
        budget.resource_group = None
        budget.azure_budget_id = None
        budget.etag = None
        budget.created_at = datetime.utcnow()
        budget.updated_at = datetime.utcnow()
        budget.last_synced_at = None
        budget.thresholds = []
        budget.alerts = MagicMock()
        budget.alerts.order_by.return_value.limit.return_value.all.return_value = []
        return budget

    @pytest.mark.asyncio
    async def test_get_budgets_with_filters(self, budget_service, mock_db):
        """Test get_budgets with tenant and status filters."""
        # Setup mock
        mock_budget = MagicMock(spec=Budget)
        mock_budget.id = "test-123"
        mock_budget.name = "Test Budget"
        mock_budget.amount = 1000.0
        mock_budget.current_spend = 500.0
        mock_budget.utilization_percentage = 50.0
        mock_budget.status = BudgetStatus.ACTIVE
        mock_budget.time_grain = "Monthly"
        mock_budget.currency = "USD"
        mock_budget.start_date = date.today()
        mock_budget.end_date = date.today() + timedelta(days=30)
        mock_budget.subscription_id = "sub-123"
        mock_budget.resource_group = None
        mock_budget.last_synced_at = None
        mock_budget.alerts = MagicMock()
        mock_budget.alerts.filter.return_value.count.return_value = 0

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [
            mock_budget
        ]
        mock_db.query.return_value = mock_query

        # Execute
        result = await budget_service.get_budgets(
            tenant_ids=["tenant-123"],
            status=BudgetStatus.ACTIVE,
        )

        # Verify
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].id == "test-123"
        assert result[0].status == BudgetStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_get_budget_by_id_success(self, budget_service, mock_db, sample_budget):
        """Test get_budget returns budget details."""
        # Setup mock
        mock_db.query.return_value.filter.return_value.first.return_value = sample_budget

        # Execute
        result = await budget_service.get_budget("test-budget-123")

        # Verify
        assert result is not None
        assert result.id == "test-budget-123"
        assert result.name == "Test Budget"
        assert result.amount == 1000.0

    @pytest.mark.asyncio
    async def test_get_budget_not_found(self, budget_service, mock_db):
        """Test get_budget returns None for non-existent budget."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = await budget_service.get_budget("non-existent")

        assert result is None

    @pytest.mark.asyncio
    async def test_create_budget_success(self, budget_service, mock_db):
        """Test create_budget creates budget with thresholds."""
        # Setup data
        data = BudgetCreate(
            tenant_id="tenant-123",
            subscription_id="sub-123",
            name="New Budget",
            amount=5000.0,
            time_grain="Monthly",
            category="Cost",
            start_date=date.today(),
            thresholds=[
                BudgetThresholdConfig(percentage=80.0, alert_type="warning"),
                BudgetThresholdConfig(percentage=100.0, alert_type="critical"),
            ],
        )

        # Mock Azure creation to avoid network calls
        with patch.object(budget_service, "_create_budget_in_azure", new_callable=AsyncMock):
            result = await budget_service.create_budget(data)

        # Verify
        assert result is not None
        assert result.name == "New Budget"
        assert result.amount == 5000.0
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_update_budget_success(self, budget_service, mock_db, sample_budget):
        """Test update_budget modifies budget fields."""
        # Setup
        mock_db.query.return_value.filter.return_value.first.return_value = sample_budget

        with patch.object(budget_service, "_update_budget_in_azure", new_callable=AsyncMock):
            data = BudgetUpdate(name="Updated Budget", amount=2000.0)
            result = await budget_service.update_budget("test-budget-123", data)

        # Verify
        assert result is not None
        assert result.name == "Updated Budget"
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_update_budget_not_found(self, budget_service, mock_db):
        """Test update_budget returns None for non-existent budget."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        data = BudgetUpdate(name="Updated")
        result = await budget_service.update_budget("non-existent", data)

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_budget_success(self, budget_service, mock_db, sample_budget):
        """Test delete_budget removes budget."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_budget

        with patch.object(budget_service, "_delete_budget_from_azure", new_callable=AsyncMock):
            result = await budget_service.delete_budget("test-budget-123")

        assert result is True
        mock_db.delete.assert_called_once_with(sample_budget)
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_delete_budget_not_found(self, budget_service, mock_db):
        """Test delete_budget returns False for non-existent budget."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = await budget_service.delete_budget("non-existent")

        assert result is False


class TestBudgetServiceAlerts:
    """Test suite for budget alert operations."""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def budget_service(self, mock_db):
        return BudgetService(db=mock_db)

    @pytest.fixture
    def sample_alert(self):
        alert = MagicMock(spec=BudgetAlert)
        alert.id = 1
        alert.budget_id = "budget-123"
        alert.threshold_id = 1
        alert.alert_type = AlertType.WARNING
        alert.status = AlertStatus.PENDING
        alert.threshold_percentage = 80.0
        alert.threshold_amount = 800.0
        alert.current_spend = 850.0
        alert.forecasted_spend = None
        alert.utilization_percentage = 85.0
        alert.triggered_at = datetime.utcnow()
        alert.acknowledged_at = None
        alert.acknowledged_by = None
        alert.resolved_at = None
        alert.resolution_note = None
        alert.notification_sent = False
        alert.notification_sent_at = None
        alert.budget = MagicMock()
        alert.budget.name = "Test Budget"
        alert.budget.tenant_id = "tenant-123"
        alert.budget.subscription_id = "sub-123"
        return alert

    @pytest.mark.asyncio
    async def test_get_budget_alerts(self, budget_service, mock_db, sample_alert):
        """Test get_budget_alerts returns filtered alerts."""
        mock_db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [
            sample_alert
        ]

        result = await budget_service.get_budget_alerts(
            budget_id="budget-123",
            status=AlertStatus.PENDING,
        )

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].id == 1
        assert result[0].status == AlertStatus.PENDING

    @pytest.mark.asyncio
    async def test_acknowledge_alert_success(self, budget_service, mock_db, sample_alert):
        """Test acknowledge_alert marks alert as acknowledged."""
        mock_db.query.return_value.filter.return_value.first.return_value = sample_alert

        result = await budget_service.acknowledge_alert(1, "user-123", "Noted")

        assert result is True
        assert sample_alert.status == AlertStatus.ACKNOWLEDGED
        assert sample_alert.acknowledged_by == "user-123"
        assert sample_alert.resolution_note == "Noted"
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_acknowledge_alert_not_found(self, budget_service, mock_db):
        """Test acknowledge_alert returns False for non-existent alert."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = await budget_service.acknowledge_alert(999, "user-123")

        assert result is False

    @pytest.mark.asyncio
    async def test_bulk_acknowledge_alerts(self, budget_service, mock_db):
        """Test bulk_acknowledge_alerts handles multiple alerts."""
        alerts = []
        for i in range(3):
            alert = MagicMock(spec=BudgetAlert)
            alert.id = i + 1
            alert.budget = MagicMock()
            alert.budget.tenant_id = "tenant-123"
            alerts.append(alert)

        mock_db.query.return_value.filter.return_value.first.side_effect = alerts

        result = await budget_service.bulk_acknowledge_alerts([1, 2, 3], "user-123")

        assert result.success is True
        assert result.acknowledged_count == 3
        assert len(result.failed_ids) == 0


class TestBudgetServiceSummary:
    """Test suite for budget summary operations."""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def budget_service(self, mock_db):
        return BudgetService(db=mock_db)

    @pytest.mark.asyncio
    async def test_get_budget_summary(self, budget_service, mock_db):
        """Test get_budget_summary returns aggregated data."""
        # Setup mock budgets
        budgets = []
        for i in range(3):
            budget = MagicMock(spec=Budget)
            budget.tenant_id = f"tenant-{i + 1}"
            budget.amount = 1000.0 * (i + 1)
            budget.current_spend = 500.0 * (i + 1)
            budget.status = BudgetStatus.ACTIVE if i < 2 else BudgetStatus.WARNING
            budgets.append(budget)

        tenants = []
        for i in range(3):
            tenant = MagicMock()
            tenant.id = f"tenant-{i + 1}"
            tenant.name = f"Tenant {i + 1}"
            tenants.append(tenant)

        # Setup mock queries - order matters
        def mock_query_side_effect(model):
            mock_q = MagicMock()
            if model == Budget:
                mock_q.filter.return_value = mock_q
                mock_q.all.return_value = budgets
            elif model.__name__ == 'BudgetAlert':
                mock_q.join.return_value.filter.return_value = mock_q
                mock_q.count.return_value = 1
            elif model == Tenant:
                mock_q.filter.return_value = mock_q
                mock_q.all.return_value = tenants
            return mock_q

        mock_db.query.side_effect = mock_query_side_effect

        result = await budget_service.get_budget_summary()

        assert result is not None
        assert result.total_budgets == 3
        assert result.total_budget_amount == 6000.0  # 1000 + 2000 + 3000
        assert result.total_current_spend == 3000.0  # 500 + 1000 + 1500

    @pytest.mark.asyncio
    async def test_get_budget_summary_empty(self, budget_service, mock_db):
        """Test get_budget_summary handles empty budget list."""
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = await budget_service.get_budget_summary()

        assert result is not None
        assert result.total_budgets == 0
        assert result.total_budget_amount == 0.0
        assert result.overall_utilization == 0.0


class TestBudgetServiceAzureSync:
    """Test suite for Azure sync operations."""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def budget_service(self, mock_db):
        return BudgetService(db=mock_db)

    @pytest.mark.asyncio
    async def test_fetch_budgets_from_azure(self, budget_service, mock_db):
        """Test _fetch_budgets_from_azure calls Azure API."""
        azure_response = {
            "value": [
                {
                    "id": "/subscriptions/sub-123/providers/Microsoft.Consumption/budgets/TestBudget",
                    "name": "TestBudget",
                    "etag": "abc123",
                    "properties": {
                        "amount": 1000.0,
                        "timeGrain": "Monthly",
                        "category": "Cost",
                        "timePeriod": {
                            "startDate": "2024-01-01",
                            "endDate": "2024-12-31",
                        },
                        "currentSpend": {"amount": 500.0, "unit": "USD"},
                        "forecast": {"amount": 900.0, "unit": "USD"},
                        "notifications": {
                            "Notification1": {
                                "enabled": True,
                                "operator": "GreaterThan",
                                "threshold": 80.0,
                                "contactEmails": ["admin@test.com"],
                            }
                        },
                    },
                }
            ]
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = azure_response
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

            with patch.object(budget_service, "db", mock_db):
                with patch(
                    "app.api.services.budget_service.azure_client_manager"
                ) as mock_azure:
                    mock_credential = MagicMock()
                    mock_token = MagicMock()
                    mock_token.token = "test-token"
                    mock_credential.get_token.return_value = mock_token
                    mock_azure.get_credential.return_value = mock_credential

                    result = await budget_service._fetch_budgets_from_azure(
                        "tenant-123", "sub-123"
                    )

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "TestBudget"

    @pytest.mark.asyncio
    async def test_sync_single_budget_create(self, budget_service, mock_db):
        """Test _sync_single_budget creates new budget."""
        azure_budget = {
            "id": "/subscriptions/sub-123/providers/Microsoft.Consumption/budgets/TestBudget",
            "name": "TestBudget",
            "etag": "abc123",
            "properties": {
                "amount": 1000.0,
                "timeGrain": "Monthly",
                "category": "Cost",
                "timePeriod": {"startDate": "2024-01-01", "endDate": "2024-12-31"},
                "currentSpend": {"amount": 500.0, "unit": "USD"},
                "forecast": {"amount": 900.0, "unit": "USD"},
                "notifications": {},
            },
        }

        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = await budget_service._sync_single_budget(
            "tenant-123", "sub-123", azure_budget
        )

        assert result == "created"
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_sync_single_budget_update(self, budget_service, mock_db):
        """Test _sync_single_budget updates existing budget."""
        existing_budget = MagicMock(spec=Budget)
        existing_budget.id = "existing-123"
        existing_budget.name = "OldName"
        existing_budget.amount = 500.0

        azure_budget = {
            "id": "/subscriptions/sub-123/providers/Microsoft.Consumption/budgets/TestBudget",
            "name": "NewName",
            "etag": "new-etag",
            "properties": {
                "amount": 1000.0,
                "timeGrain": "Monthly",
                "category": "Cost",
                "timePeriod": {"startDate": "2024-01-01", "endDate": "2024-12-31"},
                "currentSpend": {"amount": 600.0, "unit": "USD"},
                "forecast": {"amount": 950.0, "unit": "USD"},
                "notifications": {},
            },
        }

        mock_db.query.return_value.filter.return_value.first.return_value = existing_budget

        result = await budget_service._sync_single_budget(
            "tenant-123", "sub-123", azure_budget
        )

        assert result == "updated"
        assert existing_budget.name == "NewName"
        assert existing_budget.amount == 1000.0
        mock_db.commit.assert_called()

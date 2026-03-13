"""Tests for CostService summary and forecast methods.

Tests for cost summary, trends, tenant breakdowns, and forecasting.
10 tests covering:
- get_cost_summary (3 tests)
- get_cost_trends (2 tests)
- get_costs_by_tenant (2 tests)
- get_cost_forecast (3 tests)
"""

import sys
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest


# Mock the cache decorator BEFORE importing the service
def no_op_cache(cache_key):
    """Decorator that does nothing - bypasses caching."""

    def decorator(func):
        return func

    return decorator


# Patch the cache module before importing cost_service
with patch("app.core.cache.cached", no_op_cache):
    # Remove from cache if already imported
    if "app.api.services.cost_service" in sys.modules:
        del sys.modules["app.api.services.cost_service"]
    from app.api.services.cost_service import CostService

from app.models.cost import CostSnapshot  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402
from app.schemas.cost import (  # noqa: E402
    CostByTenant,
    CostForecast,
    CostSummary,
    CostTrend,
)


class TestCostServiceSummaries:
    """Test suite for CostService summary methods."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def cost_service(self, mock_db):
        """Create CostService instance."""
        return CostService(db=mock_db)

    @pytest.fixture
    def sample_cost_snapshots(self):
        """Create sample cost snapshots."""
        today = date.today()
        snapshots = []
        for i in range(30):
            snapshot = MagicMock(spec=CostSnapshot)
            snapshot.date = today - timedelta(days=i)
            snapshot.total_cost = 100.0 + (i * 5)
            snapshot.tenant_id = "tenant-1"
            snapshot.subscription_id = "sub-1"
            snapshot.service_name = "Compute" if i % 2 == 0 else "Storage"
            snapshots.append(snapshot)
        return snapshots

    @pytest.fixture
    def sample_tenants(self):
        """Create sample tenants."""
        tenants = []
        for i in range(3):
            tenant = MagicMock(spec=Tenant)
            tenant.id = f"tenant-{i + 1}"
            tenant.name = f"Tenant {i + 1}"
            tenant.is_active = True
            tenants.append(tenant)
        return tenants

    @pytest.mark.asyncio
    async def test_get_cost_summary_with_data(self, cost_service, mock_db, sample_cost_snapshots):
        """Test get_cost_summary with valid data."""
        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_cost_snapshots[:30]
        mock_db.query.return_value = mock_query

        # Execute
        result = await cost_service.get_cost_summary(period_days=30)

        # Verify
        assert isinstance(result, CostSummary)
        assert result.total_cost > 0
        assert result.currency == "USD"
        assert result.tenant_count > 0
        assert result.subscription_count > 0
        assert len(result.top_services) > 0

    @pytest.mark.asyncio
    async def test_get_cost_summary_empty_data(self):
        """Test get_cost_summary with no data."""
        # Create fresh mocks
        mock_db = MagicMock()
        service = CostService(db=mock_db)

        # Setup mock query to return empty
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query

        # Execute
        result = await service.get_cost_summary(period_days=30)

        # Verify
        assert isinstance(result, CostSummary)
        assert result.total_cost == 0
        assert result.tenant_count == 0
        assert result.subscription_count == 0
        assert result.cost_change_percent is None
        assert len(result.top_services) == 0

    @pytest.mark.asyncio
    async def test_get_cost_summary_with_change_percent(self):
        """Test get_cost_summary calculates change percentage correctly."""
        # Create fresh mocks and service
        mock_db = MagicMock()
        service = CostService(db=mock_db)

        # Create separate snapshots for current and previous periods
        today = date.today()

        current_period = []
        for i in range(15):
            snap = MagicMock(spec=CostSnapshot)
            snap.date = today - timedelta(days=i)
            snap.total_cost = 200.0
            snap.tenant_id = "tenant-1"
            snap.subscription_id = "sub-1"
            snap.service_name = "Compute"
            current_period.append(snap)

        previous_period = []
        for i in range(15):
            snap = MagicMock(spec=CostSnapshot)
            snap.date = today - timedelta(days=30 + i)
            snap.total_cost = 100.0
            snap.tenant_id = "tenant-1"
            snap.subscription_id = "sub-1"
            snap.service_name = "Compute"
            previous_period.append(snap)

        # Create two separate mock query chains
        current_query = MagicMock()
        current_query.filter.return_value = current_query
        current_query.all.return_value = current_period

        previous_query = MagicMock()
        previous_query.filter.return_value = previous_query
        previous_query.all.return_value = previous_period

        # Service makes 2 queries: current period, then previous period
        mock_db.query.side_effect = [current_query, previous_query]

        # Execute
        result = await service.get_cost_summary(period_days=30)

        # Verify - costs doubled (200 vs 100), so change should be 100%
        assert result.cost_change_percent is not None
        assert result.cost_change_percent == 100.0

    @pytest.mark.asyncio
    async def test_get_cost_trends_with_data(self, cost_service, mock_db, sample_cost_snapshots):
        """Test get_cost_trends returns daily aggregated costs."""
        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = sample_cost_snapshots
        mock_db.query.return_value = mock_query

        # Execute
        result = await cost_service.get_cost_trends(days=30)

        # Verify
        assert isinstance(result, list)
        assert all(isinstance(trend, CostTrend) for trend in result)
        assert len(result) > 0
        # Verify sorted by date
        dates = [trend.date for trend in result]
        assert dates == sorted(dates)

    @pytest.mark.asyncio
    async def test_get_cost_trends_empty_data(self):
        """Test get_cost_trends with no data."""
        # Create fresh mocks
        mock_db = MagicMock()
        service = CostService(db=mock_db)

        # Setup mock query to return empty
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query

        # Execute
        result = await service.get_cost_trends(days=30)

        # Verify
        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_costs_by_tenant_with_data(self):
        """Test get_costs_by_tenant returns costs grouped by tenant."""
        # Create fresh mocks and data
        mock_db = MagicMock()
        service = CostService(db=mock_db)

        # Create tenants
        tenants = []
        for i in range(3):
            tenant = MagicMock(spec=Tenant)
            tenant.id = f"tenant-{i + 1}"
            tenant.name = f"Tenant {i + 1}"
            tenant.is_active = True
            tenants.append(tenant)

        # Create cost snapshots
        today = date.today()
        snapshots = []
        for i in range(10):
            snap = MagicMock(spec=CostSnapshot)
            snap.date = today - timedelta(days=i)
            snap.total_cost = 100.0 + (i * 5)
            snap.tenant_id = "tenant-1"
            snap.subscription_id = "sub-1"
            snap.service_name = "Compute"
            snapshots.append(snap)

        # Setup mock queries
        def mock_query_side_effect(model):
            mock_q = MagicMock()
            if model == Tenant:
                mock_q.filter.return_value = mock_q
                mock_q.all.return_value = tenants
            elif model == CostSnapshot:
                mock_q.filter.return_value = mock_q
                mock_q.all.return_value = snapshots
            return mock_q

        mock_db.query.side_effect = mock_query_side_effect

        # Execute
        result = await service.get_costs_by_tenant(period_days=30)

        # Verify
        assert isinstance(result, list)
        assert all(isinstance(item, CostByTenant) for item in result)
        # Should be sorted by cost descending
        if len(result) > 1:
            for i in range(len(result) - 1):
                assert result[i].total_cost >= result[i + 1].total_cost

    @pytest.mark.asyncio
    async def test_get_costs_by_tenant_empty(self):
        """Test get_costs_by_tenant with no tenants."""
        # Create fresh mocks
        mock_db = MagicMock()
        service = CostService(db=mock_db)

        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query

        # Execute
        result = await service.get_costs_by_tenant(period_days=30)

        # Verify
        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_cost_forecast_with_sufficient_data(self):
        """Test get_cost_forecast generates forecast with sufficient data."""
        # Create fresh mocks
        mock_db = MagicMock()
        service = CostService(db=mock_db)

        # Create 90 days of historical data
        historical_data = []
        for i in range(90):
            row = MagicMock()
            row.date = date.today() - timedelta(days=90 - i)
            row.daily_cost = 100.0 + (i * 0.5)
            historical_data.append(row)

        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = historical_data
        mock_db.query.return_value = mock_query

        # Execute
        result = await service.get_cost_forecast(days=30)

        # Verify
        assert isinstance(result, list)
        assert len(result) == 30
        assert all(isinstance(item, CostForecast) for item in result)
        # Verify all forecasts have confidence intervals
        for forecast in result:
            assert forecast.forecasted_cost > 0
            assert forecast.confidence_lower is not None
            assert forecast.confidence_upper is not None
            assert forecast.confidence_lower <= forecast.forecasted_cost
            assert forecast.forecasted_cost <= forecast.confidence_upper

    @pytest.mark.asyncio
    async def test_get_cost_forecast_insufficient_data(self):
        """Test get_cost_forecast returns empty with insufficient data."""
        # Create fresh mocks
        mock_db = MagicMock()
        service = CostService(db=mock_db)

        # Only 5 days of data (less than 7 required)
        historical_data = []
        for i in range(5):
            row = MagicMock()
            row.date = date.today() - timedelta(days=5 - i)
            row.daily_cost = 100.0
            historical_data.append(row)

        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = historical_data
        mock_db.query.return_value = mock_query

        # Execute
        result = await service.get_cost_forecast(days=30)

        # Verify
        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_cost_forecast_zero_costs(self):
        """Test get_cost_forecast handles zero costs correctly."""
        # Create fresh mocks
        mock_db = MagicMock()
        service = CostService(db=mock_db)

        # Create 90 days of zero cost data
        historical_data = []
        for i in range(90):
            row = MagicMock()
            row.date = date.today() - timedelta(days=90 - i)
            row.daily_cost = 0.0
            historical_data.append(row)

        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = historical_data
        mock_db.query.return_value = mock_query

        # Execute
        result = await service.get_cost_forecast(days=30)

        # Verify - should still generate forecast
        assert isinstance(result, list)
        assert len(result) == 30
        # All forecasts should be >= 0
        for forecast in result:
            assert forecast.forecasted_cost >= 0
            assert forecast.confidence_lower >= 0

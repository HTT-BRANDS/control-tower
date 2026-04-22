"""Tests for CostService anomaly methods.

Tests for anomaly detection, acknowledgment, and grouping.
11 tests covering:
- get_anomalies (3 tests)
- get_anomalies_by_service (2 tests)
- get_top_anomalies (2 tests)
- acknowledge_anomaly (2 tests)
- bulk_acknowledge_anomalies (2 tests)
"""

import sys
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

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

from app.models.cost import CostAnomaly
from app.models.tenant import Tenant
from app.schemas.cost import (
    AnomaliesByService,
    BulkAcknowledgeResponse,
    TopAnomaly,
)


class TestCostServiceAnomalies:
    """Test suite for CostService anomaly methods."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def cost_service(self, mock_db):
        """Create CostService instance."""
        return CostService(db=mock_db)

    @pytest.fixture
    def sample_anomalies(self):
        """Create sample anomalies."""
        anomalies = []
        for i in range(5):
            anomaly = MagicMock(spec=CostAnomaly)
            anomaly.id = i + 1
            anomaly.tenant_id = "tenant-1"
            anomaly.subscription_id = "sub-1"
            anomaly.detected_at = datetime.utcnow() - timedelta(days=i)
            anomaly.anomaly_type = "spike"
            anomaly.description = f"Cost spike detected {i}"
            anomaly.expected_cost = 100.0
            anomaly.actual_cost = 200.0 + (i * 10)
            anomaly.percentage_change = 100.0 + (i * 10)
            anomaly.service_name = "Compute" if i % 2 == 0 else "Storage"
            anomaly.is_acknowledged = i < 2  # First 2 are acknowledged
            anomaly.acknowledged_by = "admin@test.com" if i < 2 else None
            anomaly.acknowledged_at = datetime.utcnow() if i < 2 else None
            anomalies.append(anomaly)
        return anomalies

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

    def test_get_anomalies_all(self, cost_service, mock_db, sample_anomalies):
        """Test get_anomalies returns all anomalies."""
        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = sample_anomalies
        mock_db.query.return_value = mock_query

        # Execute
        result = cost_service.get_anomalies()

        # Verify
        assert isinstance(result, list)
        assert len(result) == len(sample_anomalies)
        # Verify filter not called when acknowledged is None
        mock_query.filter.assert_not_called()

    def test_get_anomalies_acknowledged_only(self, cost_service, mock_db, sample_anomalies):
        """Test get_anomalies filters acknowledged anomalies."""
        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        acknowledged = [a for a in sample_anomalies if a.is_acknowledged]
        mock_query.all.return_value = acknowledged
        mock_db.query.return_value = mock_query

        # Execute
        result = cost_service.get_anomalies(acknowledged=True)

        # Verify
        assert isinstance(result, list)
        mock_query.filter.assert_called_once()

    def test_get_anomalies_unacknowledged_only(self, cost_service, mock_db, sample_anomalies):
        """Test get_anomalies filters unacknowledged anomalies."""
        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        unacknowledged = [a for a in sample_anomalies if not a.is_acknowledged]
        mock_query.all.return_value = unacknowledged
        mock_db.query.return_value = mock_query

        # Execute
        result = cost_service.get_anomalies(acknowledged=False)

        # Verify
        assert isinstance(result, list)
        mock_query.filter.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_anomalies_by_service_with_data(
        self, cost_service, mock_db, sample_anomalies
    ):
        """Test get_anomalies_by_service groups anomalies correctly."""
        # Setup mock query
        mock_query = MagicMock()
        mock_query.all.return_value = sample_anomalies
        mock_db.query.return_value = mock_query

        # Execute
        result = await cost_service.get_anomalies_by_service(limit=10)

        # Verify
        assert isinstance(result, list)
        assert all(isinstance(item, AnomaliesByService) for item in result)
        # Should be sorted by total_impact descending
        if len(result) > 1:
            for i in range(len(result) - 1):
                assert result[i].total_impact >= result[i + 1].total_impact

    @pytest.mark.asyncio
    async def test_get_anomalies_by_service_empty(self):
        """Test get_anomalies_by_service with no anomalies."""
        # Create fresh mocks
        mock_db = MagicMock()
        service = CostService(db=mock_db)

        # Setup mock query
        mock_query = MagicMock()
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query

        # Execute
        result = await service.get_anomalies_by_service(limit=10)

        # Verify
        assert isinstance(result, list)
        assert len(result) == 0

    def test_get_top_anomalies_with_data(
        self, cost_service, mock_db, sample_anomalies, sample_tenants
    ):
        """Test get_top_anomalies returns top N by impact."""

        # Setup mock queries
        def mock_query_side_effect(model):
            mock_q = MagicMock()
            if model == CostAnomaly:
                mock_q.filter.return_value = mock_q
                mock_q.order_by.return_value = mock_q
                mock_q.limit.return_value = mock_q
                mock_q.all.return_value = sample_anomalies
            elif model == Tenant:
                mock_q.all.return_value = sample_tenants
            return mock_q

        mock_db.query.side_effect = mock_query_side_effect

        # Execute
        result = cost_service.get_top_anomalies(n=3)

        # Verify
        assert isinstance(result, list)
        assert len(result) <= 3
        assert all(isinstance(item, TopAnomaly) for item in result)
        # Verify sorted by impact_score descending
        if len(result) > 1:
            for i in range(len(result) - 1):
                assert result[i].impact_score >= result[i + 1].impact_score

    def test_get_top_anomalies_empty(self, cost_service, mock_db, sample_tenants):
        """Test get_top_anomalies with no anomalies."""

        # Setup mock queries
        def mock_query_side_effect(model):
            mock_q = MagicMock()
            if model == CostAnomaly:
                mock_q.filter.return_value = mock_q
                mock_q.order_by.return_value = mock_q
                mock_q.limit.return_value = mock_q
                mock_q.all.return_value = []
            elif model == Tenant:
                mock_q.all.return_value = sample_tenants
            return mock_q

        mock_db.query.side_effect = mock_query_side_effect

        # Execute
        result = cost_service.get_top_anomalies(n=10)

        # Verify
        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_acknowledge_anomaly_success(self, cost_service, mock_db, sample_anomalies):
        """Test acknowledge_anomaly updates anomaly successfully."""
        anomaly = sample_anomalies[0]
        anomaly.is_acknowledged = False

        # Setup mock query
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = anomaly
        mock_db.query.return_value = mock_query

        # Mock the cache invalidation to avoid async issues
        with patch("app.core.cache.invalidate_on_sync_completion", new_callable=AsyncMock):
            # Execute
            result = await cost_service.acknowledge_anomaly(anomaly_id=1, user="admin@test.com")

            # Verify core functionality
            assert result is True
            assert anomaly.is_acknowledged is True
            assert anomaly.acknowledged_by == "admin@test.com"
            assert anomaly.acknowledged_at is not None
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_acknowledge_anomaly_not_found(self, cost_service, mock_db):
        """Test acknowledge_anomaly returns False for non-existent anomaly."""
        # Setup mock query to return None
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        mock_db.query.return_value = mock_query

        # Execute
        result = await cost_service.acknowledge_anomaly(anomaly_id=999, user="admin@test.com")

        # Verify
        assert result is False
        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_bulk_acknowledge_all_success(self, cost_service, mock_db, sample_anomalies):
        """Test bulk_acknowledge_anomalies with all successful."""
        # Setup
        anomaly_ids = [1, 2, 3]

        # Mock acknowledge_anomaly to succeed
        with patch.object(cost_service, "acknowledge_anomaly", new_callable=AsyncMock) as mock_ack:
            mock_ack.return_value = True

            # Execute
            result = await cost_service.bulk_acknowledge_anomalies(
                anomaly_ids=anomaly_ids, user="admin@test.com"
            )

            # Verify
            assert isinstance(result, BulkAcknowledgeResponse)
            assert result.success is True
            assert result.acknowledged_count == 3
            assert len(result.failed_ids) == 0
            assert mock_ack.call_count == 3

    @pytest.mark.asyncio
    async def test_bulk_acknowledge_partial_failure(self, cost_service, mock_db):
        """Test bulk_acknowledge_anomalies with some failures."""
        # Setup
        anomaly_ids = [1, 2, 3]

        # Mock acknowledge_anomaly to fail for id 2
        async def mock_acknowledge(anomaly_id, user):
            return anomaly_id != 2

        with patch.object(cost_service, "acknowledge_anomaly", side_effect=mock_acknowledge):
            # Execute
            result = await cost_service.bulk_acknowledge_anomalies(
                anomaly_ids=anomaly_ids, user="admin@test.com"
            )

            # Verify
            assert isinstance(result, BulkAcknowledgeResponse)
            assert result.success is False
            assert result.acknowledged_count == 2
            assert result.failed_ids == [2]

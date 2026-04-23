"""Tests for cost synchronization module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.sync.costs import sync_costs

# Shared patch target for the REST helper
_QUERY_COSTS_REST = "app.core.sync.costs._query_costs_rest"


class TestCostSync:
    """Test suite for cost synchronization."""

    @pytest.mark.asyncio
    async def test_sync_costs_success(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        mock_subscription,
    ):
        """Test successful cost synchronization."""
        mock_azure_client_manager["costs"].list_subscriptions.return_value = [mock_subscription]

        with patch(_QUERY_COSTS_REST, new_callable=AsyncMock) as mock_query:
            mock_query.return_value = [
                [10.50, 20240115, "USD", "rg-test", "Storage"],
                [25.00, 20240115, "USD", "rg-test", "Compute"],
            ]

            await sync_costs()

            mock_query.assert_called_once()
            mock_db_session.add.assert_called()
            mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_sync_costs_empty_data(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        mock_subscription,
    ):
        """Test cost sync with empty data."""
        mock_azure_client_manager["costs"].list_subscriptions.return_value = [mock_subscription]

        with patch(_QUERY_COSTS_REST, new_callable=AsyncMock) as mock_query:
            mock_query.return_value = []
            await sync_costs()
            mock_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_costs_no_subscriptions(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
    ):
        """Test cost sync with no subscriptions."""
        mock_azure_client_manager["costs"].list_subscriptions.return_value = []

        with patch(_QUERY_COSTS_REST, new_callable=AsyncMock) as mock_query:
            await sync_costs()
            mock_query.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_costs_disabled_subscription(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        mock_disabled_subscription,
    ):
        """Test cost sync skips disabled subscriptions."""
        mock_azure_client_manager["costs"].list_subscriptions.return_value = [
            mock_disabled_subscription
        ]

        with patch(_QUERY_COSTS_REST, new_callable=AsyncMock) as mock_query:
            await sync_costs()
            mock_query.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_costs_http_error(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        mock_subscription,
    ):
        """Test cost sync handles HTTP errors gracefully."""
        mock_azure_client_manager["costs"].list_subscriptions.return_value = [mock_subscription]

        with patch(_QUERY_COSTS_REST, new_callable=AsyncMock) as mock_query:
            mock_query.side_effect = Exception("HTTP 403")
            await sync_costs()
            mock_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_costs_auth_error(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        mock_subscription,
    ):
        """Test cost sync handles authentication errors."""
        mock_azure_client_manager["costs"].list_subscriptions.return_value = [mock_subscription]

        with patch(_QUERY_COSTS_REST, new_callable=AsyncMock) as mock_query:
            mock_query.side_effect = Exception("Auth failed")
            await sync_costs()
            mock_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_costs_db_error(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        mock_subscription,
    ):
        """Test cost sync handles database errors."""
        mock_azure_client_manager["costs"].list_subscriptions.return_value = [mock_subscription]

        with patch(_QUERY_COSTS_REST, new_callable=AsyncMock) as mock_query:
            mock_query.return_value = [[10.50, 20240115, "USD", "rg-test", "Storage"]]
            mock_db_session.commit.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(SQLAlchemyError):
                await sync_costs()

    @pytest.mark.asyncio
    async def test_sync_costs_zero_cost_skipped(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        mock_subscription,
    ):
        """Test that zero cost entries are skipped."""
        mock_azure_client_manager["costs"].list_subscriptions.return_value = [mock_subscription]

        with patch(_QUERY_COSTS_REST, new_callable=AsyncMock) as mock_query:
            mock_query.return_value = [
                [10.50, 20240115, "USD", "rg-test", "Storage"],
                [0.0, 20240115, "USD", "rg-test", "Network"],  # Skipped
                [0.00, 20240115, "USD", "rg-test", "DNS"],  # Skipped
            ]
            await sync_costs()

            # 1 SyncJobLog + 1 cost record (two zero-cost rows skipped)
            assert mock_db_session.add.call_count == 2

    @pytest.mark.asyncio
    async def test_sync_costs_malformed_row(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        mock_subscription,
    ):
        """Test handling of malformed cost rows."""
        mock_azure_client_manager["costs"].list_subscriptions.return_value = [mock_subscription]

        with patch(_QUERY_COSTS_REST, new_callable=AsyncMock) as mock_query:
            mock_query.return_value = [
                [10.50, 20240115, "USD", "rg-test", "Storage"],
                [],  # Malformed
                [25.00, 20240115],  # Missing columns
            ]
            await sync_costs()
            assert mock_db_session.add.call_count >= 1

    @pytest.mark.asyncio
    async def test_sync_costs_skips_ineligible_tenants(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
    ):
        """Test scheduled cost sync skips tenants that are not auth-configured."""
        from app.models.monitoring import SyncJobLog

        bad_tenant = MagicMock()
        bad_tenant.id = "tenant-bad-uuid"
        bad_tenant.tenant_id = "bad-tenant-id"
        bad_tenant.name = "Bad Tenant"
        bad_tenant.is_active = True

        tenant_query = MagicMock()
        tenant_query.filter.return_value = tenant_query
        tenant_query.all.return_value = [mock_tenant, bad_tenant]

        ghost_query = MagicMock()
        ghost_query.filter.return_value.all.return_value = []
        ghost_query.filter.return_value.first.return_value = None

        mock_db_session.query.side_effect = lambda model: (
            ghost_query if model is SyncJobLog else tenant_query
        )
        mock_azure_client_manager["costs"].list_subscriptions.return_value = []

        with patch("app.core.sync.costs.get_sync_eligible_tenants", return_value=[mock_tenant]):
            await sync_costs()

        mock_azure_client_manager["costs"].list_subscriptions.assert_called_once_with(
            mock_tenant.tenant_id
        )

    async def test_sync_costs_multiple_tenants(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        mock_subscription,
    ):
        """Test syncing costs from multiple tenants."""
        tenant2 = MagicMock()
        tenant2.id = "tenant-2-uuid"
        tenant2.tenant_id = "test-tenant-id-456"
        tenant2.name = "Test Tenant 2"
        tenant2.is_active = True
        tenant2.use_lighthouse = True
        tenant2.client_id = "tenant-2-client-id"
        tenant2.client_secret_ref = "tenant-2-client-secret-ref"  # pragma: allowlist secret

        # The fixture sets query.side_effect (routing by model type), which
        # takes precedence over return_value. Override the side_effect so
        # Tenant queries return both tenants while SyncJobLog stays isolated.
        from app.models.monitoring import SyncJobLog

        multi_tenant_query = MagicMock()
        multi_tenant_query.filter.return_value = multi_tenant_query
        multi_tenant_query.all.return_value = [mock_tenant, tenant2]

        ghost_query = MagicMock()
        ghost_query.filter.return_value.all.return_value = []
        ghost_query.filter.return_value.first.return_value = None

        mock_db_session.query.side_effect = lambda model: (
            ghost_query if model is SyncJobLog else multi_tenant_query
        )

        mock_azure_client_manager["costs"].list_subscriptions.return_value = [mock_subscription]

        with patch(_QUERY_COSTS_REST, new_callable=AsyncMock) as mock_query:
            mock_query.return_value = [[10.50, 20240115, "USD", "rg-test", "Storage"]]
            await sync_costs()
            assert mock_azure_client_manager["costs"].list_subscriptions.call_count == 2

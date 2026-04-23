"""Tests for resource synchronization module."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.sync.resources import sync_resources


class TestResourceSync:
    """Test suite for resource synchronization."""

    @pytest.mark.asyncio
    async def test_sync_resources_success(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        mock_subscription,
        sample_resources,
    ):
        """Test successful resource synchronization."""
        # Setup
        mock_azure_client_manager["resources"].list_subscriptions.return_value = [mock_subscription]

        mock_resource_client = MagicMock()
        mock_resource_client.resources = MagicMock()
        mock_resource_client.resources.list.return_value = sample_resources
        mock_azure_client_manager[
            "resources"
        ].get_resource_client.return_value = mock_resource_client

        # Execute
        await sync_resources()

        # Verify
        mock_azure_client_manager["resources"].list_subscriptions.assert_called_once()
        mock_resource_client.resources.list.assert_called_once()
        mock_db_session.add.assert_called()
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_sync_resources_empty_data(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        mock_subscription,
    ):
        """Test resource sync with empty data."""
        # Setup
        mock_azure_client_manager["resources"].list_subscriptions.return_value = [mock_subscription]

        mock_resource_client = MagicMock()
        mock_resource_client.resources = MagicMock()
        mock_resource_client.resources.list.return_value = []
        mock_azure_client_manager[
            "resources"
        ].get_resource_client.return_value = mock_resource_client

        # Execute
        await sync_resources()

        # Verify - should complete without errors
        # commit is called twice: once for SyncJobLog and once at end of sync
        assert mock_db_session.commit.call_count == 2

    @pytest.mark.asyncio
    async def test_sync_resources_no_subscriptions(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
    ):
        """Test resource sync with no subscriptions."""
        # Setup
        mock_azure_client_manager["resources"].list_subscriptions.return_value = []

        # Execute
        await sync_resources()

        # Verify
        mock_azure_client_manager["resources"].get_resource_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_resources_disabled_subscription(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        mock_disabled_subscription,
    ):
        """Test resource sync skips disabled subscriptions."""
        # Setup
        mock_azure_client_manager["resources"].list_subscriptions.return_value = [
            mock_disabled_subscription
        ]

        # Execute
        await sync_resources()

        # Verify
        mock_azure_client_manager["resources"].get_resource_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_resources_http_error(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        mock_subscription,
    ):
        """Test resource sync handles HTTP errors."""
        # Setup
        mock_azure_client_manager["resources"].list_subscriptions.return_value = [mock_subscription]

        mock_resource_client = MagicMock()
        mock_resource_client.resources = MagicMock()
        mock_resource_client.resources.list.side_effect = Exception("HTTP 403")
        mock_azure_client_manager[
            "resources"
        ].get_resource_client.return_value = mock_resource_client

        # Execute - should not raise
        await sync_resources()

    @pytest.mark.asyncio
    async def test_sync_resources_auth_error(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        mock_subscription,
    ):
        """Test resource sync handles authentication errors."""
        # Setup
        mock_azure_client_manager["resources"].list_subscriptions.return_value = [mock_subscription]

        mock_resource_client = MagicMock()
        mock_resource_client.resources = MagicMock()
        mock_resource_client.resources.list.side_effect = Exception("Auth failed")
        mock_azure_client_manager[
            "resources"
        ].get_resource_client.return_value = mock_resource_client

        # Execute - should not raise
        await sync_resources()

    @pytest.mark.asyncio
    async def test_sync_resources_db_error(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        mock_subscription,
        sample_resources,
    ):
        """Test resource sync handles database errors."""
        # Setup
        mock_azure_client_manager["resources"].list_subscriptions.return_value = [mock_subscription]

        mock_resource_client = MagicMock()
        mock_resource_client.resources = MagicMock()
        mock_resource_client.resources.list.return_value = sample_resources
        mock_azure_client_manager[
            "resources"
        ].get_resource_client.return_value = mock_resource_client

        mock_db_session.commit.side_effect = SQLAlchemyError("Database error")

        # Execute - should raise after retries are exhausted
        with pytest.raises(SQLAlchemyError):
            await sync_resources()

    @pytest.mark.asyncio
    async def test_sync_resources_orphaned_detection(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        mock_subscription,
    ):
        """Test detection of orphaned resources."""
        # Setup - create resources with different states
        failed_resource = MagicMock()
        failed_resource.id = "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/failedvm"
        failed_resource.name = "failedvm"
        failed_resource.location = "eastus"
        failed_resource.type = "Microsoft.Compute/virtualMachines"
        failed_resource.provisioning_state = "Failed"
        failed_resource.tags = None
        failed_resource.sku = None

        orphaned_resource = MagicMock()
        orphaned_resource.id = "/subscriptions/sub-123/resourceGroups/rg-test/providers/Microsoft.Storage/storageAccounts/orphaned"
        orphaned_resource.name = "orphaned"
        orphaned_resource.location = "westus"
        orphaned_resource.type = "Microsoft.Storage/storageAccounts"
        orphaned_resource.provisioning_state = "Succeeded"
        orphaned_resource.tags = {"orphan": "true"}
        orphaned_resource.sku = None

        mock_azure_client_manager["resources"].list_subscriptions.return_value = [mock_subscription]

        mock_resource_client = MagicMock()
        mock_resource_client.resources = MagicMock()
        mock_resource_client.resources.list.return_value = [failed_resource, orphaned_resource]
        mock_azure_client_manager[
            "resources"
        ].get_resource_client.return_value = mock_resource_client

        # Execute
        await sync_resources()

        # Verify - should mark both as orphaned + 1 SyncJobLog entry
        add_calls = mock_db_session.add.call_args_list
        assert len(add_calls) == 3  # 2 resources + 1 SyncJobLog

    @pytest.mark.asyncio
    async def test_sync_resources_update_existing(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        mock_subscription,
        sample_resources,
    ):
        """Test updating existing resources."""
        # Setup - existing resource in database
        existing_resource = MagicMock()
        mock_db_query = MagicMock()
        mock_db_query.filter.return_value = mock_db_query
        mock_db_query.first.return_value = existing_resource
        mock_db_session.query.return_value = mock_db_query

        mock_azure_client_manager["resources"].list_subscriptions.return_value = [mock_subscription]

        mock_resource_client = MagicMock()
        mock_resource_client.resources = MagicMock()
        mock_resource_client.resources.list.return_value = sample_resources
        mock_azure_client_manager[
            "resources"
        ].get_resource_client.return_value = mock_resource_client

        # Execute
        await sync_resources()

        # Verify - should update existing resource instead of creating new
        # In this case, existing_resource should have been modified

    @pytest.mark.asyncio
    async def test_sync_resources_pagination(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        mock_subscription,
    ):
        """Test resource sync with pagination."""
        # Note: The SDK handles pagination, but we should test iterator behavior
        # Setup
        resource1 = MagicMock()
        resource1.id = "/subscriptions/sub-123/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/sa1"
        resource1.name = "sa1"
        resource1.location = "eastus"
        resource1.type = "Microsoft.Storage/storageAccounts"
        resource1.provisioning_state = "Succeeded"
        resource1.tags = None
        resource1.sku = None

        resource2 = MagicMock()
        resource2.id = "/subscriptions/sub-123/resourceGroups/rg2/providers/Microsoft.Compute/virtualMachines/vm2"
        resource2.name = "vm2"
        resource2.location = "westus"
        resource2.type = "Microsoft.Compute/virtualMachines"
        resource2.provisioning_state = "Succeeded"
        resource2.tags = None
        resource2.sku = None

        mock_azure_client_manager["resources"].list_subscriptions.return_value = [mock_subscription]

        mock_resource_client = MagicMock()
        mock_resource_client.resources = MagicMock()
        mock_resource_client.resources.list.return_value = [resource1, resource2]
        mock_azure_client_manager[
            "resources"
        ].get_resource_client.return_value = mock_resource_client

        # Execute
        await sync_resources()

        # Verify - should process both resources + 1 SyncJobLog entry
        assert mock_db_session.add.call_count == 3

    @pytest.mark.asyncio
    async def test_sync_resources_malformed_id(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        mock_subscription,
    ):
        """Test handling resources with malformed IDs."""
        # Setup - resource with malformed ID
        malformed_resource = MagicMock()
        malformed_resource.id = "invalid-id-format"
        malformed_resource.name = "bad-resource"
        malformed_resource.location = "eastus"
        malformed_resource.type = "Microsoft.Storage/storageAccounts"
        malformed_resource.provisioning_state = "Succeeded"
        malformed_resource.tags = None
        malformed_resource.sku = None

        valid_resource = MagicMock()
        valid_resource.id = "/subscriptions/sub-123/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/valid"
        valid_resource.name = "valid"
        valid_resource.location = "eastus"
        valid_resource.type = "Microsoft.Storage/storageAccounts"
        valid_resource.provisioning_state = "Succeeded"
        valid_resource.tags = None
        valid_resource.sku = None

        mock_azure_client_manager["resources"].list_subscriptions.return_value = [mock_subscription]

        mock_resource_client = MagicMock()
        mock_resource_client.resources = MagicMock()
        mock_resource_client.resources.list.return_value = [malformed_resource, valid_resource]
        mock_azure_client_manager[
            "resources"
        ].get_resource_client.return_value = mock_resource_client

        # Execute - should not raise
        await sync_resources()

        # Verify - should process valid resource
        mock_db_session.add.assert_called()

    @pytest.mark.asyncio
    async def test_sync_resources_extract_cost_from_tags(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        mock_subscription,
    ):
        """Test extracting estimated cost from tags."""
        # Setup - resource with cost in tags
        cost_resource = MagicMock()
        cost_resource.id = "/subscriptions/sub-123/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/costly"
        cost_resource.name = "costly"
        cost_resource.location = "eastus"
        cost_resource.type = "Microsoft.Storage/storageAccounts"
        cost_resource.provisioning_state = "Succeeded"
        cost_resource.tags = {"costMonthly": "$100.50", "environment": "prod"}
        cost_resource.sku = None

        mock_azure_client_manager["resources"].list_subscriptions.return_value = [mock_subscription]

        mock_resource_client = MagicMock()
        mock_resource_client.resources = MagicMock()
        mock_resource_client.resources.list.return_value = [cost_resource]
        mock_azure_client_manager[
            "resources"
        ].get_resource_client.return_value = mock_resource_client

        # Execute
        await sync_resources()

        # Verify - should have processed the resource + SyncJobLog
        assert mock_db_session.add.call_count == 2

    @pytest.mark.asyncio
    async def test_sync_resources_multiple_tenants(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        mock_subscription,
        sample_resources,
    ):
        """Test syncing resources from multiple tenants."""
        # Create second tenant
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

        mock_azure_client_manager["resources"].list_subscriptions.return_value = [mock_subscription]

        mock_resource_client = MagicMock()
        mock_resource_client.resources = MagicMock()
        mock_resource_client.resources.list.return_value = sample_resources
        mock_azure_client_manager[
            "resources"
        ].get_resource_client.return_value = mock_resource_client

        # Execute
        await sync_resources()

        # Verify - called for each tenant
        assert mock_azure_client_manager["resources"].list_subscriptions.call_count == 2

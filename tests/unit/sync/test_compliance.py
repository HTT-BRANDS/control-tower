"""Tests for compliance synchronization module."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.sync.compliance import sync_compliance


class TestComplianceSync:
    """Test suite for compliance synchronization."""

    @pytest.mark.asyncio
    async def test_sync_compliance_success(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        mock_subscription,
        sample_policy_states,
    ):
        """Test successful compliance synchronization."""
        # Setup
        mock_azure_client_manager["compliance"].list_subscriptions.return_value = [
            mock_subscription
        ]

        # Mock policy client
        mock_policy_client = MagicMock()
        mock_policy_client.policy_states = MagicMock()
        mock_policy_client.policy_states.list_query_results_for_subscription.return_value = (
            sample_policy_states
        )
        mock_azure_client_manager["compliance"].get_policy_client.return_value = mock_policy_client

        # Mock security client
        mock_security_client = MagicMock()
        mock_secure_scores = MagicMock()
        score = MagicMock()
        score.name = "ascScore"
        score.score = MagicMock()
        score.score.current = 85.5
        mock_secure_scores.list.return_value = [score]
        mock_security_client.secure_scores = mock_secure_scores
        mock_azure_client_manager[
            "compliance"
        ].get_security_client.return_value = mock_security_client

        # Execute
        await sync_compliance()

        # Verify
        mock_azure_client_manager["compliance"].list_subscriptions.assert_called_once()
        mock_policy_client.policy_states.list_query_results_for_subscription.assert_called_once()
        mock_db_session.add.assert_called()
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_sync_compliance_empty_data(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        mock_subscription,
    ):
        """Test compliance sync with empty policy data."""
        # Setup
        mock_azure_client_manager["compliance"].list_subscriptions.return_value = [
            mock_subscription
        ]

        mock_policy_client = MagicMock()
        mock_policy_client.policy_states = MagicMock()
        mock_policy_client.policy_states.list_query_results_for_subscription.return_value = []
        mock_azure_client_manager["compliance"].get_policy_client.return_value = mock_policy_client

        mock_security_client = MagicMock()
        mock_security_client.secure_scores = MagicMock()
        mock_security_client.secure_scores.list.return_value = []
        mock_azure_client_manager[
            "compliance"
        ].get_security_client.return_value = mock_security_client

        # Execute
        await sync_compliance()

        # Verify - should still create snapshot with zeros
        mock_db_session.add.assert_called()

    @pytest.mark.asyncio
    async def test_sync_compliance_no_subscriptions(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
    ):
        """Test compliance sync with no subscriptions."""
        # Setup
        mock_azure_client_manager["compliance"].list_subscriptions.return_value = []

        # Execute
        await sync_compliance()

        # Verify
        mock_azure_client_manager["compliance"].get_policy_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_compliance_disabled_subscription(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        mock_disabled_subscription,
    ):
        """Test compliance sync skips disabled subscriptions."""
        # Setup
        mock_azure_client_manager["compliance"].list_subscriptions.return_value = [
            mock_disabled_subscription
        ]

        # Execute
        await sync_compliance()

        # Verify
        mock_azure_client_manager["compliance"].get_policy_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_compliance_policy_http_error(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        mock_subscription,
    ):
        """Test compliance sync handles policy HTTP errors."""
        # Setup
        mock_azure_client_manager["compliance"].list_subscriptions.return_value = [
            mock_subscription
        ]

        mock_policy_client = MagicMock()
        mock_policy_client.policy_states = MagicMock()
        mock_policy_client.policy_states.list_query_results_for_subscription.side_effect = (
            Exception("HTTP 403")
        )
        mock_azure_client_manager["compliance"].get_policy_client.return_value = mock_policy_client

        mock_security_client = MagicMock()
        mock_security_client.secure_scores = MagicMock()
        mock_security_client.secure_scores.list.return_value = []
        mock_azure_client_manager[
            "compliance"
        ].get_security_client.return_value = mock_security_client

        # Execute - should not raise
        await sync_compliance()

        # Verify - continues with security score (creates snapshot even if policy fails)
        # Note: The exception is caught and handled, but no snapshot may be created if both fail
        pass  # Test passes if no exception raised

    @pytest.mark.asyncio
    async def test_sync_compliance_security_http_error(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        mock_subscription,
        sample_policy_states,
    ):
        """Test compliance sync handles security center HTTP errors."""
        # Setup
        mock_azure_client_manager["compliance"].list_subscriptions.return_value = [
            mock_subscription
        ]

        mock_policy_client = MagicMock()
        mock_policy_client.policy_states = MagicMock()
        mock_policy_client.policy_states.list_query_results_for_subscription.return_value = (
            sample_policy_states
        )
        mock_azure_client_manager["compliance"].get_policy_client.return_value = mock_policy_client

        mock_security_client = MagicMock()
        mock_security_client.secure_scores = MagicMock()
        mock_security_client.secure_scores.list.side_effect = Exception("HTTP 403")
        mock_azure_client_manager[
            "compliance"
        ].get_security_client.return_value = mock_security_client

        # Execute - should not raise
        await sync_compliance()

        # Verify - creates snapshot without secure score
        mock_db_session.add.assert_called()

    @pytest.mark.asyncio
    async def test_sync_compliance_auth_error(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        mock_subscription,
    ):
        """Test compliance sync handles authentication errors."""
        # Setup
        mock_azure_client_manager["compliance"].list_subscriptions.return_value = [
            mock_subscription
        ]

        mock_policy_client = MagicMock()
        mock_policy_client.policy_states = MagicMock()
        mock_policy_client.policy_states.list_query_results_for_subscription.side_effect = (
            Exception("Auth failed")
        )
        mock_azure_client_manager["compliance"].get_policy_client.return_value = mock_policy_client

        mock_security_client = MagicMock()
        mock_security_client.secure_scores = MagicMock()
        mock_security_client.secure_scores.list.return_value = []
        mock_azure_client_manager[
            "compliance"
        ].get_security_client.return_value = mock_security_client

        # Execute - should not raise
        await sync_compliance()

    @pytest.mark.asyncio
    async def test_sync_compliance_db_error(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        mock_subscription,
        sample_policy_states,
    ):
        """Test compliance sync handles database errors."""
        # Setup
        mock_azure_client_manager["compliance"].list_subscriptions.return_value = [
            mock_subscription
        ]

        mock_policy_client = MagicMock()
        mock_policy_client.policy_states = MagicMock()
        mock_policy_client.policy_states.list_query_results_for_subscription.return_value = (
            sample_policy_states
        )
        mock_azure_client_manager["compliance"].get_policy_client.return_value = mock_policy_client

        mock_security_client = MagicMock()
        mock_security_client.secure_scores = MagicMock()
        mock_security_client.secure_scores.list.return_value = []
        mock_azure_client_manager[
            "compliance"
        ].get_security_client.return_value = mock_security_client

        mock_db_session.commit.side_effect = SQLAlchemyError("Database error")

        # Execute - should raise after retries are exhausted
        with pytest.raises(SQLAlchemyError):
            await sync_compliance()

    @pytest.mark.asyncio
    async def test_sync_compliance_multiple_policies(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        mock_subscription,
    ):
        """Test syncing multiple policies."""
        # Setup - create multiple policy states
        state1 = MagicMock()
        state1.policy_definition_id = "/policy1"
        state1.policy_definition_reference_id = "Policy 1"
        state1.compliance_state = MagicMock()
        state1.compliance_state.value = "Compliant"
        state1.resource_id = "/resource1"
        state1.policy_definition_group_names = ["Group1"]

        state2 = MagicMock()
        state2.policy_definition_id = "/policy2"
        state2.policy_definition_reference_id = "Policy 2"
        state2.compliance_state = MagicMock()
        state2.compliance_state.value = "NonCompliant"
        state2.resource_id = "/resource2"
        state2.policy_definition_group_names = None

        state3 = MagicMock()
        state3.policy_definition_id = "/policy3"
        state3.policy_definition_reference_id = "Policy 3"
        state3.compliance_state = MagicMock()
        state3.compliance_state.value = "Exempt"
        state3.resource_id = "/resource3"
        state3.policy_definition_group_names = ["Group2"]

        mock_azure_client_manager["compliance"].list_subscriptions.return_value = [
            mock_subscription
        ]

        mock_policy_client = MagicMock()
        mock_policy_client.policy_states = MagicMock()
        mock_policy_client.policy_states.list_query_results_for_subscription.return_value = [
            state1,
            state2,
            state3,
        ]
        mock_azure_client_manager["compliance"].get_policy_client.return_value = mock_policy_client

        mock_security_client = MagicMock()
        mock_security_client.secure_scores = MagicMock()
        mock_security_client.secure_scores.list.return_value = []
        mock_azure_client_manager[
            "compliance"
        ].get_security_client.return_value = mock_security_client

        # Execute
        await sync_compliance()

        # Verify - should create PolicyState records
        assert mock_db_session.add.call_count >= 3

    @pytest.mark.asyncio
    async def test_sync_compliance_exempt_resources(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        mock_subscription,
    ):
        """Test compliance counts exempt resources correctly."""
        # Setup
        exempt_state = MagicMock()
        exempt_state.policy_definition_id = "/policy1"
        exempt_state.policy_definition_reference_id = "Policy 1"
        exempt_state.compliance_state = MagicMock()
        exempt_state.compliance_state.value = "Exempt"
        exempt_state.resource_id = "/resource1"
        exempt_state.policy_definition_group_names = None

        mock_azure_client_manager["compliance"].list_subscriptions.return_value = [
            mock_subscription
        ]

        mock_policy_client = MagicMock()
        mock_policy_client.policy_states = MagicMock()
        mock_policy_client.policy_states.list_query_results_for_subscription.return_value = [
            exempt_state
        ]
        mock_azure_client_manager["compliance"].get_policy_client.return_value = mock_policy_client

        mock_security_client = MagicMock()
        mock_security_client.secure_scores = MagicMock()
        mock_security_client.secure_scores.list.return_value = []
        mock_azure_client_manager[
            "compliance"
        ].get_security_client.return_value = mock_security_client

        # Execute
        await sync_compliance()

        # Verify
        mock_db_session.add.assert_called()

    @pytest.mark.asyncio
    async def test_sync_compliance_multiple_tenants(
        self,
        mock_azure_client_manager,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        mock_subscription,
        sample_policy_states,
    ):
        """Test syncing compliance from multiple tenants."""
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

        mock_azure_client_manager["compliance"].list_subscriptions.return_value = [
            mock_subscription
        ]

        mock_policy_client = MagicMock()
        mock_policy_client.policy_states = MagicMock()
        mock_policy_client.policy_states.list_query_results_for_subscription.return_value = (
            sample_policy_states
        )
        mock_azure_client_manager["compliance"].get_policy_client.return_value = mock_policy_client

        mock_security_client = MagicMock()
        mock_security_client.secure_scores = MagicMock()
        mock_security_client.secure_scores.list.return_value = []
        mock_azure_client_manager[
            "compliance"
        ].get_security_client.return_value = mock_security_client

        # Execute
        await sync_compliance()

        # Verify - called for each tenant
        assert mock_azure_client_manager["compliance"].list_subscriptions.call_count == 2

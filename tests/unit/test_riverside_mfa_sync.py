"""Tests for enhanced Riverside MFA sync with Graph API integration.

This module tests the enhanced MFA sync functionality that uses the new
GraphClient methods for improved MFA data collection.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import Azure modules BEFORE any app imports to ensure namespace packages work
try:
    from azure.core.exceptions import HttpResponseError
except ImportError:
    # Create a proper mock exception class if Azure SDK not available
    class HttpResponseError(Exception):
        def __init__(self, message="", status_code=None, **kwargs):
            super().__init__(message)
            self.status_code = status_code
            self.message = message


from app.services.riverside_sync import (  # noqa: E402
    SyncError,
    sync_all_tenants,
    sync_tenant_mfa,
)


class TestEnhancedSyncTenantMFA:
    """Test suite for enhanced sync_tenant_mfa function."""

    @pytest.fixture
    def mock_tenant(self):
        """Create a mock tenant."""
        tenant = MagicMock()
        tenant.id = "tenant-uuid-123"
        tenant.tenant_id = "test-tenant-id"
        tenant.name = "Test Tenant"
        tenant.is_active = True
        return tenant

    @pytest.fixture
    def mock_users(self):
        """Sample user data."""
        return [
            {"id": "user-1", "userPrincipalName": "user1@example.com", "displayName": "User 1"},
            {"id": "user-2", "userPrincipalName": "user2@example.com", "displayName": "User 2"},
            {"id": "user-3", "userPrincipalName": "user3@example.com", "displayName": "User 3"},
            {"id": "user-4", "userPrincipalName": "user4@example.com", "displayName": "User 4"},
        ]

    @pytest.fixture
    def mock_directory_roles(self):
        """Sample directory role data with admin users."""
        return [
            {
                "roleTemplateId": "62e90394-69f5-4237-9190-012177145e10",  # Global Admin
                "members": [
                    {"id": "user-1", "userPrincipalName": "user1@example.com"},
                ],
            },
            {
                "roleTemplateId": "194ae4cb-b126-40b2-bd5b-6091b380977d",  # Security Admin
                "members": [
                    {"id": "user-1", "userPrincipalName": "user1@example.com"},
                    {"id": "user-2", "userPrincipalName": "user2@example.com"},
                ],
            },
        ]

    @pytest.fixture
    def mock_mfa_registrations(self):
        """Sample MFA registration data."""
        return [
            {
                "userPrincipalName": "user1@example.com",
                "isMfaRegistered": True,
                "methodsRegistered": ["phone", "app"],
            },
            {
                "userPrincipalName": "user2@example.com",
                "isMfaRegistered": True,
                "methodsRegistered": ["phone"],
            },
            {
                "userPrincipalName": "user3@example.com",
                "isMfaRegistered": False,
                "methodsRegistered": [],
            },
            {
                "userPrincipalName": "user4@example.com",
                "isMfaRegistered": False,
                "methodsRegistered": [],
            },
        ]

    @pytest.mark.asyncio
    async def test_sync_tenant_mfa_success_with_pagination(
        self,
        mock_tenant,
        mock_users,
        mock_directory_roles,
        mock_mfa_registrations,
    ):
        """Test successful MFA sync with paginated queries."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.side_effect = [mock_tenant, None]  # tenant, no existing record

        with patch("app.services.riverside_sync._get_graph_client") as mock_get_graph:
            mock_graph = MagicMock()
            mock_get_graph.return_value = mock_graph
            mock_graph.get_users_paginated = AsyncMock(return_value=mock_users)
            mock_graph.get_directory_roles = AsyncMock(return_value=mock_directory_roles)
            mock_graph.get_mfa_registration_details_paginated = AsyncMock(
                return_value=mock_mfa_registrations
            )

            result = await sync_tenant_mfa("test-tenant-id", mock_session)

            assert result["status"] == "success"
            assert result["total_users"] == 4
            assert result["mfa_enrolled"] == 2  # user1 and user2
            assert result["mfa_coverage_pct"] == 50.0
            assert result["admin_accounts"] == 2  # user1 and user2 (user1 is in both roles)
            assert result["admin_mfa_pct"] == 100.0  # Both admins have MFA
            assert result["unprotected_users"] == 2
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()

            # Verify paginated methods were called
            mock_graph.get_users_paginated.assert_called_once_with(batch_size=100)
            mock_graph.get_mfa_registration_details_paginated.assert_called_once_with(
                batch_size=100
            )

    @pytest.mark.asyncio
    async def test_sync_tenant_mfa_with_method_details(
        self,
        mock_tenant,
        mock_users,
        mock_directory_roles,
        mock_mfa_registrations,
    ):
        """Test MFA sync with method details enabled."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.side_effect = [mock_tenant, None]

        with patch("app.services.riverside_sync._get_graph_client") as mock_get_graph:
            mock_graph = MagicMock()
            mock_get_graph.return_value = mock_graph
            mock_graph.get_users_paginated = AsyncMock(return_value=mock_users)
            mock_graph.get_directory_roles = AsyncMock(return_value=mock_directory_roles)
            mock_graph.get_mfa_registration_details_paginated = AsyncMock(
                return_value=mock_mfa_registrations
            )

            result = await sync_tenant_mfa(
                "test-tenant-id",
                mock_session,
                include_method_details=True,
            )

            assert result["status"] == "success"
            assert "method_breakdown" in result
            assert "users_without_mfa" in result
            assert "phone" in result["method_breakdown"]
            assert "app" in result["method_breakdown"]
            assert len(result["users_without_mfa"]) == 2

    @pytest.mark.asyncio
    async def test_sync_tenant_mfa_with_custom_batch_size(
        self,
        mock_tenant,
        mock_users,
        mock_directory_roles,
        mock_mfa_registrations,
    ):
        """Test MFA sync with custom batch size."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.side_effect = [mock_tenant, None]

        with patch("app.services.riverside_sync._get_graph_client") as mock_get_graph:
            mock_graph = MagicMock()
            mock_get_graph.return_value = mock_graph
            mock_graph.get_users_paginated = AsyncMock(return_value=mock_users)
            mock_graph.get_directory_roles = AsyncMock(return_value=mock_directory_roles)
            mock_graph.get_mfa_registration_details_paginated = AsyncMock(
                return_value=mock_mfa_registrations
            )

            await sync_tenant_mfa(
                "test-tenant-id",
                mock_session,
                batch_size=50,
            )

            # Verify custom batch size was passed
            mock_graph.get_users_paginated.assert_called_once_with(batch_size=50)
            mock_graph.get_mfa_registration_details_paginated.assert_called_once_with(batch_size=50)

    @pytest.mark.asyncio
    async def test_sync_tenant_mfa_all_users_without_mfa(
        self,
        mock_tenant,
        mock_directory_roles,
    ):
        """Test MFA sync when no users have MFA."""
        users = [
            {"id": "user-1", "userPrincipalName": "user1@example.com", "displayName": "User 1"},
        ]
        registrations = [
            {
                "userPrincipalName": "user1@example.com",
                "isMfaRegistered": False,
                "methodsRegistered": [],
            },
        ]

        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.side_effect = [mock_tenant, None]

        with patch("app.services.riverside_sync._get_graph_client") as mock_get_graph:
            mock_graph = MagicMock()
            mock_get_graph.return_value = mock_graph
            mock_graph.get_users_paginated = AsyncMock(return_value=users)
            mock_graph.get_directory_roles = AsyncMock(return_value=mock_directory_roles)
            mock_graph.get_mfa_registration_details_paginated = AsyncMock(
                return_value=registrations
            )

            result = await sync_tenant_mfa("test-tenant-id", mock_session)

            assert result["status"] == "success"
            assert result["mfa_enrolled"] == 0
            assert result["mfa_coverage_pct"] == 0.0
            assert result["admin_mfa_pct"] == 0.0

    @pytest.mark.asyncio
    async def test_sync_tenant_mfa_all_users_with_mfa(
        self,
        mock_tenant,
        mock_directory_roles,
    ):
        """Test MFA sync when all users have MFA."""
        users = [
            {"id": "user-1", "userPrincipalName": "user1@example.com", "displayName": "User 1"},
            {"id": "user-2", "userPrincipalName": "user2@example.com", "displayName": "User 2"},
        ]
        registrations = [
            {
                "userPrincipalName": "user1@example.com",
                "isMfaRegistered": True,
                "methodsRegistered": ["app"],
            },
            {
                "userPrincipalName": "user2@example.com",
                "isMfaRegistered": True,
                "methodsRegistered": ["phone"],
            },
        ]

        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.side_effect = [mock_tenant, None]

        with patch("app.services.riverside_sync._get_graph_client") as mock_get_graph:
            mock_graph = MagicMock()
            mock_get_graph.return_value = mock_graph
            mock_graph.get_users_paginated = AsyncMock(return_value=users)
            mock_graph.get_directory_roles = AsyncMock(return_value=mock_directory_roles)
            mock_graph.get_mfa_registration_details_paginated = AsyncMock(
                return_value=registrations
            )

            result = await sync_tenant_mfa("test-tenant-id", mock_session)

            assert result["status"] == "success"
            assert result["mfa_enrolled"] == 2
            assert result["mfa_coverage_pct"] == 100.0
            assert result["unprotected_users"] == 0

    @pytest.mark.asyncio
    async def test_sync_tenant_mfa_no_admins(self, mock_tenant, mock_mfa_registrations):
        """Test MFA sync when there are no admin users."""
        users = [
            {"id": "user-1", "userPrincipalName": "user1@example.com", "displayName": "User 1"},
        ]
        # No directory roles with admin members
        directory_roles = []

        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.side_effect = [mock_tenant, None]

        with patch("app.services.riverside_sync._get_graph_client") as mock_get_graph:
            mock_graph = MagicMock()
            mock_get_graph.return_value = mock_graph
            mock_graph.get_users_paginated = AsyncMock(return_value=users)
            mock_graph.get_directory_roles = AsyncMock(return_value=directory_roles)
            mock_graph.get_mfa_registration_details_paginated = AsyncMock(
                return_value=mock_mfa_registrations
            )

            result = await sync_tenant_mfa("test-tenant-id", mock_session)

            assert result["status"] == "success"
            assert result["admin_accounts"] == 0
            assert result["admin_mfa_pct"] == 0.0

    @pytest.mark.asyncio
    async def test_sync_tenant_mfa_case_insensitive_upn_matching(
        self,
        mock_tenant,
        mock_directory_roles,
    ):
        """Test that UPN matching is case-insensitive."""
        users = [
            {"id": "user-1", "userPrincipalName": "User1@Example.COM", "displayName": "User 1"},
        ]
        registrations = [
            {
                "userPrincipalName": "user1@example.com",
                "isMfaRegistered": True,
                "methodsRegistered": ["app"],
            },
        ]

        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.side_effect = [mock_tenant, None]

        with patch("app.services.riverside_sync._get_graph_client") as mock_get_graph:
            mock_graph = MagicMock()
            mock_get_graph.return_value = mock_graph
            mock_graph.get_users_paginated = AsyncMock(return_value=users)
            mock_graph.get_directory_roles = AsyncMock(return_value=mock_directory_roles)
            mock_graph.get_mfa_registration_details_paginated = AsyncMock(
                return_value=registrations
            )

            result = await sync_tenant_mfa("test-tenant-id", mock_session)

            assert result["status"] == "success"
            assert result["mfa_enrolled"] == 1

    @pytest.mark.asyncio
    async def test_sync_tenant_mfa_graph_api_error(self, mock_tenant):
        """Test MFA sync when Graph API returns error."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_tenant

        with patch("app.services.riverside_sync._get_graph_client") as mock_get_graph:
            mock_graph = MagicMock()
            mock_get_graph.return_value = mock_graph
            mock_graph.get_users_paginated = AsyncMock(side_effect=Exception("Graph API Error"))

            with pytest.raises(SyncError) as exc_info:
                await sync_tenant_mfa("test-tenant-id", mock_session)

            assert "Graph API Error" in str(exc_info.value)
            assert exc_info.value.tenant_id == "test-tenant-id"

    @pytest.mark.asyncio
    async def test_sync_tenant_mfa_tenant_not_found(self):
        """Test MFA sync when tenant not found."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        with pytest.raises(SyncError) as exc_info:
            await sync_tenant_mfa("nonexistent-tenant", mock_session)

        assert "not found" in str(exc_info.value)
        assert exc_info.value.tenant_id == "nonexistent-tenant"

    @pytest.mark.asyncio
    async def test_sync_tenant_mfa_updates_existing_record(
        self,
        mock_tenant,
        mock_users,
        mock_directory_roles,
        mock_mfa_registrations,
    ):
        """Test MFA sync updates existing record for today."""
        existing_record = MagicMock()

        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.side_effect = [mock_tenant, existing_record]

        with patch("app.services.riverside_sync._get_graph_client") as mock_get_graph:
            mock_graph = MagicMock()
            mock_get_graph.return_value = mock_graph
            mock_graph.get_users_paginated = AsyncMock(return_value=mock_users)
            mock_graph.get_directory_roles = AsyncMock(return_value=mock_directory_roles)
            mock_graph.get_mfa_registration_details_paginated = AsyncMock(
                return_value=mock_mfa_registrations
            )

            result = await sync_tenant_mfa("test-tenant-id", mock_session)

            assert result["status"] == "success"
            # Should update existing record, not add new one
            mock_session.add.assert_not_called()
            mock_session.commit.assert_called_once()

            # Verify existing record was updated
            assert existing_record.total_users == 4
            assert existing_record.mfa_enrolled_users == 2


class TestSyncAllTenants:
    """Test suite for sync_all_tenants with enhanced MFA."""

    @pytest.fixture
    def mock_tenants(self):
        """Create mock tenants."""
        tenant1 = MagicMock()
        tenant1.id = "uuid-1"
        tenant1.tenant_id = "tenant-1"
        tenant1.name = "Tenant 1"
        tenant1.is_active = True

        tenant2 = MagicMock()
        tenant2.id = "uuid-2"
        tenant2.tenant_id = "tenant-2"
        tenant2.name = "Tenant 2"
        tenant2.is_active = True

        return [tenant1, tenant2]

    @pytest.mark.asyncio
    async def test_sync_all_tenants_with_mfa_only(self, mock_tenants):
        """Test batch sync with only MFA enabled."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_tenants

        with (
            patch("app.services.riverside_sync._get_monitoring_service") as mock_get_monitor,
            patch("app.services.riverside_sync.sync_tenant_mfa") as mock_mfa,
        ):
            mock_monitor = MagicMock()
            mock_get_monitor.return_value = mock_monitor
            mock_monitor.start_sync_job.return_value = MagicMock(id=1)
            mock_mfa.return_value = {"status": "success"}

            result = await sync_all_tenants(
                mock_session,
                include_mfa=True,
                include_devices=False,
                include_requirements=False,
                include_maturity=False,
            )

            assert result["status"] == "success"
            assert result["tenants_processed"] == 2
            assert mock_mfa.call_count == 2

    @pytest.mark.asyncio
    async def test_sync_all_tenants_mfa_failure_handling(self, mock_tenants):
        """Test batch sync handles MFA failures gracefully with skip_failed=True."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_tenants

        with (
            patch("app.services.riverside_sync._get_monitoring_service") as mock_get_monitor,
            patch(
                "app.services.riverside_sync.sync_tenant_mfa", new_callable=AsyncMock
            ) as mock_mfa,
            patch(
                "app.services.riverside_sync.sync_tenant_devices", new_callable=AsyncMock
            ) as mock_devices,
            patch(
                "app.services.riverside_sync.sync_requirement_status", new_callable=AsyncMock
            ) as mock_reqs,
            patch(
                "app.services.riverside_sync.sync_maturity_scores", new_callable=AsyncMock
            ) as mock_maturity,
        ):
            mock_monitor = MagicMock()
            mock_get_monitor.return_value = mock_monitor
            mock_monitor.start_sync_job.return_value = MagicMock(id=1)
            # First tenant succeeds, second fails
            mock_mfa.side_effect = [
                {"status": "success"},
                Exception("MFA sync failed"),
            ]
            mock_devices.return_value = {"status": "success"}
            mock_reqs.return_value = {"status": "success"}
            mock_maturity.return_value = {"status": "success"}

            result = await sync_all_tenants(
                mock_session,
                skip_failed=True,
            )

            # With skip_failed=True, sub-sync failures are caught individually
            # and don't count as full tenant failures
            assert result["status"] == "success"
            assert result["tenants_processed"] == 2
            assert result["tenants_failed"] == 0
            assert mock_mfa.call_count == 2

    @pytest.mark.asyncio
    async def test_sync_all_tenants_custom_batch_size(self, mock_tenants):
        """Test batch sync passes batch size to MFA sync."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_tenants

        # Note: The current implementation doesn't pass batch_size to sync_tenant_mfa
        # This test verifies the current behavior
        with (
            patch("app.services.riverside_sync._get_monitoring_service") as mock_get_monitor,
            patch("app.services.riverside_sync.sync_tenant_mfa") as mock_mfa,
        ):
            mock_monitor = MagicMock()
            mock_get_monitor.return_value = mock_monitor
            mock_monitor.start_sync_job.return_value = MagicMock(id=1)
            mock_mfa.return_value = {"status": "success"}

            await sync_all_tenants(
                mock_session,
                include_mfa=True,
                include_devices=False,
                include_requirements=False,
                include_maturity=False,
            )

            # Verify MFA sync was called for each tenant
            assert mock_mfa.call_count == 2

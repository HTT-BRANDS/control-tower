"""Tests for identity synchronization module."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.sync.identity import (
    _is_privileged_role,
    _parse_last_sign_in,
    _process_user_activity,
    sync_identity,
)


class TestIdentitySync:
    """Test suite for identity synchronization."""

    @pytest.mark.asyncio
    async def test_sync_identity_success(
        self,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        sample_users,
        sample_directory_roles,
    ):
        """Test successful identity synchronization."""
        # Setup
        with patch("app.core.sync.identity.GraphClient") as mock_graph_class:
            mock_graph_client = AsyncMock()
            mock_graph_class.return_value = mock_graph_client

            mock_graph_client.get_users.return_value = sample_users
            mock_graph_client.get_guest_users.return_value = [
                {"userPrincipalName": "guest@example.com"}
            ]
            mock_graph_client.get_directory_roles.return_value = sample_directory_roles
            mock_graph_client.get_service_principals.return_value = [
                {"id": "sp-1", "displayName": "Test App"}
            ]
            mock_graph_client.get_mfa_status.return_value = {
                "value": [
                    {"userPrincipalName": "test@example.com", "isMfaRegistered": True},
                    {"userPrincipalName": "guest@example.com", "isMfaRegistered": False},
                ]
            }

            # Execute
            await sync_identity()

            # Verify
            mock_graph_client.get_users.assert_called_once()
            mock_graph_client.get_directory_roles.assert_called_once()
            mock_db_session.add.assert_called()
            mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_sync_identity_empty_data(
        self,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
    ):
        """Test identity sync with empty data."""
        # Setup
        with patch("app.core.sync.identity.GraphClient") as mock_graph_class:
            mock_graph_client = AsyncMock()
            mock_graph_class.return_value = mock_graph_client

            mock_graph_client.get_users.return_value = []
            mock_graph_client.get_guest_users.return_value = []
            mock_graph_client.get_directory_roles.return_value = []
            mock_graph_client.get_service_principals.return_value = []
            mock_graph_client.get_mfa_status.return_value = {"value": []}

            # Execute
            await sync_identity()

            # Verify - should still create snapshot
            mock_db_session.add.assert_called()

    @pytest.mark.asyncio
    async def test_sync_identity_no_active_tenants(
        self,
        mock_db_session,
        mock_get_db_context,
    ):
        """Test identity sync with no active tenants."""
        # Setup - no tenants
        mock_db_query = MagicMock()
        mock_db_query.filter.return_value = mock_db_query
        mock_db_query.all.return_value = []
        mock_db_session.query.return_value = mock_db_query

        # Execute
        await sync_identity()

        # Verify - no GraphClient calls, but SyncJobLog is still added for monitoring
        # The sync starts before checking for tenants, so add is called once for SyncJobLog
        mock_db_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_identity_graph_error(
        self,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
    ):
        """Test identity sync handles Graph API errors."""
        # Setup
        with patch("app.core.sync.identity.GraphClient") as mock_graph_class:
            mock_graph_client = AsyncMock()
            mock_graph_class.return_value = mock_graph_client

            mock_graph_client.get_users.side_effect = Exception("Graph API error")

            # Execute - should not raise
            await sync_identity()

    @pytest.mark.asyncio
    async def test_sync_identity_mfa_fetch_error(
        self,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        sample_users,
        sample_directory_roles,
    ):
        """Test identity sync continues if MFA fetch fails."""
        # Setup
        with patch("app.core.sync.identity.GraphClient") as mock_graph_class:
            mock_graph_client = AsyncMock()
            mock_graph_class.return_value = mock_graph_client

            mock_graph_client.get_users.return_value = sample_users
            mock_graph_client.get_guest_users.return_value = []
            mock_graph_client.get_directory_roles.return_value = sample_directory_roles
            mock_graph_client.get_service_principals.return_value = []
            mock_graph_client.get_mfa_status.side_effect = Exception("MFA permission denied")

            # Execute - should not raise
            await sync_identity()

            # Verify - should complete without MFA data
            mock_db_session.add.assert_called()

    @pytest.mark.asyncio
    async def test_sync_identity_db_error(
        self,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        sample_users,
        sample_directory_roles,
    ):
        """Test identity sync handles database errors."""
        # Setup
        with patch("app.core.sync.identity.GraphClient") as mock_graph_class:
            mock_graph_client = AsyncMock()
            mock_graph_class.return_value = mock_graph_client

            mock_graph_client.get_users.return_value = sample_users
            mock_graph_client.get_guest_users.return_value = []
            mock_graph_client.get_directory_roles.return_value = sample_directory_roles
            mock_graph_client.get_service_principals.return_value = []
            mock_graph_client.get_mfa_status.return_value = {"value": []}

            mock_db_session.commit.side_effect = SQLAlchemyError("Database error")

            # Execute - should raise after retries are exhausted
            with pytest.raises(SQLAlchemyError):
                await sync_identity()

    @pytest.mark.asyncio
    async def test_sync_identity_stale_accounts(
        self,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        sample_directory_roles,
    ):
        """Test stale account detection."""
        # Setup - create users with different last sign-in times
        stale_user = {
            "id": "user-stale",
            "displayName": "Stale User",
            "userPrincipalName": "stale@example.com",
            "userType": "Member",
            "signInActivity": {
                "lastSignInDateTime": (datetime.now(UTC) - timedelta(days=100)).isoformat()
            },
        }

        active_user = {
            "id": "user-active",
            "displayName": "Active User",
            "userPrincipalName": "active@example.com",
            "userType": "Member",
            "signInActivity": {
                "lastSignInDateTime": (datetime.now(UTC) - timedelta(days=5)).isoformat()
            },
        }

        never_signed_in = {
            "id": "user-never",
            "displayName": "Never Signed In",
            "userPrincipalName": "never@example.com",
            "userType": "Member",
            "signInActivity": {},
        }

        with patch("app.core.sync.identity.GraphClient") as mock_graph_class:
            mock_graph_client = AsyncMock()
            mock_graph_class.return_value = mock_graph_client

            mock_graph_client.get_users.return_value = [stale_user, active_user, never_signed_in]
            mock_graph_client.get_guest_users.return_value = []
            mock_graph_client.get_directory_roles.return_value = []
            mock_graph_client.get_service_principals.return_value = []
            mock_graph_client.get_mfa_status.return_value = {"value": []}

            # Execute
            await sync_identity()

            # Verify
            mock_db_session.add.assert_called()

    @pytest.mark.asyncio
    async def test_sync_identity_privileged_roles(
        self,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        sample_users,
    ):
        """Test privileged role detection."""
        # Setup - directory roles with privileged users
        directory_roles = [
            {
                "displayName": "Global Administrator",
                "description": "Can manage all aspects of Azure AD",
                "members": [
                    {
                        "@odata.type": "#microsoft.graph.user",
                        "id": "user-1",
                        "displayName": "Test User",
                    }
                ],
            },
            {
                "displayName": "Security Administrator",
                "description": "Manages security features",
                "members": [
                    {
                        "@odata.type": "#microsoft.graph.user",
                        "id": "user-1",
                        "displayName": "Test User",
                    }
                ],
            },
            {
                "displayName": "Regular User",
                "description": "Regular user role",
                "members": [
                    {
                        "@odata.type": "#microsoft.graph.user",
                        "id": "user-2",
                        "displayName": "Guest User",
                    }
                ],
            },
        ]

        with patch("app.core.sync.identity.GraphClient") as mock_graph_class:
            mock_graph_client = AsyncMock()
            mock_graph_class.return_value = mock_graph_client

            mock_graph_client.get_users.return_value = sample_users
            mock_graph_client.get_guest_users.return_value = []
            mock_graph_client.get_directory_roles.return_value = directory_roles
            mock_graph_client.get_service_principals.return_value = []
            mock_graph_client.get_mfa_status.return_value = {"value": []}

            # Execute
            await sync_identity()

            # Verify - should create privileged user records for Global and Security admins
            mock_db_session.add.assert_called()

    @pytest.mark.asyncio
    async def test_sync_identity_service_principal_members(
        self,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        sample_users,
    ):
        """Test that service principals in roles are filtered out."""
        # Setup - directory role with SP member
        directory_roles = [
            {
                "displayName": "Application Administrator",
                "description": "Can manage applications",
                "members": [
                    {
                        "@odata.type": "#microsoft.graph.servicePrincipal",
                        "id": "sp-1",
                        "displayName": "Service App",
                    },
                    {
                        "@odata.type": "#microsoft.graph.user",
                        "id": "user-1",
                        "displayName": "Test User",
                    },
                ],
            },
        ]

        with patch("app.core.sync.identity.GraphClient") as mock_graph_class:
            mock_graph_client = AsyncMock()
            mock_graph_class.return_value = mock_graph_client

            mock_graph_client.get_users.return_value = sample_users
            mock_graph_client.get_guest_users.return_value = []
            mock_graph_client.get_directory_roles.return_value = directory_roles
            mock_graph_client.get_service_principals.return_value = []
            mock_graph_client.get_mfa_status.return_value = {"value": []}

            # Execute
            await sync_identity()

            # Verify
            mock_db_session.add.assert_called()

    @pytest.mark.asyncio
    async def test_sync_identity_multiple_tenants(
        self,
        mock_db_session,
        mock_get_db_context,
        mock_tenant,
        sample_users,
        sample_directory_roles,
    ):
        """Test syncing identity from multiple tenants."""
        # Create second tenant
        tenant2 = MagicMock()
        tenant2.id = "tenant-2-uuid"
        tenant2.tenant_id = "test-tenant-id-456"
        tenant2.name = "Test Tenant 2"
        tenant2.is_active = True

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

        with patch("app.core.sync.identity.GraphClient") as mock_graph_class:
            mock_graph_client = AsyncMock()
            mock_graph_class.return_value = mock_graph_client

            mock_graph_client.get_users.return_value = sample_users
            mock_graph_client.get_guest_users.return_value = []
            mock_graph_client.get_directory_roles.return_value = sample_directory_roles
            mock_graph_client.get_service_principals.return_value = []
            mock_graph_client.get_mfa_status.return_value = {"value": []}

            # Execute
            await sync_identity()

            # Verify - GraphClient should be initialized for each tenant
            assert mock_graph_class.call_count == 2


class TestIdentityHelpers:
    """Test suite for identity helper functions."""

    def test_is_privileged_role_standard_roles(self):
        """Test detection of standard privileged roles."""
        assert _is_privileged_role("Global Administrator", "") is True
        assert _is_privileged_role("Security Administrator", "") is True
        assert _is_privileged_role("Billing Administrator", "") is True

    def test_is_privileged_role_admin_in_name(self):
        """Test detection of admin in role name."""
        assert _is_privileged_role("Custom Admin", "") is True
        assert _is_privileged_role("Database Administrator", "") is True

    def test_is_privileged_role_admin_in_description(self):
        """Test detection of admin in description."""
        # "administer" does not contain "administrator", so these should be False
        assert _is_privileged_role("Reader", "Can administer resources") is False
        assert _is_privileged_role("User", "Administrator role for users") is True

    def test_is_privileged_role_not_privileged(self):
        """Test non-privileged roles."""
        assert _is_privileged_role("Reader", "Can read resources") is False
        assert _is_privileged_role("User", "Regular user") is False
        assert _is_privileged_role("Contributor", "Can contribute") is False

    def test_parse_last_sign_in_valid(self):
        """Test parsing valid sign-in datetime."""
        iso_string = "2024-01-15T10:30:00Z"
        result = _parse_last_sign_in(iso_string)
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_parse_last_sign_in_offset(self):
        """Test parsing datetime with offset."""
        iso_string = "2024-01-15T10:30:00+00:00"
        result = _parse_last_sign_in(iso_string)
        assert result is not None
        assert result.year == 2024

    def test_parse_last_sign_in_none(self):
        """Test parsing None."""
        assert _parse_last_sign_in(None) is None

    def test_parse_last_sign_in_empty(self):
        """Test parsing empty string."""
        assert _parse_last_sign_in("") is None

    def test_parse_last_sign_in_invalid(self):
        """Test parsing invalid datetime."""
        assert _parse_last_sign_in("invalid") is None

    def test_process_user_activity_active(self):
        """Test processing active user."""
        user = {
            "signInActivity": {
                "lastSignInDateTime": (datetime.now(UTC) - timedelta(days=5)).isoformat()
            }
        }
        stale_30d = datetime.now(UTC) - timedelta(days=30)
        stale_90d = datetime.now(UTC) - timedelta(days=90)

        is_active, is_stale_30d, is_stale_90d = _process_user_activity(user, stale_30d, stale_90d)

        assert is_active is True
        assert is_stale_30d is False
        assert is_stale_90d is False

    def test_process_user_activity_stale_30d(self):
        """Test processing user stale for 30 days."""
        user = {
            "signInActivity": {
                "lastSignInDateTime": (datetime.now(UTC) - timedelta(days=45)).isoformat()
            }
        }
        stale_30d = datetime.now(UTC) - timedelta(days=30)
        stale_90d = datetime.now(UTC) - timedelta(days=90)

        is_active, is_stale_30d, is_stale_90d = _process_user_activity(user, stale_30d, stale_90d)

        assert is_active is False
        assert is_stale_30d is True
        assert is_stale_90d is False

    def test_process_user_activity_stale_90d(self):
        """Test processing user stale for 90 days."""
        user = {
            "signInActivity": {
                "lastSignInDateTime": (datetime.now(UTC) - timedelta(days=100)).isoformat()
            }
        }
        stale_30d = datetime.now(UTC) - timedelta(days=30)
        stale_90d = datetime.now(UTC) - timedelta(days=90)

        is_active, is_stale_30d, is_stale_90d = _process_user_activity(user, stale_30d, stale_90d)

        assert is_active is False
        assert is_stale_30d is True
        assert is_stale_90d is True

    def test_process_user_activity_never_signed_in(self):
        """Test processing user who never signed in."""
        user = {"signInActivity": {}}
        stale_30d = datetime.now(UTC) - timedelta(days=30)
        stale_90d = datetime.now(UTC) - timedelta(days=90)

        is_active, is_stale_30d, is_stale_90d = _process_user_activity(user, stale_30d, stale_90d)

        assert is_active is False
        assert is_stale_30d is True
        assert is_stale_90d is True

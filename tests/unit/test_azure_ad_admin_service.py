"""Tests for Azure AD Admin Service.

This module tests the AzureADAdminService for collecting and managing
admin role data, including caching, retry logic, and multi-tenant support.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import Azure modules BEFORE any app imports to ensure namespace packages work
try:
    from azure.core.credentials import TokenCredential
    from azure.core.exceptions import HttpResponseError
    from azure.identity import ClientSecretCredential
except ImportError:
    # Mock classes if Azure SDK not available
    class ClientSecretCredential:
        pass

    class TokenCredential:
        pass

    class HttpResponseError(Exception):
        def __init__(self, message="", status_code=None, **kwargs):
            super().__init__(message)
            self.status_code = status_code
            self.message = message


from app.api.services.azure_ad_admin_service import (
    AdminRoleError,
    AdminRoleMetrics,
    AzureADAdminService,
    azure_ad_admin_service,
)
from app.api.services.graph_client import (
    AdminRoleSummary,
    DirectoryRole,
    PrivilegedAccessAssignment,
    RoleAssignment,
)


class TestAdminRoleDataClasses:
    """Test suite for admin role data classes."""

    def test_admin_role_metrics_creation(self):
        """Test AdminRoleMetrics dataclass creation."""
        metrics = AdminRoleMetrics(
            tenant_id="tenant-123",
            total_roles_collected=25,
            total_assignments_collected=100,
            pim_assignments_collected=10,
            privileged_users_count=15,
            privileged_service_principals_count=5,
            collection_duration_seconds=5.5,
            errors_encountered=0,
            cached=False,
        )
        assert metrics.tenant_id == "tenant-123"
        assert metrics.total_roles_collected == 25
        assert metrics.privileged_users_count == 15
        assert metrics.cached is False

    def test_admin_role_error_creation(self):
        """Test AdminRoleError exception."""
        error = AdminRoleError("Test error", tenant_id="tenant-123")
        assert str(error) == "Test error"
        assert error.tenant_id == "tenant-123"

    def test_admin_role_error_without_tenant(self):
        """Test AdminRoleError without tenant ID."""
        error = AdminRoleError("Test error")
        assert str(error) == "Test error"
        assert error.tenant_id is None


class TestAzureADAdminService:
    """Test suite for AzureADAdminService."""

    @pytest.fixture
    def admin_service(self):
        """Create AzureADAdminService instance."""
        return AzureADAdminService()

    @pytest.fixture
    def mock_graph_client(self):
        """Create mocked GraphClient."""
        client = MagicMock()
        return client

    @pytest.fixture
    def sample_directory_roles(self):
        """Sample directory roles."""
        return [
            DirectoryRole(
                role_id="role-1",
                display_name="Global Administrator",
                description="Can manage all aspects",
                role_template_id="62e90394-69f5-4237-9190-012177145e10",
                is_built_in=True,
            ),
            DirectoryRole(
                role_id="role-2",
                display_name="Security Administrator",
                description="Can manage security",
                role_template_id="194ae4cb-b126-40b2-bd5b-6091b380977d",
                is_built_in=True,
            ),
        ]

    @pytest.fixture
    def sample_role_assignments(self):
        """Sample role assignments."""
        return [
            RoleAssignment(
                assignment_id="assign-1",
                principal_id="user-1",
                principal_type="User",
                principal_display_name="admin@example.com",
                role_definition_id="role-1",
                role_name="Global Administrator",
                role_template_id="62e90394-69f5-4237-9190-012177145e10",
                scope_type="Directory",
                scope_id=None,
                created_date_time="2024-01-15T10:00:00Z",
                assignment_type="Direct",
            ),
            RoleAssignment(
                assignment_id="assign-2",
                principal_id="user-2",
                principal_type="User",
                principal_display_name="security@example.com",
                role_definition_id="role-2",
                role_name="Security Administrator",
                role_template_id="194ae4cb-b126-40b2-bd5b-6091b380977d",
                scope_type="Directory",
                scope_id=None,
                created_date_time="2024-01-15T11:00:00Z",
                assignment_type="Direct",
            ),
            RoleAssignment(
                assignment_id="assign-3",
                principal_id="sp-1",
                principal_type="ServicePrincipal",
                principal_display_name="app-123",
                role_definition_id="role-2",
                role_name="Security Administrator",
                role_template_id="194ae4cb-b126-40b2-bd5b-6091b380977d",
                scope_type="Directory",
                scope_id=None,
                created_date_time="2024-01-15T12:00:00Z",
                assignment_type="Direct",
            ),
        ]

    @pytest.fixture
    def sample_pim_assignments(self):
        """Sample PIM assignments."""
        return [
            PrivilegedAccessAssignment(
                assignment_id="pim-1",
                principal_id="user-3",
                principal_type="User",
                principal_display_name="pimadmin@example.com",
                role_definition_id="role-1",
                role_name="Global Administrator",
                assignment_state="eligible",
                start_date_time="2024-01-15T08:00:00Z",
                end_date_time="2024-01-16T08:00:00Z",
                duration="1 day",
            ),
        ]

    @pytest.mark.asyncio
    async def test_get_directory_roles_success(
        self, admin_service, mock_graph_client, sample_directory_roles
    ):
        """Test successful retrieval of directory roles."""
        mock_graph_client.get_directory_role_definitions = AsyncMock(
            return_value=sample_directory_roles
        )

        with (
            patch.object(admin_service, "_get_client", return_value=mock_graph_client),
            patch("app.api.services.azure_ad_admin_service.cache_manager") as mock_cache,
        ):
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()

            result = await admin_service.get_directory_roles("tenant-123")

            assert len(result) == 2
            assert result[0].display_name == "Global Administrator"
            assert result[1].display_name == "Security Administrator"
            mock_graph_client.get_directory_role_definitions.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_get_directory_roles_from_cache(self, admin_service, sample_directory_roles):
        """Test retrieval of directory roles from cache."""
        cached_data = [r.__dict__ for r in sample_directory_roles]

        with patch("app.api.services.azure_ad_admin_service.cache_manager") as mock_cache:
            mock_cache.get = AsyncMock(return_value=cached_data)
            mock_cache.generate_key = MagicMock(return_value="cache-key")

            result = await admin_service.get_directory_roles("tenant-123", use_cache=True)

            assert len(result) == 2
            assert result[0].display_name == "Global Administrator"

    @pytest.mark.asyncio
    async def test_get_directory_roles_error(self, admin_service, mock_graph_client):
        """Test error handling in directory roles retrieval."""
        mock_graph_client.get_directory_role_definitions = AsyncMock(
            side_effect=Exception("API Error")
        )

        with patch.object(admin_service, "_get_client", return_value=mock_graph_client):
            with pytest.raises(AdminRoleError) as exc_info:
                await admin_service.get_directory_roles("tenant-123")

            assert "tenant-123" in str(exc_info.value.tenant_id)
            assert "Failed to get directory roles" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_role_assignments_success(
        self, admin_service, mock_graph_client, sample_role_assignments
    ):
        """Test successful retrieval of role assignments."""
        mock_graph_client.get_role_assignments_paginated = AsyncMock(
            return_value=sample_role_assignments
        )

        with (
            patch.object(admin_service, "_get_client", return_value=mock_graph_client),
            patch("app.api.services.azure_ad_admin_service.cache_manager") as mock_cache,
        ):
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()
            mock_cache.generate_key = MagicMock(return_value="cache-key")

            result = await admin_service.get_role_assignments("tenant-123", batch_size=100)

            assert len(result) == 3
            assert result[0].principal_type == "User"
            assert result[2].principal_type == "ServicePrincipal"

    @pytest.mark.asyncio
    async def test_get_pim_assignments_success(
        self, admin_service, mock_graph_client, sample_pim_assignments
    ):
        """Test successful retrieval of PIM assignments."""
        mock_graph_client.get_pim_role_assignments = AsyncMock(return_value=sample_pim_assignments)

        with (
            patch.object(admin_service, "_get_client", return_value=mock_graph_client),
            patch("app.api.services.azure_ad_admin_service.cache_manager") as mock_cache,
        ):
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()
            mock_cache.generate_key = MagicMock(return_value="cache-key")

            result = await admin_service.get_pim_assignments("tenant-123")

            assert len(result) == 1
            assert result[0].principal_display_name == "pimadmin@example.com"
            assert result[0].assignment_state == "eligible"

    @pytest.mark.asyncio
    async def test_get_pim_assignments_error_returns_empty(self, admin_service, mock_graph_client):
        """Test PIM error handling returns empty list."""
        mock_graph_client.get_pim_role_assignments = AsyncMock(
            side_effect=Exception("PIM not enabled")
        )

        with (
            patch.object(admin_service, "_get_client", return_value=mock_graph_client),
            patch("app.api.services.azure_ad_admin_service.cache_manager") as mock_cache,
        ):
            mock_cache.get = AsyncMock(return_value=None)

            result = await admin_service.get_pim_assignments("tenant-123")

            assert result == []

    @pytest.mark.asyncio
    async def test_get_privileged_users(
        self, admin_service, mock_graph_client, sample_role_assignments, sample_pim_assignments
    ):
        """Test retrieval of privileged users."""
        mock_graph_client.get_role_assignments_paginated = AsyncMock(
            return_value=sample_role_assignments
        )
        mock_graph_client.get_pim_role_assignments = AsyncMock(return_value=sample_pim_assignments)

        with (
            patch.object(admin_service, "_get_client", return_value=mock_graph_client),
            patch("app.api.services.azure_ad_admin_service.cache_manager") as mock_cache,
        ):
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()

            result = await admin_service.get_privileged_users("tenant-123", include_pim=True)

            assert len(result) == 3  # 2 direct + 1 PIM

            # Check first user (Global Admin)
            user1 = next(u for u in result if u["principal_id"] == "user-1")
            assert user1["user_principal_name"] == "admin@example.com"
            assert len(user1["roles"]) == 1
            assert user1["roles"][0]["role_name"] == "Global Administrator"

    @pytest.mark.asyncio
    async def test_get_privileged_users_without_pim(
        self, admin_service, mock_graph_client, sample_role_assignments
    ):
        """Test retrieval of privileged users without PIM."""
        mock_graph_client.get_role_assignments_paginated = AsyncMock(
            return_value=sample_role_assignments
        )

        with (
            patch.object(admin_service, "_get_client", return_value=mock_graph_client),
            patch("app.api.services.azure_ad_admin_service.cache_manager") as mock_cache,
        ):
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()

            result = await admin_service.get_privileged_users("tenant-123", include_pim=False)

            # Should only get users, not service principals
            users = [u for u in result if u.get("user_principal_name")]
            assert len(users) == 2  # user-1 and user-2

    @pytest.mark.asyncio
    async def test_get_privileged_service_principals(
        self, admin_service, mock_graph_client, sample_role_assignments
    ):
        """Test retrieval of privileged service principals."""
        mock_graph_client.get_role_assignments_paginated = AsyncMock(
            return_value=sample_role_assignments
        )

        with (
            patch.object(admin_service, "_get_client", return_value=mock_graph_client),
            patch("app.api.services.azure_ad_admin_service.cache_manager") as mock_cache,
        ):
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()

            result = await admin_service.get_privileged_service_principals("tenant-123")

            assert len(result) == 1
            assert result[0]["principal_id"] == "sp-1"
            assert result[0]["app_id"] == "app-123"
            assert len(result[0]["roles"]) == 1

    @pytest.mark.asyncio
    async def test_get_admin_role_summary(self, admin_service, mock_graph_client):
        """Test admin role summary retrieval."""
        summary = AdminRoleSummary(
            tenant_id="tenant-123",
            total_roles=25,
            total_assignments=100,
            privileged_users=[],
            privileged_service_principals=[],
            pim_assignments=[],
            roles_without_members=[],
            global_admin_count=5,
            security_admin_count=3,
            privileged_role_admin_count=2,
            other_admin_count=10,
        )

        mock_graph_client.get_admin_role_summary = AsyncMock(return_value=summary)

        with (
            patch.object(admin_service, "_get_client", return_value=mock_graph_client),
            patch("app.api.services.azure_ad_admin_service.cache_manager") as mock_cache,
        ):
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()
            mock_cache.generate_key = MagicMock(return_value="cache-key")

            result = await admin_service.get_admin_role_summary("tenant-123")

            assert result.tenant_id == "tenant-123"
            assert result.total_roles == 25
            assert result.global_admin_count == 5
            assert result.security_admin_count == 3

    @pytest.mark.asyncio
    async def test_get_admin_role_summary_from_cache(self, admin_service):
        """Test admin role summary from cache."""
        cached_summary = {
            "tenant_id": "tenant-123",
            "total_roles": 25,
            "total_assignments": 100,
            "privileged_users": [],
            "privileged_service_principals": [],
            "pim_assignments": [],
            "roles_without_members": [],
            "global_admin_count": 5,
            "security_admin_count": 3,
            "privileged_role_admin_count": 2,
            "other_admin_count": 10,
        }

        with patch("app.api.services.azure_ad_admin_service.cache_manager") as mock_cache:
            mock_cache.get = AsyncMock(return_value=cached_summary)
            mock_cache.generate_key = MagicMock(return_value="cache-key")

            result = await admin_service.get_admin_role_summary("tenant-123")

            assert result.tenant_id == "tenant-123"
            assert result.global_admin_count == 5

    @pytest.mark.asyncio
    async def test_get_global_admins(
        self, admin_service, mock_graph_client, sample_role_assignments
    ):
        """Test retrieval of global admins."""
        mock_graph_client.get_role_assignments_paginated = AsyncMock(
            return_value=sample_role_assignments
        )
        mock_graph_client.get_pim_role_assignments = AsyncMock(return_value=[])

        with (
            patch.object(admin_service, "_get_client", return_value=mock_graph_client),
            patch("app.api.services.azure_ad_admin_service.cache_manager") as mock_cache,
        ):
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()

            result = await admin_service.get_global_admins("tenant-123")

            assert len(result) == 1
            assert result[0]["principal_id"] == "user-1"
            assert result[0]["user_principal_name"] == "admin@example.com"

    @pytest.mark.asyncio
    async def test_get_security_admins(
        self, admin_service, mock_graph_client, sample_role_assignments
    ):
        """Test retrieval of security admins."""
        mock_graph_client.get_role_assignments_paginated = AsyncMock(
            return_value=sample_role_assignments
        )
        mock_graph_client.get_pim_role_assignments = AsyncMock(return_value=[])

        with (
            patch.object(admin_service, "_get_client", return_value=mock_graph_client),
            patch("app.api.services.azure_ad_admin_service.cache_manager") as mock_cache,
        ):
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()

            result = await admin_service.get_security_admins("tenant-123")

            assert len(result) == 1
            assert result[0]["principal_id"] == "user-2"

    @pytest.mark.asyncio
    async def test_get_role_assignment_counts_by_user(
        self, admin_service, mock_graph_client, sample_role_assignments
    ):
        """Test role assignment counts grouped by user."""
        mock_graph_client.get_role_assignments_paginated = AsyncMock(
            return_value=sample_role_assignments
        )
        mock_graph_client.get_pim_role_assignments = AsyncMock(return_value=[])

        with (
            patch.object(admin_service, "_get_client", return_value=mock_graph_client),
            patch("app.api.services.azure_ad_admin_service.cache_manager") as mock_cache,
        ):
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock()

            result = await admin_service.get_role_assignment_counts_by_user("tenant-123")

            assert "admin@example.com" in result
            assert result["admin@example.com"]["total_role_count"] == 1

    @pytest.mark.asyncio
    async def test_invalidate_cache(self, admin_service):
        """Test cache invalidation."""
        with patch("app.api.services.azure_ad_admin_service.cache_manager") as mock_cache:
            mock_cache.delete_pattern = AsyncMock(return_value=5)

            result = await admin_service.invalidate_cache("tenant-123")

            # The result is the sum of all deleted patterns (4 patterns * 5 = 20)
            assert result == 20
            assert mock_cache.delete_pattern.call_count == 4  # 4 different patterns

    @pytest.mark.asyncio
    async def test_invalidate_cache_specific_type(self, admin_service):
        """Test cache invalidation for specific data type."""
        with patch("app.api.services.azure_ad_admin_service.cache_manager") as mock_cache:
            mock_cache.delete_pattern = AsyncMock(return_value=2)

            result = await admin_service.invalidate_cache("tenant-123", data_type="summary")

            assert result == 2
            mock_cache.delete_pattern.assert_called_once_with("summary:tenant-123")

    def test_batch_size_limit(self, admin_service):
        """Test batch size is limited to 999."""
        assert admin_service.MAX_BATCH_SIZE == 999
        assert admin_service.DEFAULT_BATCH_SIZE == 100

    def test_cache_ttl_values(self, admin_service):
        """Test cache TTL configuration."""
        assert admin_service.CACHE_TTL_ROLES == 3600  # 1 hour
        assert admin_service.CACHE_TTL_ASSIGNMENTS == 1800  # 30 minutes
        assert admin_service.CACHE_TTL_SUMMARY == 900  # 15 minutes


class TestAzureADAdminServiceGlobal:
    """Test global service instance."""

    def test_global_service_instance_exists(self):
        """Test that global service instance exists."""
        assert azure_ad_admin_service is not None
        assert isinstance(azure_ad_admin_service, AzureADAdminService)

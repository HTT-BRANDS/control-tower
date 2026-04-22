"""Tests for Microsoft Graph API admin role collection methods.

This module tests the enhanced GraphClient methods for admin role data collection
including directory roles, role assignments, PIM, and privileged access data.
"""

from unittest.mock import AsyncMock, patch

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


from app.api.services.graph_client import (
    ADMIN_ROLE_TEMPLATE_IDS,
    AdminRoleSummary,
    DirectoryRole,
    GraphClient,
    PrivilegedAccessAssignment,
    RoleAssignment,
)


class TestAdminRoleDataClasses:
    """Test suite for admin role data classes."""

    def test_directory_role_creation(self):
        """Test DirectoryRole dataclass creation."""
        role = DirectoryRole(
            role_id="role-123",
            display_name="Global Administrator",
            description="Can manage all aspects of Azure AD",
            role_template_id="62e90394-69f5-4237-9190-012177145e10",
            is_built_in=True,
        )
        assert role.role_id == "role-123"
        assert role.display_name == "Global Administrator"
        assert role.role_template_id == "62e90394-69f5-4237-9190-012177145e10"
        assert role.is_built_in is True

    def test_role_assignment_creation(self):
        """Test RoleAssignment dataclass creation."""
        assignment = RoleAssignment(
            assignment_id="assign-123",
            principal_id="user-456",
            principal_type="User",
            principal_display_name="test@example.com",
            role_definition_id="role-789",
            role_name="Security Administrator",
            role_template_id="194ae4cb-b126-40b2-bd5b-6091b380977d",
            scope_type="Directory",
            scope_id=None,
            created_date_time="2024-01-15T10:00:00Z",
            assignment_type="Direct",
        )
        assert assignment.assignment_id == "assign-123"
        assert assignment.principal_type == "User"
        assert assignment.role_name == "Security Administrator"

    def test_privileged_access_assignment_creation(self):
        """Test PrivilegedAccessAssignment dataclass creation."""
        assignment = PrivilegedAccessAssignment(
            assignment_id="pim-123",
            principal_id="user-456",
            principal_type="User",
            principal_display_name="admin@example.com",
            role_definition_id="role-789",
            role_name="Global Administrator",
            assignment_state="active",
            start_date_time="2024-01-15T08:00:00Z",
            end_date_time="2024-01-16T08:00:00Z",
            duration="1 day",
        )
        assert assignment.assignment_id == "pim-123"
        assert assignment.assignment_state == "active"
        assert assignment.duration == "1 day"

    def test_admin_role_summary_creation(self):
        """Test AdminRoleSummary dataclass creation."""
        summary = AdminRoleSummary(
            tenant_id="tenant-123",
            total_roles=25,
            total_assignments=100,
            privileged_users=[],
            privileged_service_principals=[],
            pim_assignments=[],
            roles_without_members=["role-1"],
            global_admin_count=5,
            security_admin_count=3,
            privileged_role_admin_count=2,
            other_admin_count=10,
        )
        assert summary.tenant_id == "tenant-123"
        assert summary.total_roles == 25
        assert summary.global_admin_count == 5


class TestGraphClientAdminRoles:
    """Test suite for GraphClient admin role methods."""

    @pytest.fixture
    def mock_graph_client(self):
        """Create a GraphClient with mocked credentials."""
        with patch.object(GraphClient, "_get_token") as mock_token:
            mock_token.return_value = "mock-token"
            client = GraphClient("test-tenant-id")
            return client

    @pytest.fixture
    def sample_directory_roles(self):
        """Sample directory roles from Graph API."""
        return {
            "value": [
                {
                    "id": "role-1",
                    "displayName": "Global Administrator",
                    "description": "Can manage all aspects of Azure AD",
                    "roleTemplateId": "62e90394-69f5-4237-9190-012177145e10",
                    "isBuiltIn": True,
                },
                {
                    "id": "role-2",
                    "displayName": "Security Administrator",
                    "description": "Can manage security-related features",
                    "roleTemplateId": "194ae4cb-b126-40b2-bd5b-6091b380977d",
                    "isBuiltIn": True,
                },
            ],
            "@odata.nextLink": None,
        }

    @pytest.fixture
    def sample_role_assignments(self):
        """Sample role assignments from Graph API."""
        return {
            "value": [
                {
                    "id": "assign-1",
                    "principal": {
                        "id": "user-1",
                        "@odata.type": "#microsoft.graph.user",
                        "userPrincipalName": "admin@example.com",
                        "displayName": "Admin User",
                    },
                    "roleDefinition": {
                        "id": "role-1",
                        "displayName": "Global Administrator",
                        "templateId": "62e90394-69f5-4237-9190-012177145e10",
                    },
                    "createdDateTime": "2024-01-15T10:00:00Z",
                },
                {
                    "id": "assign-2",
                    "principal": {
                        "id": "sp-1",
                        "@odata.type": "#microsoft.graph.servicePrincipal",
                        "appId": "app-123",
                        "displayName": "Service App",
                    },
                    "roleDefinition": {
                        "id": "role-2",
                        "displayName": "Security Administrator",
                        "templateId": "194ae4cb-b126-40b2-bd5b-6091b380977d",
                    },
                    "createdDateTime": "2024-01-15T11:00:00Z",
                },
            ],
            "@odata.nextLink": None,
        }

    @pytest.fixture
    def sample_pim_assignments(self):
        """Sample PIM assignments from Graph API."""
        return {
            "value": [
                {
                    "id": "pim-1",
                    "principal": {
                        "id": "user-2",
                        "@odata.type": "#microsoft.graph.user",
                        "userPrincipalName": "pimadmin@example.com",
                    },
                    "roleDefinition": {
                        "id": "role-1",
                        "displayName": "Global Administrator",
                        "templateId": "62e90394-69f5-4237-9190-012177145e10",
                    },
                    "startDateTime": "2024-01-15T08:00:00Z",
                    "endDateTime": "2024-01-16T08:00:00Z",
                },
            ],
            "@odata.nextLink": None,
        }

    @pytest.mark.asyncio
    async def test_get_directory_role_definitions(self, mock_graph_client, sample_directory_roles):
        """Test successful retrieval of directory role definitions."""
        with patch.object(mock_graph_client, "_request") as mock_request:
            mock_request.return_value = sample_directory_roles

            result = await mock_graph_client.get_directory_role_definitions()

            assert len(result) == 2
            assert result[0].display_name == "Global Administrator"
            assert result[0].role_template_id == "62e90394-69f5-4237-9190-012177145e10"
            assert result[0].is_built_in is True
            assert result[1].display_name == "Security Administrator"

    @pytest.mark.asyncio
    async def test_get_directory_role_definitions_paginated(self, mock_graph_client):
        """Test paginated directory role definitions."""
        page1 = {
            "value": [
                {
                    "id": "role-1",
                    "displayName": "Role 1",
                    "description": "Test",
                    "roleTemplateId": "template-1",
                    "isBuiltIn": True,
                },
            ],
            "@odata.nextLink": "https://graph.microsoft.com/v1.0/directoryRoles?$skip=1",
        }
        page2 = {
            "value": [
                {
                    "id": "role-2",
                    "displayName": "Role 2",
                    "description": "Test",
                    "roleTemplateId": "template-2",
                    "isBuiltIn": True,
                },
            ],
            "@odata.nextLink": None,
        }

        with patch.object(mock_graph_client, "_request") as mock_request:
            mock_request.side_effect = [page1, page2]

            result = await mock_graph_client.get_directory_role_definitions()

            assert len(result) == 2
            assert mock_request.call_count == 2

    @pytest.mark.asyncio
    async def test_get_directory_role_definitions_exclude_builtin(self, mock_graph_client):
        """Test excluding built-in roles."""
        data = {
            "value": [
                {
                    "id": "role-1",
                    "displayName": "Custom Role",
                    "roleTemplateId": "template-1",
                    "isBuiltIn": False,
                },
                {
                    "id": "role-2",
                    "displayName": "Built-in Role",
                    "roleTemplateId": "template-2",
                    "isBuiltIn": True,
                },
            ],
            "@odata.nextLink": None,
        }

        with patch.object(mock_graph_client, "_request") as mock_request:
            mock_request.return_value = data

            result = await mock_graph_client.get_directory_role_definitions(include_built_in=False)

            assert len(result) == 1
            assert result[0].display_name == "Custom Role"

    @pytest.mark.asyncio
    async def test_get_role_assignments_paginated(self, mock_graph_client, sample_role_assignments):
        """Test role assignments retrieval."""
        with patch.object(mock_graph_client, "_request") as mock_request:
            mock_request.return_value = sample_role_assignments

            result = await mock_graph_client.get_role_assignments_paginated(batch_size=100)

            assert len(result) == 2
            assert result[0].principal_type == "User"
            assert result[0].principal_display_name == "admin@example.com"
            assert result[0].role_name == "Global Administrator"
            # Service principal display_name comes from appId if available, otherwise displayName
            assert result[1].principal_display_name == "Service App"

    @pytest.mark.asyncio
    async def test_get_role_assignments_paginated_with_group(self, mock_graph_client):
        """Test role assignments with group principals."""
        data = {
            "value": [
                {
                    "id": "assign-1",
                    "principal": {
                        "id": "group-1",
                        "@odata.type": "#microsoft.graph.group",
                        "displayName": "Admins Group",
                    },
                    "roleDefinition": {
                        "id": "role-1",
                        "displayName": "Global Administrator",
                        "templateId": "62e90394-69f5-4237-9190-012177145e10",
                    },
                },
            ],
            "@odata.nextLink": None,
        }

        with patch.object(mock_graph_client, "_request") as mock_request:
            mock_request.return_value = data

            result = await mock_graph_client.get_role_assignments_paginated()

            assert len(result) == 1
            assert result[0].principal_type == "Group"
            assert result[0].assignment_type == "Group"
            assert result[0].principal_display_name == "Admins Group"

    @pytest.mark.asyncio
    async def test_get_service_principal_role_assignments(self, mock_graph_client):
        """Test service principal role assignments filtering."""
        # Note: Service principals are filtered by checking @odata.type
        assignments = [
            RoleAssignment(
                assignment_id="assign-1",
                principal_id="user-1",
                principal_type="User",
                principal_display_name="user@example.com",
                role_definition_id="role-1",
                role_name="User Administrator",
                role_template_id="fe930be7-5e62-47db-91af-98c3a49a38b1",
                scope_type="Directory",
                scope_id=None,
                created_date_time="2024-01-15T10:00:00Z",
                assignment_type="Direct",
            ),
            RoleAssignment(
                assignment_id="assign-2",
                principal_id="sp-1",
                principal_type="ServicePrincipal",
                principal_display_name="app-123",
                role_definition_id="role-2",
                role_name="Application Administrator",
                role_template_id="9b895d92-2cd3-44c7-9d02-a6ac2d5ea5c3",
                scope_type="Directory",
                scope_id=None,
                created_date_time="2024-01-15T11:00:00Z",
                assignment_type="Direct",
            ),
        ]

        with patch.object(mock_graph_client, "get_role_assignments_paginated") as mock_get:
            mock_get.return_value = assignments

            result = await mock_graph_client.get_service_principal_role_assignments()

            assert len(result) == 1
            assert result[0].principal_type == "ServicePrincipal"
            assert result[0].principal_display_name == "app-123"

    @pytest.mark.asyncio
    async def test_get_pim_role_assignments(self, mock_graph_client, sample_pim_assignments):
        """Test PIM role assignments retrieval."""
        with patch.object(mock_graph_client, "_get_token") as mock_token:
            mock_token.return_value = "mock-token"

            # Mock the _get_pim_assignments_by_type method directly
            with patch.object(mock_graph_client, "_get_pim_assignments_by_type") as mock_get_pim:
                mock_get_pim.return_value = [
                    PrivilegedAccessAssignment(
                        assignment_id="pim-1",
                        principal_id="user-2",
                        principal_type="User",
                        principal_display_name="pimadmin@example.com",
                        role_definition_id="role-1",
                        role_name="Global Administrator",
                        assignment_state="active",
                        start_date_time="2024-01-15T08:00:00Z",
                        end_date_time="2024-01-16T08:00:00Z",
                        duration="1 day",
                    )
                ]

                result = await mock_graph_client.get_pim_role_assignments(
                    batch_size=100, include_eligible=False, include_active=True
                )

                assert len(result) == 1
                assert result[0].principal_type == "User"
                assert result[0].assignment_state == "active"
                assert result[0].start_date_time == "2024-01-15T08:00:00Z"

    @pytest.mark.asyncio
    async def test_get_pim_role_assignments_error_handling(self, mock_graph_client):
        """Test PIM error handling when PIM is not enabled."""
        with patch.object(mock_graph_client, "_get_token") as mock_token:
            mock_token.return_value = "mock-token"

            with patch("httpx.AsyncClient") as mock_client:
                mock_async_client = AsyncMock()
                mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
                mock_async_client.__aexit__ = AsyncMock(return_value=None)

                # Simulate 404 error (PIM not enabled)
                import httpx

                mock_async_client.request = AsyncMock(side_effect=httpx.HTTPError("Not Found"))
                mock_client.return_value = mock_async_client

                result = await mock_graph_client.get_pim_role_assignments()

                # Should return empty list when PIM is not available
                assert result == []

    @pytest.mark.asyncio
    async def test_get_admin_role_summary(self, mock_graph_client):
        """Test admin role summary generation."""
        # Mock the various dependencies
        roles = [
            DirectoryRole(
                role_id="role-1",
                display_name="Global Administrator",
                description="Can manage all aspects",
                role_template_id="62e90394-69f5-4237-9190-012177145e10",
                is_built_in=True,
            ),
        ]

        assignments = [
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
        ]

        with (
            patch.object(mock_graph_client, "get_directory_role_definitions") as mock_roles,
            patch.object(mock_graph_client, "get_role_assignments_paginated") as mock_assignments,
            patch.object(mock_graph_client, "get_pim_role_assignments") as mock_pim,
        ):
            mock_roles.return_value = roles
            mock_assignments.return_value = assignments
            mock_pim.return_value = []

            result = await mock_graph_client.get_admin_role_summary(batch_size=100)

            assert isinstance(result, AdminRoleSummary)
            assert result.tenant_id == "test-tenant-id"
            assert result.total_roles == 1
            assert result.total_assignments == 2
            assert result.global_admin_count == 1
            assert result.security_admin_count == 1

    @pytest.mark.asyncio
    async def test_get_admin_role_summary_with_service_principals(self, mock_graph_client):
        """Test admin role summary with service principal assignments."""
        # Application Administrator is not in the admin list, use Security Admin
        assignments = [
            RoleAssignment(
                assignment_id="assign-1",
                principal_id="sp-1",
                principal_type="ServicePrincipal",
                principal_display_name="app-123",
                role_definition_id="role-2",
                role_name="Security Administrator",
                role_template_id="194ae4cb-b126-40b2-bd5b-6091b380977d",
                scope_type="Directory",
                scope_id=None,
                created_date_time="2024-01-15T10:00:00Z",
                assignment_type="Direct",
            ),
        ]

        with (
            patch.object(mock_graph_client, "get_directory_role_definitions") as mock_roles,
            patch.object(mock_graph_client, "get_role_assignments_paginated") as mock_assignments,
            patch.object(mock_graph_client, "get_pim_role_assignments") as mock_pim,
        ):
            mock_roles.return_value = []
            mock_assignments.return_value = assignments
            mock_pim.return_value = []

            result = await mock_graph_client.get_admin_role_summary()

            assert len(result.privileged_service_principals) == 1
            assert result.privileged_service_principals[0]["principal_id"] == "sp-1"
            assert result.privileged_service_principals[0]["principal_display_name"] == "app-123"


class TestAdminRoleTemplateIds:
    """Test suite for admin role template IDs."""

    def test_global_admin_template_id_present(self):
        """Test that Global Admin template ID is present."""
        assert "62e90394-69f5-4237-9190-012177145e10" in ADMIN_ROLE_TEMPLATE_IDS

    def test_security_admin_template_id_present(self):
        """Test that Security Admin template ID is present."""
        assert "194ae4cb-b126-40b2-bd5b-6091b380977d" in ADMIN_ROLE_TEMPLATE_IDS

    def test_privileged_role_admin_template_id_present(self):
        """Test that Privileged Role Admin template ID is present."""
        assert "e8611ab8-c189-46e8-94e1-60213ab1f814" in ADMIN_ROLE_TEMPLATE_IDS

    def test_all_template_ids_are_valid_uuids(self):
        """Test that all template IDs are valid UUID format."""
        import uuid

        for role_id in ADMIN_ROLE_TEMPLATE_IDS:
            try:
                uuid.UUID(role_id)
            except ValueError:
                pytest.fail(f"Invalid UUID format: {role_id}")

    def test_admin_role_count(self):
        """Test that we have expected number of admin roles."""
        # Should have at least the major admin roles
        assert len(ADMIN_ROLE_TEMPLATE_IDS) >= 10

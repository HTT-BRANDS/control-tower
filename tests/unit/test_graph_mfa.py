"""Tests for Microsoft Graph API MFA data collection methods.

This module tests the enhanced GraphClient methods for MFA data collection
including pagination, error handling, and retry logic.
"""

from unittest.mock import patch

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

from app.api.services.graph_client import (  # noqa: E402
    ADMIN_ROLE_TEMPLATE_IDS,
    GraphClient,
    MFAError,
    MFAMethodDetails,
    TenantMFASummary,
    UserMFAStatus,
)


class TestMFADataClasses:
    """Test suite for MFA data classes."""

    def test_mfa_method_details_creation(self):
        """Test MFAMethodDetails dataclass creation."""
        method = MFAMethodDetails(
            method_type="phoneAuthenticationMethod",
            is_default=True,
            is_enabled=True,
            phone_number="+1234567890",
            display_name="Mobile Phone",
        )
        assert method.method_type == "phoneAuthenticationMethod"
        assert method.is_default is True
        assert method.is_enabled is True
        assert method.phone_number == "+1234567890"
        assert method.display_name == "Mobile Phone"

    def test_user_mfa_status_creation(self):
        """Test UserMFAStatus dataclass creation."""
        method = MFAMethodDetails(
            method_type="microsoftAuthenticatorAuthenticationMethod",
            is_default=True,
            is_enabled=True,
        )
        status = UserMFAStatus(
            user_id="user-123",
            user_principal_name="test@example.com",
            display_name="Test User",
            is_mfa_registered=True,
            methods_registered=["microsoftAuthenticator"],
            auth_methods=[method],
            default_method="microsoftAuthenticatorAuthenticationMethod",
            last_updated="2024-01-15T10:30:00Z",
        )
        assert status.user_id == "user-123"
        assert status.is_mfa_registered is True
        assert len(status.auth_methods) == 1

    def test_tenant_mfa_summary_creation(self):
        """Test TenantMFASummary dataclass creation."""
        summary = TenantMFASummary(
            tenant_id="tenant-123",
            total_users=100,
            mfa_registered_users=80,
            mfa_coverage_percentage=80.0,
            admin_accounts_total=10,
            admin_accounts_mfa=10,
            admin_mfa_percentage=100.0,
            method_breakdown={"microsoftAuthenticator": 80},
            users_without_mfa=[],
        )
        assert summary.tenant_id == "tenant-123"
        assert summary.total_users == 100
        assert summary.mfa_coverage_percentage == 80.0


class TestGraphClientMFA:
    """Test suite for GraphClient MFA methods."""

    @pytest.fixture
    def mock_graph_client(self):
        """Create a GraphClient with mocked credentials."""
        with patch.object(GraphClient, "_get_token") as mock_token:
            mock_token.return_value = "mock-token"
            client = GraphClient("test-tenant-id")
            return client

    @pytest.fixture
    def sample_auth_methods(self):
        """Sample authentication methods from Graph API."""
        return [
            {
                "@odata.type": "#microsoft.graph.phoneAuthenticationMethod",
                "id": "phone-1",
                "phoneNumber": "+1234567890",
                "phoneType": "mobile",
                "isDefault": True,
                "isEnabled": True,
            },
            {
                "@odata.type": "#microsoft.graph.microsoftAuthenticatorAuthenticationMethod",
                "id": "auth-1",
                "displayName": "Authenticator App",
                "authenticatorAppId": "app-123",
                "isDefault": False,
                "isEnabled": True,
            },
        ]

    @pytest.fixture
    def sample_user_data(self):
        """Sample user data from Graph API."""
        return {
            "id": "user-123",
            "displayName": "Test User",
            "userPrincipalName": "test@example.com",
            "signInActivity": {
                "lastSignInDateTime": "2024-01-15T10:30:00Z",
            },
        }

    @pytest.mark.asyncio
    async def test_get_user_auth_methods_success(self, mock_graph_client, sample_auth_methods):
        """Test successful retrieval of user authentication methods."""
        with patch.object(mock_graph_client, "_request") as mock_request:
            mock_request.return_value = {"value": sample_auth_methods}

            result = await mock_graph_client.get_user_auth_methods("user-123")

            assert len(result) == 2
            assert result[0]["@odata.type"] == "#microsoft.graph.phoneAuthenticationMethod"
            mock_request.assert_called_once_with("GET", "/users/user-123/authentication/methods")

    @pytest.mark.asyncio
    async def test_get_user_auth_methods_empty(self, mock_graph_client):
        """Test retrieval with no authentication methods."""
        with patch.object(mock_graph_client, "_request") as mock_request:
            mock_request.return_value = {"value": []}

            result = await mock_graph_client.get_user_auth_methods("user-123")

            assert result == []

    @pytest.mark.asyncio
    async def test_get_user_auth_methods_error(self, mock_graph_client):
        """Test error handling in auth methods retrieval."""
        with patch.object(mock_graph_client, "_request") as mock_request:
            mock_request.side_effect = Exception("API Error")

            with pytest.raises(MFAError) as exc_info:
                await mock_graph_client.get_user_auth_methods("user-123")

            assert "user-123" in str(exc_info.value.user_id)
            assert "Failed to get auth methods" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_user_mfa_details_success(
        self, mock_graph_client, sample_auth_methods, sample_user_data
    ):
        """Test successful retrieval of user MFA details."""
        with patch.object(mock_graph_client, "_request") as mock_request:
            # First call returns user data, second returns auth methods
            mock_request.side_effect = [
                sample_user_data,
                {"value": sample_auth_methods},
            ]

            result = await mock_graph_client.get_user_mfa_details("user-123")

            assert result is not None
            assert result.user_id == "user-123"
            assert result.user_principal_name == "test@example.com"
            assert result.is_mfa_registered is True
            assert len(result.auth_methods) == 2
            assert "phone" in result.methods_registered
            assert "microsoftAuthenticator" in result.methods_registered

    @pytest.mark.asyncio
    async def test_get_user_mfa_details_no_user(self, mock_graph_client):
        """Test MFA details when user not found."""
        with patch.object(mock_graph_client, "_request") as mock_request:
            mock_request.return_value = None

            result = await mock_graph_client.get_user_mfa_details("user-123")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_user_mfa_details_various_methods(self, mock_graph_client, sample_user_data):
        """Test MFA details with various authentication method types."""
        auth_methods = [
            {
                "@odata.type": "#microsoft.graph.emailAuthenticationMethod",
                "id": "email-1",
                "emailAddress": "backup@example.com",
                "isDefault": False,
                "isEnabled": True,
            },
            {
                "@odata.type": "#microsoft.graph.fido2AuthenticationMethod",
                "id": "fido-1",
                "model": "YubiKey 5",
                "isDefault": False,
                "isEnabled": True,
            },
            {
                "@odata.type": "#microsoft.graph.windowsHelloForBusinessAuthenticationMethod",
                "id": "hello-1",
                "displayName": "Windows Hello",
                "isDefault": False,
                "isEnabled": True,
            },
            {
                "@odata.type": "#microsoft.graph.softwareOathAuthenticationMethod",
                "id": "oath-1",
                "displayName": "Hardware Token",
                "isDefault": False,
                "isEnabled": True,
            },
            {
                "@odata.type": "#microsoft.graph.temporaryAccessPassAuthenticationMethod",
                "id": "tap-1",
                "isDefault": False,
                "isEnabled": True,
            },
        ]

        with patch.object(mock_graph_client, "_request") as mock_request:
            mock_request.side_effect = [
                sample_user_data,
                {"value": auth_methods},
            ]

            result = await mock_graph_client.get_user_mfa_details("user-123")

            assert result is not None
            assert len(result.auth_methods) == 5
            assert "email" in result.methods_registered
            assert "fido2" in result.methods_registered
            assert "windowsHello" in result.methods_registered
            assert "softwareOath" in result.methods_registered
            assert "temporaryAccessPass" in result.methods_registered

    @pytest.mark.asyncio
    async def test_get_mfa_registration_details(self, mock_graph_client):
        """Test retrieval of MFA registration details."""
        registrations = [
            {
                "userPrincipalName": "user1@example.com",
                "isMfaRegistered": True,
                "methodsRegistered": ["microsoftAuthenticator"],
            },
            {
                "userPrincipalName": "user2@example.com",
                "isMfaRegistered": False,
                "methodsRegistered": [],
            },
        ]

        with patch.object(mock_graph_client, "_request") as mock_request:
            mock_request.return_value = {"value": registrations}

            result = await mock_graph_client.get_mfa_registration_details()

            assert len(result) == 2
            assert result[0]["isMfaRegistered"] is True
            assert result[1]["isMfaRegistered"] is False

    @pytest.mark.asyncio
    async def test_get_mfa_registration_details_with_filter(self, mock_graph_client):
        """Test retrieval with filter parameter."""
        with patch.object(mock_graph_client, "_request") as mock_request:
            mock_request.return_value = {"value": []}

            await mock_graph_client.get_mfa_registration_details(
                filter_param="isMfaRegistered eq false"
            )

            call_args = mock_request.call_args
            params = call_args[0][2]  # 3rd positional arg (method, endpoint, params)
            assert params["$filter"] == "isMfaRegistered eq false"

    @pytest.mark.asyncio
    async def test_get_mfa_registration_details_paginated(self, mock_graph_client):
        """Test paginated retrieval of MFA registration details."""
        page1 = {
            "value": [
                {"userPrincipalName": "user1@example.com", "isMfaRegistered": True},
            ],
            "@odata.nextLink": "https://graph.microsoft.com/v1.0/reports/credentialUserRegistrationDetails?$skip=1",
        }
        page2 = {
            "value": [
                {"userPrincipalName": "user2@example.com", "isMfaRegistered": False},
            ],
            "@odata.nextLink": None,
        }

        with patch.object(mock_graph_client, "_request") as mock_request:
            mock_request.side_effect = [page1, page2]

            result = await mock_graph_client.get_mfa_registration_details_paginated(batch_size=1)

            assert len(result) == 2
            assert result[0]["userPrincipalName"] == "user1@example.com"
            assert result[1]["userPrincipalName"] == "user2@example.com"

    @pytest.mark.asyncio
    async def test_get_mfa_registration_details_paginated_single_page(self, mock_graph_client):
        """Test paginated retrieval with single page result."""
        data = {
            "value": [
                {"userPrincipalName": "user1@example.com", "isMfaRegistered": True},
            ],
            "@odata.nextLink": None,
        }

        with patch.object(mock_graph_client, "_request") as mock_request:
            mock_request.return_value = data

            result = await mock_graph_client.get_mfa_registration_details_paginated()

            assert len(result) == 1
            assert mock_request.call_count == 1

    @pytest.mark.asyncio
    async def test_get_tenant_mfa_summary(self, mock_graph_client):
        """Test retrieval of tenant MFA summary."""
        users = [
            {"id": "user-1", "userPrincipalName": "user1@example.com", "displayName": "User 1"},
            {"id": "user-2", "userPrincipalName": "user2@example.com", "displayName": "User 2"},
            {"id": "user-3", "userPrincipalName": "user3@example.com", "displayName": "User 3"},
        ]

        directory_roles = [
            {
                "roleTemplateId": "62e90394-69f5-4237-9190-012177145e10",  # Global Admin
                "members": [{"id": "user-1", "userPrincipalName": "user1@example.com"}],
            },
        ]

        registrations = [
            {
                "userPrincipalName": "user1@example.com",
                "isMfaRegistered": True,
                "methodsRegistered": ["phone"],
            },
            {
                "userPrincipalName": "user2@example.com",
                "isMfaRegistered": True,
                "methodsRegistered": ["app"],
            },
            {
                "userPrincipalName": "user3@example.com",
                "isMfaRegistered": False,
                "methodsRegistered": [],
            },
        ]

        with (
            patch.object(mock_graph_client, "_get_token", return_value="mock-token"),
            patch.object(mock_graph_client, "get_users") as mock_get_users,
            patch.object(mock_graph_client, "get_directory_roles") as mock_get_roles,
            patch.object(
                mock_graph_client, "get_mfa_registration_details_paginated"
            ) as mock_get_mfa,
        ):
            mock_get_users.return_value = users
            mock_get_roles.return_value = directory_roles
            mock_get_mfa.return_value = registrations

            result = await mock_graph_client.get_tenant_mfa_summary(include_details=True)

            assert isinstance(result, TenantMFASummary)
            assert result.tenant_id == "test-tenant-id"
            assert result.total_users == 3
            assert result.mfa_registered_users == 2
            assert result.mfa_coverage_percentage == pytest.approx(66.67, 0.01)
            assert result.admin_accounts_total == 1
            assert result.admin_accounts_mfa == 1
            assert result.admin_mfa_percentage == 100.0
            assert "phone" in result.method_breakdown
            assert "app" in result.method_breakdown
            assert len(result.users_without_mfa) == 1

    @pytest.mark.asyncio
    async def test_get_tenant_mfa_summary_empty_tenant(self, mock_graph_client):
        """Test MFA summary for empty tenant."""
        with (
            patch.object(mock_graph_client, "_get_token", return_value="mock-token"),
            patch.object(mock_graph_client, "get_users") as mock_get_users,
            patch.object(mock_graph_client, "get_directory_roles") as mock_get_roles,
            patch.object(
                mock_graph_client, "get_mfa_registration_details_paginated"
            ) as mock_get_mfa,
        ):
            mock_get_users.return_value = []
            mock_get_roles.return_value = []
            mock_get_mfa.return_value = []

            result = await mock_graph_client.get_tenant_mfa_summary()

            assert result.total_users == 0
            assert result.mfa_coverage_percentage == 0.0
            assert result.method_breakdown == {}

    @pytest.mark.asyncio
    async def test_get_users_paginated(self, mock_graph_client):
        """Test paginated user retrieval."""
        page1 = {
            "value": [
                {"id": "user-1", "displayName": "User 1"},
            ],
            "@odata.nextLink": "https://graph.microsoft.com/v1.0/users?$skip=1",
        }
        page2 = {
            "value": [
                {"id": "user-2", "displayName": "User 2"},
            ],
            "@odata.nextLink": None,
        }

        with patch.object(mock_graph_client, "_request") as mock_request:
            mock_request.side_effect = [page1, page2]

            result = await mock_graph_client.get_users_paginated(batch_size=1)

            assert len(result) == 2
            assert result[0]["id"] == "user-1"
            assert result[1]["id"] == "user-2"

    @pytest.mark.asyncio
    async def test_get_users_paginated_with_filter(self, mock_graph_client):
        """Test paginated users with filter."""
        with patch.object(mock_graph_client, "_request") as mock_request:
            mock_request.return_value = {"value": [], "@odata.nextLink": None}

            await mock_graph_client.get_users_paginated(
                batch_size=100,
                filter_param="userType eq 'Member'",
            )

            call_args = mock_request.call_args
            params = call_args[0][2]  # 3rd positional arg (method, endpoint, params)
            assert params["$filter"] == "userType eq 'Member'"

    @pytest.mark.asyncio
    async def test_get_conditional_access_policies_with_details(self, mock_graph_client):
        """Test retrieval of conditional access policies with details."""
        policies = [
            {
                "id": "policy-1",
                "displayName": "Require MFA",
                "grantControls": {"builtInControls": ["mfa"]},
            },
        ]

        with patch.object(mock_graph_client, "_request") as mock_request:
            mock_request.return_value = {"value": policies}

            result = await mock_graph_client.get_conditional_access_policies_with_details()

            assert len(result) == 1
            assert result[0]["displayName"] == "Require MFA"

    @pytest.mark.asyncio
    async def test_get_sign_in_logs(self, mock_graph_client):
        """Test retrieval of sign-in logs."""
        logs = [
            {"id": "log-1", "userPrincipalName": "user1@example.com"},
        ]

        with patch.object(mock_graph_client, "_request") as mock_request:
            mock_request.return_value = {"value": logs}

            result = await mock_graph_client.get_sign_in_logs(top=50)

            assert len(result) == 1
            call_args = mock_request.call_args
            params = call_args[0][2]  # 3rd positional arg (method, endpoint, params)
            assert params["$top"] == 50

    @pytest.mark.asyncio
    async def test_get_sign_in_logs_with_filter(self, mock_graph_client):
        """Test sign-in logs with filter."""
        with patch.object(mock_graph_client, "_request") as mock_request:
            mock_request.return_value = {"value": []}

            await mock_graph_client.get_sign_in_logs(
                filter_param="userPrincipalName eq 'user1@example.com'",
                top=10,
            )

            call_args = mock_request.call_args
            params = call_args[0][2]  # 3rd positional arg (method, endpoint, params)
            assert params["$filter"] == "userPrincipalName eq 'user1@example.com'"


class TestMFAError:
    """Test suite for MFAError exception."""

    def test_mfa_error_with_user_id(self):
        """Test MFAError with user ID."""
        error = MFAError("Test error", "user-123")
        assert str(error) == "Test error"
        assert error.user_id == "user-123"

    def test_mfa_error_without_user_id(self):
        """Test MFAError without user ID."""
        error = MFAError("Test error")
        assert str(error) == "Test error"
        assert error.user_id is None


class TestAdminRoleTemplateIds:
    """Test suite for admin role template IDs."""

    def test_admin_role_template_ids_exist(self):
        """Test that admin role template IDs are defined."""
        assert len(ADMIN_ROLE_TEMPLATE_IDS) > 0
        # Verify some known admin roles are present
        assert "62e90394-69f5-4237-9190-012177145e10" in ADMIN_ROLE_TEMPLATE_IDS  # Global Admin
        assert "194ae4cb-b126-40b2-bd5b-6091b380977d" in ADMIN_ROLE_TEMPLATE_IDS  # Security Admin

    def test_all_ids_are_strings(self):
        """Test that all role template IDs are strings."""
        for role_id in ADMIN_ROLE_TEMPLATE_IDS:
            assert isinstance(role_id, str)
            assert len(role_id) == 36  # UUID format

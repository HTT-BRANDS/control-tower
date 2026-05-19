"""Unit tests for the Microsoft Graph API client.

Tests the GraphClient class, dataclass models, and API methods
in app/api/services/graph_client.py with mocked HTTP calls.

Traces: IG-001, IG-002, IG-003, IG-005, IG-006, IG-007, IG-008
"""

from dataclasses import fields
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.api.services.graph_client import (
    GRAPH_API_BASE,
    GRAPH_BETA_API_BASE,
    GRAPH_SCOPES,
    AdminRoleSummary,
    DirectoryRole,
    GraphClient,
    MFAError,
    MFAMethodDetails,
    PrivilegedAccessAssignment,
    RoleAssignment,
    TenantMFASummary,
    UserMFAStatus,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestGraphConstants:
    """Tests for module-level constants."""

    def test_graph_api_base(self):
        assert GRAPH_API_BASE == "https://graph.microsoft.com/v1.0"

    def test_graph_beta_api_base(self):
        assert GRAPH_BETA_API_BASE == "https://graph.microsoft.com/beta"

    def test_graph_scopes(self):
        assert "https://graph.microsoft.com/.default" in GRAPH_SCOPES


# ---------------------------------------------------------------------------
# Dataclass Models
# ---------------------------------------------------------------------------


class TestMFAMethodDetails:
    """Tests for MFAMethodDetails dataclass."""

    def test_creation(self):
        detail = MFAMethodDetails(
            method_type="microsoftAuthenticator",
            is_default=True,
            is_enabled=True,
        )
        assert detail.method_type == "microsoftAuthenticator"
        assert detail.is_default is True
        assert detail.is_enabled is True

    def test_optional_fields_default_none(self):
        detail = MFAMethodDetails(
            method_type="phone",
            is_default=False,
            is_enabled=True,
        )
        assert detail.phone_number is None
        assert detail.email_address is None
        assert detail.display_name is None
        assert detail.app_id is None


class TestUserMFAStatus:
    """Tests for UserMFAStatus dataclass."""

    def test_creation(self):
        status = UserMFAStatus(
            user_id="u-001",
            user_principal_name="user@example.com",
            display_name="Test User",
            is_mfa_registered=True,
            methods_registered=["microsoftAuthenticator"],
            auth_methods=[],
            default_method="microsoftAuthenticator",
            last_updated="2024-01-01T00:00:00Z",
        )
        assert status.user_id == "u-001"
        assert status.is_mfa_registered is True
        assert len(status.methods_registered) == 1

    def test_no_mfa_user(self):
        status = UserMFAStatus(
            user_id="u-002",
            user_principal_name="nope@example.com",
            display_name="No MFA User",
            is_mfa_registered=False,
            methods_registered=[],
            auth_methods=[],
            default_method=None,
            last_updated=None,
        )
        assert status.is_mfa_registered is False
        assert status.default_method is None


class TestTenantMFASummary:
    """Tests for TenantMFASummary dataclass."""

    def test_creation(self):
        summary = TenantMFASummary(
            tenant_id="t-001",
            total_users=100,
            mfa_registered_users=80,
            mfa_coverage_percentage=80.0,
            admin_accounts_total=10,
            admin_accounts_mfa=10,
            admin_mfa_percentage=100.0,
            method_breakdown={"microsoftAuthenticator": 60, "sms": 20},
            users_without_mfa=[],
        )
        assert summary.mfa_coverage_percentage == 80.0
        assert summary.admin_mfa_percentage == 100.0

    def test_field_count(self):
        assert len(fields(TenantMFASummary)) == 9


class TestDirectoryRole:
    """Tests for DirectoryRole dataclass."""

    def test_creation(self):
        role = DirectoryRole(
            role_id="r-001",
            display_name="Global Administrator",
            description="Can manage all aspects",
            role_template_id="rt-001",
            is_built_in=True,
        )
        assert role.display_name == "Global Administrator"
        assert role.is_built_in is True


class TestRoleAssignment:
    """Tests for RoleAssignment dataclass."""

    def test_creation(self):
        ra = RoleAssignment(
            assignment_id="a-001",
            principal_id="p-001",
            principal_type="User",
            principal_display_name="admin@example.com",
            role_definition_id="rd-001",
            role_name="Global Administrator",
            role_template_id="rt-001",
            scope_type="Directory",
            scope_id=None,
            created_date_time="2024-01-01T00:00:00Z",
            assignment_type="Direct",
        )
        assert ra.principal_type == "User"
        assert ra.assignment_type == "Direct"

    def test_field_count(self):
        assert len(fields(RoleAssignment)) == 11


class TestPrivilegedAccessAssignment:
    """Tests for PrivilegedAccessAssignment dataclass."""

    def test_creation(self):
        paa = PrivilegedAccessAssignment(
            assignment_id="pim-001",
            principal_id="p-001",
            principal_type="User",
            principal_display_name="admin@example.com",
            role_definition_id="rd-001",
            role_name="Security Admin",
            assignment_state="eligible",
            start_date_time="2024-01-01T00:00:00Z",
            end_date_time="2025-01-01T00:00:00Z",
            duration="365 days",
        )
        assert paa.assignment_state == "eligible"
        assert paa.duration == "365 days"


class TestAdminRoleSummary:
    """Tests for AdminRoleSummary dataclass."""

    def test_creation(self):
        summary = AdminRoleSummary(
            tenant_id="t-001",
            total_roles=5,
            total_assignments=10,
            privileged_users=[],
            privileged_service_principals=[],
            pim_assignments=[],
            roles_without_members=["Exchange Admin"],
            global_admin_count=2,
            security_admin_count=3,
            privileged_role_admin_count=1,
            other_admin_count=4,
        )
        assert summary.global_admin_count == 2
        assert summary.total_assignments == 10

    def test_field_count(self):
        assert len(fields(AdminRoleSummary)) == 11


# ---------------------------------------------------------------------------
# MFAError
# ---------------------------------------------------------------------------


class TestMFAError:
    """Tests for MFAError exception."""

    def test_creation_with_user_id(self):
        err = MFAError("Failed to fetch MFA", user_id="u-001")
        assert str(err) == "Failed to fetch MFA"
        assert err.user_id == "u-001"

    def test_creation_without_user_id(self):
        err = MFAError("General error")
        assert err.user_id is None

    def test_is_exception(self):
        assert issubclass(MFAError, Exception)


# ---------------------------------------------------------------------------
# GraphClient Initialization
# ---------------------------------------------------------------------------


class TestGraphClientInit:
    """Tests for GraphClient constructor."""

    def test_init(self):
        client = GraphClient(tenant_id="t-001")
        assert client.tenant_id == "t-001"
        assert client._token is None
        assert client._credential is None


# ---------------------------------------------------------------------------
# GraphClient._get_credential
# ---------------------------------------------------------------------------


class TestGraphClientCredential:
    """Tests for GraphClient credential resolution."""

    def test_credential_is_lazy(self):
        """Credential should not be created in __init__."""
        client = GraphClient(tenant_id="t-001")
        assert client._credential is None

    @patch("app.api.services.graph_client._base.ClientSecretCredential")
    def test_get_credential_creates_once(self, mock_csc):
        """Should create credential once and cache it."""
        # AzureClientManager is imported lazily inside _get_credential
        with patch("app.api.services.azure_client.AzureClientManager") as mock_mgr_cls:
            mock_mgr_cls.return_value._resolve_credentials.return_value = (
                "client-id",
                "client-secret",
                "tenant-id",
            )

            client = GraphClient(tenant_id="t-001")
            cred1 = client._get_credential()
            cred2 = client._get_credential()

            # Created only once
            mock_csc.assert_called_once()
            assert cred1 is cred2

    def test_get_credential_delegates_uami_to_azure_client_manager(self, monkeypatch):
        """UAMI Graph auth must not fall back to legacy client-secret resolution."""
        from app.api.services.graph_client import _base

        monkeypatch.setattr(_base.settings, "use_uami_auth", True)
        monkeypatch.setattr(_base.settings, "use_oidc_federation", False)

        mock_credential = MagicMock()
        with patch("app.api.services.azure_client.azure_client_manager") as mock_manager:
            mock_manager.get_credential.return_value = mock_credential

            client = GraphClient(tenant_id="t-001")
            assert client._get_credential() is mock_credential
            assert client._get_credential() is mock_credential

        mock_manager.get_credential.assert_called_once_with("t-001")


# ---------------------------------------------------------------------------
# GraphClient._get_token
# ---------------------------------------------------------------------------


class TestGraphClientToken:
    """Tests for GraphClient token acquisition."""

    @pytest.mark.asyncio
    async def test_get_token_returns_string(self):
        """Should return a token string."""
        client = GraphClient(tenant_id="t-001")
        mock_cred = MagicMock()
        mock_token = MagicMock()
        mock_token.token = "eyJ.test.token"
        mock_cred.get_token.return_value = mock_token
        client._credential = mock_cred

        token = await client._get_token()
        assert token == "eyJ.test.token"


# ---------------------------------------------------------------------------
# GraphClient._request
# ---------------------------------------------------------------------------


class TestGraphClientRequest:
    """Tests for GraphClient._request method."""

    @pytest.mark.asyncio
    async def test_request_sets_auth_header(self):
        """Should set Authorization bearer header."""
        client = GraphClient(tenant_id="t-001")
        client._get_token = AsyncMock(return_value="test-token")

        mock_response = MagicMock()
        mock_response.json.return_value = {"value": []}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_httpx:
            mock_ctx = AsyncMock()
            mock_ctx.request.return_value = mock_response
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client._request("GET", "/users")

            # Verify auth header was set
            call_kwargs = mock_ctx.request.call_args
            assert call_kwargs.kwargs["headers"]["Authorization"] == "Bearer test-token"
            assert result == {"value": []}


# ---------------------------------------------------------------------------
# GraphClient.get_users
# ---------------------------------------------------------------------------


class TestGraphClientGetUsers:
    """Tests for GraphClient.get_users method."""

    @pytest.mark.asyncio
    async def test_returns_user_list(self):
        """Should return list of user dicts."""
        client = GraphClient(tenant_id="t-001")
        client._request = AsyncMock(
            return_value={
                "value": [
                    {"id": "u1", "displayName": "User 1"},
                    {"id": "u2", "displayName": "User 2"},
                ]
            }
        )

        users = await client.get_users()
        assert len(users) == 2
        assert users[0]["id"] == "u1"

    @pytest.mark.asyncio
    async def test_handles_pagination(self):
        """Should follow @odata.nextLink for pagination."""
        client = GraphClient(tenant_id="t-001")
        client._request = AsyncMock(
            side_effect=[
                {
                    "value": [{"id": "u1"}],
                    "@odata.nextLink": f"{GRAPH_API_BASE}/users?skip=1",
                },
                {
                    "value": [{"id": "u2"}],
                },
            ]
        )

        users = await client.get_users()
        assert len(users) == 2

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_403(self):
        """Should retry without signInActivity on 403."""
        client = GraphClient(tenant_id="t-001")

        mock_403 = MagicMock()
        mock_403.status_code = 403

        call_count = 0

        async def mock_request(method, endpoint, params=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.HTTPStatusError("Forbidden", request=MagicMock(), response=mock_403)
            return {"value": [{"id": "u1"}]}

        client._request = mock_request
        users = await client.get_users()
        assert len(users) == 1
        assert call_count == 2


# ---------------------------------------------------------------------------
# GraphClient.get_directory_roles
# ---------------------------------------------------------------------------


class TestGraphClientGetDirectoryRoles:
    """Tests for GraphClient.get_directory_roles method."""

    @pytest.mark.asyncio
    async def test_returns_roles(self):
        """Should return list of role dicts."""
        client = GraphClient(tenant_id="t-001")
        client._request = AsyncMock(
            return_value={
                "value": [
                    {"id": "r1", "displayName": "Global Administrator"},
                    {"id": "r2", "displayName": "Security Reader"},
                ]
            }
        )

        roles = await client.get_directory_roles()
        assert len(roles) == 2
        assert roles[0]["displayName"] == "Global Administrator"

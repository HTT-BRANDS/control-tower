"""Unit tests for Azure preflight checks.

Tests the check classes and helper functions in
app/preflight/azure_checks.py.

Traces: PF-003, PF-004 — Azure authentication, subscription,
Graph API, cost management, policy, resources, security, and RBAC checks.
"""

from unittest.mock import patch

import pytest

from app.preflight.azure.azure_checks import (
    REQUIRED_AZURE_ROLES,
    REQUIRED_GRAPH_PERMISSIONS,
    AzureAuthCheck,
    AzureCheckError,
    AzureCostManagementCheck,
    AzureGraphCheck,
    AzurePolicyCheck,
    AzureRBACCheck,
    AzureResourcesCheck,
    AzureSecurityCheck,
    AzureSubscriptionsCheck,
    _parse_aad_error,
    _sanitize_error,
)
from app.preflight.azure.base import (
    AZURE_MANAGEMENT_SCOPE,
    GRAPH_API_BASE,
)
from app.preflight.models import CheckCategory, CheckStatus

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestAzureConstants:
    """Tests for Azure check constants."""

    def test_management_scope(self):
        assert "management.azure.com" in AZURE_MANAGEMENT_SCOPE

    def test_graph_api_base(self):
        assert GRAPH_API_BASE == "https://graph.microsoft.com/v1.0"

    def test_required_graph_permissions(self):
        assert "User.Read.All" in REQUIRED_GRAPH_PERMISSIONS
        assert "Directory.Read.All" in REQUIRED_GRAPH_PERMISSIONS
        assert len(REQUIRED_GRAPH_PERMISSIONS) >= 5

    def test_required_azure_roles(self):
        assert "Reader" in REQUIRED_AZURE_ROLES
        assert "Security Reader" in REQUIRED_AZURE_ROLES


# ---------------------------------------------------------------------------
# AzureCheckError
# ---------------------------------------------------------------------------


class TestAzureCheckError:
    """Tests for AzureCheckError exception."""

    def test_creation(self):
        err = AzureCheckError("test error", "ERR001")
        assert str(err) == "test error"
        assert err.error_code == "ERR001"
        assert err.details == {}

    def test_with_details(self):
        err = AzureCheckError("test", "ERR002", details={"key": "val"})
        assert err.details["key"] == "val"


# ---------------------------------------------------------------------------
# _sanitize_error
# ---------------------------------------------------------------------------


class TestSanitizeError:
    """Tests for _sanitize_error helper."""

    def test_normal_error(self):
        result = _sanitize_error(ValueError("some error"))
        assert result["error_type"] == "ValueError"
        assert result["safe_to_display"] is True

    def test_redacts_client_secret(self):
        result = _sanitize_error(Exception("client_secret=abc123"))
        assert "REDACTED" in result["error_message"]
        assert "abc123" not in result["error_message"]

    def test_redacts_token(self):
        result = _sanitize_error(Exception("Bearer token: eyJ..."))
        assert "REDACTED" in result["error_message"]

    def test_redacts_password(self):
        result = _sanitize_error(Exception("password=myPass123"))
        assert "REDACTED" in result["error_message"]


# ---------------------------------------------------------------------------
# _parse_aad_error
# ---------------------------------------------------------------------------


class TestParseAADError:
    """Tests for _parse_aad_error helper."""

    def test_invalid_client_secret(self):
        code, recs = _parse_aad_error("AADSTS7000215: Invalid client secret")
        assert code == "invalid_client_secret"
        assert len(recs) > 0

    def test_application_not_found(self):
        code, recs = _parse_aad_error("AADSTS700016: Application not found")
        assert code == "application_not_found"
        assert len(recs) > 0

    def test_unknown_error(self):
        code, recs = _parse_aad_error("Something unexpected happened")
        assert code  # Should still return some code
        assert isinstance(recs, list)


# ---------------------------------------------------------------------------
# Check Class Initialization
# ---------------------------------------------------------------------------


class TestCheckClassInitialization:
    """Tests for Azure check class constructors."""

    def test_auth_check_init(self):
        check = AzureAuthCheck()
        assert check.check_id == "azure_authentication"
        assert check.name == "Azure AD Authentication"
        assert check.category == CheckCategory.AZURE_AUTH
        assert check.timeout_seconds == 30.0

    def test_subscriptions_check_init(self):
        check = AzureSubscriptionsCheck()
        assert check.check_id == "azure_subscriptions"
        assert check.category == CheckCategory.AZURE_SUBSCRIPTIONS

    def test_graph_check_init(self):
        check = AzureGraphCheck()
        assert check.check_id == "azure_graph_api"
        assert check.category == CheckCategory.AZURE_GRAPH

    def test_cost_management_check_init(self):
        check = AzureCostManagementCheck()
        assert check.check_id == "azure_cost_management"
        assert check.category == CheckCategory.AZURE_COST_MANAGEMENT
        assert check._subscription_id is None

    def test_cost_management_with_subscription(self):
        check = AzureCostManagementCheck(subscription_id="sub-123")
        assert check._subscription_id == "sub-123"

    def test_policy_check_init(self):
        check = AzurePolicyCheck()
        assert check.check_id == "azure_policy"
        assert check.category == CheckCategory.AZURE_POLICY

    def test_resources_check_init(self):
        check = AzureResourcesCheck()
        assert check.check_id == "azure_resource_manager"
        assert check.category == CheckCategory.AZURE_RESOURCES

    def test_security_check_init(self):
        check = AzureSecurityCheck()
        assert check.check_id == "azure_security_center"
        assert check.category == CheckCategory.AZURE_SECURITY

    def test_rbac_check_init(self):
        check = AzureRBACCheck()
        assert check.check_id == "azure_rbac_permissions"
        assert check.category == CheckCategory.AZURE_SECURITY

    def test_rbac_check_with_subscription(self):
        check = AzureRBACCheck(subscription_id="sub-456")
        assert check._subscription_id == "sub-456"


# ---------------------------------------------------------------------------
# Check Execution — No Tenant ID Cases
# ---------------------------------------------------------------------------


class TestCheckNoTenantID:
    """Tests for checks that fail when no tenant_id is available."""

    @pytest.mark.asyncio
    @patch("app.preflight.azure_checks.settings")
    async def test_auth_check_no_tenant_fails(self, mock_settings):
        mock_settings.azure_tenant_id = None
        check = AzureAuthCheck()
        result = await check._execute_check(tenant_id=None)
        assert result.status == CheckStatus.FAIL
        assert "No tenant ID" in result.message

    @pytest.mark.asyncio
    @patch("app.preflight.azure_checks.settings")
    async def test_subscriptions_check_no_tenant_fails(self, mock_settings):
        mock_settings.azure_tenant_id = None
        check = AzureSubscriptionsCheck()
        result = await check._execute_check(tenant_id=None)
        assert result.status == CheckStatus.FAIL
        assert "No tenant ID" in result.message

    @pytest.mark.asyncio
    @patch("app.preflight.azure_checks.settings")
    async def test_graph_check_no_tenant_fails(self, mock_settings):
        mock_settings.azure_tenant_id = None
        check = AzureGraphCheck()
        result = await check._execute_check(tenant_id=None)
        assert result.status == CheckStatus.FAIL
        assert "No tenant ID" in result.message


# ---------------------------------------------------------------------------
# Check __repr__
# ---------------------------------------------------------------------------


class TestCheckRepr:
    """Tests for check __repr__ methods."""

    def test_auth_check_repr(self):
        check = AzureAuthCheck()
        r = repr(check)
        assert "AzureAuthCheck" in r
        assert "azure_authentication" in r

    def test_graph_check_repr(self):
        check = AzureGraphCheck()
        r = repr(check)
        assert "AzureGraphCheck" in r

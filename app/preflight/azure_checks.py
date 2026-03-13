"""Azure-specific preflight checks for governance platform.

This module provides comprehensive validation of Azure tenant connectivity,
API access, and required permissions. Each check function is designed to
be self-contained, async-friendly, and provide actionable error messages.

Two API styles are provided:
1. **Class-based checks** - For integration with PreflightRunner
2. **Function-based checks** - Direct async functions for specific use cases

Example:
    >>> # Using function-based API
    >>> from app.preflight.azure_checks import run_all_azure_checks
    >>> results = await run_all_azure_checks("12345678-1234-1234-1234-123456789012")
    >>>
    >>> # Using class-based API
    >>> from app.preflight.azure_checks import AzureAuthCheck
    >>> check = AzureAuthCheck()
    >>> result = await check.run(tenant_id="12345678-1234-1234-1234-123456789012")
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import httpx

from app.api.services.azure_client import azure_client_manager
from app.core.config import get_settings
from app.preflight.base import BasePreflightCheck
from app.preflight.models import CheckCategory, CheckResult, CheckStatus

logger = logging.getLogger(__name__)
settings = get_settings()

# Azure Management API scope
AZURE_MANAGEMENT_SCOPE = "https://management.azure.com/.default"
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPES = ["https://graph.microsoft.com/.default"]

# Required Microsoft Graph API permissions
REQUIRED_GRAPH_PERMISSIONS = [
    "User.Read.All",
    "Group.Read.All",
    "Directory.Read.All",
    "RoleManagement.Read.All",
    "Policy.Read.All",
    "AuditLog.Read.All",
    "Reports.Read.All",
]

# Required Azure RBAC roles per subscription
REQUIRED_AZURE_ROLES = [
    "Reader",
    "Cost Management Reader",
    "Security Reader",
]


class AzureCheckError(Exception):
    """Base exception for Azure preflight check errors."""

    def __init__(self, message: str, error_code: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}


def _sanitize_error(error: Exception) -> dict[str, Any]:
    """Sanitize error details to remove any sensitive information.

    Args:
        error: The exception to sanitize

    Returns:
        Dictionary with safe error information (no secrets, tokens, etc.)
    """
    error_str = str(error)

    # Remove any potential secrets from error messages
    sanitized = error_str
    for pattern in ["client_secret", "password", "token", "key", "credential"]:
        # Simple sanitization - in production, use more sophisticated patterns
        if pattern.lower() in sanitized.lower():
            sanitized = f"[REDACTED - {pattern} removed from error]"

    return {
        "error_type": type(error).__name__,
        "error_message": sanitized,
        "safe_to_display": True,
    }


def _parse_aad_error(error_message: str) -> tuple[str, list[str]]:
    """Parse Azure AD error codes and provide recommendations.

    Args:
        error_message: The error message from Azure AD

    Returns:
        Tuple of (error_code, recommendations)
    """
    recommendations: list[str] = []

    if "AADSTS7000215" in error_message:
        error_code = "invalid_client_secret"
        recommendations = [
            "The client secret is invalid or expired",
            "Navigate to Azure Portal > App Registrations > Your App > Certificates & Secrets",
            "Create a new client secret and update the application configuration",
            "Remember to grant admin consent for API permissions after updating",
        ]
    elif "AADSTS700016" in error_message:
        error_code = "application_not_found"
        recommendations = [
            "The application (client) ID is not found in the tenant",
            "Verify the client_id in your configuration is correct",
            "Ensure the app registration exists in the target tenant",
            "For multi-tenant apps, ensure the app is provisioned in this tenant",
        ]
    elif "AADSTS65001" in error_message:
        error_code = "admin_consent_required"
        recommendations = [
            "Admin consent has not been granted for the required permissions",
            "Navigate to Azure Portal > Enterprise Applications > Your App > Permissions",
            "Click 'Grant admin consent for [Tenant]' for all required permissions",
            "Required permissions: " + ", ".join(REQUIRED_GRAPH_PERMISSIONS[:3]) + "...",
        ]
    elif "AADSTS7000112" in error_message:
        error_code = "invalid_client_id"
        recommendations = [
            "The client ID (application ID) is invalid",
            "Verify the client_id matches your App Registration",
            "Check for typos or copy-paste errors in the client ID",
        ]
    elif "AADSTS900023" in error_message:
        error_code = "invalid_tenant_id"
        recommendations = [
            "The tenant ID is invalid or the tenant was not found",
            "Verify the tenant_id is a valid GUID",
            "Ensure the tenant still exists and is accessible",
        ]
    elif "AuthorizationFailed" in error_message:
        error_code = "authorization_failed"
        recommendations = [
            "The application lacks required RBAC permissions",
            "Navigate to Subscription > Access Control (IAM) > Role Assignments",
            "Add role assignments: Reader, Cost Management Reader, Security Reader",
            "Wait 5-10 minutes for role assignments to propagate",
        ]
    elif "NoSubscriptionsFound" in error_message:
        error_code = "no_subscriptions"
        recommendations = [
            "No subscriptions were found for the authenticated principal",
            "Verify the service principal has access to at least one subscription",
            "Check that subscriptions are not disabled or suspended",
            "Ensure the tenant has active Azure subscriptions",
        ]
    else:
        error_code = "unknown_authentication_error"
        recommendations = [
            "An unexpected authentication error occurred",
            "Verify all credentials (tenant_id, client_id, client_secret) are correct",
            "Check Azure service health dashboard for outages",
            "Review application logs for additional context",
        ]

    return error_code, recommendations


def _get_credential(tenant_id: str) -> Any:
    """Get Azure credential for a tenant.

    Args:
        tenant_id: Azure AD tenant ID

    Returns:
        Configured ClientSecretCredential

    Raises:
        AzureCheckError: If required credentials are not configured
    """
    if not all([settings.azure_client_id, settings.azure_client_secret]):
        raise AzureCheckError(
            message="Azure credentials not configured",
            error_code="credentials_not_configured",
            details={
                "client_id_configured": bool(settings.azure_client_id),
                "client_secret_configured": bool(settings.azure_client_secret),
            },
        )

    return azure_client_manager.get_credential(tenant_id)


def _create_check_result(
    check_id: str,
    name: str,
    category: CheckCategory,
    tenant_id: str | None,
    subscription_id: str | None,
    status: CheckStatus,
    message: str,
    start_time: datetime,
    details: dict[str, Any] | None = None,
    recommendations: list[str] | None = None,
    error_code: str | None = None,
    error: Exception | None = None,
) -> CheckResult:
    """Create a CheckResult with consistent timing and formatting.

    Args:
        check_id: Unique identifier for the check
        name: Human-readable name of the check
        category: Category of the check
        tenant_id: Optional tenant ID
        subscription_id: Optional subscription ID
        status: Check status
        message: Human-readable message
        start_time: When the check started (for duration calculation)
        details: Optional check-specific details
        recommendations: Optional recommendations
        error_code: Optional error code
        error: Optional exception for error details

    Returns:
        Populated CheckResult instance
    """
    duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

    if error:
        _sanitize_error(error)

    return CheckResult(
        check_id=check_id,
        name=name,
        category=category,
        status=status,
        message=message,
        details=details or {},
        duration_ms=duration_ms,
        timestamp=datetime.utcnow(),
        recommendations=recommendations or [],
        tenant_id=tenant_id,
    )


# ============================================================================
# CLASS-BASED CHECK IMPLEMENTATIONS
# ============================================================================


class AzureAuthCheck(BasePreflightCheck):
    """Check Azure AD authentication using ClientSecretCredential."""

    def __init__(self):
        super().__init__(
            check_id="azure_authentication",
            name="Azure AD Authentication",
            category=CheckCategory.AZURE_AUTH,
            description="Verify Azure AD authentication is configured and working",
            timeout_seconds=30.0,
        )

    async def _execute_check(self, tenant_id: str | None = None) -> CheckResult:
        """Execute the authentication check."""
        if not tenant_id:
            tenant_id = settings.azure_tenant_id

        if not tenant_id:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.FAIL,
                message="No tenant ID provided for authentication check",
                recommendations=["Configure AZURE_TENANT_ID environment variable"],
            )

        # Delegate to function-based implementation
        return await check_azure_authentication(tenant_id)


class AzureSubscriptionsCheck(BasePreflightCheck):
    """Check Azure subscription access and listing."""

    def __init__(self):
        super().__init__(
            check_id="azure_subscriptions",
            name="Azure Subscriptions Access",
            category=CheckCategory.AZURE_SUBSCRIPTIONS,
            description="Verify access to list Azure subscriptions",
            timeout_seconds=30.0,
        )

    async def _execute_check(self, tenant_id: str | None = None) -> CheckResult:
        """Execute the subscriptions check."""
        if not tenant_id:
            tenant_id = settings.azure_tenant_id

        if not tenant_id:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.FAIL,
                message="No tenant ID provided for subscriptions check",
                recommendations=["Configure AZURE_TENANT_ID environment variable"],
            )

        return await check_azure_subscriptions(tenant_id)


class AzureGraphCheck(BasePreflightCheck):
    """Check Microsoft Graph API access."""

    def __init__(self):
        super().__init__(
            check_id="azure_graph_api",
            name="Microsoft Graph API Access",
            category=CheckCategory.AZURE_GRAPH,
            description="Verify Microsoft Graph API access and permissions",
            timeout_seconds=30.0,
        )

    async def _execute_check(self, tenant_id: str | None = None) -> CheckResult:
        """Execute the Graph API check."""
        if not tenant_id:
            tenant_id = settings.azure_tenant_id

        if not tenant_id:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.FAIL,
                message="No tenant ID provided for Graph API check",
                recommendations=["Configure AZURE_TENANT_ID environment variable"],
            )

        return await check_graph_api_access(tenant_id)


class AzureCostManagementCheck(BasePreflightCheck):
    """Check Azure Cost Management API access for a subscription."""

    def __init__(self, subscription_id: str | None = None):
        super().__init__(
            check_id="azure_cost_management",
            name="Cost Management API Access",
            category=CheckCategory.AZURE_COST_MANAGEMENT,
            description="Verify Cost Management API access and permissions",
            timeout_seconds=30.0,
        )
        self._subscription_id = subscription_id

    async def _execute_check(self, tenant_id: str | None = None) -> CheckResult:
        """Execute the Cost Management check."""
        if not tenant_id:
            tenant_id = settings.azure_tenant_id

        subscription_id = self._subscription_id

        if not subscription_id:
            # Try to get first subscription
            try:
                subs_result = await check_azure_subscriptions(tenant_id)
                if subs_result.details.get("subscription_count", 0) > 0:
                    subscription_id = subs_result.details["subscriptions"][0]["subscription_id"]
            except Exception as e:
                logger.warning(f"Could not auto-detect subscription: {e}")

        if not subscription_id:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.SKIPPED,
                message="No subscription ID available for Cost Management check",
                recommendations=[
                    "Provide a subscription_id parameter",
                    "Ensure the tenant has accessible subscriptions",
                ],
            )

        return await check_cost_management_access(tenant_id, subscription_id)


class AzurePolicyCheck(BasePreflightCheck):
    """Check Azure Policy Insights API access."""

    def __init__(self, subscription_id: str | None = None):
        super().__init__(
            check_id="azure_policy",
            name="Azure Policy Insights API",
            category=CheckCategory.AZURE_POLICY,
            description="Verify Azure Policy Insights API access",
            timeout_seconds=30.0,
        )
        self._subscription_id = subscription_id

    async def _execute_check(self, tenant_id: str | None = None) -> CheckResult:
        """Execute the Policy check."""
        if not tenant_id:
            tenant_id = settings.azure_tenant_id

        subscription_id = self._subscription_id

        if not subscription_id:
            # Try to get first subscription
            try:
                subs_result = await check_azure_subscriptions(tenant_id)
                if subs_result.details.get("subscription_count", 0) > 0:
                    subscription_id = subs_result.details["subscriptions"][0]["subscription_id"]
            except Exception as e:
                logger.warning(f"Could not auto-detect subscription: {e}")

        if not subscription_id:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.SKIPPED,
                message="No subscription ID available for Policy check",
                recommendations=[
                    "Provide a subscription_id parameter",
                    "Ensure the tenant has accessible subscriptions",
                ],
            )

        return await check_policy_access(tenant_id, subscription_id)


class AzureResourcesCheck(BasePreflightCheck):
    """Check Azure Resource Manager access."""

    def __init__(self, subscription_id: str | None = None):
        super().__init__(
            check_id="azure_resource_manager",
            name="Azure Resource Manager Access",
            category=CheckCategory.AZURE_RESOURCES,
            description="Verify Azure Resource Manager API access",
            timeout_seconds=30.0,
        )
        self._subscription_id = subscription_id

    async def _execute_check(self, tenant_id: str | None = None) -> CheckResult:
        """Execute the Resource Manager check."""
        if not tenant_id:
            tenant_id = settings.azure_tenant_id

        subscription_id = self._subscription_id

        if not subscription_id:
            # Try to get first subscription
            try:
                subs_result = await check_azure_subscriptions(tenant_id)
                if subs_result.details.get("subscription_count", 0) > 0:
                    subscription_id = subs_result.details["subscriptions"][0]["subscription_id"]
            except Exception as e:
                logger.warning(f"Could not auto-detect subscription: {e}")

        if not subscription_id:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.SKIPPED,
                message="No subscription ID available for Resource Manager check",
                recommendations=[
                    "Provide a subscription_id parameter",
                    "Ensure the tenant has accessible subscriptions",
                ],
            )

        return await check_resource_manager_access(tenant_id, subscription_id)


class AzureSecurityCheck(BasePreflightCheck):
    """Check Azure Security Center access."""

    def __init__(self, subscription_id: str | None = None):
        super().__init__(
            check_id="azure_security_center",
            name="Azure Security Center Access",
            category=CheckCategory.AZURE_SECURITY,
            description="Verify Azure Security Center API access",
            timeout_seconds=30.0,
        )
        self._subscription_id = subscription_id

    async def _execute_check(self, tenant_id: str | None = None) -> CheckResult:
        """Execute the Security Center check."""
        if not tenant_id:
            tenant_id = settings.azure_tenant_id

        subscription_id = self._subscription_id

        if not subscription_id:
            # Try to get first subscription
            try:
                subs_result = await check_azure_subscriptions(tenant_id)
                if subs_result.details.get("subscription_count", 0) > 0:
                    subscription_id = subs_result.details["subscriptions"][0]["subscription_id"]
            except Exception as e:
                logger.warning(f"Could not auto-detect subscription: {e}")

        if not subscription_id:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.SKIPPED,
                message="No subscription ID available for Security Center check",
                recommendations=[
                    "Provide a subscription_id parameter",
                    "Ensure the tenant has accessible subscriptions",
                ],
            )

        return await check_security_center_access(tenant_id, subscription_id)


class AzureRBACCheck(BasePreflightCheck):
    """Check Azure RBAC role assignments."""

    def __init__(self, subscription_id: str | None = None):
        super().__init__(
            check_id="azure_rbac_permissions",
            name="Azure RBAC Permissions",
            category=CheckCategory.AZURE_SECURITY,
            description="Verify required RBAC role assignments",
            timeout_seconds=30.0,
        )
        self._subscription_id = subscription_id

    async def _execute_check(self, tenant_id: str | None = None) -> CheckResult:
        """Execute the RBAC check."""
        if not tenant_id:
            tenant_id = settings.azure_tenant_id

        subscription_id = self._subscription_id

        if not subscription_id:
            # Try to get first subscription
            try:
                subs_result = await check_azure_subscriptions(tenant_id)
                if subs_result.details.get("subscription_count", 0) > 0:
                    subscription_id = subs_result.details["subscriptions"][0]["subscription_id"]
            except Exception as e:
                logger.warning(f"Could not auto-detect subscription: {e}")

        if not subscription_id:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.SKIPPED,
                message="No subscription ID available for RBAC check",
                recommendations=[
                    "Provide a subscription_id parameter",
                    "Ensure the tenant has accessible subscriptions",
                ],
            )

        return await check_rbac_permissions(tenant_id, subscription_id)


# ============================================================================
# FUNCTION-BASED CHECK IMPLEMENTATIONS
# ============================================================================


async def check_azure_authentication(tenant_id: str) -> CheckResult:
    """Verify we can get an access token for the tenant.

    This is the most fundamental check - it validates that the application
    can authenticate to Azure AD and obtain a valid access token for the
    Azure Management API.

    Args:
        tenant_id: Azure AD tenant ID to authenticate against

    Returns:
        CheckResult with authentication status and token details

    Example:
        >>> result = await check_azure_authentication("12345678-1234-1234-1234-123456789012")
        >>> print(result.status)  # CheckStatus.PASS if successful
    """
    # Lazy import to avoid namespace package issues in tests
    from azure.core.exceptions import ClientAuthenticationError

    start_time = datetime.utcnow()
    check_id = "azure_authentication"
    name = "Azure AD Authentication"
    category = CheckCategory.AZURE_AUTH

    try:
        credential = _get_credential(tenant_id)
        token = credential.get_token(AZURE_MANAGEMENT_SCOPE)

        # Calculate token expiration time
        expires_at = datetime.fromtimestamp(token.expires_on)
        expires_in_minutes = int((expires_at - datetime.utcnow()).total_seconds() / 60)

        details = {
            "token_acquired": True,
            "token_expires_at": expires_at.isoformat(),
            "token_expires_in_minutes": expires_in_minutes,
            "scope": AZURE_MANAGEMENT_SCOPE,
        }

        # Warning if token expires soon
        if expires_in_minutes < 30:
            return _create_check_result(
                check_id=check_id,
                name=name,
                category=category,
                tenant_id=tenant_id,
                subscription_id=None,
                status=CheckStatus.WARNING,
                message=f"Authentication successful but token expires in {expires_in_minutes} minutes",
                start_time=start_time,
                details=details,
                recommendations=[
                    "Token will expire soon - normal renewal will occur automatically",
                    "If issues persist, verify credential configuration",
                ],
            )

        return _create_check_result(
            check_id=check_id,
            name=name,
            category=category,
            tenant_id=tenant_id,
            subscription_id=None,
            status=CheckStatus.PASS,
            message=f"Successfully authenticated to Azure tenant '{tenant_id[:8]}...'",
            start_time=start_time,
            details=details,
        )

    except ClientAuthenticationError as e:
        error_code, recommendations = _parse_aad_error(str(e))
        return _create_check_result(
            check_id=check_id,
            name=name,
            category=category,
            tenant_id=tenant_id,
            subscription_id=None,
            status=CheckStatus.FAIL,
            message=f"Authentication failed: {error_code}",
            start_time=start_time,
            details={"error_type": "ClientAuthenticationError"},
            recommendations=recommendations,
            error_code=error_code,
            error=e,
        )

    except AzureCheckError as e:
        return _create_check_result(
            check_id=check_id,
            name=name,
            category=category,
            tenant_id=tenant_id,
            subscription_id=None,
            status=CheckStatus.FAIL,
            message=f"Configuration error: {e.message}",
            start_time=start_time,
            details=e.details,
            recommendations=[
                "Set AZURE_CLIENT_ID and AZURE_CLIENT_SECRET environment variables",
                "Or configure via .env file or key vault integration",
            ],
            error_code=e.error_code,
            error=e,
        )

    except Exception as e:
        logger.exception(f"Unexpected error in authentication check for tenant {tenant_id}")
        return _create_check_result(
            check_id=check_id,
            name=name,
            category=category,
            tenant_id=tenant_id,
            subscription_id=None,
            status=CheckStatus.FAIL,
            message=f"Unexpected error during authentication: {type(e).__name__}",
            start_time=start_time,
            recommendations=[
                "Check application logs for detailed error information",
                "Verify network connectivity to Azure AD (login.microsoftonline.com)",
                "Check Azure service health for authentication service outages",
            ],
            error_code="unexpected_error",
            error=e,
        )


async def check_azure_subscriptions(tenant_id: str) -> CheckResult:
    """Verify we can list subscriptions in the tenant.

    Validates that the authenticated principal has access to at least one
    subscription and can enumerate them using the SubscriptionClient.

    Args:
        tenant_id: Azure AD tenant ID

    Returns:
        CheckResult with subscription count and details
    """
    # Lazy import to avoid namespace package issues in tests
    from azure.core.exceptions import ClientAuthenticationError, HttpResponseError

    start_time = datetime.utcnow()
    check_id = "azure_subscriptions"
    name = "Azure Subscriptions Access"
    category = CheckCategory.AZURE_SUBSCRIPTIONS

    try:
        _get_credential(tenant_id)
        client = azure_client_manager.get_subscription_client(tenant_id)

        subscriptions = []
        states = {}

        for sub in client.subscriptions.list():
            subscriptions.append(
                {
                    "subscription_id": sub.subscription_id,
                    "display_name": sub.display_name,
                    "state": sub.state.value if sub.state else "Unknown",
                    "tenant_id": getattr(sub, "tenant_id", None),
                }
            )
            state = sub.state.value if sub.state else "Unknown"
            states[state] = states.get(state, 0) + 1

        if not subscriptions:
            return _create_check_result(
                check_id=check_id,
                name=name,
                category=category,
                tenant_id=tenant_id,
                subscription_id=None,
                status=CheckStatus.WARNING,
                message="No subscriptions found for authenticated principal",
                start_time=start_time,
                details={"subscription_count": 0, "states": {}},
                recommendations=[
                    "Verify the service principal has access to at least one subscription",
                    "Check that subscriptions are not disabled or suspended",
                    "Navigate to Subscription > Access Control (IAM) and add Reader role",
                    "Note: Some subscriptions may be in different tenants (Lighthouse)",
                ],
                error_code="no_subscriptions_found",
            )

        # Check for disabled subscriptions
        disabled_count = states.get("Disabled", 0)
        if disabled_count > 0:
            return _create_check_result(
                check_id=check_id,
                name=name,
                category=category,
                tenant_id=tenant_id,
                subscription_id=None,
                status=CheckStatus.WARNING,
                message=f"Found {len(subscriptions)} subscriptions, {disabled_count} disabled",
                start_time=start_time,
                details={
                    "subscription_count": len(subscriptions),
                    "states": states,
                    "subscriptions": subscriptions[:5],  # First 5 for detail
                },
                recommendations=[
                    f"{disabled_count} subscription(s) are disabled and cannot be monitored",
                    "Re-enable disabled subscriptions or remove them from scope",
                    "Check subscription billing status in Azure Portal",
                ],
            )

        return _create_check_result(
            check_id=check_id,
            name=name,
            category=category,
            tenant_id=tenant_id,
            subscription_id=None,
            status=CheckStatus.PASS,
            message=f"Successfully listed {len(subscriptions)} subscription(s)",
            start_time=start_time,
            details={
                "subscription_count": len(subscriptions),
                "states": states,
                "subscriptions": subscriptions[:10],  # First 10 for detail
            },
        )

    except ClientAuthenticationError as e:
        error_code, recommendations = _parse_aad_error(str(e))
        return _create_check_result(
            check_id=check_id,
            name=name,
            category=category,
            tenant_id=tenant_id,
            subscription_id=None,
            status=CheckStatus.FAIL,
            message="Authentication failed when listing subscriptions",
            start_time=start_time,
            recommendations=recommendations,
            error_code=error_code,
            error=e,
        )

    except HttpResponseError as e:
        if e.status_code == 403:
            return _create_check_result(
                check_id=check_id,
                name=name,
                category=category,
                tenant_id=tenant_id,
                subscription_id=None,
                status=CheckStatus.FAIL,
                message="Access denied when listing subscriptions (403 Forbidden)",
                start_time=start_time,
                details={"status_code": 403},
                recommendations=[
                    "The service principal lacks permissions to list subscriptions",
                    "Add 'Reader' role at the subscription or management group level",
                    "Verify the service principal is from the same tenant as subscriptions",
                ],
                error_code="access_denied",
                error=e,
            )
        raise

    except Exception as e:
        logger.exception(f"Error listing subscriptions for tenant {tenant_id}")
        return _create_check_result(
            check_id=check_id,
            name=name,
            category=category,
            tenant_id=tenant_id,
            subscription_id=None,
            status=CheckStatus.FAIL,
            message=f"Error listing subscriptions: {type(e).__name__}",
            start_time=start_time,
            recommendations=[
                "Verify Azure Resource Manager API is accessible",
                "Check for network connectivity issues",
                "Review application logs for detailed error information",
            ],
            error_code="subscription_list_error",
            error=e,
        )


async def check_cost_management_access(tenant_id: str, subscription_id: str) -> CheckResult:
    """Verify Cost Management API access for a subscription.

    Validates that the application can query cost data for the specified
    subscription. This requires the 'Cost Management Reader' role.

    Args:
        tenant_id: Azure AD tenant ID
        subscription_id: Azure subscription ID to check

    Returns:
        CheckResult with cost API access status
    """
    # Lazy import to avoid namespace package issues in tests
    from azure.core.exceptions import HttpResponseError

    start_time = datetime.utcnow()
    check_id = "cost_management_access"
    name = "Cost Management API Access"
    category = CheckCategory.AZURE_COST_MANAGEMENT

    try:
        client = azure_client_manager.get_cost_client(tenant_id, subscription_id)

        # Build a simple cost query for last 7 days
        from_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
        to_date = datetime.utcnow().strftime("%Y-%m-%d")

        # Query for a small amount of data to verify access
        # Using QueryDefinition from azure.mgmt.costmanagement.models
        from azure.mgmt.costmanagement.models import (
            QueryAggregation,
            QueryDataset,
            QueryDefinition,
            QueryGrouping,
            QueryTimePeriod,
        )

        query = QueryDefinition(
            type="ActualCost",
            timeframe="Custom",
            time_period=QueryTimePeriod(
                from_property=from_date,
                to=to_date,
            ),
            dataset=QueryDataset(
                granularity="None",
                aggregation={"totalCost": QueryAggregation(name="Cost", function="Sum")},
                grouping=[
                    QueryGrouping(type="Dimension", name="SubscriptionName"),
                ],
            ),
        )

        # Execute the query - this will fail with 403 if no Cost Management Reader role
        result = client.query.usage(
            scope=f"/subscriptions/{subscription_id}",
            parameters=query,
        )

        # Extract cost data
        total_cost = 0.0
        currency = "USD"

        if result.properties and result.properties.rows:
            # Find the cost column (usually first column)
            for row in result.properties.rows:
                if len(row) >= 2:
                    try:
                        total_cost = float(row[0]) if isinstance(row[0], (int, float, str)) else 0.0
                        currency = str(row[1]) if len(row) > 1 and row[1] else "USD"
                        break
                    except (ValueError, TypeError):
                        continue

        return _create_check_result(
            check_id=check_id,
            name=name,
            category=category,
            tenant_id=tenant_id,
            subscription_id=subscription_id,
            status=CheckStatus.PASS,
            message=f"Cost Management API access verified for subscription {subscription_id[:8]}...",
            start_time=start_time,
            details={
                "query_successful": True,
                "period_days": 7,
                "total_cost": round(total_cost, 2),
                "currency": currency,
            },
        )

    except HttpResponseError as e:
        if e.status_code == 403:
            return _create_check_result(
                check_id=check_id,
                name=name,
                category=category,
                tenant_id=tenant_id,
                subscription_id=subscription_id,
                status=CheckStatus.FAIL,
                message="Cost Management API access denied (403 Forbidden)",
                start_time=start_time,
                details={
                    "status_code": 403,
                    "required_role": "Cost Management Reader",
                },
                recommendations=[
                    "Navigate to Subscription > Access Control (IAM)",
                    "Add role assignment: Cost Management Reader",
                    "Select the service principal as the assignee",
                    "Wait 5-10 minutes for role assignment to propagate",
                ],
                error_code="cost_management_access_denied",
                error=e,
            )
        elif e.status_code == 400:
            # Often means no cost data available yet (new subscription)
            return _create_check_result(
                check_id=check_id,
                name=name,
                category=category,
                tenant_id=tenant_id,
                subscription_id=subscription_id,
                status=CheckStatus.WARNING,
                message="Cost Management accessible but no cost data available (new subscription?)",
                start_time=start_time,
                details={"status_code": 400, "error": str(e)},
                recommendations=[
                    "Subscription may be too new to have cost data",
                    "Verify subscription has been active for more than 24 hours",
                    "Cost data can take 8-24 hours to appear for new subscriptions",
                ],
                error_code="no_cost_data",
                error=e,
            )
        raise

    except Exception as e:
        logger.exception(
            f"Error checking cost management access for subscription {subscription_id}"
        )
        return _create_check_result(
            check_id=check_id,
            name=name,
            category=category,
            tenant_id=tenant_id,
            subscription_id=subscription_id,
            status=CheckStatus.FAIL,
            message=f"Error accessing Cost Management API: {type(e).__name__}",
            start_time=start_time,
            recommendations=[
                "Verify Cost Management Reader role is assigned",
                "Check that subscription is active and has billing setup",
                "Ensure the subscription is not a free trial with expired credits",
            ],
            error_code="cost_management_error",
            error=e,
        )


async def check_policy_access(tenant_id: str, subscription_id: str) -> CheckResult:
    """Verify Azure Policy Insights API access.

    Validates that the application can query policy compliance states
    using the PolicyInsightsClient.

    Args:
        tenant_id: Azure AD tenant ID
        subscription_id: Azure subscription ID to check

    Returns:
        CheckResult with policy API access status
    """
    from azure.core.exceptions import HttpResponseError

    start_time = datetime.utcnow()
    check_id = "policy_access"
    name = "Azure Policy Insights API Access"
    category = CheckCategory.AZURE_POLICY

    try:
        client = azure_client_manager.get_policy_client(tenant_id, subscription_id)

        # Query policy states with a small top value
        policy_states = client.policy_states.list_query_results_for_subscription(
            policy_states_resource="latest",
            subscription_id=subscription_id,
        )

        # Count policy states
        state_count = 0
        compliance_counts = {"Compliant": 0, "NonCompliant": 0, "Unknown": 0}

        for state in policy_states:
            state_count += 1
            compliance = getattr(state, "compliance_state", "Unknown")
            if compliance in compliance_counts:
                compliance_counts[compliance] += 1

            # Only check first 100 to avoid long-running checks
            if state_count >= 100:
                break

        return _create_check_result(
            check_id=check_id,
            name=name,
            category=category,
            tenant_id=tenant_id,
            subscription_id=subscription_id,
            status=CheckStatus.PASS,
            message=f"Policy Insights API access verified ({state_count} policy states found)",
            start_time=start_time,
            details={
                "policy_states_found": state_count,
                "compliance_summary": compliance_counts,
                "subscription_scoped": True,
            },
        )

    except HttpResponseError as e:
        if e.status_code == 403:
            return _create_check_result(
                check_id=check_id,
                name=name,
                category=category,
                tenant_id=tenant_id,
                subscription_id=subscription_id,
                status=CheckStatus.FAIL,
                message="Policy Insights API access denied (403 Forbidden)",
                start_time=start_time,
                details={"status_code": 403, "required_role": "Reader"},
                recommendations=[
                    "Navigate to Subscription > Access Control (IAM)",
                    "Add role assignment: Reader (minimum required)",
                    "For enhanced policy management, consider: Resource Policy Contributor",
                ],
                error_code="policy_access_denied",
                error=e,
            )
        raise

    except Exception as e:
        logger.exception(f"Error checking policy access for subscription {subscription_id}")
        return _create_check_result(
            check_id=check_id,
            name=name,
            category=category,
            tenant_id=tenant_id,
            subscription_id=subscription_id,
            status=CheckStatus.FAIL,
            message=f"Error accessing Policy Insights API: {type(e).__name__}",
            start_time=start_time,
            recommendations=[
                "Verify Reader role is assigned at subscription level",
                "Check that Azure Policy service is enabled for the subscription",
                "Ensure subscription has at least one policy assignment",
            ],
            error_code="policy_access_error",
            error=e,
        )


async def check_resource_manager_access(tenant_id: str, subscription_id: str) -> CheckResult:
    """Verify Azure Resource Manager access.

    Validates that the application can list resource groups and resources
    using the ResourceManagementClient.

    Args:
        tenant_id: Azure AD tenant ID
        subscription_id: Azure subscription ID to check

    Returns:
        CheckResult with resource manager access status
    """
    from azure.core.exceptions import HttpResponseError

    start_time = datetime.utcnow()
    check_id = "resource_manager_access"
    name = "Azure Resource Manager Access"
    category = CheckCategory.AZURE_RESOURCES

    try:
        client = azure_client_manager.get_resource_client(tenant_id, subscription_id)

        # List resource groups
        resource_groups = list(client.resource_groups.list())
        rg_count = len(resource_groups)

        # Try to get a quick resource count
        resources = list(client.resources.list(top=100))
        resource_count = len(resources)

        # Get location distribution
        locations = {}
        for rg in resource_groups[:10]:  # Sample first 10
            location = rg.location
            locations[location] = locations.get(location, 0) + 1

        return _create_check_result(
            check_id=check_id,
            name=name,
            category=category,
            tenant_id=tenant_id,
            subscription_id=subscription_id,
            status=CheckStatus.PASS,
            message=f"Resource Manager access verified ({rg_count} RGs, {resource_count}+ resources)",
            start_time=start_time,
            details={
                "resource_group_count": rg_count,
                "resource_sample_count": resource_count,
                "locations": locations,
                "access_verified": True,
            },
        )

    except HttpResponseError as e:
        if e.status_code == 403:
            return _create_check_result(
                check_id=check_id,
                name=name,
                category=category,
                tenant_id=tenant_id,
                subscription_id=subscription_id,
                status=CheckStatus.FAIL,
                message="Resource Manager access denied (403 Forbidden)",
                start_time=start_time,
                details={"status_code": 403, "required_role": "Reader"},
                recommendations=[
                    "Navigate to Subscription > Access Control (IAM)",
                    "Add role assignment: Reader",
                    "Select the service principal as the assignee",
                    "For full resource management, consider: Contributor role",
                ],
                error_code="resource_manager_access_denied",
                error=e,
            )
        raise

    except Exception as e:
        logger.exception(
            f"Error checking resource manager access for subscription {subscription_id}"
        )
        return _create_check_result(
            check_id=check_id,
            name=name,
            category=category,
            tenant_id=tenant_id,
            subscription_id=subscription_id,
            status=CheckStatus.FAIL,
            message=f"Error accessing Resource Manager: {type(e).__name__}",
            start_time=start_time,
            recommendations=[
                "Verify Reader role is assigned at subscription level",
                "Check Azure Resource Manager service health",
                "Ensure subscription is active (not disabled or suspended)",
            ],
            error_code="resource_manager_error",
            error=e,
        )


async def check_graph_api_access(tenant_id: str) -> CheckResult:
    """Verify Microsoft Graph API access.

    Validates that the application can authenticate to Microsoft Graph
    and has the required permissions to read directory data.

    Args:
        tenant_id: Azure AD tenant ID

    Returns:
        CheckResult with Graph API access status and permission details
    """
    from azure.core.exceptions import ClientAuthenticationError

    start_time = datetime.utcnow()
    check_id = "graph_api_access"
    name = "Microsoft Graph API Access"
    category = CheckCategory.AZURE_GRAPH

    try:
        # Get credential for Graph API
        credential = _get_credential(tenant_id)
        token = credential.get_token(*GRAPH_SCOPES)

        # Make a test request to Graph API
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {token.token}",
                "Content-Type": "application/json",
            }

            # Test user read access
            response = await client.get(
                f"{GRAPH_API_BASE}/users",
                headers=headers,
                params={"$top": 1, "$select": "id,displayName"},
                timeout=30.0,
            )

            if response.status_code == 403:
                return _create_check_result(
                    check_id=check_id,
                    name=name,
                    category=category,
                    tenant_id=tenant_id,
                    subscription_id=None,
                    status=CheckStatus.FAIL,
                    message="Graph API access denied - admin consent required",
                    start_time=start_time,
                    details={
                        "status_code": 403,
                        "required_permissions": REQUIRED_GRAPH_PERMISSIONS,
                    },
                    recommendations=[
                        "Navigate to Azure Portal > App Registrations > Your App > API Permissions",
                        "Add required permissions: User.Read.All, Group.Read.All, etc.",
                        "Click 'Grant admin consent for [Tenant]' button",
                        "Admin consent must be granted by a Global Administrator",
                    ],
                    error_code="graph_admin_consent_required",
                )

            response.raise_for_status()
            data = response.json()
            user_count = len(data.get("value", []))

            # Try to get organization info
            org_response = await client.get(
                f"{GRAPH_API_BASE}/organization",
                headers=headers,
                timeout=30.0,
            )

            org_info = None
            if org_response.status_code == 200:
                org_data = org_response.json()
                if org_data.get("value"):
                    org = org_data["value"][0]
                    org_info = {
                        "display_name": org.get("displayName"),
                        "tenant_type": org.get("tenantType"),
                        "created": org.get("createdDateTime"),
                    }

        return _create_check_result(
            check_id=check_id,
            name=name,
            category=category,
            tenant_id=tenant_id,
            subscription_id=None,
            status=CheckStatus.PASS,
            message="Graph API access verified, can read users and directory data",
            start_time=start_time,
            details={
                "token_acquired": True,
                "users_readable": user_count > 0,
                "organization_info": org_info,
                "required_permissions": REQUIRED_GRAPH_PERMISSIONS,
            },
        )

    except ClientAuthenticationError as e:
        error_code, recommendations = _parse_aad_error(str(e))
        return _create_check_result(
            check_id=check_id,
            name=name,
            category=category,
            tenant_id=tenant_id,
            subscription_id=None,
            status=CheckStatus.FAIL,
            message=f"Graph API authentication failed: {error_code}",
            start_time=start_time,
            recommendations=recommendations,
            error_code=f"graph_{error_code}",
            error=e,
        )

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return _create_check_result(
                check_id=check_id,
                name=name,
                category=category,
                tenant_id=tenant_id,
                subscription_id=None,
                status=CheckStatus.FAIL,
                message="Graph API authentication failed (401 Unauthorized)",
                start_time=start_time,
                recommendations=[
                    "Verify the application has required Graph API permissions",
                    "Check that admin consent has been granted for all permissions",
                    "Ensure the client secret has not expired",
                ],
                error_code="graph_unauthorized",
                error=e,
            )
        raise

    except Exception as e:
        logger.exception(f"Error checking Graph API access for tenant {tenant_id}")
        return _create_check_result(
            check_id=check_id,
            name=name,
            category=category,
            tenant_id=tenant_id,
            subscription_id=None,
            status=CheckStatus.FAIL,
            message=f"Error accessing Graph API: {type(e).__name__}",
            start_time=start_time,
            recommendations=[
                "Verify network connectivity to graph.microsoft.com",
                "Check that required API permissions are configured",
                "Ensure admin consent has been granted",
            ],
            error_code="graph_api_error",
            error=e,
        )


async def check_security_center_access(tenant_id: str, subscription_id: str) -> CheckResult:
    """Verify Security Center API access.

    Validates that the application can access Azure Security Center data
    including secure scores and security recommendations.

    Args:
        tenant_id: Azure AD tenant ID
        subscription_id: Azure subscription ID to check

    Returns:
        CheckResult with security center access status
    """
    from azure.core.exceptions import HttpResponseError

    start_time = datetime.utcnow()
    check_id = "security_center_access"
    name = "Azure Security Center Access"
    category = CheckCategory.AZURE_SECURITY

    try:
        client = azure_client_manager.get_security_client(tenant_id, subscription_id)

        # Try to get secure scores
        secure_scores = list(client.secure_scores.list())
        score_count = len(secure_scores)

        # Get the overall secure score if available
        overall_score = None
        max_score = None
        for score in secure_scores:
            if getattr(score, "name", "") == "ascScore" or score_count == 1:
                overall_score = getattr(score, "score", {}).get("current", None)
                max_score = getattr(score, "score", {}).get("max", None)
                break

        details = {
            "secure_scores_found": score_count,
            "overall_score": overall_score,
            "max_score": max_score,
            "percentage": (
                round((overall_score / max_score * 100), 2) if overall_score and max_score else None
            ),
        }

        if score_count == 0:
            return _create_check_result(
                check_id=check_id,
                name=name,
                category=category,
                tenant_id=tenant_id,
                subscription_id=subscription_id,
                status=CheckStatus.WARNING,
                message="Security Center accessible but no secure scores available",
                start_time=start_time,
                details=details,
                recommendations=[
                    "Azure Security Center may not be fully enabled",
                    "Security data can take 24-48 hours to populate for new subscriptions",
                    "Verify Defender for Cloud is enabled in the subscription",
                ],
            )

        return _create_check_result(
            check_id=check_id,
            name=name,
            category=category,
            tenant_id=tenant_id,
            subscription_id=subscription_id,
            status=CheckStatus.PASS,
            message=f"Security Center access verified ({score_count} secure score records)",
            start_time=start_time,
            details=details,
        )

    except HttpResponseError as e:
        if e.status_code == 403:
            return _create_check_result(
                check_id=check_id,
                name=name,
                category=category,
                tenant_id=tenant_id,
                subscription_id=subscription_id,
                status=CheckStatus.FAIL,
                message="Security Center API access denied (403 Forbidden)",
                start_time=start_time,
                details={"status_code": 403, "required_role": "Security Reader"},
                recommendations=[
                    "Navigate to Subscription > Access Control (IAM)",
                    "Add role assignment: Security Reader",
                    "Select the service principal as the assignee",
                    "Wait 5-10 minutes for role assignment to propagate",
                ],
                error_code="security_center_access_denied",
                error=e,
            )
        elif e.status_code == 404:
            return _create_check_result(
                check_id=check_id,
                name=name,
                category=category,
                tenant_id=tenant_id,
                subscription_id=subscription_id,
                status=CheckStatus.WARNING,
                message="Security Center not enabled for this subscription",
                start_time=start_time,
                details={"status_code": 404},
                recommendations=[
                    "Enable Microsoft Defender for Cloud for this subscription",
                    "Navigate to Microsoft Defender for Cloud > Getting Started",
                    "Click 'Upgrade' to enable enhanced security features",
                ],
                error_code="security_center_not_enabled",
                error=e,
            )
        raise

    except Exception as e:
        logger.exception(
            f"Error checking security center access for subscription {subscription_id}"
        )
        return _create_check_result(
            check_id=check_id,
            name=name,
            category=category,
            tenant_id=tenant_id,
            subscription_id=subscription_id,
            status=CheckStatus.FAIL,
            message=f"Error accessing Security Center: {type(e).__name__}",
            start_time=start_time,
            recommendations=[
                "Verify Security Reader role is assigned",
                "Check that Microsoft Defender for Cloud is enabled",
                "Ensure subscription is not a free tier without Defender",
            ],
            error_code="security_center_error",
            error=e,
        )


async def check_rbac_permissions(tenant_id: str, subscription_id: str) -> CheckResult:
    """Verify RBAC role assignments for the service principal.

    Checks which required Azure RBAC roles are assigned to the application
    and reports any missing roles.

    Args:
        tenant_id: Azure AD tenant ID
        subscription_id: Azure subscription ID to check

    Returns:
        CheckResult with RBAC assignment details
    """
    # Lazy import to avoid namespace package issues in tests
    from azure.core.exceptions import HttpResponseError
    from azure.mgmt.authorization import AuthorizationManagementClient

    start_time = datetime.utcnow()
    check_id = "rbac_permissions"
    name = "Azure RBAC Permissions"
    category = CheckCategory.AZURE_SECURITY

    try:
        credential = _get_credential(tenant_id)
        auth_client = AuthorizationManagementClient(credential, subscription_id)

        # Get role assignments for this subscription
        assignments = list(auth_client.role_assignments.list())

        # Get role definitions to map IDs to names
        role_defs = {}
        for role_def in auth_client.role_definitions.list():
            role_defs[role_def.id] = role_def

        # Find our service principal's assignments
        # We need to match by principal ID (client_id)

        our_assignments = []
        for assignment in assignments:
            # Check if this assignment is for our service principal
            if hasattr(assignment, "principal_id"):
                role_def = role_defs.get(assignment.role_definition_id)
                if role_def:
                    our_assignments.append(
                        {
                            "role_name": role_def.role_name,
                            "role_type": role_def.role_type,
                            "scope": assignment.scope,
                        }
                    )

        # Determine which required roles are present
        found_roles = {a["role_name"] for a in our_assignments}
        missing_roles = [r for r in REQUIRED_AZURE_ROLES if r not in found_roles]

        # Check if we have at minimum the Reader role
        has_reader = "Reader" in found_roles or any(
            r in found_roles for r in ["Contributor", "Owner"]
        )

        details = {
            "assignments_found": len(our_assignments),
            "roles_present": list(found_roles),
            "required_roles": REQUIRED_AZURE_ROLES,
            "missing_roles": missing_roles,
            "has_reader": has_reader,
        }

        if missing_roles and not has_reader:
            return _create_check_result(
                check_id=check_id,
                name=name,
                category=category,
                tenant_id=tenant_id,
                subscription_id=subscription_id,
                status=CheckStatus.FAIL,
                message=f"Missing required RBAC roles: {', '.join(missing_roles)}",
                start_time=start_time,
                details=details,
                recommendations=[
                    f"Add missing role(s): {', '.join(missing_roles)}",
                    "Navigate to Subscription > Access Control (IAM) > Add > Add role assignment",
                    "Select the service principal as the assignee",
                    "Wait 5-10 minutes for role propagation",
                ],
                error_code="missing_rbac_roles",
            )
        elif missing_roles:
            return _create_check_result(
                check_id=check_id,
                name=name,
                category=category,
                tenant_id=tenant_id,
                subscription_id=subscription_id,
                status=CheckStatus.WARNING,
                message=f"Basic Reader role present, but missing: {', '.join(missing_roles)}",
                start_time=start_time,
                details=details,
                recommendations=[
                    f"For full functionality, add: {', '.join(missing_roles)}",
                    "Cost Management Reader is required for cost data",
                    "Security Reader is required for security center data",
                ],
            )

        return _create_check_result(
            check_id=check_id,
            name=name,
            category=category,
            tenant_id=tenant_id,
            subscription_id=subscription_id,
            status=CheckStatus.PASS,
            message=f"All required RBAC roles assigned ({len(found_roles)} roles)",
            start_time=start_time,
            details=details,
        )

    except HttpResponseError as e:
        if e.status_code == 403:
            return _create_check_result(
                check_id=check_id,
                name=name,
                category=category,
                tenant_id=tenant_id,
                subscription_id=subscription_id,
                status=CheckStatus.WARNING,
                message="Cannot read RBAC assignments - permission denied",
                start_time=start_time,
                details={"status_code": 403},
                recommendations=[
                    "User Access Administrator or Reader role needed to enumerate assignments",
                    "The basic Reader role may be sufficient for operations",
                    "This check is informational - actual access is verified by other checks",
                ],
                error_code="rbac_read_denied",
                error=e,
            )
        raise

    except Exception as e:
        logger.exception(f"Error checking RBAC permissions for subscription {subscription_id}")
        return _create_check_result(
            check_id=check_id,
            name=name,
            category=category,
            tenant_id=tenant_id,
            subscription_id=subscription_id,
            status=CheckStatus.WARNING,
            message=f"Could not verify RBAC assignments: {type(e).__name__}",
            start_time=start_time,
            details={"error": str(e)},
            recommendations=[
                "This check is informational - actual access is verified by other checks",
                "Verify manually in Azure Portal if needed",
            ],
            error_code="rbac_check_error",
            error=e,
        )


async def run_all_azure_checks(
    tenant_id: str, subscription_id: str | None = None
) -> list[CheckResult]:
    """Run all Azure checks for a tenant in parallel.

    Executes all preflight checks concurrently for efficiency. If a subscription_id
    is provided, subscription-specific checks are run against that subscription.
    Otherwise, only tenant-level checks are performed.

    Args:
        tenant_id: Azure AD tenant ID to check
        subscription_id: Optional subscription ID for subscription-scoped checks

    Returns:
        List of CheckResult objects for all executed checks

    Example:
        >>> results = await run_all_azure_checks(
        ...     tenant_id="12345678-1234-1234-1234-123456789012",
        ...     subscription_id="87654321-4321-4321-4321-210987654321"
        ... )
        >>> failed = [r for r in results if r.status == CheckStatus.FAIL]
        >>> print(f"Failed checks: {len(failed)}")
    """
    start_time = datetime.utcnow()
    logger.info(f"Starting preflight checks for tenant {tenant_id[:8]}...")

    results: list[CheckResult] = []

    # Always run tenant-level checks
    tenant_checks = [
        check_azure_authentication(tenant_id),
        check_azure_subscriptions(tenant_id),
        check_graph_api_access(tenant_id),
    ]

    # Run tenant checks concurrently
    tenant_results = await asyncio.gather(*tenant_checks, return_exceptions=True)

    for result in tenant_results:
        if isinstance(result, Exception):
            logger.error(f"Check failed with exception: {result}")
            results.append(
                CheckResult(
                    check_id="unknown",
                    name="Unknown Check",
                    category=CheckCategory.AZURE_AUTH,
                    status=CheckStatus.FAIL,
                    message=f"Check failed with exception: {type(result).__name__}",
                    details={"error": str(result)},
                    duration_ms=0.0,
                    timestamp=datetime.utcnow(),
                    recommendations=["Check application logs for details"],
                )
            )
        else:
            results.append(result)

    # If we have a subscription ID, run subscription-scoped checks
    if subscription_id:
        logger.info(f"Running subscription-scoped checks for {subscription_id[:8]}...")

        sub_checks = [
            check_cost_management_access(tenant_id, subscription_id),
            check_policy_access(tenant_id, subscription_id),
            check_resource_manager_access(tenant_id, subscription_id),
            check_security_center_access(tenant_id, subscription_id),
            check_rbac_permissions(tenant_id, subscription_id),
        ]

        sub_results = await asyncio.gather(*sub_checks, return_exceptions=True)

        for result in sub_results:
            if isinstance(result, Exception):
                logger.error(f"Subscription check failed with exception: {result}")
                results.append(
                    CheckResult(
                        check_id="unknown",
                        name="Unknown Check",
                        category=CheckCategory.AZURE_RESOURCES,
                        status=CheckStatus.FAIL,
                        message=f"Check failed with exception: {type(result).__name__}",
                        details={"error": str(result)},
                        duration_ms=0.0,
                        timestamp=datetime.utcnow(),
                        recommendations=["Check application logs for details"],
                    )
                )
            else:
                results.append(result)

    total_duration = (datetime.utcnow() - start_time).total_seconds() * 1000
    logger.info(
        f"Completed {len(results)} preflight checks in {total_duration:.0f}ms "
        f"for tenant {tenant_id[:8]}..."
    )

    return results


# Export all check classes and functions
__all__ = [
    # Class-based checks
    "AzureAuthCheck",
    "AzureSubscriptionsCheck",
    "AzureCostManagementCheck",
    "AzureGraphCheck",
    "AzurePolicyCheck",
    "AzureResourcesCheck",
    "AzureSecurityCheck",
    "AzureRBACCheck",
    # Function-based checks
    "check_azure_authentication",
    "check_azure_subscriptions",
    "check_cost_management_access",
    "check_graph_api_access",
    "check_policy_access",
    "check_resource_manager_access",
    "check_rbac_permissions",
    "check_security_center_access",
    "run_all_azure_checks",
    # Error class
    "AzureCheckError",
    # Constants
    "REQUIRED_GRAPH_PERMISSIONS",
    "REQUIRED_AZURE_ROLES",
]

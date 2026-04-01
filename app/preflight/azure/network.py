"""Azure network and connectivity preflight checks.

This module provides checks for Azure subscription access, Microsoft Graph API
connectivity, and network-related permissions.
"""

import asyncio
import logging
import time
from typing import Any

import httpx

from app.api.services.azure_client import azure_client_manager
from app.preflight.azure.base import (
    GRAPH_API_BASE,
    GRAPH_SCOPES,
    REQUIRED_GRAPH_PERMISSIONS,
    _create_check_result,
    _get_credential,
    _parse_aad_error,
)
from app.preflight.base import BasePreflightCheck
from app.preflight.models import CheckCategory, CheckResult, CheckStatus

logger = logging.getLogger(__name__)


class AzureSubscriptionsCheck(BasePreflightCheck):
    """Check Azure subscription access and listing."""

    def __init__(self) -> None:
        super().__init__(
            check_id="azure_subscriptions",
            name="Azure Subscriptions Access",
            category=CheckCategory.AZURE_SUBSCRIPTIONS,
            description="Verify access to list Azure subscriptions",
            timeout_seconds=30.0,
        )

    async def _execute_check(self, tenant_id: str | None = None) -> CheckResult:
        """Execute subscription access check."""
        if not tenant_id:
            from app.core.config import get_settings

            tenant_id = get_settings().azure_tenant_id
        return await check_azure_subscriptions(tenant_id or "")


class AzureGraphCheck(BasePreflightCheck):
    """Check Microsoft Graph API access."""

    def __init__(self) -> None:
        super().__init__(
            check_id="graph_api",
            name="Microsoft Graph API Access",
            category=CheckCategory.AZURE_GRAPH,
            description="Verify Microsoft Graph API access and permissions",
            timeout_seconds=30.0,
        )

    async def _execute_check(self, tenant_id: str | None = None) -> CheckResult:
        """Execute Graph API access check."""
        if not tenant_id:
            from app.core.config import get_settings

            tenant_id = get_settings().azure_tenant_id
        return await check_graph_api_access(tenant_id or "")


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

    start_time = time.perf_counter()
    check_id = "azure_subscriptions"
    name = "Azure Subscriptions Access"
    category = CheckCategory.AZURE_SUBSCRIPTIONS

    try:
        _get_credential(tenant_id)
        client = azure_client_manager.get_subscription_client(tenant_id)

        subscriptions: list[dict[str, Any]] = []
        states: dict[str, int] = {}

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
        logger.error(
            "Error listing subscriptions",
            extra={
                "tenant_prefix": tenant_id[:8] if tenant_id else "unknown",
                "error_type": type(e).__name__,
            },
        )
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

    start_time = time.perf_counter()
    check_id = "graph_api_access"
    name = "Microsoft Graph API Access"
    category = CheckCategory.AZURE_GRAPH

    try:
        # Get credential for Graph API
        credential = _get_credential(tenant_id)
        token = await asyncio.to_thread(credential.get_token, *GRAPH_SCOPES)

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

            org_info: dict[str, Any] | None = None
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
        logger.error(
            "Error checking Graph API access",
            extra={
                "tenant_prefix": tenant_id[:8] if tenant_id else "unknown",
                "error_type": type(e).__name__,
            },
        )
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


__all__ = [
    "AzureSubscriptionsCheck",
    "AzureGraphCheck",
    "check_azure_subscriptions",
    "check_graph_api_access",
]

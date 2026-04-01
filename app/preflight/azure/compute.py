"""Azure compute and resource management preflight checks.

This module provides checks for Azure Resource Manager access,
compute resource management, and resource group operations.
"""

import logging
import time

from azure.core.exceptions import HttpResponseError

from app.api.services.azure_client import azure_client_manager
from app.preflight.azure.base import (
    _create_check_result,
)
from app.preflight.base import BasePreflightCheck
from app.preflight.models import CheckCategory, CheckResult, CheckStatus

logger = logging.getLogger(__name__)


class AzureResourcesCheck(BasePreflightCheck):
    """Check Azure Resource Manager access."""

    def __init__(self) -> None:
        super().__init__(
            check_id="azure_resources",
            name="Azure Resource Manager Access",
            category=CheckCategory.AZURE_RESOURCES,
            description="Verify access to Azure Resource Manager API",
            timeout_seconds=30.0,
        )

    async def _execute_check(self, tenant_id: str | None = None) -> CheckResult:
        """Execute resource manager access check."""
        if not tenant_id:
            from app.core.config import get_settings

            tenant_id = get_settings().azure_tenant_id

        # Need subscription ID for this check
        from app.preflight.azure.network import check_azure_subscriptions

        sub_result = await check_azure_subscriptions(tenant_id or "")
        if sub_result.status != CheckStatus.PASS:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.SKIPPED,
                message="Cannot check resource manager - no subscriptions available",
                recommendations=["Fix subscription access first, then retry"],
            )

        # Get first subscription to test with
        subs = sub_result.details.get("subscriptions", [])
        if not subs:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.SKIPPED,
                message="No subscriptions available to test resource manager access",
            )

        subscription_id = subs[0].get("subscription_id", "")
        return await check_resource_manager_access(tenant_id or "", subscription_id)


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
    start_time = time.perf_counter()
    check_id = "resource_manager_access"
    name = "Azure Resource Manager Access"
    category = CheckCategory.AZURE_RESOURCES

    try:
        client = azure_client_manager.get_resource_client(tenant_id, subscription_id)

        # List resource groups
        resource_groups = []
        for rg in client.resource_groups.list():
            resource_groups.append(
                {
                    "name": rg.name,
                    "location": rg.location,
                    "provisioning_state": rg.properties.provisioning_state
                    if rg.properties
                    else None,
                }
            )
            # Limit to first 10 to avoid long-running checks
            if len(resource_groups) >= 10:
                break

        # Count resources in first resource group
        resource_count = 0
        if resource_groups:
            first_rg = resource_groups[0]["name"]
            for _ in client.resources.list_by_resource_group(first_rg):
                resource_count += 1
                # Limit to first 20
                if resource_count >= 20:
                    break

        return _create_check_result(
            check_id=check_id,
            name=name,
            category=category,
            tenant_id=tenant_id,
            subscription_id=subscription_id,
            status=CheckStatus.PASS,
            message=f"Resource Manager access verified ({len(resource_groups)} resource groups)",
            start_time=start_time,
            details={
                "resource_groups_found": len(resource_groups),
                "sample_resource_groups": resource_groups[:5],
                "resources_in_first_rg": resource_count,
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
                details={"status_code": 403},
                recommendations=[
                    "Navigate to Subscription > Access Control (IAM)",
                    "Add role assignment: Reader (minimum required)",
                    "The Reader role allows listing resources but not making changes",
                ],
                error_code="resource_manager_access_denied",
                error=e,
            )
        raise

    except Exception as e:
        logger.error(
            "Error checking resource manager access",
            extra={
                "subscription_prefix": subscription_id[:8] if subscription_id else "unknown",
                "error_type": type(e).__name__,
            },
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
                "Check that Azure Resource Manager service is available",
                "Ensure subscription is active and not disabled",
            ],
            error_code="resource_manager_error",
            error=e,
        )


__all__ = [
    "AzureResourcesCheck",
    "check_resource_manager_access",
]

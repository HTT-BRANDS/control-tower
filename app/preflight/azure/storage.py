"""Azure storage, cost management, and policy preflight checks.

This module provides checks for Azure Cost Management API access,
Azure Policy Insights API access, and related storage operations.
"""

import logging
import time
from datetime import UTC, datetime, timedelta

from azure.core.exceptions import HttpResponseError

from app.api.services.azure_client import azure_client_manager
from app.preflight.azure.base import (
    _create_check_result,
    _get_credential,
)
from app.preflight.base import BasePreflightCheck
from app.preflight.models import CheckCategory, CheckResult, CheckStatus

logger = logging.getLogger(__name__)


class AzureCostManagementCheck(BasePreflightCheck):
    """Check Azure Cost Management API access."""

    def __init__(self) -> None:
        super().__init__(
            check_id="azure_cost_management",
            name="Azure Cost Management Access",
            category=CheckCategory.AZURE_COST_MANAGEMENT,
            description="Verify access to Azure Cost Management API",
            timeout_seconds=30.0,
        )

    async def _execute_check(self, tenant_id: str | None = None) -> CheckResult:
        """Execute cost management access check."""
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
                message="Cannot check cost management - no subscriptions available",
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
                message="No subscriptions available to test cost management access",
            )

        subscription_id = subs[0].get("subscription_id", "")
        return await check_cost_management_access(tenant_id or "", subscription_id)


class AzurePolicyCheck(BasePreflightCheck):
    """Check Azure Policy Insights API access."""

    def __init__(self) -> None:
        super().__init__(
            check_id="azure_policy",
            name="Azure Policy Insights Access",
            category=CheckCategory.AZURE_POLICY,
            description="Verify access to Azure Policy Insights API",
            timeout_seconds=30.0,
        )

    async def _execute_check(self, tenant_id: str | None = None) -> CheckResult:
        """Execute policy access check."""
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
                message="Cannot check policy access - no subscriptions available",
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
                message="No subscriptions available to test policy access",
            )

        subscription_id = subs[0].get("subscription_id", "")
        return await check_policy_access(tenant_id or "", subscription_id)


async def check_cost_management_access(tenant_id: str, subscription_id: str) -> CheckResult:
    """Verify Cost Management API access for a subscription.

    Validates that the application can query cost data for the specified
    subscription. This requires the 'Cost Management Reader' role.

    Args:
        tenant_id: Azure AD tenant ID
        subscription_id: Azure subscription ID to check

    Returns:
        CheckResult with cost management access status
    """
    from azure.mgmt.costmanagement import CostManagementClient
    from azure.mgmt.costmanagement.models import QueryDefinition, QueryTimePeriod

    start_time = time.perf_counter()
    check_id = "cost_management_access"
    name = "Azure Cost Management API Access"
    category = CheckCategory.AZURE_COST_MANAGEMENT

    try:
        credential = _get_credential(tenant_id)
        cost_client = CostManagementClient(credential, subscription_id)

        # Query for last 7 days of costs
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=7)

        query_def = QueryDefinition(
            type="Usage",
            timeframe="Custom",
            time_period=QueryTimePeriod(from_property=start_date, to=end_date),
            dataset={
                "granularity": "None",
                "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
            },
        )

        # Query at subscription scope
        result = cost_client.query.usage(
            scope=f"/subscriptions/{subscription_id}",
            parameters=query_def,
        )

        total_cost = 0.0
        if result and result.properties and result.properties.rows:
            for row in result.properties.rows:
                if len(row) >= 2:
                    total_cost += float(row[0] or 0)

        return _create_check_result(
            check_id=check_id,
            name=name,
            category=category,
            tenant_id=tenant_id,
            subscription_id=subscription_id,
            status=CheckStatus.PASS,
            message=f"Cost Management API access verified (last 7 days: ${total_cost:.2f})",
            start_time=start_time,
            details={
                "cost_data_available": True,
                "total_cost_last_7d": round(total_cost, 2),
                "currency": result.properties.rows[0][1] if result.properties.rows else "USD",
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
                details={"status_code": 403, "required_role": "Cost Management Reader"},
                recommendations=[
                    "Navigate to Subscription > Access Control (IAM)",
                    "Add role assignment: Cost Management Reader",
                    "Select the service principal as the assignee",
                    "Wait 5-10 minutes for role assignment to propagate",
                ],
                error_code="cost_management_access_denied",
                error=e,
            )
        raise

    except Exception as e:
        logger.error(
            "Error checking cost management access",
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
            message=f"Error accessing Cost Management API: {type(e).__name__}",
            start_time=start_time,
            recommendations=[
                "Verify Cost Management Reader role is assigned",
                "Check that subscription has billing data available",
                "Ensure subscription is not a free trial or sponsorship",
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
    start_time = time.perf_counter()
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
        logger.error(
            "Error checking policy access",
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


__all__ = [
    "AzureCostManagementCheck",
    "AzurePolicyCheck",
    "check_cost_management_access",
    "check_policy_access",
]

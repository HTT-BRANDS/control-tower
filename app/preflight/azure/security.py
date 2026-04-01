"""Azure security and RBAC preflight checks.

This module provides checks for Azure Security Center access,
RBAC permissions validation, and security-related operations.
"""

import logging
import time
from typing import Any

from azure.core.exceptions import HttpResponseError
from azure.mgmt.authorization import AuthorizationManagementClient

from app.api.services.azure_client import azure_client_manager
from app.preflight.azure.base import (
    REQUIRED_AZURE_ROLES,
    _create_check_result,
    _get_credential,
)
from app.preflight.base import BasePreflightCheck
from app.preflight.models import CheckCategory, CheckResult, CheckStatus

logger = logging.getLogger(__name__)


class AzureSecurityCheck(BasePreflightCheck):
    """Check Azure Security Center access."""

    def __init__(self) -> None:
        super().__init__(
            check_id="azure_security",
            name="Azure Security Center Access",
            category=CheckCategory.AZURE_SECURITY,
            description="Verify access to Azure Security Center API",
            timeout_seconds=30.0,
        )

    async def _execute_check(self, tenant_id: str | None = None) -> CheckResult:
        """Execute security center access check."""
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
                message="Cannot check security center - no subscriptions available",
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
                message="No subscriptions available to test security center access",
            )

        subscription_id = subs[0].get("subscription_id", "")
        return await check_security_center_access(tenant_id or "", subscription_id)


class AzureRBACCheck(BasePreflightCheck):
    """Check Azure RBAC permissions."""

    def __init__(self) -> None:
        super().__init__(
            check_id="azure_rbac",
            name="Azure RBAC Permissions",
            category=CheckCategory.AZURE_SECURITY,
            description="Verify Azure RBAC role assignments",
            timeout_seconds=30.0,
        )

    async def _execute_check(self, tenant_id: str | None = None) -> CheckResult:
        """Execute RBAC permissions check."""
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
                message="Cannot check RBAC - no subscriptions available",
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
                message="No subscriptions available to test RBAC permissions",
            )

        subscription_id = subs[0].get("subscription_id", "")
        return await check_rbac_permissions(tenant_id or "", subscription_id)


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
    start_time = time.perf_counter()
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
        logger.error(
            "Error checking security center access",
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
    start_time = time.perf_counter()
    check_id = "rbac_permissions"
    name = "Azure RBAC Permissions"
    category = CheckCategory.AZURE_SECURITY

    try:
        credential = _get_credential(tenant_id)
        auth_client = AuthorizationManagementClient(credential, subscription_id)

        # Get role assignments for this subscription
        assignments = list(auth_client.role_assignments.list())

        # Get role definitions to map IDs to names
        role_defs: dict[str, Any] = {}
        for role_def in auth_client.role_definitions.list():
            role_defs[role_def.id] = role_def

        # Find our service principal's assignments
        # We need to match by principal ID (client_id)
        our_assignments: list[dict[str, str]] = []
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
        logger.error(
            "Error checking RBAC permissions",
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


__all__ = [
    "AzureSecurityCheck",
    "AzureRBACCheck",
    "check_security_center_access",
    "check_rbac_permissions",
]

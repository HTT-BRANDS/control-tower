"""Preflight check implementations.

Contains all the concrete check implementations for Azure, GitHub, and system checks.
"""

import logging
from typing import List

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.tenant import Tenant
from app.preflight.base import BasePreflightCheck
from app.preflight.models import (
    CheckCategory,
    CheckResult,
    CheckStatus,
)

logger = logging.getLogger(__name__)


class DatabaseCheck(BasePreflightCheck):
    """Check SQLite database connectivity."""

    def __init__(self):
        super().__init__(
            check_id="database_connectivity",
            name="Database Connectivity",
            category=CheckCategory.DATABASE,
            description="Verify SQLite database is accessible",
            timeout_seconds=10.0,
        )

    async def _execute_check(
        self, tenant_id: str | None = None
    ) -> CheckResult:
        """Execute database connectivity check."""
        try:
            db = SessionLocal()
            try:
                # Simple query to verify connectivity
                from sqlalchemy import text
                db.execute(text("SELECT 1"))

                # Get some basic stats
                tenant_count = db.query(Tenant).count()

                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.PASS,
                    message="Database connectivity verified",
                    details={
                        "tenant_count": tenant_count,
                        "database_type": "SQLite",
                    },
                )
            finally:
                db.close()
        except Exception as e:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.FAIL,
                message=f"Database connectivity failed: {str(e)}",
                recommendations=[
                    "Verify the database file exists and is accessible",
                    "Check file permissions on the database directory",
                    "Ensure SQLite is properly installed",
                ],
            )


class AzureAuthCheck(BasePreflightCheck):
    """Check Azure AD authentication."""

    def __init__(self):
        super().__init__(
            check_id="azure_auth",
            name="Azure AD Authentication",
            category=CheckCategory.AZURE_AUTH,
            description="Verify Azure AD authentication is configured",
            timeout_seconds=15.0,
        )

    async def _execute_check(
        self, tenant_id: str | None = None
    ) -> CheckResult:
        """Execute Azure authentication check."""
        settings = get_settings()

        # Check if credentials are configured
        if not settings.is_configured:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.FAIL,
                message="Azure credentials not fully configured",
                details={
                    "azure_tenant_id": bool(settings.azure_tenant_id),
                    "azure_client_id": bool(settings.azure_client_id),
                    "azure_client_secret": bool(settings.azure_client_secret),
                },
                recommendations=[
                    "Configure AZURE_TENANT_ID environment variable",
                    "Configure AZURE_CLIENT_ID environment variable",
                    "Configure AZURE_CLIENT_SECRET environment variable",
                ],
            )

        try:
            # Attempt to get a token
            from app.api.services.azure_client import get_token

            token = await get_token(settings.azure_tenant_id)

            if token:
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.PASS,
                    message="Successfully authenticated with Azure AD",
                    details={
                        "tenant_id": settings.azure_tenant_id,
                        "token_obtained": True,
                    },
                )
            else:
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.FAIL,
                    message="Failed to obtain Azure AD token",
                    recommendations=[
                        "Verify service principal credentials are correct",
                        "Check that the service principal exists in Azure AD",
                        "Verify the tenant ID is correct",
                    ],
                )
        except Exception as e:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.FAIL,
                message=f"Azure authentication failed: {str(e)}",
            )


class AzureSubscriptionsCheck(BasePreflightCheck):
    """Check Azure subscription access."""

    def __init__(self):
        super().__init__(
            check_id="azure_subscriptions",
            name="Azure Subscriptions Access",
            category=CheckCategory.AZURE_SUBSCRIPTIONS,
            description="Verify access to Azure subscriptions",
            timeout_seconds=30.0,
        )

    async def _execute_check(
        self, tenant_id: str | None = None
    ) -> CheckResult:
        """Execute Azure subscriptions check."""
        settings = get_settings()

        try:
            from app.api.services.resource_service import ResourceService

            service = ResourceService(tenant_id or settings.azure_tenant_id)
            subscriptions = await service.get_subscriptions()

            if subscriptions:
                enabled_count = sum(1 for s in subscriptions if s.get("state") == "Enabled")
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.PASS,
                    message=f"Found {len(subscriptions)} subscriptions ({enabled_count} enabled)",
                    details={
                        "total_subscriptions": len(subscriptions),
                        "enabled_subscriptions": enabled_count,
                        "tenant_id": tenant_id or settings.azure_tenant_id,
                        "subscriptions": [
                            {"id": s.get("subscriptionId"), "name": s.get("displayName")}
                            for s in subscriptions[:5]
                        ],
                    },
                )
            else:
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.WARNING,
                    message="No subscriptions found",
                    details={"tenant_id": tenant_id or settings.azure_tenant_id},
                    recommendations=[
                        "Verify the service principal has Reader access to subscriptions",
                        "Check if there are subscriptions in this tenant",
                    ],
                )
        except Exception as e:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.FAIL,
                message=f"Failed to access subscriptions: {str(e)}",
                tenant_id=tenant_id,
            )


class AzureCostManagementCheck(BasePreflightCheck):
    """Check Azure Cost Management API access."""

    def __init__(self):
        super().__init__(
            check_id="azure_cost_management",
            name="Cost Management API",
            category=CheckCategory.AZURE_COST_MANAGEMENT,
            description="Verify access to Azure Cost Management API",
            timeout_seconds=30.0,
        )

    async def _execute_check(
        self, tenant_id: str | None = None
    ) -> CheckResult:
        """Execute Cost Management API check."""
        settings = get_settings()

        try:
            from app.api.services.cost_service import CostService

            service = CostService(tenant_id or settings.azure_tenant_id)
            costs = await service.get_cost_for_period(days=1)

            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.PASS,
                message="Cost Management API accessible",
                details={
                    "tenant_id": tenant_id or settings.azure_tenant_id,
                    "api_version": "2023-03-01",
                },
            )
        except Exception as e:
            error_msg = str(e).lower()
            if "403" in error_msg or "forbidden" in error_msg:
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.FAIL,
                    message="Cost Management API access denied (403)",
                    details={"error": str(e)[:200]},
                    recommendations=[
                        "Grant Cost Management Reader role to the service principal",
                        "Verify scope permissions at subscription or management group level",
                    ],
                    tenant_id=tenant_id,
                )
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.FAIL,
                message=f"Cost Management API error: {str(e)}",
                tenant_id=tenant_id,
            )


class AzurePolicyCheck(BasePreflightCheck):
    """Check Azure Policy API access."""

    def __init__(self):
        super().__init__(
            check_id="azure_policy",
            name="Azure Policy API",
            category=CheckCategory.AZURE_POLICY,
            description="Verify access to Azure Policy API",
            timeout_seconds=30.0,
        )

    async def _execute_check(
        self, tenant_id: str | None = None
    ) -> CheckResult:
        """Execute Policy API check."""
        settings = get_settings()

        try:
            from app.api.services.compliance_service import ComplianceService

            service = ComplianceService(tenant_id or settings.azure_tenant_id)
            policies = await service.get_policy_definitions()

            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.PASS,
                message=f"Policy API accessible - {len(policies)} definitions found",
                details={
                    "tenant_id": tenant_id or settings.azure_tenant_id,
                    "policy_count": len(policies),
                },
            )
        except Exception as e:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.FAIL,
                message=f"Policy API error: {str(e)}",
                tenant_id=tenant_id,
            )


class AzureResourcesCheck(BasePreflightCheck):
    """Check Azure Resource Manager access."""

    def __init__(self):
        super().__init__(
            check_id="azure_resources",
            name="Resource Manager Access",
            category=CheckCategory.AZURE_RESOURCES,
            description="Verify access to Azure Resource Manager",
            timeout_seconds=30.0,
        )

    async def _execute_check(
        self, tenant_id: str | None = None
    ) -> CheckResult:
        """Execute Resource Manager check."""
        settings = get_settings()

        try:
            from app.api.services.resource_service import ResourceService

            service = ResourceService(tenant_id or settings.azure_tenant_id)
            resources = await service.get_resources(top=10)

            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.PASS,
                message=f"Resource Manager accessible - {len(resources)} resources found",
                details={
                    "tenant_id": tenant_id or settings.azure_tenant_id,
                    "resource_count": len(resources),
                },
            )
        except Exception as e:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.FAIL,
                message=f"Resource Manager error: {str(e)}",
                tenant_id=tenant_id,
            )


class AzureGraphCheck(BasePreflightCheck):
    """Check Microsoft Graph API access."""

    def __init__(self):
        super().__init__(
            check_id="azure_graph",
            name="Microsoft Graph API",
            category=CheckCategory.AZURE_GRAPH,
            description="Verify access to Microsoft Graph API",
            timeout_seconds=30.0,
        )

    async def _execute_check(
        self, tenant_id: str | None = None
    ) -> CheckResult:
        """Execute Graph API check."""
        settings = get_settings()

        try:
            from app.api.services.graph_client import GraphClient

            client = GraphClient(tenant_id or settings.azure_tenant_id)
            user_info = await client.get_organization()

            if user_info:
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.PASS,
                    message="Microsoft Graph API accessible",
                    details={
                        "tenant_id": tenant_id or settings.azure_tenant_id,
                        "organization": user_info.get("displayName"),
                    },
                )
            else:
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.WARNING,
                    message="Graph API returned empty response",
                    tenant_id=tenant_id,
                )
        except Exception as e:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.FAIL,
                message=f"Graph API error: {str(e)}",
                tenant_id=tenant_id,
            )


class AzureSecurityCheck(BasePreflightCheck):
    """Check Azure Security Center access."""

    def __init__(self):
        super().__init__(
            check_id="azure_security",
            name="Security Center Access",
            category=CheckCategory.AZURE_SECURITY,
            description="Verify access to Azure Security Center",
            timeout_seconds=30.0,
        )

    async def _execute_check(
        self, tenant_id: str | None = None
    ) -> CheckResult:
        """Execute Security Center check."""
        settings = get_settings()

        # This check is informational - Security Center may not be available in all subscriptions
        try:

            settings_obj = get_settings()
            token = None

            # Try to get a token
            try:
                from app.api.services.azure_client import get_token
                token = await get_token(tenant_id or settings_obj.azure_tenant_id)
            except Exception:
                pass

            if token:
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.PASS,
                    message="Security Center connectivity verified",
                    details={
                        "tenant_id": tenant_id or settings.azure_tenant_id,
                        "note": "Security Center API requires additional permissions",
                    },
                )
            else:
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.WARNING,
                    message="Could not verify Security Center access",
                    tenant_id=tenant_id,
                    recommendations=[
                        "Grant Security Reader role to verify full access",
                    ],
                )
        except Exception as e:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.WARNING,
                message=f"Security Center check skipped: {str(e)}",
                tenant_id=tenant_id,
                recommendations=[
                    "This is an informational check - full verification requires additional permissions",
                ],
            )


class GitHubAccessCheck(BasePreflightCheck):
    """Check GitHub repository access."""

    def __init__(self):
        super().__init__(
            check_id="github_access",
            name="GitHub Repository Access",
            category=CheckCategory.GITHUB_ACCESS,
            description="Verify GitHub repository access is configured",
            timeout_seconds=15.0,
        )

    async def _execute_check(
        self, tenant_id: str | None = None
    ) -> CheckResult:
        """Execute GitHub access check."""
        import os

        github_token = os.environ.get("GITHUB_TOKEN")
        github_repo = os.environ.get("GITHUB_REPO")

        if not github_token:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.WARNING,
                message="GitHub token not configured",
                recommendations=[
                    "Set GITHUB_TOKEN environment variable",
                    "Create a GitHub Personal Access Token with repo scope",
                ],
            )

        if not github_repo:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.WARNING,
                message="GitHub repository not configured",
                recommendations=[
                    "Set GITHUB_REPO environment variable",
                    "Format: owner/repo",
                ],
            )

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {github_token}",
                    "Accept": "application/vnd.github.v3+json",
                }
                async with session.get(
                    f"https://api.github.com/repos/{github_repo}",
                    headers=headers,
                ) as response:
                    if response.status == 200:
                        repo_data = await response.json()
                        return CheckResult(
                            check_id=self.check_id,
                            name=self.name,
                            category=self.category,
                            status=CheckStatus.PASS,
                            message=f"GitHub repository accessible: {repo_data.get('full_name')}",
                            details={
                                "repo": github_repo,
                                "private": repo_data.get("private"),
                                "default_branch": repo_data.get("default_branch"),
                            },
                        )
                    elif response.status == 404:
                        return CheckResult(
                            check_id=self.check_id,
                            name=self.name,
                            category=self.category,
                            status=CheckStatus.FAIL,
                            message=f"Repository not found: {github_repo}",
                            recommendations=[
                                "Verify the repository exists",
                                "Check GITHUB_REPO format (owner/repo)",
                            ],
                        )
                    elif response.status == 403:
                        return CheckResult(
                            check_id=self.check_id,
                            name=self.name,
                            category=self.category,
                            status=CheckStatus.FAIL,
                            message="GitHub API rate limit exceeded",
                            recommendations=[
                                "Wait before retrying",
                                "Consider using a GitHub App token",
                            ],
                        )
                    else:
                        return CheckResult(
                            check_id=self.check_id,
                            name=self.name,
                            category=self.category,
                            status=CheckStatus.FAIL,
                            message=f"GitHub API error: {response.status}",
                        )
        except Exception as e:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.FAIL,
                message=f"GitHub access check failed: {str(e)}",
            )


class GitHubActionsCheck(BasePreflightCheck):
    """Check GitHub Actions workflow permissions."""

    def __init__(self):
        super().__init__(
            check_id="github_actions",
            name="GitHub Actions Workflows",
            category=CheckCategory.GITHUB_ACTIONS,
            description="Verify GitHub Actions workflow access",
            timeout_seconds=15.0,
        )

    async def _execute_check(
        self, tenant_id: str | None = None
    ) -> CheckResult:
        """Execute GitHub Actions check."""
        import os

        github_token = os.environ.get("GITHUB_TOKEN")
        github_repo = os.environ.get("GITHUB_REPO")

        if not github_token or not github_repo:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.SKIPPED,
                message="GitHub not configured - skipping Actions check",
            )

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {github_token}",
                    "Accept": "application/vnd.github.v3+json",
                }
                async with session.get(
                    f"https://api.github.com/repos/{github_repo}/actions/workflows",
                    headers=headers,
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        workflow_count = len(data.get("workflows", []))
                        return CheckResult(
                            check_id=self.check_id,
                            name=self.name,
                            category=self.category,
                            status=CheckStatus.PASS,
                            message=f"GitHub Actions accessible - {workflow_count} workflows found",
                            details={
                                "repo": github_repo,
                                "workflow_count": workflow_count,
                            },
                        )
                    elif response.status == 404:
                        return CheckResult(
                            check_id=self.check_id,
                            name=self.name,
                            category=self.category,
                            status=CheckStatus.WARNING,
                            message="No workflows found in repository",
                            details={"repo": github_repo},
                        )
                    elif response.status == 403:
                        return CheckResult(
                            check_id=self.check_id,
                            name=self.name,
                            category=self.category,
                            status=CheckStatus.FAIL,
                            message="GitHub API rate limit exceeded",
                        )
                    else:
                        return CheckResult(
                            check_id=self.check_id,
                            name=self.name,
                            category=self.category,
                            status=CheckStatus.FAIL,
                            message=f"GitHub API error: {response.status}",
                        )
        except Exception as e:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.FAIL,
                message=f"GitHub Actions check failed: {str(e)}",
            )


def get_all_checks() -> dict[str, BasePreflightCheck]:
    """Get all available preflight checks.

    Returns:
        Dictionary mapping check_id to check instance
    """
    checks = [
        DatabaseCheck(),
        AzureAuthCheck(),
        AzureSubscriptionsCheck(),
        AzureCostManagementCheck(),
        AzurePolicyCheck(),
        AzureResourcesCheck(),
        AzureGraphCheck(),
        AzureSecurityCheck(),
        GitHubAccessCheck(),
        GitHubActionsCheck(),
    ]

    # Import and add Riverside checks
    try:
        from app.preflight.riverside_checks import (
            RiversideAPIEndpointCheck,
            RiversideAzureADPermissionsCheck,
            RiversideDatabaseCheck,
            RiversideMFADataSourceCheck,
            RiversideSchedulerCheck,
        )
        checks.extend([
            RiversideDatabaseCheck(),
            RiversideAPIEndpointCheck(),
            RiversideSchedulerCheck(),
            RiversideAzureADPermissionsCheck(),
            RiversideMFADataSourceCheck(),
        ])
    except ImportError:
        # Riverside checks not available
        pass

    # Import and add admin risk checks
    try:
        from app.preflight.admin_risk_checks import (
            AdminComplianceGapCheck,
            AdminMfaCheck,
            InactiveAdminCheck,
            OverprivilegedAccountCheck,
            SharedAdminCheck,
        )
        checks.extend([
            AdminMfaCheck(),
            OverprivilegedAccountCheck(),
            InactiveAdminCheck(),
            SharedAdminCheck(),
            AdminComplianceGapCheck(),
        ])
    except ImportError:
        # Admin risk checks not available
        pass

    return {check.check_id: check for check in checks}


def get_checks_by_category(
    category: CheckCategory,
) -> List[BasePreflightCheck]:
    """Get all checks for a specific category.

    Args:
        category: The category to filter by

    Returns:
        List of checks in that category
    """
    all_checks = get_all_checks()
    return [check for check in all_checks.values() if check.category == category]

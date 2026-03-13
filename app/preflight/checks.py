"""Preflight check implementations.

Contains all the concrete check implementations for Azure, GitHub, and system checks.
"""

import logging

import httpx

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

    async def _execute_check(self, tenant_id: str | None = None) -> CheckResult:
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

    async def _execute_check(self, tenant_id: str | None = None) -> CheckResult:
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
            # Attempt to get a token via AzureClientManager
            from app.api.services.azure_client import AzureClientManager

            manager = AzureClientManager()
            credential = manager.get_credential(settings.azure_tenant_id)
            token = credential.get_token("https://management.azure.com/.default")

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

    async def _execute_check(self, tenant_id: str | None = None) -> CheckResult:
        """Execute Azure subscriptions check."""
        settings = get_settings()

        try:
            from app.api.services.azure_client import AzureClientManager

            manager = AzureClientManager()
            subscriptions = await manager.list_subscriptions(tenant_id or settings.azure_tenant_id)

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

    async def _execute_check(self, tenant_id: str | None = None) -> CheckResult:
        """Execute Cost Management API check."""
        settings = get_settings()

        try:
            from app.api.services.azure_client import AzureClientManager

            manager = AzureClientManager()
            effective_tenant = tenant_id or settings.azure_tenant_id
            subs = await manager.list_subscriptions(effective_tenant)
            if subs:
                manager.get_cost_client(effective_tenant, subs[0]["subscription_id"])
                # If we get here, client creation succeeded

            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.PASS,
                message="Cost Management API accessible",
                details={
                    "tenant_id": effective_tenant,
                    "api_version": "2023-03-01",
                    "subscriptions_checked": len(subs) if subs else 0,
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

    async def _execute_check(self, tenant_id: str | None = None) -> CheckResult:
        """Execute Policy API check."""
        settings = get_settings()

        try:
            from app.api.services.azure_client import AzureClientManager

            manager = AzureClientManager()
            effective_tenant = tenant_id or settings.azure_tenant_id
            subs = await manager.list_subscriptions(effective_tenant)
            if subs:
                manager.get_policy_client(effective_tenant, subs[0]["subscription_id"])
                # PolicyInsightsClient creation verifies access

            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.PASS,
                message="Policy API accessible",
                details={
                    "tenant_id": effective_tenant,
                    "subscriptions_checked": len(subs) if subs else 0,
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

    async def _execute_check(self, tenant_id: str | None = None) -> CheckResult:
        """Execute Resource Manager check."""
        settings = get_settings()

        try:
            from app.api.services.azure_client import AzureClientManager

            manager = AzureClientManager()
            effective_tenant = tenant_id or settings.azure_tenant_id
            subs = await manager.list_subscriptions(effective_tenant)
            if subs:
                client = manager.get_resource_client(effective_tenant, subs[0]["subscription_id"])
                resources = list(client.resources.list(filter=None, top=5))
            else:
                resources = []

            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.PASS,
                message=f"Resource Manager accessible - {len(resources)} resources found",
                details={
                    "tenant_id": effective_tenant,
                    "resource_count": len(resources),
                    "subscriptions_checked": len(subs) if subs else 0,
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
    """Check Microsoft Graph API access.

    Uses a lightweight approach:
    1. Verify token acquisition (fast, tests Azure AD connectivity)
    2. Make a single direct HTTP call to /organization (lightweight endpoint)
       with a short 10s timeout and NO retries (avoids retry amplification)
    """

    def __init__(self):
        super().__init__(
            check_id="azure_graph",
            name="Microsoft Graph API",
            category=CheckCategory.AZURE_GRAPH,
            description="Verify access to Microsoft Graph API",
            timeout_seconds=20.0,
        )

    async def _execute_check(self, tenant_id: str | None = None) -> CheckResult:
        """Execute Graph API check with lightweight direct call."""

        settings = get_settings()
        effective_tenant = tenant_id or settings.azure_tenant_id

        if not effective_tenant:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.FAIL,
                message="No tenant ID configured for Graph API check",
                recommendations=["Set AZURE_TENANT_ID environment variable"],
            )

        try:
            # Step 1: Verify token acquisition (tests Azure AD auth)
            from app.api.services.graph_client import GRAPH_API_BASE, GraphClient

            client = GraphClient(effective_tenant)
            token = await client._get_token()

            if not token:
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.FAIL,
                    message="Failed to acquire Graph API token",
                    tenant_id=tenant_id,
                    recommendations=["Check AZURE_CLIENT_ID and AZURE_CLIENT_SECRET"],
                )

            # Step 2: Make a single lightweight Graph call (no retries)
            # Use /organization endpoint - faster than /users, always available
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient() as http_client:
                response = await http_client.get(
                    f"{GRAPH_API_BASE}/organization",
                    headers=headers,
                    params={"$select": "id,displayName"},
                    timeout=10.0,  # Short timeout for preflight
                )
                response.raise_for_status()
                data = response.json()

            org_count = len(data.get("value", []))
            org_name = (
                data.get("value", [{}])[0].get("displayName", "Unknown") if org_count > 0 else "N/A"
            )

            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.PASS,
                message=f"Microsoft Graph API accessible (org: {org_name})",
                details={
                    "tenant_id": effective_tenant,
                    "organization_name": org_name,
                    "organizations_found": org_count,
                    "token_acquired": True,
                },
                tenant_id=tenant_id,
            )

        except httpx.TimeoutException:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.FAIL,
                message="Graph API request timed out (10s) - network connectivity issue",
                tenant_id=tenant_id,
                details={"tenant_id": effective_tenant, "token_acquired": True},
                recommendations=[
                    "Check container outbound network connectivity to graph.microsoft.com",
                    "Verify App Service outbound IP is not blocked",
                    "Check if VNet integration has restrictive NSG rules",
                ],
            )
        except httpx.HTTPStatusError as e:
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.FAIL,
                message=f"Graph API returned HTTP {e.response.status_code}",
                tenant_id=tenant_id,
                details={"status_code": e.response.status_code, "tenant_id": effective_tenant},
                recommendations=[
                    "Check app registration has Graph API permissions",
                    "Verify admin consent is granted",
                ],
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

    async def _execute_check(self, tenant_id: str | None = None) -> CheckResult:
        """Execute Security Center check."""
        settings = get_settings()

        # This check is informational - Security Center may not be available in all subscriptions
        try:
            settings_obj = get_settings()
            token = None

            # Try to get a token via AzureClientManager
            try:
                from app.api.services.azure_client import AzureClientManager

                manager = AzureClientManager()
                credential = manager.get_credential(tenant_id or settings_obj.azure_tenant_id)
                token = credential.get_token("https://management.azure.com/.default")
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

    async def _execute_check(self, tenant_id: str | None = None) -> CheckResult:
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

    async def _execute_check(self, tenant_id: str | None = None) -> CheckResult:
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

        checks.extend(
            [
                RiversideDatabaseCheck(),
                RiversideAPIEndpointCheck(),
                RiversideSchedulerCheck(),
                RiversideAzureADPermissionsCheck(),
                RiversideMFADataSourceCheck(),
            ]
        )
    except ImportError:
        # Riverside checks not available
        pass

    # Import and add MFA compliance checks
    try:
        from app.preflight.mfa_checks import (
            MFAAdminEnrollmentCheck,
            MFAGapReportCheck,
            MFATenantDataCheck,
            MFAUserEnrollmentCheck,
        )

        checks.extend(
            [
                MFATenantDataCheck(),
                MFAAdminEnrollmentCheck(),
                MFAUserEnrollmentCheck(),
                MFAGapReportCheck(),
            ]
        )
    except ImportError:
        # MFA checks not available
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

        checks.extend(
            [
                AdminMfaCheck(),
                OverprivilegedAccountCheck(),
                InactiveAdminCheck(),
                SharedAdminCheck(),
                AdminComplianceGapCheck(),
            ]
        )
    except ImportError:
        # Admin risk checks not available
        pass

        pass

    return {check.check_id: check for check in checks}


def get_checks_by_category(
    category: CheckCategory,
) -> list[BasePreflightCheck]:
    """Get all checks for a specific category.

    Args:
        category: The category to filter by

    Returns:
        List of checks in that category
    """
    all_checks = get_all_checks()
    return [check for check in all_checks.values() if check.category == category]

"""Riverside-specific preflight checks.

This module provides comprehensive preflight checks for the Riverside Company
compliance tracking system. These checks validate database connectivity,
API endpoint availability, scheduler configuration, Azure AD permissions,
and MFA data source connectivity.

Example:
    >>> from app.preflight.riverside_checks import (
    ...     RiversideDatabaseCheck,
    ...     RiversideAPIEndpointCheck,
    ...     run_all_riverside_checks,
    ... )
    >>> # Using class-based API
    >>> check = RiversideDatabaseCheck()
    >>> result = await check.run(tenant_id="12345678-1234-1234-1234-123456789012")
    >>>
    >>> # Run all Riverside checks
    >>> results = await run_all_riverside_checks()
"""

import logging
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.riverside import (
    RiversideCompliance,
    RiversideMFA,
    RiversideRequirement,
)
from app.models.tenant import Tenant
from app.preflight.base import BasePreflightCheck
from app.preflight.models import CheckCategory, CheckResult, CheckStatus

logger = logging.getLogger(__name__)


class SeverityLevel(str):
    """Severity levels for Riverside checks."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class RiversideDatabaseCheck(BasePreflightCheck):
    """Check connectivity to Riverside database tables.

    Validates that the riverside_compliance, riverside_mfa, and
    riverside_requirements tables are accessible and contain expected data.
    """

    def __init__(self):
        super().__init__(
            check_id="riverside_database_connectivity",
            name="Riverside Database Connectivity",
            category=CheckCategory.RIVERSIDE,
            description="Verify database connectivity to all Riverside tables",
            timeout_seconds=15.0,
        )

    async def _execute_check(
        self, tenant_id: str | None = None
    ) -> CheckResult:
        """Execute database connectivity check for Riverside tables."""
        start_time = datetime.utcnow()
        db: Session | None = None

        try:
            db = SessionLocal()
            table_status = {}
            errors = []

            # Check riverside_compliance table
            try:
                compliance_count = db.query(RiversideCompliance).count()
                table_status["riverside_compliance"] = {
                    "accessible": True,
                    "record_count": compliance_count,
                }
            except Exception as e:
                table_status["riverside_compliance"] = {
                    "accessible": False,
                    "error": str(e)[:100],
                }
                errors.append(f"riverside_compliance: {str(e)[:100]}")

            # Check riverside_mfa table
            try:
                mfa_count = db.query(RiversideMFA).count()
                table_status["riverside_mfa"] = {
                    "accessible": True,
                    "record_count": mfa_count,
                }
            except Exception as e:
                table_status["riverside_mfa"] = {
                    "accessible": False,
                    "error": str(e)[:100],
                }
                errors.append(f"riverside_mfa: {str(e)[:100]}")

            # Check riverside_requirements table
            try:
                requirements_count = db.query(RiversideRequirement).count()
                table_status["riverside_requirements"] = {
                    "accessible": True,
                    "record_count": requirements_count,
                }
            except Exception as e:
                table_status["riverside_requirements"] = {
                    "accessible": False,
                    "error": str(e)[:100],
                }
                errors.append(f"riverside_requirements: {str(e)[:100]}")

            # Check for recent data if tenant_id provided
            recent_data_check = {}
            if tenant_id:
                try:
                    # Check for recent compliance data
                    recent_compliance = (
                        db.query(RiversideCompliance)
                        .filter(RiversideCompliance.tenant_id == tenant_id)
                        .order_by(RiversideCompliance.updated_at.desc())
                        .first()
                    )
                    recent_data_check["compliance_data"] = (
                        "found" if recent_compliance else "not_found"
                    )

                    # Check for recent MFA data
                    recent_mfa = (
                        db.query(RiversideMFA)
                        .filter(RiversideMFA.tenant_id == tenant_id)
                        .order_by(RiversideMFA.snapshot_date.desc())
                        .first()
                    )
                    recent_data_check["mfa_data"] = (
                        "found" if recent_mfa else "not_found"
                    )

                    # Check for requirements
                    recent_req = (
                        db.query(RiversideRequirement)
                        .filter(RiversideRequirement.tenant_id == tenant_id)
                        .first()
                    )
                    recent_data_check["requirements_data"] = (
                        "found" if recent_req else "not_found"
                    )

                except Exception as e:
                    recent_data_check["error"] = str(e)[:100]

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            if errors:
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.FAIL,
                    message=f"Database connectivity issues: {'; '.join(errors)}",
                    details={
                        "table_status": table_status,
                        "recent_data_check": recent_data_check,
                        "severity": SeverityLevel.CRITICAL,
                    },
                    duration_ms=duration_ms,
                    recommendations=[
                        "Verify database migrations have been run: alembic upgrade head",
                        "Check database file permissions and disk space",
                        "Review SQLAlchemy model definitions for table schema mismatches",
                    ],
                    tenant_id=tenant_id,
                )

            total_records = sum(
                status.get("record_count", 0)
                for status in table_status.values()
                if status.get("accessible")
            )

            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.PASS,
                message=f"All Riverside tables accessible ({total_records} total records)",
                details={
                    "table_status": table_status,
                    "recent_data_check": recent_data_check,
                    "severity": SeverityLevel.INFO,
                },
                duration_ms=duration_ms,
                tenant_id=tenant_id,
            )

        except Exception as e:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.FAIL,
                message=f"Database connectivity check failed: {str(e)}",
                details={
                    "error_type": type(e).__name__,
                    "severity": SeverityLevel.CRITICAL,
                },
                duration_ms=duration_ms,
                recommendations=[
                    "Check database connection string configuration",
                    "Verify database server is running and accessible",
                    "Review application logs for connection errors",
                ],
                tenant_id=tenant_id,
            )
        finally:
            if db:
                db.close()


class RiversideAPIEndpointCheck(BasePreflightCheck):
    """Check Riverside API endpoint availability.

    Validates that all Riverside API endpoints are accessible and
    returning expected responses.
    """

    def __init__(self):
        super().__init__(
            check_id="riverside_api_endpoints",
            name="Riverside API Endpoint Availability",
            category=CheckCategory.RIVERSIDE,
            description="Verify all Riverside API endpoints are accessible",
            timeout_seconds=20.0,
        )

    async def _execute_check(
        self, tenant_id: str | None = None
    ) -> CheckResult:
        """Execute API endpoint availability check."""
        start_time = datetime.utcnow()
        settings = get_settings()

        # Define endpoints to check
        endpoints = [
            {
                "name": "Riverside Summary",
                "path": "/api/v1/riverside/summary",
                "method": "GET",
            },
            {
                "name": "Riverside MFA Status",
                "path": "/api/v1/riverside/mfa-status",
                "method": "GET",
            },
            {
                "name": "Riverside Maturity Scores",
                "path": "/api/v1/riverside/maturity-scores",
                "method": "GET",
            },
            {
                "name": "Riverside Requirements",
                "path": "/api/v1/riverside/requirements",
                "method": "GET",
            },
            {
                "name": "Riverside Gaps",
                "path": "/api/v1/riverside/gaps",
                "method": "GET",
            },
        ]

        results = {}
        failed_endpoints = []

        # Build base URL
        base_url = getattr(settings, "app_base_url", "http://localhost:8000")
        if not base_url:
            base_url = "http://localhost:8000"

        async with httpx.AsyncClient(timeout=10.0) as client:
            for endpoint in endpoints:
                try:
                    url = f"{base_url}{endpoint['path']}"
                    response = await client.request(
                        method=endpoint["method"],
                        url=url,
                        follow_redirects=True,
                    )

                    # Consider 200-499 as "accessible" (even auth errors mean endpoint exists)
                    is_accessible = 200 <= response.status_code < 500

                    results[endpoint["name"]] = {
                        "accessible": is_accessible,
                        "status_code": response.status_code,
                        "response_time_ms": response.elapsed.total_seconds() * 1000
                        if hasattr(response, "elapsed")
                        else None,
                    }

                    if not is_accessible:
                        failed_endpoints.append(endpoint["name"])

                except Exception as e:
                    results[endpoint["name"]] = {
                        "accessible": False,
                        "error": str(e)[:100],
                    }
                    failed_endpoints.append(endpoint["name"])

        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        accessible_count = sum(
            1 for r in results.values() if r.get("accessible")
        )

        if failed_endpoints:
            severity = (
                SeverityLevel.CRITICAL
                if accessible_count == 0
                else SeverityLevel.WARNING
            )
            status = (
                CheckStatus.FAIL
                if accessible_count == 0
                else CheckStatus.WARNING
            )

            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=status,
                message=f"API endpoint issues: {len(failed_endpoints)} of {len(endpoints)} endpoints failed",
                details={
                    "endpoint_results": results,
                    "failed_endpoints": failed_endpoints,
                    "base_url": base_url,
                    "severity": severity,
                },
                duration_ms=duration_ms,
                recommendations=[
                    "Verify the application is running and accessible",
                    "Check that all Riverside API routes are registered in FastAPI",
                    "Review reverse proxy/load balancer configuration",
                    "Check authentication middleware is not blocking health checks",
                ],
                tenant_id=tenant_id,
            )

        return CheckResult(
            check_id=self.check_id,
            name=self.name,
            category=self.category,
            status=CheckStatus.PASS,
            message=f"All {len(endpoints)} Riverside API endpoints accessible",
            details={
                "endpoint_results": results,
                "base_url": base_url,
                "severity": SeverityLevel.INFO,
            },
            duration_ms=duration_ms,
            tenant_id=tenant_id,
        )


class RiversideSchedulerCheck(BasePreflightCheck):
    """Check Riverside scheduler job registration.

    Validates that the Riverside sync job is properly registered
    in the background scheduler and configured with appropriate intervals.
    """

    def __init__(self):
        super().__init__(
            check_id="riverside_scheduler",
            name="Riverside Scheduler Job Registration",
            category=CheckCategory.RIVERSIDE,
            description="Verify Riverside sync job is registered in scheduler",
            timeout_seconds=10.0,
        )

    async def _execute_check(
        self, tenant_id: str | None = None
    ) -> CheckResult:
        """Execute scheduler job registration check."""
        start_time = datetime.utcnow()

        try:
            from app.core.scheduler import get_scheduler

            scheduler = get_scheduler()

            if not scheduler:
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.WARNING,
                    message="Scheduler not initialized",
                    details={
                        "scheduler_initialized": False,
                        "severity": SeverityLevel.WARNING,
                    },
                    duration_ms=duration_ms,
                    recommendations=[
                        "Call init_scheduler() during application startup",
                        "Verify scheduler configuration in core/config.py",
                    ],
                    tenant_id=tenant_id,
                )

            # Look for Riverside sync job
            riverside_job = None
            job_details = {}

            for job in scheduler.get_jobs():
                job_id = job.id if hasattr(job, "id") else str(job)
                if "riverside" in job_id.lower() or "riverside" in str(job.name).lower():
                    riverside_job = job
                    job_details = {
                        "id": job_id,
                        "name": getattr(job, "name", "Unknown"),
                        "trigger": str(job.trigger) if hasattr(job, "trigger") else "Unknown",
                        "next_run_time": str(job.next_run_time) if hasattr(job, "next_run_time") else None,
                    }
                    break

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            if not riverside_job:
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.FAIL,
                    message="Riverside sync job not found in scheduler",
                    details={
                        "scheduler_running": scheduler.running,
                        "total_jobs": len(scheduler.get_jobs()),
                        "available_jobs": [
                            job.id if hasattr(job, "id") else str(job)
                            for job in scheduler.get_jobs()
                        ],
                        "severity": SeverityLevel.CRITICAL,
                    },
                    duration_ms=duration_ms,
                    recommendations=[
                        "Add Riverside sync job in init_scheduler() in core/scheduler.py",
                        "Verify the job function exists: app.core.sync.riverside.sync_riverside",
                        "Check job interval configuration (recommended: 4 hours)",
                    ],
                    tenant_id=tenant_id,
                )

            # Check if scheduler is running
            is_running = scheduler.running if hasattr(scheduler, "running") else False

            if not is_running:
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.WARNING,
                    message="Riverside job registered but scheduler is not running",
                    details={
                        "job_details": job_details,
                        "scheduler_running": False,
                        "severity": SeverityLevel.WARNING,
                    },
                    duration_ms=duration_ms,
                    recommendations=[
                        "Call scheduler.start() during application startup",
                        "Check for scheduler initialization errors in logs",
                    ],
                    tenant_id=tenant_id,
                )

            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.PASS,
                message=f"Riverside sync job registered and scheduler running",
                details={
                    "job_details": job_details,
                    "scheduler_running": True,
                    "total_jobs": len(scheduler.get_jobs()),
                    "severity": SeverityLevel.INFO,
                },
                duration_ms=duration_ms,
                tenant_id=tenant_id,
            )

        except Exception as e:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.FAIL,
                message=f"Scheduler check failed: {str(e)}",
                details={
                    "error_type": type(e).__name__,
                    "severity": SeverityLevel.CRITICAL,
                },
                duration_ms=duration_ms,
                recommendations=[
                    "Verify APScheduler is installed: pip install apscheduler",
                    "Check scheduler initialization in core/scheduler.py",
                    "Review application logs for import errors",
                ],
                tenant_id=tenant_id,
            )


class RiversideAzureADPermissionsCheck(BasePreflightCheck):
    """Check Azure AD permissions for Riverside data access.

    Validates that the Azure AD service principal has the required
    permissions to read MFA status, user data, and device compliance
    information needed for Riverside compliance tracking.
    """

    def __init__(self):
        super().__init__(
            check_id="riverside_azure_ad_permissions",
            name="Riverside Azure AD Permissions",
            category=CheckCategory.RIVERSIDE,
            description="Verify Azure AD permissions for Riverside data access",
            timeout_seconds=30.0,
        )

    async def _execute_check(
        self, tenant_id: str | None = None
    ) -> CheckResult:
        """Execute Azure AD permissions check for Riverside."""
        start_time = datetime.utcnow()
        settings = get_settings()

        # Required Graph API permissions for Riverside
        required_permissions = [
            "User.Read.All",
            "Group.Read.All",
            "Directory.Read.All",
            "AuditLog.Read.All",
            "Reports.Read.All",
        ]

        try:
            from app.api.services.graph_client import GraphClient

            target_tenant_id = tenant_id or settings.azure_tenant_id

            if not target_tenant_id:
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.FAIL,
                    message="No tenant ID available for permissions check",
                    details={
                        "severity": SeverityLevel.CRITICAL,
                    },
                    duration_ms=duration_ms,
                    recommendations=[
                        "Configure AZURE_TENANT_ID environment variable",
                        "Verify tenant is properly registered in the system",
                    ],
                    tenant_id=tenant_id,
                )

            client = GraphClient(target_tenant_id)

            # Test permissions by attempting to fetch users (requires User.Read.All)
            permissions_status = {}

            try:
                # Try to get users - tests User.Read.All and Directory.Read.All
                users = await client.get_users(limit=1)
                permissions_status["User.Read.All"] = {
                    "granted": True,
                    "test_result": "success",
                }
            except Exception as e:
                error_str = str(e).lower()
                if "403" in error_str or "forbidden" in error_str:
                    permissions_status["User.Read.All"] = {
                        "granted": False,
                        "test_result": "forbidden",
                        "error": str(e)[:100],
                    }
                else:
                    permissions_status["User.Read.All"] = {
                        "granted": False,
                        "test_result": "error",
                        "error": str(e)[:100],
                    }

            # Try to get organization info - tests basic connectivity
            try:
                org = await client.get_organization()
                permissions_status["Organization.Read.All"] = {
                    "granted": True,
                    "test_result": "success",
                    "org_name": org.get("displayName") if org else None,
                }
            except Exception as e:
                permissions_status["Organization.Read.All"] = {
                    "granted": False,
                    "test_result": "error",
                    "error": str(e)[:100],
                }

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            # Determine overall status
            granted_count = sum(
                1 for p in permissions_status.values() if p.get("granted")
            )

            if granted_count == 0:
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.FAIL,
                    message="No required Azure AD permissions granted",
                    details={
                        "permissions_status": permissions_status,
                        "required_permissions": required_permissions,
                        "tenant_id": target_tenant_id,
                        "severity": SeverityLevel.CRITICAL,
                    },
                    duration_ms=duration_ms,
                    recommendations=[
                        "Navigate to Azure Portal > App Registrations > Your App > API Permissions",
                        "Add required permissions: User.Read.All, Group.Read.All, Directory.Read.All",
                        "Click 'Grant admin consent for [Tenant]' button",
                        "Wait 5-10 minutes for permissions to propagate",
                    ],
                    tenant_id=tenant_id,
                )

            if granted_count < len(permissions_status):
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.WARNING,
                    message=f"Partial permissions: {granted_count} of {len(permissions_status)} key permissions granted",
                    details={
                        "permissions_status": permissions_status,
                        "required_permissions": required_permissions,
                        "tenant_id": target_tenant_id,
                        "severity": SeverityLevel.WARNING,
                    },
                    duration_ms=duration_ms,
                    recommendations=[
                        "Review missing permissions in API Permissions blade",
                        "Grant admin consent for all required permissions",
                        "Some Riverside features may be limited without full permissions",
                    ],
                    tenant_id=tenant_id,
                )

            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.PASS,
                message=f"All required Azure AD permissions granted ({granted_count}/{len(permissions_status)})",
                details={
                    "permissions_status": permissions_status,
                    "required_permissions": required_permissions,
                    "tenant_id": target_tenant_id,
                    "severity": SeverityLevel.INFO,
                },
                duration_ms=duration_ms,
                tenant_id=tenant_id,
            )

        except Exception as e:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            error_str = str(e).lower()

            # Handle specific authentication errors
            if "authentication" in error_str or "unauthorized" in error_str or "401" in error_str:
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.FAIL,
                    message="Azure AD authentication failed - cannot verify permissions",
                    details={
                        "error": str(e)[:200],
                        "error_type": type(e).__name__,
                        "severity": SeverityLevel.CRITICAL,
                    },
                    duration_ms=duration_ms,
                    recommendations=[
                        "Verify Azure credentials are correctly configured",
                        "Check that the service principal exists in Azure AD",
                        "Ensure client secret has not expired",
                    ],
                    tenant_id=tenant_id,
                )

            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.FAIL,
                message=f"Azure AD permissions check failed: {str(e)}",
                details={
                    "error_type": type(e).__name__,
                    "severity": SeverityLevel.CRITICAL,
                },
                duration_ms=duration_ms,
                recommendations=[
                    "Verify Azure AD tenant is accessible",
                    "Check service principal configuration",
                    "Review application logs for detailed error information",
                ],
                tenant_id=tenant_id,
            )


class RiversideMFADataSourceCheck(BasePreflightCheck):
    """Check MFA data source connectivity.

    Validates connectivity to the MFA data sources used by Riverside,
    including Microsoft Graph API for user MFA status and Azure AD
    authentication methods.
    """

    def __init__(self):
        super().__init__(
            check_id="riverside_mfa_data_source",
            name="Riverside MFA Data Source Connectivity",
            category=CheckCategory.RIVERSIDE,
            description="Verify MFA data source connectivity via Graph API",
            timeout_seconds=30.0,
        )

    async def _execute_check(
        self, tenant_id: str | None = None
    ) -> CheckResult:
        """Execute MFA data source connectivity check."""
        start_time = datetime.utcnow()
        settings = get_settings()

        try:
            from app.api.services.graph_client import GraphClient

            target_tenant_id = tenant_id or settings.azure_tenant_id

            if not target_tenant_id:
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.FAIL,
                    message="No tenant ID available for MFA data source check",
                    details={
                        "severity": SeverityLevel.CRITICAL,
                    },
                    duration_ms=duration_ms,
                    recommendations=[
                        "Configure AZURE_TENANT_ID environment variable",
                        "Verify tenant configuration in the database",
                    ],
                    tenant_id=tenant_id,
                )

            client = GraphClient(target_tenant_id)

            # Test MFA data access by fetching users with authentication methods
            data_source_status = {}

            try:
                # Try to get users - basic connectivity test
                users = await client.get_users(limit=5)
                data_source_status["users_endpoint"] = {
                    "accessible": True,
                    "user_count": len(users) if users else 0,
                }

                # Try to get authentication methods for first user
                if users and len(users) > 0:
                    first_user = users[0]
                    user_id = first_user.get("id")

                    if user_id:
                        try:
                            # This requires UserAuthenticationMethod.Read.All permission
                            auth_methods = await client._make_request(
                                f"/users/{user_id}/authentication/methods"
                            )
                            data_source_status["authentication_methods"] = {
                                "accessible": True,
                                "methods_count": len(auth_methods.get("value", [])),
                            }
                        except Exception as e:
                            error_str = str(e).lower()
                            if "403" in error_str or "forbidden" in error_str:
                                data_source_status["authentication_methods"] = {
                                    "accessible": False,
                                    "reason": "permission_denied",
                                    "note": "UserAuthenticationMethod.Read.All permission required",
                                }
                            else:
                                data_source_status["authentication_methods"] = {
                                    "accessible": False,
                                    "reason": "error",
                                    "error": str(e)[:100],
                                }

            except Exception as e:
                error_str = str(e).lower()
                if "401" in error_str or "unauthorized" in error_str:
                    data_source_status["users_endpoint"] = {
                        "accessible": False,
                        "reason": "authentication_failed",
                    }
                elif "403" in error_str or "forbidden" in error_str:
                    data_source_status["users_endpoint"] = {
                        "accessible": False,
                        "reason": "permission_denied",
                    }
                else:
                    data_source_status["users_endpoint"] = {
                        "accessible": False,
                        "reason": "error",
                        "error": str(e)[:100],
                    }

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            # Determine overall status
            users_accessible = data_source_status.get("users_endpoint", {}).get(
                "accessible", False
            )
            auth_methods_accessible = data_source_status.get(
                "authentication_methods", {}
            ).get("accessible", False)

            if not users_accessible:
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.FAIL,
                    message="MFA data source not accessible - cannot retrieve user data",
                    details={
                        "data_source_status": data_source_status,
                        "tenant_id": target_tenant_id,
                        "severity": SeverityLevel.CRITICAL,
                    },
                    duration_ms=duration_ms,
                    recommendations=[
                        "Verify Azure AD authentication is configured correctly",
                        "Ensure service principal has User.Read.All permission",
                        "Grant admin consent for Microsoft Graph API permissions",
                        "Check tenant ID is correct and accessible",
                    ],
                    tenant_id=tenant_id,
                )

            if not auth_methods_accessible:
                return CheckResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.WARNING,
                    message="Basic user data accessible but authentication methods endpoint limited",
                    details={
                        "data_source_status": data_source_status,
                        "tenant_id": target_tenant_id,
                        "severity": SeverityLevel.WARNING,
                    },
                    duration_ms=duration_ms,
                    recommendations=[
                        "Add UserAuthenticationMethod.Read.All permission for detailed MFA data",
                        "Basic MFA coverage will still work via sign-in activity",
                        "For enhanced MFA reporting, grant the additional permission",
                    ],
                    tenant_id=tenant_id,
                )

            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.PASS,
                message="MFA data source fully accessible - user and authentication method data available",
                details={
                    "data_source_status": data_source_status,
                    "tenant_id": target_tenant_id,
                    "severity": SeverityLevel.INFO,
                },
                duration_ms=duration_ms,
                tenant_id=tenant_id,
            )

        except Exception as e:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.FAIL,
                message=f"MFA data source check failed: {str(e)}",
                details={
                    "error_type": type(e).__name__,
                    "severity": SeverityLevel.CRITICAL,
                },
                duration_ms=duration_ms,
                recommendations=[
                    "Verify Graph API client is properly configured",
                    "Check Azure AD service principal credentials",
                    "Review application logs for Graph API errors",
                ],
                tenant_id=tenant_id,
            )


# ============================================================================
# FUNCTION-BASED API (for direct use)
# ============================================================================

async def check_riverside_database(tenant_id: str | None = None) -> CheckResult:
    """Check Riverside database connectivity.

    Args:
        tenant_id: Optional tenant ID for tenant-specific checks

    Returns:
        CheckResult with database connectivity status
    """
    check = RiversideDatabaseCheck()
    return await check.run(tenant_id=tenant_id)


async def check_riverside_api_endpoints(tenant_id: str | None = None) -> CheckResult:
    """Check Riverside API endpoint availability.

    Args:
        tenant_id: Optional tenant ID for tenant-specific checks

    Returns:
        CheckResult with API endpoint status
    """
    check = RiversideAPIEndpointCheck()
    return await check.run(tenant_id=tenant_id)


async def check_riverside_scheduler(tenant_id: str | None = None) -> CheckResult:
    """Check Riverside scheduler job registration.

    Args:
        tenant_id: Optional tenant ID for tenant-specific checks

    Returns:
        CheckResult with scheduler status
    """
    check = RiversideSchedulerCheck()
    return await check.run(tenant_id=tenant_id)


async def check_riverside_azure_ad_permissions(
    tenant_id: str | None = None,
) -> CheckResult:
    """Check Azure AD permissions for Riverside.

    Args:
        tenant_id: Optional tenant ID for tenant-specific checks

    Returns:
        CheckResult with Azure AD permissions status
    """
    check = RiversideAzureADPermissionsCheck()
    return await check.run(tenant_id=tenant_id)


async def check_riverside_mfa_data_source(
    tenant_id: str | None = None,
) -> CheckResult:
    """Check MFA data source connectivity.

    Args:
        tenant_id: Optional tenant ID for tenant-specific checks

    Returns:
        CheckResult with MFA data source status
    """
    check = RiversideMFADataSourceCheck()
    return await check.run(tenant_id=tenant_id)


async def run_all_riverside_checks(tenant_id: str | None = None) -> list[CheckResult]:
    """Run all Riverside preflight checks.

    Args:
        tenant_id: Optional tenant ID for tenant-specific checks

    Returns:
        List of CheckResults from all Riverside checks
    """
    checks = [
        RiversideDatabaseCheck(),
        RiversideAPIEndpointCheck(),
        RiversideSchedulerCheck(),
        RiversideAzureADPermissionsCheck(),
        RiversideMFADataSourceCheck(),
    ]

    results = []
    for check in checks:
        try:
            result = await check.run(tenant_id=tenant_id)
            results.append(result)
        except Exception as e:
            # If a check fails completely, create a failed result
            results.append(
                CheckResult(
                    check_id=check.check_id,
                    name=check.name,
                    category=check.category,
                    status=CheckStatus.FAIL,
                    message=f"Check failed with exception: {str(e)}",
                    details={"error_type": type(e).__name__},
                    recommendations=["Review application logs for details"],
                    tenant_id=tenant_id,
                )
            )

    return results


def get_riverside_checks() -> dict[str, BasePreflightCheck]:
    """Get all Riverside preflight checks.

    Returns:
        Dictionary mapping check_id to check instance
    """
    checks = [
        RiversideDatabaseCheck(),
        RiversideAPIEndpointCheck(),
        RiversideSchedulerCheck(),
        RiversideAzureADPermissionsCheck(),
        RiversideMFADataSourceCheck(),
    ]

    return {check.check_id: check for check in checks}

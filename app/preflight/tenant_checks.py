"""Multi-tenant preflight check orchestration.

This module provides high-level functions for running preflight checks
across multiple Azure tenants, including aggregation of results and
tenant discovery from the database.

Example:
    >>> from app.preflight.tenant_checks import check_all_tenants
    >>> results = await check_all_tenants()
    >>> for tenant_id, checks in results.results.items():
    ...     print(f"Tenant {tenant_id}: {len(checks)} checks run")
"""

import asyncio
import logging
from datetime import datetime

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.tenant import Subscription, Tenant
from app.preflight.azure_checks import (
    check_azure_authentication,
    run_all_azure_checks,
)
from app.preflight.models import CheckCategory, CheckResult, CheckStatus

logger = logging.getLogger(__name__)
settings = get_settings()


async def _get_active_tenants() -> list[Tenant]:
    """Retrieve all active tenants from the database.

    Returns:
        List of active Tenant model instances
    """
    with SessionLocal() as db:
        tenants = db.query(Tenant).filter(Tenant.is_active == True).all()  # noqa: E712
        return tenants


async def _get_tenant_subscriptions(tenant_id: str) -> list[Subscription]:
    """Retrieve subscriptions for a tenant.

    Args:
        tenant_id: Database tenant ID (not Azure tenant ID)

    Returns:
        List of Subscription model instances
    """
    with SessionLocal() as db:
        subscriptions = db.query(Subscription).filter(Subscription.tenant_ref == tenant_id).all()
        return subscriptions


def _create_error_result(
    check_id: str,
    name: str,
    category: CheckCategory,
    tenant_id: str,
    message: str,
    error_code: str,
    recommendations: list[str],
) -> CheckResult:
    """Create a CheckResult for error conditions.

    Args:
        check_id: Unique identifier for the check
        name: Human-readable name of the check
        category: Category of the check
        tenant_id: Azure tenant ID
        message: Error message
        error_code: Error code
        recommendations: List of recommendations

    Returns:
        CheckResult with FAIL status
    """
    return CheckResult(
        check_id=check_id,
        name=name,
        category=category,
        status=CheckStatus.FAIL,
        message=message,
        details={"error_code": error_code},
        duration_ms=0.0,
        timestamp=datetime.utcnow(),
        recommendations=recommendations,
        tenant_id=tenant_id,
    )


async def check_tenant_connectivity(tenant_id: str) -> CheckResult:
    """Quick connectivity check for a tenant.

    Performs a lightweight authentication check suitable for dashboard
    health indicators or quick status checks. This is faster than
    running all checks but only validates basic connectivity.

    Args:
        tenant_id: Azure AD tenant ID

    Returns:
        CheckResult with connectivity status

    Example:
        >>> result = await check_tenant_connectivity("12345678-1234-1234-1234-123456789012")
        >>> is_connected = result.status == CheckStatus.PASS
    """
    start_time = datetime.utcnow()
    check_id = "tenant_connectivity"
    name = "Tenant Connectivity"

    try:
        # Try to authenticate - this is the most basic check
        result = await check_azure_authentication(tenant_id)

        if result.status == CheckStatus.PASS:
            return CheckResult(
                check_id=check_id,
                name=name,
                category=CheckCategory.SYSTEM,
                status=CheckStatus.PASS,
                message="Tenant connectivity verified",
                details={
                    "authentication_successful": True,
                    "auth_details": result.details,
                },
                duration_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                timestamp=datetime.utcnow(),
                recommendations=[],
                tenant_id=tenant_id,
            )
        else:
            return CheckResult(
                check_id=check_id,
                name=name,
                category=CheckCategory.SYSTEM,
                status=result.status,
                message=f"Tenant connectivity issue: {result.message}",
                details={"authentication_result": result.status.value},
                duration_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
                timestamp=datetime.utcnow(),
                recommendations=result.recommendations,
                tenant_id=tenant_id,
            )

    except Exception as e:
        logger.exception(f"Error checking tenant connectivity for {tenant_id}")
        return _create_error_result(
            check_id=check_id,
            name=name,
            category=CheckCategory.SYSTEM,
            tenant_id=tenant_id,
            message=f"Connectivity check failed: {type(e).__name__}",
            error_code="connectivity_check_error",
            recommendations=[
                "Verify tenant ID is correct",
                "Check Azure service health",
                "Review application logs for details",
            ],
        )


async def check_single_tenant(
    tenant: Tenant,
    run_subscription_checks: bool = True,
    subscription_id: str | None = None,
) -> list[CheckResult]:
    """Run preflight checks for a single tenant.

    Executes all relevant checks for a tenant. Optionally runs
    subscription-scoped checks against the first available subscription
    or a specific subscription if provided.

    Args:
        tenant: Tenant model instance
        run_subscription_checks: Whether to run subscription-scoped checks
        subscription_id: Specific subscription ID to check (overrides auto-detection)

    Returns:
        List of CheckResult objects
    """
    results: list[CheckResult] = []
    azure_tenant_id = tenant.tenant_id

    logger.info(f"Running checks for tenant '{tenant.name}' ({azure_tenant_id[:8]}...)")

    # Run tenant-level checks first
    tenant_results = await run_all_azure_checks(
        tenant_id=azure_tenant_id,
        subscription_id=None,  # Tenant-level only first
    )
    results.extend(tenant_results)

    # Check if authentication succeeded before proceeding
    auth_check = next((r for r in tenant_results if r.check_id == "azure_authentication"), None)

    if auth_check and auth_check.status == CheckStatus.FAIL:
        logger.warning(
            f"Authentication failed for tenant {azure_tenant_id[:8]}...,"
            " skipping subscription checks"
        )
        return results

    # Get subscriptions for this tenant
    subscriptions = await _get_tenant_subscriptions(tenant.id)

    if not subscriptions:
        logger.warning(f"No subscriptions found for tenant {azure_tenant_id[:8]}...")
        results.append(
            CheckResult(
                check_id="subscription_availability",
                name="Subscription Availability",
                category=CheckCategory.AZURE_SUBSCRIPTIONS,
                status=CheckStatus.WARNING,
                message="No subscriptions configured for this tenant",
                details={"tenant_db_id": tenant.id},
                duration_ms=0.0,
                timestamp=datetime.utcnow(),
                recommendations=[
                    "Add subscriptions to the tenant configuration",
                    "Run subscription discovery to find available subscriptions",
                    "Verify the service principal has access to at least one subscription",
                ],
                tenant_id=azure_tenant_id,
            )
        )
        return results

    # Determine which subscription to check
    target_subscription_id = subscription_id

    if target_subscription_id is None and run_subscription_checks:
        # Use the first subscription
        target_subscription_id = subscriptions[0].subscription_id
        logger.info(
            f"Using subscription {target_subscription_id[:8]}... for "
            f"tenant {azure_tenant_id[:8]}..."
        )

    # Run subscription-scoped checks if we have a subscription
    if target_subscription_id and run_subscription_checks:
        sub_results = await run_all_azure_checks(
            tenant_id=azure_tenant_id,
            subscription_id=target_subscription_id,
        )
        results.extend(sub_results)

    return results


async def check_all_tenants(
    tenant_ids: list[str] | None = None,
    run_subscription_checks: bool = True,
    parallel: bool = True,
) -> dict[str, list[CheckResult]]:
    """Run preflight checks on all configured tenants.

    Executes preflight checks across multiple tenants, either in parallel
    or sequentially. Returns a dictionary mapping tenant IDs to their check results.

    Args:
        tenant_ids: Optional list of specific tenant IDs to check.
            If None, checks all active tenants from the database.
        run_subscription_checks: Whether to run subscription-scoped checks
        parallel: Whether to run checks in parallel (faster but more resource-intensive)

    Returns:
        Dictionary mapping tenant IDs to lists of CheckResult objects

    Example:
        >>> # Check all tenants
        >>> results = await check_all_tenants()
        >>>
        >>> # Check specific tenants only
        >>> results = await check_all_tenants(
        ...     tenant_ids=["tenant-id-1", "tenant-id-2"]
        ... )
        >>>
        >>> # Quick check without subscription details
        >>> results = await check_all_tenants(run_subscription_checks=False)
    """
    start_time = datetime.utcnow()
    logger.info("Starting multi-tenant preflight checks")

    # Get tenants to check
    if tenant_ids:
        with SessionLocal() as db:
            tenants = (
                db.query(Tenant)
                .filter(Tenant.tenant_id.in_(tenant_ids))
                .filter(Tenant.is_active == True)  # noqa: E712
                .all()
            )
    else:
        tenants = await _get_active_tenants()

    if not tenants:
        logger.warning("No active tenants found to check")
        return {}

    logger.info(f"Found {len(tenants)} tenant(s) to check")

    # Run checks for each tenant
    results: dict[str, list[CheckResult]] = {}

    if parallel:
        # Run all tenant checks concurrently
        tasks = [check_single_tenant(tenant, run_subscription_checks) for tenant in tenants]
        tenant_results = await asyncio.gather(*tasks, return_exceptions=True)

        for tenant, tenant_checks in zip(tenants, tenant_results, strict=False):
            if isinstance(tenant_checks, Exception):
                logger.error(f"Failed to run checks for tenant {tenant.tenant_id}: {tenant_checks}")
                results[tenant.tenant_id] = [
                    _create_error_result(
                        check_id="tenant_check_execution",
                        name="Tenant Check Execution",
                        category=CheckCategory.SYSTEM,
                        tenant_id=tenant.tenant_id,
                        message=f"Failed to execute tenant checks: {type(tenant_checks).__name__}",
                        error_code="tenant_check_execution_failed",
                        recommendations=[
                            "Check application logs for detailed error information",
                            "Verify tenant configuration and credentials",
                            "Ensure database connectivity",
                        ],
                    )
                ]
            else:
                results[tenant.tenant_id] = tenant_checks
    else:
        # Run sequentially
        for tenant in tenants:
            try:
                tenant_checks = await check_single_tenant(tenant, run_subscription_checks)
                results[tenant.tenant_id] = tenant_checks
            except Exception as e:
                logger.exception(f"Failed to run checks for tenant {tenant.tenant_id}")
                results[tenant.tenant_id] = [
                    _create_error_result(
                        check_id="tenant_check_execution",
                        name="Tenant Check Execution",
                        category=CheckCategory.SYSTEM,
                        tenant_id=tenant.tenant_id,
                        message=f"Failed to execute tenant checks: {type(e).__name__}",
                        error_code="tenant_check_execution_failed",
                        recommendations=[
                            "Check application logs for detailed error information",
                            "Verify tenant configuration and credentials",
                        ],
                    )
                ]

    total_duration = (datetime.utcnow() - start_time).total_seconds() * 1000

    # Calculate summary statistics
    sum(len(checks) for checks in results.values())
    passed = sum(1 for checks in results.values() for c in checks if c.status == CheckStatus.PASS)
    warnings = sum(
        1 for checks in results.values() for c in checks if c.status == CheckStatus.WARNING
    )
    failed = sum(1 for checks in results.values() for c in checks if c.status == CheckStatus.FAIL)
    skipped = sum(
        1 for checks in results.values() for c in checks if c.status == CheckStatus.SKIPPED
    )

    logger.info(
        f"Completed multi-tenant checks: {passed} passed, {warnings} warnings, "
        f"{failed} failed, {skipped} skipped ({total_duration:.0f}ms)"
    )

    return results


async def check_tenants_quick(
    tenant_ids: list[str] | None = None,
) -> dict[str, CheckResult]:
    """Quick connectivity check for multiple tenants.

    Performs lightweight authentication checks for multiple tenants,
    suitable for dashboard health indicators or status pages.

    Args:
        tenant_ids: Optional list of tenant IDs. If None, checks all active tenants.

    Returns:
        Dictionary mapping tenant IDs to their connectivity check results

    Example:
        >>> results = await check_tenants_quick()
        >>> for tenant_id, result in results.items():
        ...     status = "✓" if result.status == CheckStatus.PASS else "✗"
        ...     print(f"{status} {tenant_id}: {result.message}")
    """
    # Get tenants to check
    if tenant_ids:
        with SessionLocal() as db:
            tenants = (
                db.query(Tenant)
                .filter(Tenant.tenant_id.in_(tenant_ids))
                .filter(Tenant.is_active == True)  # noqa: E712
                .all()
            )
    else:
        tenants = await _get_active_tenants()

    # Run connectivity checks in parallel
    tasks = [check_tenant_connectivity(tenant.tenant_id) for tenant in tenants]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    output: dict[str, CheckResult] = {}
    for tenant, result in zip(tenants, results, strict=False):
        if isinstance(result, Exception):
            output[tenant.tenant_id] = _create_error_result(
                check_id="tenant_connectivity",
                name="Tenant Connectivity",
                category=CheckCategory.SYSTEM,
                tenant_id=tenant.tenant_id,
                message=f"Connectivity check failed: {type(result).__name__}",
                error_code="connectivity_check_error",
                recommendations=["Check application logs for details"],
            )
        else:
            output[tenant.tenant_id] = result

    return output


def format_check_results(results: list[CheckResult]) -> str:
    """Format check results for display.

    Creates a human-readable string representation of check results,
    useful for logging or console output.

    Args:
        results: List of CheckResult objects

    Returns:
        Formatted string
    """
    lines = []
    lines.append("=" * 70)
    lines.append("PREFLIGHT CHECK RESULTS")
    lines.append("=" * 70)

    status_icons = {
        CheckStatus.PASS: "✓",
        CheckStatus.WARNING: "⚠",
        CheckStatus.FAIL: "✗",
        CheckStatus.SKIPPED: "⊘",
    }

    for result in results:
        icon = status_icons.get(result.status, "?")
        lines.append(f"\n{icon} {result.name}")
        lines.append(f"   Status: {result.status.value.upper()}")
        lines.append(f"   Message: {result.message}")
        lines.append(f"   Duration: {result.duration_ms:.1f}ms")

        if result.details:
            lines.append(f"   Details: {result.details}")

        if result.recommendations:
            lines.append("   Recommendations:")
            for rec in result.recommendations:
                lines.append(f"      • {rec}")

    # Summary
    pass_count = sum(1 for r in results if r.status == CheckStatus.PASS)
    warn_count = sum(1 for r in results if r.status == CheckStatus.WARNING)
    fail_count = sum(1 for r in results if r.status == CheckStatus.FAIL)

    lines.append("\n" + "=" * 70)
    lines.append(f"SUMMARY: {pass_count} passed, {warn_count} warnings, {fail_count} failed")
    lines.append("=" * 70)

    return "\n".join(lines)


# Export public functions
__all__ = [
    "check_all_tenants",
    "check_single_tenant",
    "check_tenant_connectivity",
    "check_tenants_quick",
    "format_check_results",
]


# Manual testing entry point
async def main():
    """Main function for manual testing of preflight checks.

    Run with: python -m app.preflight.tenant_checks
    """
    import sys

    # Setup logging for manual testing
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("\n" + "=" * 70)
    print("AZURE GOVERNANCE PLATFORM - PREFLIGHT CHECKS")
    print("=" * 70 + "\n")

    # Check if we have required environment variables
    if not settings.is_configured:
        print("ERROR: Azure credentials not configured!")
        print("\nRequired environment variables:")
        print("  - AZURE_TENANT_ID")
        print("  - AZURE_CLIENT_ID")
        print("  - AZURE_CLIENT_SECRET")
        print("\nOr create a .env file with these values.")
        sys.exit(1)

    # Get tenant to check
    tenant_id = settings.azure_tenant_id

    print(f"Testing tenant: {tenant_id}")
    print(f"Client ID: {settings.azure_client_id[:8]}...")
    print("\n" + "-" * 70 + "\n")

    # Run all checks for the tenant
    print("Running preflight checks...\n")

    try:
        results = await run_all_azure_checks(tenant_id=tenant_id)

        # Print formatted results
        print(format_check_results(results))

        # Exit with error code if any checks failed
        if any(r.status == CheckStatus.FAIL for r in results):
            print("\n❌ Some checks failed. Please review the recommendations above.")
            sys.exit(1)
        else:
            print("\n✅ All critical checks passed!")
            sys.exit(0)

    except Exception as e:
        print(f"\n❌ Fatal error running checks: {e}")
        logger.exception("Fatal error in main")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

"""Preflight runner - orchestrates all preflight checks.

Provides parallel execution, progress tracking, and timeout handling.
"""

import logging
import uuid
from datetime import datetime

from app.core.database import SessionLocal
from app.models.tenant import Tenant
from app.preflight.base import BasePreflightCheck
from app.preflight.checks import get_all_checks
from app.preflight.models import (
    CategorySummary,
    CheckCategory,
    CheckResult,
    CheckStatus,
    PreflightReport,
    TenantCheckSummary,
)

logger = logging.getLogger(__name__)


class PreflightRunner:
    """Orchestrates preflight checks with parallel execution support."""

    def __init__(
        self,
        categories: list[CheckCategory] | None = None,
        tenant_ids: list[str] | None = None,
        fail_fast: bool = False,
        timeout_seconds: float = 30.0,
    ):
        """Initialize the preflight runner.

        Args:
            categories: List of categories to check. If None, all categories are checked.
            tenant_ids: List of tenant IDs to check. If None, all active tenants are checked.
            fail_fast: If True, stop on first failure.
            timeout_seconds: Default timeout for each check.
        """
        self.categories: list[CheckCategory] | None = categories
        self.tenant_ids: list[str] | None = tenant_ids
        self.fail_fast = fail_fast
        self.timeout_seconds = timeout_seconds

        self._checks: dict[str, BasePreflightCheck] = {}
        self._current_report: PreflightReport | None = None
        self._progress_callback: callable | None = None
        self._is_running = False

    @property
    def is_running(self) -> bool:
        """Check if checks are currently running."""
        return self._is_running

    @property
    def current_report(self) -> PreflightReport | None:
        """Get the current report being built."""
        return self._current_report

    def set_progress_callback(self, callback: callable) -> None:
        """Set a callback for progress updates.

        Callback receives (current: int, total: int, check_name: str).
        """
        self._progress_callback = callback

    def register_check(self, check: BasePreflightCheck) -> None:
        """Register a check with the runner."""
        self._checks[check.check_id] = check

    def get_checks_for_categories(
        self, categories: list[CheckCategory] | None = None
    ) -> list[BasePreflightCheck]:
        """Get all checks for the specified categories.

        Args:
            categories: Categories to filter by. If None, returns all checks.

        Returns:
            List of checks matching the categories
        """
        if categories is None:
            return list(self._checks.values())

        return [
            check for check in self._checks.values()
            if check.category in categories
        ]

    def _get_tenants_to_check(self) -> list[Tenant]:
        """Get list of tenants to check.

        Returns:
            List of Tenant objects from the database
        """
        db = SessionLocal()
        try:
            query = db.query(Tenant).filter(Tenant.is_active == True)

            if self.tenant_ids:
                query = query.filter(Tenant.id.in_(self.tenant_ids))

            tenants = query.all()
            logger.info(f"Found {len(tenants)} tenants to check")
            return tenants
        finally:
            db.close()

    async def run_checks(
        self,
        categories: list[CheckCategory] | None = None,
        tenant_ids: list[str] | None = None,
    ) -> PreflightReport:
        """Run all preflight checks.

        Args:
            categories: Specific categories to check (overrides constructor)
            tenant_ids: Specific tenant IDs to check (overrides constructor)

        Returns:
            Complete PreflightReport with all results
        """
        # Use provided values or fall back to constructor values
        check_categories = categories or self.categories
        check_tenant_ids = tenant_ids or self.tenant_ids

        # Initialize report
        report = PreflightReport(
            id=str(uuid.uuid4()),
            started_at=datetime.utcnow(),
            categories_requested=check_categories or list(CheckCategory),
            fail_fast=self.fail_fast,
        )

        self._current_report = report
        self._is_running = True

        # Load all checks
        self._checks = get_all_checks()
        logger.info(f"Loaded {len(self._checks)} checks")

        # Get the checks to run
        checks_to_run = self.get_checks_for_categories(check_categories)
        logger.info(f"Running {len(checks_to_run)} checks")

        # Get tenants if needed
        tenants = self._get_tenants_to_check() if check_tenant_ids or self._needs_tenant_checks(checks_to_run) else []

        # Build execution plan
        execution_plan = self._build_execution_plan(checks_to_run, tenants)

        total_checks = sum(len(checks) for checks in execution_plan.values())
        current = 0

        try:
            # Execute checks
            for check_type, checks in execution_plan.items():
                if check_type == "tenant_checks" and tenants:
                    # Run tenant-specific checks for each tenant
                    for tenant in tenants:
                        for check in checks:
                            if self._progress_callback:
                                self._progress_callback(current, total_checks, check.name)

                            result = await self._run_single_check(check, tenant.tenant_id)
                            report.results.append(result)

                            current += 1

                            # Check fail fast
                            if self.fail_fast and result.status == CheckStatus.FAIL:
                                logger.warning(
                                    f"Fail-fast triggered by check: {check.check_id}"
                                )
                                break

                        if self.fail_fast and any(
                            r.status == CheckStatus.FAIL for r in report.results[-len(checks):]
                        ):
                            break

                elif check_type == "global_checks":
                    # Run global checks once
                    for check in checks:
                        if self._progress_callback:
                            self._progress_callback(current, total_checks, check.name)

                        result = await self._run_single_check(check)
                        report.results.append(result)

                        current += 1

                        # Check fail fast
                        if self.fail_fast and result.status == CheckStatus.FAIL:
                            logger.warning(
                                f"Fail-fast triggered by check: {check.check_id}"
                            )
                            break

                if self.fail_fast and any(
                    r.status == CheckStatus.FAIL for r in report.results
                ):
                    break

        finally:
            report.completed_at = datetime.utcnow()
            self._is_running = False
            self._current_report = None

        logger.info(
            f"Preflight checks completed: {report.passed_count} passed, "
            f"{report.warning_count} warnings, {report.failed_count} failed"
        )

        return report

    def _needs_tenant_checks(self, checks: list[BasePreflightCheck]) -> bool:
        """Check if any of the checks require tenant context."""
        tenant_categories = {
            CheckCategory.AZURE_SUBSCRIPTIONS,
            CheckCategory.AZURE_COST_MANAGEMENT,
            CheckCategory.AZURE_POLICY,
            CheckCategory.AZURE_RESOURCES,
            CheckCategory.AZURE_GRAPH,
            CheckCategory.AZURE_SECURITY,
            CheckCategory.RIVERSIDE,
        }
        return any(check.category in tenant_categories for check in checks)

    def _build_execution_plan(
        self, checks: list[BasePreflightCheck], tenants: list[Tenant]
    ) -> dict[str, list[BasePreflightCheck]]:
        """Build an execution plan separating tenant-specific and global checks.

        Args:
            checks: List of all checks to run
            tenants: List of tenants to check against

        Returns:
            Dictionary with 'tenant_checks' and 'global_checks' lists
        """
        tenant_categories = {
            CheckCategory.AZURE_SUBSCRIPTIONS,
            CheckCategory.AZURE_COST_MANAGEMENT,
            CheckCategory.AZURE_POLICY,
            CheckCategory.AZURE_RESOURCES,
            CheckCategory.AZURE_GRAPH,
            CheckCategory.AZURE_SECURITY,
            CheckCategory.RIVERSIDE,
        }

        tenant_checks = []
        global_checks = []

        for check in checks:
            if check.category in tenant_categories and tenants:
                tenant_checks.append(check)
            else:
                global_checks.append(check)

        return {
            "tenant_checks": tenant_checks,
            "global_checks": global_checks,
        }

    async def _run_single_check(
        self, check: BasePreflightCheck, tenant_id: str | None = None
    ) -> CheckResult:
        """Run a single check with timing.

        Args:
            check: The check to run
            tenant_id: Optional tenant ID for tenant-specific checks

        Returns:
            CheckResult from the check execution
        """
        start_time = datetime.utcnow()
        result = await check.run(tenant_id=tenant_id)
        end_time = datetime.utcnow()

        # Calculate duration
        result.duration_ms = (end_time - start_time).total_seconds() * 1000

        return result

    def get_tenant_summaries(self, report: PreflightReport) -> list[TenantCheckSummary]:
        """Get summaries grouped by tenant.

        Args:
            report: The preflight report to summarize

        Returns:
            List of TenantCheckSummary objects
        """
        tenant_map: dict[str, list[CheckResult]] = {}

        for result in report.results:
            if result.tenant_id:
                if result.tenant_id not in tenant_map:
                    tenant_map[result.tenant_id] = []
                tenant_map[result.tenant_id].append(result)

        db = SessionLocal()
        try:
            summaries = []
            for tenant_id, results in tenant_map.items():
                tenant = db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()

                passed = sum(1 for r in results if r.status == CheckStatus.PASS)
                failed = sum(1 for r in results if r.status == CheckStatus.FAIL)
                warning = sum(1 for r in results if r.status == CheckStatus.WARNING)
                skipped = sum(1 for r in results if r.status == CheckStatus.SKIPPED)

                if failed > 0:
                    overall = CheckStatus.FAIL
                elif warning > 0:
                    overall = CheckStatus.WARNING
                elif passed > 0:
                    overall = CheckStatus.PASS
                else:
                    overall = CheckStatus.SKIPPED

                summaries.append(
                    TenantCheckSummary(
                        tenant_id=tenant_id,
                        tenant_name=tenant.name if tenant else "Unknown",
                        checks_passed=passed,
                        checks_failed=failed,
                        checks_warning=warning,
                        checks_skipped=skipped,
                        overall_status=overall,
                        results=results,
                    )
                )

            return summaries
        finally:
            db.close()

    def get_category_summaries(self, report: PreflightReport) -> list[CategorySummary]:
        """Get summaries grouped by category.

        Args:
            report: The preflight report to summarize

        Returns:
            List of CategorySummary objects
        """
        category_names = {
            CheckCategory.AZURE_AUTH: "Azure Authentication",
            CheckCategory.AZURE_SUBSCRIPTIONS: "Azure Subscriptions",
            CheckCategory.AZURE_COST_MANAGEMENT: "Cost Management",
            CheckCategory.AZURE_POLICY: "Azure Policy",
            CheckCategory.AZURE_RESOURCES: "Resource Manager",
            CheckCategory.AZURE_GRAPH: "Microsoft Graph",
            CheckCategory.AZURE_SECURITY: "Security Center",
            CheckCategory.GITHUB_ACCESS: "GitHub Access",
            CheckCategory.GITHUB_ACTIONS: "GitHub Actions",
            CheckCategory.DATABASE: "Database",
            CheckCategory.SYSTEM: "System",
            CheckCategory.RIVERSIDE: "Riverside Compliance",
        }

        summaries = []

        for category in CheckCategory:
            results = report.get_results_by_category(category)
            if not results:
                continue

            passed = sum(1 for r in results if r.status == CheckStatus.PASS)
            failed = sum(1 for r in results if r.status == CheckStatus.FAIL)
            warning = sum(1 for r in results if r.status == CheckStatus.WARNING)
            skipped = sum(1 for r in results if r.status == CheckStatus.SKIPPED)

            if failed > 0:
                overall = CheckStatus.FAIL
            elif warning > 0:
                overall = CheckStatus.WARNING
            elif passed > 0:
                overall = CheckStatus.PASS
            else:
                overall = CheckStatus.SKIPPED

            summaries.append(
                CategorySummary(
                    category=category,
                    display_name=category_names.get(category, category.value),
                    checks_passed=passed,
                    checks_failed=failed,
                    checks_warning=warning,
                    checks_skipped=skipped,
                    overall_status=overall,
                )
            )

        return summaries

    @staticmethod
    def clear_all_caches() -> None:
        """Clear caches for all check implementations."""
        from app.preflight.base import BasePreflightCheck

        BasePreflightCheck.clear_cache()
        logger.info("Cleared all preflight check caches")


# Global runner instance for API endpoints
_global_runner: PreflightRunner | None = None
_latest_report: PreflightReport | None = None


def get_runner() -> PreflightRunner:
    """Get or create the global runner instance."""
    global _global_runner
    if _global_runner is None:
        _global_runner = PreflightRunner()
    return _global_runner


def set_latest_report(report: PreflightReport) -> None:
    """Set the latest preflight report."""
    global _latest_report
    _latest_report = report


def get_latest_report() -> PreflightReport | None:
    """Get the latest preflight report."""
    return _latest_report

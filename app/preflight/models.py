"""Pydantic models for preflight checks."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CheckStatus(str, Enum):
    """Enumeration of possible check statuses."""

    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    SKIPPED = "skipped"
    RUNNING = "running"


class CheckCategory(str, Enum):
    """Categories of preflight checks."""

    # Azure checks
    AZURE_AUTH = "azure_auth"
    AZURE_SUBSCRIPTIONS = "azure_subscriptions"
    AZURE_COST_MANAGEMENT = "azure_cost_management"
    AZURE_POLICY = "azure_policy"
    AZURE_RESOURCES = "azure_resources"
    AZURE_GRAPH = "azure_graph"
    AZURE_SECURITY = "azure_security"

    # GitHub checks
    GITHUB_ACCESS = "github_access"
    GITHUB_ACTIONS = "github_actions"

    # Database checks
    DATABASE = "database"

    # System checks
    SYSTEM = "system"

    # Riverside checks
    RIVERSIDE = "riverside"


class CheckResult(BaseModel):
    """Result of a single preflight check."""

    check_id: str = Field(..., description="Unique identifier for the check")
    name: str = Field(..., description="Human-readable name of the check")
    category: CheckCategory = Field(..., description="Category this check belongs to")
    status: CheckStatus = Field(..., description="Current status of the check")
    message: str = Field(..., description="Human-readable description of the result")
    details: dict[str, Any] = Field(
        default_factory=dict, description="Technical details and error messages"
    )
    duration_ms: float = Field(0, description="Execution time in milliseconds")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When this check was run"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="List of fix recommendations"
    )
    tenant_id: str | None = Field(
        None, description="Tenant ID if this check is tenant-specific"
    )

    model_config = {"from_attributes": True}

    def is_pass(self) -> bool:
        """Check if the result is a pass."""
        return self.status == CheckStatus.PASS

    def is_warning(self) -> bool:
        """Check if the result is a warning."""
        return self.status == CheckStatus.WARNING

    def is_fail(self) -> bool:
        """Check if the result is a failure."""
        return self.status == CheckStatus.FAIL

    def is_skipped(self) -> bool:
        """Check if the check was skipped."""
        return self.status == CheckStatus.SKIPPED

    def is_success(self) -> bool:
        """Check if the result indicates success (pass or warning)."""
        return self.status in (CheckStatus.PASS, CheckStatus.WARNING)


class PreflightReport(BaseModel):
    """Complete preflight check report."""

    id: str = Field(..., description="Unique identifier for this report")
    started_at: datetime = Field(
        default_factory=datetime.utcnow, description="When the check run started"
    )
    completed_at: datetime | None = Field(
        None, description="When the check run completed"
    )
    results: list[CheckResult] = Field(
        default_factory=list, description="Results of all checks"
    )
    categories_requested: list[CheckCategory] = Field(
        default_factory=list, description="Categories that were checked"
    )
    fail_fast: bool = Field(False, description="Whether fail-fast mode was enabled")

    model_config = {"from_attributes": True}

    @property
    def passed_count(self) -> int:
        """Get count of passed checks."""
        return sum(1 for r in self.results if r.status == CheckStatus.PASS)

    @property
    def warning_count(self) -> int:
        """Get count of warnings."""
        return sum(1 for r in self.results if r.status == CheckStatus.WARNING)

    @property
    def failed_count(self) -> int:
        """Get count of failed checks."""
        return sum(1 for r in self.results if r.status == CheckStatus.FAIL)

    @property
    def skipped_count(self) -> int:
        """Get count of skipped checks."""
        return sum(1 for r in self.results if r.status == CheckStatus.SKIPPED)

    @property
    def total_duration_ms(self) -> float:
        """Get total execution time."""
        return sum(r.duration_ms for r in self.results)

    @property
    def is_success(self) -> bool:
        """Check if all checks passed."""
        return self.failed_count == 0

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return self.warning_count > 0

    @property
    def has_failures(self) -> bool:
        """Check if there are any failures."""
        return self.failed_count > 0

    def get_results_by_category(
        self, category: CheckCategory
    ) -> list[CheckResult]:
        """Get all results for a specific category."""
        return [r for r in self.results if r.category == category]

    def get_failed_checks(self) -> list[CheckResult]:
        """Get all failed checks."""
        return [r for r in self.results if r.status == CheckStatus.FAIL]

    def get_all_recommendations(self) -> list[str]:
        """Get all recommendations from failed checks."""
        recommendations = []
        for result in self.get_failed_checks():
            recommendations.extend(result.recommendations)
        return recommendations

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the report."""
        return {
            "id": self.id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "passed": self.passed_count,
            "warnings": self.warning_count,
            "failed": self.failed_count,
            "skipped": self.skipped_count,
            "total": len(self.results),
            "duration_ms": self.total_duration_ms,
            "is_success": self.is_success,
            "has_warnings": self.has_warnings,
            "has_failures": self.has_failures,
        }


class PreflightCheckRequest(BaseModel):
    """Request model for running preflight checks."""

    categories: list[CheckCategory] | None = Field(
        None,
        description="Categories to check. If None, all categories will be checked.",
    )
    tenant_ids: list[str] | None = Field(
        None,
        description="Specific tenant IDs to check. If None, all active tenants will be checked.",
    )
    fail_fast: bool = Field(
        False,
        description="Stop on first failure. If True, the runner will stop executing checks after the first failure.",
    )
    timeout_seconds: float = Field(
        30.0,
        description="Timeout for each individual check in seconds.",
    )


class PreflightStatusResponse(BaseModel):
    """Response model for preflight status endpoint."""

    latest_report: PreflightReport | None = Field(
        None, description="The most recent preflight report"
    )
    last_run_at: datetime | None = Field(
        None, description="When the last check run was initiated"
    )
    is_running: bool = Field(False, description="Whether checks are currently running")


class TenantCheckSummary(BaseModel):
    """Summary of checks for a specific tenant."""

    tenant_id: str
    tenant_name: str
    checks_passed: int
    checks_failed: int
    checks_warning: int
    checks_skipped: int
    overall_status: CheckStatus
    results: list[CheckResult]


class CategorySummary(BaseModel):
    """Summary of checks by category."""

    category: CheckCategory
    display_name: str
    checks_passed: int
    checks_failed: int
    checks_warning: int
    checks_skipped: int
    overall_status: CheckStatus

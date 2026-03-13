"""Report generation for preflight checks.

Provides HTML, JSON, and markdown output formats with summary statistics
and failed check recommendations.
"""

import json
import logging
from typing import Any

from app.preflight.models import (
    CheckCategory,
    CheckResult,
    CheckStatus,
    PreflightReport,
)

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generate reports from preflight check results."""

    def __init__(self, report: PreflightReport):
        """Initialize the report generator.

        Args:
            report: The preflight report to generate reports from
        """
        self.report = report

    def to_json(self, pretty: bool = True) -> str:
        """Generate JSON report.

        Args:
            pretty: Whether to pretty-print the JSON

        Returns:
            JSON string representation of the report
        """
        data = {
            "id": self.report.id,
            "started_at": self.report.started_at.isoformat(),
            "completed_at": self.report.completed_at.isoformat()
            if self.report.completed_at
            else None,
            "summary": {
                "passed": self.report.passed_count,
                "warnings": self.report.warning_count,
                "failed": self.report.failed_count,
                "skipped": self.report.skipped_count,
                "total": len(self.report.results),
                "duration_ms": self.report.total_duration_ms,
                "is_success": self.report.is_success,
            },
            "categories_requested": [cat.value for cat in self.report.categories_requested],
            "fail_fast": self.report.fail_fast,
            "results": [
                {
                    "check_id": r.check_id,
                    "name": r.name,
                    "category": r.category.value,
                    "status": r.status.value,
                    "message": r.message,
                    "details": r.details,
                    "duration_ms": r.duration_ms,
                    "timestamp": r.timestamp.isoformat(),
                    "recommendations": r.recommendations,
                    "tenant_id": r.tenant_id,
                }
                for r in self.report.results
            ],
        }

        if pretty:
            return json.dumps(data, indent=2)
        return json.dumps(data)

    def to_markdown(self) -> str:
        """Generate Markdown report.

        Returns:
            Markdown string representation of the report
        """
        lines = [
            "# Preflight Check Report",
            "",
            f"**Report ID:** `{self.report.id}`",
            f"**Started:** {self.report.started_at.strftime('%Y-%m-%d %H:%M:%S')} UTC",
        ]

        if self.report.completed_at:
            lines.append(
                f"**Completed:** {self.report.completed_at.strftime('%Y-%m-%d %H:%M:%S')} UTC"
            )

        lines.extend(
            [
                "",
                "## Summary",
                "",
                f"- ✅ **Passed:** {self.report.passed_count}",
                f"- ⚠️ **Warnings:** {self.report.warning_count}",
                f"- ❌ **Failed:** {self.report.failed_count}",
                f"- ⏭️ **Skipped:** {self.report.skipped_count}",
                f"- 📊 **Total:** {len(self.report.results)}",
                f"- ⏱️ **Duration:** {self.report.total_duration_ms:.2f}ms",
                "",
            ]
        )

        if self.report.is_success:
            status_emoji = "✅"
            status_text = "SUCCESS"
        else:
            status_emoji = "❌"
            status_text = "FAILED"

        lines.extend(
            [
                f"## Overall Status: {status_emoji} **{status_text}**",
                "",
            ]
        )

        # Group results by category
        category_groups: dict[CheckCategory, list[CheckResult]] = {}
        for result in self.report.results:
            if result.category not in category_groups:
                category_groups[result.category] = []
            category_groups[result.category].append(result)

        for category, results in category_groups.items():
            lines.append(f"### {self._get_category_display_name(category)}")
            lines.append("")

            for result in results:
                status_emoji = self._get_status_emoji(result.status)
                lines.append(f"- {status_emoji} **{result.name}**: {result.message}")

                if result.status == CheckStatus.FAIL and result.recommendations:
                    lines.append("  - Recommendations:")
                    for rec in result.recommendations:
                        lines.append(f"    - {rec}")

            lines.append("")

        # Add failed check details
        failed_checks = self.report.get_failed_checks()
        if failed_checks:
            lines.extend(
                [
                    "## Failed Check Details",
                    "",
                ]
            )

            for result in failed_checks:
                lines.extend(
                    [
                        f"### {result.name}",
                        "",
                        f"**Status:** {result.status.value}",
                        "",
                        f"**Message:** {result.message}",
                        "",
                    ]
                )

                if result.details:
                    lines.append("**Details:**")
                    lines.append("```")
                    for key, value in result.details.items():
                        lines.append(f"{key}: {value}")
                    lines.append("```")
                    lines.append("")

                if result.recommendations:
                    lines.append("**Recommendations:**")
                    for rec in result.recommendations:
                        lines.append(f"- {rec}")
                    lines.append("")

        return "\n".join(lines)

    def to_html(self, include_details: bool = True) -> str:
        """Generate HTML report.

        Args:
            include_details: Whether to include detailed result information

        Returns:
            HTML string representation of the report
        """
        summary = self.report.get_summary()

        html = f"""
<div class="preflight-report">
    <h2>Preflight Check Report</h2>
    <p class="report-meta">
        <strong>Report ID:</strong> {summary["id"]}<br>
        <strong>Started:</strong> {summary["started_at"]}<br>
        {f"<strong>Completed:</strong> {summary['completed_at']}<br>" if summary["completed_at"] else ""}
    </p>

    <div class="summary-cards">
        <div class="summary-card passed">
            <span class="count">{summary["passed"]}</span>
            <span class="label">Passed</span>
        </div>
        <div class="summary-card warning">
            <span class="count">{summary["warnings"]}</span>
            <span class="label">Warnings</span>
        </div>
        <div class="summary-card failed">
            <span class="count">{summary["failed"]}</span>
            <span class="label">Failed</span>
        </div>
        <div class="summary-card skipped">
            <span class="count">{summary["skipped"]}</span>
            <span class="label">Skipped</span>
        </div>
    </div>

    <div class="overall-status {("success" if summary["is_success"] else "failure")}">
        {"✅ All checks passed!" if summary["is_success"] else "❌ Some checks failed"}
    </div>
"""

        if include_details:
            # Group results by category
            category_groups: dict[CheckCategory, list[CheckResult]] = {}
            for result in self.report.results:
                if result.category not in category_groups:
                    category_groups[result.category] = []
                category_groups[result.category].append(result)

            for category, results in category_groups.items():
                html += f"\n    <h3>{self._get_category_display_name(category)}</h3>\n"
                html += '    <ul class="check-list">\n'

                for result in results:
                    status_class = result.status.value
                    status_emoji = self._get_status_emoji(result.status)

                    html += f"""
        <li class="check-item {status_class}">
            <span class="status">{status_emoji}</span>
            <span class="name">{result.name}</span>
            <span class="message">{result.message}</span>
        </li>
"""

                    if result.status == CheckStatus.FAIL and result.recommendations:
                        html += '        <ul class="recommendations">\n'
                        for rec in result.recommendations:
                            html += f"            <li>{rec}</li>\n"
                        html += "        </ul>\n"

                html += "    </ul>\n"

        html += "</div>"

        return html

    def get_summary_statistics(self) -> dict[str, Any]:
        """Get detailed summary statistics.

        Returns:
            Dictionary with summary statistics
        """
        total = len(self.report.results)
        if total == 0:
            return {
                "total_checks": 0,
                "pass_rate": 0.0,
                "fail_rate": 0.0,
            }

        return {
            "total_checks": total,
            "passed": self.report.passed_count,
            "warnings": self.report.warning_count,
            "failed": self.report.failed_count,
            "skipped": self.report.skipped_count,
            "pass_rate": (self.report.passed_count / total) * 100,
            "fail_rate": (self.report.failed_count / total) * 100,
            "total_duration_ms": self.report.total_duration_ms,
            "average_duration_ms": self.report.total_duration_ms / total if total > 0 else 0,
            "is_success": self.report.is_success,
            "has_warnings": self.report.has_warnings,
            "has_failures": self.report.has_failures,
        }

    def get_failed_checks_with_recommendations(
        self,
    ) -> list[dict[str, Any]]:
        """Get detailed information about failed checks and recommendations.

        Returns:
            List of dictionaries with failed check details
        """
        failed = []

        for result in self.report.get_failed_checks():
            failed.append(
                {
                    "check_id": result.check_id,
                    "name": result.name,
                    "category": result.category.value,
                    "status": result.status.value,
                    "message": result.message,
                    "details": result.details,
                    "duration_ms": result.duration_ms,
                    "recommendations": result.recommendations,
                    "tenant_id": result.tenant_id,
                }
            )

        return failed

    def _get_status_emoji(self, status: CheckStatus) -> str:
        """Get emoji for a check status."""
        mapping = {
            CheckStatus.PASS: "✅",
            CheckStatus.WARNING: "⚠️",
            CheckStatus.FAIL: "❌",
            CheckStatus.SKIPPED: "⏭️",
            CheckStatus.RUNNING: "🔄",
        }
        return mapping.get(status, "❓")

    def _get_category_display_name(self, category: CheckCategory) -> str:
        """Get human-readable category name."""
        names = {
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
        }
        return names.get(category, category.value)


def generate_report(
    report: PreflightReport,
    format: str = "json",
) -> str:
    """Generate a report in the specified format.

    Args:
        report: The preflight report to generate
        format: Output format ('json', 'markdown', or 'html')

    Returns:
        Formatted report string

    Raises:
        ValueError: If an unsupported format is specified
    """
    generator = ReportGenerator(report)

    format_mapping = {
        "json": generator.to_json,
        "markdown": generator.to_markdown,
        "md": generator.to_markdown,
        "html": generator.to_html,
    }

    if format not in format_mapping:
        raise ValueError(
            f"Unsupported format: {format}. Supported formats: {', '.join(format_mapping.keys())}"
        )

    return format_mapping[format]()


def get_recommendations_for_failed_checks(
    report: PreflightReport,
) -> list[str]:
    """Get all unique recommendations from failed checks.

    Args:
        report: The preflight report

    Returns:
        List of unique recommendation strings
    """
    recommendations = set()

    for result in report.get_failed_checks():
        for rec in result.recommendations:
            recommendations.add(rec)

    return sorted(recommendations)

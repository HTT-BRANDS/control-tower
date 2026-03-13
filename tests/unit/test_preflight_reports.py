"""Unit tests for ReportGenerator.

Tests for preflight check report generation in multiple formats (JSON, Markdown)
with summary statistics and error handling.

6 tests covering:
- JSON report generation
- Markdown report generation
- Summary statistics calculation
- Empty results handling
"""

import json
from datetime import datetime, timedelta

from app.preflight.models import (
    CheckCategory,
    CheckResult,
    CheckStatus,
    PreflightReport,
)
from app.preflight.reports import ReportGenerator


class TestJSONReportGeneration:
    """Tests for JSON report generation."""

    def test_to_json_basic_structure(self):
        """Test JSON report contains required fields."""
        results = [
            CheckResult(
                check_id="check1",
                name="Security Check",
                category=CheckCategory.AZURE_SECURITY,
                status=CheckStatus.PASS,
                message="Check passed",
            ),
            CheckResult(
                check_id="check2",
                name="Compliance Check",
                category=CheckCategory.MFA_COMPLIANCE,
                status=CheckStatus.FAIL,
                message="Check failed",
            ),
        ]

        report = PreflightReport(
            id="test-run",
            results=results,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow() + timedelta(seconds=5),
            categories_requested=[CheckCategory.AZURE_SECURITY, CheckCategory.MFA_COMPLIANCE],
            fail_fast=False,
        )

        generator = ReportGenerator(report)
        json_output = generator.to_json(pretty=True)

        # Parse JSON to verify structure
        data = json.loads(json_output)

        assert "summary" in data
        assert "results" in data
        assert "categories_requested" in data
        assert data["summary"]["total"] == 2
        assert len(data["results"]) == 2

    def test_to_json_summary_counts(self):
        """Test JSON report has correct summary counts."""
        results = [
            CheckResult(
                check_id="c1",
                name="Check 1",
                category=CheckCategory.SYSTEM,
                status=CheckStatus.PASS,
                message="Pass",
            ),
            CheckResult(
                check_id="c2",
                name="Check 2",
                category=CheckCategory.SYSTEM,
                status=CheckStatus.PASS,
                message="Pass",
            ),
            CheckResult(
                check_id="c3",
                name="Check 3",
                category=CheckCategory.SYSTEM,
                status=CheckStatus.FAIL,
                message="Fail",
            ),
            CheckResult(
                check_id="c4",
                name="Check 4",
                category=CheckCategory.SYSTEM,
                status=CheckStatus.WARNING,
                message="Warn",
            ),
            CheckResult(
                check_id="c5",
                name="Check 5",
                category=CheckCategory.SYSTEM,
                status=CheckStatus.SKIPPED,
                message="Skip",
            ),
        ]

        report = PreflightReport(
            id="test-run",
            results=results,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            categories_requested=[],
            fail_fast=False,
        )

        generator = ReportGenerator(report)
        json_output = generator.to_json(pretty=False)
        data = json.loads(json_output)

        assert data["summary"]["passed"] == 2
        assert data["summary"]["failed"] == 1
        assert data["summary"]["warnings"] == 1
        assert data["summary"]["skipped"] == 1
        assert data["summary"]["total"] == 5

    def test_to_json_includes_result_details(self):
        """Test JSON report includes detailed result information."""
        result = CheckResult(
            check_id="detailed_check",
            name="Detailed Check",
            category=CheckCategory.AZURE_SECURITY,
            status=CheckStatus.FAIL,
            message="Failed with details",
            details={"reason": "Insufficient permissions", "code": 403},
            recommendations=["Grant required permissions"],
            tenant_id="test-tenant",
        )

        report = PreflightReport(
            id="test-run",
            results=[result],
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            categories_requested=[],
            fail_fast=False,
        )

        generator = ReportGenerator(report)
        json_output = generator.to_json()
        data = json.loads(json_output)

        result_data = data["results"][0]
        assert result_data["check_id"] == "detailed_check"
        assert result_data["name"] == "Detailed Check"
        assert result_data["category"] == "azure_security"
        assert result_data["status"] == "fail"
        assert result_data["message"] == "Failed with details"
        assert result_data["details"] == {"reason": "Insufficient permissions", "code": 403}
        assert result_data["recommendations"] == ["Grant required permissions"]
        assert result_data["tenant_id"] == "test-tenant"


class TestMarkdownReportGeneration:
    """Tests for Markdown report generation."""

    def test_to_markdown_basic_structure(self):
        """Test Markdown report has proper structure."""
        results = [
            CheckResult(
                check_id="check1",
                name="Test Check",
                category=CheckCategory.AZURE_SECURITY,
                status=CheckStatus.PASS,
                message="Check passed",
            ),
        ]

        report = PreflightReport(
            id="test-run",
            results=results,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            categories_requested=[CheckCategory.AZURE_SECURITY],
            fail_fast=False,
        )

        generator = ReportGenerator(report)
        markdown = generator.to_markdown()

        # Should contain header
        assert "# Preflight Check Report" in markdown
        assert "**Report ID:**" in markdown
        assert "**Started:**" in markdown

    def test_to_markdown_includes_summary(self):
        """Test Markdown report includes summary section."""
        results = [
            CheckResult(
                check_id="c1",
                name="Check 1",
                category=CheckCategory.SYSTEM,
                status=CheckStatus.PASS,
                message="Pass",
            ),
            CheckResult(
                check_id="c2",
                name="Check 2",
                category=CheckCategory.SYSTEM,
                status=CheckStatus.FAIL,
                message="Fail",
            ),
        ]

        report = PreflightReport(
            id="test-run",
            results=results,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            categories_requested=[],
            fail_fast=False,
        )

        generator = ReportGenerator(report)
        markdown = generator.to_markdown()

        # Should contain summary statistics
        assert "Summary" in markdown or "## Summary" in markdown


class TestSummaryCalculation:
    """Tests for summary statistics calculation."""

    def test_calculate_summary_stats(self):
        """Test summary statistics are correctly calculated."""
        results = [
            CheckResult(
                check_id="c1",
                name="Check 1",
                category=CheckCategory.SYSTEM,
                status=CheckStatus.PASS,
                message="Pass",
            ),
            CheckResult(
                check_id="c2",
                name="Check 2",
                category=CheckCategory.SYSTEM,
                status=CheckStatus.PASS,
                message="Pass",
            ),
            CheckResult(
                check_id="c3",
                name="Check 3",
                category=CheckCategory.SYSTEM,
                status=CheckStatus.PASS,
                message="Pass",
            ),
            CheckResult(
                check_id="c4",
                name="Check 4",
                category=CheckCategory.SYSTEM,
                status=CheckStatus.FAIL,
                message="Fail",
            ),
            CheckResult(
                check_id="c5",
                name="Check 5",
                category=CheckCategory.SYSTEM,
                status=CheckStatus.WARNING,
                message="Warn",
            ),
        ]

        report = PreflightReport(
            id="test-run",
            results=results,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow() + timedelta(seconds=10),
            categories_requested=[],
            fail_fast=False,
        )

        # Verify counts
        assert report.passed_count == 3
        assert report.failed_count == 1
        assert report.warning_count == 1
        assert report.skipped_count == 0

        # Overall success should be False if any failed
        assert report.is_success is False


class TestEmptyResults:
    """Tests for handling empty results."""

    def test_empty_results_json(self):
        """Test JSON generation with no results."""
        report = PreflightReport(
            id="empty-run",
            results=[],
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            categories_requested=[],
            fail_fast=False,
        )

        generator = ReportGenerator(report)
        json_output = generator.to_json()
        data = json.loads(json_output)

        assert data["summary"]["total"] == 0
        assert data["summary"]["passed"] == 0
        assert data["summary"]["failed"] == 0
        assert len(data["results"]) == 0

    def test_empty_results_markdown(self):
        """Test Markdown generation with no results."""
        report = PreflightReport(
            id="empty-run",
            results=[],
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            categories_requested=[],
            fail_fast=False,
        )

        generator = ReportGenerator(report)
        markdown = generator.to_markdown()

        # Should still have valid structure
        assert "# Preflight Check Report" in markdown
        assert "**Report ID:**" in markdown

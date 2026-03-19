"""Tests for CM-005: Automated remediation suggestions.

Expands coverage of riverside_compliance.py from smoke-only to proper
unit-level testing of calculate_compliance_summary() and analyze_mfa_gaps().
"""
from datetime import date, datetime
from unittest.mock import MagicMock

import pytest


def _make_compliance_record(
    tenant_id: str,
    overall_maturity_score: float = 2.5,
    critical_gaps_count: int = 5,
    requirements_total: int = 72,
    requirements_completed: int = 36,
    created_at: datetime | None = None,
):
    """Factory for RiversideCompliance-shaped mock objects."""
    record = MagicMock()
    record.tenant_id = tenant_id
    record.overall_maturity_score = overall_maturity_score
    record.critical_gaps_count = critical_gaps_count
    record.requirements_total = requirements_total
    record.requirements_completed = requirements_completed
    record.created_at = created_at or datetime(2026, 3, 1)
    return record


def _make_mfa_record(
    tenant_id: str,
    mfa_coverage_percentage: float = 75.0,
    admin_mfa_coverage_percentage: float = 90.0,
    total_users: int = 100,
    mfa_enabled_users: int = 75,
    admin_users: int = 10,
    admin_mfa_enabled: int = 9,
    snapshot_date: date | None = None,
):
    """Factory for RiversideMFA-shaped mock objects.

    Sets both the canonical field names used by the test parameters AND the
    field names the service actually reads (admin_mfa_percentage, unprotected_users).
    """
    record = MagicMock()
    record.tenant_id = tenant_id
    record.mfa_coverage_percentage = mfa_coverage_percentage
    record.admin_mfa_coverage_percentage = admin_mfa_coverage_percentage
    # Fields the service actually reads from the model:
    record.admin_mfa_percentage = admin_mfa_coverage_percentage
    record.unprotected_users = total_users - mfa_enabled_users
    record.total_users = total_users
    record.mfa_enabled_users = mfa_enabled_users
    record.admin_users = admin_users
    record.admin_mfa_enabled = admin_mfa_enabled
    record.snapshot_date = snapshot_date or date(2026, 3, 1)
    return record


def _make_db_with_compliance(records):
    """Build a mock db session that returns compliance records via join query."""
    mock_db = MagicMock()
    # Chain: db.query().group_by().subquery() → subquery
    subquery = MagicMock()
    mock_db.query.return_value.group_by.return_value.subquery.return_value = subquery
    # Chain: db.query().join().all() → records
    mock_db.query.return_value.join.return_value.all.return_value = records
    return mock_db


def _make_db_with_mfa(records):
    """Build a mock db session that returns MFA records via join query."""
    mock_db = MagicMock()
    subquery = MagicMock()
    mock_db.query.return_value.group_by.return_value.subquery.return_value = subquery
    joined = MagicMock()
    joined.all.return_value = records
    joined.filter.return_value.all.return_value = records
    mock_db.query.return_value.join.return_value = joined
    return mock_db


class TestCalculateComplianceSummary:
    """Unit tests for calculate_compliance_summary() — CM-005."""

    def test_basic_summary_structure(self):
        """Result should contain all expected keys."""
        from app.api.services.riverside_compliance import calculate_compliance_summary
        record = _make_compliance_record("tenant-1")
        db = _make_db_with_compliance([record])
        result = calculate_compliance_summary(db)
        assert "overall_compliance_percentage" in result
        assert "average_maturity_score" in result
        assert "total_critical_gaps" in result
        assert "tenants_analyzed" in result
        assert "maturity_distribution" in result
        assert "compliance_trend" in result

    def test_empty_data_raises_value_error(self):
        """Should raise ValueError when no compliance records exist."""
        from app.api.services.riverside_compliance import calculate_compliance_summary
        db = _make_db_with_compliance([])
        with pytest.raises(ValueError, match="No compliance data"):
            calculate_compliance_summary(db)

    def test_compliance_percentage_calculation(self):
        """36/72 completed requirements → 50% compliance."""
        from app.api.services.riverside_compliance import calculate_compliance_summary
        record = _make_compliance_record(
            "tenant-1", requirements_total=72, requirements_completed=36
        )
        db = _make_db_with_compliance([record])
        result = calculate_compliance_summary(db)
        assert result["overall_compliance_percentage"] == 50.0

    def test_trend_improving_above_70_percent(self):
        """>=70% completion → trend should be 'improving'."""
        from app.api.services.riverside_compliance import calculate_compliance_summary
        record = _make_compliance_record(
            "tenant-1", requirements_total=100, requirements_completed=75
        )
        db = _make_db_with_compliance([record])
        result = calculate_compliance_summary(db)
        assert result["compliance_trend"] == "improving"

    def test_trend_critical_below_30_percent(self):
        """<30% completion → trend should be 'critical'."""
        from app.api.services.riverside_compliance import calculate_compliance_summary
        record = _make_compliance_record(
            "tenant-1", requirements_total=100, requirements_completed=20
        )
        db = _make_db_with_compliance([record])
        result = calculate_compliance_summary(db)
        assert result["compliance_trend"] == "critical"

    def test_maturity_distribution_below_2(self):
        """Maturity 1.5 should land in 'below_2' bucket."""
        from app.api.services.riverside_compliance import calculate_compliance_summary
        record = _make_compliance_record("tenant-1", overall_maturity_score=1.5)
        db = _make_db_with_compliance([record])
        result = calculate_compliance_summary(db)
        assert result["maturity_distribution"]["below_2"] == 1

    def test_maturity_distribution_above_4(self):
        """Maturity 4.5 should land in 'above_4' bucket."""
        from app.api.services.riverside_compliance import calculate_compliance_summary
        record = _make_compliance_record("tenant-1", overall_maturity_score=4.5)
        db = _make_db_with_compliance([record])
        result = calculate_compliance_summary(db)
        assert result["maturity_distribution"]["above_4"] == 1

    def test_multiple_tenants_aggregation(self):
        """Two tenants should aggregate critical gaps and count correctly."""
        from app.api.services.riverside_compliance import calculate_compliance_summary
        records = [
            _make_compliance_record("tenant-1", critical_gaps_count=3),
            _make_compliance_record("tenant-2", critical_gaps_count=7),
        ]
        db = _make_db_with_compliance(records)
        result = calculate_compliance_summary(db)
        assert result["tenants_analyzed"] == 2
        assert result["total_critical_gaps"] == 10

    def test_tenants_analyzed_count(self):
        """tenants_analyzed should equal number of records returned."""
        from app.api.services.riverside_compliance import calculate_compliance_summary
        records = [_make_compliance_record(f"tenant-{i}") for i in range(4)]
        db = _make_db_with_compliance(records)
        result = calculate_compliance_summary(db)
        assert result["tenants_analyzed"] == 4


class TestAnalyzeMfaGaps:
    """Unit tests for analyze_mfa_gaps() — CM-005 / RM-006 remediation path."""

    def test_basic_result_structure(self):
        """Result should contain all expected keys."""
        from app.api.services.riverside_compliance import analyze_mfa_gaps
        record = _make_mfa_record("tenant-1")
        db = _make_db_with_mfa([record])
        result = analyze_mfa_gaps(db)
        assert "overall_coverage_percentage" in result
        assert "admin_coverage_percentage" in result
        assert "total_unprotected_users" in result
        assert "coverage_gap_percentage" in result
        assert "high_risk_tenants" in result
        assert "tenant_breakdown" in result
        assert "recommendations" in result

    def test_empty_data_raises_value_error(self):
        """Should raise ValueError when no MFA records exist."""
        from app.api.services.riverside_compliance import analyze_mfa_gaps
        db = _make_db_with_mfa([])
        with pytest.raises(ValueError, match="No MFA data"):
            analyze_mfa_gaps(db)

    def test_high_risk_tenant_below_50_percent(self):
        """Tenant with <50% MFA coverage should appear in high_risk_tenants."""
        from app.api.services.riverside_compliance import analyze_mfa_gaps
        record = _make_mfa_record("tenant-1", mfa_coverage_percentage=30.0)
        db = _make_db_with_mfa([record])
        result = analyze_mfa_gaps(db)
        assert len(result["high_risk_tenants"]) >= 1

    def test_no_high_risk_tenants_above_80_percent(self):
        """Tenant with >80% MFA coverage should NOT appear in high_risk_tenants."""
        from app.api.services.riverside_compliance import analyze_mfa_gaps
        record = _make_mfa_record("tenant-1", mfa_coverage_percentage=90.0)
        db = _make_db_with_mfa([record])
        result = analyze_mfa_gaps(db)
        assert len(result["high_risk_tenants"]) == 0

    def test_unprotected_users_calculation(self):
        """total_unprotected_users = total_users - mfa_enabled_users."""
        from app.api.services.riverside_compliance import analyze_mfa_gaps
        record = _make_mfa_record(
            "tenant-1", total_users=100, mfa_enabled_users=75, mfa_coverage_percentage=75.0
        )
        db = _make_db_with_mfa([record])
        result = analyze_mfa_gaps(db)
        assert result["total_unprotected_users"] == 25

    def test_recommendations_list_not_empty(self):
        """Remediation recommendations should always be present."""
        from app.api.services.riverside_compliance import analyze_mfa_gaps
        record = _make_mfa_record("tenant-1", mfa_coverage_percentage=50.0)
        db = _make_db_with_mfa([record])
        result = analyze_mfa_gaps(db)
        assert isinstance(result["recommendations"], list)
        assert len(result["recommendations"]) > 0

    def test_tenant_breakdown_per_tenant(self):
        """tenant_breakdown should have one entry per tenant."""
        from app.api.services.riverside_compliance import analyze_mfa_gaps
        records = [
            _make_mfa_record("tenant-1", mfa_coverage_percentage=80.0),
            _make_mfa_record("tenant-2", mfa_coverage_percentage=40.0),
        ]
        db = _make_db_with_mfa(records)
        result = analyze_mfa_gaps(db)
        assert len(result["tenant_breakdown"]) == 2

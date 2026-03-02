"""Unit tests for MFA compliance preflight checks.

Tests for the mfa_checks.py module to ensure all MFA compliance checks
function correctly and return expected result structures.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from app.preflight.models import CheckCategory, CheckStatus


class TestMFATenantDataCheck:
    """Tests for MFATenantDataCheck."""

    @pytest.fixture
    def check(self):
        """Create a MFATenantDataCheck instance."""
        from app.preflight.mfa_checks import MFATenantDataCheck
        return MFATenantDataCheck()

    def test_check_initialization(self, check):
        """Test check is initialized with correct attributes."""
        assert check.check_id == "mfa_tenant_data"
        assert check.name == "MFA Tenant Data Availability"
        assert check.category == CheckCategory.MFA_COMPLIANCE
        assert check.timeout_seconds == 15.0

    @pytest.mark.asyncio
    async def test_check_no_data(self, check):
        """Test check fails when no MFA data exists."""
        with patch("app.preflight.mfa_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
            mock_db.query.return_value.filter.return_value.count.return_value = 0

            result = await check.run(tenant_id="test-tenant")

            assert result.status == CheckStatus.FAIL
            assert "no mfa data found" in result.message.lower()
            assert result.details["severity"] == "critical"
            assert len(result.recommendations) > 0

    @pytest.mark.asyncio
    async def test_check_stale_data(self, check):
        """Test check warns when MFA data is stale."""
        from app.models.riverside import RiversideMFA

        with patch("app.preflight.mfa_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            # Create stale MFA record (10 days old)
            stale_mfa = MagicMock()
            stale_mfa.snapshot_date = datetime.utcnow() - timedelta(days=10)
            mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = stale_mfa
            mock_db.query.return_value.filter.return_value.count.return_value = 1

            result = await check.run(tenant_id="test-tenant")

            assert result.status == CheckStatus.WARNING
            assert "stale" in result.message.lower()
            assert result.details["severity"] == "warning"

    @pytest.mark.asyncio
    async def test_check_fresh_data(self, check):
        """Test check passes with fresh MFA data."""
        with patch("app.preflight.mfa_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            # Create fresh MFA record (1 day old)
            fresh_mfa = MagicMock()
            fresh_mfa.snapshot_date = datetime.utcnow() - timedelta(days=1)
            mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = fresh_mfa
            mock_db.query.return_value.filter.return_value.count.return_value = 5

            result = await check.run(tenant_id="test-tenant")

            assert result.status == CheckStatus.PASS
            assert "available" in result.message.lower()
            assert result.details["severity"] == "info"


class TestMFAAdminEnrollmentCheck:
    """Tests for MFAAdminEnrollmentCheck."""

    @pytest.fixture
    def check(self):
        """Create a MFAAdminEnrollmentCheck instance."""
        from app.preflight.mfa_checks import MFAAdminEnrollmentCheck
        return MFAAdminEnrollmentCheck()

    def test_check_initialization(self, check):
        """Test check is initialized with correct attributes."""
        assert check.check_id == "mfa_admin_enrollment"
        assert check.name == "MFA Admin Enrollment Compliance"
        assert check.category == CheckCategory.MFA_COMPLIANCE
        assert check.ADMIN_MFA_TARGET == 100.0

    @pytest.mark.asyncio
    async def test_check_no_data(self, check):
        """Test check fails when no MFA data exists."""
        with patch("app.preflight.mfa_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

            result = await check.run(tenant_id="test-tenant")

            assert result.status == CheckStatus.FAIL
            assert "no mfa data available" in result.message.lower()

    @pytest.mark.asyncio
    async def test_check_no_admins(self, check):
        """Test check warns when no admin accounts found."""
        with patch("app.preflight.mfa_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            mfa_record = MagicMock()
            mfa_record.admin_accounts_total = 0
            mfa_record.admin_accounts_mfa = 0
            mfa_record.admin_mfa_percentage = 0.0
            mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = mfa_record

            result = await check.run(tenant_id="test-tenant")

            assert result.status == CheckStatus.WARNING
            assert "no admin accounts" in result.message.lower()

    @pytest.mark.asyncio
    async def test_check_full_compliance(self, check):
        """Test check passes when all admins have MFA."""
        with patch("app.preflight.mfa_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            mfa_record = MagicMock()
            mfa_record.admin_accounts_total = 10
            mfa_record.admin_accounts_mfa = 10
            mfa_record.admin_mfa_percentage = 100.0
            mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = mfa_record

            result = await check.run(tenant_id="test-tenant")

            assert result.status == CheckStatus.PASS
            assert "100.0%" in result.message
            assert result.details["admin_accounts_total"] == 10
            assert result.details["admin_accounts_mfa"] == 10
            assert result.details["unprotected_admins"] == 0

    @pytest.mark.asyncio
    async def test_check_partial_compliance(self, check):
        """Test check fails when some admins lack MFA."""
        with patch("app.preflight.mfa_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            mfa_record = MagicMock()
            mfa_record.admin_accounts_total = 10
            mfa_record.admin_accounts_mfa = 8
            mfa_record.admin_mfa_percentage = 80.0
            mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = mfa_record

            result = await check.run(tenant_id="test-tenant")

            assert result.status == CheckStatus.FAIL
            assert "critical" in result.message.lower()
            assert "2 admin accounts" in result.message or "below target" in result.message.lower()
            assert result.details["severity"] == "critical"
            assert result.details["unprotected_admins"] == 2
            assert len(result.recommendations) > 0


class TestMFAUserEnrollmentCheck:
    """Tests for MFAUserEnrollmentCheck."""

    @pytest.fixture
    def check(self):
        """Create a MFAUserEnrollmentCheck instance."""
        from app.preflight.mfa_checks import MFAUserEnrollmentCheck
        return MFAUserEnrollmentCheck()

    def test_check_initialization(self, check):
        """Test check is initialized with correct attributes."""
        assert check.check_id == "mfa_user_enrollment"
        assert check.name == "MFA User Enrollment Compliance"
        assert check.category == CheckCategory.MFA_COMPLIANCE
        assert check.USER_MFA_TARGET == 95.0
        assert check.WARNING_THRESHOLD == 90.0

    @pytest.mark.asyncio
    async def test_check_no_data(self, check):
        """Test check fails when no MFA data exists."""
        with patch("app.preflight.mfa_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

            result = await check.run(tenant_id="test-tenant")

            assert result.status == CheckStatus.FAIL

    @pytest.mark.asyncio
    async def test_check_no_users(self, check):
        """Test check warns when no users found."""
        with patch("app.preflight.mfa_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            mfa_record = MagicMock()
            mfa_record.total_users = 0
            mfa_record.mfa_enrolled_users = 0
            mfa_record.mfa_coverage_percentage = 0.0
            mfa_record.unprotected_users = 0
            mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = mfa_record

            result = await check.run(tenant_id="test-tenant")

            assert result.status == CheckStatus.WARNING
            assert "no users" in result.message.lower()

    @pytest.mark.asyncio
    async def test_check_target_met(self, check):
        """Test check passes when MFA target is met (95%+)."""
        with patch("app.preflight.mfa_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            mfa_record = MagicMock()
            mfa_record.total_users = 100
            mfa_record.mfa_enrolled_users = 95
            mfa_record.mfa_coverage_percentage = 95.0
            mfa_record.unprotected_users = 5
            mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = mfa_record

            result = await check.run(tenant_id="test-tenant")

            assert result.status == CheckStatus.PASS
            assert "95.0%" in result.message
            assert result.details["mfa_coverage_percentage"] == 95.0

    @pytest.mark.asyncio
    async def test_check_warning_threshold(self, check):
        """Test check warns when MFA is between 90-95%."""
        with patch("app.preflight.mfa_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            mfa_record = MagicMock()
            mfa_record.total_users = 100
            mfa_record.mfa_enrolled_users = 92
            mfa_record.mfa_coverage_percentage = 92.0
            mfa_record.unprotected_users = 8
            mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = mfa_record

            result = await check.run(tenant_id="test-tenant")

            assert result.status == CheckStatus.WARNING
            assert "below target" in result.message.lower()
            assert result.details["severity"] == "warning"

    @pytest.mark.asyncio
    async def test_check_failure_threshold(self, check):
        """Test check fails when MFA is below 90%."""
        with patch("app.preflight.mfa_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            mfa_record = MagicMock()
            mfa_record.total_users = 100
            mfa_record.mfa_enrolled_users = 85
            mfa_record.mfa_coverage_percentage = 85.0
            mfa_record.unprotected_users = 15
            mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = mfa_record

            result = await check.run(tenant_id="test-tenant")

            assert result.status == CheckStatus.FAIL
            assert "significantly below target" in result.message.lower()
            assert result.details["severity"] == "critical"
            assert "gap_to_target_percentage" in result.details


class TestMFAGapReportCheck:
    """Tests for MFAGapReportCheck."""

    @pytest.fixture
    def check(self):
        """Create a MFAGapReportCheck instance."""
        from app.preflight.mfa_checks import MFAGapReportCheck
        return MFAGapReportCheck()

    def test_check_initialization(self, check):
        """Test check is initialized with correct attributes."""
        assert check.check_id == "mfa_gap_report"
        assert check.name == "MFA Gap Analysis Report"
        assert check.category == CheckCategory.MFA_COMPLIANCE

    @pytest.mark.asyncio
    async def test_check_no_data(self, check):
        """Test check fails when no MFA data exists."""
        with patch("app.preflight.mfa_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            # Mock the query chain for latest dates
            mock_subquery = MagicMock()
            mock_subquery.c = MagicMock()
            mock_subquery.c.tenant_id = "tenant_id"
            mock_subquery.c.latest_date = "latest_date"

            mock_db.query.return_value.group_by.return_value.subquery.return_value = mock_subquery
            mock_db.query.return_value.join.return_value.all.return_value = []

            result = await check.run()

            assert result.status == CheckStatus.FAIL
            assert "no mfa data available" in result.message.lower()

    @pytest.mark.asyncio
    async def test_check_all_compliant(self, check):
        """Test check passes when all tenants are compliant."""
        with patch("app.preflight.mfa_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            # Create compliant MFA records
            compliant_record = MagicMock()
            compliant_record.tenant_id = "tenant-1"
            compliant_record.total_users = 100
            compliant_record.mfa_enrolled_users = 95
            compliant_record.mfa_coverage_percentage = 95.0
            compliant_record.admin_accounts_total = 5
            compliant_record.admin_accounts_mfa = 5
            compliant_record.admin_mfa_percentage = 100.0

            # Need to mock the subquery and join properly
            mock_subquery = MagicMock()
            mock_subquery.c = MagicMock()
            mock_subquery.c.tenant_id = "tenant_id"
            mock_subquery.c.latest_date = "latest_date"

            mock_db.query.return_value.group_by.return_value.subquery.return_value = mock_subquery
            mock_db.query.return_value.join.return_value.all.return_value = [compliant_record]

            result = await check.run()

            assert result.status == CheckStatus.PASS
            assert "compliant" in result.message.lower()

    @pytest.mark.asyncio
    async def test_check_with_gaps(self, check):
        """Test check identifies gaps in MFA coverage."""
        with patch("app.preflight.mfa_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            # Create non-compliant MFA record
            non_compliant = MagicMock()
            non_compliant.tenant_id = "tenant-1"
            non_compliant.total_users = 100
            non_compliant.mfa_enrolled_users = 85
            non_compliant.mfa_coverage_percentage = 85.0
            non_compliant.admin_accounts_total = 5
            non_compliant.admin_accounts_mfa = 3
            non_compliant.admin_mfa_percentage = 60.0

            mock_subquery = MagicMock()
            mock_subquery.c = MagicMock()
            mock_subquery.c.tenant_id = "tenant_id"
            mock_subquery.c.latest_date = "latest_date"

            mock_db.query.return_value.group_by.return_value.subquery.return_value = mock_subquery
            mock_db.query.return_value.join.return_value.all.return_value = [non_compliant]

            result = await check.run()

            assert result.status == CheckStatus.FAIL
            assert "critical" in result.message.lower()
            assert "admin mfa gaps" in result.message.lower()
            assert result.details["critical_gaps"] > 0


class TestMFACheckFunctions:
    """Tests for MFA check convenience functions."""

    @pytest.mark.asyncio
    async def test_run_all_mfa_checks(self):
        """Test run_all_mfa_checks runs all checks."""
        from app.preflight.mfa_checks import run_all_mfa_checks

        with patch("app.preflight.mfa_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            # Mock all data queries to return valid data
            mfa_record = MagicMock()
            mfa_record.snapshot_date = datetime.utcnow() - timedelta(days=1)
            mfa_record.total_users = 100
            mfa_record.mfa_enrolled_users = 95
            mfa_record.mfa_coverage_percentage = 95.0
            mfa_record.admin_accounts_total = 10
            mfa_record.admin_accounts_mfa = 10
            mfa_record.admin_mfa_percentage = 100.0
            mfa_record.unprotected_users = 5
            mfa_record.tenant_id = "test-tenant"

            mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = mfa_record
            mock_db.query.return_value.filter.return_value.count.return_value = 1

            # Mock gap report queries
            mock_subquery = MagicMock()
            mock_subquery.c = MagicMock()
            mock_db.query.return_value.group_by.return_value.subquery.return_value = mock_subquery
            mock_db.query.return_value.join.return_value.all.return_value = [mfa_record]

            results = await run_all_mfa_checks(tenant_id="test-tenant")

            # Should return 4 check results
            assert len(results) == 4
            # All should be CheckResult instances
            from app.preflight.models import CheckResult
            assert all(isinstance(r, CheckResult) for r in results)

    def test_get_mfa_checks(self):
        """Test get_mfa_checks returns all checks."""
        from app.preflight.mfa_checks import get_mfa_checks

        checks = get_mfa_checks()

        # Should return 4 checks
        assert len(checks) == 4
        # All should have the correct category
        from app.preflight.base import BasePreflightCheck
        assert all(isinstance(c, BasePreflightCheck) for c in checks.values())
        # Verify check IDs
        assert "mfa_tenant_data" in checks
        assert "mfa_admin_enrollment" in checks
        assert "mfa_user_enrollment" in checks
        assert "mfa_gap_report" in checks


class TestSeverityLevels:
    """Tests to verify severity level constants."""

    def test_severity_levels(self):
        """Test severity level constants."""
        from app.preflight.mfa_checks import SeverityLevel

        assert SeverityLevel.CRITICAL == "critical"
        assert SeverityLevel.WARNING == "warning"
        assert SeverityLevel.INFO == "info"


class TestCheckResultStructure:
    """Tests to verify check result structure."""

    @pytest.mark.asyncio
    async def test_all_checks_return_valid_results(self):
        """Verify all MFA checks return properly structured results."""
        from app.preflight.mfa_checks import (
            MFATenantDataCheck,
            MFAAdminEnrollmentCheck,
            MFAUserEnrollmentCheck,
        )

        checks = [
            MFATenantDataCheck(),
            MFAAdminEnrollmentCheck(),
            MFAUserEnrollmentCheck(),
        ]

        with patch("app.preflight.mfa_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            # Mock data for all checks
            mfa_record = MagicMock()
            mfa_record.snapshot_date = datetime.utcnow() - timedelta(days=1)
            mfa_record.total_users = 100
            mfa_record.mfa_enrolled_users = 95
            mfa_record.mfa_coverage_percentage = 95.0
            mfa_record.admin_accounts_total = 10
            mfa_record.admin_accounts_mfa = 10
            mfa_record.admin_mfa_percentage = 100.0
            mfa_record.unprotected_users = 5

            mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = mfa_record
            mock_db.query.return_value.filter.return_value.count.return_value = 1

            for check in checks:
                result = await check.run(tenant_id="test-tenant")

                # Verify result structure
                assert result.check_id
                assert result.name
                assert result.category == CheckCategory.MFA_COMPLIANCE
                assert result.status in CheckStatus
                assert isinstance(result.message, str)
                assert isinstance(result.details, dict)
                assert isinstance(result.duration_ms, float)
                assert isinstance(result.recommendations, list)
                assert "severity" in result.details

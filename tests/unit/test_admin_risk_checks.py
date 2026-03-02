"""Unit tests for admin risk preflight checks.

Tests for the admin_risk_checks.py module to ensure all checks
function correctly and return expected result structures.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.preflight.models import CheckCategory, CheckStatus


class TestAdminMfaCheck:
    """Tests for AdminMfaCheck."""

    @pytest.fixture
    def check(self):
        """Create an AdminMfaCheck instance."""
        from app.preflight.admin_risk_checks import AdminMfaCheck
        return AdminMfaCheck()

    def test_check_initialization(self, check):
        """Test check is initialized with correct attributes."""
        assert check.check_id == "admin_mfa_enabled"
        assert check.name == "Privileged Account MFA Status"
        assert check.category == CheckCategory.AZURE_SECURITY
        assert check.timeout_seconds == 15.0

    @pytest.mark.asyncio
    async def test_check_all_mfa_enabled(self, check):
        """Test successful check when all privileged accounts have MFA."""
        with patch("app.preflight.admin_risk_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            # Mock empty result - no users without MFA
            mock_query = MagicMock()
            mock_db.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.all.return_value = []

            result = await check.run(force=True)

            assert result.status == CheckStatus.PASS
            assert "MFA enabled" in result.message

    @pytest.mark.asyncio
    async def test_check_users_without_mfa(self, check):
        """Test check finds users without MFA."""
        with patch("app.preflight.admin_risk_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            # Create mock users without MFA
            mock_user = MagicMock()
            mock_user.user_principal_name = "admin@example.com"
            mock_user.display_name = "Admin User"
            mock_user.role_name = "User Administrator"
            mock_user.mfa_enabled = 0

            mock_query = MagicMock()
            mock_db.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.all.return_value = [mock_user]

            result = await check.run(force=True)

            assert result.status in [CheckStatus.WARNING, CheckStatus.FAIL]
            assert "without MFA" in result.message
            assert len(result.recommendations) > 0

    @pytest.mark.asyncio
    async def test_check_critical_roles_without_mfa(self, check):
        """Test check flags critical roles without MFA as critical."""
        with patch("app.preflight.admin_risk_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            # Create mock user with critical role without MFA
            mock_user = MagicMock()
            mock_user.user_principal_name = "globaladmin@example.com"
            mock_user.display_name = "Global Admin"
            mock_user.role_name = "Global Administrator"
            mock_user.mfa_enabled = 0

            mock_query = MagicMock()
            mock_db.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.all.return_value = [mock_user]

            result = await check.run(force=True)

            assert result.status == CheckStatus.FAIL
            assert result.details.get("critical_role_count", 0) >= 1

    @pytest.mark.asyncio
    async def test_check_database_error(self, check):
        """Test database error handling."""
        with patch("app.preflight.admin_risk_checks.SessionLocal") as mock_session:
            mock_session.side_effect = Exception("Connection failed")

            result = await check.run(force=True)

            assert result.status == CheckStatus.FAIL
            assert len(result.recommendations) > 0


class TestOverprivilegedAccountCheck:
    """Tests for OverprivilegedAccountCheck."""

    @pytest.fixture
    def check(self):
        """Create an OverprivilegedAccountCheck instance."""
        from app.preflight.admin_risk_checks import OverprivilegedAccountCheck
        return OverprivilegedAccountCheck()

    def test_check_initialization(self, check):
        """Test check is initialized with correct attributes."""
        assert check.check_id == "admin_overprivileged"
        assert check.name == "Overprivileged Account Detection"
        assert check.category == CheckCategory.AZURE_SECURITY

    @pytest.mark.asyncio
    async def test_check_no_overprivileged(self, check):
        """Test check passes when no overprivileged accounts."""
        with patch("app.preflight.admin_risk_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            # Create users with normal role counts (one role each)
            mock_users = []
            for i in range(3):
                mock_user = MagicMock()
                mock_user.user_principal_name = f"user{i}@example.com"
                mock_user.display_name = f"User {i}"
                mock_user.role_name = f"Role {i}"
                mock_user.role_scope = "/"
                mock_user.is_permanent = 1
                mock_user.tenant_id = "tenant-1"
                mock_users.append(mock_user)

            mock_query = MagicMock()
            mock_db.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.all.return_value = mock_users

            result = await check.run(force=True)

            assert result.status == CheckStatus.PASS
            assert "No overprivileged" in result.message

    @pytest.mark.asyncio
    async def test_check_overprivileged_detected(self, check):
        """Test check finds overprivileged accounts."""
        with patch("app.preflight.admin_risk_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            # Create user with too many roles (5 roles, threshold is 3)
            mock_users = []
            upn = "superadmin@example.com"
            for i in range(5):
                mock_user = MagicMock()
                mock_user.user_principal_name = upn
                mock_user.display_name = "Super Admin"
                mock_user.role_name = f"Role {i}"
                mock_user.role_scope = "/"
                mock_user.is_permanent = 1
                mock_user.tenant_id = "tenant-1"
                mock_users.append(mock_user)

            mock_query = MagicMock()
            mock_db.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.all.return_value = mock_users

            result = await check.run(force=True)

            assert result.status in [CheckStatus.WARNING, CheckStatus.FAIL]
            assert result.details.get("overprivileged_count", 0) >= 1
            assert len(result.recommendations) > 0


class TestInactiveAdminCheck:
    """Tests for InactiveAdminCheck."""

    @pytest.fixture
    def check(self):
        """Create an InactiveAdminCheck instance."""
        from app.preflight.admin_risk_checks import InactiveAdminCheck
        return InactiveAdminCheck()

    def test_check_initialization(self, check):
        """Test check is initialized with correct attributes."""
        assert check.check_id == "admin_inactive"
        assert check.name == "Inactive Administrator Detection"
        assert check.category == CheckCategory.AZURE_SECURITY

    @pytest.mark.asyncio
    async def test_check_no_inactive_admins(self, check):
        """Test check passes when no inactive admins."""
        with patch("app.preflight.admin_risk_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            # Mock the chained query calls - no inactive admins
            mock_query = MagicMock()
            mock_db.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.all.return_value = []

            result = await check.run(force=True)

            assert result.status == CheckStatus.PASS
            assert "No inactive" in result.message

    @pytest.mark.asyncio
    async def test_check_inactive_admins_found(self, check):
        """Test check finds inactive admin accounts."""
        with patch("app.preflight.admin_risk_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            # Create inactive admin user
            mock_user = MagicMock()
            mock_user.user_principal_name = "inactive@example.com"
            mock_user.display_name = "Inactive Admin"
            mock_user.role_name = "User Administrator"
            mock_user.last_sign_in = datetime.utcnow() - timedelta(days=100)
            mock_user.mfa_enabled = 1

            mock_query = MagicMock()
            mock_db.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.all.return_value = [mock_user]

            result = await check.run(force=True)

            assert result.status in [CheckStatus.WARNING, CheckStatus.FAIL]
            assert "inactive" in result.message.lower()
            assert result.details.get("inactive_count", 0) >= 1


class TestSharedAdminCheck:
    """Tests for SharedAdminCheck."""

    @pytest.fixture
    def check(self):
        """Create a SharedAdminCheck instance."""
        from app.preflight.admin_risk_checks import SharedAdminCheck
        return SharedAdminCheck()

    def test_check_initialization(self, check):
        """Test check is initialized with correct attributes."""
        assert check.check_id == "admin_shared_accounts"
        assert check.name == "Shared Admin Account Detection"
        assert check.category == CheckCategory.AZURE_SECURITY

    @pytest.mark.asyncio
    async def test_check_no_shared_accounts(self, check):
        """Test check passes when no shared accounts."""
        with patch("app.preflight.admin_risk_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            # Create normal users (not shared)
            mock_users = []
            for i in range(3):
                mock_user = MagicMock()
                mock_user.user_principal_name = f"john.doe{i}@example.com"
                mock_user.display_name = f"John Doe {i}"
                mock_user.role_name = "Reader"
                mock_user.tenant_id = "tenant-1"
                mock_users.append(mock_user)

            mock_query = MagicMock()
            mock_db.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.all.return_value = mock_users

            result = await check.run(force=True)

            assert result.status == CheckStatus.PASS
            assert "No shared" in result.message

    @pytest.mark.asyncio
    async def test_check_shared_account_detected(self, check):
        """Test check finds shared admin accounts."""
        with patch("app.preflight.admin_risk_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            # Create shared admin user
            mock_user = MagicMock()
            mock_user.user_principal_name = "shared-admin@example.com"
            mock_user.display_name = "Shared Admin"
            mock_user.role_name = "User Administrator"
            mock_user.tenant_id = "tenant-1"
            mock_user.mfa_enabled = 1
            mock_user.last_sign_in = datetime.utcnow()

            mock_query = MagicMock()
            mock_db.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.all.return_value = [mock_user]

            result = await check.run(force=True)

            assert result.status in [CheckStatus.WARNING, CheckStatus.FAIL]
            assert result.details.get("shared_account_count", 0) >= 1

    @pytest.mark.asyncio
    async def test_check_service_account_detected(self, check):
        """Test check finds service admin accounts."""
        with patch("app.preflight.admin_risk_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            # Create service account
            mock_user = MagicMock()
            mock_user.user_principal_name = "svc-backup@example.com"
            mock_user.display_name = "Backup Service"
            mock_user.role_name = "Backup Reader"
            mock_user.tenant_id = "tenant-1"
            mock_user.mfa_enabled = 0
            mock_user.last_sign_in = datetime.utcnow()

            mock_query = MagicMock()
            mock_db.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.all.return_value = [mock_user]

            result = await check.run(force=True)

            assert result.status in [CheckStatus.WARNING, CheckStatus.FAIL]
            assert result.details.get("shared_account_count", 0) >= 1


class TestAdminComplianceGapCheck:
    """Tests for AdminComplianceGapCheck."""

    @pytest.fixture
    def check(self):
        """Create an AdminComplianceGapCheck instance."""
        from app.preflight.admin_risk_checks import AdminComplianceGapCheck
        return AdminComplianceGapCheck()

    def test_check_initialization(self, check):
        """Test check is initialized with correct attributes."""
        assert check.check_id == "admin_compliance_gaps"
        assert check.name == "Privileged Access Compliance Assessment"
        assert check.category == CheckCategory.AZURE_SECURITY

    @pytest.mark.asyncio
    async def test_check_no_privileged_users(self, check):
        """Test check skips when no privileged users."""
        with patch("app.preflight.admin_risk_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            # Mock the chained query calls - no privileged users
            mock_query = MagicMock()
            mock_db.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.all.return_value = []

            result = await check.run(force=True)

            assert result.status == CheckStatus.SKIPPED
            assert "No privileged users" in result.message

    @pytest.mark.asyncio
    async def test_check_high_compliance(self, check):
        """Test check passes with high compliance score."""
        with patch("app.preflight.admin_risk_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            # Create compliant users (with MFA, active)
            mock_users = []
            for i in range(5):
                mock_user = MagicMock()
                mock_user.user_principal_name = f"admin{i}@example.com"
                mock_user.display_name = f"Admin {i}"
                mock_user.role_name = "Reader"
                mock_user.mfa_enabled = 1
                mock_user.last_sign_in = datetime.utcnow() - timedelta(days=10)
                mock_user.tenant_id = "tenant-1"
                mock_users.append(mock_user)

            mock_query = MagicMock()
            mock_db.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.all.return_value = mock_users

            result = await check.run(force=True)

            assert result.status == CheckStatus.PASS
            assert result.details["compliance_score"] >= 90

    @pytest.mark.asyncio
    async def test_check_low_compliance(self, check):
        """Test check fails with low compliance score."""
        with patch("app.preflight.admin_risk_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            # Create non-compliant users (no MFA, inactive)
            mock_users = []
            for i in range(5):
                mock_user = MagicMock()
                mock_user.user_principal_name = f"admin{i}@example.com"
                mock_user.display_name = f"Admin {i}"
                mock_user.role_name = f"Role {i}"
                mock_user.mfa_enabled = 0
                mock_user.last_sign_in = datetime.utcnow() - timedelta(days=100)
                mock_user.tenant_id = "tenant-1"
                mock_users.append(mock_user)

            mock_query = MagicMock()
            mock_db.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.all.return_value = mock_users

            result = await check.run(force=True)

            # Low compliance should result in warning or fail
            assert result.details["compliance_score"] < 75
            assert len(result.recommendations) > 0


class TestAdminRiskCheckFunctions:
    """Tests for admin risk check convenience functions."""

    def test_get_admin_risk_checks(self):
        """Test get_admin_risk_checks returns all checks."""
        from app.preflight.admin_risk_checks import get_admin_risk_checks

        checks = get_admin_risk_checks()

        # Should return 5 checks
        assert len(checks) == 5
        # All should have the correct category
        from app.preflight.base import BasePreflightCheck
        assert all(isinstance(c, BasePreflightCheck) for c in checks.values())

        # Verify check IDs
        expected_ids = {
            "admin_mfa_enabled",
            "admin_overprivileged",
            "admin_inactive",
            "admin_shared_accounts",
            "admin_compliance_gaps",
        }
        assert set(checks.keys()) == expected_ids

    @pytest.mark.asyncio
    async def test_run_all_admin_risk_checks(self):
        """Test run_all_admin_risk_checks runs all checks."""
        from app.preflight.admin_risk_checks import run_all_admin_risk_checks

        with patch("app.preflight.admin_risk_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            mock_query = MagicMock()
            mock_db.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.all.return_value = []

            results = await run_all_admin_risk_checks()

        # Should return 5 check results
        assert len(results) == 5
        # All should be CheckResult instances
        from app.preflight.models import CheckResult
        assert all(isinstance(r, CheckResult) for r in results)


class TestCheckResultStructure:
    """Tests to verify check result structure and severity levels."""

    @pytest.mark.asyncio
    async def test_check_result_structure(self):
        """Verify all checks return properly structured results."""
        from app.preflight.admin_risk_checks import (
            AdminComplianceGapCheck,
            AdminMfaCheck,
            InactiveAdminCheck,
            OverprivilegedAccountCheck,
            SharedAdminCheck,
        )

        checks = [
            AdminMfaCheck(),
            OverprivilegedAccountCheck(),
            InactiveAdminCheck(),
            SharedAdminCheck(),
            AdminComplianceGapCheck(),
        ]

        with patch("app.preflight.admin_risk_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            mock_query = MagicMock()
            mock_db.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.all.return_value = []

            for check in checks:
                result = await check.run(force=True)

                # Verify result structure
                assert result.check_id
                assert result.name
                assert result.category == CheckCategory.AZURE_SECURITY
                assert result.status in CheckStatus
                assert isinstance(result.message, str)
                assert isinstance(result.details, dict)
                assert isinstance(result.duration_ms, float)
                assert isinstance(result.recommendations, list)
                assert "severity" in result.details

    def test_severity_levels(self):
        """Test severity level constants."""
        from app.preflight.admin_risk_checks import AdminRiskSeverity

        assert AdminRiskSeverity.CRITICAL == "critical"
        assert AdminRiskSeverity.HIGH == "high"
        assert AdminRiskSeverity.MEDIUM == "medium"
        assert AdminRiskSeverity.LOW == "low"
        assert AdminRiskSeverity.INFO == "info"

    def test_thresholds_defined(self):
        """Test that threshold constants are defined."""
        from app.preflight import admin_risk_checks

        assert admin_risk_checks.OVERPRIVILEGED_ROLE_THRESHOLD == 3
        assert admin_risk_checks.INACTIVE_ADMIN_DAYS == 90
        assert len(admin_risk_checks.SHARED_ACCOUNT_INDICATORS) > 0
        assert len(admin_risk_checks.CRITICAL_ROLES) > 0


class TestIntegrationWithPreflightSystem:
    """Tests for integration with the preflight system."""

    def test_checks_in_get_all_checks(self):
        """Test that admin risk checks are registered in get_all_checks."""
        from app.preflight.checks import get_all_checks

        all_checks = get_all_checks()

        # Verify admin risk checks are included
        assert "admin_mfa_enabled" in all_checks
        assert "admin_overprivileged" in all_checks
        assert "admin_inactive" in all_checks
        assert "admin_shared_accounts" in all_checks
        assert "admin_compliance_gaps" in all_checks

    @pytest.mark.asyncio
    async def test_tenant_specific_check(self):
        """Test that checks support tenant_id parameter."""
        from app.preflight.admin_risk_checks import AdminMfaCheck

        check = AdminMfaCheck()
        tenant_id = "12345678-1234-1234-1234-123456789012"

        with patch("app.preflight.admin_risk_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            mock_query = MagicMock()
            mock_db.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.all.return_value = []

            result = await check.run(tenant_id=tenant_id, force=True)

            assert result.tenant_id == tenant_id

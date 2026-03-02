"""Unit tests for Riverside preflight checks.

Tests for the riverside_checks.py module to ensure all checks
function correctly and return expected result structures.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, AsyncMock

from app.preflight.models import CheckCategory, CheckStatus


class TestRiversideDatabaseCheck:
    """Tests for RiversideDatabaseCheck."""

    @pytest.fixture
    def check(self):
        """Create a RiversideDatabaseCheck instance."""
        from app.preflight.riverside_checks import RiversideDatabaseCheck
        return RiversideDatabaseCheck()

    def test_check_initialization(self, check):
        """Test check is initialized with correct attributes."""
        assert check.check_id == "riverside_database_connectivity"
        assert check.name == "Riverside Database Connectivity"
        assert check.category == CheckCategory.RIVERSIDE
        assert check.timeout_seconds == 15.0

    @pytest.mark.asyncio
    async def test_check_success(self, check):
        """Test successful database connectivity check."""
        with patch("app.preflight.riverside_checks.SessionLocal") as mock_session:
            # Mock the database session
            mock_db = MagicMock()
            mock_session.return_value = mock_db

            # Mock query counts
            mock_db.query.return_value.count.return_value = 5

            result = await check.run()

            assert result.status == CheckStatus.PASS
            assert "accessible" in result.message.lower()
            assert result.category == CheckCategory.RIVERSIDE
            assert result.details["severity"] == "info"

    @pytest.mark.asyncio
    async def test_check_database_error(self, check):
        """Test database error handling."""
        with patch("app.preflight.riverside_checks.SessionLocal") as mock_session:
            mock_session.side_effect = Exception("Connection failed")

            result = await check.run()

            assert result.status == CheckStatus.FAIL
            assert "severity" in result.details
            assert result.details["severity"] == "critical"
            assert len(result.recommendations) > 0


class TestRiversideAPIEndpointCheck:
    """Tests for RiversideAPIEndpointCheck."""

    @pytest.fixture
    def check(self):
        """Create a RiversideAPIEndpointCheck instance."""
        from app.preflight.riverside_checks import RiversideAPIEndpointCheck
        return RiversideAPIEndpointCheck()

    def test_check_initialization(self, check):
        """Test check is initialized with correct attributes."""
        assert check.check_id == "riverside_api_endpoints"
        assert check.name == "Riverside API Endpoint Availability"
        assert check.category == CheckCategory.RIVERSIDE

    @pytest.mark.asyncio
    async def test_check_with_endpoint_failures(self, check):
        """Test check handles endpoint failures gracefully."""
        with patch("app.preflight.riverside_checks.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_client.return_value.__aenter__.return_value.request = AsyncMock(
                return_value=mock_response
            )

            with patch("app.preflight.riverside_checks.get_settings") as mock_settings:
                mock_settings.return_value.app_base_url = "http://localhost:8000"

                result = await check.run()

                # Should fail or warning when endpoints return errors
                assert result.status in [CheckStatus.FAIL, CheckStatus.WARNING]
                assert "endpoint" in result.message.lower() or "failed" in result.message.lower()


class TestRiversideSchedulerCheck:
    """Tests for RiversideSchedulerCheck."""

    @pytest.fixture
    def check(self):
        """Create a RiversideSchedulerCheck instance."""
        from app.preflight.riverside_checks import RiversideSchedulerCheck
        return RiversideSchedulerCheck()

    def test_check_initialization(self, check):
        """Test check is initialized with correct attributes."""
        assert check.check_id == "riverside_scheduler"
        assert check.name == "Riverside Scheduler Job Registration"
        assert check.category == CheckCategory.RIVERSIDE

    @pytest.mark.asyncio
    async def test_check_scheduler_not_initialized(self, check):
        """Test check handles uninitialized scheduler."""
        with patch("app.preflight.riverside_checks.get_scheduler") as mock_get_scheduler:
            mock_get_scheduler.return_value = None

            result = await check.run()

            assert result.status == CheckStatus.WARNING
            assert "not initialized" in result.message.lower()

    @pytest.mark.asyncio
    async def test_check_job_not_found(self, check):
        """Test check handles missing Riverside job."""
        with patch("app.preflight.riverside_checks.get_scheduler") as mock_get_scheduler:
            mock_scheduler = MagicMock()
            mock_scheduler.get_jobs.return_value = []  # No jobs
            mock_get_scheduler.return_value = mock_scheduler

            result = await check.run()

            assert result.status == CheckStatus.FAIL
            assert "not found" in result.message.lower() or "job" in result.message.lower()


class TestRiversideAzureADPermissionsCheck:
    """Tests for RiversideAzureADPermissionsCheck."""

    @pytest.fixture
    def check(self):
        """Create a RiversideAzureADPermissionsCheck instance."""
        from app.preflight.riverside_checks import RiversideAzureADPermissionsCheck
        return RiversideAzureADPermissionsCheck()

    def test_check_initialization(self, check):
        """Test check is initialized with correct attributes."""
        assert check.check_id == "riverside_azure_ad_permissions"
        assert check.name == "Riverside Azure AD Permissions"
        assert check.category == CheckCategory.RIVERSIDE

    @pytest.mark.asyncio
    async def test_check_no_tenant_id(self, check):
        """Test check handles missing tenant ID."""
        with patch("app.preflight.riverside_checks.get_settings") as mock_settings:
            mock_settings.return_value.azure_tenant_id = None

            result = await check.run()

            assert result.status == CheckStatus.FAIL
            assert "tenant" in result.message.lower()


class TestRiversideMFADataSourceCheck:
    """Tests for RiversideMFADataSourceCheck."""

    @pytest.fixture
    def check(self):
        """Create a RiversideMFADataSourceCheck instance."""
        from app.preflight.riverside_checks import RiversideMFADataSourceCheck
        return RiversideMFADataSourceCheck()

    def test_check_initialization(self, check):
        """Test check is initialized with correct attributes."""
        assert check.check_id == "riverside_mfa_data_source"
        assert check.name == "Riverside MFA Data Source Connectivity"
        assert check.category == CheckCategory.RIVERSIDE

    @pytest.mark.asyncio
    async def test_check_no_tenant_id(self, check):
        """Test check handles missing tenant ID."""
        with patch("app.preflight.riverside_checks.get_settings") as mock_settings:
            mock_settings.return_value.azure_tenant_id = None

            result = await check.run()

            assert result.status == CheckStatus.FAIL
            assert "tenant" in result.message.lower()


class TestRiversideCheckFunctions:
    """Tests for Riverside check convenience functions."""

    @pytest.mark.asyncio
    async def test_run_all_riverside_checks(self):
        """Test run_all_riverside_checks runs all checks."""
        from app.preflight.riverside_checks import run_all_riverside_checks

        with patch("app.preflight.riverside_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            mock_db.query.return_value.count.return_value = 0

            # Mock all the checks to avoid external dependencies
            with patch("app.preflight.riverside_checks.httpx.AsyncClient"):
                with patch("app.preflight.riverside_checks.get_scheduler") as mock_scheduler:
                    mock_scheduler.return_value = None

                    with patch("app.preflight.riverside_checks.get_settings") as mock_settings:
                        mock_settings.return_value.azure_tenant_id = None

                        results = await run_all_riverside_checks()

        # Should return 5 check results
        assert len(results) == 5
        # All should be CheckResult instances
        from app.preflight.models import CheckResult
        assert all(isinstance(r, CheckResult) for r in results)

    def test_get_riverside_checks(self):
        """Test get_riverside_checks returns all checks."""
        from app.preflight.riverside_checks import get_riverside_checks

        checks = get_riverside_checks()

        # Should return 5 checks
        assert len(checks) == 5
        # All should have the correct category
        from app.preflight.base import BasePreflightCheck
        assert all(isinstance(c, BasePreflightCheck) for c in checks.values())


class TestCheckResultStructure:
    """Tests to verify check result structure and severity levels."""

    @pytest.mark.asyncio
    async def test_check_result_structure(self):
        """Verify all checks return properly structured results."""
        from app.preflight.riverside_checks import (
            RiversideDatabaseCheck,
            RiversideAPIEndpointCheck,
            RiversideSchedulerCheck,
        )

        checks = [
            RiversideDatabaseCheck(),
            RiversideAPIEndpointCheck(),
            RiversideSchedulerCheck(),
        ]

        for check in checks:
            # Mock dependencies to ensure check runs
            with patch("app.preflight.riverside_checks.SessionLocal") as mock_session:
                mock_db = MagicMock()
                mock_session.return_value = mock_db
                mock_db.query.return_value.count.return_value = 0

                with patch("app.preflight.riverside_checks.get_scheduler") as mock_scheduler:
                    mock_scheduler.return_value = None

                    with patch("app.preflight.riverside_checks.get_settings") as mock_settings:
                        mock_settings.return_value.azure_tenant_id = None

                        result = await check.run()

            # Verify result structure
            assert result.check_id
            assert result.name
            assert result.category == CheckCategory.RIVERSIDE
            assert result.status in CheckStatus
            assert isinstance(result.message, str)
            assert isinstance(result.details, dict)
            assert isinstance(result.duration_ms, float)
            assert isinstance(result.recommendations, list)

    def test_severity_levels(self):
        """Test severity level constants."""
        from app.preflight.riverside_checks import SeverityLevel

        assert SeverityLevel.CRITICAL == "critical"
        assert SeverityLevel.WARNING == "warning"
        assert SeverityLevel.INFO == "info"

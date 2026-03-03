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

            result = await check.run(force=True)

            assert result.status == CheckStatus.PASS
            assert "accessible" in result.message.lower()
            assert result.category == CheckCategory.RIVERSIDE
            assert result.details["severity"] == "info"

    @pytest.mark.asyncio
    async def test_check_database_error(self, check):
        """Test database error handling."""
        with patch("app.preflight.riverside_checks.SessionLocal") as mock_session:
            mock_session.side_effect = Exception("Connection failed")

            result = await check.run(force=True)

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

                result = await check.run(force=True)

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
        with patch("app.core.scheduler.get_scheduler") as mock_get_scheduler:
            mock_get_scheduler.return_value = None

            result = await check.run(force=True)

            assert result.status == CheckStatus.WARNING
            assert "not initialized" in result.message.lower()

    @pytest.mark.asyncio
    async def test_check_job_not_found(self, check):
        """Test check handles missing Riverside job."""
        with patch("app.core.scheduler.get_scheduler") as mock_get_scheduler:
            mock_scheduler = MagicMock()
            mock_scheduler.get_jobs.return_value = []  # No jobs
            mock_get_scheduler.return_value = mock_scheduler

            result = await check.run(force=True)

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

            result = await check.run(force=True)

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

            result = await check.run(force=True)

            assert result.status == CheckStatus.FAIL
            assert "tenant" in result.message.lower()


class TestRiversideEvidenceCheck:
    """Tests for RiversideEvidenceCheck."""

    @pytest.fixture
    def check(self):
        """Create a RiversideEvidenceCheck instance."""
        from app.preflight.riverside_checks import RiversideEvidenceCheck
        return RiversideEvidenceCheck()

    def test_check_initialization(self, check):
        """Test check is initialized with correct attributes."""
        assert check.check_id == "riverside_requirement_evidence"
        assert check.name == "Riverside Requirement Evidence Verification"
        assert check.category == CheckCategory.RIVERSIDE

    def test_get_severity_for_priority(self, check):
        """Test severity mapping based on priority."""
        from app.preflight.riverside_checks import SeverityLevel

        assert check._get_severity_for_priority("P0") == SeverityLevel.CRITICAL
        assert check._get_severity_for_priority("P1") == SeverityLevel.WARNING
        assert check._get_severity_for_priority("P2") == SeverityLevel.INFO
        assert check._get_severity_for_priority("UNKNOWN") == SeverityLevel.INFO

    def test_validate_evidence_format(self, check):
        """Test evidence format validation."""
        # Test valid PDF
        result = check._validate_evidence_format("/path/to/evidence.pdf")
        assert result["valid"] is True
        assert result["type"] == "local_file"

        # Test valid external URL
        result = check._validate_evidence_format("https://sharepoint.com/doc.pdf")
        assert result["valid"] is True
        assert result["type"] == "external_url"

        # Test invalid extension
        result = check._validate_evidence_format("/path/to/evidence.exe")
        assert result["valid"] is False
        assert result["reason"] == "invalid_extension"

        # Test no URL
        result = check._validate_evidence_format(None)
        assert result["valid"] is False
        assert result["reason"] == "no_evidence_url"

    def test_check_evidence_exists_external(self, check):
        """Test evidence existence check for external URLs."""
        result = check._check_evidence_exists("https://example.com/doc.pdf")
        assert result["exists"] is True
        assert result["type"] == "external"

    def test_check_evidence_exists_no_url(self, check):
        """Test evidence existence check with no URL."""
        result = check._check_evidence_exists(None)
        assert result["exists"] is False
        assert result["reason"] == "no_url"

    @pytest.mark.asyncio
    async def test_check_no_completed_requirements(self, check):
        """Test check when no completed requirements exist."""
        with patch("app.preflight.riverside_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            mock_db.query.return_value.filter.return_value.all.return_value = []

            result = await check.run(force=True)

            assert result.status == CheckStatus.PASS
            assert "no completed requirements" in result.message.lower()
            assert result.details["completed_count"] == 0

    @pytest.mark.asyncio
    async def test_check_with_completed_requirements_all_have_evidence(self, check):
        """Test check with completed requirements that all have evidence."""
        from app.models.riverside import (
            RequirementStatus,
            RequirementPriority,
            RiversideRequirement,
        )

        # Create mock completed requirements with evidence
        mock_req = MagicMock(spec=RiversideRequirement)
        mock_req.requirement_id = "RC-001"
        mock_req.title = "Test Requirement"
        mock_req.priority = RequirementPriority.P1
        mock_req.status = RequirementStatus.COMPLETED
        mock_req.tenant_id = "tenant-123"
        mock_req.evidence_url = "https://example.com/evidence.pdf"

        with patch("app.preflight.riverside_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            mock_db.query.return_value.filter.return_value.all.return_value = [mock_req]

            result = await check.run(force=True)

            assert result.status == CheckStatus.PASS
            assert result.details["completed_count"] == 1
            assert result.details["with_evidence"] == 1
            assert result.details["missing_evidence"] == 0

    @pytest.mark.asyncio
    async def test_check_p0_missing_evidence(self, check):
        """Test check fails when P0 requirement is missing evidence."""
        from app.models.riverside import (
            RequirementStatus,
            RequirementPriority,
            RiversideRequirement,
        )

        # Create mock P0 requirement without evidence
        mock_req = MagicMock(spec=RiversideRequirement)
        mock_req.requirement_id = "RC-001"
        mock_req.title = "Critical Requirement"
        mock_req.priority = RequirementPriority.P0
        mock_req.status = RequirementStatus.COMPLETED
        mock_req.tenant_id = "tenant-123"
        mock_req.evidence_url = None

        with patch("app.preflight.riverside_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            mock_db.query.return_value.filter.return_value.all.return_value = [mock_req]

            result = await check.run(force=True)

            assert result.status == CheckStatus.FAIL
            assert result.details["p0_missing"] == 1
            assert "critical" in result.message.lower()
            assert len(result.recommendations) > 0

    @pytest.mark.asyncio
    async def test_check_p1_missing_evidence(self, check):
        """Test check warns when P1 requirement is missing evidence."""
        from app.models.riverside import (
            RequirementStatus,
            RequirementPriority,
            RiversideRequirement,
        )

        # Create mock P1 requirement without evidence
        mock_req = MagicMock(spec=RiversideRequirement)
        mock_req.requirement_id = "RC-002"
        mock_req.title = "High Priority Requirement"
        mock_req.priority = RequirementPriority.P1
        mock_req.status = RequirementStatus.COMPLETED
        mock_req.tenant_id = "tenant-123"
        mock_req.evidence_url = None

        with patch("app.preflight.riverside_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            mock_db.query.return_value.filter.return_value.all.return_value = [mock_req]

            result = await check.run(force=True)

            assert result.status == CheckStatus.WARNING
            assert result.details["p1_missing"] == 1
            assert "warning" in result.message.lower()

    @pytest.mark.asyncio
    async def test_check_with_tenant_filter(self, check):
        """Test check respects tenant_id filter."""
        with patch("app.preflight.riverside_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            mock_query = MagicMock()
            mock_db.query.return_value = mock_query
            mock_query.filter.return_value = mock_query
            mock_query.all.return_value = []

            result = await check.run(tenant_id="test-tenant-123", force=True)

            # Verify tenant filter was applied
            mock_query.filter.assert_called()
            assert result.status == CheckStatus.PASS


class TestRiversideCheckFunctions:
    """Tests for Riverside check convenience functions."""

    @pytest.mark.asyncio
    async def test_run_all_riverside_checks(self):
        """Test run_all_riverside_checks runs all checks."""
        from app.preflight.riverside_checks import run_all_riverside_checks
        from app.preflight.base import BasePreflightCheck
        BasePreflightCheck.clear_cache()

        with patch("app.preflight.riverside_checks.SessionLocal") as mock_session:
            mock_db = MagicMock()
            mock_session.return_value = mock_db
            mock_db.query.return_value.filter.return_value.all.return_value = []

            # Mock all the checks to avoid external dependencies
            with patch("app.preflight.riverside_checks.httpx.AsyncClient"):
                with patch("app.core.scheduler.get_scheduler") as mock_scheduler:
                    mock_scheduler.return_value = None

                    with patch("app.preflight.riverside_checks.get_settings") as mock_settings:
                        mock_settings.return_value.azure_tenant_id = None

                        results = await run_all_riverside_checks()

        # Should return 6 check results (including new evidence check)
        assert len(results) == 6
        # All should be CheckResult instances
        from app.preflight.models import CheckResult
        assert all(isinstance(r, CheckResult) for r in results)

    def test_get_riverside_checks(self):
        """Test get_riverside_checks returns all checks."""
        from app.preflight.riverside_checks import get_riverside_checks

        checks = get_riverside_checks()

        # Should return 6 checks (including new evidence check)
        assert len(checks) == 6
        # All should have the correct category
        from app.preflight.base import BasePreflightCheck
        assert all(isinstance(c, BasePreflightCheck) for c in checks.values())
        # Verify evidence check is included
        assert "riverside_requirement_evidence" in checks


class TestCheckResultStructure:
    """Tests to verify check result structure and severity levels."""

    @pytest.mark.asyncio
    async def test_check_result_structure(self):
        """Verify all checks return properly structured results."""
        from app.preflight.base import BasePreflightCheck
        BasePreflightCheck.clear_cache()

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

                with patch("app.core.scheduler.get_scheduler") as mock_scheduler:
                    mock_scheduler.return_value = None

                    with patch("app.preflight.riverside_checks.get_settings") as mock_settings:
                        mock_settings.return_value.azure_tenant_id = None

                        result = await check.run(force=True)

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

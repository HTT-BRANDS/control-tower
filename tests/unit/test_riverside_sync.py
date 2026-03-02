"""Tests for Riverside Azure sync services module."""

import sys
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock Azure SDK modules before importing
azure_mock = MagicMock()
sys.modules['azure'] = azure_mock
sys.modules['azure.mgmt'] = azure_mock
sys.modules['azure.mgmt.resource'] = azure_mock
sys.modules['azure.mgmt.costmanagement'] = azure_mock
sys.modules['azure.mgmt.policyinsights'] = azure_mock
sys.modules['azure.mgmt.security'] = azure_mock
sys.modules['azure.identity'] = azure_mock
sys.modules['azure.core'] = azure_mock
sys.modules['azure.core.exceptions'] = azure_mock

from app.models.riverside import (
    RequirementPriority,
    RequirementStatus,
    RiversideCompliance,
    RiversideDeviceCompliance,
    RiversideMFA,
    RiversideRequirement,
)
from app.services.riverside_sync import (
    ProgressTracker,
    SyncError,
    sync_all_tenants,
    sync_maturity_scores,
    sync_requirement_status,
    sync_tenant_devices,
    sync_tenant_mfa,
)


class TestProgressTracker:
    """Test suite for ProgressTracker."""

    def test_init(self):
        """Test ProgressTracker initialization."""
        tracker = ProgressTracker()
        assert tracker.total == 0
        assert tracker.completed == 0
        assert tracker.failed == 0
        assert tracker.errors == []

    def test_increment_completed(self):
        """Test incrementing completed count."""
        tracker = ProgressTracker()
        tracker.increment_completed()
        assert tracker.completed == 1

    def test_increment_failed(self):
        """Test incrementing failed count with error."""
        tracker = ProgressTracker()
        tracker.increment_failed("Test error", "tenant-123")
        assert tracker.failed == 1
        assert len(tracker.errors) == 1
        assert tracker.errors[0]["tenant_id"] == "tenant-123"

    def test_percentage_calculation(self):
        """Test percentage calculation."""
        tracker = ProgressTracker()
        tracker.set_total(10)
        tracker.increment_completed()
        assert tracker.percentage == 10.0

    def test_percentage_zero_total(self):
        """Test percentage with zero total."""
        tracker = ProgressTracker()
        assert tracker.percentage == 0.0

    def test_to_dict(self):
        """Test conversion to dictionary."""
        tracker = ProgressTracker()
        tracker.set_total(10)
        tracker.increment_completed()
        tracker.increment_failed("error", "tenant-123")

        result = tracker.to_dict()
        assert result["total"] == 10
        assert result["completed"] == 1
        assert result["failed"] == 1
        assert result["percentage"] == 20.0


class TestSyncError:
    """Test suite for SyncError."""

    def test_init_with_tenant(self):
        """Test SyncError with tenant ID."""
        error = SyncError("Test message", "tenant-123")
        assert str(error) == "Test message"
        assert error.tenant_id == "tenant-123"

    def test_init_without_tenant(self):
        """Test SyncError without tenant ID."""
        error = SyncError("Test message")
        assert str(error) == "Test message"
        assert error.tenant_id is None


class TestSyncTenantMFA:
    """Test suite for sync_tenant_mfa function."""

    @pytest.fixture
    def mock_tenant(self):
        """Create a mock tenant."""
        tenant = MagicMock()
        tenant.id = "tenant-uuid-123"
        tenant.tenant_id = "test-tenant-id"
        tenant.name = "Test Tenant"
        tenant.is_active = True
        return tenant

    @pytest.fixture
    def mock_mfa_registrations(self):
        """Sample MFA registration data."""
        return [
            {"userPrincipalName": "user1@test.com", "isMfaRegistered": True, "methodsRegistered": ["phone"]},
            {"userPrincipalName": "user2@test.com", "isMfaRegistered": False, "methodsRegistered": []},
            {"userPrincipalName": "user3@test.com", "isMfaRegistered": True, "methodsRegistered": ["app"]},
        ]

    @pytest.fixture
    def mock_users(self):
        """Sample user data."""
        return [
            {"id": "1", "userPrincipalName": "user1@test.com"},
            {"id": "2", "userPrincipalName": "user2@test.com"},
            {"id": "3", "userPrincipalName": "user3@test.com"},
            {"id": "4", "userPrincipalName": "user4@test.com"},
        ]

    @pytest.fixture
    def mock_directory_roles(self):
        """Sample directory role data."""
        return [
            {
                "roleTemplateId": "62e90394-69f5-4237-9190-012177145e10",  # Global Admin
                "members": [
                    {"userPrincipalName": "user1@test.com"},
                    {"userPrincipalName": "user2@test.com"},
                ]
            }
        ]

    @pytest.mark.asyncio
    async def test_sync_tenant_mfa_success(
        self,
        mock_tenant,
        mock_mfa_registrations,
        mock_users,
        mock_directory_roles,
    ):
        """Test successful MFA sync."""
        # Setup mocks
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_tenant

        with patch("app.services.riverside_sync.GraphClient") as MockGraphClient:
            mock_graph = MagicMock()
            MockGraphClient.return_value = mock_graph
            mock_graph.get_mfa_status = AsyncMock(return_value={"value": mock_mfa_registrations})
            mock_graph.get_users = AsyncMock(return_value=mock_users)
            mock_graph.get_directory_roles = AsyncMock(return_value=mock_directory_roles)

            # Execute
            result = await sync_tenant_mfa("test-tenant-id", mock_session)

            # Verify
            assert result["status"] == "success"
            assert result["total_users"] == 4
            assert result["mfa_enrolled"] == 2
            assert result["admin_accounts"] == 2
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_tenant_mfa_tenant_not_found(self):
        """Test MFA sync when tenant not found."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        with pytest.raises(SyncError) as exc_info:
            await sync_tenant_mfa("nonexistent-tenant", mock_session)

        assert "not found" in str(exc_info.value)
        assert exc_info.value.tenant_id == "nonexistent-tenant"

    @pytest.mark.asyncio
    async def test_sync_tenant_mfa_updates_existing(
        self,
        mock_tenant,
        mock_mfa_registrations,
        mock_users,
        mock_directory_roles,
    ):
        """Test MFA sync updates existing record."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.side_effect = [mock_tenant, MagicMock()]  # tenant, then existing MFA record

        with patch("app.services.riverside_sync.GraphClient") as MockGraphClient:
            mock_graph = MagicMock()
            MockGraphClient.return_value = mock_graph
            mock_graph.get_mfa_status = AsyncMock(return_value={"value": mock_mfa_registrations})
            mock_graph.get_users = AsyncMock(return_value=mock_users)
            mock_graph.get_directory_roles = AsyncMock(return_value=mock_directory_roles)

            result = await sync_tenant_mfa("test-tenant-id", mock_session)

            assert result["status"] == "success"
            mock_session.add.assert_not_called()  # Should update, not add
            mock_session.commit.assert_called_once()


class TestSyncTenantDevices:
    """Test suite for sync_tenant_devices function."""

    @pytest.fixture
    def mock_tenant(self):
        """Create a mock tenant."""
        tenant = MagicMock()
        tenant.id = "tenant-uuid-123"
        tenant.tenant_id = "test-tenant-id"
        tenant.name = "Test Tenant"
        return tenant

    @pytest.fixture
    def mock_devices(self):
        """Sample device data."""
        return [
            {"id": "1", "complianceState": "compliant", "managementAgent": "mdm", "isEncrypted": True},
            {"id": "2", "complianceState": "noncompliant", "managementAgent": "mdm", "isEncrypted": False},
            {"id": "3", "complianceState": "compliant", "managementAgent": "eas", "isEncrypted": True},
            {"id": "4", "complianceState": "compliant", "managementAgent": "configurationManagerClientMdm", "isEncrypted": True},
        ]

    @pytest.mark.asyncio
    async def test_sync_tenant_devices_success(self, mock_tenant, mock_devices):
        """Test successful device sync."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.side_effect = [mock_tenant, None]  # tenant, no existing record

        with patch("app.services.riverside_sync.GraphClient") as MockGraphClient:
            mock_graph = MagicMock()
            MockGraphClient.return_value = mock_graph
            mock_graph._request = AsyncMock(return_value={"value": mock_devices})

            result = await sync_tenant_devices("test-tenant-id", mock_session)

            assert result["status"] == "success"
            assert result["total_devices"] == 4
            assert result["compliant_devices"] == 3
            assert result["mdm_enrolled"] == 3  # mdm, configurationManagerClientMdm
            assert result["encrypted_devices"] == 3
            mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_tenant_devices_empty_data(self, mock_tenant):
        """Test device sync with no devices."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.side_effect = [mock_tenant, None]

        with patch("app.services.riverside_sync.GraphClient") as MockGraphClient:
            mock_graph = MagicMock()
            MockGraphClient.return_value = mock_graph
            mock_graph._request = AsyncMock(return_value={"value": []})

            result = await sync_tenant_devices("test-tenant-id", mock_session)

            assert result["status"] == "success"
            assert result["total_devices"] == 0
            assert result["compliance_pct"] == 0.0


class TestSyncRequirementStatus:
    """Test suite for sync_requirement_status function."""

    @pytest.fixture
    def mock_tenant(self):
        """Create a mock tenant."""
        tenant = MagicMock()
        tenant.id = "tenant-uuid-123"
        tenant.tenant_id = "test-tenant-id"
        tenant.name = "Test Tenant"
        return tenant

    @pytest.fixture
    def mock_requirements(self):
        """Sample requirement data."""
        req1 = MagicMock()
        req1.id = 1
        req1.requirement_id = "RC-MFA-001"
        req1.title = "Enable MFA for all users"
        req1.status = RequirementStatus.NOT_STARTED

        req2 = MagicMock()
        req2.id = 2
        req2.requirement_id = "RC-DS-001"
        req2.title = "Enable encryption"
        req2.status = RequirementStatus.IN_PROGRESS

        return [req1, req2]

    @pytest.fixture
    def mock_ca_policies_with_mfa(self):
        """Sample CA policies with MFA enforcement."""
        return [
            {
                "displayName": "Require MFA for Admins",
                "grantControls": {"builtInControls": ["mfa"]}
            }
        ]

    @pytest.mark.asyncio
    async def test_sync_requirement_status_success(
        self,
        mock_tenant,
        mock_requirements,
        mock_ca_policies_with_mfa,
    ):
        """Test successful requirement status sync."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_tenant
        mock_query.all.return_value = mock_requirements

        with patch("app.services.riverside_sync.GraphClient") as MockGraphClient:
            mock_graph = MagicMock()
            MockGraphClient.return_value = mock_graph
            mock_graph.get_conditional_access_policies = AsyncMock(return_value=mock_ca_policies_with_mfa)

            result = await sync_requirement_status("test-tenant-id", mock_session)

            assert result["status"] == "success"
            assert result["requirements_checked"] == 2
            assert result["requirements_updated"] == 1  # MFA requirement updated
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_requirement_status_no_mfa_policy(self, mock_tenant, mock_requirements):
        """Test requirement sync with no MFA policy."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_tenant
        mock_query.all.return_value = mock_requirements

        with patch("app.services.riverside_sync.GraphClient") as MockGraphClient:
            mock_graph = MagicMock()
            MockGraphClient.return_value = mock_graph
            mock_graph.get_conditional_access_policies = AsyncMock(return_value=[])

            result = await sync_requirement_status("test-tenant-id", mock_session)

            assert result["status"] == "success"
            assert result["requirements_checked"] == 2
            assert result["requirements_updated"] == 0  # No updates without MFA policy


class TestSyncMaturityScores:
    """Test suite for sync_maturity_scores function."""

    @pytest.fixture
    def mock_tenant(self):
        """Create a mock tenant."""
        tenant = MagicMock()
        tenant.id = "tenant-uuid-123"
        tenant.tenant_id = "test-tenant-id"
        tenant.name = "Test Tenant"
        return tenant

    @pytest.fixture
    def mock_mfa_data(self):
        """Sample MFA data."""
        mfa = MagicMock()
        mfa.total_users = 100
        mfa.mfa_coverage_percentage = 75.0
        return mfa

    @pytest.fixture
    def mock_device_data(self):
        """Sample device data."""
        device = MagicMock()
        device.total_devices = 50
        device.compliance_percentage = 80.0
        return device

    @pytest.mark.asyncio
    async def test_sync_maturity_scores_success(
        self,
        mock_tenant,
        mock_mfa_data,
        mock_device_data,
    ):
        """Test successful maturity score sync."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        # Setup query results
        def mock_query_side_effect(model):
            if model == mock_session.query.call_args[0][0]:
                return mock_query
            return mock_query

        mock_query.first.side_effect = [
            mock_tenant,      # First call: get tenant
            mock_mfa_data,    # Second call: get MFA data
            mock_device_data, # Third call: get device data
            None,             # Fourth call: check existing compliance record
        ]
        mock_query.count.side_effect = [10, 5]  # total_reqs, completed_reqs

        result = await sync_maturity_scores("test-tenant-id", mock_session)

        assert result["status"] == "success"
        assert result["requirements_total"] == 10
        assert result["requirements_completed"] == 5
        assert "maturity_score" in result
        assert "domain_scores" in result
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_maturity_scores_no_data(self, mock_tenant):
        """Test maturity sync with no historical data."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.side_effect = [
            mock_tenant,
            None,  # No MFA data
            None,  # No device data
            None,  # No existing compliance record
        ]
        mock_query.count.return_value = 0

        result = await sync_maturity_scores("test-tenant-id", mock_session)

        assert result["status"] == "success"
        assert result["maturity_score"] == 0.0
        assert result["domain_scores"]["mfa"] == 0.0
        assert result["domain_scores"]["device"] == 0.0


class TestSyncAllTenants:
    """Test suite for sync_all_tenants function."""

    @pytest.fixture
    def mock_tenants(self):
        """Create mock tenants."""
        tenant1 = MagicMock()
        tenant1.id = "uuid-1"
        tenant1.tenant_id = "tenant-1"
        tenant1.name = "Tenant 1"
        tenant1.is_active = True

        tenant2 = MagicMock()
        tenant2.id = "uuid-2"
        tenant2.tenant_id = "tenant-2"
        tenant2.name = "Tenant 2"
        tenant2.is_active = True

        return [tenant1, tenant2]

    @pytest.mark.asyncio
    async def test_sync_all_tenants_success(self, mock_tenants):
        """Test successful batch sync of all tenants."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_tenants

        with patch("app.services.riverside_sync.MonitoringService") as MockMonitoring:
            mock_monitor = MagicMock()
            MockMonitoring.return_value = mock_monitor
            mock_monitor.start_sync_job.return_value = MagicMock(id=1)

            with patch("app.services.riverside_sync.sync_tenant_mfa") as mock_mfa, \
                 patch("app.services.riverside_sync.sync_tenant_devices") as mock_devices, \
                 patch("app.services.riverside_sync.sync_requirement_status") as mock_reqs, \
                 patch("app.services.riverside_sync.sync_maturity_scores") as mock_maturity:

                mock_mfa.return_value = {"status": "success"}
                mock_devices.return_value = {"status": "success"}
                mock_reqs.return_value = {"status": "success"}
                mock_maturity.return_value = {"status": "success"}

                result = await sync_all_tenants(mock_session)

                assert result["status"] == "success"
                assert result["tenants_processed"] == 2
                assert result["tenants_failed"] == 0
                mock_monitor.complete_sync_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_all_tenants_partial_failure(self, mock_tenants):
        """Test batch sync with partial failures."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_tenants

        with patch("app.services.riverside_sync.MonitoringService") as MockMonitoring:
            mock_monitor = MagicMock()
            MockMonitoring.return_value = mock_monitor
            mock_monitor.start_sync_job.return_value = MagicMock(id=1)

            with patch("app.services.riverside_sync.sync_tenant_mfa") as mock_mfa:
                # First tenant succeeds, second fails
                mock_mfa.side_effect = [
                    {"status": "success"},
                    Exception("Sync failed"),
                ]

                result = await sync_all_tenants(mock_session, skip_failed=True)

                assert result["status"] == "partial"
                assert result["tenants_processed"] == 1
                assert result["tenants_failed"] == 1

    @pytest.mark.asyncio
    async def test_sync_all_tenants_selective_sync(self, mock_tenants):
        """Test batch sync with selective data types."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = mock_tenants

        with patch("app.services.riverside_sync.MonitoringService") as MockMonitoring:
            mock_monitor = MagicMock()
            MockMonitoring.return_value = mock_monitor
            mock_monitor.start_sync_job.return_value = MagicMock(id=1)

            with patch("app.services.riverside_sync.sync_tenant_mfa") as mock_mfa, \
                 patch("app.services.riverside_sync.sync_tenant_devices") as mock_devices:

                mock_mfa.return_value = {"status": "success"}
                mock_devices.return_value = {"status": "success"}

                result = await sync_all_tenants(
                    mock_session,
                    include_mfa=True,
                    include_devices=True,
                    include_requirements=False,
                    include_maturity=False,
                )

                assert result["status"] == "success"
                mock_mfa.assert_called()
                mock_devices.assert_called()

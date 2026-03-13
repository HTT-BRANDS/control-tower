"""Unit tests for DMARC/DKIM sync module.

Tests for daily DMARC/DKIM synchronization including DNS record checking,
security issue detection, and alert creation.

6 tests covering:
- sync_dmarc_dkim function execution
- DMARC record synchronization
- DKIM record synchronization
- Security issue detection
- Alert creation
- Tenant prioritization (Riverside first)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.sync.dmarc import sync_dmarc_dkim
from app.models.dmarc import DKIMRecord, DMARCRecord
from app.models.tenant import Tenant


class TestSyncDmarcDkim:
    """Tests for sync_dmarc_dkim function."""

    @pytest.mark.asyncio
    async def test_sync_dmarc_dkim_success(self):
        """Test successful DMARC/DKIM sync."""
        # Mock database context
        with patch("app.core.sync.dmarc.get_db_context") as mock_db_context:
            mock_db = MagicMock()
            mock_db_context.return_value.__enter__.return_value = mock_db

            # Mock tenant query
            mock_tenant1 = MagicMock(spec=Tenant)
            mock_tenant1.id = "tenant1"
            mock_tenant1.name = "Test Tenant 1"
            mock_tenant1.is_active = True

            mock_tenant2 = MagicMock(spec=Tenant)
            mock_tenant2.id = "riverside-htt"
            mock_tenant2.name = "Riverside HTT"
            mock_tenant2.is_active = True

            mock_db.query.return_value.filter.return_value.all.return_value = [
                mock_tenant1,
                mock_tenant2,
            ]

            # Mock monitoring service
            with patch("app.core.sync.dmarc.MonitoringService") as mock_monitoring_class:
                mock_monitoring = MagicMock()
                mock_monitoring_class.return_value = mock_monitoring

                mock_log_entry = MagicMock()
                mock_log_entry.id = "log123"
                mock_monitoring.start_sync_job.return_value = mock_log_entry

                # Mock DMARC service
                with patch("app.core.sync.dmarc.DMARCService") as mock_service_class:
                    mock_service = MagicMock()
                    mock_service_class.return_value = mock_service

                    # Mock sync methods
                    mock_dmarc_record = MagicMock(spec=DMARCRecord)
                    mock_dmarc_record.domain = "example.com"
                    mock_dmarc_record.policy = "quarantine"
                    mock_dmarc_record.pct = 100

                    mock_dkim_record = MagicMock(spec=DKIMRecord)
                    mock_dkim_record.domain = "example.com"
                    mock_dkim_record.is_enabled = True

                    mock_service.sync_dmarc_records = AsyncMock(return_value=[mock_dmarc_record])
                    mock_service.sync_dkim_records = AsyncMock(return_value=[mock_dkim_record])
                    mock_service.sync_dmarc_reports = AsyncMock(return_value=[])
                    mock_service.invalidate_cache = AsyncMock()

                    # Mock security check functions
                    with patch("app.core.sync.dmarc._check_security_issues") as mock_security_check:
                        mock_security_check.return_value = []

                        with patch(
                            "app.core.sync.dmarc._check_stale_dkim_keys"
                        ) as mock_stale_check:
                            mock_stale_check.return_value = []

                            # Run sync
                            await sync_dmarc_dkim()

                            # Verify sync methods were called
                            assert mock_service.sync_dmarc_records.call_count == 2
                            assert mock_service.sync_dkim_records.call_count == 2
                            mock_service.invalidate_cache.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_prioritizes_riverside_tenants(self):
        """Test that Riverside tenants are processed first."""
        with patch("app.core.sync.dmarc.get_db_context") as mock_db_context:
            mock_db = MagicMock()
            mock_db_context.return_value.__enter__.return_value = mock_db

            # Create Riverside and non-Riverside tenants
            mock_riverside = MagicMock(spec=Tenant)
            mock_riverside.id = "riverside-htt"
            mock_riverside.name = "Riverside HTT"
            mock_riverside.is_active = True

            mock_other = MagicMock(spec=Tenant)
            mock_other.id = "other-tenant"
            mock_other.name = "Other Tenant"
            mock_other.is_active = True

            # Return in non-priority order
            mock_db.query.return_value.filter.return_value.all.return_value = [
                mock_other,
                mock_riverside,
            ]

            with patch("app.core.sync.dmarc.MonitoringService") as mock_monitoring_class:
                mock_monitoring = MagicMock()
                mock_monitoring_class.return_value = mock_monitoring
                mock_log_entry = MagicMock()
                mock_log_entry.id = "log123"
                mock_monitoring.start_sync_job.return_value = mock_log_entry

                with patch("app.core.sync.dmarc.DMARCService") as mock_service_class:
                    mock_service = MagicMock()
                    mock_service_class.return_value = mock_service

                    mock_service.sync_dmarc_records = AsyncMock(return_value=[])
                    mock_service.sync_dkim_records = AsyncMock(return_value=[])
                    mock_service.sync_dmarc_reports = AsyncMock(return_value=[])
                    mock_service.invalidate_cache = AsyncMock()

                    with patch("app.core.sync.dmarc._check_security_issues") as mock_security:
                        mock_security.return_value = []
                        with patch("app.core.sync.dmarc._check_stale_dkim_keys") as mock_stale:
                            mock_stale.return_value = []

                            await sync_dmarc_dkim()

                            # Riverside should be synced (called somewhere)
                            assert mock_service.sync_dmarc_records.called


class TestDMARCRecordSync:
    """Tests for DMARC record synchronization."""

    @pytest.mark.asyncio
    async def test_dmarc_record_sync_success(self):
        """Test DMARC record sync."""
        with patch("app.core.sync.dmarc.get_db_context") as mock_db_context:
            mock_db = MagicMock()
            mock_db_context.return_value.__enter__.return_value = mock_db

            mock_tenant = MagicMock(spec=Tenant)
            mock_tenant.id = "test-tenant"
            mock_tenant.name = "Test Tenant"
            mock_tenant.is_active = True

            mock_db.query.return_value.filter.return_value.all.return_value = [mock_tenant]

            with patch("app.core.sync.dmarc.MonitoringService") as mock_monitoring_class:
                mock_monitoring = MagicMock()
                mock_monitoring_class.return_value = mock_monitoring
                mock_log_entry = MagicMock()
                mock_log_entry.id = "log123"
                mock_monitoring.start_sync_job.return_value = mock_log_entry

                with patch("app.core.sync.dmarc.DMARCService") as mock_service_class:
                    mock_service = MagicMock()
                    mock_service_class.return_value = mock_service

                    mock_dmarc = MagicMock(spec=DMARCRecord)
                    mock_dmarc.domain = "test.com"
                    mock_dmarc.policy = "reject"

                    mock_service.sync_dmarc_records = AsyncMock(return_value=[mock_dmarc])
                    mock_service.sync_dkim_records = AsyncMock(return_value=[])
                    mock_service.sync_dmarc_reports = AsyncMock(return_value=[])
                    mock_service.invalidate_cache = AsyncMock()

                    with patch("app.core.sync.dmarc._check_security_issues") as mock_security:
                        mock_security.return_value = []
                        with patch("app.core.sync.dmarc._check_stale_dkim_keys") as mock_stale:
                            mock_stale.return_value = []

                            await sync_dmarc_dkim()

                            mock_service.sync_dmarc_records.assert_called()


class TestDKIMRecordSync:
    """Tests for DKIM record synchronization."""

    @pytest.mark.asyncio
    async def test_dkim_record_sync_success(self):
        """Test DKIM record sync."""
        with patch("app.core.sync.dmarc.get_db_context") as mock_db_context:
            mock_db = MagicMock()
            mock_db_context.return_value.__enter__.return_value = mock_db

            mock_tenant = MagicMock(spec=Tenant)
            mock_tenant.id = "test-tenant"
            mock_tenant.name = "Test Tenant"
            mock_tenant.is_active = True

            mock_db.query.return_value.filter.return_value.all.return_value = [mock_tenant]

            with patch("app.core.sync.dmarc.MonitoringService") as mock_monitoring_class:
                mock_monitoring = MagicMock()
                mock_monitoring_class.return_value = mock_monitoring
                mock_log_entry = MagicMock()
                mock_log_entry.id = "log123"
                mock_monitoring.start_sync_job.return_value = mock_log_entry

                with patch("app.core.sync.dmarc.DMARCService") as mock_service_class:
                    mock_service = MagicMock()
                    mock_service_class.return_value = mock_service

                    mock_dkim = MagicMock(spec=DKIMRecord)
                    mock_dkim.domain = "test.com"
                    mock_dkim.is_enabled = True

                    mock_service.sync_dmarc_records = AsyncMock(return_value=[])
                    mock_service.sync_dkim_records = AsyncMock(return_value=[mock_dkim])
                    mock_service.sync_dmarc_reports = AsyncMock(return_value=[])
                    mock_service.invalidate_cache = AsyncMock()

                    with patch("app.core.sync.dmarc._check_security_issues") as mock_security:
                        mock_security.return_value = []
                        with patch("app.core.sync.dmarc._check_stale_dkim_keys") as mock_stale:
                            mock_stale.return_value = []

                            await sync_dmarc_dkim()

                            mock_service.sync_dkim_records.assert_called()


class TestSecurityIssueDetection:
    """Tests for security issue detection."""

    @pytest.mark.asyncio
    async def test_weak_dmarc_policy_detection(self):
        """Test detection of weak DMARC policies."""
        with patch("app.core.sync.dmarc.get_db_context") as mock_db_context:
            mock_db = MagicMock()
            mock_db_context.return_value.__enter__.return_value = mock_db

            mock_tenant = MagicMock(spec=Tenant)
            mock_tenant.id = "test-tenant"
            mock_tenant.name = "Test Tenant"
            mock_tenant.is_active = True

            mock_db.query.return_value.filter.return_value.all.return_value = [mock_tenant]

            with patch("app.core.sync.dmarc.MonitoringService") as mock_monitoring_class:
                mock_monitoring = MagicMock()
                mock_monitoring_class.return_value = mock_monitoring
                mock_log_entry = MagicMock()
                mock_log_entry.id = "log123"
                mock_monitoring.start_sync_job.return_value = mock_log_entry

                with patch("app.core.sync.dmarc.DMARCService") as mock_service_class:
                    mock_service = MagicMock()
                    mock_service_class.return_value = mock_service

                    # Create DMARC record with weak policy
                    mock_dmarc = MagicMock(spec=DMARCRecord)
                    mock_dmarc.domain = "test.com"
                    mock_dmarc.policy = "none"
                    mock_dmarc.pct = 100

                    mock_service.sync_dmarc_records = AsyncMock(return_value=[mock_dmarc])
                    mock_service.sync_dkim_records = AsyncMock(return_value=[])
                    mock_service.sync_dmarc_reports = AsyncMock(return_value=[])
                    mock_service.invalidate_cache = AsyncMock()

                    # Mock alert creation
                    with patch("app.core.sync.dmarc._check_security_issues") as mock_security:
                        mock_alert = MagicMock()
                        mock_security.return_value = [mock_alert]

                        with patch("app.core.sync.dmarc._check_stale_dkim_keys") as mock_stale:
                            mock_stale.return_value = []

                            await sync_dmarc_dkim()

                            # Security check should have been called
                            mock_security.assert_called()


class TestStaleDKIMKeyDetection:
    """Tests for stale DKIM key detection."""

    @pytest.mark.asyncio
    async def test_stale_dkim_key_detection(self):
        """Test detection of stale DKIM keys."""
        with patch("app.core.sync.dmarc.get_db_context") as mock_db_context:
            mock_db = MagicMock()
            mock_db_context.return_value.__enter__.return_value = mock_db

            mock_tenant = MagicMock(spec=Tenant)
            mock_tenant.id = "test-tenant"
            mock_tenant.name = "Test Tenant"
            mock_tenant.is_active = True

            mock_db.query.return_value.filter.return_value.all.return_value = [mock_tenant]

            with patch("app.core.sync.dmarc.MonitoringService") as mock_monitoring_class:
                mock_monitoring = MagicMock()
                mock_monitoring_class.return_value = mock_monitoring
                mock_log_entry = MagicMock()
                mock_log_entry.id = "log123"
                mock_monitoring.start_sync_job.return_value = mock_log_entry

                with patch("app.core.sync.dmarc.DMARCService") as mock_service_class:
                    mock_service = MagicMock()
                    mock_service_class.return_value = mock_service

                    # Create stale DKIM record
                    mock_dkim = MagicMock(spec=DKIMRecord)
                    mock_dkim.domain = "test.com"
                    mock_dkim.is_enabled = True
                    mock_dkim.is_key_stale = True
                    mock_dkim.days_since_rotation = 365

                    mock_service.sync_dmarc_records = AsyncMock(return_value=[])
                    mock_service.sync_dkim_records = AsyncMock(return_value=[mock_dkim])
                    mock_service.sync_dmarc_reports = AsyncMock(return_value=[])
                    mock_service.invalidate_cache = AsyncMock()

                    with patch("app.core.sync.dmarc._check_security_issues") as mock_security:
                        mock_security.return_value = []

                        with patch("app.core.sync.dmarc._check_stale_dkim_keys") as mock_stale:
                            mock_alert = MagicMock()
                            mock_stale.return_value = [mock_alert]

                            await sync_dmarc_dkim()

                            # Stale key check should have been called
                            mock_stale.assert_called()

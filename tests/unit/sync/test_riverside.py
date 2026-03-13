"""Unit tests for Riverside compliance sync module.

Tests for scheduled Riverside data synchronization including MFA enrollment,
device compliance, requirement tracking, and maturity calculations.

6 tests covering:
- sync_riverside function execution
- MFA data synchronization
- Device compliance synchronization
- Requirement status synchronization
- Maturity score calculation
- Error handling and monitoring
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.sync.riverside import sync_riverside


class TestSyncRiverside:
    """Tests for sync_riverside function."""

    @pytest.mark.asyncio
    async def test_sync_riverside_success(self):
        """Test successful Riverside compliance sync."""
        # Mock database context
        with patch("app.core.sync.riverside.get_db_context") as mock_db_context:
            mock_db = MagicMock()
            mock_db_context.return_value.__enter__.return_value = mock_db

            # Mock monitoring service
            with patch("app.core.sync.riverside.MonitoringService") as mock_monitoring_class:
                mock_monitoring = MagicMock()
                mock_monitoring_class.return_value = mock_monitoring

                mock_log_entry = MagicMock()
                mock_log_entry.id = "log123"
                mock_monitoring.start_sync_job.return_value = mock_log_entry

                # Mock Riverside service
                with patch("app.core.sync.riverside.RiversideService") as mock_service_class:
                    mock_service = MagicMock()
                    mock_service_class.return_value = mock_service

                    # Mock sync methods
                    mock_service.sync_riverside_mfa = AsyncMock(
                        return_value={
                            "tenant1": {"status": "success"},
                            "tenant2": {"status": "success"},
                        }
                    )
                    mock_service.sync_riverside_device_compliance = AsyncMock(
                        return_value={
                            "tenant1": {"status": "success"},
                            "tenant2": {"status": "success"},
                        }
                    )
                    mock_service.sync_riverside_requirements = AsyncMock(
                        return_value={"requirements_synced": 5}
                    )
                    mock_service.sync_riverside_maturity_scores = AsyncMock(
                        return_value={
                            "tenant1": {"status": "success"},
                            "tenant2": {"status": "success"},
                        }
                    )

                    results = await sync_riverside()

                    # Verify results
                    assert results["mfa_synced"] == 2
                    assert results["device_synced"] == 2
                    assert results["requirements_synced"] == 5
                    assert results["maturity_calculated"] == 2

                    # Verify monitoring was called
                    mock_monitoring.start_sync_job.assert_called_once_with(job_type="riverside")
                    mock_monitoring.complete_sync_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_riverside_with_errors(self):
        """Test Riverside sync with some tenant errors."""
        with patch("app.core.sync.riverside.get_db_context") as mock_db_context:
            mock_db = MagicMock()
            mock_db_context.return_value.__enter__.return_value = mock_db

            with patch("app.core.sync.riverside.MonitoringService") as mock_monitoring_class:
                mock_monitoring = MagicMock()
                mock_monitoring_class.return_value = mock_monitoring

                mock_log_entry = MagicMock()
                mock_log_entry.id = "log123"
                mock_monitoring.start_sync_job.return_value = mock_log_entry

                with patch("app.core.sync.riverside.RiversideService") as mock_service_class:
                    mock_service = MagicMock()
                    mock_service_class.return_value = mock_service

                    # Mock with some errors
                    mock_service.sync_riverside_mfa = AsyncMock(
                        return_value={
                            "tenant1": {"status": "success"},
                            "tenant2": {"status": "error", "error": "Connection failed"},
                        }
                    )
                    mock_service.sync_riverside_device_compliance = AsyncMock(
                        return_value={
                            "tenant1": {"status": "success"},
                            "tenant2": {"status": "success"},
                        }
                    )
                    mock_service.sync_riverside_requirements = AsyncMock(
                        return_value={"requirements_synced": 3}
                    )
                    mock_service.sync_riverside_maturity_scores = AsyncMock(
                        return_value={
                            "tenant1": {"status": "success"},
                            "tenant2": {"status": "success"},
                        }
                    )

                    results = await sync_riverside()

                    # Should have 1 success for MFA (tenant2 error)
                    assert results["mfa_synced"] == 1


class TestMFASync:
    """Tests for MFA data synchronization."""

    @pytest.mark.asyncio
    async def test_mfa_sync_success(self):
        """Test MFA enrollment sync."""
        with patch("app.core.sync.riverside.get_db_context") as mock_db_context:
            mock_db = MagicMock()
            mock_db_context.return_value.__enter__.return_value = mock_db

            with patch("app.core.sync.riverside.MonitoringService") as mock_monitoring_class:
                mock_monitoring = MagicMock()
                mock_monitoring_class.return_value = mock_monitoring
                mock_log_entry = MagicMock()
                mock_log_entry.id = "log123"
                mock_monitoring.start_sync_job.return_value = mock_log_entry

                with patch("app.core.sync.riverside.RiversideService") as mock_service_class:
                    mock_service = MagicMock()
                    mock_service_class.return_value = mock_service

                    mock_service.sync_riverside_mfa = AsyncMock(
                        return_value={
                            "tenant1": {
                                "status": "success",
                                "enrollment_rate": 95.5,
                            }
                        }
                    )
                    mock_service.sync_riverside_device_compliance = AsyncMock(return_value={})
                    mock_service.sync_riverside_requirements = AsyncMock(
                        return_value={"requirements_synced": 0}
                    )
                    mock_service.sync_riverside_maturity_scores = AsyncMock(return_value={})

                    await sync_riverside()

                    # Verify MFA sync was called
                    mock_service.sync_riverside_mfa.assert_called_once()


class TestDeviceComplianceSync:
    """Tests for device compliance synchronization."""

    @pytest.mark.asyncio
    async def test_device_compliance_sync_success(self):
        """Test device compliance sync."""
        with patch("app.core.sync.riverside.get_db_context") as mock_db_context:
            mock_db = MagicMock()
            mock_db_context.return_value.__enter__.return_value = mock_db

            with patch("app.core.sync.riverside.MonitoringService") as mock_monitoring_class:
                mock_monitoring = MagicMock()
                mock_monitoring_class.return_value = mock_monitoring
                mock_log_entry = MagicMock()
                mock_log_entry.id = "log123"
                mock_monitoring.start_sync_job.return_value = mock_log_entry

                with patch("app.core.sync.riverside.RiversideService") as mock_service_class:
                    mock_service = MagicMock()
                    mock_service_class.return_value = mock_service

                    mock_service.sync_riverside_mfa = AsyncMock(return_value={})
                    mock_service.sync_riverside_device_compliance = AsyncMock(
                        return_value={"tenant1": {"status": "success", "devices_synced": 150}}
                    )
                    mock_service.sync_riverside_requirements = AsyncMock(
                        return_value={"requirements_synced": 0}
                    )
                    mock_service.sync_riverside_maturity_scores = AsyncMock(return_value={})

                    await sync_riverside()

                    # Verify device compliance sync was called
                    mock_service.sync_riverside_device_compliance.assert_called_once()


class TestRequirementsSync:
    """Tests for requirement status synchronization."""

    @pytest.mark.asyncio
    async def test_requirements_sync_success(self):
        """Test requirement status sync."""
        with patch("app.core.sync.riverside.get_db_context") as mock_db_context:
            mock_db = MagicMock()
            mock_db_context.return_value.__enter__.return_value = mock_db

            with patch("app.core.sync.riverside.MonitoringService") as mock_monitoring_class:
                mock_monitoring = MagicMock()
                mock_monitoring_class.return_value = mock_monitoring
                mock_log_entry = MagicMock()
                mock_log_entry.id = "log123"
                mock_monitoring.start_sync_job.return_value = mock_log_entry

                with patch("app.core.sync.riverside.RiversideService") as mock_service_class:
                    mock_service = MagicMock()
                    mock_service_class.return_value = mock_service

                    mock_service.sync_riverside_mfa = AsyncMock(return_value={})
                    mock_service.sync_riverside_device_compliance = AsyncMock(return_value={})
                    mock_service.sync_riverside_requirements = AsyncMock(
                        return_value={"requirements_synced": 12}
                    )
                    mock_service.sync_riverside_maturity_scores = AsyncMock(return_value={})

                    results = await sync_riverside()

                    # Verify requirements sync was called
                    assert results["requirements_synced"] == 12
                    mock_service.sync_riverside_requirements.assert_called_once()


class TestMaturityScoreCalculation:
    """Tests for maturity score calculation."""

    @pytest.mark.asyncio
    async def test_maturity_score_calculation_success(self):
        """Test maturity score calculation."""
        with patch("app.core.sync.riverside.get_db_context") as mock_db_context:
            mock_db = MagicMock()
            mock_db_context.return_value.__enter__.return_value = mock_db

            with patch("app.core.sync.riverside.MonitoringService") as mock_monitoring_class:
                mock_monitoring = MagicMock()
                mock_monitoring_class.return_value = mock_monitoring
                mock_log_entry = MagicMock()
                mock_log_entry.id = "log123"
                mock_monitoring.start_sync_job.return_value = mock_log_entry

                with patch("app.core.sync.riverside.RiversideService") as mock_service_class:
                    mock_service = MagicMock()
                    mock_service_class.return_value = mock_service

                    mock_service.sync_riverside_mfa = AsyncMock(return_value={})
                    mock_service.sync_riverside_device_compliance = AsyncMock(return_value={})
                    mock_service.sync_riverside_requirements = AsyncMock(
                        return_value={"requirements_synced": 0}
                    )
                    mock_service.sync_riverside_maturity_scores = AsyncMock(
                        return_value={"tenant1": {"status": "success", "maturity_score": 3.5}}
                    )

                    results = await sync_riverside()

                    # Verify maturity calculation was called
                    assert results["maturity_calculated"] == 1
                    mock_service.sync_riverside_maturity_scores.assert_called_once()

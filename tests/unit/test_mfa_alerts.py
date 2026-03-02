"""Unit tests for MFA alert detection and notification system.

Tests the MFAGapDetector class and related functions for detecting
MFA enrollment gaps and triggering notifications across Riverside tenants.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.alerts.mfa_alerts import (
    ADMIN_MFA_TARGET,
    MFAComplianceStatus,
    MFAGapDetector,
    RIVERSIDE_TENANTS,
    USER_MFA_TARGET,
    check_admin_mfa_compliance,
    check_user_mfa_compliance,
    detect_mfa_gaps,
    trigger_mfa_alert,
)
from app.core.notifications import Severity


class TestMFAComplianceStatus:
    """Tests for MFAComplianceStatus dataclass."""

    def test_compliance_status_creation(self):
        """Test creating MFAComplianceStatus with default compliance."""
        now = datetime.utcnow()
        status = MFAComplianceStatus(
            tenant_id="HTT",
            user_mfa_percentage=96.0,
            admin_mfa_percentage=100.0,
            total_users=100,
            mfa_enrolled_users=96,
            admin_accounts_total=5,
            admin_accounts_mfa=5,
            unprotected_admins=0,
            snapshot_date=now,
        )

        assert status.tenant_id == "HTT"
        assert status.user_mfa_percentage == 96.0
        assert status.admin_mfa_percentage == 100.0
        assert status.user_compliant is True
        assert status.admin_compliant is True

    def test_compliance_status_below_thresholds(self):
        """Test compliance status below thresholds."""
        now = datetime.utcnow()
        status = MFAComplianceStatus(
            tenant_id="BCC",
            user_mfa_percentage=90.0,
            admin_mfa_percentage=80.0,
            total_users=100,
            mfa_enrolled_users=90,
            admin_accounts_total=5,
            admin_accounts_mfa=4,
            unprotected_admins=1,
            snapshot_date=now,
        )

        assert status.user_compliant is False
        assert status.admin_compliant is False

    def test_compliance_status_edge_cases(self):
        """Test compliance at exact thresholds."""
        now = datetime.utcnow()

        # Exactly at user threshold
        status = MFAComplianceStatus(
            tenant_id="FN",
            user_mfa_percentage=95.0,
            admin_mfa_percentage=100.0,
            total_users=100,
            mfa_enrolled_users=95,
            admin_accounts_total=3,
            admin_accounts_mfa=3,
            unprotected_admins=0,
            snapshot_date=now,
        )
        assert status.user_compliant is True
        assert status.admin_compliant is True

        # Just below thresholds
        status = MFAComplianceStatus(
            tenant_id="TLL",
            user_mfa_percentage=94.9,
            admin_mfa_percentage=99.9,
            total_users=100,
            mfa_enrolled_users=94,
            admin_accounts_total=3,
            admin_accounts_mfa=2,
            unprotected_admins=1,
            snapshot_date=now,
        )
        assert status.user_compliant is False
        assert status.admin_compliant is False


class TestMFAGapDetectorInit:
    """Tests for MFAGapDetector initialization."""

    def test_detector_init_without_session(self):
        """Test detector initializes without database session."""
        detector = MFAGapDetector()
        assert detector._db is None
        assert detector._riv_tenants == set(RIVERSIDE_TENANTS)

    def test_detector_init_with_session(self):
        """Test detector initializes with database session."""
        mock_db = MagicMock(spec=Session)
        detector = MFAGapDetector(db=mock_db)
        assert detector._db == mock_db


class TestMFAGapDetectorDetectGaps:
    """Tests for MFAGapDetector.detect_gaps method."""

    @patch("app.alerts.mfa_alerts.get_db_context")
    async def test_detect_gaps_no_session(self, mock_get_db_context):
        """Test detection creates session when not provided."""
        mock_session = MagicMock(spec=Session)
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_session)
        mock_context.__exit__ = MagicMock(return_value=None)
        mock_get_db_context.return_value = mock_context

        # Mock query results - empty (all compliant)
        mock_session.query.return_value.filter.return_value.group_by.return_value.subquery.return_value = MagicMock()
        mock_session.query.return_value.join.return_value.all.return_value = []

        detector = MFAGapDetector()
        gaps = await detector.detect_gaps()

        # Should return empty list when all compliant
        assert gaps == []

    async def test_detect_gaps_with_session(self):
        """Test detection with provided session."""
        mock_session = MagicMock(spec=Session)

        # Mock MFA record - compliant
        mock_record = MagicMock()
        mock_record.tenant_id = "HTT"
        mock_record.mfa_coverage_percentage = 96.0
        mock_record.admin_mfa_percentage = 100.0
        mock_record.total_users = 100
        mock_record.mfa_enrolled_users = 96
        mock_record.admin_accounts_total = 5
        mock_record.admin_accounts_mfa = 5
        mock_record.snapshot_date = datetime.utcnow()

        mock_session.query.return_value.filter.return_value.group_by.return_value.subquery.return_value = MagicMock()
        mock_session.query.return_value.join.return_value.all.return_value = [mock_record]

        detector = MFAGapDetector(db=mock_session)
        gaps = await detector.detect_gaps(mock_session)

        # Compliant tenant should not be in gaps
        assert len(gaps) == 0

    @patch("app.alerts.mfa_alerts.get_db_context")
    async def test_detect_gaps_finds_violations(self, mock_get_db_context):
        """Test detection finds non-compliant tenants."""
        mock_session = MagicMock(spec=Session)
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_session)
        mock_context.__exit__ = MagicMock(return_value=None)
        mock_get_db_context.return_value = mock_context

        # Mock non-compliant record
        mock_record = MagicMock()
        mock_record.tenant_id = "BCC"
        mock_record.mfa_coverage_percentage = 90.0  # Below 95%
        mock_record.admin_mfa_percentage = 80.0  # Below 100%
        mock_record.total_users = 100
        mock_record.mfa_enrolled_users = 90
        mock_record.admin_accounts_total = 5
        mock_record.admin_accounts_mfa = 4
        mock_record.snapshot_date = datetime.utcnow()

        mock_session.query.return_value.filter.return_value.group_by.return_value.subquery.return_value = MagicMock()
        mock_session.query.return_value.join.return_value.all.return_value = [mock_record]

        detector = MFAGapDetector()
        gaps = await detector.detect_gaps()

        assert len(gaps) == 1
        assert gaps[0].tenant_id == "BCC"
        assert gaps[0].user_mfa_percentage == 90.0
        assert gaps[0].admin_mfa_percentage == 80.0
        assert gaps[0].unprotected_admins == 1

    @patch("app.alerts.mfa_alerts.get_db_context")
    async def test_detect_gaps_multiple_tenants(self, mock_get_db_context):
        """Test detection with multiple tenant records."""
        mock_session = MagicMock(spec=Session)
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_session)
        mock_context.__exit__ = MagicMock(return_value=None)
        mock_get_db_context.return_value = mock_context

        # Mock multiple records - mix of compliant and non-compliant
        compliant_record = MagicMock()
        compliant_record.tenant_id = "HTT"
        compliant_record.mfa_coverage_percentage = 96.0
        compliant_record.admin_mfa_percentage = 100.0
        compliant_record.total_users = 100
        compliant_record.mfa_enrolled_users = 96
        compliant_record.admin_accounts_total = 5
        compliant_record.admin_accounts_mfa = 5
        compliant_record.snapshot_date = datetime.utcnow()

        non_compliant_record = MagicMock()
        non_compliant_record.tenant_id = "DCE"
        non_compliant_record.mfa_coverage_percentage = 92.0
        non_compliant_record.admin_mfa_percentage = 100.0
        non_compliant_record.total_users = 50
        non_compliant_record.mfa_enrolled_users = 46
        non_compliant_record.admin_accounts_total = 3
        non_compliant_record.admin_accounts_mfa = 3
        non_compliant_record.snapshot_date = datetime.utcnow()

        mock_session.query.return_value.filter.return_value.group_by.return_value.subquery.return_value = MagicMock()
        mock_session.query.return_value.join.return_value.all.return_value = [
            compliant_record,
            non_compliant_record,
        ]

        detector = MFAGapDetector()
        gaps = await detector.detect_gaps()

        assert len(gaps) == 1
        assert gaps[0].tenant_id == "DCE"

    @patch("app.alerts.mfa_alerts.get_db_context")
    @patch("app.alerts.mfa_alerts.logger")
    async def test_detect_gaps_database_error(self, mock_logger, mock_get_db_context):
        """Test detection handles database errors gracefully."""
        mock_get_db_context.side_effect = Exception("Database connection failed")

        detector = MFAGapDetector()
        gaps = await detector.detect_gaps()

        # Should return empty list on error
        assert gaps == []
        mock_logger.error.assert_called()


class TestMFAGapDetectorCheckAdminCompliance:
    """Tests for admin MFA compliance checking."""

    @patch("app.alerts.mfa_alerts.get_db_context")
    async def test_check_admin_compliance_finds_only_admin_gaps(self, mock_get_db_context):
        """Test admin check returns only admin-violating tenants."""
        mock_session = MagicMock(spec=Session)
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_session)
        mock_context.__exit__ = MagicMock(return_value=None)
        mock_get_db_context.return_value = mock_context

        # Record with user gap but admin compliant
        user_gap_record = MagicMock()
        user_gap_record.tenant_id = "FN"
        user_gap_record.mfa_coverage_percentage = 90.0  # Below 95%
        user_gap_record.admin_mfa_percentage = 100.0  # Compliant
        user_gap_record.total_users = 100
        user_gap_record.mfa_enrolled_users = 90
        user_gap_record.admin_accounts_total = 5
        user_gap_record.admin_accounts_mfa = 5
        user_gap_record.snapshot_date = datetime.utcnow()

        # Record with admin gap
        admin_gap_record = MagicMock()
        admin_gap_record.tenant_id = "TLL"
        admin_gap_record.mfa_coverage_percentage = 96.0  # Compliant
        admin_gap_record.admin_mfa_percentage = 80.0  # Below 100%
        admin_gap_record.total_users = 100
        admin_gap_record.mfa_enrolled_users = 96
        admin_gap_record.admin_accounts_total = 5
        admin_gap_record.admin_accounts_mfa = 4
        admin_gap_record.snapshot_date = datetime.utcnow()

        mock_session.query.return_value.filter.return_value.group_by.return_value.subquery.return_value = MagicMock()
        mock_session.query.return_value.join.return_value.all.return_value = [
            user_gap_record,
            admin_gap_record,
        ]

        detector = MFAGapDetector()
        gaps = await detector.check_admin_compliance()

        # Should only return TLL (admin gap), not FN (only user gap)
        assert len(gaps) == 1
        assert gaps[0].tenant_id == "TLL"
        assert gaps[0].admin_compliant is False


class TestMFAGapDetectorCheckUserCompliance:
    """Tests for user MFA compliance checking."""

    @patch("app.alerts.mfa_alerts.get_db_context")
    async def test_check_user_compliance_finds_only_user_gaps(self, mock_get_db_context):
        """Test user check returns only user-violating tenants."""
        mock_session = MagicMock(spec=Session)
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_session)
        mock_context.__exit__ = MagicMock(return_value=None)
        mock_get_db_context.return_value = mock_context

        # Record with user gap
        user_gap_record = MagicMock()
        user_gap_record.tenant_id = "BCC"
        user_gap_record.mfa_coverage_percentage = 90.0  # Below 95%
        user_gap_record.admin_mfa_percentage = 100.0  # Compliant
        user_gap_record.total_users = 100
        user_gap_record.mfa_enrolled_users = 90
        user_gap_record.admin_accounts_total = 5
        user_gap_record.admin_accounts_mfa = 5
        user_gap_record.snapshot_date = datetime.utcnow()

        # Record with only admin gap
        admin_gap_record = MagicMock()
        admin_gap_record.tenant_id = "DCE"
        admin_gap_record.mfa_coverage_percentage = 96.0  # Compliant
        admin_gap_record.admin_mfa_percentage = 66.7  # Below 100%
        admin_gap_record.total_users = 100
        admin_gap_record.mfa_enrolled_users = 96
        admin_gap_record.admin_accounts_total = 3
        admin_gap_record.admin_accounts_mfa = 2
        admin_gap_record.snapshot_date = datetime.utcnow()

        mock_session.query.return_value.filter.return_value.group_by.return_value.subquery.return_value = MagicMock()
        mock_session.query.return_value.join.return_value.all.return_value = [
            user_gap_record,
            admin_gap_record,
        ]

        detector = MFAGapDetector()
        gaps = await detector.check_user_compliance()

        # Should only return BCC (user gap), not DCE (only admin gap)
        assert len(gaps) == 1
        assert gaps[0].tenant_id == "BCC"
        assert gaps[0].user_compliant is False


class TestMFAGapDetectorTriggerAlert:
    """Tests for MFA alert triggering."""

    @patch("app.alerts.mfa_alerts.send_notification")
    @patch("app.alerts.mfa_alerts.should_notify")
    async def test_trigger_alert_admin_violation(self, mock_should_notify, mock_send):
        """Test HIGH severity alert for admin MFA violation."""
        mock_should_notify.return_value = True
        mock_send.return_value = {"success": True}

        now = datetime.utcnow()
        status = MFAComplianceStatus(
            tenant_id="HTT",
            user_mfa_percentage=96.0,
            admin_mfa_percentage=80.0,
            total_users=100,
            mfa_enrolled_users=96,
            admin_accounts_total=5,
            admin_accounts_mfa=4,
            unprotected_admins=1,
            snapshot_date=now,
        )

        detector = MFAGapDetector()
        result = await detector.trigger_alert(status)

        assert result["success"] is True
        assert result["tenant_id"] == "HTT"
        assert result["severity"] == "error"

        # Verify notification was called with ERROR severity (admin gap = critical)
        call_args = mock_send.call_args[0][0]
        assert call_args.severity == Severity.ERROR

    @patch("app.alerts.mfa_alerts.send_notification")
    @patch("app.alerts.mfa_alerts.should_notify")
    async def test_trigger_alert_user_violation_only(self, mock_should_notify, mock_send):
        """Test MEDIUM severity alert for user-only MFA violation."""
        mock_should_notify.return_value = True
        mock_send.return_value = {"success": True}

        now = datetime.utcnow()
        status = MFAComplianceStatus(
            tenant_id="BCC",
            user_mfa_percentage=90.0,
            admin_mfa_percentage=100.0,
            total_users=100,
            mfa_enrolled_users=90,
            admin_accounts_total=5,
            admin_accounts_mfa=5,
            unprotected_admins=0,
            snapshot_date=now,
        )

        detector = MFAGapDetector()
        result = await detector.trigger_alert(status)

        assert result["success"] is True
        assert result["severity"] == "warning"

        # Verify notification was called with WARNING severity (user gap)
        call_args = mock_send.call_args[0][0]
        assert call_args.severity == Severity.WARNING

    @patch("app.alerts.mfa_alerts.send_notification")
    @patch("app.alerts.mfa_alerts.should_notify")
    async def test_trigger_alert_respects_cooldown(self, mock_should_notify, mock_send):
        """Test alert respects cooldown period."""
        mock_should_notify.return_value = False

        now = datetime.utcnow()
        status = MFAComplianceStatus(
            tenant_id="FN",
            user_mfa_percentage=90.0,
            admin_mfa_percentage=100.0,
            total_users=100,
            mfa_enrolled_users=90,
            admin_accounts_total=5,
            admin_accounts_mfa=5,
            unprotected_admins=0,
            snapshot_date=now,
        )

        detector = MFAGapDetector()
        result = await detector.trigger_alert(status)

        assert result["success"] is False
        assert result["reason"] == "in_cooldown"
        mock_send.assert_not_called()

    @patch("app.alerts.mfa_alerts.send_notification")
    @patch("app.alerts.mfa_alerts.should_notify")
    async def test_trigger_alert_forces_send(self, mock_should_notify, mock_send):
        """Test force flag bypasses cooldown."""
        mock_should_notify.return_value = False  # Would normally block
        mock_send.return_value = {"success": True}

        now = datetime.utcnow()
        status = MFAComplianceStatus(
            tenant_id="TLL",
            user_mfa_percentage=90.0,
            admin_mfa_percentage=100.0,
            total_users=100,
            mfa_enrolled_users=90,
            admin_accounts_total=5,
            admin_accounts_mfa=5,
            unprotected_admins=0,
            snapshot_date=now,
        )

        detector = MFAGapDetector()
        result = await detector.trigger_alert(status, force=True)

        assert result["success"] is True
        mock_should_notify.assert_not_called()  # Should skip check when forced
        mock_send.assert_called_once()


class TestMFAGapDetectorCheckAndAlert:
    """Tests for the combined check and alert method."""

    @patch("app.alerts.mfa_alerts.get_db_context")
    @patch("app.alerts.mfa_alerts.should_notify")
    @patch("app.alerts.mfa_alerts.send_notification")
    async def test_check_and_alert_success(self, mock_send, mock_should, mock_get_db):
        """Test full check and alert cycle."""
        mock_session = MagicMock(spec=Session)
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_session)
        mock_context.__exit__ = MagicMock(return_value=None)
        mock_get_db.return_value = mock_context

        mock_should.return_value = True
        mock_send.return_value = {"success": True}

        # Mock non-compliant record
        mock_record = MagicMock()
        mock_record.tenant_id = "HTT"
        mock_record.mfa_coverage_percentage = 90.0
        mock_record.admin_mfa_percentage = 100.0
        mock_record.total_users = 100
        mock_record.mfa_enrolled_users = 90
        mock_record.admin_accounts_total = 5
        mock_record.admin_accounts_mfa = 5
        mock_record.snapshot_date = datetime.utcnow()

        mock_session.query.return_value.filter.return_value.group_by.return_value.subquery.return_value = MagicMock()
        mock_session.query.return_value.join.return_value.all.return_value = [mock_record]

        detector = MFAGapDetector()
        result = await detector.check_and_alert()

        assert result["success"] is True
        assert result["gaps_found"] == 1
        assert result["alerts_sent"] == 1
        assert len(result["gaps"]) == 1
        assert result["gaps"][0]["tenant_id"] == "HTT"


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    @patch("app.alerts.mfa_alerts.MFAGapDetector")
    async def test_detect_mfa_gaps_convenience(self, mock_detector_class):
        """Test detect_mfa_gaps convenience function."""
        mock_detector = MagicMock()

        # Create an async mock that returns an empty list
        async def mock_detect(db=None):
            return []

        mock_detector.detect_gaps = mock_detect
        mock_detector_class.return_value = mock_detector

        result = await detect_mfa_gaps()

        mock_detector_class.assert_called_once()
        assert result == []

    @patch("app.alerts.mfa_alerts.MFAGapDetector")
    async def test_check_admin_mfa_compliance_convenience(self, mock_detector_class):
        """Test check_admin_mfa_compliance convenience function."""
        mock_detector = MagicMock()

        async def mock_check(db=None):
            return []

        mock_detector.check_admin_compliance = mock_check
        mock_detector_class.return_value = mock_detector

        result = await check_admin_mfa_compliance()

        mock_detector_class.assert_called_once()
        assert result == []

    @patch("app.alerts.mfa_alerts.MFAGapDetector")
    async def test_check_user_mfa_compliance_convenience(self, mock_detector_class):
        """Test check_user_mfa_compliance convenience function."""
        mock_detector = MagicMock()

        async def mock_check(db=None):
            return []

        mock_detector.check_user_compliance = mock_check
        mock_detector_class.return_value = mock_detector

        result = await check_user_mfa_compliance()

        mock_detector_class.assert_called_once()
        assert result == []

    @patch("app.alerts.mfa_alerts.MFAGapDetector")
    async def test_trigger_mfa_alert_convenience(self, mock_detector_class):
        """Test trigger_mfa_alert convenience function."""
        mock_detector = MagicMock()

        async def mock_trigger(status, force):
            return {"success": True}

        mock_detector.trigger_alert = mock_trigger
        mock_detector_class.return_value = mock_detector

        now = datetime.utcnow()
        status = MFAComplianceStatus(
            tenant_id="DCE",
            user_mfa_percentage=90.0,
            admin_mfa_percentage=100.0,
            total_users=100,
            mfa_enrolled_users=90,
            admin_accounts_total=5,
            admin_accounts_mfa=5,
            unprotected_admins=0,
            snapshot_date=now,
        )

        result = await trigger_mfa_alert(status, force=True)

        mock_detector_class.assert_called_once()
        assert result["success"] is True


class TestConstants:
    """Tests for module constants."""

    def test_riverside_tenants(self):
        """Test RIVERSIDE_TENANTS constant."""
        assert "HTT" in RIVERSIDE_TENANTS
        assert "BCC" in RIVERSIDE_TENANTS
        assert "FN" in RIVERSIDE_TENANTS
        assert "TLL" in RIVERSIDE_TENANTS
        assert "DCE" in RIVERSIDE_TENANTS
        assert len(RIVERSIDE_TENANTS) == 5

    def test_mfa_targets(self):
        """Test MFA target constants."""
        assert USER_MFA_TARGET == 95.0
        assert ADMIN_MFA_TARGET == 100.0

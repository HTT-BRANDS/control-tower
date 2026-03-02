"""Unit tests for deadline alert system.

Tests for the deadline_alerts module covering:
- DeadlineTracker class initialization and configuration
- Alert level calculations (INFO, WARNING, HIGH, CRITICAL)
- Deadline tracking with database queries
- Notification triggering and deduplication
- Alert filtering by level
"""

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.alerts.deadline_alerts import (
    ALERT_SCHEDULE,
    ALERT_TO_SEVERITY,
    DEFAULT_DEADLINE,
    AlertLevel,
    DeadlineAlert,
    DeadlineTracker,
    DeadlineTrackingResult,
    calculate_deadline_warnings,
    calculate_critical_alerts,
    check_deadlines_with_tracker,
    send_deadline_alerts_from_tracker,
)
from app.core.notifications import Severity
from app.models.riverside import RequirementStatus, RiversideRequirement


class TestAlertLevel:
    """Tests for AlertLevel enum."""

    def test_alert_level_values(self):
        """Test alert level enum values."""
        assert AlertLevel.INFO == "info"
        assert AlertLevel.WARNING == "warning"
        assert AlertLevel.HIGH == "high"
        assert AlertLevel.CRITICAL == "critical"


class TestAlertSchedule:
    """Tests for alert schedule constants."""

    def test_alert_schedule_mapping(self):
        """Test that alert schedule maps days to correct levels."""
        assert ALERT_SCHEDULE[90] == AlertLevel.INFO
        assert ALERT_SCHEDULE[60] == AlertLevel.WARNING
        assert ALERT_SCHEDULE[30] == AlertLevel.HIGH
        assert ALERT_SCHEDULE[14] == AlertLevel.CRITICAL
        assert ALERT_SCHEDULE[7] == AlertLevel.CRITICAL
        assert ALERT_SCHEDULE[1] == AlertLevel.CRITICAL

    def test_alert_to_severity_mapping(self):
        """Test alert level to notification severity mapping."""
        assert ALERT_TO_SEVERITY[AlertLevel.INFO] == Severity.INFO
        assert ALERT_TO_SEVERITY[AlertLevel.WARNING] == Severity.WARNING
        assert ALERT_TO_SEVERITY[AlertLevel.HIGH] == Severity.ERROR
        assert ALERT_TO_SEVERITY[AlertLevel.CRITICAL] == Severity.CRITICAL


class TestDeadlineAlert:
    """Tests for DeadlineAlert dataclass."""

    def test_creation(self):
        """Test creating DeadlineAlert."""
        alert = DeadlineAlert(
            requirement_id="RC-001",
            tenant_id="htt-tenant",
            title="Test Requirement",
            days_until_deadline=30,
            alert_level=AlertLevel.HIGH,
            is_overdue=False,
            alert_stage=30,
            status=RequirementStatus.IN_PROGRESS,
        )
        assert alert.requirement_id == "RC-001"
        assert alert.tenant_id == "htt-tenant"
        assert alert.days_until_deadline == 30
        assert alert.alert_level == AlertLevel.HIGH

    def test_overdue_alert(self):
        """Test creating overdue alert."""
        alert = DeadlineAlert(
            requirement_id="RC-001",
            tenant_id="htt-tenant",
            title="Overdue Requirement",
            days_until_deadline=-5,
            alert_level=AlertLevel.CRITICAL,
            is_overdue=True,
            alert_stage=None,
            status=RequirementStatus.NOT_STARTED,
        )
        assert alert.is_overdue
        assert alert.days_until_deadline == -5
        assert alert.alert_level == AlertLevel.CRITICAL


class TestDeadlineTrackingResult:
    """Tests for DeadlineTrackingResult dataclass."""

    def test_creation(self):
        """Test creating DeadlineTrackingResult."""
        result = DeadlineTrackingResult()
        assert result.alerts == []
        assert result.info_count == 0
        assert result.warning_count == 0
        assert result.high_count == 0
        assert result.critical_count == 0
        assert result.overdue_count == 0
        assert isinstance(result.checked_at, datetime)

    def test_with_alerts(self):
        """Test creating result with alerts."""
        alerts = [
            DeadlineAlert(
                requirement_id="RC-001",
                tenant_id="htt",
                title="Test",
                days_until_deadline=90,
                alert_level=AlertLevel.INFO,
                is_overdue=False,
                alert_stage=90,
                status=RequirementStatus.NOT_STARTED,
            ),
            DeadlineAlert(
                requirement_id="RC-002",
                tenant_id="htt",
                title="Test 2",
                days_until_deadline=-3,
                alert_level=AlertLevel.CRITICAL,
                is_overdue=True,
                alert_stage=None,
                status=RequirementStatus.IN_PROGRESS,
            ),
        ]
        result = DeadlineTrackingResult(alerts=alerts, info_count=1, overdue_count=1, critical_count=1)
        assert len(result.alerts) == 2
        assert result.info_count == 1
        assert result.overdue_count == 1


class TestDeadlineTrackerInitialization:
    """Tests for DeadlineTracker initialization."""

    def test_default_initialization(self):
        """Test tracker with default deadline."""
        tracker = DeadlineTracker()
        assert tracker.target_deadline == DEFAULT_DEADLINE
        assert tracker.alert_schedule == ALERT_SCHEDULE

    def test_custom_deadline(self):
        """Test tracker with custom deadline."""
        custom_deadline = date(2026, 12, 31)
        tracker = DeadlineTracker(target_deadline=custom_deadline)
        assert tracker.target_deadline == custom_deadline

    def test_custom_alert_schedule(self):
        """Test tracker with custom alert schedule."""
        custom_schedule = {90: AlertLevel.WARNING, 30: AlertLevel.CRITICAL}
        tracker = DeadlineTracker(alert_schedule=custom_schedule)
        assert tracker.alert_schedule == custom_schedule


class TestDeadlineTrackerEvaluateRequirement:
    """Tests for _evaluate_requirement method."""

    def test_overdue_requirement(self):
        """Test evaluation of overdue requirement."""
        tracker = DeadlineTracker()
        req = MagicMock(spec=RiversideRequirement)
        req.requirement_id = "RC-001"
        req.tenant_id = "htt"
        req.title = "Test"
        req.due_date = date.today() - timedelta(days=5)
        req.status = RequirementStatus.IN_PROGRESS

        alert = tracker._evaluate_requirement(req, date.today())

        assert alert is not None
        assert alert.is_overdue
        assert alert.alert_level == AlertLevel.CRITICAL
        assert alert.days_until_deadline == -5

    def test_info_level_alert(self):
        """Test evaluation at 90 days (INFO level)."""
        tracker = DeadlineTracker()
        req = MagicMock(spec=RiversideRequirement)
        req.requirement_id = "RC-001"
        req.tenant_id = "htt"
        req.title = "Test"
        req.due_date = date.today() + timedelta(days=90)
        req.status = RequirementStatus.NOT_STARTED

        alert = tracker._evaluate_requirement(req, date.today())

        assert alert is not None
        assert alert.alert_level == AlertLevel.INFO
        assert alert.alert_stage == 90

    def test_warning_level_alert(self):
        """Test evaluation at 60 days (WARNING level)."""
        tracker = DeadlineTracker()
        req = MagicMock(spec=RiversideRequirement)
        req.requirement_id = "RC-001"
        req.tenant_id = "htt"
        req.title = "Test"
        req.due_date = date.today() + timedelta(days=60)
        req.status = RequirementStatus.IN_PROGRESS

        alert = tracker._evaluate_requirement(req, date.today())

        assert alert is not None
        assert alert.alert_level == AlertLevel.WARNING
        assert alert.alert_stage == 60

    def test_high_level_alert(self):
        """Test evaluation at 30 days (HIGH level)."""
        tracker = DeadlineTracker()
        req = MagicMock(spec=RiversideRequirement)
        req.requirement_id = "RC-001"
        req.tenant_id = "htt"
        req.title = "Test"
        req.due_date = date.today() + timedelta(days=30)
        req.status = RequirementStatus.IN_PROGRESS

        alert = tracker._evaluate_requirement(req, date.today())

        assert alert is not None
        assert alert.alert_level == AlertLevel.HIGH
        assert alert.alert_stage == 30

    def test_critical_level_alert(self):
        """Test evaluation at 7 days (CRITICAL level)."""
        tracker = DeadlineTracker()
        req = MagicMock(spec=RiversideRequirement)
        req.requirement_id = "RC-001"
        req.tenant_id = "htt"
        req.title = "Test"
        req.due_date = date.today() + timedelta(days=7)
        req.status = RequirementStatus.IN_PROGRESS

        alert = tracker._evaluate_requirement(req, date.today())

        assert alert is not None
        assert alert.alert_level == AlertLevel.CRITICAL
        assert alert.alert_stage == 7

    def test_no_alert_non_threshold_day(self):
        """Test that no alert is generated on non-threshold days."""
        tracker = DeadlineTracker()
        req = MagicMock(spec=RiversideRequirement)
        req.requirement_id = "RC-001"
        req.tenant_id = "htt"
        req.title = "Test"
        req.due_date = date.today() + timedelta(days=25)  # Not in ALERT_SCHEDULE
        req.status = RequirementStatus.IN_PROGRESS

        alert = tracker._evaluate_requirement(req, date.today())

        assert alert is None

    def test_no_alert_no_due_date(self):
        """Test that requirements without due dates are skipped."""
        tracker = DeadlineTracker()
        req = MagicMock(spec=RiversideRequirement)
        req.requirement_id = "RC-001"
        req.tenant_id = "htt"
        req.title = "Test"
        req.due_date = None
        req.status = RequirementStatus.IN_PROGRESS

        alert = tracker._evaluate_requirement(req, date.today())

        assert alert is None


class TestDeadlineTrackerUpdateCounts:
    """Tests for _update_counts method."""

    def test_update_info_count(self):
        """Test updating INFO count."""
        tracker = DeadlineTracker()
        result = DeadlineTrackingResult()
        alert = DeadlineAlert(
            requirement_id="RC-001",
            tenant_id="htt",
            title="Test",
            days_until_deadline=90,
            alert_level=AlertLevel.INFO,
            is_overdue=False,
            alert_stage=90,
            status=RequirementStatus.NOT_STARTED,
        )
        tracker._update_counts(result, alert)
        assert result.info_count == 1

    def test_update_warning_count(self):
        """Test updating WARNING count."""
        tracker = DeadlineTracker()
        result = DeadlineTrackingResult()
        alert = DeadlineAlert(
            requirement_id="RC-001",
            tenant_id="htt",
            title="Test",
            days_until_deadline=60,
            alert_level=AlertLevel.WARNING,
            is_overdue=False,
            alert_stage=60,
            status=RequirementStatus.NOT_STARTED,
        )
        tracker._update_counts(result, alert)
        assert result.warning_count == 1

    def test_update_overdue_count(self):
        """Test updating overdue count."""
        tracker = DeadlineTracker()
        result = DeadlineTrackingResult()
        alert = DeadlineAlert(
            requirement_id="RC-001",
            tenant_id="htt",
            title="Test",
            days_until_deadline=-5,
            alert_level=AlertLevel.CRITICAL,
            is_overdue=True,
            alert_stage=None,
            status=RequirementStatus.IN_PROGRESS,
        )
        tracker._update_counts(result, alert)
        assert result.overdue_count == 1
        assert result.critical_count == 1


class TestDeadlineTrackerCalculateWarnings:
    """Tests for calculate_deadline_warnings method."""

    def test_finds_warning_at_60_days(self):
        """Test finding warning alerts at 60 days."""
        tracker = DeadlineTracker()
        requirements = []
        
        for days in [90, 60, 30]:
            req = MagicMock(spec=RiversideRequirement)
            req.requirement_id = f"RC-{days}"
            req.tenant_id = "htt"
            req.title = f"Req {days}"
            req.due_date = date.today() + timedelta(days=days)
            req.status = RequirementStatus.IN_PROGRESS
            requirements.append(req)

        warnings = tracker.calculate_deadline_warnings(requirements)

        assert len(warnings) == 1
        assert warnings[0].days_until_deadline == 60
        assert warnings[0].alert_level == AlertLevel.WARNING

    def test_no_warnings_when_not_60_days(self):
        """Test no warnings when not at 60 day threshold."""
        tracker = DeadlineTracker()
        requirements = []
        
        for days in [90, 30, 14]:
            req = MagicMock(spec=RiversideRequirement)
            req.requirement_id = f"RC-{days}"
            req.tenant_id = "htt"
            req.title = f"Req {days}"
            req.due_date = date.today() + timedelta(days=days)
            req.status = RequirementStatus.IN_PROGRESS
            requirements.append(req)

        warnings = tracker.calculate_deadline_warnings(requirements)

        assert len(warnings) == 0


class TestDeadlineTrackerCalculateCriticalAlerts:
    """Tests for calculate_critical_alerts method."""

    def test_finds_critical_at_14_7_1_days(self):
        """Test finding critical alerts at 14, 7, and 1 days."""
        tracker = DeadlineTracker()
        requirements = []
        
        for days in [14, 7, 1, 30, 60]:
            req = MagicMock(spec=RiversideRequirement)
            req.requirement_id = f"RC-{days}"
            req.tenant_id = "htt"
            req.title = f"Req {days}"
            req.due_date = date.today() + timedelta(days=days)
            req.status = RequirementStatus.IN_PROGRESS
            requirements.append(req)

        critical = tracker.calculate_critical_alerts(requirements)

        assert len(critical) == 3
        days_found = [c.days_until_deadline for c in critical]
        assert 14 in days_found
        assert 7 in days_found
        assert 1 in days_found

    def test_finds_overdue_critical(self):
        """Test finding overdue critical alerts."""
        tracker = DeadlineTracker()
        req = MagicMock(spec=RiversideRequirement)
        req.requirement_id = "RC-001"
        req.tenant_id = "htt"
        req.title = "Overdue"
        req.due_date = date.today() - timedelta(days=5)
        req.status = RequirementStatus.IN_PROGRESS

        critical = tracker.calculate_critical_alerts([req])

        assert len(critical) == 1
        assert critical[0].is_overdue
        assert critical[0].alert_level == AlertLevel.CRITICAL


class TestDeadlineTrackerBuildAlertKey:
    """Tests for _build_alert_key method."""

    def test_overdue_alert_key(self):
        """Test key generation for overdue alerts."""
        tracker = DeadlineTracker()
        alert = DeadlineAlert(
            requirement_id="RC-001",
            tenant_id="htt",
            title="Test",
            days_until_deadline=-5,
            alert_level=AlertLevel.CRITICAL,
            is_overdue=True,
            alert_stage=None,
            status=RequirementStatus.IN_PROGRESS,
        )
        key = tracker._build_alert_key(alert)
        assert key == "deadline_overdue_RC-001_htt"

    def test_approaching_alert_key(self):
        """Test key generation for approaching alerts."""
        tracker = DeadlineTracker()
        alert = DeadlineAlert(
            requirement_id="RC-001",
            tenant_id="htt",
            title="Test",
            days_until_deadline=30,
            alert_level=AlertLevel.HIGH,
            is_overdue=False,
            alert_stage=30,
            status=RequirementStatus.NOT_STARTED,
        )
        key = tracker._build_alert_key(alert)
        assert key == "deadline_30d_RC-001_htt"


class TestDeadlineTrackerTrackDeadlines:
    """Tests for track_requirement_deadlines method."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock(spec=Session)

    @pytest.mark.asyncio
    async def test_no_requirements(self, mock_db):
        """Test when there are no requirements."""
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query

        tracker = DeadlineTracker()
        result = await tracker.track_requirement_deadlines(mock_db)

        assert result.info_count == 0
        assert result.warning_count == 0
        assert result.high_count == 0
        assert result.critical_count == 0
        assert result.overdue_count == 0
        assert len(result.alerts) == 0

    @pytest.mark.asyncio
    async def test_single_alert_at_each_level(self, mock_db):
        """Test generating alerts at each level."""
        requirements = []
        for days in [90, 60, 30, 14, 7, 1]:
            req = MagicMock(spec=RiversideRequirement)
            req.requirement_id = f"RC-{days}"
            req.tenant_id = "htt"
            req.title = f"Req {days}"
            req.due_date = date.today() + timedelta(days=days)
            req.status = RequirementStatus.IN_PROGRESS
            requirements.append(req)

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = requirements
        mock_db.query.return_value = mock_query

        tracker = DeadlineTracker()
        result = await tracker.track_requirement_deadlines(mock_db)

        assert result.info_count == 1  # 90 days
        assert result.warning_count == 1  # 60 days
        assert result.high_count == 1  # 30 days
        assert result.critical_count == 3  # 14, 7, 1 days
        assert len(result.alerts) == 6

    @pytest.mark.asyncio
    async def test_overdue_requirement(self, mock_db):
        """Test detecting overdue requirements."""
        req = MagicMock(spec=RiversideRequirement)
        req.requirement_id = "RC-001"
        req.tenant_id = "htt"
        req.title = "Overdue"
        req.due_date = date.today() - timedelta(days=3)
        req.status = RequirementStatus.IN_PROGRESS

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [req]
        mock_db.query.return_value = mock_query

        tracker = DeadlineTracker()
        result = await tracker.track_requirement_deadlines(mock_db)

        assert result.overdue_count == 1
        assert result.critical_count == 1
        assert len(result.alerts) == 1
        assert result.alerts[0].is_overdue

    @pytest.mark.asyncio
    async def test_completed_requirements_filtered(self, mock_db):
        """Test that completed requirements are not tracked."""
        req = MagicMock(spec=RiversideRequirement)
        req.requirement_id = "RC-001"
        req.tenant_id = "htt"
        req.title = "Completed"
        req.due_date = date.today() - timedelta(days=5)
        req.status = RequirementStatus.COMPLETED

        # Query should filter out completed requirements
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []  # Empty after filtering
        mock_db.query.return_value = mock_query

        tracker = DeadlineTracker()
        result = await tracker.track_requirement_deadlines(mock_db)

        assert len(result.alerts) == 0

    @pytest.mark.asyncio
    @patch("app.alerts.deadline_alerts.get_db_context")
    async def test_uses_db_context_when_no_session(self, mock_get_context):
        """Test that tracker creates its own session when none provided."""
        mock_db = MagicMock(spec=Session)
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_db)
        mock_context.__exit__ = MagicMock(return_value=False)
        mock_get_context.return_value = mock_context

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query

        tracker = DeadlineTracker()
        result = await tracker.track_requirement_deadlines()

        mock_get_context.assert_called_once()
        assert isinstance(result, DeadlineTrackingResult)


class TestDeadlineTrackerTriggerAlert:
    """Tests for trigger_deadline_alert method."""

    @pytest.mark.asyncio
    @patch("app.alerts.deadline_alerts.should_notify")
    @patch("app.alerts.deadline_alerts.send_notification")
    async def test_send_info_notification(self, mock_send, mock_should_notify):
        """Test sending INFO level notification."""
        mock_should_notify.return_value = True
        mock_send.return_value = {"success": True}

        tracker = DeadlineTracker()
        alert = DeadlineAlert(
            requirement_id="RC-001",
            tenant_id="htt",
            title="Test Requirement",
            days_until_deadline=90,
            alert_level=AlertLevel.INFO,
            is_overdue=False,
            alert_stage=90,
            status=RequirementStatus.NOT_STARTED,
        )

        result = await tracker.trigger_deadline_alert(alert)

        assert result["success"] is True
        mock_send.assert_called_once()
        
        # Verify notification was created with correct severity
        call_args = mock_send.call_args[0][0]
        assert call_args.severity == Severity.INFO

    @pytest.mark.asyncio
    @patch("app.alerts.deadline_alerts.should_notify")
    @patch("app.alerts.deadline_alerts.send_notification")
    async def test_send_critical_overdue_notification(self, mock_send, mock_should_notify):
        """Test sending CRITICAL overdue notification."""
        mock_should_notify.return_value = True
        mock_send.return_value = {"success": True}

        tracker = DeadlineTracker()
        alert = DeadlineAlert(
            requirement_id="RC-001",
            tenant_id="htt",
            title="Overdue Requirement",
            days_until_deadline=-5,
            alert_level=AlertLevel.CRITICAL,
            is_overdue=True,
            alert_stage=None,
            status=RequirementStatus.IN_PROGRESS,
        )

        result = await tracker.trigger_deadline_alert(alert)

        assert result["success"] is True
        mock_send.assert_called_once()
        
        # Verify notification was created with CRITICAL severity
        call_args = mock_send.call_args[0][0]
        assert call_args.severity == Severity.CRITICAL
        assert "OVERDUE" in call_args.message

    @pytest.mark.asyncio
    @patch("app.alerts.deadline_alerts.should_notify")
    async def test_skip_notification_in_cooldown(self, mock_should_notify):
        """Test that notifications are skipped when in cooldown."""
        mock_should_notify.return_value = False

        tracker = DeadlineTracker()
        alert = DeadlineAlert(
            requirement_id="RC-001",
            tenant_id="htt",
            title="Test",
            days_until_deadline=90,
            alert_level=AlertLevel.INFO,
            is_overdue=False,
            alert_stage=90,
            status=RequirementStatus.NOT_STARTED,
        )

        result = await tracker.trigger_deadline_alert(alert)

        assert result["success"] is False
        assert result["error"] == "In cooldown period"

    @pytest.mark.asyncio
    @patch("app.alerts.deadline_alerts.should_notify")
    @patch("app.alerts.deadline_alerts.send_notification")
    async def test_notification_failure_handling(self, mock_send, mock_should_notify):
        """Test handling of notification failures."""
        mock_should_notify.return_value = True
        mock_send.return_value = {"success": False, "error": "Network error"}

        tracker = DeadlineTracker()
        alert = DeadlineAlert(
            requirement_id="RC-001",
            tenant_id="htt",
            title="Test",
            days_until_deadline=90,
            alert_level=AlertLevel.INFO,
            is_overdue=False,
            alert_stage=90,
            status=RequirementStatus.NOT_STARTED,
        )

        result = await tracker.trigger_deadline_alert(alert)

        assert result["success"] is False
        assert result["error"] == "Network error"

    @pytest.mark.asyncio
    @patch("app.alerts.deadline_alerts.should_notify")
    @patch("app.alerts.deadline_alerts.send_notification")
    @patch("app.alerts.deadline_alerts.record_notification_sent")
    async def test_records_notification_sent(self, mock_record, mock_send, mock_should_notify):
        """Test that successful notifications are recorded."""
        mock_should_notify.return_value = True
        mock_send.return_value = {"success": True}

        tracker = DeadlineTracker()
        alert = DeadlineAlert(
            requirement_id="RC-001",
            tenant_id="htt",
            title="Test",
            days_until_deadline=90,
            alert_level=AlertLevel.INFO,
            is_overdue=False,
            alert_stage=90,
            status=RequirementStatus.NOT_STARTED,
        )

        await tracker.trigger_deadline_alert(alert)

        mock_record.assert_called_once()


class TestDeadlineTrackerSendNotifications:
    """Tests for send_deadline_notifications method."""

    @pytest.mark.asyncio
    @patch("app.alerts.deadline_alerts.should_notify")
    @patch("app.alerts.deadline_alerts.send_notification")
    async def test_send_multiple_notifications(self, mock_send, mock_should_notify):
        """Test sending notifications for multiple alerts."""
        mock_should_notify.return_value = True
        mock_send.return_value = {"success": True}

        tracker = DeadlineTracker()
        alerts = [
            DeadlineAlert(
                requirement_id="RC-001",
                tenant_id="htt",
                title="Test 1",
                days_until_deadline=90,
                alert_level=AlertLevel.INFO,
                is_overdue=False,
                alert_stage=90,
                status=RequirementStatus.NOT_STARTED,
            ),
            DeadlineAlert(
                requirement_id="RC-002",
                tenant_id="bcc",
                title="Test 2",
                days_until_deadline=30,
                alert_level=AlertLevel.HIGH,
                is_overdue=False,
                alert_stage=30,
                status=RequirementStatus.IN_PROGRESS,
            ),
        ]

        results = await tracker.send_deadline_notifications(alerts)

        assert len(results) == 2
        assert all(r["success"] for r in results)
        assert mock_send.call_count == 2


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    @pytest.mark.asyncio
    @patch("app.alerts.deadline_alerts.DeadlineTracker.track_requirement_deadlines")
    async def test_check_deadlines_with_tracker(self, mock_track):
        """Test check_deadlines_with_tracker convenience function."""
        expected_result = DeadlineTrackingResult(info_count=1)
        mock_track.return_value = expected_result

        result = await check_deadlines_with_tracker()

        assert result == expected_result
        mock_track.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.alerts.deadline_alerts.DeadlineTracker.send_deadline_notifications")
    async def test_send_deadline_alerts_from_tracker(self, mock_send):
        """Test send_deadline_alerts_from_tracker convenience function."""
        mock_send.return_value = [{"success": True}]

        alerts = [
            DeadlineAlert(
                requirement_id="RC-001",
                tenant_id="htt",
                title="Test",
                days_until_deadline=90,
                alert_level=AlertLevel.INFO,
                is_overdue=False,
                alert_stage=90,
                status=RequirementStatus.NOT_STARTED,
            ),
        ]

        results = await send_deadline_alerts_from_tracker(alerts)

        assert len(results) == 1
        mock_send.assert_called_once_with(alerts)


class TestSchedulerIntegration:
    """Tests for integration with riverside_scheduler."""

    @pytest.mark.asyncio
    @patch("app.alerts.deadline_alerts.DeadlineTracker.track_requirement_deadlines")
    @patch("app.alerts.deadline_alerts.DeadlineTracker.send_deadline_notifications")
    async def test_schedule_deadline_checks(self, mock_send, mock_track):
        """Test schedule_deadline_checks from riverside_scheduler."""
        from app.core.riverside_scheduler import schedule_deadline_checks
        
        mock_result = DeadlineTrackingResult(
            alerts=[
                DeadlineAlert(
                    requirement_id="RC-001",
                    tenant_id="htt",
                    title="Test",
                    days_until_deadline=90,
                    alert_level=AlertLevel.INFO,
                    is_overdue=False,
                    alert_stage=90,
                    status=RequirementStatus.NOT_STARTED,
                ),
            ],
            info_count=1,
        )
        mock_track.return_value = mock_result
        mock_send.return_value = [{"success": True}]

        result = await schedule_deadline_checks()

        assert result["success"] is True
        assert result["alerts_found"] == 1
        assert result["info_count"] == 1
        assert result["notifications_sent"] == 1
        assert "checked_at" in result

    @pytest.mark.asyncio
    @patch("app.alerts.deadline_alerts.DeadlineTracker.track_requirement_deadlines")
    async def test_schedule_deadline_checks_error_handling(self, mock_track):
        """Test error handling in schedule_deadline_checks."""
        from app.core.riverside_scheduler import schedule_deadline_checks
        
        mock_track.side_effect = Exception("Database error")

        result = await schedule_deadline_checks()

        assert result["success"] is False
        assert "error" in result
        assert result["alerts_found"] == 0

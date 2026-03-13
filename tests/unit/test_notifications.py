"""Tests for notification utilities."""

from unittest.mock import MagicMock, patch

from app.core.notifications import (
    Notification,
    NotificationChannel,
    Severity,
    create_dashboard_url,
    create_retry_url,
    format_sync_alert,
    get_severity_color,
    record_notification_sent,
    send_notification,
    severity_meets_threshold,
    should_notify,
)


class TestSeverity:
    """Tests for severity enum and utilities."""

    def test_severity_values(self):
        """Test severity enum has expected values."""
        assert Severity.INFO.value == "info"
        assert Severity.WARNING.value == "warning"
        assert Severity.ERROR.value == "error"
        assert Severity.CRITICAL.value == "critical"

    def test_severity_order(self):
        """Test severity meets threshold correctly."""
        assert severity_meets_threshold(Severity.INFO, Severity.INFO)
        assert severity_meets_threshold(Severity.WARNING, Severity.INFO)
        assert severity_meets_threshold(Severity.ERROR, Severity.WARNING)
        assert severity_meets_threshold(Severity.CRITICAL, Severity.ERROR)
        assert not severity_meets_threshold(Severity.WARNING, Severity.ERROR)

    def test_severity_color_mapping(self):
        """Test severity to color mapping."""
        assert get_severity_color(Severity.INFO) == "#0078D4"
        assert get_severity_color(Severity.WARNING) == "#FFB900"
        assert get_severity_color(Severity.ERROR) == "#D83B01"
        assert get_severity_color(Severity.CRITICAL) == "#A80000"


class TestNotificationDataclass:
    """Tests for Notification dataclass."""

    def test_notification_creation(self):
        """Test creating a notification with default values."""
        notification = Notification(
            title="Test Alert",
            message="This is a test message",
        )
        assert notification.title == "Test Alert"
        assert notification.message == "This is a test message"
        assert notification.severity == Severity.INFO
        assert notification.channel == NotificationChannel.TEAMS
        assert notification.metadata == {}

    def test_notification_with_all_fields(self):
        """Test creating a notification with all fields."""
        notification = Notification(
            title="Test Alert",
            message="This is a test message",
            severity=Severity.ERROR,
            channel=NotificationChannel.TEAMS,
            metadata={"key": "value"},
            alert_id=123,
            job_type="resources",
            tenant_id="tenant-123",
            error_message="Something went wrong",
            dashboard_url="http://localhost:8000/dashboard",
            retry_url="http://localhost:8000/api/sync",
        )
        assert notification.severity == Severity.ERROR
        assert notification.alert_id == 123
        assert notification.job_type == "resources"


class TestFormatSyncAlert:
    """Tests for Teams Adaptive Card formatting."""

    def test_format_sync_alert_basic(self):
        """Test basic card formatting."""
        notification = Notification(
            title="Sync Failed",
            message="The sync job failed",
            severity=Severity.ERROR,
            job_type="resources",
        )
        card = format_sync_alert(notification)

        assert card["type"] == "message"
        assert len(card["attachments"]) == 1
        content = card["attachments"][0]["content"]
        assert content["type"] == "AdaptiveCard"

    def test_format_sync_alert_with_actions(self):
        """Test card with action buttons."""
        notification = Notification(
            title="Sync Failed",
            message="The sync job failed",
            severity=Severity.ERROR,
            job_type="resources",
            dashboard_url="http://localhost/dashboard",
            retry_url="http://localhost/api/sync",
        )
        card = format_sync_alert(notification)
        content = card["attachments"][0]["content"]

        assert "actions" in content
        actions = content["actions"]
        assert len(actions) == 2
        assert actions[0]["title"] == "📊 View Dashboard"
        assert actions[1]["title"] == "🔄 Retry Sync"

    def test_format_sync_alert_with_error(self):
        """Test card includes error details."""
        notification = Notification(
            title="Sync Failed",
            message="The sync job failed",
            severity=Severity.ERROR,
            error_message="Connection timeout after 30s",
        )
        card = format_sync_alert(notification)
        content = card["attachments"][0]["content"]

        # Error details should be in the body
        body_items = content["body"]
        error_container = [item for item in body_items if item.get("type") == "Container"]
        assert len(error_container) > 0


class TestShouldNotify:
    """Tests for notification deduplication logic."""

    @patch("app.core.notifications.get_settings")
    def test_should_notify_disabled(self, mock_get_settings):
        """Test notification disabled returns False."""
        mock_settings = MagicMock()
        mock_settings.notification_enabled = False
        mock_get_settings.return_value = mock_settings

        assert should_notify("test_alert") is False

    @patch("app.core.notifications.get_settings")
    def test_should_notify_first_time(self, mock_get_settings):
        """Test first notification is allowed."""
        mock_settings = MagicMock()
        mock_settings.notification_enabled = True
        mock_settings.notification_cooldown_minutes = 30
        mock_get_settings.return_value = mock_settings

        # Clear any existing history
        from app.core.notifications import _notification_history

        _notification_history.clear()

        assert should_notify("test_alert") is True

    @patch("app.core.notifications.get_settings")
    def test_should_notify_in_cooldown(self, mock_get_settings):
        """Test notification in cooldown is blocked."""
        mock_settings = MagicMock()
        mock_settings.notification_enabled = True
        mock_settings.notification_cooldown_minutes = 30
        mock_get_settings.return_value = mock_settings

        # Clear and set history
        from app.core.notifications import _notification_history

        _notification_history.clear()
        record_notification_sent("test_alert")

        assert should_notify("test_alert") is False


class TestUrlHelpers:
    """Tests for URL helper functions."""

    @patch("app.core.notifications.get_settings")
    def test_create_dashboard_url(self, mock_get_settings):
        """Test dashboard URL generation."""
        mock_settings = MagicMock()
        mock_settings.host = "localhost"
        mock_settings.port = 8000
        mock_get_settings.return_value = mock_settings

        url = create_dashboard_url("resources")
        assert "localhost:8000" in url
        assert "type=resources" in url

        url = create_dashboard_url()
        assert "/sync-dashboard" in url
        assert "?" not in url

    @patch("app.core.notifications.get_settings")
    def test_create_retry_url(self, mock_get_settings):
        """Test retry URL generation."""
        mock_settings = MagicMock()
        mock_settings.host = "localhost"
        mock_settings.port = 8000
        mock_get_settings.return_value = mock_settings

        url = create_retry_url("resources", "tenant-123")
        assert "api/sync/resources" in url
        assert "tenant_id=tenant-123" in url

        url = create_retry_url("costs")
        assert "api/sync/costs" in url


class TestSendNotification:
    """Tests for send_notification dispatcher."""

    @patch("app.core.notifications.get_settings")
    async def test_send_notification_disabled(self, mock_get_settings):
        """Test notification disabled."""
        mock_settings = MagicMock()
        mock_settings.notification_enabled = False
        mock_get_settings.return_value = mock_settings

        notification = Notification(title="Test", message="Test")
        result = await send_notification(notification)

        assert result["success"] is False
        assert "disabled" in result["error"]

    @patch("app.core.notifications.get_settings")
    async def test_send_notification_below_threshold(self, mock_get_settings):
        """Test notification below severity threshold."""
        mock_settings = MagicMock()
        mock_settings.notification_enabled = True
        mock_settings.notification_min_severity = "error"
        mock_get_settings.return_value = mock_settings

        notification = Notification(
            title="Test",
            message="Test",
            severity=Severity.INFO,
        )
        result = await send_notification(notification)

        assert result["success"] is False
        assert "below threshold" in result["error"]

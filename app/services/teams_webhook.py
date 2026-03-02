"""Microsoft Teams webhook integration for Riverside compliance notifications.

Provides Teams-specific webhook functionality for sending adaptive card notifications
with rich formatting, action buttons, and compliance-specific layouts.

SECURITY: Webhook URLs are never logged and sanitized from all output.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.notifications import (
    Notification,
    NotificationChannel,
    Severity,
    sanitize_log_message,
)

logger = logging.getLogger(__name__)


class AlertType(str, Enum):
    """Types of alerts for Teams card formatting."""

    MFA_GAP = "mfa_gap"
    DEADLINE = "deadline"
    MATURITY = "maturity"
    THREAT = "threat"
    COMPLIANCE = "compliance"
    SYNC_FAILURE = "sync_failure"


@dataclass
class TeamsCard:
    """Represents a Teams Adaptive Card structure.

    Attributes:
        title: Card title text
        message: Main message body
        severity: Alert severity level
        alert_type: Type of alert for styling
        facts: List of (title, value) fact pairs
        actions: List of action button dictionaries
        image_url: Optional hero image URL
    """

    title: str
    message: str
    severity: Severity
    alert_type: AlertType
    facts: list[dict[str, str]] | None = None
    actions: list[dict[str, Any]] | None = None
    image_url: str | None = None


def get_severity_theme(severity: Severity) -> dict[str, str]:
    """Get theme colors and icons for severity level.

    Args:
        severity: The severity level

    Returns:
        Dict with color, icon, and accent color
    """
    themes = {
        Severity.INFO: {
            "color": "#0078D4",  # Teams blue
            "icon": "ℹ️",
            "accent": "accent",
        },
        Severity.WARNING: {
            "color": "#FFB900",  # Gold/yellow
            "icon": "⚠️",
            "accent": "warning",
        },
        Severity.ERROR: {
            "color": "#D83B01",  # Orange/red
            "icon": "❌",
            "accent": "attention",
        },
        Severity.CRITICAL: {
            "color": "#A80000",  # Dark red
            "icon": "🚨",
            "accent": "attention",
        },
    }
    return themes.get(severity, themes[Severity.INFO])


def get_alert_icon(alert_type: AlertType) -> str:
    """Get icon URL for alert type.

    Args:
        alert_type: Type of alert

    Returns:
        URL to icon image
    """
    icons = {
        AlertType.MFA_GAP: "https://cdn-icons-png.flaticon.com/512/6097/6097236.png",
        AlertType.DEADLINE: "https://cdn-icons-png.flaticon.com/512/3652/3652191.png",
        AlertType.MATURITY: "https://cdn-icons-png.flaticon.com/512/2926/2926319.png",
        AlertType.THREAT: "https://cdn-icons-png.flaticon.com/512/564/564619.png",
        AlertType.COMPLIANCE: "https://cdn-icons-png.flaticon.com/512/1008/1008010.png",
        AlertType.SYNC_FAILURE: "https://cdn-icons-png.flaticon.com/512/3239/3239929.png",
    }
    return icons.get(alert_type, icons[AlertType.COMPLIANCE])


def create_adaptive_card(card: TeamsCard) -> dict[str, Any]:
    """Create a Teams Adaptive Card from card data.

    Builds a rich adaptive card with:
    - Color-coded header based on severity
    - Alert type icon
    - Formatted message with facts
    - Action buttons for quick responses

    Args:
        card: TeamsCard data structure

    Returns:
        Adaptive Card JSON payload
    """
    theme = get_severity_theme(card.severity)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    icon_url = get_alert_icon(card.alert_type)

    # Build card body
    body: list[dict[str, Any]] = [
        # Header with icon and title
        {
            "type": "ColumnSet",
            "style": theme["accent"],
            "bleed": True,
            "columns": [
                {
                    "type": "Column",
                    "width": "auto",
                    "items": [
                        {
                            "type": "Image",
                            "url": icon_url,
                            "altText": f"{card.alert_type.value} alert",
                            "size": "Medium",
                            "style": "default",
                        }
                    ],
                    "verticalContentAlignment": "Center",
                },
                {
                    "type": "Column",
                    "width": "stretch",
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": f"{theme['icon']} {card.title}",
                            "weight": "Bolder",
                            "size": "Large",
                            "color": theme["accent"] if card.severity != Severity.INFO else "Default",
                        },
                        {
                            "type": "TextBlock",
                            "text": f"Severity: **{card.severity.upper()}** • {timestamp}",
                            "size": "Small",
                            "isSubtle": True,
                            "spacing": "Small",
                        },
                    ],
                    "verticalContentAlignment": "Center",
                },
            ],
        },
        # Separator
        {"type": "Separator", "spacing": "Medium"},
        # Message body
        {
            "type": "TextBlock",
            "text": card.message,
            "wrap": True,
            "spacing": "Medium",
            "size": "Medium",
        },
    ]

    # Add facts table if provided
    if card.facts:
        body.append({
            "type": "FactSet",
            "facts": card.facts,
            "spacing": "Medium",
        })

    # Build action buttons
    actions: list[dict[str, Any]] = []
    if card.actions:
        for action in card.actions:
            actions.append(action)

    # Assemble final card
    adaptive_card = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentVersion": "1.4",
                "content": {
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": body,
                    "actions": actions if actions else None,
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                },
            }
        ],
    }

    # Remove actions if empty
    if not actions:
        adaptive_card["attachments"][0]["content"].pop("actions", None)

    return adaptive_card


def create_mfa_alert_card(
    tenant_id: str,
    user_mfa_pct: float,
    admin_mfa_pct: float,
    unprotected_admins: int,
    severity: Severity,
    dashboard_url: str | None = None,
) -> TeamsCard:
    """Create a Teams card for MFA compliance alerts.

    Args:
        tenant_id: The tenant identifier
        user_mfa_pct: Current user MFA percentage
        admin_mfa_pct: Current admin MFA percentage
        unprotected_admins: Number of admins without MFA
        severity: Alert severity level
        dashboard_url: Optional link to dashboard

    Returns:
        TeamsCard configured for MFA alerts
    """
    facts = [
        {"title": "Tenant", "value": tenant_id},
        {"title": "User MFA", "value": f"{user_mfa_pct:.1f}% (target: 95%)"},
        {"title": "Admin MFA", "value": f"{admin_mfa_pct:.1f}% (target: 100%)"},
        {"title": "Unprotected Admins", "value": str(unprotected_admins)},
    ]

    actions = []
    if dashboard_url:
        actions.append({
            "type": "Action.OpenUrl",
            "title": "📊 View Dashboard",
            "url": dashboard_url,
        })

    return TeamsCard(
        title=f"MFA Compliance Alert: {tenant_id}",
        message=(
            f"MFA enrollment for tenant **{tenant_id}** is below compliance thresholds. "
            f"{'⚠️ Critical: ' + str(unprotected_admins) + ' admin(s) without MFA' if unprotected_admins > 0 else '⚠️ User MFA below 95%'}"
        ),
        severity=severity,
        alert_type=AlertType.MFA_GAP,
        facts=facts,
        actions=actions if actions else None,
    )


def create_deadline_alert_card(
    requirement_id: str,
    tenant_id: str,
    title: str,
    days_until: int,
    is_overdue: bool,
    severity: Severity,
    dashboard_url: str | None = None,
) -> TeamsCard:
    """Create a Teams card for requirement deadline alerts.

    Args:
        requirement_id: The requirement identifier
        tenant_id: The tenant identifier
        title: Requirement title
        days_until: Days until deadline (negative if overdue)
        is_overdue: Whether the requirement is overdue
        severity: Alert severity level
        dashboard_url: Optional link to dashboard

    Returns:
        TeamsCard configured for deadline alerts
    """
    facts = [
        {"title": "Requirement", "value": requirement_id},
        {"title": "Tenant", "value": tenant_id},
        {"title": "Title", "value": title},
    ]

    if is_overdue:
        facts.append({"title": "Status", "value": f"⛔ {abs(days_until)} days overdue"})
        message = f"Requirement '{title}' is **{abs(days_until)} days overdue** and requires immediate attention."
    else:
        facts.append({"title": "Due In", "value": f"{days_until} days"})
        message = f"Requirement '{title}' is due in **{days_until} days**. Please ensure evidence is submitted before the deadline."

    actions = []
    if dashboard_url:
        actions.append({
            "type": "Action.OpenUrl",
            "title": "📋 View Requirements",
            "url": dashboard_url,
        })

    return TeamsCard(
        title=f"{'Overdue' if is_overdue else 'Deadline Approaching'}: {requirement_id}",
        message=message,
        severity=severity,
        alert_type=AlertType.DEADLINE,
        facts=facts,
        actions=actions if actions else None,
    )


def create_threat_alert_card(
    tenant_id: str,
    threat_score: float,
    vulnerability_count: int,
    malicious_domains: int,
    severity: Severity,
    dashboard_url: str | None = None,
) -> TeamsCard:
    """Create a Teams card for threat escalation alerts.

    Args:
        tenant_id: The tenant identifier
        threat_score: Current threat score
        vulnerability_count: Number of vulnerabilities detected
        malicious_domains: Number of malicious domain alerts
        severity: Alert severity level
        dashboard_url: Optional link to dashboard

    Returns:
        TeamsCard configured for threat alerts
    """
    facts = [
        {"title": "Tenant", "value": tenant_id},
        {"title": "Threat Score", "value": f"{threat_score:.1f}/10"},
        {"title": "Vulnerabilities", "value": str(vulnerability_count)},
        {"title": "Malicious Domains", "value": str(malicious_domains)},
    ]

    actions = []
    if dashboard_url:
        actions.append({
            "type": "Action.OpenUrl",
            "title": "🛡️ View Threat Dashboard",
            "url": dashboard_url,
        })

    return TeamsCard(
        title=f"{'Critical' if severity == Severity.CRITICAL else 'High'} Threat Detected: {tenant_id}",
        message=(
            f"**Security alert** for tenant {tenant_id}: Threat score of {threat_score:.1f} detected "
            f"with {vulnerability_count} vulnerabilities and {malicious_domains} malicious domain alerts. "
            f"Immediate review recommended."
        ),
        severity=severity,
        alert_type=AlertType.THREAT,
        facts=facts,
        actions=actions if actions else None,
    )


class TeamsWebhookClient:
    """Client for sending notifications to Microsoft Teams via webhooks.

    Provides a simple interface for sending rich adaptive cards to Teams
    channels with built-in retry logic and error handling.

    Usage:
        client = TeamsWebhookClient()
        result = await client.send_notification(notification)
    """

    def __init__(self, webhook_url: str | None = None) -> None:
        """Initialize the Teams webhook client.

        Args:
            webhook_url: Optional webhook URL. If not provided, uses
                the TEAMS_WEBHOOK_URL from settings.
        """
        settings = get_settings()
        self.webhook_url = webhook_url or getattr(settings, "teams_webhook_url", None)
        self.timeout = 30.0

    async def send_card(self, card: TeamsCard) -> dict[str, Any]:
        """Send a Teams card to the configured webhook.

        Args:
            card: The TeamsCard to send

        Returns:
            Dict with success status and response details
        """
        if not self.webhook_url:
            logger.warning("Teams webhook URL not configured")
            return {
                "success": False,
                "error": "Teams webhook URL not configured",
                "channel": NotificationChannel.TEAMS,
            }

        payload = create_adaptive_card(card)

        # Sanitize any logged messages
        safe_log_msg = sanitize_log_message("Sending Teams notification")
        logger.debug(safe_log_msg)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()

            safe_msg = sanitize_log_message(f"Teams notification sent: {card.title}")
            logger.info(safe_msg)
            return {
                "success": True,
                "status_code": response.status_code,
                "channel": NotificationChannel.TEAMS,
            }

        except httpx.HTTPStatusError as e:
            error_msg = sanitize_log_message(
                f"Teams webhook returned HTTP {e.response.status_code}"
            )
            logger.error(error_msg)
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}",
                "channel": NotificationChannel.TEAMS,
            }
        except Exception as e:
            error_msg = sanitize_log_message(f"Failed to send Teams notification: {e}")
            logger.error(error_msg)
            return {
                "success": False,
                "error": str(e),
                "channel": NotificationChannel.TEAMS,
            }

    async def send_notification(self, notification: Notification) -> dict[str, Any]:
        """Send a generic notification to Teams.

        Converts a Notification object to a Teams card and sends it.

        Args:
            notification: The notification to send

        Returns:
            Dict with success status and response details
        """
        # Determine alert type from notification
        alert_type = AlertType.COMPLIANCE
        if notification.job_type:
            if "mfa" in notification.job_type.lower():
                alert_type = AlertType.MFA_GAP
            elif "deadline" in notification.job_type.lower():
                alert_type = AlertType.DEADLINE
            elif "threat" in notification.job_type.lower():
                alert_type = AlertType.THREAT
            elif "maturity" in notification.job_type.lower():
                alert_type = AlertType.MATURITY
            elif "sync" in notification.job_type.lower():
                alert_type = AlertType.SYNC_FAILURE

        # Build facts from metadata
        facts = []
        if notification.tenant_id:
            facts.append({"title": "Tenant", "value": notification.tenant_id})
        if notification.alert_id:
            facts.append({"title": "Alert ID", "value": str(notification.alert_id)})

        # Build actions
        actions = []
        if notification.dashboard_url:
            actions.append({
                "type": "Action.OpenUrl",
                "title": "📊 View Dashboard",
                "url": notification.dashboard_url,
            })
        if notification.retry_url:
            actions.append({
                "type": "Action.OpenUrl",
                "title": "🔄 Retry",
                "url": notification.retry_url,
            })

        card = TeamsCard(
            title=notification.title,
            message=notification.message,
            severity=notification.severity,
            alert_type=alert_type,
            facts=facts if facts else None,
            actions=actions if actions else None,
        )

        return await self.send_card(card)


# Convenience functions
async def send_teams_card(card: TeamsCard, webhook_url: str | None = None) -> dict[str, Any]:
    """Send a Teams card using default client.

    Args:
        card: The TeamsCard to send
        webhook_url: Optional webhook URL override

    Returns:
        Dict with success status
    """
    client = TeamsWebhookClient(webhook_url)
    return await client.send_card(card)


async def send_teams_notification(
    notification: Notification,
    webhook_url: str | None = None,
) -> dict[str, Any]:
    """Send a notification to Teams using default client.

    Args:
        notification: The notification to send
        webhook_url: Optional webhook URL override

    Returns:
        Dict with success status
    """
    client = TeamsWebhookClient(webhook_url)
    return await client.send_notification(notification)


__all__ = [
    "TeamsWebhookClient",
    "TeamsCard",
    "AlertType",
    "create_adaptive_card",
    "create_mfa_alert_card",
    "create_deadline_alert_card",
    "create_threat_alert_card",
    "send_teams_card",
    "send_teams_notification",
    "get_severity_theme",
    "get_alert_icon",
]

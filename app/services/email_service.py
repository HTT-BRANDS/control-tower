"""Email notification service for Riverside compliance alerts.

Provides SMTP-based email notifications with HTML templates for
MFA compliance, deadline tracking, maturity regressions, and
threat escalations.

SECURITY: Email credentials are never logged. All sensitive data
is sanitized from log output.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import StrEnum
from typing import Any

import aiosmtplib

from app.core.config import get_settings
from app.core.notifications import Notification, NotificationChannel, Severity

logger = logging.getLogger(__name__)


class EmailTemplate(StrEnum):
    """Email template types."""

    MFA_ALERT = "mfa_alert"
    DEADLINE_ALERT = "deadline_alert"
    MATURITY_ALERT = "maturity_alert"
    THREAT_ALERT = "threat_alert"
    COMPLIANCE_REPORT = "compliance_report"
    GENERIC = "generic"


@dataclass
class EmailMessage:
    """Email message structure.

    Attributes:
        subject: Email subject line
        body_text: Plain text body
        body_html: HTML body content
        to_addresses: List of recipient addresses
        from_address: Sender address
        template: Template type used
    """

    subject: str
    body_text: str
    body_html: str
    to_addresses: list[str]
    from_address: str
    template: EmailTemplate


# HTML email template with styling
EMAIL_TEMPLATE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{subject}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background-color: #ffffff;
            border-radius: 8px;
            padding: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .header {{
            border-bottom: 3px solid {accent_color};
            padding-bottom: 15px;
            margin-bottom: 25px;
        }}
        .severity {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            background-color: {accent_color};
            color: white;
            margin-bottom: 10px;
        }}
        h1 {{
            color: #1a1a1a;
            font-size: 22px;
            margin: 10px 0;
        }}
        .timestamp {{
            color: #666;
            font-size: 13px;
            margin-top: 5px;
        }}
        .content {{
            margin: 25px 0;
            font-size: 15px;
            line-height: 1.7;
        }}
        .facts {{
            background-color: #f8f9fa;
            border-left: 4px solid {accent_color};
            padding: 15px 20px;
            margin: 20px 0;
            border-radius: 0 4px 4px 0;
        }}
        .facts table {{
            width: 100%;
            border-collapse: collapse;
        }}
        .facts td {{
            padding: 8px 0;
            border-bottom: 1px solid #e0e0e0;
        }}
        .facts td:first-child {{
            font-weight: 600;
            width: 35%;
            color: #555;
        }}
        .facts tr:last-child td {{
            border-bottom: none;
        }}
        .actions {{
            margin-top: 25px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
        }}
        .button {{
            display: inline-block;
            padding: 12px 24px;
            background-color: #0078d4;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            font-weight: 500;
            margin-right: 10px;
            margin-bottom: 10px;
        }}
        .button:hover {{
            background-color: #005a9e;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
            font-size: 12px;
            color: #666;
            text-align: center;
        }}
        .icon {{
            font-size: 24px;
            margin-right: 8px;
            vertical-align: middle;
        }}
        .critical {{ background-color: #a80000; }}
        .error {{ background-color: #d83b01; }}
        .warning {{ background-color: #ffb900; color: #333; }}
        .info {{ background-color: #0078d4; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <span class="severity {severity_class}">{icon} {severity}</span>
            <h1>{title}</h1>
            <div class="timestamp">{timestamp}</div>
        </div>

        <div class="content">
            {message}
        </div>

        {facts_html}

        {actions_html}

        <div class="footer">
            <p>Riverside Compliance Platform • Azure Governance</p>
            <p>This is an automated alert from the compliance monitoring system.</p>
        </div>
    </div>
</body>
</html>
"""


def get_severity_colors(severity: Severity) -> dict[str, str]:
    """Get color scheme for severity level.

    Args:
        severity: The severity level

    Returns:
        Dict with color codes and classes
    """
    colors = {
        Severity.INFO: {"accent": "#0078D4", "class": "info", "icon": "ℹ️"},
        Severity.WARNING: {"accent": "#FFB900", "class": "warning", "icon": "⚠️"},
        Severity.ERROR: {"accent": "#D83B01", "class": "error", "icon": "❌"},
        Severity.CRITICAL: {"accent": "#A80000", "class": "critical", "icon": "🚨"},
    }
    return colors.get(severity, colors[Severity.INFO])


def sanitize_email_address(email: str) -> str:
    """Sanitize email address for logging.

    Masks the local part of the email for privacy.

    Args:
        email: Email address to sanitize

    Returns:
        Sanitized email address
    """
    if "@" not in email:
        return email
    local, domain = email.rsplit("@", 1)
    if len(local) > 2:
        return f"{local[0]}***@{domain}"
    return f"***@{domain}"


def create_facts_html(facts: list[dict[str, str]]) -> str:
    """Create HTML table for facts.

    Args:
        facts: List of fact dictionaries with 'title' and 'value' keys

    Returns:
        HTML string for facts section
    """
    if not facts:
        return ""

    rows = ""
    for fact in facts:
        rows += f"<tr><td>{fact['title']}</td><td>{fact['value']}</td></tr>\n"

    return f"""
        <div class="facts">
            <table>
                {rows}
            </table>
        </div>
    """


def create_actions_html(actions: list[dict[str, str]]) -> str:
    """Create HTML for action buttons.

    Args:
        actions: List of action dicts with 'url' and 'title' keys

    Returns:
        HTML string for actions section
    """
    if not actions:
        return ""

    buttons = ""
    for action in actions:
        buttons += f'<a href="{action["url"]}" class="button">{action["title"]}</a>\n'

    return f"""
        <div class="actions">
            {buttons}
        </div>
    """


def render_email_template(
    subject: str,
    message: str,
    severity: Severity,
    facts: list[dict[str, str]] | None = None,
    actions: list[dict[str, str]] | None = None,
) -> tuple[str, str]:
    """Render email template with given content.

    Args:
        subject: Email subject
        message: Message body
        severity: Severity level
        facts: Optional list of facts to display
        actions: Optional list of action buttons

    Returns:
        Tuple of (plain_text, html_content)
    """
    theme = get_severity_colors(severity)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # Build plain text version
    plain_text = f"""{subject}
Severity: {severity.upper()}
Time: {timestamp}

{message}

"""
    if facts:
        plain_text += "Details:\n"
        for fact in facts:
            plain_text += f"  {fact['title']}: {fact['value']}\n"

    if actions:
        plain_text += "\nActions:\n"
        for action in actions:
            plain_text += f"  - {action['title']}: {action['url']}\n"

    plain_text += "\n---\nRiverside Compliance Platform • Azure Governance"

    # Build HTML version
    facts_html = create_facts_html(facts or [])
    actions_html = create_actions_html(actions or [])

    html = EMAIL_TEMPLATE_HTML.format(
        subject=subject,
        title=subject,
        severity=severity.upper(),
        severity_class=theme["class"],
        icon=theme["icon"],
        accent_color=theme["accent"],
        message=message.replace("\n", "<br>"),
        timestamp=timestamp,
        facts_html=facts_html,
        actions_html=actions_html,
    )

    return plain_text, html


class EmailService:
    """Email notification service using SMTP.

    Provides async email sending with HTML templates for compliance alerts.

    Usage:
        service = EmailService()
        result = await service.send_notification(notification, ["admin@example.com"])
    """

    def __init__(
        self,
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        smtp_user: str | None = None,
        smtp_password: str | None = None,
        from_address: str | None = None,
        use_tls: bool | None = None,
    ) -> None:
        """Initialize the email service.

        Args:
            smtp_host: SMTP server host (defaults to settings.SMTP_HOST)
            smtp_port: SMTP server port (defaults to settings.SMTP_PORT)
            smtp_user: SMTP username (defaults to settings.SMTP_USER)
            smtp_password: SMTP password (defaults to settings.SMTP_PASSWORD)
            from_address: From email address (defaults to settings.FROM_EMAIL)
            use_tls: Whether to use TLS (defaults to settings.SMTP_USE_TLS)
        """
        settings = get_settings()

        self.smtp_host = smtp_host or getattr(settings, "smtp_host", "localhost")
        self.smtp_port = smtp_port or getattr(settings, "smtp_port", 587)
        self.smtp_user = smtp_user or getattr(settings, "smtp_user", None)
        self.smtp_password = smtp_password or getattr(settings, "smtp_password", None)
        self.from_address = from_address or getattr(
            settings, "from_email", "riverside-alerts@httbrands.com"
        )
        self.use_tls = use_tls if use_tls is not None else getattr(settings, "smtp_use_tls", True)
        self.timeout = 30.0

    async def send_email(
        self,
        to_addresses: list[str],
        subject: str,
        body_text: str,
        body_html: str,
    ) -> dict[str, Any]:
        """Send an email via SMTP.

        Args:
            to_addresses: List of recipient email addresses
            subject: Email subject
            body_text: Plain text body
            body_html: HTML body

        Returns:
            Dict with success status and response details
        """
        if not self.smtp_host:
            logger.warning("SMTP host not configured")
            return {
                "success": False,
                "error": "SMTP not configured",
                "channel": NotificationChannel.EMAIL,
            }

        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_address
        msg["To"] = ", ".join(to_addresses)

        # Attach parts
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        # Log sanitized recipients
        safe_recipients = [sanitize_email_address(e) for e in to_addresses]
        logger.info(f"Sending email to: {', '.join(safe_recipients)}")

        try:
            # Connect and send
            client = aiosmtplib.SMTP(
                hostname=self.smtp_host,
                port=self.smtp_port,
                timeout=self.timeout,
            )

            await client.connect()

            if self.use_tls:
                await client.starttls()

            if self.smtp_user and self.smtp_password:
                await client.login(self.smtp_user, self.smtp_password)

            await client.sendmail(
                self.from_address,
                to_addresses,
                msg.as_string(),
            )
            await client.quit()

            logger.info(f"Email sent successfully: {subject}")
            return {
                "success": True,
                "recipients": len(to_addresses),
                "channel": NotificationChannel.EMAIL,
            }

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return {
                "success": False,
                "error": str(e),
                "channel": NotificationChannel.EMAIL,
            }

    async def send_notification(
        self,
        notification: Notification,
        to_addresses: list[str],
    ) -> dict[str, Any]:
        """Send a notification as an email.

        Args:
            notification: The notification to send
            to_addresses: List of recipient email addresses

        Returns:
            Dict with success status
        """
        # Build facts from notification metadata
        facts = []
        if notification.tenant_id:
            facts.append({"title": "Tenant", "value": notification.tenant_id})
        if notification.job_type:
            facts.append({"title": "Alert Type", "value": notification.job_type})
        if notification.alert_id:
            facts.append({"title": "Alert ID", "value": str(notification.alert_id)})

        # Build actions
        actions = []
        if notification.dashboard_url:
            actions.append(
                {
                    "title": "View Dashboard",
                    "url": notification.dashboard_url,
                }
            )
        if notification.retry_url:
            actions.append(
                {
                    "title": "Retry Action",
                    "url": notification.retry_url,
                }
            )

        # Render template
        plain_text, html = render_email_template(
            subject=notification.title,
            message=notification.message,
            severity=notification.severity,
            facts=facts,
            actions=actions,
        )

        return await self.send_email(
            to_addresses=to_addresses,
            subject=f"[Riverside] {notification.title}",
            body_text=plain_text,
            body_html=html,
        )

    async def send_mfa_alert(
        self,
        to_addresses: list[str],
        tenant_id: str,
        user_mfa_pct: float,
        admin_mfa_pct: float,
        unprotected_admins: int,
        dashboard_url: str | None = None,
    ) -> dict[str, Any]:
        """Send MFA compliance alert email.

        Args:
            to_addresses: Recipient addresses
            tenant_id: Tenant identifier
            user_mfa_pct: User MFA percentage
            admin_mfa_pct: Admin MFA percentage
            unprotected_admins: Number of admins without MFA
            dashboard_url: Optional dashboard link

        Returns:
            Dict with success status
        """
        severity = Severity.ERROR if unprotected_admins > 0 else Severity.WARNING

        facts = [
            {"title": "Tenant", "value": tenant_id},
            {"title": "User MFA", "value": f"{user_mfa_pct:.1f}% (target: 95%)"},
            {"title": "Admin MFA", "value": f"{admin_mfa_pct:.1f}% (target: 100%)"},
            {"title": "Unprotected Admins", "value": str(unprotected_admins)},
        ]

        actions = []
        if dashboard_url:
            actions.append({"title": "View Dashboard", "url": dashboard_url})

        plain_text, html = render_email_template(
            subject=f"MFA Compliance Alert: {tenant_id}",
            message=(
                f"MFA enrollment for tenant {tenant_id} is below compliance thresholds. "
                f"{'Critical: ' + str(unprotected_admins) + ' admin(s) without MFA' if unprotected_admins > 0 else 'User MFA below 95%'}. "
                f"Please review and remediate immediately."
            ),
            severity=severity,
            facts=facts,
            actions=actions,
        )

        return await self.send_email(
            to_addresses=to_addresses,
            subject=f"[Riverside] MFA Compliance Alert: {tenant_id}",
            body_text=plain_text,
            body_html=html,
        )

    async def send_deadline_alert(
        self,
        to_addresses: list[str],
        requirement_id: str,
        tenant_id: str,
        title: str,
        days_until: int,
        is_overdue: bool,
        dashboard_url: str | None = None,
    ) -> dict[str, Any]:
        """Send deadline alert email.

        Args:
            to_addresses: Recipient addresses
            requirement_id: Requirement identifier
            tenant_id: Tenant identifier
            title: Requirement title
            days_until: Days until deadline
            is_overdue: Whether overdue
            dashboard_url: Optional dashboard link

        Returns:
            Dict with success status
        """
        if is_overdue:
            severity = Severity.ERROR
            message = f"Requirement '{title}' is {abs(days_until)} days overdue and requires immediate attention."
        elif days_until <= 3:
            severity = Severity.ERROR
            message = (
                f"Requirement '{title}' is due in {days_until} days. Immediate action required."
            )
        elif days_until <= 7:
            severity = Severity.WARNING
            message = (
                f"Requirement '{title}' is due in {days_until} days. Please submit evidence soon."
            )
        else:
            severity = Severity.WARNING
            message = f"Requirement '{title}' is due in {days_until} days. Please plan accordingly."

        facts = [
            {"title": "Requirement", "value": requirement_id},
            {"title": "Tenant", "value": tenant_id},
            {"title": "Title", "value": title},
            {
                "title": "Status",
                "value": f"{abs(days_until)} days overdue"
                if is_overdue
                else f"{days_until} days remaining",
            },
        ]

        actions = []
        if dashboard_url:
            actions.append({"title": "View Requirements", "url": dashboard_url})

        plain_text, html = render_email_template(
            subject=f"{'Overdue' if is_overdue else 'Deadline'}: {requirement_id}",
            message=message,
            severity=severity,
            facts=facts,
            actions=actions,
        )

        return await self.send_email(
            to_addresses=to_addresses,
            subject=f"[Riverside] {'OVERDUE' if is_overdue else 'Deadline'}: {requirement_id}",
            body_text=plain_text,
            body_html=html,
        )


# Convenience functions
async def send_email_notification(
    notification: Notification,
    to_addresses: list[str],
    **kwargs: Any,
) -> dict[str, Any]:
    """Send notification via email using default service.

    Args:
        notification: Notification to send
        to_addresses: Recipient addresses
        **kwargs: Additional EmailService kwargs

    Returns:
        Dict with success status
    """
    service = EmailService(**kwargs)
    return await service.send_notification(notification, to_addresses)


__all__ = [
    "EmailService",
    "EmailMessage",
    "EmailTemplate",
    "render_email_template",
    "send_email_notification",
    "sanitize_email_address",
    "create_facts_html",
    "create_actions_html",
    "get_severity_colors",
]

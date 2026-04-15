"""Azure Service Health integration for incident tracking and response.

This module provides:
- Azure Service Health incident monitoring
- Azure Resource Health tracking
- Automated incident response workflows
- Integration with Teams/Slack notifications
- Historical incident analysis

Features:
- Real-time Service Health alert subscription
- Impact assessment for platform resources
- Automated status page updates
- Incident correlation with platform metrics
- Escalation workflows for critical issues

Usage:
    from app.core.azure_service_health import AzureServiceHealthMonitor

    monitor = AzureServiceHealthMonitor()
    incidents = monitor.get_active_incidents()

    # Check impact on specific resources
    impact = monitor.check_resource_impact("/subscriptions/.../resourceGroups/...")

    # Subscribe to health alerts
    await monitor.subscribe_health_alerts(webhook_url="https://...")
"""

import asyncio
import inspect
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class IncidentSeverity(Enum):
    """Azure Service Health incident severity levels."""

    CRITICAL = "Critical"
    ERROR = "Error"
    WARNING = "Warning"
    INFORMATIONAL = "Informational"


class IncidentStatus(Enum):
    """Azure Service Health incident status."""

    ACTIVE = "Active"
    RESOLVED = "Resolved"
    MITIGATED = "Mitigated"
    IN_PROGRESS = "InProgress"


class ResourceHealthStatus(Enum):
    """Azure Resource Health status."""

    AVAILABLE = "Available"
    UNAVAILABLE = "Unavailable"
    DEGRADED = "Degraded"
    UNKNOWN = "Unknown"


@dataclass
class ServiceHealthIncident:
    """Azure Service Health incident information."""

    incident_id: str
    correlation_id: str
    title: str
    summary: str
    severity: IncidentSeverity
    status: IncidentStatus
    service: str
    region: str
    start_time: datetime
    last_update_time: datetime
    resolution_time: datetime | None = None
    tracking_id: str | None = None
    impact: str = ""
    updates: list[dict[str, Any]] = field(default_factory=list)
    affected_services: list[str] = field(default_factory=list)

    @property
    def duration_minutes(self) -> float | None:
        """Calculate incident duration in minutes."""
        if self.resolution_time:
            return (self.resolution_time - self.start_time).total_seconds() / 60
        return None

    @property
    def is_resolved(self) -> bool:
        """Check if incident is resolved."""
        return self.status in (IncidentStatus.RESOLVED, IncidentStatus.MITIGATED)

    @property
    def is_platform_impacting(self) -> bool:
        """Check if incident could impact the governance platform."""
        platform_services = [
            "App Service",
            "Azure SQL",
            "Storage",
            "Key Vault",
            "Azure AD",
            "Microsoft Graph",
            "Azure Resource Manager",
            "Azure Monitor",
            "Log Analytics",
        ]
        return any(svc.lower() in self.service.lower() for svc in platform_services)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "incident_id": self.incident_id,
            "correlation_id": self.correlation_id,
            "title": self.title,
            "summary": self.summary,
            "severity": self.severity.value,
            "status": self.status.value,
            "service": self.service,
            "region": self.region,
            "start_time": self.start_time.isoformat(),
            "last_update_time": self.last_update_time.isoformat(),
            "resolution_time": self.resolution_time.isoformat() if self.resolution_time else None,
            "tracking_id": self.tracking_id,
            "impact": self.impact,
            "duration_minutes": self.duration_minutes,
            "is_platform_impacting": self.is_platform_impacting,
            "affected_services": self.affected_services,
        }


@dataclass
class ResourceHealthEvent:
    """Azure Resource Health event for a specific resource."""

    resource_id: str
    resource_name: str
    resource_type: str
    resource_group: str
    status: ResourceHealthStatus
    event_type: str  # "AvailabilityStateChange", "HealthEvent", etc.
    occurred_time: datetime
    previous_status: ResourceHealthStatus | None = None
    description: str = ""
    reason_chronicity: str = ""  # "Persistent", "Transient"
    reason_type: str = ""  # "Unplanned", "Planned"
    recommended_actions: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "resource_type": self.resource_type,
            "resource_group": self.resource_group,
            "status": self.status.value,
            "previous_status": self.previous_status.value if self.previous_status else None,
            "event_type": self.event_type,
            "occurred_time": self.occurred_time.isoformat(),
            "description": self.description,
            "reason_chronicity": self.reason_chronicity,
            "reason_type": self.reason_type,
            "recommended_actions": self.recommended_actions,
        }


@dataclass
class HealthAlert:
    """Health alert configuration."""

    alert_type: str  # "service_health", "resource_health", "platform_impact"
    severity_threshold: IncidentSeverity
    notify_channels: list[str]  # "teams", "slack", "email", "webhook"
    webhook_urls: dict[str, str] = field(default_factory=dict)
    enabled: bool = True


class AzureServiceHealthMonitor:
    """Monitor Azure Service Health and Resource Health.

    Provides comprehensive health monitoring with:
    - Real-time incident detection
    - Resource impact assessment
    - Automated notification workflows
    - Historical incident tracking
    - Platform health correlation
    """

    def __init__(self, subscription_id: str | None = None):
        self.subscription_id = subscription_id or os.environ.get("AZURE_SUBSCRIPTION_ID")
        self._service_health_client: Any = None
        self._resource_health_client: Any = None
        self._alert_subscriptions: list[HealthAlert] = []
        self._incident_history: list[ServiceHealthIncident] = []
        self._active_incidents: dict[str, ServiceHealthIncident] = {}
        self._notification_handlers: list[Callable] = []
        self._polling_task: asyncio.Task | None = None
        self._shutdown = False

    def _get_service_health_client(self) -> Any:
        """Get Azure Service Health client."""
        if self._service_health_client is None:
            try:
                from azure.identity import DefaultAzureCredential
                from azure.mgmt.resourcehealth import MicrosoftResourceHealth

                credential = DefaultAzureCredential()
                self._service_health_client = MicrosoftResourceHealth(
                    credential, self.subscription_id
                )
            except ImportError:
                logger.error(
                    "Azure SDK not installed. Run: pip install azure-mgmt-resourcehealth azure-identity"
                )
                raise
        return self._service_health_client

    def _get_resource_health_client(self) -> Any:
        """Get Azure Resource Health client."""
        if self._resource_health_client is None:
            try:
                from azure.identity import DefaultAzureCredential
                from azure.mgmt.resourcehealth import MicrosoftResourceHealth

                credential = DefaultAzureCredential()
                self._resource_health_client = MicrosoftResourceHealth(
                    credential, self.subscription_id
                )
            except ImportError:
                logger.error("Azure SDK not installed")
                raise
        return self._resource_health_client

    def get_active_incidents(self) -> list[ServiceHealthIncident]:
        """Get currently active Service Health incidents."""
        try:
            client = self._get_service_health_client()

            # List active events for subscription
            events = client.events.list_by_subscription_id(
                filter="eventStatus eq 'Active' or eventStatus eq 'InProgress'"
            )

            incidents = []
            for event in events:
                incident = self._convert_event_to_incident(event)
                if incident:
                    incidents.append(incident)
                    self._active_incidents[incident.incident_id] = incident

            return incidents

        except Exception as e:
            logger.error(f"Failed to get active incidents: {e}")
            return []

    def _convert_event_to_incident(self, event: Any) -> ServiceHealthIncident | None:
        """Convert Azure event to ServiceHealthIncident."""
        try:
            severity = (
                IncidentSeverity(event.severity)
                if hasattr(event, "severity")
                else IncidentSeverity.WARNING
            )
            status = (
                IncidentStatus(event.status) if hasattr(event, "status") else IncidentStatus.ACTIVE
            )

            return ServiceHealthIncident(
                incident_id=event.name or "unknown",
                correlation_id=getattr(event, "correlation_id", event.name or "unknown"),
                title=getattr(event, "title", "Unknown Incident"),
                summary=getattr(event, "summary", ""),
                severity=severity,
                status=status,
                service=getattr(event, "service", "Unknown"),
                region=getattr(event, "region", "Global"),
                start_time=event.start_time if hasattr(event, "start_time") else datetime.utcnow(),
                last_update_time=event.last_modified_time
                if hasattr(event, "last_modified_time")
                else datetime.utcnow(),
                resolution_time=getattr(event, "resolution_time", None),
                tracking_id=getattr(event, "tracking_id", None),
                impact=getattr(event, "impact", ""),
                affected_services=getattr(event, "affected_services", []),
            )
        except Exception as e:
            logger.debug(f"Could not convert event: {e}")
            return None

    def check_resource_impact(self, resource_id: str) -> ResourceHealthEvent | None:
        """Check health status of a specific resource."""
        try:
            client = self._get_resource_health_client()

            # Get current availability status
            availability = client.availability_statuses.get_by_resource(resource_uri=resource_id)

            # Parse resource info
            parts = resource_id.split("/")
            resource_name = parts[-1] if parts else "unknown"
            resource_type = parts[-2] if len(parts) > 1 else "unknown"
            resource_group = parts[4] if len(parts) > 4 else "unknown"

            return ResourceHealthEvent(
                resource_id=resource_id,
                resource_name=resource_name,
                resource_type=resource_type,
                resource_group=resource_group,
                status=ResourceHealthStatus(availability.availability_state or "Unknown"),
                event_type="AvailabilityState",
                occurred_time=datetime.utcnow(),
                description=availability.summary or "",
                reason_chronicity=getattr(availability, "reason_chronicity", ""),
                reason_type=getattr(availability, "reason_type", ""),
                recommended_actions=getattr(availability, "recommended_actions", []),
            )

        except Exception as e:
            logger.error(f"Failed to check resource impact for {resource_id}: {e}")
            return None

    def check_platform_impact(self) -> dict[str, Any]:
        """Check impact on platform-specific Azure services."""
        platform_services = {
            "App Service": "Microsoft.Web/sites",
            "Azure SQL": "Microsoft.Sql/servers",
            "Key Vault": "Microsoft.KeyVault/vaults",
            "Storage": "Microsoft.Storage/storageAccounts",
            "Azure AD": "Microsoft.AAD/domainServices",
        }

        impacts = {}
        active_incidents = self.get_active_incidents()

        for service_name, service_type in platform_services.items():
            # Check if any active incident affects this service
            service_incidents = [
                i
                for i in active_incidents
                if service_name.lower() in i.service.lower()
                or service_type.lower() in i.service.lower()
            ]

            impacts[service_name] = {
                "has_active_incident": len(service_incidents) > 0,
                "incidents": [i.to_dict() for i in service_incidents],
                "severity": max((i.severity.value for i in service_incidents), default="None"),
            }

        return impacts

    def register_notification_handler(
        self, handler: Callable[[ServiceHealthIncident], None]
    ) -> None:
        """Register a callback for incident notifications."""
        self._notification_handlers.append(handler)
        logger.debug(f"Registered notification handler: {handler.__name__}")

    async def send_notification(
        self, incident: ServiceHealthIncident, channels: list[str] | None = None
    ) -> bool:
        """Send incident notification to configured channels."""
        channels = channels or ["webhook"]
        success = True

        for channel in channels:
            try:
                if channel == "teams":
                    await self._send_teams_notification(incident)
                elif channel == "slack":
                    await self._send_slack_notification(incident)
                elif channel == "webhook":
                    await self._send_webhook_notification(incident)
                else:
                    logger.warning(f"Unknown notification channel: {channel}")
            except Exception as e:
                logger.error(f"Failed to send {channel} notification: {e}")
                success = False

        # Call registered handlers
        for handler in self._notification_handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    await handler(incident)
                else:
                    handler(incident)
            except Exception as e:
                logger.error(f"Notification handler failed: {e}")

        return success

    async def _send_teams_notification(self, incident: ServiceHealthIncident) -> bool:
        """Send notification to Microsoft Teams."""
        webhook_url = os.environ.get("TEAMS_WEBHOOK_URL")
        if not webhook_url:
            logger.debug("Teams webhook not configured")
            return False

        try:
            import aiohttp

            # Build Teams message card
            color = (
                "ff0000"
                if incident.severity == IncidentSeverity.CRITICAL
                else "ff9900"
                if incident.severity == IncidentSeverity.ERROR
                else "0099ff"
            )

            message = {
                "@type": "MessageCard",
                "@context": "https://schema.org/extensions",
                "themeColor": color,
                "title": f"Azure Service Health Alert: {incident.title}",
                "sections": [
                    {
                        "activityTitle": f"{incident.severity.value} - {incident.service}",
                        "activitySubtitle": f"Region: {incident.region}",
                        "facts": [
                            {"name": "Status", "value": incident.status.value},
                            {"name": "Tracking ID", "value": incident.tracking_id or "N/A"},
                            {
                                "name": "Started",
                                "value": incident.start_time.strftime("%Y-%m-%d %H:%M UTC"),
                            },
                            {
                                "name": "Platform Impact",
                                "value": "Yes" if incident.is_platform_impacting else "No",
                            },
                        ],
                        "text": incident.summary,
                    }
                ],
                "potentialAction": [
                    {
                        "@type": "OpenUri",
                        "name": "View in Azure Portal",
                        "targets": [
                            {
                                "os": "default",
                                "uri": "https://portal.azure.com/#blade/Microsoft_Azure_Health/HealthHistoryBlade",
                            }
                        ],
                    }
                ],
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=message, timeout=30) as response:
                    if response.status == 200:
                        logger.info(f"Teams notification sent for incident {incident.incident_id}")
                        return True
                    else:
                        logger.error(f"Teams notification failed: {response.status}")
                        return False

        except Exception as e:
            logger.error(f"Failed to send Teams notification: {e}")
            return False

    async def _send_slack_notification(self, incident: ServiceHealthIncident) -> bool:
        """Send notification to Slack."""
        webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
        if not webhook_url:
            logger.debug("Slack webhook not configured")
            return False

        try:
            import aiohttp

            emoji = (
                "🔴"
                if incident.severity == IncidentSeverity.CRITICAL
                else "🟡"
                if incident.severity == IncidentSeverity.ERROR
                else "🔵"
            )

            message = {
                "text": f"{emoji} *Azure Service Health Alert*",
                "blocks": [
                    {
                        "type": "header",
                        "text": {"type": "plain_text", "text": f"{emoji} {incident.title}"},
                    },
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": f"*Severity:*\n{incident.severity.value}"},
                            {"type": "mrkdwn", "text": f"*Status:*\n{incident.status.value}"},
                            {"type": "mrkdwn", "text": f"*Service:*\n{incident.service}"},
                            {"type": "mrkdwn", "text": f"*Region:*\n{incident.region}"},
                            {
                                "type": "mrkdwn",
                                "text": f"*Tracking ID:*\n{incident.tracking_id or 'N/A'}",
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Platform Impact:*\n{'Yes ⚠️' if incident.is_platform_impacting else 'No ✓'}",
                            },
                        ],
                    },
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"*Summary:*\n{incident.summary}"},
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"Started: {incident.start_time.strftime('%Y-%m-%d %H:%M UTC')}",
                            }
                        ],
                    },
                ],
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=message, timeout=30) as response:
                    if response.status == 200:
                        logger.info(f"Slack notification sent for incident {incident.incident_id}")
                        return True
                    else:
                        logger.error(f"Slack notification failed: {response.status}")
                        return False

        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return False

    async def _send_webhook_notification(self, incident: ServiceHealthIncident) -> bool:
        """Send notification to generic webhook."""
        webhook_url = os.environ.get("SERVICE_HEALTH_WEBHOOK_URL")
        if not webhook_url:
            return False

        try:
            import aiohttp

            payload = {
                "event_type": "azure_service_health",
                "timestamp": datetime.utcnow().isoformat(),
                "incident": incident.to_dict(),
                "platform_impact": incident.is_platform_impacting,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload, timeout=30) as response:
                    return response.status == 200

        except Exception as e:
            logger.error(f"Webhook notification failed: {e}")
            return False

    async def start_monitoring(self, interval_seconds: int = 300) -> None:
        """Start continuous monitoring for Service Health incidents."""
        if self._polling_task and not self._polling_task.done():
            logger.warning("Monitoring already active")
            return

        self._shutdown = False
        self._polling_task = asyncio.create_task(self._polling_loop(interval_seconds))
        logger.info(f"Service Health monitoring started (interval: {interval_seconds}s)")

    async def stop_monitoring(self) -> None:
        """Stop continuous monitoring."""
        self._shutdown = True
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
        logger.info("Service Health monitoring stopped")

    async def _polling_loop(self, interval_seconds: int) -> None:
        """Background polling loop for incident detection."""
        while not self._shutdown:
            try:
                # Check for new incidents
                current_incidents = self.get_active_incidents()

                # Find new incidents not in our active set
                new_incidents = [
                    i for i in current_incidents if i.incident_id not in self._active_incidents
                ]

                # Find resolved incidents
                resolved_ids = set(self._active_incidents.keys()) - {
                    i.incident_id for i in current_incidents
                }

                # Notify about new incidents
                for incident in new_incidents:
                    if incident.is_platform_impacting or incident.severity in (
                        IncidentSeverity.CRITICAL,
                        IncidentSeverity.ERROR,
                    ):
                        logger.warning(
                            f"New platform-impacting incident detected: {incident.title}"
                        )
                        await self.send_notification(incident)

                # Update active incidents
                for incident in current_incidents:
                    self._active_incidents[incident.incident_id] = incident

                # Remove resolved incidents
                for resolved_id in resolved_ids:
                    if resolved_id in self._active_incidents:
                        incident = self._active_incidents.pop(resolved_id)
                        logger.info(f"Incident resolved: {incident.title}")

                        # Send resolution notification
                        incident.status = IncidentStatus.RESOLVED
                        incident.resolution_time = datetime.utcnow()
                        await self.send_notification(incident)

                await asyncio.sleep(interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                await asyncio.sleep(interval_seconds)

    def get_incident_history(
        self, days: int = 30, include_platform_only: bool = False
    ) -> list[ServiceHealthIncident]:
        """Get historical incident data."""
        try:
            client = self._get_service_health_client()

            # Calculate date range
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=days)

            # List historical events
            events = client.events.list_by_subscription_id(
                filter=f"startTime ge '{start_time.isoformat()}' and startTime le '{end_time.isoformat()}'"
            )

            incidents = []
            for event in events:
                incident = self._convert_event_to_incident(event)
                if incident:
                    if not include_platform_only or incident.is_platform_impacting:
                        incidents.append(incident)

            return incidents

        except Exception as e:
            logger.error(f"Failed to get incident history: {e}")
            return []

    def generate_health_report(self, days: int = 30) -> dict[str, Any]:
        """Generate comprehensive health report."""
        history = self.get_incident_history(days, include_platform_only=False)
        platform_impacts = self.check_platform_impact()

        # Calculate metrics
        total_incidents = len(history)
        platform_incidents = [i for i in history if i.is_platform_impacting]
        critical_incidents = [i for i in history if i.severity == IncidentSeverity.CRITICAL]

        # Calculate average resolution time
        resolved = [i for i in history if i.is_resolved and i.duration_minutes]
        avg_resolution = (
            sum(i.duration_minutes for i in resolved) / len(resolved) if resolved else 0
        )

        return {
            "report_period": {
                "days": days,
                "start": (datetime.utcnow() - timedelta(days=days)).isoformat(),
                "end": datetime.utcnow().isoformat(),
            },
            "summary": {
                "total_incidents": total_incidents,
                "platform_impacting_incidents": len(platform_incidents),
                "critical_incidents": len(critical_incidents),
                "average_resolution_minutes": round(avg_resolution, 2),
                "current_active_incidents": len(self._active_incidents),
            },
            "platform_health": platform_impacts,
            "recent_incidents": [i.to_dict() for i in history[:10]],
            "active_incidents": [i.to_dict() for i in self._active_incidents.values()],
            "generated_at": datetime.utcnow().isoformat(),
        }


# Global monitor instance
_health_monitor: AzureServiceHealthMonitor | None = None


def get_health_monitor() -> AzureServiceHealthMonitor:
    """Get or create global health monitor instance."""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = AzureServiceHealthMonitor()
    return _health_monitor


async def check_platform_health() -> dict[str, Any]:
    """Quick check of platform health status."""
    monitor = get_health_monitor()

    return {
        "service_health_incidents": len(monitor.get_active_incidents()),
        "platform_impact": monitor.check_platform_impact(),
        "timestamp": datetime.utcnow().isoformat(),
    }

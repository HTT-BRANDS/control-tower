"""Azure Application Insights integration with custom telemetry.

Provides request telemetry middleware and optional OpenCensus integration
for Azure Application Insights. Includes custom telemetry for:
- Sync operations (duration, success/failure, records processed)
- Authentication events (login/logout, token refresh, failures)
- Performance metrics (API latency, database queries)
- Business metrics (compliance scores, cost changes)

Falls back to structured logging when the OpenCensus SDK is not installed.
"""

import logging
import time
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class TelemetryEventType(Enum):
    """Types of telemetry events tracked."""

    # Sync events
    SYNC_STARTED = "sync.started"
    SYNC_COMPLETED = "sync.completed"
    SYNC_FAILED = "sync.failed"

    # Auth events
    AUTH_LOGIN_SUCCESS = "auth.login.success"
    AUTH_LOGIN_FAILURE = "auth.login.failure"
    AUTH_LOGOUT = "auth.logout"
    AUTH_TOKEN_REFRESH = "auth.token.refresh"
    AUTH_TOKEN_EXPIRED = "auth.token.expired"

    # Performance events
    API_REQUEST = "api.request"
    DB_QUERY = "db.query"
    CACHE_OPERATION = "cache.operation"

    # Dependency tracking
    DEPENDENCY = "dependency"

    # Business events
    COMPLIANCE_VIOLATION = "compliance.violation"
    BUDGET_ALERT = "budget.alert"
    COST_ANOMALY = "cost.anomaly"


@dataclass
class TelemetryEvent:
    """Structured telemetry event data."""

    event_type: TelemetryEventType
    timestamp: float = field(default_factory=time.time)
    duration_ms: float | None = None
    success: bool | None = None
    tenant_id: str | None = None
    user_id: str | None = None
    operation_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    properties: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for logging/serialization."""
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "operation_id": self.operation_id,
            "properties": self.properties,
            "metrics": self.metrics,
        }


class AppInsightsTelemetryClient:
    """Client for sending custom telemetry to Application Insights.

    Supports both Azure Monitor (OpenCensus) and structured logging fallback.
    """

    def __init__(self):
        self.settings = get_settings()
        self.enabled = self.settings.app_insights_enabled
        self._exporter = None
        self._tracer = None

        if self.enabled:
            try:
                from opencensus.ext.azure.trace_exporter import AzureExporter
                from opencensus.trace.samplers import ProbabilitySampler
                from opencensus.trace.tracer import Tracer

                connection_string = self.settings.app_insights_connection_string
                if connection_string:
                    self._exporter = AzureExporter(connection_string=connection_string)
                    self._tracer = Tracer(
                        exporter=self._exporter,
                        sampler=ProbabilitySampler(1.0),
                    )
                    logger.info("App Insights telemetry client initialized")
                else:
                    logger.warning("App Insights enabled but connection string not set")
                    self.enabled = False
            except ImportError:
                logger.warning(
                    "OpenCensus not installed. Using structured logging fallback. "
                    "Install with: pip install opencensus-ext-azure"
                )
                self.enabled = False

    def track_event(self, event: TelemetryEvent) -> None:
        """Track a telemetry event."""
        event_dict = event.to_dict()

        if self.enabled and self._tracer:
            try:
                # Add event as custom property in trace
                with self._tracer.span(name=event.event_type.value) as span:
                    span.add_attribute("event_data", str(event_dict))
                    for key, value in event.properties.items():
                        span.add_attribute(f"prop.{key}", str(value))
                    for key, value in event.metrics.items():
                        span.add_attribute(f"metric.{key}", value)
            except Exception as e:
                logger.debug(f"Failed to send to App Insights: {e}")

        # Always log to structured logging
        log_data = {
            "telemetry_event": event.event_type.value,
            "operation_id": event.operation_id,
            "tenant_id": event.tenant_id,
            "user_id": event.user_id,
            "duration_ms": event.duration_ms,
            "success": event.success,
            **event.properties,
            **{f"metric_{k}": v for k, v in event.metrics.items()},
        }
        logger.info("telemetry_event", extra=log_data)

    def track_metric(
        self, name: str, value: float, properties: dict[str, str] | None = None
    ) -> None:
        """Track a custom metric."""
        if self.enabled and self._tracer:
            try:
                with self._tracer.span(name=f"metric.{name}") as span:
                    span.add_attribute("metric_value", value)
                    if properties:
                        for k, v in properties.items():
                            span.add_attribute(f"prop.{k}", v)
            except Exception as e:
                logger.debug(f"Failed to track metric: {e}")

        logger.info(
            "custom_metric",
            extra={
                "metric_name": name,
                "metric_value": value,
                **(properties or {}),
            },
        )

    def track_exception(
        self,
        exception: Exception,
        properties: dict[str, str] | None = None,
    ) -> None:
        """Track an exception."""
        if self.enabled and self._tracer:
            try:
                with self._tracer.span(name="exception") as span:
                    span.add_attribute("exception_type", type(exception).__name__)
                    span.add_attribute("exception_message", str(exception))
                    if properties:
                        for k, v in properties.items():
                            span.add_attribute(f"prop.{k}", v)
            except Exception as e:
                logger.debug(f"Failed to track exception: {e}")

        logger.exception(
            "tracked_exception",
            extra={
                "exception_type": type(exception).__name__,
                **(properties or {}),
            },
        )


# Global telemetry client instance
telemetry_client = AppInsightsTelemetryClient()


class AppInsightsMiddleware(BaseHTTPMiddleware):
    """Middleware that tracks request duration and logs telemetry.

    Emits structured log lines for every request including method, path,
    status code, and duration in milliseconds. Integrates with telemetry
    client for custom dimensions.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        operation_id = str(uuid.uuid4())[:8]
        request.state.operation_id = operation_id

        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        # Skip noisy health-check logging
        if request.url.path not in ("/health", "/health/detailed", "/metrics"):
            # Extract user context if available
            user_id = getattr(request.state, "user_id", None)
            tenant_id = getattr(request.state, "tenant_id", None)

            # Create telemetry event
            event = TelemetryEvent(
                event_type=TelemetryEventType.API_REQUEST,
                operation_id=operation_id,
                duration_ms=round(duration_ms, 1),
                success=response.status_code < 400,
                user_id=user_id,
                tenant_id=tenant_id,
                properties={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "client_host": request.client.host if request.client else None,
                    "user_agent": request.headers.get("user-agent"),
                },
                metrics={
                    "duration_ms": duration_ms,
                    "response_size_bytes": int(response.headers.get("content-length", 0)),
                },
            )
            telemetry_client.track_event(event)

        # Attach server-timing header for observability
        response.headers["Server-Timing"] = f"total;dur={duration_ms:.1f}"
        response.headers["X-Operation-ID"] = operation_id
        return response


# =============================================================================
# Sync Operation Telemetry
# =============================================================================


@contextmanager
def track_sync_operation(
    sync_type: str,
    tenant_id: str | None = None,
    is_full_sync: bool = False,
) -> Callable[[], None]:
    """Context manager to track sync operation telemetry.

    Usage:
        with track_sync_operation("costs", tenant_id="abc123") as complete:
            # Perform sync
            result = sync_costs()
            complete(records_synced=result.count)
    """
    start_time = time.time()
    operation_id = str(uuid.uuid4())[:8]

    # Track start
    start_event = TelemetryEvent(
        event_type=TelemetryEventType.SYNC_STARTED,
        operation_id=operation_id,
        tenant_id=tenant_id,
        properties={
            "sync_type": sync_type,
            "is_full_sync": is_full_sync,
        },
    )
    telemetry_client.track_event(start_event)

    records_synced = 0
    success = False
    error_message = None

    def complete(**kwargs) -> None:
        nonlocal records_synced, success
        records_synced = kwargs.get("records_synced", 0)
        success = kwargs.get("success", True)

    try:
        yield complete
    except Exception as e:
        success = False
        error_message = str(e)
        raise
    finally:
        duration_ms = (time.time() - start_time) * 1000

        # Track completion or failure
        if success:
            complete_event = TelemetryEvent(
                event_type=TelemetryEventType.SYNC_COMPLETED,
                operation_id=operation_id,
                tenant_id=tenant_id,
                duration_ms=duration_ms,
                success=True,
                properties={
                    "sync_type": sync_type,
                    "is_full_sync": is_full_sync,
                    "records_synced": records_synced,
                },
                metrics={
                    "duration_ms": duration_ms,
                    "records_synced": float(records_synced),
                    "records_per_second": records_synced / (duration_ms / 1000)
                    if duration_ms > 0
                    else 0,
                },
            )
            telemetry_client.track_event(complete_event)
        else:
            fail_event = TelemetryEvent(
                event_type=TelemetryEventType.SYNC_FAILED,
                operation_id=operation_id,
                tenant_id=tenant_id,
                duration_ms=duration_ms,
                success=False,
                properties={
                    "sync_type": sync_type,
                    "is_full_sync": is_full_sync,
                    "error": error_message,
                },
                metrics={
                    "duration_ms": duration_ms,
                },
            )
            telemetry_client.track_event(fail_event)


def track_sync_completed(
    sync_type: str,
    tenant_id: str,
    records_synced: int,
    duration_seconds: float,
    is_full_sync: bool = False,
) -> None:
    """Track a completed sync operation."""
    event = TelemetryEvent(
        event_type=TelemetryEventType.SYNC_COMPLETED,
        tenant_id=tenant_id,
        duration_ms=duration_seconds * 1000,
        success=True,
        properties={
            "sync_type": sync_type,
            "is_full_sync": is_full_sync,
            "records_synced": records_synced,
        },
        metrics={
            "duration_ms": duration_seconds * 1000,
            "records_synced": float(records_synced),
            "records_per_second": records_synced / duration_seconds if duration_seconds > 0 else 0,
        },
    )
    telemetry_client.track_event(event)


def track_sync_failed(
    sync_type: str,
    tenant_id: str,
    error: Exception,
    duration_seconds: float,
    is_full_sync: bool = False,
) -> None:
    """Track a failed sync operation."""
    event = TelemetryEvent(
        event_type=TelemetryEventType.SYNC_FAILED,
        tenant_id=tenant_id,
        duration_ms=duration_seconds * 1000,
        success=False,
        properties={
            "sync_type": sync_type,
            "is_full_sync": is_full_sync,
            "error_type": type(error).__name__,
            "error_message": str(error)[:500],  # Truncate long messages
        },
        metrics={
            "duration_ms": duration_seconds * 1000,
        },
    )
    telemetry_client.track_event(event)


# =============================================================================
# Authentication Telemetry
# =============================================================================


def track_auth_login_success(
    user_id: str,
    tenant_id: str,
    auth_method: str = "oauth2",
    mfa_used: bool = False,
) -> None:
    """Track successful authentication."""
    event = TelemetryEvent(
        event_type=TelemetryEventType.AUTH_LOGIN_SUCCESS,
        user_id=user_id,
        tenant_id=tenant_id,
        success=True,
        properties={
            "auth_method": auth_method,
            "mfa_used": mfa_used,
        },
    )
    telemetry_client.track_event(event)


def track_auth_login_failure(
    user_id: str | None,
    tenant_id: str | None,
    auth_method: str,
    failure_reason: str,
    ip_address: str | None = None,
) -> None:
    """Track failed authentication attempt."""
    event = TelemetryEvent(
        event_type=TelemetryEventType.AUTH_LOGIN_FAILURE,
        user_id=user_id,
        tenant_id=tenant_id,
        success=False,
        properties={
            "auth_method": auth_method,
            "failure_reason": failure_reason,
            "ip_address": ip_address,
        },
    )
    telemetry_client.track_event(event)


def track_auth_logout(user_id: str, tenant_id: str) -> None:
    """Track user logout."""
    event = TelemetryEvent(
        event_type=TelemetryEventType.AUTH_LOGOUT,
        user_id=user_id,
        tenant_id=tenant_id,
        success=True,
    )
    telemetry_client.track_event(event)


def track_auth_token_refresh(user_id: str, tenant_id: str, success: bool) -> None:
    """Track token refresh operation."""
    event = TelemetryEvent(
        event_type=TelemetryEventType.AUTH_TOKEN_REFRESH,
        user_id=user_id,
        tenant_id=tenant_id,
        success=success,
    )
    telemetry_client.track_event(event)


# =============================================================================
# Business Metrics Telemetry
# =============================================================================


def track_compliance_violation(
    tenant_id: str,
    framework: str,
    control_id: str,
    severity: str,
    resource_count: int = 1,
) -> None:
    """Track a compliance violation detection."""
    event = TelemetryEvent(
        event_type=TelemetryEventType.COMPLIANCE_VIOLATION,
        tenant_id=tenant_id,
        properties={
            "framework": framework,
            "control_id": control_id,
            "severity": severity,
        },
        metrics={
            "resource_count": float(resource_count),
        },
    )
    telemetry_client.track_event(event)


def track_budget_alert(
    tenant_id: str,
    budget_id: str,
    budget_name: str,
    threshold_percent: float,
    current_spend: float,
    budget_amount: float,
) -> None:
    """Track a budget threshold alert."""
    event = TelemetryEvent(
        event_type=TelemetryEventType.BUDGET_ALERT,
        tenant_id=tenant_id,
        properties={
            "budget_id": budget_id,
            "budget_name": budget_name,
            "threshold_percent": threshold_percent,
        },
        metrics={
            "current_spend": current_spend,
            "budget_amount": budget_amount,
            "remaining_budget": budget_amount - current_spend,
            "consumed_percent": (current_spend / budget_amount * 100) if budget_amount > 0 else 0,
        },
    )
    telemetry_client.track_event(event)


def track_cost_anomaly(
    tenant_id: str,
    service_name: str,
    expected_cost: float,
    actual_cost: float,
    anomaly_score: float,
) -> None:
    """Track a cost anomaly detection."""
    variance = actual_cost - expected_cost
    event = TelemetryEvent(
        event_type=TelemetryEventType.COST_ANOMALY,
        tenant_id=tenant_id,
        properties={
            "service_name": service_name,
            "variance_direction": "increase" if variance > 0 else "decrease",
        },
        metrics={
            "expected_cost": expected_cost,
            "actual_cost": actual_cost,
            "variance": variance,
            "variance_percent": (variance / expected_cost * 100) if expected_cost > 0 else 0,
            "anomaly_score": anomaly_score,
        },
    )
    telemetry_client.track_event(event)


# =============================================================================
# Dependency Tracking
# =============================================================================


def track_dependency(
    name: str,
    data: str,
    duration: float,
    success: bool,
    dependency_type: str | None = None,
    properties: dict[str, Any] | None = None,
) -> None:
    """Track a dependency call (e.g. database query, HTTP call).

    Args:
        name: Name of the dependency (e.g. "slow_query", "blob_storage").
        data: Details about the call (truncated to 100 chars by callers).
        duration: Duration in milliseconds.
        success: Whether the call succeeded.
        dependency_type: Type of dependency (e.g. "SQL", "HTTP", "BLOB").
        properties: Optional additional key/value properties.
    """
    event = TelemetryEvent(
        event_type=TelemetryEventType.DEPENDENCY,
        duration_ms=duration,
        success=success,
        properties={
            "dependency_name": name,
            "dependency_data": data[:100],
            "dependency_type": dependency_type or "unknown",
            **(properties or {}),
        },
        metrics={
            "duration_ms": duration,
        },
    )
    telemetry_client.track_event(event)


# =============================================================================
# Initialization
# =============================================================================


def init_app_insights(app) -> None:
    """Initialize Application Insights telemetry on the FastAPI app.

    When ``APPLICATIONINSIGHTS_CONNECTION_STRING`` is set **and** the
    ``opencensus`` package is available, a full Azure exporter is
    configured. Otherwise we fall back to the lightweight
    :class:`AppInsightsMiddleware` for structured request logging.

    Also initializes the global telemetry client for custom events.
    """
    settings = get_settings()

    if settings.app_insights_enabled:
        try:
            # Imports are done in __init__ of telemetry_client
            # Just verify that opencensus is available
            from opencensus.ext.azure.trace_exporter import AzureExporter  # noqa: F401

            logger.info("App Insights enabled - telemetry client initialized")
        except ImportError:
            logger.warning(
                "opencensus not installed; using basic request logging. "
                "Install with: pip install opencensus-ext-azure"
            )
    else:
        logger.info("APPLICATIONINSIGHTS_CONNECTION_STRING not set — telemetry disabled")

    app.add_middleware(AppInsightsMiddleware)
    logger.info("App Insights request middleware registered")

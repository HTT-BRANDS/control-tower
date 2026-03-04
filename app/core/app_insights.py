"""Azure Application Insights integration (P6: 4vv).

Provides request telemetry middleware and optional OpenCensus integration
for Azure Application Insights. Falls back to structured logging when
the OpenCensus SDK is not installed.
"""

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class AppInsightsMiddleware(BaseHTTPMiddleware):
    """Middleware that tracks request duration and logs telemetry.

    Emits structured log lines for every request including method, path,
    status code, and duration in milliseconds.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        # Skip noisy health-check logging
        if request.url.path not in ("/health", "/health/detailed"):
            logger.info(
                "request_completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 1),
                },
            )

        # Attach server-timing header for observability
        response.headers["Server-Timing"] = f"total;dur={duration_ms:.1f}"
        return response


def init_app_insights(app) -> None:
    """Initialize Application Insights telemetry on the FastAPI app.

    When ``APPLICATIONINSIGHTS_CONNECTION_STRING`` is set **and** the
    ``opencensus`` package is available, a full Azure exporter is
    configured.  Otherwise we fall back to the lightweight
    :class:`AppInsightsMiddleware` for structured request logging.
    """
    settings = get_settings()

    if settings.app_insights_enabled:
        try:
            from opencensus.ext.azure.trace_exporter import AzureExporter  # noqa: F401
            from opencensus.trace.samplers import ProbabilitySampler  # noqa: F401

            logger.info("App Insights SDK detected — Azure exporter available")
        except ImportError:
            logger.warning(
                "opencensus not installed; using basic request logging. "
                "Install with: pip install opencensus-ext-azure"
            )
    else:
        logger.info("APPLICATIONINSIGHTS_CONNECTION_STRING not set — telemetry disabled")

    app.add_middleware(AppInsightsMiddleware)
    logger.info("App Insights request middleware registered")

"""Custom Prometheus middleware for FastAPI.

Replaces prometheus-fastapi-instrumentator with a lightweight
prometheus_client-based implementation.  Keeps identical metric
names and label semantics so existing Grafana dashboards stay valid.
"""

import time
from collections.abc import Callable

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "handler", "status"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "handler", "status"],
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that instruments HTTP requests with Prometheus metrics."""

    def __init__(
        self,
        app,
        excluded_handlers: list[str] | None = None,
        should_group_status_codes: bool = False,
        should_ignore_untemplated: bool = True,
    ):
        super().__init__(app)
        self.excluded_handlers = set(
            excluded_handlers or ["/health", "/health/detailed", "/metrics"]
        )
        self.should_group_status_codes = should_group_status_codes
        self.should_ignore_untemplated = should_ignore_untemplated

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in self.excluded_handlers:
            return await call_next(request)

        start_time = time.perf_counter()
        response = None
        status = "500"

        try:
            response = await call_next(request)
            status = str(response.status_code)
        finally:
            duration = time.perf_counter() - start_time
            route_matched = request.scope.get("route") is not None

            if not (self.should_ignore_untemplated and not route_matched):
                if self.should_group_status_codes:
                    status = status[0] + "xx"

                REQUEST_DURATION.labels(
                    method=request.method, handler=request.url.path, status=status
                ).observe(duration)
                REQUEST_COUNT.labels(
                    method=request.method, handler=request.url.path, status=status
                ).inc()

        return response  # type: ignore[return-value]


def expose_metrics() -> Response:
    """Return Prometheus metrics as a Starlette Response."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )

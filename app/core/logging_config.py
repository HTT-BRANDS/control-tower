"""
Structured Logging Configuration

JSON-formatted logs with correlation IDs for distributed tracing and
API endpoint timing metrics.
"""

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from typing import Any

# Context variable for correlation ID
correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)

# Context variable for request timing
request_start_time: ContextVar[float | None] = ContextVar("request_start_time", default=None)


def get_correlation_id() -> str:
    """Get or create correlation ID for current context."""
    cid = correlation_id.get()
    if not cid:
        cid = str(uuid.uuid4())[:8]
        correlation_id.set(cid)
    return cid


def set_correlation_id(cid: str):
    """Set correlation ID for current context."""
    correlation_id.set(cid)


def set_request_start_time():
    """Set the request start time for timing calculations."""
    request_start_time.set(time.perf_counter())


def get_request_duration_ms() -> float | None:
    """Get the request duration in milliseconds since start_time was set."""
    start = request_start_time.get()
    if start is None:
        return None
    return (time.perf_counter() - start) * 1000


def log_api_request(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    user_id: str | None = None,
    tenant_id: str | None = None,
    extra: dict[str, Any] | None = None,
):
    """Log API request with timing and context.

    Args:
        method: HTTP method (GET, POST, etc.)
        path: Request path
        status_code: HTTP status code
        duration_ms: Request duration in milliseconds
        user_id: Optional user ID
        tenant_id: Optional tenant ID
        extra: Additional fields to include in log
    """
    log_data = {
        "event": "api_request",
        "correlation_id": get_correlation_id(),
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
        "user_id": user_id,
        "tenant_id": tenant_id,
    }

    if extra:
        log_data.update(extra)

    # Determine log level based on status code
    logger = logging.getLogger("api.requests")
    if status_code >= 500:
        logger.error(json.dumps(log_data))
    elif status_code >= 400:
        logger.warning(json.dumps(log_data))
    else:
        logger.info(json.dumps(log_data))


class JSONFormatter(logging.Formatter):
    """JSON log formatter with correlation ID."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", None) or get_correlation_id(),
            "path": f"{record.pathname}:{record.lineno}",
        }

        # Add extra fields
        if hasattr(record, "extra"):
            log_data.update(record.extra)

        # Add timing info if available
        duration = get_request_duration_ms()
        if duration is not None:
            log_data["duration_ms"] = round(duration, 2)

        # Add exception info
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


def configure_logging():
    """Configure structured JSON logging."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.INFO)

    # API request logger
    api_logger = logging.getLogger("api.requests")
    api_logger.setLevel(logging.INFO)

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

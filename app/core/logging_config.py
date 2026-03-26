"""
Structured Logging Configuration

JSON-formatted logs with correlation IDs for distributed tracing.
"""

import logging
import json
import sys
from contextvars import ContextVar
from typing import Any, Optional
import uuid

# Context variable for correlation ID
correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


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


class JSONFormatter(logging.Formatter):
    """JSON log formatter with correlation ID."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'correlation_id': getattr(record, 'correlation_id', None) or get_correlation_id(),
            'path': f"{record.pathname}:{record.lineno}",
        }

        # Add extra fields
        if hasattr(record, 'extra'):
            log_data.update(record.extra)

        # Add exception info
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


def configure_logging():
    """Configure structured JSON logging."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.INFO)

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

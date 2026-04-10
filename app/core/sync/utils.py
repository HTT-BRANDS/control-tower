"""Sync utility functions for data safety and audit trail.

Provides helpers to prevent column overflow errors that can poison
SQLAlchemy sessions and cascade to kill ALL sync jobs (ADR-0010).
"""

import logging

logger = logging.getLogger(__name__)


def safe_truncate(
    value: str | None,
    max_len: int,
    field_name: str,
    context: dict | None = None,
) -> str | None:
    """Safely truncate a string value to fit a database column.

    Returns the value unchanged if it fits, or truncates with a structured
    warning log for audit trail (STRIDE T-1, R-1).

    Args:
        value: The string value to check/truncate.
        max_len: Maximum allowed length.
        field_name: Name of the field (for logging).
        context: Optional context dict (e.g. tenant, subscription).

    Returns:
        The original value, truncated value, or None.
    """
    if value is None:
        return None
    if len(value) <= max_len:
        return value

    logger.warning(
        "Truncating oversized field",
        extra={
            "field_name": field_name,
            "original_length": len(value),
            "max_length": max_len,
            "context": context or {},
        },
    )
    return value[:max_len]

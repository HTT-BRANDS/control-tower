"""Shared Riverside sync helpers and constants."""

import logging
from collections.abc import Callable
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)

RIVERSIDE_DEADLINE = date(2026, 7, 8)
TARGET_MATURITY_SCORE = 3.0


def _resolve_package_attr(name: str) -> Callable[..., Any]:
    """Resolve historical package-level patch points at call time."""
    from app.services import riverside_sync

    return getattr(riverside_sync, name)


# Lazy imports to avoid circular dependency issues
_graph_client = None


def _get_graph_client(tenant_id: str):
    """Get GraphClient instance lazily to avoid circular imports."""
    global _graph_client
    if _graph_client is None:
        from app.api.services.graph_client import GraphClient

        _graph_client = GraphClient
    return _graph_client(tenant_id)


def _get_monitoring_service(db):
    """Get MonitoringService instance lazily to avoid circular imports."""
    from app.api.services.monitoring_service import MonitoringService

    return MonitoringService(db)


class SyncError(Exception):
    """Exception raised when sync operations fail.

    Carries optional HTTP status_code so the retry decorator can
    correctly identify non-retryable errors (e.g. 403 Forbidden).
    """

    def __init__(
        self,
        message: str,
        tenant_id: str | None = None,
        status_code: int | None = None,
    ) -> None:
        """Initialize sync error.

        Args:
            message: Error message
            tenant_id: Optional tenant ID associated with the error
            status_code: Optional HTTP status code (e.g. 403 for permission errors)
        """
        super().__init__(message)
        self.tenant_id = tenant_id
        self.status_code = status_code


class ProgressTracker:
    """Track sync progress for batch operations."""

    def __init__(self) -> None:
        """Initialize progress tracker."""
        self.total = 0
        self.completed = 0
        self.failed = 0
        self.errors: list[dict] = []

    def increment_completed(self) -> None:
        """Increment completed count."""
        self.completed += 1

    def increment_failed(self, error: str, tenant_id: str | None = None) -> None:
        """Increment failed count and record error.

        Args:
            error: Error message
            tenant_id: Optional tenant ID associated with the error
        """
        self.failed += 1
        self.errors.append({"tenant_id": tenant_id, "error": error})

    def set_total(self, total: int) -> None:
        """Set total items to process."""
        self.total = total

    @property
    def percentage(self) -> float:
        """Calculate completion percentage."""
        if self.total == 0:
            return 0.0
        return (self.completed + self.failed) / self.total * 100

    def to_dict(self) -> dict:
        """Convert tracker to dictionary."""
        return {
            "total": self.total,
            "completed": self.completed,
            "failed": self.failed,
            "percentage": round(self.percentage, 1),
            "errors": self.errors,
        }

"""Data retention service for automated cleanup (P6: 6ty).

Purges time-series records older than configurable thresholds to keep
the database lean.  Each table has its own retention window (in days).

Usage::

    from app.services.retention_service import run_retention_cleanup
    results = run_retention_cleanup()          # use defaults
    results = run_retention_cleanup({"sync_job_logs": 14})  # override one table
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import get_db_context
from app.models.compliance import ComplianceSnapshot
from app.models.cost import CostAnomaly, CostSnapshot
from app.models.identity import IdentitySnapshot
from app.models.monitoring import SyncJobLog
from app.models.resource import IdleResource

logger = logging.getLogger(__name__)

# Default retention periods (days)
DEFAULT_RETENTION: dict[str, int] = {
    "cost_snapshots": 365,
    "identity_snapshots": 365,
    "compliance_snapshots": 365,
    "cost_anomalies": 180,
    "idle_resources": 90,
    "sync_job_logs": 30,
}

# Mapping of table key -> (Model, date column)
_TABLE_CONFIG: list[tuple[str, Any, Any]] = [
    ("cost_snapshots", CostSnapshot, CostSnapshot.synced_at),
    ("identity_snapshots", IdentitySnapshot, IdentitySnapshot.synced_at),
    ("compliance_snapshots", ComplianceSnapshot, ComplianceSnapshot.synced_at),
    ("cost_anomalies", CostAnomaly, CostAnomaly.detected_at),
    ("idle_resources", IdleResource, IdleResource.detected_at),
    ("sync_job_logs", SyncJobLog, SyncJobLog.started_at),
]


class RetentionService:
    """Deletes stale records from time-series tables."""

    def __init__(self, db: Session, retention_days: dict[str, int] | None = None):
        self.db = db
        self.retention = {**DEFAULT_RETENTION, **(retention_days or {})}

    def cleanup_table(self, model, date_col, table_name: str) -> int:
        """Delete records older than the configured retention period."""
        days = self.retention.get(table_name, 365)
        cutoff = datetime.utcnow() - timedelta(days=days)
        count = (
            self.db.query(model)
            .filter(date_col < cutoff)
            .delete(
                synchronize_session=False,
            )
        )
        self.db.commit()
        logger.info("Deleted %d records from %s older than %dd", count, table_name, days)
        return count

    def run_all(self) -> dict[str, int]:
        """Run retention cleanup across all configured tables."""
        results: dict[str, int] = {}
        for table_name, model, date_col in _TABLE_CONFIG:
            results[table_name] = self.cleanup_table(model, date_col, table_name)

        total = sum(results.values())
        logger.info("Retention cleanup complete: %d total records deleted", total)
        return results


def run_retention_cleanup(retention_days: dict[str, int] | None = None) -> dict[str, int]:
    """Convenience wrapper that manages its own DB session."""
    with get_db_context() as db:
        service = RetentionService(db, retention_days)
        return service.run_all()

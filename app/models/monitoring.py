"""Monitoring and observability models for sync jobs."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.tenant import Tenant


class SyncJobLog(Base):
    """Detailed log entry for each sync job execution."""

    __tablename__ = "sync_job_logs"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    job_type: Mapped[str] = Column(
        String(50), nullable=False, index=True
    )  # costs, compliance, resources, identity
    tenant_id: Mapped[str | None] = Column(
        String(36), ForeignKey("tenants.id"), nullable=True
    )  # NULL = all tenants
    status: Mapped[str] = Column(
        String(50), nullable=False, default="running"
    )  # running, completed, failed
    started_at: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    ended_at: Mapped[datetime | None] = Column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = Column(Integer, nullable=True)
    records_processed: Mapped[int] = Column(Integer, default=0)
    records_created: Mapped[int] = Column(Integer, default=0)
    records_updated: Mapped[int] = Column(Integer, default=0)
    errors_count: Mapped[int] = Column(Integer, default=0)
    error_message: Mapped[str | None] = Column(Text, nullable=True)
    details_json: Mapped[str | None] = Column(Text, nullable=True)  # Additional JSON details

    # Relationship
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")

    def __repr__(self) -> str:
        return f"<SyncJobLog {self.job_type}: {self.status}>"

    @property
    def duration_seconds(self) -> float | None:
        """Calculate job duration in seconds."""
        if self.duration_ms:
            return self.duration_ms / 1000.0
        if self.ended_at and self.started_at:
            return (self.ended_at - self.started_at).total_seconds()
        return None


class SyncJobMetrics(Base):
    """Aggregated metrics for sync jobs."""

    __tablename__ = "sync_job_metrics"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    job_type: Mapped[str] = Column(String(50), nullable=False, unique=True, index=True)
    calculated_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Execution counts
    total_runs: Mapped[int] = Column(Integer, default=0)
    successful_runs: Mapped[int] = Column(Integer, default=0)
    failed_runs: Mapped[int] = Column(Integer, default=0)

    # Timing metrics (in milliseconds)
    avg_duration_ms: Mapped[float | None] = Column(Float, nullable=True)
    min_duration_ms: Mapped[int | None] = Column(Integer, nullable=True)
    max_duration_ms: Mapped[int | None] = Column(Integer, nullable=True)

    # Records metrics
    avg_records_processed: Mapped[float | None] = Column(Float, nullable=True)
    total_records_processed: Mapped[int] = Column(Integer, default=0)
    total_errors: Mapped[int] = Column(Integer, default=0)

    # Success rate (0.0 - 1.0)
    success_rate: Mapped[float | None] = Column(Float, nullable=True)

    # Last execution info
    last_run_at: Mapped[datetime | None] = Column(DateTime, nullable=True)
    last_success_at: Mapped[datetime | None] = Column(DateTime, nullable=True)
    last_failure_at: Mapped[datetime | None] = Column(DateTime, nullable=True)
    last_error_message: Mapped[str | None] = Column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<SyncJobMetrics {self.job_type}: {self.success_rate:.2%} success>"


class Alert(Base):
    """Alert history for sync job failures and anomalies."""

    __tablename__ = "alerts"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    alert_type: Mapped[str] = Column(
        String(50), nullable=False, index=True
    )  # sync_failure, no_records, stale_sync, high_error_rate
    severity: Mapped[str] = Column(
        String(20), nullable=False, default="warning"
    )  # info, warning, error, critical
    job_type: Mapped[str | None] = Column(
        String(50), nullable=True, index=True
    )  # costs, compliance, resources, identity
    tenant_id: Mapped[str | None] = Column(String(36), ForeignKey("tenants.id"), nullable=True)
    title: Mapped[str] = Column(String(255), nullable=False)
    message: Mapped[str] = Column(Text, nullable=False)
    details_json: Mapped[str | None] = Column(Text, nullable=True)
    is_resolved: Mapped[bool] = Column(
        Integer, default=False
    )  # Store as 0/1 for SQLite compatibility
    created_at: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    resolved_at: Mapped[datetime | None] = Column(DateTime, nullable=True)
    resolved_by: Mapped[str | None] = Column(String(100), nullable=True)

    # Relationship
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="joined")

    def __repr__(self) -> str:
        return f"<Alert {self.alert_type}: {self.title}>"

    @property
    def is_resolved_bool(self) -> bool:
        """Return is_resolved as boolean."""
        return bool(self.is_resolved)

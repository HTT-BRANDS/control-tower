"""Backfill job tracking model with resumable processing support."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped

from app.core.database import Base


class BackfillStatus(StrEnum):
    """Backfill job status states."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BackfillJob(Base):
    """Track historical data backfill jobs with checkpoint support.

    Supports resumable day-by-day processing with progress tracking.
    """

    __tablename__ = "backfill_jobs"

    id: Mapped[str] = Column(String(36), primary_key=True)
    job_type: Mapped[str] = Column(
        String(50), nullable=False
    )  # costs, identity, compliance, resources
    tenant_id: Mapped[str | None] = Column(String(36))
    status: Mapped[str] = Column(String(50), nullable=False, default=BackfillStatus.PENDING.value)

    # Date range
    start_date: Mapped[datetime] = Column(DateTime, nullable=False)
    end_date: Mapped[datetime] = Column(DateTime, nullable=False)

    # Checkpointing
    current_date: Mapped[datetime | None] = Column(DateTime)  # Current processing date
    progress_percent: Mapped[float] = Column(Float, default=0.0)  # 0.0-100.0

    # Tracking
    records_processed: Mapped[int] = Column(Integer, default=0)
    records_inserted: Mapped[int] = Column(Integer, default=0)
    records_failed: Mapped[int] = Column(Integer, default=0)

    # Error tracking
    last_error: Mapped[str | None] = Column(Text)
    error_count: Mapped[int] = Column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = Column(DateTime)
    completed_at: Mapped[datetime | None] = Column(DateTime)
    paused_at: Mapped[datetime | None] = Column(DateTime)
    cancelled_at: Mapped[datetime | None] = Column(DateTime)

    def __repr__(self) -> str:
        return f"<BackfillJob {self.id}: {self.job_type} {self.status}>"

    @property
    def duration_seconds(self) -> float | None:
        """Calculate job duration in seconds."""
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def is_pending(self) -> bool:
        """Check if job is pending."""
        return self.status == BackfillStatus.PENDING.value

    @property
    def is_running(self) -> bool:
        """Check if job is running."""
        return self.status == BackfillStatus.RUNNING.value

    @property
    def is_paused(self) -> bool:
        """Check if job is paused."""
        return self.status == BackfillStatus.PAUSED.value

    @property
    def is_completed(self) -> bool:
        """Check if job is completed."""
        return self.status == BackfillStatus.COMPLETED.value

    @property
    def is_failed(self) -> bool:
        """Check if job is failed."""
        return self.status == BackfillStatus.FAILED.value

    @property
    def is_cancelled(self) -> bool:
        """Check if job is cancelled."""
        return self.status == BackfillStatus.CANCELLED.value

    @property
    def is_terminal(self) -> bool:
        """Check if job is in a terminal state."""
        return self.status in {
            BackfillStatus.COMPLETED.value,
            BackfillStatus.FAILED.value,
            BackfillStatus.CANCELLED.value,
        }

    @property
    def can_resume(self) -> bool:
        """Check if job can be resumed."""
        return self.status in {
            BackfillStatus.PAUSED.value,
            BackfillStatus.FAILED.value,
        }

    @property
    def can_cancel(self) -> bool:
        """Check if job can be cancelled."""
        return self.status in {
            BackfillStatus.PENDING.value,
            BackfillStatus.RUNNING.value,
            BackfillStatus.PAUSED.value,
        }

    def update_status(self, status: BackfillStatus) -> None:
        """Update job status with appropriate timestamp."""
        self.status = status.value

        if status == BackfillStatus.RUNNING:
            if not self.started_at:
                self.started_at = datetime.utcnow()
        elif status == BackfillStatus.COMPLETED:
            self.completed_at = datetime.utcnow()
        elif status == BackfillStatus.PAUSED:
            self.paused_at = datetime.utcnow()
        elif status == BackfillStatus.CANCELLED:
            self.cancelled_at = datetime.utcnow()

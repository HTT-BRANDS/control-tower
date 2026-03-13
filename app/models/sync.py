"""Sync job tracking model."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped

from app.core.database import Base


class SyncJob(Base):
    """Track background sync job execution."""

    __tablename__ = "sync_jobs"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    job_type: Mapped[str] = Column(
        String(50), nullable=False
    )  # costs, compliance, resources, identity
    tenant_id: Mapped[str | None] = Column(String(36))  # NULL = all tenants
    status: Mapped[str] = Column(String(50), nullable=False)  # pending, running, completed, failed
    started_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = Column(DateTime)
    records_processed: Mapped[int] = Column(Integer, default=0)
    error_message: Mapped[str | None] = Column(Text)

    def __repr__(self) -> str:
        return f"<SyncJob {self.job_type}: {self.status}>"

    @property
    def duration_seconds(self) -> float | None:
        """Calculate job duration in seconds."""
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

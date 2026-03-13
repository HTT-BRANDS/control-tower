"""Notification tracking models for sync job alerts.

Tracks notification delivery status and history for audit and
deduplication purposes.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.alerts import Alert
    from app.models.tenants import Tenant


class NotificationLog(Base):
    """Log entry for sent notifications.

    Tracks when notifications were sent, to which channels,
    and whether delivery was successful for audit purposes.
    """

    __tablename__ = "notification_logs"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)

    # Notification metadata
    channel: Mapped[str] = Column(String(20), nullable=False, index=True)  # teams, email, webhook
    severity: Mapped[str] = Column(
        String(20), nullable=False, default="warning"
    )  # info, warning, error, critical

    # Related entities
    alert_id: Mapped[int | None] = Column(
        Integer, ForeignKey("alerts.id"), nullable=True, index=True
    )
    job_type: Mapped[str | None] = Column(
        String(50), nullable=True, index=True
    )  # costs, compliance, resources, identity
    tenant_id: Mapped[str | None] = Column(
        String(36), ForeignKey("tenants.id"), nullable=True, index=True
    )

    # Notification content
    title: Mapped[str] = Column(String(255), nullable=False)
    message: Mapped[str] = Column(Text, nullable=False)

    # Delivery status
    status: Mapped[str] = Column(
        String(50), nullable=False, default="pending"
    )  # pending, sent, failed, retrying
    sent_at: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    delivered_at: Mapped[datetime | None] = Column(DateTime, nullable=True)

    # Response tracking
    response_status: Mapped[str | None] = Column(
        String(10), nullable=True
    )  # HTTP status code or error
    response_body: Mapped[str | None] = Column(
        Text, nullable=True
    )  # Response content or error message

    # Retry tracking
    retry_count: Mapped[int] = Column(Integer, default=0)
    last_retry_at: Mapped[datetime | None] = Column(DateTime, nullable=True)

    # Metadata
    metadata_json: Mapped[str | None] = Column(Text, nullable=True)  # Additional JSON metadata

    # Relationships
    alert: Mapped[Alert] = relationship("Alert", lazy="joined")
    tenant: Mapped[Tenant] = relationship("Tenant", lazy="joined")

    def __repr__(self) -> str:
        return f"<NotificationLog {self.channel}: {self.title} [{self.status}]>"

    @property
    def is_success(self) -> bool:
        """Check if notification was successfully delivered."""
        return self.status == "sent" and self.delivered_at is not None

    @property
    def can_retry(self) -> bool:
        """Check if notification can be retried."""
        if self.status in ("sent", "delivered"):
            return False
        return self.retry_count < 3

    def mark_sent(
        self, response_status: str | None = None, response_body: str | None = None
    ) -> None:
        """Mark notification as successfully sent.

        Args:
            response_status: HTTP status code or success indicator
            response_body: Response content from the channel
        """
        self.status = "sent"
        self.delivered_at = datetime.utcnow()
        if response_status:
            self.response_status = response_status
        if response_body:
            self.response_body = response_body

    def mark_failed(self, error_message: str) -> None:
        """Mark notification as failed.

        Args:
            error_message: Error message or response body
        """
        self.status = "failed"
        self.response_body = error_message

    def mark_retrying(self) -> None:
        """Mark notification as being retried."""
        self.status = "retrying"
        self.retry_count += 1
        self.last_retry_at = datetime.utcnow()

"""ResourceLifecycleEvent model — tracks resource changes over time (RM-004)."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ResourceLifecycleEvent(Base):
    """Records create/update/delete events for Azure resources."""

    __tablename__ = "resource_lifecycle_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    resource_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    resource_name: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(200), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    subscription_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    event_type: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # created | updated | deleted | reappeared
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )
    previous_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    current_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    changed_fields: Mapped[list | None] = mapped_column(JSON, nullable=True)
    sync_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    __table_args__ = (
        Index("ix_lifecycle_resource_time", "resource_id", "detected_at"),
        Index("ix_lifecycle_tenant_type", "tenant_id", "event_type"),
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "resource_type": self.resource_type,
            "tenant_id": self.tenant_id,
            "subscription_id": self.subscription_id,
            "event_type": self.event_type,
            "detected_at": self.detected_at.isoformat() if self.detected_at else None,
            "changed_fields": self.changed_fields,
            "sync_run_id": self.sync_run_id,
        }

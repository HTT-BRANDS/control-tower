"""AuditLogEntry model for persistent audit trail.

Tracks all user-initiated actions: authentication, sync triggers,
bulk operations, and configuration changes.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditLogEntry(Base):
    """Persistent audit log for user and system actions."""

    __tablename__ = "audit_log_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )
    actor_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="success"
    )  # success | failure | warning
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        Index("ix_audit_log_timestamp_actor", "timestamp", "actor_id"),
        Index("ix_audit_log_action_tenant", "action", "tenant_id"),
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to response dict."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "actor_id": self.actor_id,
            "actor_email": self.actor_email,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "tenant_id": self.tenant_id,
            "status": self.status,
            "detail": self.detail,
            "metadata": self.metadata_json,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
        }

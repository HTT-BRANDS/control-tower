"""Audit log service — write and query audit log entries.

Provides write_entry() for recording actions and query methods
with filtering and pagination for the API routes.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLogEntry

logger = logging.getLogger(__name__)


class AuditAction:
    """Well-known action constants — extend as new actions are wired up."""

    # Auth
    LOGIN_SUCCESS = "auth.login.success"
    LOGIN_FAILURE = "auth.login.failure"
    LOGOUT = "auth.logout"
    TOKEN_REFRESH = "auth.token.refresh"

    # Sync
    SYNC_TRIGGERED = "sync.triggered"
    SYNC_COMPLETED = "sync.completed"
    SYNC_FAILED = "sync.failed"

    # Bulk operations
    BULK_UPDATE = "bulk.update"
    BULK_DELETE = "bulk.delete"

    # Compliance
    COMPLIANCE_RULE_CREATED = "compliance.rule.created"
    COMPLIANCE_RULE_UPDATED = "compliance.rule.updated"
    COMPLIANCE_RULE_DELETED = "compliance.rule.deleted"

    # Resource
    RESOURCE_REVIEWED = "resource.reviewed"
    BUDGET_UPDATED = "budget.updated"

    # Admin
    USER_ROLE_CHANGED = "admin.user.role_changed"
    SETTINGS_UPDATED = "admin.settings.updated"


class AuditLogService:
    """Service for reading and writing audit log entries."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def write_entry(
        self,
        action: str,
        *,
        actor_id: str | None = None,
        actor_email: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        tenant_id: str | None = None,
        status: str = "success",
        detail: str | None = None,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        request: Request | None = None,
    ) -> AuditLogEntry:
        """Write a single audit log entry.

        If `request` is provided, ip_address and user_agent are
        extracted automatically (kwargs take precedence if provided).
        """
        if request is not None:
            if ip_address is None:
                forwarded = request.headers.get("X-Forwarded-For")
                ip_address = (
                    forwarded.split(",")[0].strip()
                    if forwarded
                    else str(request.client.host)
                    if request.client
                    else None
                )
            if user_agent is None:
                user_agent = request.headers.get("User-Agent")

        entry = AuditLogEntry(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC),
            actor_id=actor_id,
            actor_email=actor_email,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            tenant_id=tenant_id,
            status=status,
            detail=detail,
            metadata_json=metadata,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        try:
            self.db.add(entry)
            self.db.commit()
            self.db.refresh(entry)
            logger.debug("Audit: %s by %s", action, actor_email or actor_id or "system")
        except Exception as exc:
            self.db.rollback()
            logger.warning("Audit log write failed (non-fatal): %s", exc)
        return entry

    def query(
        self,
        *,
        actor_id: str | None = None,
        actor_email: str | None = None,
        action: str | None = None,
        action_prefix: str | None = None,
        tenant_id: str | None = None,
        resource_type: str | None = None,
        status: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLogEntry]:
        """Query audit log entries with optional filters.

        Filters are ANDed together. Use action_prefix for wildcard
        prefix matching (e.g. 'auth.' returns all auth events).
        """
        q = self.db.query(AuditLogEntry)

        if actor_id:
            q = q.filter(AuditLogEntry.actor_id == actor_id)
        if actor_email:
            q = q.filter(AuditLogEntry.actor_email == actor_email)
        if action:
            q = q.filter(AuditLogEntry.action == action)
        elif action_prefix:
            q = q.filter(AuditLogEntry.action.like(f"{action_prefix}%"))
        if tenant_id:
            q = q.filter(AuditLogEntry.tenant_id == tenant_id)
        if resource_type:
            q = q.filter(AuditLogEntry.resource_type == resource_type)
        if status:
            q = q.filter(AuditLogEntry.status == status)
        if since:
            q = q.filter(AuditLogEntry.timestamp >= since)
        if until:
            q = q.filter(AuditLogEntry.timestamp <= until)

        return (
            q.order_by(AuditLogEntry.timestamp.desc()).offset(offset).limit(min(limit, 500)).all()
        )

    def count(
        self,
        *,
        actor_id: str | None = None,
        action_prefix: str | None = None,
        tenant_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> int:
        """Return total count matching filters (for pagination)."""
        q = self.db.query(AuditLogEntry)
        if actor_id:
            q = q.filter(AuditLogEntry.actor_id == actor_id)
        if action_prefix:
            q = q.filter(AuditLogEntry.action.like(f"{action_prefix}%"))
        if tenant_id:
            q = q.filter(AuditLogEntry.tenant_id == tenant_id)
        if since:
            q = q.filter(AuditLogEntry.timestamp >= since)
        if until:
            q = q.filter(AuditLogEntry.timestamp <= until)
        return q.count()

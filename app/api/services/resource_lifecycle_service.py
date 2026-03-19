"""Resource lifecycle service — detects and records resource change events (RM-004)."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.resource import Resource
from app.models.resource_lifecycle import ResourceLifecycleEvent

logger = logging.getLogger(__name__)


class ResourceLifecycleService:
    """Detects resource lifecycle events and provides history queries."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def record_event(
        self,
        resource: Resource,
        event_type: str,
        *,
        previous_state: dict | None = None,
        current_state: dict | None = None,
        changed_fields: list[str] | None = None,
        sync_run_id: str | None = None,
    ) -> ResourceLifecycleEvent:
        """Record a single lifecycle event for a resource."""
        event = ResourceLifecycleEvent(
            id=str(uuid.uuid4()),
            resource_id=resource.id,
            resource_name=resource.name,
            resource_type=resource.resource_type,
            tenant_id=resource.tenant_id,
            subscription_id=resource.subscription_id,
            event_type=event_type,
            detected_at=datetime.now(UTC),
            previous_state=previous_state,
            current_state=current_state,
            changed_fields=changed_fields,
            sync_run_id=sync_run_id,
        )
        try:
            self.db.add(event)
            self.db.commit()
            self.db.refresh(event)
        except Exception as exc:
            self.db.rollback()
            logger.warning(f"Lifecycle event write failed (non-fatal): {exc}")
        return event

    def detect_changes(
        self,
        previous: dict[str, Any],
        current: dict[str, Any],
        tracked_fields: list[str] | None = None,
    ) -> list[str]:
        """Compare two resource state dicts and return list of changed field names."""
        fields = tracked_fields or [
            "provisioning_state",
            "location",
            "sku",
            "tags_json",
            "estimated_monthly_cost",
            "is_orphaned",
        ]
        changed = []
        for field in fields:
            if previous.get(field) != current.get(field):
                changed.append(field)
        return changed

    def get_history(
        self,
        resource_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ResourceLifecycleEvent]:
        """Return lifecycle events for a specific resource, newest first."""
        return (
            self.db.query(ResourceLifecycleEvent)
            .filter(ResourceLifecycleEvent.resource_id == resource_id)
            .order_by(ResourceLifecycleEvent.detected_at.desc())
            .offset(offset)
            .limit(min(limit, 200))
            .all()
        )

    def get_tenant_events(
        self,
        tenant_id: str,
        *,
        event_type: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ResourceLifecycleEvent]:
        """Return recent lifecycle events for a tenant."""
        q = self.db.query(ResourceLifecycleEvent).filter(
            ResourceLifecycleEvent.tenant_id == tenant_id
        )
        if event_type:
            q = q.filter(ResourceLifecycleEvent.event_type == event_type)
        if since:
            q = q.filter(ResourceLifecycleEvent.detected_at >= since)
        return (
            q.order_by(ResourceLifecycleEvent.detected_at.desc())
            .offset(offset)
            .limit(min(limit, 500))
            .all()
        )

    def get_changes(
        self,
        *,
        tenant_id: str | None = None,
        tenant_ids: list[str] | None = None,
        resource_type: str | None = None,
        event_type: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ResourceLifecycleEvent], int]:
        """Return cross-resource lifecycle events with optional filtering (RM-010).

        Supports filtering by tenant, resource type, event type, and date range.
        Pass tenant_ids (list) for multi-tenant isolation; tenant_id (single string)
        is kept for backward compatibility with direct service callers.
        Returns (events, total_count) for paginated responses.
        """
        q = self.db.query(ResourceLifecycleEvent)
        # tenant_ids (list) takes priority — used by the route for proper isolation
        if tenant_ids is not None:
            q = q.filter(ResourceLifecycleEvent.tenant_id.in_(tenant_ids))
        elif tenant_id:
            q = q.filter(ResourceLifecycleEvent.tenant_id == tenant_id)
        if resource_type:
            q = q.filter(ResourceLifecycleEvent.resource_type == resource_type)
        if event_type:
            q = q.filter(ResourceLifecycleEvent.event_type == event_type)
        if since:
            q = q.filter(ResourceLifecycleEvent.detected_at >= since)
        if until:
            q = q.filter(ResourceLifecycleEvent.detected_at <= until)
        total = q.count()
        events = (
            q.order_by(ResourceLifecycleEvent.detected_at.desc())
            .offset(offset)
            .limit(min(limit, 200))
            .all()
        )
        return events, total

"""Audit log API routes — CM-010."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.services.audit_log_service import AuditLogService
from app.core.auth import User, get_current_user
from app.core.database import get_db
from app.core.rate_limit import rate_limit

router = APIRouter(
    prefix="/api/v1/audit-logs",
    tags=["audit-logs"],
    dependencies=[Depends(rate_limit("default"))],
)


@router.get("")
async def list_audit_logs(
    actor_id: str | None = Query(default=None, description="Filter by actor user ID"),
    actor_email: str | None = Query(default=None, description="Filter by actor email"),
    action: str | None = Query(
        default=None, description="Exact action match (e.g. auth.login.success)"
    ),
    action_prefix: str | None = Query(
        default=None, description="Action prefix match (e.g. 'auth.')"
    ),
    tenant_id: str | None = Query(default=None, description="Filter by tenant UUID"),
    resource_type: str | None = Query(default=None, description="Filter by resource type"),
    status: str | None = Query(
        default=None, description="Filter by status: success | failure | warning"
    ),
    since: datetime | None = Query(default=None, description="ISO 8601 start datetime"),
    until: datetime | None = Query(default=None, description="ISO 8601 end datetime"),
    limit: int = Query(default=100, ge=1, le=500, description="Max records to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """List audit log entries with optional filters.

    Returns paginated audit log entries ordered by timestamp descending.
    Requires authentication. Admin users see all entries; standard users
    see only their own entries (filtered by actor_id = current user).
    """
    service = AuditLogService(db)

    # Non-admin users can only see their own entries
    if not getattr(current_user, "is_admin", False):
        actor_id = current_user.id

    entries = service.query(
        actor_id=actor_id,
        actor_email=actor_email,
        action=action,
        action_prefix=action_prefix,
        tenant_id=tenant_id,
        resource_type=resource_type,
        status=status,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )
    total = service.count(
        actor_id=actor_id,
        action_prefix=action_prefix,
        tenant_id=tenant_id,
        since=since,
        until=until,
    )

    return {
        "entries": [e.to_dict() for e in entries],
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total,
    }


@router.get("/summary")
async def audit_log_summary(
    tenant_id: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get audit log summary counts grouped by action category."""
    service = AuditLogService(db)

    categories = ["auth", "sync", "bulk", "compliance", "resource", "admin"]
    summary = {}
    for cat in categories:
        summary[cat] = service.count(
            action_prefix=f"{cat}.",
            tenant_id=tenant_id,
            since=since,
        )

    return {
        "summary": summary,
        "total": sum(summary.values()),
        "tenant_id": tenant_id,
        "since": since.isoformat() if since else None,
    }

"""Admin service for user management and role assignment.

Provides CRUD operations for user-tenant mappings and role management.
Works with existing ``UserTenant`` as the source of known users — no new
DB models required (ADR-0011 Phase 1).

Phase 4 will add a dedicated ``User`` table for richer profile management.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.permissions import (
    ALL_PERMISSIONS,
    LEGACY_ROLE_MAP,
    WILDCARD_PERMISSION,
    Role,
    get_all_permissions,
)
from app.models.sync import SyncJob
from app.models.tenant import Tenant, UserTenant

logger = logging.getLogger(__name__)

# Role hierarchy for picking highest-privilege role (index = priority).
_ROLE_HIERARCHY: list[str] = [
    Role.VIEWER,
    Role.ANALYST,
    Role.TENANT_ADMIN,
    Role.ADMIN,
]


def _highest_role(roles: list[str]) -> str:
    """Return the highest-privilege role from a list of role slugs."""
    best_idx = -1
    best_role = roles[0] if roles else Role.VIEWER
    for r in roles:
        try:
            idx = _ROLE_HIERARCHY.index(r)
        except ValueError:
            continue
        if idx > best_idx:
            best_idx = idx
            best_role = r
    return best_role


class AdminService:
    """Service layer for admin user-management operations.

    All methods work with ``UserTenant`` and ``Tenant`` tables.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def get_users(
        self,
        *,
        page: int = 1,
        per_page: int = 20,
        search: str | None = None,
        role_filter: str | None = None,
    ) -> dict[str, Any]:
        """List known users with pagination and optional filters.

        Users are discovered from ``UserTenant`` records.  Search matches
        against ``user_id`` (Phase 4 will add email/name search).

        Returns:
            Dict with ``items``, ``total``, ``page``, ``per_page``, ``pages``.
        """
        query = self.db.query(UserTenant)

        if search:
            query = query.filter(UserTenant.user_id.ilike(f"%{search}%"))

        if role_filter:
            # Resolve legacy role names for the filter
            resolved = LEGACY_ROLE_MAP.get(role_filter, role_filter)
            query = query.filter(UserTenant.role == resolved)

        mappings: list[UserTenant] = query.order_by(UserTenant.user_id).all()

        # Group by user_id
        users_map: dict[str, list[UserTenant]] = {}
        for ut in mappings:
            users_map.setdefault(ut.user_id, []).append(ut)

        # Sort user_ids for deterministic pagination
        all_user_ids = sorted(users_map.keys())
        total = len(all_user_ids)
        pages = max(1, math.ceil(total / per_page))
        start = (page - 1) * per_page
        end = start + per_page
        page_user_ids = all_user_ids[start:end]

        items: list[dict[str, Any]] = []
        for uid in page_user_ids:
            uts = users_map[uid]
            roles = sorted({ut.role for ut in uts})
            items.append(
                {
                    "user_id": uid,
                    "tenant_count": len(uts),
                    "roles": roles,
                    "is_active": any(ut.is_active for ut in uts),
                }
            )

        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
        }

    def get_user_by_id(self, user_id: str) -> dict[str, Any]:
        """Get detailed info for a single user.

        Raises:
            HTTPException 404 if no ``UserTenant`` records exist for *user_id*.
        """
        mappings: list[UserTenant] = (
            self.db.query(UserTenant)
            .filter(UserTenant.user_id == user_id)
            .all()
        )

        if not mappings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User '{user_id}' not found",
            )

        # Collect tenant details
        tenant_ids = [ut.tenant_id for ut in mappings]
        tenants: dict[str, Tenant] = {
            t.id: t
            for t in self.db.query(Tenant).filter(Tenant.id.in_(tenant_ids)).all()
        }

        roles = sorted({ut.role for ut in mappings})
        permissions = sorted(get_all_permissions(roles) - {WILDCARD_PERMISSION})
        if any(r == Role.ADMIN or LEGACY_ROLE_MAP.get(r) == Role.ADMIN for r in roles):
            permissions = sorted(ALL_PERMISSIONS)

        tenant_access: list[dict[str, Any]] = []
        for ut in mappings:
            tenant = tenants.get(ut.tenant_id)
            tenant_access.append(
                {
                    "tenant_id": ut.tenant_id,
                    "tenant_name": tenant.name if tenant else "Unknown",
                    "role": ut.role,
                    "is_active": ut.is_active,
                    "can_manage_resources": ut.can_manage_resources,
                    "can_view_costs": ut.can_view_costs,
                    "can_manage_compliance": ut.can_manage_compliance,
                    "granted_at": ut.granted_at.isoformat() if ut.granted_at else None,
                    "last_accessed_at": (
                        ut.last_accessed_at.isoformat() if ut.last_accessed_at else None
                    ),
                }
            )

        return {
            "user_id": user_id,
            "roles": roles,
            "permissions": permissions,
            "tenant_access": tenant_access,
        }

    # ------------------------------------------------------------------
    # Role assignment
    # ------------------------------------------------------------------

    def update_user_roles(
        self,
        user_id: str,
        roles: list[str],
    ) -> dict[str, Any]:
        """Update the role assignment for a user.

        Validates all role names against ``permissions.Role``.  Updates
        ``UserTenant.role`` for **all** of the user's active tenant
        mappings to the highest-privilege role in *roles*.

        Args:
            user_id: The user to update.
            roles: List of role slugs (e.g. ``["analyst"]``).

        Returns:
            Updated user detail dict (same shape as ``get_user_by_id``).

        Raises:
            HTTPException 400 if *roles* is empty or contains invalid values.
            HTTPException 404 if user not found.
        """
        if not roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="roles list must not be empty",
            )

        # Validate each role
        valid_slugs: list[str] = []
        for r in roles:
            resolved = LEGACY_ROLE_MAP.get(r, r)
            try:
                Role(resolved)
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Invalid role '{r}'. "
                        f"Valid roles: {[role.value for role in Role]}"
                    ),
                ) from exc
            valid_slugs.append(resolved)

        # Get existing mappings
        mappings: list[UserTenant] = (
            self.db.query(UserTenant)
            .filter(UserTenant.user_id == user_id)
            .all()
        )

        if not mappings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User '{user_id}' not found",
            )

        # Determine effective role (highest privilege)
        effective_role = _highest_role(valid_slugs)

        # Update all mappings
        for ut in mappings:
            ut.role = effective_role

        self.db.commit()

        logger.info(
            "Roles updated: user=%s, requested=%s, effective=%s",
            user_id,
            roles,
            effective_role,
        )

        return self.get_user_by_id(user_id)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_admin_stats(self) -> dict[str, Any]:
        """Aggregate admin dashboard statistics."""
        total_users: int = (
            self.db.query(func.count(func.distinct(UserTenant.user_id)))
            .scalar()
            or 0
        )

        role_counts = (
            self.db.query(UserTenant.role, func.count(func.distinct(UserTenant.user_id)))
            .group_by(UserTenant.role)
            .all()
        )
        users_by_role: dict[str, int] = dict(role_counts)

        active_tenants: int = (
            self.db.query(func.count(Tenant.id))
            .filter(Tenant.is_active.is_(True))
            .scalar()
            or 0
        )
        total_tenants: int = self.db.query(func.count(Tenant.id)).scalar() or 0

        total_mappings: int = (
            self.db.query(func.count(UserTenant.id)).scalar() or 0
        )

        # Last sync per job type
        last_syncs: dict[str, str | None] = {}
        try:
            latest = (
                self.db.query(SyncJob.job_type, func.max(SyncJob.completed_at))
                .filter(SyncJob.status == "completed")
                .group_by(SyncJob.job_type)
                .all()
            )
            last_syncs = {
                jt: ts.isoformat() if ts else None for jt, ts in latest
            }
        except Exception:
            # SyncJob table may not exist yet in test databases
            pass

        return {
            "total_users": total_users,
            "users_by_role": users_by_role,
            "active_tenants": active_tenants,
            "total_tenants": total_tenants,
            "total_user_tenant_mappings": total_mappings,
            "last_syncs": last_syncs,
        }

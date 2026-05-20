"""Admin API routes for user management and role assignment.

All endpoints require ``system:admin`` permission (admin role only).
A ``POST /api/v1/admin/seed`` endpoint is also available for staging
cold-starts—protected by the ``admin`` role.

Endpoints::

    GET    /api/v1/admin/users               — paginated user list
    GET    /api/v1/admin/users/{user_id}      — single user detail
    PUT    /api/v1/admin/users/{user_id}/roles — update user roles
    GET    /api/v1/admin/roles                — list available roles
    GET    /api/v1/admin/roles/{role_name}    — single role detail
    GET    /api/v1/admin/stats                — admin dashboard stats
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.services.admin_service import AdminService
from app.core.auth import User, require_roles
from app.core.database import get_db
from app.core.permissions import (
    ALL_PERMISSIONS,
    ROLE_PERMISSIONS,
    WILDCARD_PERMISSION,
    Role,
)
from app.core.rate_limit import rate_limit
from app.core.rbac import require_permissions

logger = logging.getLogger(__name__)

# ============================================================================
# Pydantic Schemas
# ============================================================================


class UserSummary(BaseModel):
    """Compact user representation for list endpoints."""

    user_id: str
    tenant_count: int
    roles: list[str]
    is_active: bool


class PaginatedUsersResponse(BaseModel):
    """Paginated collection of users."""

    items: list[UserSummary]
    total: int
    page: int
    per_page: int
    pages: int


class UserTenantAccessInfo(BaseModel):
    """Per-tenant access details for a user."""

    tenant_id: str
    tenant_name: str
    role: str
    is_active: bool
    can_manage_resources: bool
    can_view_costs: bool
    can_manage_compliance: bool
    granted_at: str | None = None
    last_accessed_at: str | None = None


class UserDetailResponse(BaseModel):
    """Full user profile with roles, permissions, and tenant access."""

    user_id: str
    roles: list[str]
    permissions: list[str]
    tenant_access: list[UserTenantAccessInfo]


class RolesUpdateRequest(BaseModel):
    """Request body for updating a user's roles."""

    roles: list[str] = Field(
        ...,
        min_length=1,
        description="List of role slugs (e.g. ['analyst', 'viewer'])",
        json_schema_extra={"examples": [["tenant_admin"], ["analyst", "viewer"]]},
    )


class RoleDetailResponse(BaseModel):
    """Detailed role information with its permission set."""

    name: str
    slug: str
    description: str
    permissions: list[str]
    permission_count: int


class AdminStatsResponse(BaseModel):
    """Admin dashboard statistics."""

    total_users: int
    users_by_role: dict[str, int]
    active_tenants: int
    total_tenants: int
    total_user_tenant_mappings: int
    last_syncs: dict[str, str | None] = Field(default_factory=dict)


# ============================================================================
# Role metadata (static — no DB needed)
# ============================================================================

_ROLE_DESCRIPTIONS: dict[str, tuple[str, str]] = {
    Role.ADMIN: ("Admin", "Full system access with wildcard permissions"),
    Role.TENANT_ADMIN: (
        "Tenant Admin",
        "Manages tenant config, users, compliance, and data. "
        "Cannot create tenants or access system settings.",
    ),
    Role.ANALYST: (
        "Analyst",
        "Read and export data across accessible modules. Cannot modify configuration.",
    ),
    Role.VIEWER: (
        "Viewer",
        "Read-only dashboard access. No exports, no writes.",
    ),
}


def _role_to_detail(role: Role) -> RoleDetailResponse:
    """Build a ``RoleDetailResponse`` from a Role enum member."""
    display_name, description = _ROLE_DESCRIPTIONS[role]
    perms = ROLE_PERMISSIONS[role]
    if WILDCARD_PERMISSION in perms:
        resolved = sorted(ALL_PERMISSIONS)
    else:
        resolved = sorted(perms)

    return RoleDetailResponse(
        name=display_name,
        slug=role.value,
        description=description,
        permissions=resolved,
        permission_count=len(resolved),
    )


# ============================================================================
# Router
# ============================================================================

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"],
)


# ============================================================================
# User endpoints
# ============================================================================


@router.get(
    "/users",
    response_model=PaginatedUsersResponse,
    summary="List users with pagination and filters",
)
async def list_users(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    search: str | None = Query(None, description="Search by user ID"),
    role: str | None = Query(None, description="Filter by role slug"),
    user: User = Depends(require_permissions("system:admin")),
    db: Session = Depends(get_db),
) -> PaginatedUsersResponse:
    """List all known users with their roles and tenant access.

    Users are discovered from ``UserTenant`` mappings.  Results can be
    filtered by role and searched by user ID.
    """
    svc = AdminService(db)
    data = svc.get_users(page=page, per_page=per_page, search=search, role_filter=role)
    return PaginatedUsersResponse(**data)


@router.get(
    "/users/{user_id}",
    response_model=UserDetailResponse,
    summary="Get user detail",
)
async def get_user(
    user_id: str,
    user: User = Depends(require_permissions("system:admin")),
    db: Session = Depends(get_db),
) -> UserDetailResponse:
    """Get a single user's profile with roles, permissions, and tenant access."""
    svc = AdminService(db)
    data = svc.get_user_by_id(user_id)
    return UserDetailResponse(**data)


@router.put(
    "/users/{user_id}/roles",
    response_model=UserDetailResponse,
    summary="Update user roles",
)
async def update_user_roles(
    user_id: str,
    body: RolesUpdateRequest,
    _rate_check: None = Depends(rate_limit("admin_write")),
    user: User = Depends(require_permissions("system:admin")),
    db: Session = Depends(get_db),
) -> UserDetailResponse:
    """Update roles for a user across all tenant mappings.

    Validates each role against ``permissions.Role``.  The highest-privilege
    role is stored in ``UserTenant.role`` for all of the user's active
    tenant mappings.
    """
    # F-01: Segregation of duties — admins cannot modify their own roles.
    if user_id == user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify your own roles — another admin must make this change",
        )

    svc = AdminService(db)
    data = svc.update_user_roles(user_id, body.roles, current_user_id=user.id)
    return UserDetailResponse(**data)


# ============================================================================
# Role endpoints (static — no DB queries)
# ============================================================================


@router.get(
    "/roles",
    response_model=list[RoleDetailResponse],
    summary="List all available roles",
)
async def list_roles(
    user: User = Depends(require_permissions("system:admin")),
) -> list[RoleDetailResponse]:
    """List all available roles with their permission sets."""
    return [_role_to_detail(role) for role in Role]


@router.get(
    "/roles/{role_name}",
    response_model=RoleDetailResponse,
    summary="Get role detail",
)
async def get_role(
    role_name: str,
    user: User = Depends(require_permissions("system:admin")),
) -> RoleDetailResponse:
    """Get a single role's detail with its full permission list."""
    try:
        role = Role(role_name)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role '{role_name}' not found. Valid roles: {[r.value for r in Role]}",
        ) from exc
    return _role_to_detail(role)


# ============================================================================
# Stats endpoint
# ============================================================================


@router.get(
    "/stats",
    response_model=AdminStatsResponse,
    summary="Admin dashboard statistics",
)
async def get_admin_stats(
    user: User = Depends(require_permissions("system:admin")),
    db: Session = Depends(get_db),
) -> AdminStatsResponse:
    """Get aggregate stats: user counts, tenant counts, last sync times."""
    svc = AdminService(db)
    data = svc.get_admin_stats()
    return AdminStatsResponse(**data)


# ============================================================================
# One-off data seed endpoint (staging cold-start helper)
# ============================================================================


class SeedResponse(BaseModel):
    """Result of a one-off seed operation."""

    seeded: bool
    message: str
    rows: dict[str, int]


@router.post(
    "/seed",
    response_model=SeedResponse,
    summary="Seed demo data if tables are empty",
)
async def post_admin_seed(
    user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
) -> SeedResponse:
    """Populate the local SQLite database with demo data for all dashboards.

    Idempotent: safe to call multiple times — existing rows are skipped
    by composite key (tenant_id + snapshot_date). Protected behind admin
    role so it cannot be triggered by unauthenticated callers.

    *Intended for staging cold-starts only.*  Production databases should
    never be seeded via this endpoint.
    """
    from app.models.compliance import ComplianceSnapshot
    from app.models.cost import CostSnapshot
    from app.models.identity import IdentitySnapshot
    from app.models.resource import Resource
    from app.models.tenant import Tenant

    # Fast guard: if CostSnapshot has rows, the DB is already seeded.
    existing_cost = db.query(CostSnapshot).count()
    if existing_cost > 0:
        return SeedResponse(
            seeded=False,
            message="Database already seeded (CostSnapshot has rows).",
            rows={
                "cost_snapshots": existing_cost,
                "compliance_snapshots": db.query(ComplianceSnapshot).count(),
                "identity_snapshots": db.query(IdentitySnapshot).count(),
                "resources": db.query(Resource).count(),
                "tenants": db.query(Tenant).count(),
            },
        )

    try:
        # Only perform heavy import when actually seeding
        import subprocess
        import sys

        # Run the existing seed_data.py CLI in-process
        # This reuses the same SQLAlchemy models and inserts via SessionLocal
        result = subprocess.run(
            [sys.executable, "scripts/seed_data.py", "--yes"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

        if result.returncode != 0:
            logger.error(f"seed_data.py failed: {result.stderr}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Seed script failed: {result.stderr[:200]}",
            )

        db.invalidate()  # Refresh session after external inserts

        return SeedResponse(
            seeded=True,
            message="Demo data seeded successfully. Refresh the dashboard.",
            rows={
                "cost_snapshots": db.query(CostSnapshot).count(),
                "compliance_snapshots": db.query(ComplianceSnapshot).count(),
                "identity_snapshots": db.query(IdentitySnapshot).count(),
                "resources": db.query(Resource).count(),
                "tenants": db.query(Tenant).count(),
            },
        )

    except TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Seed script timed out after 60s.",
        ) from None
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error during admin seed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {exc}",
        ) from exc

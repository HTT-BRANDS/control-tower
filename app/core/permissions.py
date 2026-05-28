"""Permission constants and role definitions for granular RBAC.

Implements ADR-0011: Code-defined roles with ``resource:action`` permission
strings.  Permission resolution is purely server-side from ``user.roles`` —
no database queries, no external dependencies.

Architecture layer::

    Request → Auth (JWT) → Tenant Isolation → **Permission Check** → Handler

Usage::

    from app.core.permissions import has_permission, get_all_permissions

    if has_permission(user.roles, "costs:read"):
        ...

See also:
    - ``app/core/rbac.py`` — FastAPI dependencies that use these helpers.
    - ``docs/decisions/adr-0011-granular-rbac.md`` — design rationale.
"""

from __future__ import annotations

import logging
from enum import StrEnum
from typing import Final

logger = logging.getLogger(__name__)


# ============================================================================
# Permission String Constants  (resource:action format — all lowercase)
# ============================================================================

# -- Dashboard ---------------------------------------------------------------
DASHBOARD_READ: Final[str] = "dashboard:read"

# -- Costs -------------------------------------------------------------------
COSTS_READ: Final[str] = "costs:read"
COSTS_EXPORT: Final[str] = "costs:export"
COSTS_MANAGE: Final[str] = "costs:manage"

# -- Compliance --------------------------------------------------------------
COMPLIANCE_READ: Final[str] = "compliance:read"
COMPLIANCE_WRITE: Final[str] = "compliance:write"
COMPLIANCE_MANAGE: Final[str] = "compliance:manage"

# -- Resources ---------------------------------------------------------------
RESOURCES_READ: Final[str] = "resources:read"
RESOURCES_EXPORT: Final[str] = "resources:export"
RESOURCES_MANAGE: Final[str] = "resources:manage"

# -- Identity ----------------------------------------------------------------
IDENTITY_READ: Final[str] = "identity:read"
IDENTITY_EXPORT: Final[str] = "identity:export"
IDENTITY_MANAGE: Final[str] = "identity:manage"

# -- Audit Logs --------------------------------------------------------------
AUDIT_LOGS_READ: Final[str] = "audit_logs:read"
AUDIT_LOGS_EXPORT: Final[str] = "audit_logs:export"

# -- Sync --------------------------------------------------------------------
SYNC_READ: Final[str] = "sync:read"
SYNC_TRIGGER: Final[str] = "sync:trigger"
SYNC_MANAGE: Final[str] = "sync:manage"

# -- Tenants -----------------------------------------------------------------
TENANTS_READ: Final[str] = "tenants:read"
TENANTS_MANAGE: Final[str] = "tenants:manage"

# -- Users -------------------------------------------------------------------
USERS_READ: Final[str] = "users:read"
USERS_MANAGE: Final[str] = "users:manage"

# -- System ------------------------------------------------------------------
SYSTEM_HEALTH: Final[str] = "system:health"
SYSTEM_ADMIN: Final[str] = "system:admin"

# -- Riverside ---------------------------------------------------------------
RIVERSIDE_READ: Final[str] = "riverside:read"
RIVERSIDE_MANAGE: Final[str] = "riverside:manage"

# -- DMARC -------------------------------------------------------------------
DMARC_READ: Final[str] = "dmarc:read"
DMARC_MANAGE: Final[str] = "dmarc:manage"

# -- Preflight ---------------------------------------------------------------
PREFLIGHT_READ: Final[str] = "preflight:read"
PREFLIGHT_RUN: Final[str] = "preflight:run"

# -- Budgets -----------------------------------------------------------------
BUDGETS_READ: Final[str] = "budgets:read"
BUDGETS_MANAGE: Final[str] = "budgets:manage"

# -- Recommendations ---------------------------------------------------------
RECOMMENDATIONS_READ: Final[str] = "recommendations:read"

# -- Franchise Coach (cross-brand insights for franchise leadership) ---------
FRANCHISE_COACH_READ: Final[str] = "franchise_coach:read"
FRANCHISE_COACH_EXPORT: Final[str] = "franchise_coach:export"

# -- Monitoring --------------------------------------------------------------
MONITORING_READ: Final[str] = "monitoring:read"
MONITORING_MANAGE: Final[str] = "monitoring:manage"

# -- Wildcard (admin-only) ---------------------------------------------------
WILDCARD_PERMISSION: Final[str] = "*"


# ============================================================================
# Complete Permission Registry
# ============================================================================

ALL_PERMISSIONS: Final[frozenset[str]] = frozenset(
    {
        DASHBOARD_READ,
        # Costs
        COSTS_READ,
        COSTS_EXPORT,
        COSTS_MANAGE,
        # Compliance
        COMPLIANCE_READ,
        COMPLIANCE_WRITE,
        COMPLIANCE_MANAGE,
        # Resources
        RESOURCES_READ,
        RESOURCES_EXPORT,
        RESOURCES_MANAGE,
        # Identity
        IDENTITY_READ,
        IDENTITY_EXPORT,
        IDENTITY_MANAGE,
        # Audit Logs
        AUDIT_LOGS_READ,
        AUDIT_LOGS_EXPORT,
        # Sync
        SYNC_READ,
        SYNC_TRIGGER,
        SYNC_MANAGE,
        # Tenants
        TENANTS_READ,
        TENANTS_MANAGE,
        # Users
        USERS_READ,
        USERS_MANAGE,
        # System
        SYSTEM_HEALTH,
        SYSTEM_ADMIN,
        # Riverside
        RIVERSIDE_READ,
        RIVERSIDE_MANAGE,
        # DMARC
        DMARC_READ,
        DMARC_MANAGE,
        # Preflight
        PREFLIGHT_READ,
        PREFLIGHT_RUN,
        # Budgets
        BUDGETS_READ,
        BUDGETS_MANAGE,
        # Recommendations
        RECOMMENDATIONS_READ,
        # Monitoring
        MONITORING_READ,
        MONITORING_MANAGE,
    }
)


# ============================================================================
# Role Definitions
# ============================================================================


class Role(StrEnum):
    """Application roles matching Entra ID App Roles.

    Containment hierarchy: ``VIEWER ⊂ ANALYST ⊂ MANAGER ⊂ TENANT_ADMIN ⊂ ADMIN``

    ``MANAGER`` is the franchise-leadership tier: cross-brand insight access
    plus exports, but no write/manage capability. Designed to equip franchise
    executives to have data-driven conversations with brand operators.
    See: docs/decisions/adr-0012-manager-role-franchise-coach.md
    """

    ADMIN = "admin"
    TENANT_ADMIN = "tenant_admin"
    MANAGER = "manager"
    ANALYST = "analyst"
    VIEWER = "viewer"


# ============================================================================
# Role → Permission Mappings  (immutable frozen sets)
# ============================================================================

# Viewer: read-only dashboard access — no exports, no writes.
_VIEWER_PERMISSIONS: Final[frozenset[str]] = frozenset(
    {
        DASHBOARD_READ,
        COSTS_READ,
        COMPLIANCE_READ,
        RESOURCES_READ,
        IDENTITY_READ,
        AUDIT_LOGS_READ,
        SYNC_READ,
        TENANTS_READ,
        USERS_READ,
        RIVERSIDE_READ,
        DMARC_READ,
        PREFLIGHT_READ,
        BUDGETS_READ,
        RECOMMENDATIONS_READ,
        MONITORING_READ,
    }
)

# Analyst: Viewer + export capabilities across accessible modules.
_ANALYST_PERMISSIONS: Final[frozenset[str]] = _VIEWER_PERMISSIONS | frozenset(
    {
        COSTS_EXPORT,
        RESOURCES_EXPORT,
        IDENTITY_EXPORT,
        AUDIT_LOGS_EXPORT,
    }
)

# Manager (Franchise Coach): Analyst + cross-brand insight view.
# Designed for franchise leadership coaching conversations with brand operators.
# Read-only by design — Managers surface conversations, not configuration changes.
_MANAGER_PERMISSIONS: Final[frozenset[str]] = _ANALYST_PERMISSIONS | frozenset(
    {
        FRANCHISE_COACH_READ,
        FRANCHISE_COACH_EXPORT,
    }
)

# Tenant Admin: Analyst + manage/write/trigger/run
# EXCEPT system:admin and tenants:manage (those are admin-only).
_TENANT_ADMIN_PERMISSIONS: Final[frozenset[str]] = _ANALYST_PERMISSIONS | frozenset(
    {
        COSTS_MANAGE,
        COMPLIANCE_WRITE,
        COMPLIANCE_MANAGE,
        RESOURCES_MANAGE,
        IDENTITY_MANAGE,
        SYNC_TRIGGER,
        SYNC_MANAGE,
        USERS_MANAGE,
        RIVERSIDE_MANAGE,
        DMARC_MANAGE,
        PREFLIGHT_RUN,
        BUDGETS_MANAGE,
        MONITORING_MANAGE,
        SYSTEM_HEALTH,
    }
)

# Admin: wildcard — grants every permission, checked specially in has_permission().
_ADMIN_PERMISSIONS: Final[frozenset[str]] = frozenset({"*"})


# Public mapping — used by fitness tests and resolution functions.
ROLE_PERMISSIONS: Final[dict[Role, frozenset[str]]] = {
    Role.ADMIN: _ADMIN_PERMISSIONS,
    Role.TENANT_ADMIN: _TENANT_ADMIN_PERMISSIONS,
    Role.MANAGER: _MANAGER_PERMISSIONS,
    Role.ANALYST: _ANALYST_PERMISSIONS,
    Role.VIEWER: _VIEWER_PERMISSIONS,
}


# ============================================================================
# Legacy Role Mapping (backward compatibility — ADR-0011 §Legacy Role Mapping)
# ============================================================================

LEGACY_ROLE_MAP: Final[dict[str, str]] = {
    "admin": "admin",
    "operator": "tenant_admin",
    "manager": "manager",
    "reader": "viewer",
    "user": "viewer",
}


# ============================================================================
# Permission Resolution Functions
# ============================================================================


def _resolve_role(role: str) -> str:
    """Resolve a role string, applying legacy mapping if needed."""
    return LEGACY_ROLE_MAP.get(role, role)


def get_permissions_for_role(role: str) -> frozenset[str]:
    """Get the permission set for a single role.

    Applies legacy role mapping automatically.
    Unknown roles return an empty frozenset (fail-closed).

    Args:
        role: Role name (e.g., ``"viewer"``, ``"operator"``).

    Returns:
        Frozen set of permission strings for the role.
    """
    resolved = _resolve_role(role)
    try:
        role_enum = Role(resolved)
    except ValueError:
        logger.warning(
            "Unknown role '%s' (resolved: '%s') — granting zero permissions",
            role,
            resolved,
        )
        return frozenset()
    return ROLE_PERMISSIONS.get(role_enum, frozenset())


def get_all_permissions(roles: list[str]) -> frozenset[str]:
    """Resolve the complete permission set from a list of role strings.

    Accumulates permissions from all roles.  Applies legacy mapping.

    Args:
        roles: List of role names from ``user.roles``.

    Returns:
        Union of all permission sets for the given roles.
    """
    permissions: set[str] = set()
    for role in roles:
        permissions |= get_permissions_for_role(role)
    return frozenset(permissions)


def has_permission(user_roles: list[str], permission: str) -> bool:
    """Check if a user with the given roles has a specific permission.

    Handles wildcard admin access: if any role resolves to ``ADMIN``,
    all permissions are granted.

    Args:
        user_roles: List of role names from ``user.roles``.
        permission: The permission string to check (e.g., ``"costs:read"``).

    Returns:
        ``True`` if the user has the permission, ``False`` otherwise.
    """
    all_perms = get_all_permissions(user_roles)
    # Wildcard check — admin has everything
    if WILDCARD_PERMISSION in all_perms:
        return True
    return permission in all_perms

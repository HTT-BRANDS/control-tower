# Recommendations — RBAC Implementation for Azure Governance Platform

## Overview

This document provides a concrete, copy-paste-ready implementation plan for adding granular RBAC to the Azure Governance Platform. The approach is designed to be:

- **Non-breaking**: Existing `require_roles()` continues to work
- **Incremental**: Routes migrate one at a time
- **Testable**: Permission sets are frozen sets, trivially unit-testable
- **Zero-dependency**: No new libraries — uses FastAPI's built-in patterns

---

## Implementation Step 1: Permission & Role Registry

Create a new file `app/core/permissions.py`:

```python
"""Permission and role definitions for RBAC.

This module defines the canonical permission strings and role-to-permission
mappings for the Azure Governance Platform. Permissions follow the
"resource:action" format (OAuth2 scope convention).

Roles are predefined as frozen sets of permission strings. This keeps
role definitions version-controlled, testable, and avoids DB queries
on every request.

Usage:
    from app.core.permissions import Role, ROLE_PERMISSIONS, has_permission

    # Check if a role has a specific permission
    if has_permission(Role.ANALYST, "costs:read"):
        ...

    # Get all permissions for a user's roles
    perms = resolve_user_permissions(user)
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.auth import User


# =============================================================================
# Permission String Registry
# =============================================================================
# All valid permission strings. Used for validation at startup to catch typos.
# Format: "resource:action"

class Permission(str, Enum):
    """Canonical permission strings.
    
    Using an enum prevents typos — if you reference a non-existent
    permission, you'll get an AttributeError at import time.
    """
    
    # Dashboard
    DASHBOARD_READ = "dashboard:read"
    
    # Cost Management
    COSTS_READ = "costs:read"
    COSTS_EXPORT = "costs:export"
    COSTS_MANAGE = "costs:manage"
    
    # Compliance
    COMPLIANCE_READ = "compliance:read"
    COMPLIANCE_WRITE = "compliance:write"
    COMPLIANCE_MANAGE = "compliance:manage"
    
    # Resources
    RESOURCES_READ = "resources:read"
    RESOURCES_EXPORT = "resources:export"
    RESOURCES_MANAGE = "resources:manage"
    
    # Identity
    IDENTITY_READ = "identity:read"
    IDENTITY_EXPORT = "identity:export"
    IDENTITY_MANAGE = "identity:manage"
    
    # Audit Logs
    AUDIT_LOGS_READ = "audit_logs:read"
    AUDIT_LOGS_EXPORT = "audit_logs:export"
    
    # Sync / Data Pipeline
    SYNC_READ = "sync:read"
    SYNC_TRIGGER = "sync:trigger"
    SYNC_MANAGE = "sync:manage"
    
    # Tenant Management
    TENANTS_READ = "tenants:read"
    TENANTS_MANAGE = "tenants:manage"
    
    # User Management
    USERS_READ = "users:read"
    USERS_MANAGE = "users:manage"
    
    # System
    SYSTEM_HEALTH = "system:health"
    SYSTEM_ADMIN = "system:admin"
    
    # Riverside Module
    RIVERSIDE_READ = "riverside:read"
    RIVERSIDE_MANAGE = "riverside:manage"
    
    # DMARC Module
    DMARC_READ = "dmarc:read"
    DMARC_MANAGE = "dmarc:manage"
    
    # Preflight
    PREFLIGHT_READ = "preflight:read"
    PREFLIGHT_RUN = "preflight:run"
    
    # Budgets
    BUDGETS_READ = "budgets:read"
    BUDGETS_MANAGE = "budgets:manage"
    
    # Recommendations
    RECOMMENDATIONS_READ = "recommendations:read"
    
    # Monitoring
    MONITORING_READ = "monitoring:read"
    MONITORING_MANAGE = "monitoring:manage"


# Wildcard — only for Admin role
WILDCARD_PERMISSION = "*"


# =============================================================================
# Role Definitions
# =============================================================================

class Role(str, Enum):
    """Application roles.
    
    These map 1:1 to Entra ID App Roles defined in the
    App Registration manifest.
    """
    ADMIN = "admin"
    TENANT_ADMIN = "tenant_admin"
    ANALYST = "analyst"
    VIEWER = "viewer"
    # Legacy roles (mapped to new roles during transition)
    OPERATOR = "operator"       # → TENANT_ADMIN
    READER = "reader"           # → VIEWER
    USER = "user"               # → VIEWER


# =============================================================================
# Role → Permission Mappings
# =============================================================================

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    Role.ADMIN: frozenset({WILDCARD_PERMISSION}),
    
    Role.TENANT_ADMIN: frozenset({
        Permission.DASHBOARD_READ,
        Permission.COSTS_READ, Permission.COSTS_EXPORT, Permission.COSTS_MANAGE,
        Permission.COMPLIANCE_READ, Permission.COMPLIANCE_WRITE, Permission.COMPLIANCE_MANAGE,
        Permission.RESOURCES_READ, Permission.RESOURCES_EXPORT, Permission.RESOURCES_MANAGE,
        Permission.IDENTITY_READ, Permission.IDENTITY_EXPORT, Permission.IDENTITY_MANAGE,
        Permission.AUDIT_LOGS_READ, Permission.AUDIT_LOGS_EXPORT,
        Permission.SYNC_READ, Permission.SYNC_TRIGGER,
        Permission.TENANTS_READ,
        Permission.USERS_READ, Permission.USERS_MANAGE,
        Permission.SYSTEM_HEALTH,
        Permission.RIVERSIDE_READ, Permission.RIVERSIDE_MANAGE,
        Permission.DMARC_READ, Permission.DMARC_MANAGE,
        Permission.PREFLIGHT_READ, Permission.PREFLIGHT_RUN,
        Permission.BUDGETS_READ, Permission.BUDGETS_MANAGE,
        Permission.RECOMMENDATIONS_READ,
        Permission.MONITORING_READ, Permission.MONITORING_MANAGE,
    }),
    
    Role.ANALYST: frozenset({
        Permission.DASHBOARD_READ,
        Permission.COSTS_READ, Permission.COSTS_EXPORT,
        Permission.COMPLIANCE_READ,
        Permission.RESOURCES_READ, Permission.RESOURCES_EXPORT,
        Permission.IDENTITY_READ, Permission.IDENTITY_EXPORT,
        Permission.AUDIT_LOGS_READ,
        Permission.SYNC_READ,
        Permission.TENANTS_READ,
        Permission.SYSTEM_HEALTH,
        Permission.RIVERSIDE_READ,
        Permission.DMARC_READ,
        Permission.PREFLIGHT_READ,
        Permission.BUDGETS_READ,
        Permission.RECOMMENDATIONS_READ,
        Permission.MONITORING_READ,
    }),
    
    Role.VIEWER: frozenset({
        Permission.DASHBOARD_READ,
        Permission.COSTS_READ,
        Permission.COMPLIANCE_READ,
        Permission.RESOURCES_READ,
        Permission.IDENTITY_READ,
        Permission.SYNC_READ,
        Permission.TENANTS_READ,
        Permission.SYSTEM_HEALTH,
        Permission.RIVERSIDE_READ,
        Permission.DMARC_READ,
        Permission.PREFLIGHT_READ,
        Permission.BUDGETS_READ,
        Permission.RECOMMENDATIONS_READ,
        Permission.MONITORING_READ,
    }),
    
    # Legacy role mappings
    Role.OPERATOR: frozenset(),   # Resolved by mapping to TENANT_ADMIN
    Role.READER: frozenset(),     # Resolved by mapping to VIEWER
    Role.USER: frozenset(),       # Resolved by mapping to VIEWER
}

# Legacy role → new role mapping (for transition period)
LEGACY_ROLE_MAP: dict[str, str] = {
    "operator": Role.TENANT_ADMIN,
    "reader": Role.VIEWER,
    "user": Role.VIEWER,
}


# =============================================================================
# Permission Resolution Functions
# =============================================================================

def resolve_role_permissions(role_name: str) -> frozenset[str]:
    """Get the permission set for a single role name.
    
    Handles legacy role names by mapping them to new roles.
    """
    # Map legacy roles
    mapped_role = LEGACY_ROLE_MAP.get(role_name, role_name)
    return ROLE_PERMISSIONS.get(mapped_role, frozenset())


def resolve_user_permissions(user: "User") -> set[str]:
    """Resolve all permissions for a user based on their roles.
    
    Unions all permission sets from all of the user's roles.
    Returns a mutable set for potential per-tenant augmentation.
    """
    permissions: set[str] = set()
    for role in user.roles:
        permissions.update(resolve_role_permissions(role))
    return permissions


def has_permission(permissions: set[str], required: str) -> bool:
    """Check if a permission set includes a required permission.
    
    Handles wildcard (*) — admin has all permissions.
    """
    if WILDCARD_PERMISSION in permissions:
        return True
    return required in permissions


def has_any_permission(permissions: set[str], required: list[str]) -> bool:
    """Check if a permission set includes ANY of the required permissions."""
    if WILDCARD_PERMISSION in permissions:
        return True
    return bool(permissions.intersection(required))


def has_all_permissions(permissions: set[str], required: list[str]) -> bool:
    """Check if a permission set includes ALL required permissions."""
    if WILDCARD_PERMISSION in permissions:
        return True
    return set(required).issubset(permissions)
```

---

## Implementation Step 2: Permission-Checking Dependencies

Add to `app/core/auth.py` or create `app/core/rbac.py`:

```python
"""RBAC enforcement dependencies for FastAPI routes.

Usage in routes:
    from app.core.rbac import require_permissions

    @router.get("/costs")
    async def get_costs(
        user: User = Depends(require_permissions(["costs:read"])),
    ):
        ...
    
    # Require ANY of the listed permissions
    @router.post("/costs/export")
    async def export_costs(
        user: User = Depends(require_permissions(
            ["costs:export", "costs:manage"], 
            require_all=False,
        )),
    ):
        ...
"""

import logging
from typing import Any

from fastapi import Depends, HTTPException, status

from app.core.auth import User, get_current_user
from app.core.permissions import (
    Permission,
    has_all_permissions,
    has_any_permission,
    resolve_user_permissions,
)

logger = logging.getLogger(__name__)

# Valid permission strings for startup validation
_VALID_PERMISSIONS = {p.value for p in Permission}


def require_permissions(
    required: list[str],
    require_all: bool = True,
):
    """FastAPI dependency factory: require specific permissions.
    
    Args:
        required: List of permission strings (e.g., ["costs:read"])
        require_all: If True, ALL permissions required. If False, ANY suffices.
    
    Usage:
        @router.get("/costs")
        async def get_costs(
            user: User = Depends(require_permissions(["costs:read"])),
        ):
            ...
    
    Raises ValueError at import time if invalid permission strings are used.
    """
    # Validate permission strings at route registration time (fail fast)
    for perm in required:
        if perm not in _VALID_PERMISSIONS:
            raise ValueError(
                f"Invalid permission '{perm}'. "
                f"Valid permissions: {sorted(_VALID_PERMISSIONS)}"
            )
    
    async def permission_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        user_perms = resolve_user_permissions(current_user)
        
        if require_all:
            granted = has_all_permissions(user_perms, required)
        else:
            granted = has_any_permission(user_perms, required)
        
        if not granted:
            logger.warning(
                f"Permission denied: user={current_user.id}, "
                f"required={required}, had={sorted(user_perms)}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {', '.join(required)}",
            )
        
        return current_user
    
    return permission_checker


def require_any_permission(*permissions: str):
    """Convenience: require ANY of the listed permissions.
    
    Usage:
        @router.get("/data")
        async def get_data(
            user: User = Depends(require_any_permission(
                "costs:read", "resources:read"
            )),
        ):
            ...
    """
    return require_permissions(list(permissions), require_all=False)
```

---

## Implementation Step 3: Update User Model

Add a computed `permissions` property to the existing `User` model in `app/core/auth.py`:

```python
class User(BaseModel):
    """Authenticated user model."""
    
    id: str
    email: str | None = None
    name: str | None = None
    roles: list[str] = []
    tenant_ids: list[str] = []
    personas: list[str] = []
    is_active: bool = True
    auth_provider: str = "internal"
    
    # --- Existing methods (unchanged) ---
    
    def has_role(self, role: str) -> bool:
        """Check if user has a specific role."""
        return role in self.roles or "admin" in self.roles
    
    def has_access_to_tenant(self, tenant_id: str) -> bool:
        """Check tenant access. Fails closed."""
        if "admin" in self.roles:
            return True
        if not self.tenant_ids:
            return False
        return tenant_id in self.tenant_ids
    
    # --- New permission methods ---
    
    @property
    def permissions(self) -> set[str]:
        """Resolve permission set from roles. Cached per request."""
        if not hasattr(self, "_permissions_cache"):
            from app.core.permissions import resolve_user_permissions
            object.__setattr__(self, "_permissions_cache", 
                             resolve_user_permissions(self))
        return self._permissions_cache
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        from app.core.permissions import has_permission
        return has_permission(self.permissions, permission)
```

---

## Implementation Step 4: Azure AD App Roles Integration

### 4a. Define App Roles in Entra ID App Registration Manifest

In the Azure Portal → App Registration → App roles, create:

| Display Name | Value | Description | Member Types |
|-------------|-------|-------------|--------------|
| Admin | `admin` | Full system administrator | Users/Groups |
| Tenant Admin | `tenant_admin` | Tenant-level administrator | Users/Groups |
| Analyst | `analyst` | Read + export access | Users/Groups |
| Viewer | `viewer` | Read-only access | Users/Groups |

These values will appear in the `roles` claim of the JWT token.

### 4b. Update Token Validation

Update `_map_groups_to_roles()` in `app/core/auth.py` to use the `roles` claim directly:

```python
async def validate_token(self, token: str) -> TokenData:
    """Validate an Azure AD JWT token."""
    # ... existing validation code ...
    
    # CHANGED: Use 'roles' claim directly (from App Roles)
    # instead of mapping from 'groups' claim
    app_roles = payload.get("roles", [])
    if isinstance(app_roles, str):
        app_roles = [app_roles]
    
    # Fall back to group-based mapping for backward compatibility
    groups = payload.get("groups", [])
    mapped_roles = self._map_groups_to_roles(groups) if groups else []
    
    # Merge: app roles take precedence
    all_roles = list(set(app_roles + mapped_roles))
    if not all_roles:
        all_roles = ["viewer"]  # Default role
    
    return TokenData(
        sub=user_id,
        email=email,
        name=name,
        roles=all_roles,  # Now from 'roles' claim
        tenant_ids=self._extract_tenant_ids_from_groups(groups),
        personas=resolve_personas(groups),
        azure_tenant_id=azure_tenant_id,
        # ... rest unchanged ...
    )
```

---

## Implementation Step 5: Route Migration Examples

### Before (Current Pattern)

```python
@router.get("/costs")
async def get_costs(
    user: User = Depends(require_roles(["admin", "operator", "reader"])),
):
    ...

@router.post("/sync/trigger")
async def trigger_sync(
    user: User = Depends(require_roles(["admin", "operator"])),
):
    ...
```

### After (RBAC Pattern)

```python
from app.core.rbac import require_permissions

@router.get("/costs")
async def get_costs(
    user: User = Depends(require_permissions(["costs:read"])),
):
    ...

@router.post("/sync/trigger")
async def trigger_sync(
    user: User = Depends(require_permissions(["sync:trigger"])),
):
    ...
```

### Migration of UserTenant Boolean Flags

**Before**: `UserTenant.can_manage_resources`, `can_view_costs`, `can_manage_compliance`

**After**: These are replaced by the user's role within the tenant:

```python
# Old pattern
if user_tenant.can_manage_resources:
    ...

# New pattern — check user's tenant-scoped permissions
user_perms = resolve_user_permissions(user)
if has_permission(user_perms, "resources:manage"):
    ...
```

The boolean flags become unnecessary once permissions are resolved from roles. They can be kept during transition and deprecated later.

---

## Implementation Step 6: Testing

```python
"""Tests for RBAC permission system."""

import pytest
from app.core.permissions import (
    Permission,
    Role,
    ROLE_PERMISSIONS,
    has_permission,
    has_all_permissions,
    has_any_permission,
    resolve_role_permissions,
    resolve_user_permissions,
    WILDCARD_PERMISSION,
)


class TestPermissionStrings:
    """Verify permission string registry integrity."""
    
    def test_all_permissions_use_colon_format(self):
        for p in Permission:
            assert ":" in p.value, f"Permission {p.name} missing colon: {p.value}"
    
    def test_no_spaces_in_permissions(self):
        for p in Permission:
            assert " " not in p.value, f"Permission {p.name} has spaces"
    
    def test_all_permissions_lowercase(self):
        for p in Permission:
            assert p.value == p.value.lower(), f"Permission {p.name} not lowercase"


class TestRoleHierarchy:
    """Verify role permission containment."""
    
    def test_admin_has_wildcard(self):
        assert WILDCARD_PERMISSION in ROLE_PERMISSIONS[Role.ADMIN]
    
    def test_viewer_is_subset_of_analyst(self):
        viewer_perms = ROLE_PERMISSIONS[Role.VIEWER]
        analyst_perms = ROLE_PERMISSIONS[Role.ANALYST]
        assert viewer_perms.issubset(analyst_perms), (
            f"Viewer has permissions not in Analyst: "
            f"{viewer_perms - analyst_perms}"
        )
    
    def test_analyst_is_subset_of_tenant_admin(self):
        analyst_perms = ROLE_PERMISSIONS[Role.ANALYST]
        ta_perms = ROLE_PERMISSIONS[Role.TENANT_ADMIN]
        assert analyst_perms.issubset(ta_perms), (
            f"Analyst has permissions not in TenantAdmin: "
            f"{analyst_perms - ta_perms}"
        )
    
    def test_viewer_cannot_write(self):
        viewer_perms = ROLE_PERMISSIONS[Role.VIEWER]
        write_perms = {p for p in viewer_perms if ":write" in p or ":manage" in p}
        assert not write_perms, f"Viewer has write permissions: {write_perms}"
    
    def test_viewer_cannot_export(self):
        viewer_perms = ROLE_PERMISSIONS[Role.VIEWER]
        export_perms = {p for p in viewer_perms if ":export" in p}
        assert not export_perms, f"Viewer has export permissions: {export_perms}"


class TestPermissionChecking:
    
    def test_wildcard_grants_everything(self):
        perms = {"*"}
        assert has_permission(perms, "costs:read")
        assert has_permission(perms, "system:admin")
        assert has_permission(perms, "anything:at_all")
    
    def test_specific_permission_check(self):
        perms = {"costs:read", "costs:export"}
        assert has_permission(perms, "costs:read")
        assert has_permission(perms, "costs:export")
        assert not has_permission(perms, "costs:manage")
    
    def test_has_any_permission(self):
        perms = {"costs:read"}
        assert has_any_permission(perms, ["costs:read", "costs:manage"])
        assert not has_any_permission(perms, ["costs:manage", "costs:export"])
    
    def test_has_all_permissions(self):
        perms = {"costs:read", "costs:export"}
        assert has_all_permissions(perms, ["costs:read", "costs:export"])
        assert not has_all_permissions(perms, ["costs:read", "costs:manage"])


class TestLegacyRoleMapping:
    
    def test_operator_maps_to_tenant_admin(self):
        perms = resolve_role_permissions("operator")
        ta_perms = resolve_role_permissions("tenant_admin")
        assert perms == ta_perms
    
    def test_reader_maps_to_viewer(self):
        perms = resolve_role_permissions("reader")
        viewer_perms = resolve_role_permissions("viewer")
        assert perms == viewer_perms
```

---

## Relationship to Existing Concepts

### Permissions vs Personas vs Roles

| Concept | Purpose | Where Defined | Example |
|---------|---------|--------------|---------|
| **Role** | Authorization — what can you DO | JWT `roles` claim / UserTenant | `admin`, `analyst` |
| **Permission** | Granular authorization check | Resolved from Role | `costs:read`, `sync:trigger` |
| **Persona** | UI gating — what can you SEE | Entra ID groups → `config/personas.yaml` | `it_admin`, `finance` |
| **Tenant Access** | Data isolation — WHICH data | UserTenant / token `tenant_ids` | `tenant-123` |

These are **orthogonal** concerns that compose together:

```
Can user X do action Y on tenant Z?
  = user has permission Y (from roles)
  AND user has access to tenant Z (from tenant mappings)
  
Should user X see nav section W?
  = user has persona W (from groups)
  OR user is admin (bypass)
```

---

## Timeline & Effort Estimate

| Phase | Tasks | Effort | Risk |
|-------|-------|--------|------|
| **Phase 1** (Week 1) | Create `permissions.py`, `rbac.py`, tests | 6 hours | Low |
| **Phase 2** (Week 2) | Add `permissions` property to User, update token handling | 3 hours | Low |
| **Phase 3** (Weeks 3-4) | Migrate routes from `require_roles` → `require_permissions` | 8 hours | Medium |
| **Phase 4** (Week 5) | Define Entra ID App Roles, update token validation | 4 hours | Low |
| **Phase 5** (Optional) | Deprecate UserTenant boolean flags, add per-tenant role overrides | 4 hours | Low |

**Total**: ~25 hours across 5 weeks for full migration.

---

## What NOT to Do

1. **Don't use PyCasbin** — it's a powerful policy engine but massive overkill for 4 roles × 5 tenants. The learning curve and operational complexity aren't justified.

2. **Don't store permissions in JWT tokens** — resolve them server-side from roles. Token bloat and inability to revoke permissions immediately are real problems.

3. **Don't use `fastapi-permissions`** — it's effectively unmaintained (last significant update ~2022) and focused on row-level ACL, not role-based permissions.

4. **Don't build a database-driven role editor** — for 4 predefined roles, code-defined permission sets are simpler, safer, and more testable. A DB-driven system only makes sense if you need per-customer custom roles (you don't, with 5 tenants).

5. **Don't try to replace everything at once** — the phased migration ensures zero downtime and allows testing each step.

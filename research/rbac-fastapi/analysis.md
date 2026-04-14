# Multi-Dimensional Analysis — RBAC for FastAPI Multi-Tenant Applications

## 1. Permission String Pattern Analysis

### Pattern Comparison

| Pattern | Example | Used By | Pros | Cons |
|---------|---------|---------|------|------|
| `resource:action` | `costs:read` | OAuth2, Azure, AWS | Simple, intuitive, grep-able | Flat — no hierarchy |
| `resource.action` | `Survey.Create` | Entra ID app roles | Dot notation familiar | Conflicts with Python attribute access |
| `resource:action:scope` | `costs:read:own` | Advanced RBAC | Supports ownership scopes | Over-engineering for small teams |
| `verb-resource` | `read-costs` | REST-style | Natural language | Harder to group by resource |
| URI-style | `/api/costs:GET` | RESTful ACL | Maps directly to routes | Brittle, tightly coupled |
| Hierarchical | `governance.costs.read` | Java JAAS | Tree-based inheritance | Complex, verbose |

### **Recommended: `resource:action` format**

**Why**: It's the OAuth2 standard format, used by FastAPI's built-in `SecurityScopes`, aligns with how Azure AD scopes work, and is simple enough for grep/search. The colon separator avoids conflicts with Python identifiers and URL components.

**Naming conventions**:
- Resources: plural nouns, snake_case → `costs`, `compliance`, `resources`, `identity`, `audit_logs`
- Actions: verbs → `read`, `write`, `delete`, `manage`, `export`
- Wildcard: `*` for all actions → `costs:*` (admin-level)

### Permission String Registry (Proposed for This Project)

```python
# Organized by module matching our route structure
PERMISSIONS = {
    # Dashboard
    "dashboard:read",
    
    # Cost Management
    "costs:read",
    "costs:export",
    "costs:manage",          # budgets, anomaly config
    
    # Compliance
    "compliance:read",
    "compliance:write",      # custom rules
    "compliance:manage",     # framework config
    
    # Resources
    "resources:read",
    "resources:export",
    "resources:manage",      # lifecycle, tagging
    
    # Identity
    "identity:read",
    "identity:export",
    "identity:manage",       # access reviews
    
    # Audit
    "audit_logs:read",
    "audit_logs:export",
    
    # Sync / Data Pipeline
    "sync:read",             # view sync status
    "sync:trigger",          # manually trigger syncs
    "sync:manage",           # configure sync schedules
    
    # Tenants
    "tenants:read",
    "tenants:manage",        # add/remove tenants, configure
    
    # Users / Roles
    "users:read",
    "users:manage",          # assign roles, manage access
    
    # System / Admin
    "system:health",         # health endpoints
    "system:admin",          # system-level configuration
    
    # Riverside (module-specific)
    "riverside:read",
    "riverside:manage",
    
    # DMARC
    "dmarc:read",
    "dmarc:manage",
    
    # Preflight
    "preflight:read",
    "preflight:run",
}
```

---

## 2. Role-Permission Mapping Approaches

### Approach A: Code-Defined Roles (RECOMMENDED)

Roles defined as frozen sets in Python — version-controlled, tested, no DB migration needed.

```python
from enum import Enum

class Role(str, Enum):
    ADMIN = "admin"
    TENANT_ADMIN = "tenant_admin"
    ANALYST = "analyst"
    VIEWER = "viewer"

ROLE_PERMISSIONS: dict[Role, frozenset[str]] = {
    Role.ADMIN: frozenset({"*"}),  # wildcard = all permissions
    
    Role.TENANT_ADMIN: frozenset({
        "dashboard:read",
        "costs:read", "costs:export", "costs:manage",
        "compliance:read", "compliance:write", "compliance:manage",
        "resources:read", "resources:export", "resources:manage",
        "identity:read", "identity:export", "identity:manage",
        "audit_logs:read", "audit_logs:export",
        "sync:read", "sync:trigger",
        "tenants:read",
        "users:read", "users:manage",
        "riverside:read", "riverside:manage",
        "dmarc:read", "dmarc:manage",
        "preflight:read", "preflight:run",
    }),
    
    Role.ANALYST: frozenset({
        "dashboard:read",
        "costs:read", "costs:export",
        "compliance:read",
        "resources:read", "resources:export",
        "identity:read", "identity:export",
        "audit_logs:read",
        "sync:read",
        "tenants:read",
        "riverside:read",
        "dmarc:read",
        "preflight:read",
    }),
    
    Role.VIEWER: frozenset({
        "dashboard:read",
        "costs:read",
        "compliance:read",
        "resources:read",
        "identity:read",
        "sync:read",
        "tenants:read",
        "riverside:read",
        "dmarc:read",
        "preflight:read",
    }),
}
```

**Pros**: Simple, testable, version-controlled, no DB queries, no migration needed, fast (set lookup).

**Cons**: Requires code deployment to change roles, no per-tenant customization without additional logic.

### Approach B: Database-Defined Roles

Roles and permissions stored in DB tables (Role, Permission, RolePermission).

**Pros**: Runtime-modifiable, per-tenant overrides possible, admin UI for role management.

**Cons**: Requires DB migration, more complex, cache invalidation needed, harder to test, risk of misconfiguration.

### Approach C: Hybrid (RECOMMENDED for Phase 2)

Code-defined defaults with optional per-tenant overrides in DB.

```python
def resolve_permissions(user: User, tenant_id: str, db: Session) -> set[str]:
    """Resolve permissions: code defaults + optional DB overrides."""
    # Start with role-based permissions
    perms = set()
    for role in user.roles:
        role_enum = Role(role) if role in Role.__members__.values() else None
        if role_enum:
            perms.update(ROLE_PERMISSIONS.get(role_enum, set()))
    
    # Check for per-tenant role override
    user_tenant = get_user_tenant(user.id, tenant_id, db)
    if user_tenant and user_tenant.role:
        tenant_role = Role(user_tenant.role)
        perms.update(ROLE_PERMISSIONS.get(tenant_role, set()))
    
    return perms
```

---

## 3. Security Analysis

| Aspect | Current State | With RBAC | Risk Level |
|--------|--------------|-----------|------------|
| **Least Privilege** | ❌ Coarse roles (admin/viewer) | ✅ Granular per-action | Improved |
| **Privilege Escalation** | ⚠️ Admin bypass in all checks | ⚠️ Still needed but auditable | Same |
| **Tenant Isolation** | ✅ TenantAuthorization class | ✅ Add permission scoping per tenant | Same |
| **Permission Creep** | ❌ No visibility into effective perms | ✅ Explicit permission sets | Improved |
| **Audit Trail** | ⚠️ Logs role, not specific permission | ✅ Log exact permission checked | Improved |
| **Token Size** | ⚠️ roles[] in JWT | ⚠️ Same — resolve perms server-side | Same |

### Security Recommendations

1. **Never embed permissions in JWT** — only embed role names. Resolve permissions server-side to avoid token bloat and allow immediate role changes.
2. **Wildcard `*` only for admin** — no other role should use wildcards.
3. **Deny by default** — if a permission isn't explicitly granted, it's denied.
4. **Log permission checks** — audit log should capture `(user, permission, resource, tenant, result)`.
5. **Validate permission strings** — use an enum or registry to prevent typos at deploy time.

---

## 4. Implementation Complexity Analysis

| Approach | Initial Effort | Ongoing Maintenance | Learning Curve | Dependencies |
|----------|---------------|--------------------|----|------|
| Code-defined roles + custom dependency | **Low** (4-6 hours) | **Low** | **Low** — standard FastAPI patterns | None |
| PyCasbin integration | **Medium** (8-12 hours) | **Medium** — policy file management | **Medium** — Casbin DSL | `pycasbin`, adapter |
| fastapi-permissions | **Medium** (6-8 hours) | **High** — unmaintained lib | **Medium** — Pyramid ACL concepts | `fastapi-permissions` |
| Database-driven RBAC | **High** (16-20 hours) | **Medium** — admin UI needed | **Low** | DB migration |
| FastAPI SecurityScopes only | **Low** (3-4 hours) | **Low** | **Low** | None |

---

## 5. Cost Analysis

| Solution | License | Infrastructure | Maintenance Hours/Year |
|----------|---------|---------------|----------------------|
| Custom code (recommended) | Free | None | ~4 hours |
| PyCasbin | Apache 2.0 (free) | None (or Redis for distributed) | ~8 hours |
| Commercial RBAC (Auth0, Permit.io) | $$$$ | SaaS dependency | ~2 hours |
| Database-driven custom | Free | DB table storage (negligible) | ~12 hours |

---

## 6. Compatibility Analysis

### With Existing Codebase

| Component | Compatibility | Migration Effort |
|-----------|--------------|-----------------|
| `User.roles: list[str]` | ✅ Keep as-is, add `permissions` property | None |
| `require_roles()` | ✅ Keep for backward compat, add `require_permissions()` | None |
| `TenantAuthorization` | ✅ Orthogonal — tenant isolation is separate from permissions | None |
| Personas | ✅ Orthogonal — UI gating is separate from authorization | None |
| `UserTenant.role` | ✅ Maps to per-tenant role override | Rename values |
| `UserTenant.can_*` booleans | ⚠️ Replaced by permission strings | Migration needed |
| Azure AD token validation | ✅ Map `roles` claim to Role enum | Update `_map_groups_to_roles()` |
| JWT internal tokens | ✅ Add `roles` to token, resolve perms server-side | Minor update |

### With Azure AD / Entra ID

The `roles` claim in Azure AD tokens maps cleanly to our Role enum:

```
Entra ID App Role "Admin"         → Role.ADMIN
Entra ID App Role "TenantAdmin"   → Role.TENANT_ADMIN
Entra ID App Role "Analyst"       → Role.ANALYST  
Entra ID App Role "Viewer"        → Role.VIEWER
```

This requires defining 4 app roles in the App Registration manifest.

---

## 7. Stability & Maintenance Analysis

| Solution | Maturity | Breaking Change Risk | Long-term Support | Vendor Lock-in |
|----------|---------|---------------------|-------------------|----------------|
| Custom code | N/A — our code | Full control | We maintain it | None |
| FastAPI SecurityScopes | Stable (core framework) | Low — official API | FastAPI team | Low |
| PyCasbin | Mature (Apache) | Medium — major versions | Apache Foundation | Low |
| fastapi-permissions | Declining | High — unmaintained | None | Medium |

---

## 8. Migration Strategy: Current → RBAC

### Current Auth Layers (What We Have)

```
Layer 1: Authentication (JWT/Azure AD tokens)
Layer 2: Global Roles (admin, operator, reader, user, viewer)
Layer 3: Tenant Access (TenantAuthorization, UserTenant)
Layer 4: Personas (UI-gating, not authorization)
Layer 5: Boolean Flags (can_manage_resources, can_view_costs, can_manage_compliance)
```

### Target Auth Layers (Where We're Going)

```
Layer 1: Authentication (unchanged)
Layer 2: Roles → Permissions (Role enum → permission sets)
Layer 3: Tenant Access + Tenant-Scoped Roles (unchanged, enhanced)
Layer 4: Personas (unchanged — separate concern)
Layer 5: Permission Checking (replaces boolean flags)
```

### Migration Phases

**Phase 1: Foundation (Non-Breaking)**
- Define `Permission` enum/registry and `Role` enum
- Define `ROLE_PERMISSIONS` mapping
- Add `require_permissions()` dependency (alongside `require_roles()`)
- Add `permissions` property to `User` model (computed from roles)
- All existing code continues to work

**Phase 2: Route Migration (Gradual)**
- Replace `require_roles(["admin"])` → `require_permissions(["users:manage"])`
- Replace `user.has_role("operator")` → `user.has_permission("sync:trigger")`
- Replace `UserTenant.can_manage_resources` → check `resources:manage` permission
- Replace `UserTenant.can_view_costs` → check `costs:read` permission

**Phase 3: Azure AD Integration**
- Define app roles in App Registration manifest
- Map `roles` claim directly to `Role` enum
- Remove keyword-based `_map_groups_to_roles()`

**Phase 4: Per-Tenant Enhancement (Optional)**
- Add per-tenant role override capability
- User can be `Admin` globally but `Viewer` for a specific tenant

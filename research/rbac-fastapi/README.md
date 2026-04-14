# RBAC Implementation Patterns for FastAPI + SQLAlchemy Multi-Tenant Applications

**Research Date:** 2026-04-14
**Researcher:** web-puppy-42091f
**Status:** Complete
**Project Context:** Azure Governance Platform — 5 tenants, FastAPI + SQLAlchemy + Azure AD/Entra ID

---

## Executive Summary

This research covers practical RBAC (Role-Based Access Control) implementation patterns for evolving the Azure Governance Platform's existing auth system from simple string-based roles to granular, permission-based RBAC with `resource:action` permission strings.

### Key Findings

1. **Permission String Pattern**: The `resource:action` format (e.g., `costs:read`, `compliance:write`) is the dominant industry pattern — used by OAuth2 scopes, AWS IAM, Azure RBAC, and most SaaS platforms. Our project should adopt this format.

2. **Predefined Roles as Permission Sets**: Define roles as frozen sets of permission strings in Python code (not in the database). This keeps role definitions version-controlled, testable, and simple for a 5-tenant team.

3. **Migration Path**: A phased approach works best — (1) define permission strings, (2) map existing roles to permission sets, (3) add permission checking alongside existing role checks, (4) gradually migrate routes.

4. **Azure AD App Roles**: Entra ID app roles emit a `roles` claim in JWT tokens that can directly map to our predefined role names. App roles are preferred over group claims for SaaS-style apps.

5. **Library Recommendation**: **Don't add a library** — FastAPI's built-in `Security` + `SecurityScopes` + custom dependency injection is sufficient. PyCasbin is overkill for 4 roles × 5 tenants. `fastapi-permissions` is unmaintained and row-level-focused.

### Recommended Architecture

```
Azure AD App Roles (Entra ID)
    ↓ "roles" claim in JWT
Permission Resolver (maps role → permission set)
    ↓ set of permission strings
require_permissions() dependency (FastAPI)
    ↓ checks user permissions ⊇ required permissions
Route Handler
```

### Priority Actions

| Priority | Action | Effort | Impact |
|----------|--------|--------|--------|
| 🔴 P0 | Define permission string registry | 2 hours | Foundation for everything |
| 🔴 P0 | Define role→permission mappings | 1 hour | Enables permission checking |
| 🟡 P1 | Create `require_permissions()` dependency | 3 hours | Route-level enforcement |
| 🟡 P1 | Add `permissions` field to User model | 1 hour | Carry resolved perms |
| 🟢 P2 | Map Entra ID app roles to platform roles | 2 hours | Azure AD integration |
| 🟢 P2 | Migrate routes from `require_roles` to `require_permissions` | 4 hours | Granular control |
| ⚪ P3 | Add per-tenant role overrides in UserTenant | 2 hours | Tenant-scoped RBAC |

---

## Files in This Research

| File | Description |
|------|-------------|
| `README.md` | This file — executive summary and key findings |
| `sources.md` | All sources with credibility assessments |
| `analysis.md` | Multi-dimensional analysis of RBAC approaches |
| `recommendations.md` | Project-specific implementation guide with code examples |
| `raw-findings/fastapi-oauth2-scopes.md` | FastAPI SecurityScopes patterns |
| `raw-findings/fastapi-permissions-lib.md` | fastapi-permissions library evaluation |
| `raw-findings/azure-ad-app-roles.md` | Entra ID app roles → custom RBAC mapping |
| `raw-findings/pycasbin-evaluation.md` | PyCasbin library evaluation |

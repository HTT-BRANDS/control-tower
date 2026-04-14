# Sources — RBAC for FastAPI Multi-Tenant Applications

## Source Evaluation Summary

| # | Source | Tier | Authority | Currency | Bias | Used For |
|---|--------|------|-----------|----------|------|----------|
| 1 | FastAPI Official Docs — OAuth2 Scopes | Tier 1 | Official framework docs | Current (v0.135.3) | None | Scope-based permission patterns |
| 2 | FastAPI Official Docs — Security | Tier 1 | Official framework docs | Current | None | Security dependency patterns |
| 3 | Microsoft Learn — Entra ID App Roles | Tier 1 | Official vendor docs | Updated 2024-11-13 | Vendor (Microsoft ecosystem) | Azure AD app roles → RBAC mapping |
| 4 | GitHub — holgi/fastapi-permissions | Tier 3 | Community library | Last commit ~2022 | None | ACL-based permission library eval |
| 5 | GitHub — apache/casbin-pycasbin | Tier 2 | Apache Foundation project | Active development | None | Policy engine evaluation |
| 6 | GitHub — yezz123/authx | Tier 3 | Community library | Active | None | Auth library evaluation |
| 7 | Project codebase — app/core/auth.py | Primary | Our own code | Current | N/A | Existing auth implementation |
| 8 | Project codebase — app/core/authorization.py | Primary | Our own code | Current | N/A | Existing tenant authorization |
| 9 | Project codebase — app/core/personas.py | Primary | Our own code | Current | N/A | Existing persona/UI gating |
| 10 | Project codebase — app/models/tenant.py | Primary | Our own code | Current | N/A | UserTenant model with role field |

---

## Detailed Source Assessments

### Source 1: FastAPI Official Documentation — OAuth2 Scopes
- **URL**: https://fastapi.tiangolo.com/advanced/security/oauth2-scopes/
- **Tier**: 1 (Highest — Official Documentation)
- **Authority**: Sebastián Ramírez, FastAPI creator. Official framework docs.
- **Currency**: Current, updated with v0.135.3 (97.2k GitHub stars)
- **Validation**: Cross-referenced with FastAPI source code on GitHub
- **Bias**: None — framework docs describing built-in features
- **Key Findings**:
  - FastAPI has built-in `Security()` and `SecurityScopes` for scope-based auth
  - Scopes are strings in `resource:action` format (e.g., `users:read`, `items:write`)
  - Scopes aggregate through dependency chain automatically
  - Uses `Security()` instead of `Depends()` to declare scope requirements
  - Integrates with OpenAPI docs for interactive scope selection
- **Relevance**: HIGH — provides the foundation pattern we should build on

### Source 2: Microsoft Learn — Add App Roles to Your Application
- **URL**: https://learn.microsoft.com/en-us/entra/identity-platform/howto-add-app-roles-in-apps
- **Tier**: 1 (Highest — Official Vendor Documentation)
- **Authority**: Microsoft identity platform team
- **Currency**: Updated 2024-11-13
- **Validation**: Cross-referenced with Azure AD JWT token claims documentation
- **Bias**: Vendor docs favoring Microsoft ecosystem (expected, not problematic)
- **Key Findings**:
  - App roles are defined in App Registration manifest
  - Emitted as `roles` claim (not `groups` claim) in JWT tokens
  - App roles are portable across tenants (groups are not)
  - Value field is the string in the JWT claim (e.g., `Survey.Create`)
  - Can assign to users, groups, or service principals
  - App roles vs groups: roles are app-specific, groups are tenant-specific
  - For SaaS apps, **app roles are recommended** over groups
- **Relevance**: HIGH — directly applicable to our Azure AD integration

### Source 3: GitHub — holgi/fastapi-permissions
- **URL**: https://github.com/holgi/fastapi-permissions
- **Tier**: 3 (Community Library)
- **Authority**: Individual developer, inspired by Pyramid framework
- **Currency**: Last significant update ~2022, low maintenance activity
- **Validation**: 500+ GitHub stars, but declining activity
- **Bias**: None
- **Key Findings**:
  - Implements Pyramid-style ACL (Access Control Lists) for FastAPI
  - Resource-level permissions via `__acl__` attribute
  - Principal-based: users have principals like `role:admin`, `user:bob`
  - ACL entries are tuples: `(Allow/Deny, principal, permission)`
  - Row-level security focused — more granular than we need
  - Author recommends: "Use scopes until you need something different"
- **Relevance**: MEDIUM — good conceptual model but not recommended for adoption
- **Concerns**: Unmaintained, PyPI blocked by Cloudflare during research, no async support

### Source 4: GitHub — apache/casbin-pycasbin
- **URL**: https://github.com/apache/casbin-pycasbin (redirected from casbin/pycasbin)
- **Tier**: 2 (Established Open Source — Apache Foundation)
- **Authority**: Apache Software Foundation, widely adopted
- **Currency**: Active development, production-ready
- **Validation**: Used by major companies, extensive test suite
- **Bias**: None
- **Key Findings**:
  - Supports ACL, RBAC, RBAC with domains/tenants, ABAC
  - RBAC with domains/tenants model fits our multi-tenant use case
  - Model defined in CONF file, policies in CSV or database
  - Has SQLAlchemy adapter (`casbin-sqlalchemy-adapter`)
  - Has async support via `AsyncEnforcer`
  - Policy format: `p, alice, data1, read`
  - Role hierarchy: `g, alice, admin`
  - Domain/tenant support: `p, admin, tenant1, data1, read`
- **Relevance**: LOW for our use case — significant overkill for 4 roles × 5 tenants
- **Concerns**: Adds external dependency, separate policy storage, learning curve

### Source 5: Project Codebase Analysis (Primary Source)
- **Files Analyzed**: `app/core/auth.py`, `app/core/authorization.py`, `app/core/personas.py`, `app/models/tenant.py`
- **Tier**: Primary (Our own code)
- **Key Findings**:
  - Current roles: `admin`, `operator`, `reader`, `user`, `viewer`
  - Roles are simple strings in `User.roles: list[str]`
  - `require_roles()` dependency factory — checks `any(role in user.roles)`
  - Admin always bypasses all checks
  - UserTenant model has per-tenant `role` field: `viewer`, `operator`, `admin`
  - UserTenant has boolean permission flags: `can_manage_resources`, `can_view_costs`, `can_manage_compliance`
  - Personas are separate UI-gating layer (not authorization)
  - Azure AD groups mapped to roles via `_map_groups_to_roles()` — keyword matching
  - No permission string system exists yet
  - TenantAuthorization class handles tenant isolation

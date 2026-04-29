# Identity Domain

> Phase 1 paper boundary per `PORTFOLIO_PLATFORM_PLAN_V2.md` §5. No code
> has moved here yet. This document defines the target bounded context for
> Phase 1.5 refactors and Phase 2 DDD relocation.

## Purpose

The Identity domain owns portfolio identity truth and identity-governance
workflows across HTT-managed Entra tenants. It turns Microsoft Graph, tenant
configuration, MFA state, role assignments, sign-in activity, and license data
into tenant-scoped facts and review actions.

This domain answers:

- Who exists in each tenant and what kind of account are they?
- Which users, guests, service principals, and privileged accounts carry risk?
- Are MFA and admin-role controls healthy enough for the portfolio?
- Which role assignments are stale and need review/removal?
- What Microsoft license state exists per tenant/user?
- Which cross-tenant / Lighthouse access paths are configured and auditable?

## Entities and Value Objects

| Entity / value object | Current model/schema | Notes |
|---|---|---|
| Identity snapshot | `app/models/identity.py:11-32` | Tenant-level user/MFA/privileged/stale/service-principal counts. |
| Privileged user | `app/models/identity.py:34-52` | User principal, display name, role, scope, permanence, MFA, and sign-in state. |
| User account | `app/schemas/identity.py:137-156` | API DTO for user records from Graph/local snapshots. |
| Guest account | `app/schemas/identity.py:109-121` | API DTO for guest-user review. |
| Stale account | `app/schemas/identity.py:123-135` | API DTO for inactivity risk. |
| Privileged account | `app/schemas/identity.py:93-107` | API DTO for admin-role risk. |
| Directory role | `app/api/services/graph_client/_models.py:56-65` | Graph role definition summary. |
| Role assignment | `app/api/services/graph_client/_models.py:67-82` | Graph principal-to-role assignment. |
| Privileged access assignment | `app/api/services/graph_client/_models.py:84-98` | PIM/privileged role assignment DTO. |
| MFA status | `app/api/services/graph_client/_models.py:14-54` | Per-user and tenant MFA summaries. |
| Access review | `app/schemas/access_review.py:31-109` | Stale assignment, review record, and review action request. |
| License summary | `app/schemas/license.py:12-64` | User and tenant license/service-plan DTOs. |

## Invariants

1. **Tenant authorization is mandatory at every HTTP entry point.** Identity
   queries and review actions must be constrained to the caller's accessible
   tenant IDs.
2. **Identity data is personal data by default.** UPNs, display names, job
   titles, departments, MFA state, sign-in activity, and role assignments are
   all regulated/sensitive enough to require least-privilege access.
3. **Privileged access is high-risk data.** Admin roles, PIM assignments,
   service-principal role assignments, and stale privileged accounts require
   stricter retention, audit, and breach handling than aggregate counts.
4. **Review actions are auditable commands.** Dismiss/remove/defer actions must
   identify actor, target, tenant, timestamp, and outcome.
5. **Graph is an outbound adapter.** Microsoft Graph SDK/REST mechanics do not
   belong in identity domain rules.
6. **Authentication plumbing is shared core; identity facts are domain-owned.**
   Token validation/session middleware supports all domains. Identity owns
   users, roles, grants, MFA, access review, and license truth.
7. **No lateral domain imports.** Identity may expose read models/interfaces to
   compliance, lifecycle, and BI, but must not import their internals.
8. **Cross-tenant grants are explicit.** Lighthouse/B2B/delegated access must be
   represented as auditable grants or tenant-access facts, not hidden in config.

## Current Code Locations

These files currently belong wholly or partly to the Identity bounded context.
Line ranges are current as of 2026-04-29 and are the source map for later
refactors.

### HTTP routes

| Path | Lines | Domain responsibility |
|---|---:|---|
| `app/api/routes/identity.py` | 1-696 | Identity summary, users, privileged accounts, guest/stale accounts, trends, admin roles, licenses, and access review endpoints. |
| `app/api/routes/auth.py` | 1-940 | Mixed shared-auth and identity surface. Identity owns user/session-facing identity semantics; shared token plumbing should move to shared core. Phase 1.5 split target. |
| `app/api/routes/admin.py` | 1-290 | Mixed admin surface; Identity owns identity/admin-risk related controls only. |
| `app/api/routes/sync.py` | 1-320 | Shared sync API; Identity owns `identity` sync command semantics. |

### Services and Graph adapters

| Path | Lines | Domain responsibility |
|---|---:|---|
| `app/api/services/identity_service.py` | 1-521 | Identity summaries, privileged accounts, users, guests, stale accounts, trends, group/user stats, cache invalidation. |
| `app/api/services/access_review_service.py` | 1-453 | Stale assignment discovery, access-review creation, and review action execution. |
| `app/api/services/azure_ad_admin_service.py` | 1-592 | Directory roles, role assignments, PIM assignments, privileged users/service principals, admin-role summaries. |
| `app/api/services/license_service.py` | 1-332 | Microsoft license and service-plan collection by tenant/user. |
| `app/api/services/graph_client/_client.py` | 1-25 | Composed Graph client. |
| `app/api/services/graph_client/_base.py` | 1-311 | Graph auth/request core, users, guests, service principals, conditional access, sign-in logs. |
| `app/api/services/graph_client/_admin_roles.py` | 1-482 | Directory roles, PIM, privileged role assignments, service-principal assignments. |
| `app/api/services/graph_client/_mfa.py` | 1-347 | User authentication methods, MFA registration detail, tenant MFA summary. |
| `app/api/services/graph_client/_models.py` | 1-121 | Graph identity DTOs. |
| `app/core/sync/identity.py` | 1-377 | Scheduled/manual identity sync into snapshots and privileged-user tables. |
| `app/preflight/admin_risk_checks.py` | 1-921 | Admin MFA, overprivileged account, inactive admin, shared admin, and aggregate admin-risk checks. Phase 1.5 split target. |
| `app/alerts/mfa_alerts.py` | 1-422 | MFA gap detection and alert formatting; currently Riverside-flavored, but the MFA-risk rules belong in Identity. |
| `app/services/lighthouse_client.py` | 670-851 | Delegated subscription/tenant-access validation and discovery portions relevant to cross-tenant identity stance. Other cost/resource/security methods belong to their respective domains/adapters. |

### Models and schemas

| Path | Lines | Domain responsibility |
|---|---:|---|
| `app/models/identity.py` | 1-52 | Identity snapshots and privileged-user persistence. |
| `app/schemas/identity.py` | 1-156 | Identity summary, user, group, privileged, guest, stale-account DTOs. |
| `app/schemas/access_review.py` | 1-109 | Stale-assignment, review, and review-action DTOs. |
| `app/schemas/license.py` | 1-64 | License and service-plan DTOs. |

### Shared dependencies the domain consumes but does not own

| Path | Lines | Boundary note |
|---|---:|---|
| `app/core/auth.py` | 1-520 | Shared authentication/token/session utilities. Identity consumes the authenticated principal; shared auth remains platform core. |
| `app/core/authorization.py` | 1-384 | Shared tenant authorization guard. Identity routes consume it; role resolution is shared core until a dedicated IAM interface exists. |
| `app/models/tenant.py` | 1-114 | Shared tenant read model. Identity may read tenant names/IDs/auth paths through an interface; tenant lifecycle remains separate. |
| `app/api/services/azure_client.py` | 1-606 | Shared Azure credential/client adapter. Identity should depend on Graph/Entra interfaces, not concrete credential plumbing. |
| `app/api/services/monitoring_service.py` | 1-871 | Shared sync logs/alerts. Identity emits sync status and risk alerts through monitoring interfaces. |
| `app/models/monitoring.py` | 15-134 | Shared sync/alert persistence. Identity contributes job types/messages but does not own monitoring. |
| `app/core/cache.py` | 1-1181 | Shared cache decorators/invalidation. Identity uses cache policy; it does not own cache implementation. |

## Inbound Interface Contracts

### HTTP API

Owned route prefix: `/api/v1/identity`.

Current commands/queries:

- `GET /summary` — portfolio or tenant-filtered identity summary.
- `GET /users` — tenant-filtered user list with pagination/search/MFA filters.
- `GET /privileged`, `/guest`, `/stale` — account-risk views.
- `GET /trends` — identity trend points.
- Admin-role endpoints: summary, privileged users, global admins, security
  admins, privileged service principals, and cache invalidation.
- License endpoints: tenant license summaries and per-user license details.
- Access-review endpoints: list stale assignments/reviews and take review
  actions.

Shared auth routes may publish user/session/profile semantics, but token
validation, JWT mechanics, OAuth callback plumbing, and cookie/session middleware
belong to shared platform core.

### Sync commands

The scheduler or sync API may request:

- `sync_identity()` to ingest tenant identity snapshots and privileged-user
  facts.
- MFA/admin-risk checks through preflight/alert orchestration.
- License refresh through the license service.

### Domain events/read models

Identity may publish:

- Tenant identity health summary.
- Privileged access summary.
- MFA coverage summary.
- Cross-tenant/delegated-access summary.
- Access-review action audit facts.

Other domains consume those read models through interfaces only. Compliance may
use identity evidence; lifecycle may use onboarding readiness; BI may query
aggregates. Nobody gets to import `identity_service.py` directly like a gremlin.

## Outbound Interface Contracts

| Interface | Current concrete implementation | Contract |
|---|---|---|
| Microsoft Graph users/groups | `GraphClient` base methods | Read users, guests, groups, service principals, conditional access, sign-in logs. |
| Microsoft Graph admin roles/PIM | `GraphClient` admin-role mixin and `AzureADAdminService` | Read directory roles, assignments, PIM status, privileged users, service-principal grants. |
| Microsoft Graph MFA/auth methods | `GraphClient` MFA mixin | Read authentication methods and MFA registration status. |
| Microsoft licensing | `LicenseService` Graph calls | Read subscribed SKUs/service plans and user license assignments. |
| Tenant read model | `Tenant` ORM via `Session` | Read tenant IDs, names, active state, and auth/delegation metadata. No lifecycle mutation. |
| Authorization | `TenantAuthorization` | Filter tenant IDs and validate caller scope before data access or review actions. |
| Monitoring | `MonitoringService`/`SyncJobLog` | Emit sync status, admin-risk alerts, and access-review action results through shared monitoring. |
| Cache | `cached`, cache manager | Cache read models by tenant/auth scope and invalidate after sync or review action. |
| Cross-tenant delegation | Lighthouse client tenant-access methods | Discover/validate delegated access as identity facts; resource/cost/security collection remains in other domains. |

## Explicit Non-Goals

- Identity does not own cost, resource, compliance, lifecycle, or BI data.
- Identity does not own generic HTTP auth middleware after the route split;
  token/session validation is shared core.
- Identity does not own tenant onboarding workflows, but it exposes readiness and
  grant state for lifecycle to consume.
- Identity does not buy or assign Microsoft licenses unless a future explicit
  command is approved; current license work is read-only.
- Identity does not remediate admin roles automatically without explicit review
  action and audit trail.

## Phase 1.5 Refactor Guidance

1. Split `app/api/routes/auth.py` into shared auth plumbing and identity-facing
   user/session/profile concerns.
2. Split `app/preflight/admin_risk_checks.py` by strategy: MFA, overprivilege,
   inactive admins, shared admins, aggregate risk.
3. Keep Graph client as an adapter behind identity interfaces. Domain services
   should not hand-roll Graph URLs forever. That way lies spaghetti with OAuth
   sprinkles.
4. Extract access-review command handling from read-only stale assignment
   discovery.
5. Keep route modules thin: authz, validation, service invocation, response.
6. Do not introduce lateral imports from future `domains/cost`,
   `domains/compliance`, `domains/resources`, `domains/lifecycle`, or
   `domains/bi_bridge`.

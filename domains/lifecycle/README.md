# Lifecycle Domain

> Phase 1 paper boundary per `PORTFOLIO_PLATFORM_PLAN_V2.md` §5. No code
> has moved here yet. This document defines the target bounded context for
> Phase 1.5 refactors and Phase 2 DDD relocation.

## Purpose

The Lifecycle domain owns tenant, brand, subscription, and playbook lifecycle:
onboarding, configuration-as-code reconciliation, activation/deactivation,
self-service Lighthouse delegation, setup verification, and future acquisition /
change-management workflows.

This is the platform's "how does a brand become, remain, change, and eventually
stop being managed by HTT?" context.

It answers:

- Which brands/tenants/subscriptions are declared and active?
- How does a new tenant get onboarded or verified?
- Which tenant DB rows drift from configuration-as-code?
- Which brand-level presentation/configuration metadata applies?
- Which setup/playbook steps are complete, blocked, or intentionally skipped?
- How will future DCE/DeltaSetup-style templates become parameterized lifecycle
  playbooks?

## Scope Boundary

Lifecycle owns **business and operational lifecycle state**. It does not own
cloud resource inventory itself.

- Tenant onboarding/offboarding belongs here.
- Brand and subscription declaration/reconciliation belongs here.
- Delegation template generation and onboarding verification belongs here.
- Resource create/update/delete facts belong to Resources; Lifecycle may consume
  them as evidence for playbook progress.
- User-to-tenant access grants belong to Identity, even though they reference
  tenants.
- Cost/compliance/identity sync execution belongs to those domains; Lifecycle
  coordinates prerequisite readiness.

Yes, the repo currently uses "resource lifecycle" for change events. That name
is unfortunate. We are not letting noun soup drive architecture. Tiny violin.

## Entities and Value Objects

| Entity / value object | Current model/schema | Notes |
|---|---|---|
| Tenant | `app/models/tenant.py:18-49` | Managed Azure tenant / brand environment record. |
| Subscription | `app/models/tenant.py:53-68` | Azure subscription attached to a tenant. |
| Tenant create/update/response DTOs | `app/schemas/tenant.py:31-120` | Public API shape for tenant lifecycle operations. |
| Tenant YAML config | `app/core/tenants_config.py:31-187`, `config/tenants.yaml:1-71` | Configuration-as-code declaration of managed tenants. |
| Tenant setup config | `scripts/setup-tenants.py:48-137` | Legacy/ops setup declaration for Riverside tenants. |
| Brand configuration | `app/models/brand_config.py:22-91`, `config/brands.yaml` | Per-tenant brand presentation/config metadata. |
| Lighthouse delegation template | `app/api/routes/onboarding.py:273-380` | Generated ARM template used for self-service onboarding. |
| Onboarding status | `app/api/routes/onboarding.py:697-746` | Read model for tenant onboarding completion. |
| Tenant drift report | `scripts/reconcile_tenants.py:66-252` | Configuration-vs-database lifecycle reconciliation. |
| Provisioning validation result | `app/api/services/provisioning_standards_service.py:25-72` | Consumed by Lifecycle playbooks; Resources owns the standards service today. |

Future Phase 4d concepts from V2:

- Lifecycle playbook.
- Lifecycle step.
- Change request / acquisition onboarding run.
- Template parameter set.
- Rollback / offboarding checklist.

These are not implemented yet. Do not invent tables until a filed issue says so.
YAGNI is not a suggestion, it's a leash.

## Invariants

1. **Configuration-as-code is authoritative for declared tenants.** Drift between
   `config/tenants.yaml` and the DB must be detected and either fixed or
   intentionally documented.
2. **Tenant identity is immutable.** Azure tenant IDs and subscription IDs must
   not be silently rewritten after creation.
3. **Activation is explicit.** A tenant/brand is not sync-eligible merely because
   it exists; active flags, credentials/delegation, and subscriptions must align.
4. **Onboarding verification precedes operational sync.** Delegation or credential
   readiness must be checked before cost/resources/compliance/identity syncs are
   expected to work.
5. **Secrets are referenced, not stored.** Lifecycle may store Key Vault secret
   references or OIDC/delegation mode, never raw secret values.
6. **Lifecycle coordinates; domains execute.** Lifecycle can orchestrate or gate
   setup, but Cost/Identity/Compliance/Resources own their domain sync semantics.
7. **Every manual decision has an owner.** Open setup gaps must be marked with a
   🔴 owner/TODO instead of fictional certainty. Future-you hates fan fiction.
8. **No lateral domain imports.** Cross-domain access goes through published
   read models/adapters.

## Current Code Locations

These files currently belong wholly or partly to the Lifecycle bounded context.
Line ranges are current as of 2026-04-29 and guide later refactors.

### HTTP routes

| Path | Lines | Domain responsibility |
|---|---:|---|
| `app/api/routes/onboarding.py` | 1-875 | Self-service onboarding UI/API, Lighthouse template generation, delegation verification, tenant creation, onboarding status. |
| `app/api/routes/tenants.py` | 1-325 | Tenant CRUD, activation/deactivation, subscription listing. |
| `app/api/routes/provisioning_standards.py` | 1-99 | Lifecycle consumes validation commands for pre-provisioning playbooks; Resources owns resource standards logic today. |

### Configuration, setup, and reconciliation

| Path | Lines | Domain responsibility |
|---|---:|---|
| `app/core/tenants_config.py` | 1-220 | YAML tenant config loading, tenant config DTOs, active tenant discovery helpers. |
| `config/tenants.yaml` | 1-71 | Real tenant declaration file; sensitive, local/ops-controlled. |
| `config/tenants.yaml.example` | 1-71 | Committed template for tenant declarations. |
| `scripts/setup-tenants.py` | 1-531 | Legacy Riverside tenant setup, validation, DB initialization, Graph verification instructions. |
| `scripts/reconcile_tenants.py` | 1-253 | Drift detection and auto-fix between YAML tenant declarations and DB state. |
| `scripts/seed_riverside_tenants.py` | 1-181 | Deterministic seeding of Riverside tenant rows. |
| `docs/TENANT_SETUP.md` | 1-386 | Human setup procedure and tenant onboarding documentation. |
| `docs/COMMON_PITFALLS.md` | 1-455 | Operational pitfalls relevant to setup/reconciliation. |

### Models and schemas

| Path | Lines | Domain responsibility |
|---|---:|---|
| `app/models/tenant.py` | 18-68 | Tenant and subscription persistence. `UserTenant` lines 72-114 belong to Identity. |
| `app/schemas/tenant.py` | 1-120 | Tenant and subscription API DTOs. |
| `app/models/brand_config.py` | 1-91 | Brand configuration tied to tenant lifecycle and future sister-repo theming. |
| `config/brands.yaml` | 1-end | Brand configuration-as-code source for presentation/design metadata. |

### Adjacent code consumed by Lifecycle but not owned

| Path | Lines | Boundary note |
|---|---:|---|
| `app/api/services/provisioning_standards_service.py` | 1-417 | Lifecycle consumes validation outcomes in playbooks; Resources owns standards rules and resource shape. |
| `app/models/resource_lifecycle.py` | 1-54 | Despite the name, this records resource change facts and belongs to Resources. Lifecycle may consume it for playbook evidence. |
| `app/api/services/resource_lifecycle_service.py` | 1-160 | Resource change detection/history; owned by Resources, not Lifecycle. |
| `app/preflight/tenant_checks.py` | 1-532 | Readiness checks consumed by Lifecycle gates; individual Azure/Graph checks belong to Identity/Resources/Compliance/Cost adapters. |
| `app/services/lighthouse_client.py` | 92-201 | Delegation verification adapter method consumed by onboarding. Resource/cost/security methods stay with their domains. |
| `app/core/authorization.py` | 1-384 | Shared authorization; Lifecycle routes consume it. |
| `app/models/monitoring.py` | 15-134 | Shared sync/alert logs. Lifecycle may emit setup/reconciliation status. |

## Inbound Interface Contracts

### HTTP API / UI

Owned route prefixes:

- `/onboarding`
- `/api/v1/tenants`

Current commands/queries:

- Generate Lighthouse delegation template for a named organization.
- Verify delegation and create tenant record.
- Return onboarding status by tenant UUID.
- Create, read, update, deactivate/delete tenant records.
- List subscriptions for a tenant.

### CLI / ops commands

Owned commands:

- `python scripts/reconcile_tenants.py [--apply]` detects and fixes
  configuration-vs-DB drift for tenant declarations.
- `python scripts/seed_riverside_tenants.py [--dry-run]` seeds known Riverside
  tenant rows.
- `python scripts/setup-tenants.py --check|--init|--verify|--all` validates and
  initializes legacy Riverside tenant setup.

### Future playbook interface

Future lifecycle playbooks should expose:

- `start_playbook(playbook_type, tenant_or_brand, parameters, requested_by)`
- `record_step_result(run_id, step_id, status, evidence_ref)`
- `gate_on_domain_readiness(run_id, domain, readiness_contract)`
- `rollback_or_offboard(run_id, reason, approved_by)`

Do not build this yet. This is a boundary contract, not a permission slip for
premature framework origami.

## Outbound Interface Contracts

| Interface | Current concrete implementation | Contract |
|---|---|---|
| Tenant DB repository | SQLAlchemy `Tenant` / `Subscription` | Create/update/read tenant lifecycle state and subscriptions. |
| Tenant config loader | `app/core/tenants_config.py` | Read declared tenant/brand setup from YAML; no secrets in code. |
| Azure Lighthouse | `LighthouseAzureClient.verify_delegation()` | Verify delegated subscription access before activation. |
| Provisioning standards | `ProvisioningStandardsService` | Validate proposed names, regions, tags, and SKUs before playbook steps proceed. |
| Preflight checks | `app/preflight/tenant_checks.py` | Run readiness checks across tenant/subscription surfaces. |
| Identity domain | `UserTenant`, authz interfaces | Request/consume access-grant status; Identity owns grant semantics. |
| Resources domain | Resource inventory and lifecycle-event read models | Consume resource/change evidence to verify playbook outcomes. |
| Cost domain | Cost sync/readiness read models | Consume billing readiness; Cost owns spend data. |
| Compliance domain | Control/evidence readiness read models | Consume compliance readiness; Compliance owns scoring. |
| Monitoring | `SyncJobLog`, alerting/webhook services | Emit setup, drift, and playbook status. |

## Explicit Non-Goals

- Lifecycle does not own MFA/user/group/role analytics; Identity owns those.
- Lifecycle does not own resource inventory or resource change detection;
  Resources owns those.
- Lifecycle does not own control scoring, evidence interpretation, or audit
  readiness; Compliance owns those.
- Lifecycle does not own spend, budgets, or forecasts; Cost owns those.
- Lifecycle does not own broad BI datasets; BI bridge owns export/federation.
- Lifecycle should not store raw secrets or provider tokens. Ever. Bad puppy.

## Phase 1.5 Refactor Guidance

1. Split `app/api/routes/onboarding.py` before adding more onboarding features;
   875 lines is not a personality trait.
2. Extract Lighthouse template generation from HTTP rendering.
3. Keep tenant CRUD thin and move lifecycle policy into services.
4. Move YAML/DB reconciliation behind a lifecycle service interface before DDD
   relocation.
5. Make future playbook state explicit only when a filed Phase 4d issue requires
   it; don't create placeholder tables now.
6. Preserve boundaries: Lifecycle can orchestrate, but domain data remains owned
   by Cost, Identity, Compliance, Resources, and BI bridge.

# Compliance Domain

> Phase 1 paper boundary per `PORTFOLIO_PLATFORM_PLAN_V2.md` §5. No code
> has moved here yet. This document defines the target bounded context for
> Phase 1.5 refactors and Phase 2 DDD relocation.

## Purpose

The Compliance domain owns control posture, policy evidence, requirements,
framework mappings, compliance scoring, maturity tracking, and evidence-ready
Riverside views. Riverside is one consumer of evidence; it is not the platform
identity and not the only compliance audience.

This domain answers:

- What is each tenant's current compliance score and trend?
- Which Azure policy states or requirements are non-compliant?
- Which framework controls map to custom rules or requirements?
- Which maturity, MFA, device, deadline, or threat items need escalation?
- What evidence can be exported or summarized for Riverside/leadership?

## Entities and Value Objects

| Entity / value object | Current model/schema | Notes |
|---|---|---|
| Compliance snapshot | `app/models/compliance.py:22-39` | Tenant/date compliance score and control counts. |
| Policy state | `app/models/compliance.py:42-62` | Azure policy assignment/compliance state. |
| Custom compliance rule | `app/models/custom_rule.py:12-66` | Tenant-scoped custom rule definition and evaluation schema. |
| Compliance score/status/trend/gap | `app/schemas/compliance.py:8-110` | API DTOs for scorecards, violations, trends, and gaps. |
| Riverside compliance | `app/models/riverside.py:49-89` | Evidence/maturity score by tenant/category. |
| Riverside MFA | `app/models/riverside.py:91-128` | MFA evidence snapshot for Riverside-facing reporting. |
| Riverside requirement | `app/models/riverside.py:130-175` | Requirement, priority, status, due date, evidence link, owner. |
| Riverside device compliance | `app/models/riverside.py:177-207` | Device compliance evidence. |
| Riverside threat data | `app/models/riverside.py:209-234` | Threat/compliance evidence facts. |
| Scheduler result DTOs | `app/core/riverside_scheduler.py:59-94` | MFA, maturity regression, and threat escalation result objects. |

## Invariants

1. **Evidence is tenant-scoped and source-cited.** Compliance facts must retain
   tenant/source/date context so executive claims can be traced back.
2. **Riverside is a view, not the domain boundary.** Riverside requirements and
   reports live here as evidence products; the domain remains HTT-owned.
3. **Identity evidence is consumed through interfaces.** MFA/admin/user posture
   belongs to Identity; Compliance may consume approved identity read models.
4. **Resource/policy evidence is consumed through interfaces.** Resource truth
   belongs to Resources; Compliance may consume policy/resource read models.
5. **Custom rules are declarative.** Rule definitions and JSON schemas are data;
   arbitrary code execution is forbidden. We are not building a policy RCE
   machine, thanks.
6. **Requirement status changes are auditable.** Owner, due date, evidence link,
   status, and update timestamp matter.
7. **Alerts/escalations are derived facts.** Scheduler jobs generate evidence or
   notifications; they do not own identity/resource truth.
8. **No lateral domain imports.** Cross-domain data arrives via interfaces/read
   models, never by importing future `domains/identity` or `domains/resources`
   internals.

## Current Code Locations

These files currently belong wholly or partly to the Compliance bounded context.
Line ranges are current as of 2026-04-29 and are the source map for later
refactors.

### HTTP routes

| Path | Lines | Domain responsibility |
|---|---:|---|
| `app/api/routes/compliance.py` | 1-227 | Compliance summary, scores, non-compliant policies, trends, and status routes. |
| `app/api/routes/compliance_frameworks.py` | 1-123 | Framework/control catalog and tag mapping routes. |
| `app/api/routes/compliance_rules.py` | 1-145 | Custom compliance rule CRUD/evaluation routes. |
| `app/api/routes/riverside.py` | 1-174 | Riverside dashboard, badge, summary, MFA status, maturity scores, requirements, gaps, and sync trigger routes. |
| `app/api/routes/sync.py` | 1-320 | Shared sync API; Compliance owns `compliance` and Riverside evidence-sync semantics. |

### Services, sync, and scheduler

| Path | Lines | Domain responsibility |
|---|---:|---|
| `app/api/services/compliance_service.py` | 1-475 | Compliance summaries, top violations, policy status, score/trend/gap queries, cache invalidation. |
| `app/api/services/compliance_frameworks_service.py` | 1-305 | Framework catalog loading, controls, tag-to-control mapping, rule/framework mapping. |
| `app/api/services/custom_rule_service.py` | 1-204 | Custom rule validation, CRUD, and evaluation. |
| `app/api/services/riverside_compliance.py` | 1-241 | Riverside compliance summaries and MFA gap analysis. |
| `app/api/services/riverside_requirements.py` | 1-819 | Riverside requirement listing, filtering, updates, dashboards, and gap calculations. |
| `app/core/sync/compliance.py` | 1-347 | Azure policy/compliance sync into snapshots and policy state. |
| `app/services/riverside_sync.py` | 1-1075 | Riverside tenant evidence sync for MFA, devices, requirements, maturity, and full tenant sync. Phase 1.5 split target. |
| `app/core/riverside_scheduler.py` | 1-1110 | Scheduled compliance checks, deadline checks, maturity regression, threat escalation, reports, and alert scheduling. Phase 1.5 split target. |
| `app/alerts/mfa_alerts.py` | 1-422 | MFA gap alerts currently Riverside-specific; rules should be split with Identity owning MFA truth and Compliance owning evidence/escalation view. |

### Models and schemas

| Path | Lines | Domain responsibility |
|---|---:|---|
| `app/models/compliance.py` | 1-62 | Compliance snapshots and policy state persistence. |
| `app/models/custom_rule.py` | 1-66 | Custom compliance rule persistence. |
| `app/models/riverside.py` | 1-234 | Riverside evidence models: compliance, MFA, requirements, devices, threats. |
| `app/schemas/compliance.py` | 1-110 | Compliance API DTOs. |
| `app/schemas/riverside/__init__.py` | 1-94 | Riverside schema exports. |
| `app/schemas/riverside/compliance.py` | 1-128 | Riverside compliance DTOs. |
| `app/schemas/riverside/requirements.py` | 1-184 | Riverside requirement DTOs. |
| `app/schemas/riverside/dashboard.py` | 1-178 | Riverside dashboard summary DTOs. |
| `app/schemas/riverside/mfa.py` | 1-83 | Riverside MFA DTOs. |
| `app/schemas/riverside/device.py` | 1-76 | Riverside device compliance DTOs. |
| `app/schemas/riverside/threat.py` | 1-65 | Riverside threat DTOs. |
| `app/schemas/riverside/bulk.py` | 1-100 | Bulk update/pagination DTOs. |
| `app/schemas/riverside/enums.py` | 1-28 | Requirement category/priority/status enums. |

### Shared dependencies the domain consumes but does not own

| Path | Lines | Boundary note |
|---|---:|---|
| `app/core/authorization.py` | 1-384 | Tenant authorization guard. Compliance routes consume it; authz remains shared core. |
| `app/models/tenant.py` | 1-114 | Shared tenant read model. Compliance reads tenant names/IDs/status through an interface. |
| `app/api/services/azure_client.py` | 1-606 | Shared Azure credential/client adapter. Compliance should depend on Azure Policy/Security adapters. |
| `app/api/services/graph_client/` | 1-121 plus mixins | Identity-owned Graph adapter; Compliance consumes identity/MFA evidence via interface. |
| `app/api/services/monitoring_service.py` | 1-871 | Shared sync logs/alerts. Compliance emits check and sync results through monitoring. |
| `app/models/monitoring.py` | 15-134 | Shared sync/alert persistence. Compliance contributes job types/messages but does not own monitoring. |
| `app/core/cache.py` | 1-1181 | Shared cache decorators/invalidation. Compliance uses cache policy; it does not own cache implementation. |

## Inbound Interface Contracts

### HTTP API

Owned route prefixes:

- `/api/v1/compliance`
- `/api/v1/compliance-frameworks`
- `/api/v1/compliance-rules`
- `/api/v1/riverside` for Riverside-facing evidence views

Current commands/queries:

- Compliance summary, tenant scores, non-compliant policy list, trends, status.
- Framework catalog and control lookup.
- Custom rule CRUD and evaluation.
- Riverside dashboard/summary/badge/MFA/maturity/requirements/gaps.
- Manual Riverside sync trigger.

### Sync and scheduled checks

The scheduler or sync API may request:

- `sync_compliance()` for Azure policy/compliance ingestion.
- Riverside evidence sync for MFA, device compliance, requirements, maturity,
  and threat data.
- Scheduled MFA compliance, deadline, maturity-regression, threat-escalation,
  and daily report checks.

### Domain events/read models

Compliance may publish:

- Tenant compliance score and trend.
- Non-compliant policy/control list.
- Framework/control evidence mapping.
- Requirement status and deadline risk.
- Riverside/evidence-consumer dashboard summaries.
- Escalation events for overdue or regressed controls.

## Outbound Interface Contracts

| Interface | Current concrete implementation | Contract |
|---|---|---|
| Azure Policy/Resource Graph | `app/core/sync/compliance.py` and Azure client plumbing | Read policy state and compliance facts by tenant/subscription; no resource mutation. |
| Identity evidence | Graph/MFA/Riverside sync paths | Consume approved MFA/admin/user posture read models; do not own raw identity collection long-term. |
| Resource evidence | Azure resource/policy data | Consume resource/policy read models for compliance evaluation; do not own inventory. |
| Tenant read model | `Tenant` ORM via `Session` | Read tenant IDs, names, and active state. No lifecycle mutation. |
| Monitoring | `MonitoringService`/`SyncJobLog` | Emit sync/check status and alerts. |
| Notifications | Shared notification/Teams adapters | Send escalations through shared notification interfaces. |
| Cache | `cached`, cache manager | Cache read models by tenant/scope; invalidate after sync/status changes. |
| Evidence export/UI | Riverside routes/schemas | Provide evidence DTOs; exported artifacts inherit Compliance classification. |

## Explicit Non-Goals

- Compliance does not own identity collection, MFA method truth, or admin-role
  remediation; Identity owns those facts/actions.
- Compliance does not own resource inventory or lifecycle onboarding.
- Compliance does not own generic alert storage, notification delivery, or cache
  mechanics.
- Compliance does not define the platform brand. Riverside views are evidence
  products, not naming direction.
- Compliance does not execute arbitrary user-provided rule code.

## Phase 1.5 Refactor Guidance

1. Split `app/services/riverside_sync.py` into per-evidence modules: MFA,
   device compliance, requirements, maturity, threat, and orchestration.
2. Split `app/core/riverside_scheduler.py` into per-check schedulers/handlers:
   MFA compliance, deadlines, maturity regression, threat escalation, reports,
   and job wiring.
3. Keep custom-rule validation/evaluation separate from framework catalog reads.
4. Route modules should be thin: authz, validation, service invocation, response.
5. Replace direct Graph/identity calls with an Identity evidence interface before
   Phase 2 relocation.
6. Do not introduce lateral imports from future `domains/cost`,
   `domains/identity`, `domains/resources`, `domains/lifecycle`, or
   `domains/bi_bridge`.

# Cost Domain Data Classification

> Required Phase 1 artifact per `PORTFOLIO_PLATFORM_PLAN_V2.md` §5 and the
> V2 red-team remediation for per-domain GDPR/CCPA framing.

## Classification Summary

| Category | Classification | Rationale |
|---|---|---|
| Primary data class | Confidential business data | Spend, budget, chargeback, and invoice-like facts reveal portfolio economics and vendor/resource strategy. |
| Personal data | Limited / indirect | Most records are not about people, but user IDs, acknowledgements, email-like resource tags, owner tags, and vendor/person names can identify individuals. |
| Sensitive personal data | Not expected | No health, biometric, government ID, precise geolocation, or protected-class attributes should be stored here. If discovered, treat as incident data. |
| Financial-regulated data | Business financial data, not payment-card data | Stores cloud spend and budget facts; must not store card numbers, bank account numbers, or payroll records. |
| Tenant boundary | Strict | Every cost fact exposed through the app must be scoped to an authorized tenant/brand unless explicitly aggregated for an authorized portfolio user. |

## Data Elements

### Cost facts

Current locations:

- `app/models/cost.py:22-39` (`CostSnapshot`)
- `app/schemas/cost.py:8-203`
- `app/core/sync/costs.py:1-293`

Fields include:

- Tenant ID and subscription ID.
- Resource group, service name, resource ID, and date.
- Total cost and currency.

Potential personal data:

- Resource names, resource groups, tags, or service dimensions may contain names,
  email handles, ticket numbers, customer names, or other human-entered strings.
- Subscription/resource naming may reveal brand acquisition or project names.

### Cost anomalies

Current locations:

- `app/models/cost.py:42-63` (`CostAnomaly`)
- `app/api/services/cost_service.py:261-466`

Fields include:

- Tenant ID, service name, detected date, actual/expected cost, variance,
  severity, description, acknowledgement flag, acknowledgement actor, and
  acknowledgement timestamp.

Potential personal data:

- `acknowledged_by` identifies an operator.
- `description` may include resource/service strings copied from user-controlled
  cloud names or tags.

### Budgets and budget alerts

Current locations:

- `app/models/budget.py:61-344`
- `app/schemas/budget.py:1-413`
- `app/api/services/budget_service.py:1-1026`
- `app/core/sync/budgets.py:1-322`

Fields include:

- Tenant ID, subscription ID, resource group, budget amount, current spend,
  threshold configuration, contact emails, alert status, alert message, Azure
  budget IDs, sync status, and sync error messages.

Potential personal data:

- Notification contact emails are direct personal data if they identify an
  individual.
- Alert messages and sync errors may include resource names, subscription names,
  or manually entered budget names.
- `acknowledged_by` / `acknowledged_at` are operator audit facts.

### Chargeback/showback exports

Current locations:

- `app/api/services/chargeback_service.py:1-316`
- `app/schemas/chargeback.py:1-80`
- `app/api/routes/costs.py:395-502`

Fields include:

- Tenant name, tenant ID, reporting period, total cost, allocation percent,
  resource-type cost, resource-group cost, and exported CSV/JSON content.

Potential personal data:

- Resource group names may include employee, contractor, vendor, or project names.
- Export filenames and generated reports can be forwarded outside the app, so
  access and retention rules matter. CSV is still data, not confetti.

### Reservation utilisation

Current locations:

- `app/api/services/reservation_service.py:1-275`
- `app/schemas/reservation.py:1-170`
- `app/api/routes/costs.py:325-393`

Fields include:

- Reservation order/name, SKU, region, utilisation percentage, used/reserved
  hours, and monetary savings metadata when available.

Potential personal data:

- Reservation names or order labels may contain manually entered names or project
  codes.

## Sources

| Source | Direction | Notes |
|---|---|---|
| Azure Cost Management Usage API | Inbound | Usage/cost rows by subscription and date range. |
| Azure Cost Management Budget API | Inbound/outbound | Read Azure budgets; create/update/delete budget definitions. |
| Azure Consumption Reservations API | Inbound | Reservation utilisation summaries. |
| Local operators | Inbound | Budget definitions, acknowledgement actions, notification contacts. |
| Future Pax8 / SaaS invoice feeds | Planned inbound | Must be normalized behind an adapter and re-evaluated for PII/vendor contract terms before production use. |

## Sinks and Recipients

| Sink | Data shared | Controls |
|---|---|---|
| Authenticated platform UI/API | Cost summaries, trends, anomalies, budgets, chargeback reports | TenantAuthorization and platform auth. |
| CSV/JSON exports | Chargeback/showback reports | Same authz as source query; exported files inherit confidential classification. |
| Monitoring/alerts | Sync status, error messages, alert metadata | Avoid secret values and raw provider tokens in errors. |
| Cache | Aggregated cost DTOs | Cache keys must include tenant scope and query parameters. |
| Future BI bridge | Approved aggregated/read-model cost facts | Read-only contract; no raw unfiltered tenant dumps. |

## Retention Policy

| Data type | Default retention | Reason |
|---|---:|---|
| Cost snapshots | 7 years | Supports financial analysis, acquisition diligence, and portfolio trend reporting. Reassess if storage cost or legal policy changes. |
| Cost anomalies | 2 years | Operational review and recurring-spend analysis. Older anomalies should be aggregated or archived. |
| Budget definitions | Life of budget + 7 years | Budget history is financial governance evidence. |
| Budget alerts and acknowledgements | 2 years | Operational audit trail; long enough for annual review and recurring issue analysis. |
| Budget sync results | 1 year | Troubleshooting/audit value declines quickly; retain summaries longer only if incident-related. |
| Chargeback/export files generated by app | Do not persist by default | Generate on demand. If exports are stored, classify as confidential and expire within 90 days unless finance requests longer retention. |
| Cache entries | Hours, not days | Cached cost data should follow existing cache TTL policy and be invalidated after sync completion. |

If legal hold, audit, incident response, or finance policy requires longer
retention, the hold wins. Document the owner and expiry date; eternal retention
because "maybe useful someday" is not a strategy, it is digital hoarding.

## Breach Notification Scope

A Cost-domain incident is in breach-notification scope when any of the following
are exposed to an unauthorized party:

1. Tenant-scoped cost or budget data tied to an identifiable brand, resource,
   vendor, project, or operator.
2. Notification contacts, acknowledgement actors, or other direct identifiers.
3. Exported chargeback/showback files.
4. Raw API responses or logs containing resource names/tags with personal data.
5. Any provider credential, token, connection string, or secret accidentally
   captured in cost sync or budget sync logs.

Potential notification audiences:

- HTT internal security/IT owner.
- Affected brand leadership if brand-specific financial data leaked.
- Legal/privacy owner for GDPR/CCPA assessment when identifiers are involved.
- Riverside or other evidence consumers only if contractual reporting requires
  it; Riverside is a consumer, not the platform owner.

## Minimization Rules

1. Do not store provider access tokens, refresh tokens, or raw authorization
   headers in Cost tables, sync logs, alerts, exports, or caches.
2. Do not copy full raw Azure API payloads into persistent records unless a field
   is explicitly modeled and needed.
3. Sanitize sync error messages before persistence. Include enough detail to
   debug; exclude secrets and bearer material. Shocking concept, yes.
4. Keep cache keys tenant-scoped. A cached portfolio result must never be served
   to a tenant-only user.
5. Treat CSV exports as confidential artifacts. The app should not persist them
   unless an explicit export-storage feature defines owner, expiry, and access.
6. Avoid storing personal emails in budget notification config when a role/group
   address works.

## Access Controls

| Actor | Access |
|---|---|
| Portfolio admin | Read all tenant cost facts; create/update budgets; acknowledge anomalies and budget alerts. |
| Tenant/brand operator | Read only assigned tenant cost facts; acknowledge only anomalies/alerts for assigned tenants if role permits. |
| Finance/evidence consumer | Read approved aggregate or tenant-scoped exports; no budget mutation unless explicitly granted. |
| Service principal / scheduler | Read Azure cost APIs and write normalized cost/budget sync facts; no user-facing export access. |
| Future BI bridge | Read approved aggregated cost read models; no direct ORM/session access. |

## Domain-Specific Risks

| Risk | Mitigation |
|---|---|
| Cross-tenant cost disclosure | Enforce `TenantAuthorization` before every query and mutation; test tenant isolation for summaries, anomalies, budgets, and exports. |
| Human-entered cloud names containing PII | Treat names/tags/resource groups as potentially identifying; avoid logging/exporting more detail than needed. |
| Secret leakage in sync errors | Scrub provider errors before persistence and alerting. |
| Stale cached aggregate served to wrong principal | Include tenant scope and auth context in cache keys; invalidate after sync. |
| Export sprawl | Generate on demand and document external handling expectations. |
| Future Pax8 invoice ingestion expands PII scope | Run a data-classification update before enabling ingestion; invoices may include customer/vendor/person-level details. |

## Open Questions

- 🔴 Tyler/legal/finance: Confirm whether 7-year retention for cost snapshots and
  budget definitions matches HTT finance policy, or whether this should align to
  a different accounting retention schedule.
- 🔴 Tyler: Decide whether future Pax8/SaaS invoice ingestion is aggregate-only
  or line-item level. Line-item ingestion may materially increase PII and
  contract-data exposure.

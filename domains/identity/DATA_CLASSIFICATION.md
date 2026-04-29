# Identity Domain Data Classification

> Required Phase 1 artifact per `PORTFOLIO_PLATFORM_PLAN_V2.md` §5 and the
> V2 red-team remediation for per-domain GDPR/CCPA framing.

## Classification Summary

| Category | Classification | Rationale |
|---|---|---|
| Primary data class | Confidential identity and access-management data | Identity facts reveal account inventory, admin roles, MFA posture, sign-in activity, and cross-tenant grants. |
| Personal data | Yes | UPNs, display names, job titles, departments, office locations, sign-in activity, group membership, license assignments, and review actors identify people. |
| Sensitive personal data | Security-sensitive personal data | MFA status, admin roles, stale-account status, and sign-in activity are security posture data and can create user risk if exposed. |
| Financial-regulated data | Limited | License assignments may imply cost allocation; no payment-card/bank data should exist. |
| Tenant boundary | Strict | Identity records must never cross tenant/brand authorization boundaries unless shown to an authorized portfolio admin. |

## Data Elements

### Identity snapshots

Current locations:

- `app/models/identity.py:11-32`
- `app/api/services/identity_service.py:34-108`
- `app/core/sync/identity.py:116-377`

Fields include tenant ID, snapshot date, total/active/guest users, MFA-enabled
and MFA-disabled counts, privileged-user count, stale-account counts, service
principal count, and sync timestamp.

Personal data scope:

- Aggregated counts are low direct-PII risk, but small tenants can make counts
  inferential. Treat tenant-level identity posture as confidential.

### User, guest, stale account, and group DTOs

Current locations:

- `app/schemas/identity.py:51-156`
- `app/api/services/identity_service.py:174-365`
- `app/api/services/graph_client/_base.py:105-310`

Fields include Azure AD object ID, tenant ID/name, UPN, display name, user type,
account enabled state, MFA state, last sign-in, created date, job title,
department, office location, group counts/types, stale-account flags, license
presence, and privileged-role flags.

Personal data scope:

- Direct identifiers: UPN, display name, object ID when linkable to a person.
- Employment/context data: title, department, office location.
- Behavioral/security data: sign-in recency, account enabled state, MFA state,
  stale-account status.

### Privileged access and admin roles

Current locations:

- `app/models/identity.py:34-52`
- `app/schemas/identity.py:93-107`
- `app/api/services/azure_ad_admin_service.py:91-559`
- `app/api/services/graph_client/_admin_roles.py:1-482`
- `app/preflight/admin_risk_checks.py:1-921`

Fields include UPN, display name, user type, role name, role scope, permanence,
PIM eligibility/activation, MFA state, last sign-in, tenant ID, service
principal grants, global/security admin status, and risk summaries.

Personal data scope:

- High sensitivity. This data identifies who can administer tenant systems and
  where access may be excessive, stale, or missing MFA.
- Service-principal role assignments are not personal data by themselves, but
  they are security-sensitive and can expose attack paths.

### MFA status and authentication methods

Current locations:

- `app/api/services/graph_client/_mfa.py:1-347`
- `app/api/services/graph_client/_models.py:14-54`
- `app/alerts/mfa_alerts.py:1-422`

Fields include authentication-method presence/type, MFA enabled/disabled status,
tenant MFA coverage, admin MFA gaps, and alert metadata.

Personal data scope:

- MFA state is security-sensitive personal data. Do not expose method details to
  broad audiences unless required for remediation.

### Access reviews

Current locations:

- `app/schemas/access_review.py:31-109`
- `app/api/services/access_review_service.py:1-453`
- `app/api/routes/identity.py:570-696`

Fields include stale assignment ID, principal ID/name/type, role, scope, last
sign-in, days inactive, created/reviewed timestamps, reviewer, status, action,
notes, and action request metadata.

Personal data scope:

- Direct identity and security-review data. Notes may contain free text and must
  be treated as potentially sensitive.

### License assignments

Current locations:

- `app/schemas/license.py:12-64`
- `app/api/services/license_service.py:1-332`
- `app/api/routes/identity.py:470-568`

Fields include user ID, UPN, display name, SKU IDs/part numbers, service-plan
names, enabled/disabled provisioning status, tenant totals, assigned/unassigned
counts, and sync timestamp.

Personal data scope:

- License assignment is personal data when tied to a user. It may also reveal job
  function or tool access.

### Cross-tenant / delegated access

Current locations:

- `app/services/lighthouse_client.py:670-851`
- `app/models/tenant.py:1-114`
- `app/core/sync/utils.py:1-181`

Fields include tenant IDs, subscription IDs, delegation/eligibility state,
credential path metadata, and tenant sync eligibility decisions.

Personal data scope:

- Tenant IDs alone are not usually personal data, but delegated access metadata
  is security-sensitive. If grants are tied to users/service principals, treat as
  privileged-access data.

## Sources

| Source | Direction | Notes |
|---|---|---|
| Microsoft Graph users/groups | Inbound | Users, guests, groups, service principals, sign-in activity, conditional access. |
| Microsoft Graph role/PIM APIs | Inbound | Directory roles, assignments, privileged users, service-principal grants. |
| Microsoft Graph authentication-method APIs | Inbound | MFA/auth method state. |
| Microsoft Graph subscribed SKU/license APIs | Inbound | Tenant and user license facts. |
| Local tenant configuration | Inbound | Tenant IDs, active state, delegation/auth path metadata. |
| Operator review actions | Inbound/outbound | Access-review decisions and optional remediation actions. |

## Sinks and Recipients

| Sink | Data shared | Controls |
|---|---|---|
| Authenticated platform UI/API | Identity summaries, user lists, privileged-role views, license views, access reviews | TenantAuthorization and role checks. |
| Monitoring/alerts | Sync status, MFA gaps, admin-risk alerts, access-review action results | No tokens or raw secrets; avoid over-sharing user details in broad alerts. |
| Cache | Tenant-scoped identity DTOs | Cache keys must include tenant/auth scope and expire/invalidate after sync/review action. |
| Compliance domain | Approved aggregate identity posture and evidence | Interface/read model only; no ORM/session coupling. |
| Lifecycle domain | Tenant onboarding/readiness identity checks | Interface/read model only. |
| Future BI bridge | Aggregated, approved identity metrics only | No raw user lists unless explicitly approved and classified. |

## Retention Policy

| Data type | Default retention | Reason |
|---|---:|---|
| Identity snapshots | 2 years | Trend/security posture evidence without retaining unnecessary user detail forever. |
| Privileged-user records | 2 years active history; 7 years if incident/legal hold | Supports access reviews and incident response. |
| MFA/admin-risk alerts | 2 years | Operational audit and recurring-risk analysis. |
| Access-review records/actions | 7 years | Governance evidence for privileged access decisions. |
| Sign-in activity copied into app records | 180 days unless attached to review/incident | Minimize behavioral data retention. |
| User/license read-model cache | Hours, not days | Cache is operational acceleration, not identity archive. |
| Raw Graph responses | Do not persist by default | Normalize only required fields; raw payloads are too juicy and too messy. |

If legal hold, security incident response, or contractual audit requirements
apply, the hold overrides these defaults. Document owner, purpose, and expiry.

## Breach Notification Scope

An Identity-domain incident is in breach-notification scope when any of the
following are exposed to an unauthorized party:

1. User lists containing UPN, display name, object ID, job title, department,
   office, account state, MFA state, or sign-in activity.
2. Guest-user or stale-account lists.
3. Privileged-role assignments, global/security admin lists, PIM assignments, or
   privileged service-principal grants.
4. Access-review records, reviewer notes, action history, or stale assignment
   findings.
5. License assignments tied to named users.
6. Cross-tenant/delegated-access grant details tied to users, service
   principals, or subscriptions.
7. Any credential, token, connection string, Graph bearer token, or secret
   accidentally logged or persisted.

Potential notification audiences:

- HTT internal security/IT owner.
- Affected brand leadership for brand-specific tenant exposure.
- Legal/privacy owner for GDPR/CCPA assessment.
- Affected users when legally required or operationally appropriate.
- Riverside/evidence consumers only if contractual reporting requires it;
  Riverside is not the platform owner.

## Minimization Rules

1. Persist aggregate identity snapshots where possible; avoid storing full raw
   user payloads unless a product requirement demands it.
2. Do not persist raw Graph responses, bearer tokens, refresh tokens,
   authorization headers, client secrets, or certificate material.
3. Keep access-review notes short, factual, and free of secrets or HR commentary.
4. Do not expose MFA method details to non-admin readers; aggregate MFA posture
   is enough for most audiences.
5. Cache by tenant and role scope. A cached admin view must never be served to a
   non-admin tenant operator. Revolutionary, I know.
6. Redact UPN/display name in broad operational logs when object ID or aggregate
   count is sufficient.
7. Treat service-principal grants as security-sensitive even when not personal
   data.

## Access Controls

| Actor | Access |
|---|---|
| Portfolio admin/security owner | Read all tenant identity risk, privileged roles, MFA state, license summaries; perform access-review actions. |
| Tenant/brand operator | Read assigned-tenant aggregate identity posture and limited user/remediation views if role permits. |
| Finance/evidence consumer | Read approved aggregate identity evidence only; no raw user lists by default. |
| Service principal / scheduler | Read Graph data and write normalized identity snapshots/review candidates; no user-facing export access. |
| Future BI bridge | Read aggregate identity metrics only unless a separate approved data contract exists. |

## Domain-Specific Risks

| Risk | Mitigation |
|---|---|
| Cross-tenant user disclosure | Enforce `TenantAuthorization` before every identity query and review action; test tenant isolation. |
| Privileged-access map leaked | Restrict privileged-role views to admin/security roles; avoid broad alert payloads with full user lists. |
| MFA status used for social engineering | Limit MFA method detail visibility and redact from general logs. |
| Review action removes wrong assignment | Require tenant scope, target ID, actor, timestamp, dry-run/confirmation where practical, and audit result. |
| Raw Graph payload sprawl | Normalize only required fields and ban raw response persistence. |
| Cache leaks admin view | Include tenant and role scope in cache key; invalidate after sync/review actions. |
| Future CIEM integration expands scope | Revisit this classification before integrating Entra Permissions Management or another CIEM feed. |

## Open Questions

- 🔴 Tyler/security: Confirm whether access-review action retention should be 7
  years or align to a shorter internal security-audit period.
- 🔴 Tyler: D10 cross-tenant identity stance remains open in V2 §9; current
  recommendation is hybrid audit-each-grant. This data classification assumes
  every cross-tenant grant is auditable and security-sensitive.
- 🔴 Tyler: D8 CIEM build-vs-buy remains open. Any CIEM feed may add richer
  entitlement graphs and require an updated DPIA/classification pass.

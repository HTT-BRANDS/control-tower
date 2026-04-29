# Compliance Domain Data Classification

> Required Phase 1 artifact per `PORTFOLIO_PLATFORM_PLAN_V2.md` §5 and the
> V2 red-team remediation for per-domain GDPR/CCPA framing.

## Classification Summary

| Category | Classification | Rationale |
|---|---|---|
| Primary data class | Confidential compliance/evidence data | Control posture, requirements, gaps, deadlines, threats, and executive evidence can reveal operational weaknesses. |
| Personal data | Yes, when evidence references users/owners/devices | Requirement owners, MFA/user evidence, device/user associations, reviewer notes, and alert recipients can identify people. |
| Sensitive personal data | Security-sensitive operational data | MFA gaps, threats, non-compliance, device posture, and admin/control failures can expose attack paths. |
| Financial-regulated data | Indirect | Compliance evidence can affect audits/contracts but should not include payment-card/bank data. |
| Tenant boundary | Strict | Evidence is tenant/brand scoped unless intentionally aggregated for authorized portfolio or evidence consumers. |

## Data Elements

### Compliance snapshots and policy state

Current locations:

- `app/models/compliance.py:22-62`
- `app/schemas/compliance.py:8-110`
- `app/api/services/compliance_service.py:1-475`
- `app/core/sync/compliance.py:1-347`

Fields include tenant ID, snapshot date, compliance score, compliant and
non-compliant resource counts, policy assignment ID/name, compliance state,
resource ID, policy category, and sync timestamp.

Personal data scope:

- Usually resource/control data, not direct PII.
- Resource IDs/names/tags may contain user, customer, vendor, or project names.
- Policy failures can reveal security posture and must be treated as
  confidential even without direct PII.

### Custom compliance rules

Current locations:

- `app/models/custom_rule.py:12-66`
- `app/api/services/custom_rule_service.py:1-204`
- `app/api/routes/compliance_rules.py:1-145`

Fields include tenant ID, rule name/description, category, severity, JSON rule
schema, enabled state, creator, creation/update timestamps.

Personal data scope:

- Creator/owner fields can identify operators.
- Free-text rule descriptions may include system names, vendor names, or people.
- Rule schemas must never include secrets or executable code.

### Riverside evidence models

Current locations:

- `app/models/riverside.py:49-234`
- `app/schemas/riverside/*.py:1-184`
- `app/api/services/riverside_compliance.py:1-241`
- `app/api/services/riverside_requirements.py:1-819`
- `app/services/riverside_sync.py:1-1075`

Fields include tenant ID/name, category, score, maturity score, evidence URLs,
requirement title/description, priority/status, due date, owner, notes, MFA
coverage, device compliance facts, threat facts, gaps, and dashboard summaries.

Personal data scope:

- Requirement owners, notes, device/user associations, MFA evidence, and threat
  context can identify people or teams.
- Evidence URLs may point to documents containing broader sensitive data.
- Riverside-facing exports inherit this classification even when the data is
  summarized.

### Scheduler checks and alerts

Current locations:

- `app/core/riverside_scheduler.py:1-1110`
- `app/alerts/mfa_alerts.py:1-422`
- `app/api/services/monitoring_service.py:1-871` as shared sink

Fields include MFA compliance results, overdue requirement deadlines, maturity
regressions, threat escalations, generated alert messages, notification targets,
run status, and error messages.

Personal data scope:

- Alert payloads may identify owners, tenants, users without MFA, devices, or
  threat context.
- Broad notifications should prefer aggregate counts and links to authorized
  detail views.

## Sources

| Source | Direction | Notes |
|---|---|---|
| Azure Policy / Resource Graph | Inbound | Policy states and resource compliance facts. |
| Identity evidence/read models | Inbound | MFA/admin/user posture. Raw identity collection belongs to Identity. |
| Resource evidence/read models | Inbound | Device/resource compliance facts. Resource inventory belongs to Resources. |
| Local custom rules | Inbound | Declarative rules created by authorized operators. |
| Riverside/evidence operator updates | Inbound | Requirement status, owners, notes, evidence links. |
| Scheduler/check outputs | Inbound | Derived deadline, maturity, threat, and MFA gap facts. |

## Sinks and Recipients

| Sink | Data shared | Controls |
|---|---|---|
| Authenticated platform UI/API | Compliance scorecards, policy violations, requirements, gaps, dashboards | TenantAuthorization and role checks. |
| Riverside/evidence views | Evidence summaries and requirement status | Treat Riverside as a consumer with scoped evidence needs, not owner. |
| Monitoring/alerts | Sync/check status and escalation summaries | Avoid secrets and minimize user-level detail in broad notifications. |
| Cache | Tenant-scoped compliance DTOs | Cache keys must include tenant/auth scope and expire/invalidate after sync/status changes. |
| Future evidence bundle | Approved compliance evidence bundle | Bundle must cite sources and carry classification/handling instructions. |

## Retention Policy

| Data type | Default retention | Reason |
|---|---:|---|
| Compliance snapshots | 7 years | Audit/evidence trend history and contractual compliance reporting. |
| Policy state history | 2 years detailed; 7 years aggregate | Detailed resource posture ages quickly; aggregate evidence supports audits. |
| Custom rule definitions | Life of rule + 7 years | Rule history is governance evidence. |
| Riverside requirements/status history | 7 years | Evidence of requirement tracking and audit commitments. |
| MFA/device/threat evidence | 2 years unless incident/legal hold | Security-sensitive detail should not linger forever. |
| Scheduler/check logs | 1 year | Operational troubleshooting; incident-related logs may be retained longer. |
| Alert notifications | 2 years | Operational audit and recurring-risk analysis. |
| Exported evidence bundles | 90 days by default unless audit package requires longer | Avoid unmanaged evidence sprawl. |

If legal hold, audit request, or incident response requires longer retention, the
hold overrides defaults. Document owner, purpose, and expiry. Otherwise it is not
"governance," it is just hoarding with a nicer dashboard.

## Breach Notification Scope

A Compliance-domain incident is in breach-notification scope when any of the
following are exposed to an unauthorized party:

1. Tenant-specific compliance scores, policy failures, gaps, maturity
   regressions, or threat escalations.
2. Requirement owner names, notes, evidence links, or status history tied to a
   person/team.
3. MFA/user/device compliance details or alert payloads identifying users.
4. Custom rule definitions containing sensitive infrastructure details.
5. Evidence exports or Riverside-facing reports.
6. Any credential, token, secret, connection string, raw Graph token, or Azure
   provider response accidentally persisted in logs/evidence.

Potential notification audiences:

- HTT internal security/IT owner.
- Affected brand leadership for brand-specific evidence exposure.
- Legal/privacy owner for GDPR/CCPA assessment when identifiers are involved.
- Affected individuals if user-level MFA/device/owner data is exposed and notice
  is legally required.
- Riverside/evidence consumers only if contractual reporting requires it.

## Minimization Rules

1. Prefer aggregated posture over user-level compliance detail in dashboards and
   alerts.
2. Store source IDs and evidence links, not full raw provider payloads, unless a
   field is explicitly modeled.
3. Sanitize sync/check errors before persistence. No bearer tokens, secrets, or
   full provider headers. Wild idea: logs are not a password manager.
4. Keep custom rules declarative; reject executable payloads and unexpected
   schema fields.
5. Keep cache keys tenant/role scoped and invalidate after sync or requirement
   status changes.
6. Evidence exports must include handling expectations and expiry.
7. Free-text owner notes should be factual, short, and free of HR, medical, or
   secret material.

## Access Controls

| Actor | Access |
|---|---|
| Portfolio admin/security/compliance owner | Read all tenant compliance evidence; update requirements; trigger checks/syncs. |
| Tenant/brand operator | Read assigned-tenant evidence and update assigned requirements if role permits. |
| Riverside/evidence consumer | Read approved evidence summaries/bundles only; no raw tenant internals by default. |
| Service principal / scheduler | Read provider evidence and write normalized compliance facts/check results. |
| Future BI bridge | Read approved aggregate compliance metrics only unless a separate data contract exists. |

## Domain-Specific Risks

| Risk | Mitigation |
|---|---|
| Security posture disclosure | Restrict detailed failures to authorized admins/operators; summarize for broad audiences. |
| Cross-tenant evidence leak | Enforce tenant authorization before every query/export/status update. |
| Identity/resource domain coupling | Consume identity/resource read models via interfaces; no lateral imports. |
| Secret leakage in evidence/errors | Scrub provider errors and ban raw token/header persistence. |
| Custom-rule abuse | Validate schemas, forbid executable code, and audit rule changes. |
| Evidence export sprawl | Default to on-demand generation and short retention. |
| Riverside framing drift | Treat Riverside as one consumer; do not encode platform identity around it. |

## Open Questions

- 🔴 Tyler/compliance: Confirm whether 7-year retention for compliance snapshots,
  requirement status, and rule definitions matches HTT audit expectations.
- 🔴 Tyler: Confirm who may approve evidence bundle release to Riverside or other
  external evidence consumers.
- 🔴 Tyler: Decide whether user-level MFA/device evidence should ever appear in
  exported bundles, or only aggregate/control-level evidence.

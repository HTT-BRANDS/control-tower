# Lifecycle Domain Data Classification

> Required Phase 1 artifact per `PORTFOLIO_PLATFORM_PLAN_V2.md` §5 and the
> V2 red-team remediation for per-domain GDPR/CCPA framing.

## Classification Summary

| Category | Classification | Rationale |
|---|---|---|
| Primary data class | Confidential tenant/brand operations data | Tenant IDs, subscriptions, onboarding state, delegation mode, and setup drift reveal managed portfolio structure. |
| Personal data | Yes / contextual | Admin emails, requester/reviewer identities, setup notes, tenant names, and brand metadata can identify people or businesses. |
| Sensitive personal data | Not expected | No protected-class, health, biometric, or government-ID data should be stored. Treat accidental inclusion as incident data. |
| Security-sensitive data | Yes | Client IDs, secret references, OIDC/delegation flags, drift reports, and setup status expose access posture. |
| Tenant boundary | Strict | Tenant lifecycle data must be visible only to platform admins or authorized tenant/brand operators. |

## Data Elements

### Tenant and subscription records

Current locations:

- `app/models/tenant.py:18-68`
- `app/schemas/tenant.py:31-120`
- `app/api/routes/tenants.py:74-325`

Fields include internal tenant UUID, tenant display name, Azure tenant ID,
client/application ID, client secret reference, billing account ID, description,
active flag, Lighthouse flag, OIDC flag, timestamps, subscription ID, display
name, state, and sync timestamp.

Personal data scope:

- Tenant/brand names can identify legal/business entities.
- Descriptions can contain free-form personal or confidential operational data.
- Client IDs are not passwords but are security-relevant identifiers.
- Secret references can reveal Key Vault naming conventions and credential
  locations; raw secret values must never be stored.

### User-to-tenant relationship data

Current location:

- `app/models/tenant.py:72-114`

Boundary note: Identity owns access-grant semantics. Lifecycle may consume grant
status to validate onboarding/offboarding completeness.

Personal data scope:

- `user_id`, `granted_by`, role, expiration, and last-access timestamps can
  identify individuals and their access patterns.

### Tenant configuration-as-code

Current locations:

- `app/core/tenants_config.py:31-187`
- `config/tenants.yaml:1-71`
- `config/tenants.yaml.example:1-71`
- `scripts/reconcile_tenants.py:1-253`
- `scripts/setup-tenants.py:48-183`

Fields include tenant IDs, codes, names, admin emails, app IDs, Key Vault secret
names, domains, active flags, Riverside flags, priorities, OIDC status, and
multi-tenant app IDs.

Personal data scope:

- Admin email addresses are direct personal data when they identify a person.
- Domains, tenant codes, and brand names can reveal business relationships.
- Key Vault secret names and OIDC flags are security-sensitive even without raw
  credentials.

### Self-service onboarding / Lighthouse delegation

Current locations:

- `app/api/routes/onboarding.py:273-875`
- `app/services/lighthouse_client.py:92-201`

Fields include organization name, generated ARM template metadata, managed-by
tenant ID, principal/object ID, role definition IDs, tenant name, Azure tenant
ID, subscription ID, description, verification result, delegated display name,
and onboarding status.

Personal data scope:

- Organization names and descriptions can contain customer/brand/operator data.
- Subscription IDs and delegation metadata expose tenant infrastructure posture.
- Verification errors can accidentally include provider details; scrub before
  broad logging or alerting.

### Brand configuration

Current locations:

- `app/models/brand_config.py:22-91`
- `config/brands.yaml`

Fields include brand name, brand key, color/design tokens, logo paths, font
choices, gradient, timestamps, and tenant association.

Personal data scope:

- Usually business/confidential rather than personal.
- Logo paths, brand names, and brand keys can reveal acquisition or launch plans
  before they are public.

### Drift reports and setup outputs

Current locations:

- `scripts/reconcile_tenants.py:66-252`
- `scripts/seed_riverside_tenants.py:1-181`
- `scripts/setup-tenants.py:193-531`
- `docs/TENANT_SETUP.md:1-386`
- `docs/COMMON_PITFALLS.md:1-455`

Fields include missing/extra tenants, active-state mismatches, name mismatches,
inserted/reactivated/deactivated tenant codes, validation errors, setup results,
and verification output.

Personal data scope:

- Drift reports can include tenant IDs, tenant names, admin emails, app IDs, and
  operational readiness state.
- CLI output should not be pasted into broad channels without reviewing for
  identifiers. Yes, screenshots count. Sneaky little data leaks.

## Sources

| Source | Direction | Notes |
|---|---|---|
| `config/tenants.yaml` / examples | Inbound | Declared tenant inventory and setup metadata. Real file may contain sensitive identifiers. |
| `config/brands.yaml` | Inbound | Brand presentation/config metadata. |
| Platform API operators | Inbound | Tenant create/update/deactivate requests and descriptions. |
| Self-service onboarding users | Inbound | Organization/tenant/subscription identifiers for Lighthouse verification. |
| Azure Lighthouse / ARM | Inbound | Delegation verification and subscription metadata. |
| Preflight checks | Inbound | Readiness signals for tenant/subscription setup. |
| Identity domain | Inbound/outbound | Access-grant state for onboarding/offboarding completeness. |

## Sinks and Recipients

| Sink | Data shared | Controls |
|---|---|---|
| Authenticated platform UI/API | Tenant records, subscription lists, onboarding status | Admin/tenant authz and rate limits. |
| Database | Tenant/subscription/brand lifecycle state | Encrypted storage/backups according to platform DB policy. |
| Azure ARM/Lighthouse | Generated delegation template and verification inputs | Operator-controlled deployment; no raw secrets. |
| CLI/stdout | Drift/setup reports | Intended for platform operators; review before sharing. |
| Monitoring/alerts | Setup/reconciliation/playbook status | Avoid raw IDs where summaries are sufficient. |
| Identity domain | Tenant activation/offboarding context | Interface only; Identity owns grant mutation. |
| Resources/Cost/Compliance domains | Readiness gates and active-tenant lists | Interface/read model only; each domain owns its data. |
| Future BI bridge | Approved aggregate lifecycle metrics | No raw tenant setup dumps without explicit data contract. |

## Retention Policy

| Data type | Default retention | Reason |
|---|---:|---|
| Active tenant/subscription records | Life of management relationship + 2 years | Operational continuity and audit trail after offboarding. |
| Deactivated/offboarded tenant records | 2 years after offboarding unless legal hold applies | Incident response, historical audit, rollback context. |
| Tenant config YAML history | Git retention, but avoid committing real secrets/PII | Configuration-as-code audit. Real sensitive files must remain protected. |
| Onboarding verification results | 1 year detailed; 2 years aggregate status | Troubleshooting and onboarding audit. |
| Drift reports | 1 year | Detect repeated configuration hygiene issues. |
| Brand configuration | Life of brand relationship + 1 year | Theming/config continuity. |
| CLI logs/screenshots | 30-90 days unless attached to incident/change record | Minimize accidental identifier retention. |
| Future playbook step evidence | 2 years by default | Change-management and acquisition audit. |

Legal hold, incident response, contract, or audit requirements override these
defaults. Document owner, reason, and expiry.

## Breach Notification Scope

A Lifecycle-domain incident is in breach-notification scope when any of the
following are exposed to an unauthorized party:

1. Tenant/subscription IDs, tenant names, onboarding status, or active/inactive
   managed-tenant inventory.
2. Admin emails, user IDs, `granted_by`, setup notes, or descriptions that
   identify people.
3. Client/application IDs, Key Vault secret references, OIDC flags, Lighthouse
   delegation metadata, or drift reports revealing access posture.
4. Brand configuration for non-public brands, acquisitions, launches, or design
   assets.
5. Raw secrets, tokens, provider authorization headers, or connection strings
   accidentally captured in setup output or notes.

Potential notification audiences:

- HTT internal security/IT owner.
- Affected brand/business owner.
- Legal/privacy owner for GDPR/CCPA assessment when personal identifiers are
  involved.
- Affected individuals if admin emails/user IDs/access events are exposed and
  notice is required.
- Evidence consumers only when contractual obligations require it.

## Minimization Rules

1. Store secret references only, never raw client secrets, access tokens, refresh
   tokens, or provider headers.
2. Do not persist full ARM/Lighthouse provider responses unless a filed issue
   explicitly requires evidence retention and defines redaction.
3. Keep tenant descriptions and onboarding notes short, factual, and free of
   credentials or unnecessary personal data.
4. Prefer tenant codes or internal UUIDs in broad logs; include full tenant IDs
   only where needed for troubleshooting.
5. Scrub CLI output before pasting into tickets, chat, or docs.
6. Treat `config/tenants.yaml` as sensitive ops material even if it contains no
   passwords. IDs + secret names + active flags are still useful to attackers.
7. Future playbook evidence must store references to domain-owned evidence, not
   duplicate raw Cost/Identity/Compliance/Resources payloads.
8. Offboarding must include access-grant review with Identity; do not leave
   zombie user mappings because zombies are famously bad at least privilege.

## Access Controls

| Actor | Access |
|---|---|
| Portfolio admin/platform engineer | Full tenant lifecycle, onboarding, drift, and brand configuration access. |
| Tenant/brand admin | Read own tenant onboarding/subscription status; limited update rights only if explicitly implemented. |
| Security/compliance owner | Read lifecycle evidence needed for audits/incidents. |
| Service principal / scheduler | Read active tenant declarations and write reconciliation/setup status where required. |
| Future BI bridge | Approved aggregate lifecycle metrics only unless separate data contract exists. |

## Domain-Specific Risks

| Risk | Mitigation |
|---|---|
| Real tenant config committed accidentally | Keep sensitive config gitignored; detect-secrets/pre-commit; examples use placeholders. |
| Cross-tenant lifecycle leak | Enforce tenant authorization on every tenant/subscription/onboarding status query. |
| Secret-reference overexposure | Treat Key Vault paths/names as confidential; redact in broad logs. |
| Incorrect activation causes sync failures | Reconcile YAML vs DB and require preflight/delegation checks before expecting sync success. |
| Offboarding leaves access behind | Coordinate with Identity grant review and record completion evidence. |
| Onboarding provider errors reveal internals | Normalize/scrub errors before user-facing HTML/API or alert output. |
| Lifecycle becomes god-domain | Keep orchestration only; domain facts remain owned by Cost/Identity/Compliance/Resources/BI. |

## Open Questions

- 🔴 Tyler/platform: Confirm whether offboarded tenant records should retain full
  identifiers for 2 years or be partially redacted after a shorter interval.
- 🔴 Tyler/security: Decide whether tenant operators can self-service onboarding
  in production or whether Tyler/platform approval is required before activation.
- 🔴 Tyler: Define future Phase 4d playbook evidence requirements before adding
  playbook persistence tables.

# HTT Control Tower — documentation index

The authoritative docs. If something here disagrees with a file in
[`archive/`](archive/), this set wins — `archive/` is historical only.

## Start here

| If you want to... | Read |
|-------------------|------|
| Know where the project is **right now** | [`../STATE.md`](../STATE.md) |
| See the plan to **ops go-live** | [`PRODUCTION_READINESS_PLAN.md`](PRODUCTION_READINESS_PLAN.md) |
| **Operate** Control Tower (recovery how-to) | [`OPERATIONAL_RUNBOOK.md`](OPERATIONAL_RUNBOOK.md) |
| Know **who to call / how urgent** | [`INCIDENT_RESPONSE.md`](INCIDENT_RESPONSE.md) |
| **Use** Control Tower as an ops person (day one) | [`OPS_ONBOARDING.md`](OPS_ONBOARDING.md) |
| Understand a past **decision** | [`decisions/`](decisions/) (ADRs) |

## Operating & ops

- [`OPERATIONAL_RUNBOOK.md`](OPERATIONAL_RUNBOOK.md) — SRE/operational reference (incl. data-freshness & sync recovery)
- [`INCIDENT_RESPONSE.md`](INCIDENT_RESPONSE.md) — severity matrix, escalation, on-call, comms templates
- [`OPS_ONBOARDING.md`](OPS_ONBOARDING.md) — day-one walkthrough for the operations team
- [`runbooks/`](runbooks/) — task-specific runbooks (sync recovery, secret fallback, GHCR auth, UAMI, …)
  - [`runbooks/provision-ops-users.md`](runbooks/provision-ops-users.md) — add ops users at the right tier (ct-hvv)
  - [`runbooks/staging-rollback-drill.md`](runbooks/staging-rollback-drill.md) — rehearse rollback on staging (ct-c60)
- [`FULL_SEND_CRITERIA.md`](FULL_SEND_CRITERIA.md) — go/no-go decision matrix

## Architecture & platform

- [`decisions/`](decisions/) — Architecture Decision Records (current)
- [`DEPLOYMENT.md`](DEPLOYMENT.md), [`DEVELOPMENT.md`](DEVELOPMENT.md), [`API.md`](API.md)
- [`COST_MODEL_AND_SCALING.md`](COST_MODEL_AND_SCALING.md), [`DATA_RETENTION_POLICY.md`](DATA_RETENTION_POLICY.md)
- Auth/identity: [`OIDC_SETUP.md`](OIDC_SETUP.md), [`OIDC_TENANT_AUTH.md`](OIDC_TENANT_AUTH.md), [`AUTH_TRANSITION_ROADMAP.md`](AUTH_TRANSITION_ROADMAP.md), [`PERMISSIONS_REFERENCE.md`](PERMISSIONS_REFERENCE.md)

## Historical

- [`archive/`](archive/) — superseded phase/migration/closure docs and old status reports. Provenance only; not current guidance.

---
*Tracked by bd `ct-ana`. When you add a top-level doc, link it here so this stays the one authoritative index.*

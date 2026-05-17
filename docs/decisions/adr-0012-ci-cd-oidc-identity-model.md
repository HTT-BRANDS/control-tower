---
status: accepted
date: 2026-05-17
decision-makers: Tyler Granlund, Solutions Architect 🏛️, code-puppy-1c7422
consulted: Obsidian Agent 🪨
informed: Engineering, release-gate reviewers, Azure subscription administrators
relates-to: ct-90r, ct-90r.8, docs/release-gate/ci-cd-oidc-remediation-evidence-2026-05-17.md
---

# ADR-0012: CI/CD OIDC Identity Model for Control Tower

## Context and Problem Statement

The Obsidian CI/CD discovery pass and Richard validation found that Control Tower's GitHub Actions deployment path currently relies on one Entra app registration, `azure-governance-platform-oidc-dev`, across multiple environments.

The validated baseline in `docs/release-gate/ci-cd-oidc-remediation-evidence-2026-05-17.md` showed:

- One app registration/client ID serving dev, staging, production, backup, and drift concerns.
- Ten stale federated identity credentials referencing `HTT-BRANDS/azure-governance-platform`.
- Current federated credentials referencing `HTT-BRANDS/control-tower` for production, staging, main, pull requests, and production-backup.
- `Contributor` on `rg-governance-staging` and `rg-governance-production` for the shared app.
- GitHub environment sprawl from historical names.
- BCC/FN/TLL tenant secrets exist but no active application/workflow consumers were found in the initial code search.

The core question: what identity model should Control Tower use for GitHub Actions OIDC and future multi-tenant work?

## Decision Drivers

- **Blast-radius reduction:** production compromise must not imply staging/dev or unrelated workflow access.
- **Least privilege:** deployment identities should have only the roles needed for their environment.
- **Operational clarity:** GitHub environment names, Entra FIC subjects, and Azure RBAC scopes must map cleanly.
- **Recoverability:** backup/drift workflows should not share unnecessary production deployment power.
- **Azure boundary correctness:** Azure Lighthouse solves ARM delegation, not Microsoft Graph/Entra directory operations.
- **Incremental migration:** avoid breaking production deployment while reducing risk in safe stages.

## Considered Options

1. **Keep one shared app registration, tighten FICs/RBAC only.**
2. **Create separate app registrations per environment/concern.**
3. **Use Azure Lighthouse for all sibling-tenant access.**
4. **Use one multi-tenant app registration for all tenant/Graph/ARM needs.**

## Decision Outcome

Chosen option: **separate OIDC workload identities per environment/concern, with a hybrid tenant-access model.**

Control Tower should migrate toward:

| Concern | Target identity model |
|---|---|
| Development deploys | Dedicated dev OIDC app/client ID |
| Staging deploys | Dedicated staging OIDC app/client ID |
| Production deploys | Dedicated production OIDC app/client ID |
| Production backup/export | Dedicated backup identity or tightly-scoped production-backup identity |
| Drift/read-only inventory | Dedicated read-only/drift identity |
| Cross-tenant Azure Resource Manager work | Azure Lighthouse where target tenants have Azure subscriptions/resource groups |
| Microsoft Graph / Entra directory operations | Per-tenant app registrations or narrowly scoped multi-tenant app with explicit admin consent |

The current shared app registration may remain temporarily only as a migration bridge, not as the long-term target.

## Federated Credential Policy

Production deployment credentials should prefer environment-scoped subjects:

```text
repo:HTT-BRANDS/control-tower:environment:production
```

Staging deployment credentials should prefer:

```text
repo:HTT-BRANDS/control-tower:environment:staging
```

Backup should use:

```text
repo:HTT-BRANDS/control-tower:environment:production-backup
```

Broad production-capable credentials should not trust pull request subjects or generic branch subjects unless explicitly justified by a separate bead and evidence note.

## Azure Lighthouse Boundary

Azure Lighthouse is approved for cross-tenant Azure Resource Manager delegation when the target tenant owns Azure subscriptions/resource groups that HTT-CORE needs to manage.

Azure Lighthouse is **not** a replacement for Microsoft Graph or Entra directory permissions. If BCC/FN/TLL are Graph-only integrations, they require tenant-local app registrations or a narrowly scoped multi-tenant application with admin consent and documented Graph permissions.

## Consequences

### Positive

- Production identity can be scoped only to production resources.
- Staging identity can be validated without risking production RBAC.
- Backup and drift workflows can be constrained independently.
- Future tenant onboarding has a clear decision tree: Lighthouse for ARM, Graph app permissions for directory APIs.

### Negative / Cost

- More app registrations and GitHub environment secrets to manage.
- Requires staged rollout and validation windows.
- RBAC least-privilege testing may temporarily block deployment if required roles are missed.

## Implementation Plan

Tracked by bd epic `ct-90r`:

1. `ct-90r.1` — capture read-only evidence baseline.
2. `ct-90r.2` — delete stale old-repo federated credentials.
3. `ct-90r.9` — implement per-environment OIDC app registrations and environment-scoped client IDs.
4. `ct-90r.10` — replace Contributor RBAC with tested least-privilege roles.
5. `ct-90r.11` — remove repo-scope deployment secret/variable split-brain after env-scoped secrets are validated.
6. `ct-90r.12` / `ct-90r.13` — classify and dispose BCC/FN/TLL tenant secrets.

## Validation

A remediation is complete only when:

- No federated credential references `HTT-BRANDS/azure-governance-platform`.
- Production deployment uses an environment-scoped production credential.
- Staging deployment uses an environment-scoped staging credential.
- No CI/CD principal has broad `Contributor` on staging/production unless there is explicit, time-boxed risk acceptance.
- GitHub branch/environment protection supports the chosen OIDC subject model.
- Evidence is appended to `docs/release-gate/ci-cd-oidc-remediation-evidence-2026-05-17.md`.

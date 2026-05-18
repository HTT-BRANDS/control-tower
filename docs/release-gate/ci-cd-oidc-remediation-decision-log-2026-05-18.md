# CI/CD OIDC Remediation Decision Log — 2026-05-18

> **Collector:** `code-puppy-1c7422` for Tyler Granlund  
> **Scope:** follow-up remediation from the Obsidian validation baseline in
> `docs/release-gate/ci-cd-oidc-remediation-evidence-2026-05-17.md`.  
> **Secret handling:** no secret values were read or recorded. This document
> records names, subjects, roles, PRs, and command-result summaries only.

---

## Executive summary

| Bead | Decision / action | Evidence |
|---|---|---|
| `ct-652` | Restored deterministic development deployment workflow. | `.github/workflows/deploy-dev.yml`; successful run `26040857842`; dev image `acrgovernancedev.azurecr.io/governance-platform:dev-9373778-ct-652e`. |
| `ct-jcx` | Hardened dev deployment verification for App Service warmup. | `scripts/verify-dev-deployment.sh`; successful post-run local verification: `24 pass / 0 fail / 0 warnings`. |
| `ct-90r.7` | Hardened `main` branch protection. | PR #17 records before/after evidence; remote setting already applied and direct push to `main` is blocked. |
| `ct-90r.6` | Removed production deploy `skip_tests` bypass. | PR #18 removes the dispatch input and test-skip guards; validation proves no `skip_tests` remains. |
| `ct-90r.5` | Deleted unused GitHub environment sprawl. | PR #19 records before/after evidence; ghost environments are absent via GitHub API. |
| `ct-90r.4` | Added this decision log. | This file. |

---

## Decisions

### 1. Development deploys must be deterministic, not manual snowflakes

**Decision:** add a real development deployment workflow instead of relying on
manual ACR/App Service mutation.

**Implementation:** `.github/workflows/deploy-dev.yml`

The workflow now performs:

1. QA gate: ruff, format check, detect-secrets, unit/integration tests, Bandit
   high-severity gate.
2. Azure login via GitHub OIDC.
3. Docker buildx production-target image build.
4. Push to dev ACR.
5. Dev App Service container update.
6. Health gate with rollback to previous image.
7. Hardened dev validation.

**Validation receipt:**

```text
Workflow: Deploy to Development
Run:      https://github.com/HTT-BRANDS/control-tower/actions/runs/26040857842
Result:   success
Jobs:     QA Gate success; Build and Deploy Dev Image success; Dev Validation success
Image:    acrgovernancedev.azurecr.io/governance-platform:dev-9373778-ct-652e
```

**RBAC remediation applied:** the GitHub OIDC service principal required push
access to the dev ACR. A least-privilege role assignment was added:

```text
Principal object id: 7307bf65-6bbb-428d-b21e-d7b86d3be16f
Role:                AcrPush
Scope:               acrgovernancedev only
```

This avoided granting broader ACR task/build permissions.

**Rollback note:** the workflow captures the previous App Service container image
before mutation and rolls back if the health gate fails.

---

### 2. Dev validation should gate readiness, not expensive internals

**Decision:** use `/health` and `/health/detailed` as readiness signals; keep
heavier status-style endpoints out of the critical post-deploy gate.

**Why:** proof runs showed `/api/v1/status` could return `502/503/000` or time
out immediately after App Service restart while `/health` eventually stabilized.
That endpoint is useful for diagnostics, not deployment readiness.

**Implementation:** `scripts/verify-dev-deployment.sh`

Critical checks now include:

- `/health` returns HTTP 200 and JSON has:
  - `status=healthy`
  - `environment=development`
  - non-empty `version`
- `/health/detailed` returns valid JSON.
- `/openapi.json`, `/docs`, `/login`, static CSS, and protected-route no-500
  smoke pass.
- Optional Azure metadata checks warn if CLI context/permissions are unavailable.

**Validation receipt:**

```text
Post-workflow local verification
Tests Passed: 24
Tests Failed: 0
Warnings:     0
```

---

### 3. `main` must require PR review and admin enforcement

**Decision:** harden `main` branch protection rather than accept an exception.

**Applied remote state:**

```text
Required status checks: Browser Smoke, Security Scan
Strict status checks:   enabled
Required PR approvals:  1
Dismiss stale reviews:  enabled
Admin enforcement:      enabled
Force pushes:           disabled
Deletion:               disabled
Rulesets:               none
```

**Evidence:** PR #17 records:

- `reports/github-security/ct-90r.7-main-protection-before.md`
- `reports/github-security/ct-90r.7-main-protection-after.md`

**Validation receipt:** direct push to `main` is blocked:

```text
GH006: Protected branch update failed for refs/heads/main.
- Changes must be made through a pull request.
- 2 of 2 required status checks are expected.
```

**Rollback note:** if this blocks an emergency production fix, use the GitHub UI
or API to temporarily adjust branch protection with explicit incident approval,
then restore this state immediately after the emergency PR merges. Do not disable
required checks as a convenience path.

---

### 4. Production deploys cannot skip required tests through normal dispatch

**Decision:** remove the production deploy `skip_tests` input entirely. No
break-glass bypass was retained because there is no current approved emergency
procedure requiring one.

**Implementation:** PR #18 updates `.github/workflows/deploy-production.yml`.

Removed:

```text
workflow_dispatch.inputs.skip_tests
if: ${{ !inputs.skip_tests }}
```

After remediation, production workflow dispatch inputs are:

```json
{
  "reason": {
    "description": "Deployment reason (shown in Teams notification)",
    "required": true,
    "type": "string"
  }
}
```

**Validation receipts:**

```text
rg -n "skip_tests" .github/workflows/deploy-production.yml
# no matches

actionlint .github/workflows/deploy-production.yml
# pass

uv run pre-commit run --all-files
# pass
```

**Rollback note:** if Tyler later wants an emergency deploy lane, create a
separate break-glass workflow/job requiring protected environment approval,
explicit justification, and non-skippable security scanning. Do not reintroduce a
normal `skip_tests` dispatch input.

---

### 5. Remove unused GitHub environment sprawl

**Decision:** delete the four empty ghost environments after confirming no active
workflow, secret, or OIDC dependency.

Deleted GitHub environments:

```text
production-production
production-staging
staging-production
staging-staging
```

Retained environments:

```text
development
github-pages
production
production-backup
staging
```

**Active OIDC FIC subjects after cleanup:**

```text
repo:HTT-BRANDS/control-tower:environment:production-backup
repo:HTT-BRANDS/control-tower:pull_request
repo:HTT-BRANDS/control-tower:ref:refs/heads/main
repo:HTT-BRANDS/control-tower:environment:production
repo:HTT-BRANDS/control-tower:environment:staging
```

Ghost-subject query result:

```json
[]
```

**Evidence:** PR #19 records:

- `reports/github-security/ct-90r.5-environment-sprawl-before.md`
- `reports/github-security/ct-90r.5-environment-sprawl-after.md`

**Rollback note:** deleted GitHub environments can be recreated if a future
workflow explicitly needs them, but recreation must include an owner, workflow
consumer, secrets inventory, and matching OIDC subject decision.

---

## Open PRs carrying remediation evidence

| PR | Purpose | Notes |
|---|---|---|
| #17 | Branch protection evidence for `ct-90r.7` | Remote branch protection is already applied; PR records evidence/bead state. |
| #18 | Production `skip_tests` removal for `ct-90r.6` | Code change must merge before workflow file on `main` reflects the removal. |
| #19 | GitHub environment sprawl evidence for `ct-90r.5` | Remote environments are already deleted; PR records evidence/bead state. |

Because `main` now requires PR review, these PRs require reviewer approval before
merge. That is the desired security posture, not a regression.

---

## Remaining follow-ups

| Bead | Follow-up |
|---|---|
| `ct-90r.12` | Inventory BCC/FN/TLL tenant secrets and determine whether they are still needed. |
| `ct-90r.14` | Confirm `production-backup` OIDC credential and environment ownership. |
| `ct-90r.15` | Validate the full CI/CD OIDC remediation end-to-end after remediation PRs merge. |

---

## Non-secret validation command summary

```bash
# Branch protection

gh api repos/HTT-BRANDS/control-tower/branches/main/protection

# GitHub environments

gh api repos/HTT-BRANDS/control-tower/environments --paginate --jq '.environments[].name'

# Active Azure federated credentials

az ad app federated-credential list \
  --id 3184145f-dab3-4f22-8cd4-4b8a11eea6ed \
  --query '[].{name:name,subject:subject,issuer:issuer}' \
  -o table

# Production skip-tests removal

rg -n "skip_tests" .github/workflows/deploy-production.yml
actionlint .github/workflows/deploy-production.yml
uv run pre-commit run --all-files
```

---

## Final decision

The remediation path favors small, auditable, least-privilege changes:

- deterministic dev deployment instead of manual promotion,
- readiness-focused validation instead of flaky deep probes,
- PR-review/admin enforcement on `main`,
- no normal production test bypass,
- removal of unused GitHub environments,
- explicit evidence PRs for remote-setting changes.

No secret values were exposed or required for these decisions.

# Production Readiness & Release-Gate Roadmap

**Author:** Richard (`code-puppy-824f08`)  
**Date:** 2026-04-24  
**Status:** Active execution roadmap (updated 2026-04-26 after prod evidence pass + current-main deploy retry)  
**Goal:** Get the Azure Governance Platform production-ready, fully functional, compliant, and able to pass the release-gate arbiter with evidence instead of wishful thinking.

---

## Executive summary

Current strict verdict: **NOT READY**.

Three independent assessments were used to build this roadmap:

1. **Planning Agent** — prioritized the production-readiness workstreams
2. **Pack Leader** — mapped what can run in parallel vs what must be serialized
3. **Release Gate Arbiter** — gave the adversarial gate view and named the highest-risk blockers

The repo already has good foundations:

- supply-chain controls in `deploy-production.yml`
- browser smoke infrastructure in CI/tests
- sync recovery verification tooling
- tenant auth investigation tooling
- existing release-gate docs/runbooks

But the current release story still has five material blockers:

1. attestation verification in the production deploy path is not yet deterministic enough to trust
2. browser smoke is still advisory instead of a required merge/release gate
3. production sync/tenant auth remains unresolved (`918b` / `0gz3`)
4. rollback/waiver evidence is too prose-heavy and operationally incomplete
5. release docs/evidence drift undermines trust in the packet

This roadmap turns those into tracked execution work.

### Latest verified state (2026-04-26)
- Production App Service is still running image `ghcr.io/htt-brands/azure-governance-platform:6a7306a`, which predates commit `5647fab` (`fix: skip unconfigured tenants in scheduled sync`).
- Read-only prod evidence confirmed runtime is **secret Key Vault mode** (`USE_OIDC_FEDERATION=false`), not OIDC mode.
- The five noisy tenants behind `918b` are all active + `use_oidc=true` but have no `client_secret_ref`; under current repo logic they are **scheduler-ineligible** and should be skipped.
- Fresh production workflow run `24961635696` on current `main` (`a929791`) failed in **QA Gate**, so deploy never happened and prod is still stale.
- The immediate blocker is now concrete instead of mystical: fix the four QA regressions, rerun deploy, then verify prod burn-down honestly.

---

## Current arbiter blockers

### 1. Attestation verification determinism
**Issue:** `azure-governance-platform-g1cc`  
**Why it matters:** a strict gate does not care that supply-chain controls exist in theory if the production workflow still fails closed unpredictably.

**Required outcome:**
- deterministic attestation verification source of truth
- successful end-to-end run on `main`
- evidence linking policy → digest → verification → deploy

**Current state:** workflow has already been pivoted toward deterministic attestation verification, but the newest proof attempt (`24961635696`) died in QA before the deploy/attestation stages even ran. So this blocker is now split into two sub-steps: restore QA to green, then prove the deploy path end to end.

### 2. Browser/UI gate still advisory
**Issue:** `azure-governance-platform-aiob`  
**Why it matters:** the repo already shipped a broken UI through strong process gates because the browser-level checks were not a required signal.

**Required outcome:**
- browser smoke stable enough to hard-gate
- `continue-on-error` removed from CI gate path
- branch protection/ruleset updated accordingly

### 3. Production sync / tenant auth confidence hole
**Issues:** `azure-governance-platform-918b`, `azure-governance-platform-0gz3`  
**Why it matters:** prod can be technically deployed and still functionally broken in the data plane.

**Required outcome:**
- classify the real auth path in prod
- explain the repeated fallback noise with evidence
- verify sync recovery and alert burn-down from real prod data

### 4. Rollback / waiver readiness is not machine-verifiable enough
**Issues:** `azure-governance-platform-213e`, `azure-governance-platform-j875`  
**Why it matters:** a rollback plan with stale commands, prose-only waivers, or one-human ownership is weak evidence.

**Required outcome:**
- named second rollback human or explicit current-state coverage artifact
- machine-verifiable waiver trail
- rollback docs aligned with live workflow/resource names

### 5. Release packet coherence drift
**Issues:** `azure-governance-platform-3ogi`, `azure-governance-platform-0nup`  
**Why it matters:** contradictions between docs, workflow truth, and runbooks reduce confidence in every other claim.

**Required outcome:**
- one coherent evidence bundle
- current versions/resource names
- explicit blocker/non-blocker narrative

---

## Priority workstreams

## Workstream A — Harden deploy attestation verification
**Primary issue:** `azure-governance-platform-g1cc`  
**Priority:** P1  
**Execution mode:** parallel-safe, but release-critical

### Scope
- confirm the current `deploy-production.yml` deterministic verification path is the intended source of truth
- fix the current QA blockers preventing the workflow from even reaching deploy
- produce one successful mainline proof run with evidence

### Immediate resume point
- inspect failing run `24961635696`
- fix these four failing tests so QA can clear again:
  - `tests/unit/test_browser_smoke_ci_rollout.py::TestBrowserSmokeCiWorkflow::test_ci_workflow_contains_browser_smoke_job`
  - `tests/unit/test_browser_smoke_ci_rollout.py::TestBrowserSmokeCiDocs::test_rollout_doc_covers_soak_and_branch_protection`
  - `tests/unit/test_investigate_sync_tenant_auth.py::test_classifies_oidc_runtime_from_app_settings`
  - `tests/unit/test_investigate_sync_tenant_auth.py::test_render_markdown_includes_table_and_counts`
- rerun production workflow only after those regressions are green locally and in CI

### Done means
- one recent run proves SLSA + SBOM verification succeeded for the deployed digest
- workflow behavior is deterministic enough for arbiter review
- evidence is captured for the release packet

---

## Workstream B — Promote browser smoke into a real gate
**Primary issue:** `azure-governance-platform-aiob`  
**Priority:** P1  
**Execution mode:** highly parallelizable

### Scope
- finish remaining browser-smoke hardening work
- validate scheduler-isolation and auth-stable fixture behavior remain correct
- remove advisory behavior and prepare required-check promotion
- keep artifact hygiene and failure clarity intact

### Done means
- browser smoke is stable across soak runs
- CI no longer treats it as optional noise
- a broken page/partial/console-error regression would block promotion

---

## Workstream C — Resolve prod tenant auth ambiguity and verify sync recovery
**Primary issues:** `azure-governance-platform-918b` → `azure-governance-platform-0gz3`  
**Priority:** P1  
**Execution mode:** serialized lead-investigator flow

### Scope
- gather prod evidence using:
  - `scripts/investigate_sync_tenant_auth.py`
  - `scripts/verify_sync_recovery_report.py`
  - `docs/runbooks/sync-recovery-verification.md`
- preserve the now-established explanation that prod is secret mode + stale image, not some abstract auth mystery
- deploy a post-`5647fab` image to production
- only then verify alert burn-down and successful intended syncs

### Done means
- `918b` has a real explanation, not a hypothesis cloud
- prod is no longer running stale image `6a7306a`
- `0gz3` has a report-backed verification outcome after a successful modern deploy
- release packet can honestly describe sync health in production

**Note:** beads currently records a `discovered-from` linkage from `918b` to `0gz3`, but the intended execution order is still **solve/explain `918b` before claiming `0gz3` complete**.

---

## Workstream D — Fix rollback / waiver evidence quality
**Primary issues:** `azure-governance-platform-213e`, `azure-governance-platform-j875`  
**Priority:** P1  
**Execution mode:** parallel-safe

### Scope
- name the second rollback human before waiver expiry
- migrate waiver evidence out of prose-only state
- reconcile rollback docs with current workflow/resource names
- ensure release docs can point at one authoritative rollback/waiver source

### Done means
- no single-human operational fragility is being hand-waved
- rollback commands are current and credible
- waiver evidence is machine-verifiable and reviewable

---

## Workstream E — Assemble the release evidence bundle and rehearse the gate
**Primary issue:** `azure-governance-platform-0nup`  
**Priority:** P1  
**Execution mode:** serialized late-stage aggregation

### Scope
- build an evidence index covering:
  - supply chain
  - browser/UI gate
  - prod sync verification
  - rollback readiness
  - waivers / ownership / exceptions
- reconcile release packet docs and live references
- perform one internal release-gate rehearsal against current `main`

### Depends on
- `azure-governance-platform-g1cc`
- `azure-governance-platform-aiob`
- `azure-governance-platform-0gz3`
- `azure-governance-platform-213e`
- `azure-governance-platform-j875`
- `azure-governance-platform-3ogi`

### Done means
- an internal reviewer can inspect one evidence packet and understand the release story without hunting across ten documents and three issue threads like a doomed archaeologist

---

## Workstream F — Reconcile docs/evidence drift
**Primary issue:** `azure-governance-platform-3ogi`  
**Priority:** P2  
**Execution mode:** parallel-safe

### Scope
- reconcile README version/resource references
- reconcile release-dossier docs with workflow truth
- remove stale claims that weaken the packet

### Done means
- docs tell the same story as code, workflow, and runbooks

---

## Dependency / sequencing map

### Can run in parallel now
- `azure-governance-platform-g1cc`
- `azure-governance-platform-aiob`
- `azure-governance-platform-213e`
- `azure-governance-platform-j875`
- `azure-governance-platform-3ogi`
- `azure-governance-platform-xkgp`

### Must be serialized
- `azure-governance-platform-918b` before meaningful closure of `azure-governance-platform-0gz3`
- `azure-governance-platform-0nup` after its blocker issues have real evidence attached

### Coordination guidance
- **Pack approach is good for:** browser/CI work, docs cleanup, attestation workflow investigation, low-risk hygiene
- **Single lead is better for:** prod auth/sync evidence interpretation and final release-readiness call

---

## Evidence required before calling this READY

Minimum evidence expected for a credible re-review:

1. successful deploy-path attestation verification with receipts
2. browser-smoke promoted from advisory to real gate behavior
3. prod sync recovery report based on actual exported evidence
4. tenant auth investigation report explaining the fallback pattern
5. rollback/waiver evidence aligned with current operational truth
6. coherent release packet linking all of the above

If any of those are missing, the repo may be improved, but it is still not honestly “release-gate ready.”

---

## Recommended execution moves

### Immediate next 3
1. Fix the four QA regressions exposed by run `24961635696`, then rerun production deploy on current `main`
2. Once a deploy actually lands, re-run `azure-governance-platform-0gz3` verification from fresh prod evidence
3. In parallel, keep `azure-governance-platform-aiob`, `azure-governance-platform-213e`, and `azure-governance-platform-j875` moving so release readiness does not become a one-thread traffic jam

### Near-term after that
4. Confirm prod is off image `6a7306a` and that fallback spam burns down for the five misconfigured tenants
5. Reconcile release docs/resource/version drift (`3ogi`)
6. Assemble the first full evidence bundle (`0nup`)

---

## Issue map created/confirmed in this session

- `azure-governance-platform-g1cc` — attestation verification deterministic + arbiter-aligned
- `azure-governance-platform-0nup` — release evidence bundle and gate rehearsal
- `azure-governance-platform-j875` — migrate rollback waiver + rollback docs to machine-verifiable current-state artifacts
- `azure-governance-platform-3ogi` — reconcile release-dossier / README / live references drift
- `azure-governance-platform-aiob` — browser gate umbrella
- `azure-governance-platform-918b` — prod tenant auth fallback investigation
- `azure-governance-platform-0gz3` — sync recovery verification
- `azure-governance-platform-213e` — second rollback human
- `azure-governance-platform-xkgp` — datetime cleanup

---

## Exit condition for this roadmap

This roadmap is complete when the arbiter can look at the repo and say, with a straight face and actual receipts:

- deploy provenance is trustworthy
- the product works in a browser
- production sync behavior is understood and healthy
- rollback/change ownership is credible
- the release packet is coherent

Until then: keep chewing.

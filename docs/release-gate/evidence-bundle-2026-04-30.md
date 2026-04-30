# Release Evidence Bundle — 2026-04-30

> **Purpose:** Single index of the evidence required to justify a strict
> production release-gate pass against the current state of `main`.
> This bundle closes bd `azure-governance-platform-0nup` (Workstream E
> of `docs/plans/production-readiness-and-release-gate-roadmap-2026-04-24.md`).
>
> **Submitter:** code-puppy (autonomous, on behalf of Tyler Granlund)
> **Bundle artifact ref:** `htt-brands/control-tower @ main @ f91f4d7`
> **Pyproject version:** `2.5.0` (next release: `v2.5.1`, prospective RTM at
> `docs/release-gate/rtm-v2.5.1-DRAFT.md`)
> **Rehearsal verdict:** `docs/release-gate/verdicts/rehearsal-2026-04-30-internal.md`
> **Prior external verdict:** `docs/release-gate/verdicts/rga-2026-04-22-azgov-v2.5.0-02.md` → `CONDITIONAL_PASS` (staging only)

---

## 0. Executive summary

All five blockers named in the prior external arbiter verdict and the
2026-04-24 production-readiness roadmap are now closed:

| Prior blocker | Closing bd | Status |
|---|---|---|
| Attestation verification not deterministic | `g1cc` | ✅ closed 2026-04-29 |
| Browser/UI gate still advisory | `aiob` (+ 5 sub-issues) | ✅ closed 2026-04-29 |
| Prod sync / tenant auth confidence hole | `918b`, `0gz3` | ✅ closed 2026-04-29 |
| Rollback / waiver readiness not machine-verifiable | `j875`, `213e`, `q46o` | ✅ closed 2026-04-30 |
| Release packet coherence drift | `3ogi` | ✅ closed 2026-04-25 |

Material additions since the prior verdict that strengthen the gate:

- **Auto-rollback** in production deploy workflow (bd `39yp`, commit `d9d9d88`) — health-gate failure auto-restores previous-good digest.
- **Bus-factor 1 → 2** with Dustin Boyd onboarded as second rollback human (bd `213e`, commit `64515a5`); waiver YAML status `active → resolved` 53 days ahead of original expiry.
- **Production GitHub environment** now has required reviewers (`t-granlund` + `htt-db`) + `main`-only branch policy (bd `gm9h`, same commit).
- **Six domain boundary READMEs** shipped (Phase 1 of `PORTFOLIO_PLATFORM_PLAN_V2.md` §5) — 32d8 / fos1 / htnh / c10e / ewdp / sl01.
- **Ten oversized-file refactors** (Phase 1.5) — bu72, gvpt, lq11, oknl, qb8u, uxzr, 2l4h, a3oq, fbx8, wnpf.
- **Operational continuity docs** — `RUNBOOK.md`, `AGENT_ONBOARDING.md`, `docs/dr/rto-rpo.md`, `docs/dr/second-rollback-human-checklist.md`.

**Internal rehearsal verdict:** `CONDITIONAL_PASS` for v2.5.1 production-gate
contingent on (1) Tyler dispatching a fresh successful prod deploy off
current `main` and (2) `SECRETS_OF_RECORD.md` (bd `9lfn`) authored.
See `docs/release-gate/verdicts/rehearsal-2026-04-30-internal.md` for
pillar-by-pillar walkthrough.

---

## 1. Supply-chain receipts

**Primary closing bd:** `g1cc` — "ci/release: make deploy-production attestation verification deterministic and arbiter-aligned"

**Verification policy (machine-readable):** `arbiter/policies/verify.yaml`

**Workflow gate:** `.github/workflows/deploy-production.yml`
- Job: **QA Gate** — runs full test matrix before any image build.
- Job: **Build & Push to GHCR** — produces image + SLSA attestation + cosign signature + SBOM.
- Job: **Deploy to Production** — verifies attestations against deployed digest before mutating App Service container config; auto-rolls back on health-gate failure (bd `39yp`).

**Last successful proof run on `main`:** [run `25131829042`](https://github.com/HTT-BRANDS/control-tower/actions/runs/25131829042) — 2026-04-29 20:21:53 UTC

| Job | Conclusion | Duration |
|---|---|---|
| QA Gate | ✅ success | 3m 15s |
| Security Scan | ✅ success | 1m 5s |
| Build & Push to GHCR | ✅ success | 1m 10s |
| Deploy to Production | ✅ success | 3m 10s |
| Production Smoke Tests | ✅ success | 31s |
| Notify Teams | ✅ success | 3s |

**Deployed image (current prod state):**
```
ghcr.io/htt-brands/azure-governance-platform@sha256:a76f3eeb9f7c0f28b27c196a8f9c8cf06368fc47875c51ea7a95f0bbbdd680e4
```
Resolves to commit `3c9c317` (parent of the 2026-04-30 rebrand cutover). See §6.1 below for stale-image disclosure.

**Adjacent supply-chain hygiene closures:**
- bd `7mk8` — SLSA L3 + Sigstore cosign + SBOM in production workflow.
- bd `dq49` — SHA-pin attest-* + cosign-installer + sbom-action.
- bd `my5r` — env-delta.yaml schema validator + literal-rejection gate.

---

## 2. Browser / UI gate proof

**Primary closing bd:** `aiob` — "meta(ci): no frontend smoke / visual-regression tests in CI — shipped broken UI through all gates"

**Sub-issues closed:**
- `aiob.1` — canonical browser session fixture
- `aiob.2` — deterministic seeded/empty-state contract for browser smoke routes
- `aiob.3` — browser smoke coverage for critical pages and HTMX partials
- `aiob.4` — CI browser-smoke job with sanitized failure artifacts and soak-based promotion
- `aiob.5` — RBAC negative coverage for browser-gated routes

**Workflow:** `.github/workflows/ci.yml` — `browser-smoke` job is now a
required check, no `continue-on-error`. Branch protection on `main`
enforces.

**Surface:** `tests/browser_smoke/` (Playwright). Recent run cadence on
push commits: ~3-4 minutes per run, soak-stable across the last 20+
commits (verified via `gh run list --workflow=ci.yml --branch=main`).

**Adjacent stabilization closure:**
- bd `mf9r` — disable background scheduler during browser/e2e app startup.

---

## 3. Production sync verification

**Primary closing bds:** `918b` (investigation) → `0gz3` (post-deploy verification)

**Investigation receipts:**
- `scripts/investigate_sync_tenant_auth.py` — auth-path classifier
- `scripts/verify_sync_recovery_report.py` — recovery report generator
- `scripts/collect-sync-tenant-auth-evidence.sh` — evidence collection driver
- `docs/runbooks/sync-recovery-verification.md` — runbook

**Final explanation (for the record):** the prod fallback noise had
two compounding causes:
1. Prod was running stale image `6a7306a` (predated commit `5647fab` which
   added the "skip unconfigured tenants" guard).
2. Five tenants in prod had `use_oidc=true` but no `client_secret_ref`,
   so under post-`5647fab` logic they correctly become scheduler-ineligible
   and are skipped — eliminating the noise.

**Adjacent closures from the same investigation:**
- bd `tbvs` — prod sync jobs failing with 222 active alerts (root-caused).
- bd `tg2z` — Riverside batch and DMARC alerts after `0gz3` (residual noise classification).

---

## 4. Rollback readiness

**Primary closing bds:** `j875` (machine-verifiable waiver) + `213e` (second human) + `q46o` (post-auto-rollback checklist rewrite) + `gm9h` (env protection)

**Source-of-truth artifact:** `docs/release-gate/rollback-current-state.yaml`

```yaml
waiver:
  status: resolved          # was: active
  resolved_on: "2026-04-30"
  current_authorized_humans:
    - Tyler Granlund
    - Dustin Boyd            # added 2026-04-30
  original_expires_on: "2026-06-22"
  machine_verification:
    requires_min_authorized_humans: 2
```

**Rollback automation:** `deploy-production.yml` `Health gate with
auto-rollback` step (bd `39yp`, commit `d9d9d88`):
- Captures previous-good digest pre-deploy.
- Polls `/health` for 5 minutes post-deploy.
- On failure: auto-restores previous digest + restarts App Service + posts incident notification to Teams.
- On success: emits structured run-summary used by `0nup` evidence pulls.

**Manual rollback path (residual scenarios):**
- `docs/runbooks/disaster-recovery.md` §A.4 — auto-rollback failed, manual recovery.
- `docs/runbooks/disaster-recovery.md` §B.3 — point-in-time database restore.
- `docs/runbooks/disaster-recovery.md` §C.3 — Key Vault soft-delete recovery.

**Second-human provisioning evidence (Dustin Boyd):**

| Plane | Access | Verification |
|---|---|---|
| Azure RBAC | Owner + Contributor on `/subscriptions/32a28177-...` | `az role assignment list --assignee 22ddf06b-...` |
| Key Vault `kv-gov-prod` | Full access policy (legacy auth model) | KV access policy count 3 → 4, granted commit `2e51d5a` |
| GitHub `HTT-BRANDS` org | `admin` role since 2025-04-28 | `gh api /orgs/HTT-BRANDS/memberships/htt-db` |
| `control-tower` repo | `admin` permission | `gh api /repos/HTT-BRANDS/control-tower/collaborators/htt-db/permission` |
| `production` environment | Required reviewer | `gh api /repos/HTT-BRANDS/control-tower/environments/production` |
| GHCR | Implicit via org `read:packages` | n/a |

**Production environment protection (bd `gm9h`):**
- `required_reviewers: [t-granlund, htt-db]`
- `deployment_branch_policy: main`-only
- `prevent_self_review: false`
- `wait_timer: 0`

**Adjacent rollback-discipline artifacts:**
- `docs/dr/rto-rpo.md` — quantitative RTO/RPO targets (bd `0dhj`).
- `docs/dr/second-rollback-human-checklist.md` — onboarding checklist (bd `q46o`, all §5 closure criteria met).
- `RUNBOOK.md` — operational entry point for Tyler-unavailable scenarios (bd `68g7`).
- `AGENT_ONBOARDING.md` — new-engineer pickup doc (bd `2au0`).

---

## 5. Waivers / exceptions / open carve-outs

**No active blocking waivers** as of 2026-04-30. The single-human
rollback waiver was `resolved` (not waived) by closing `213e`.

**Open issues that are explicitly NOT v2.5.1 prod-gate blockers:**

| bd ID | Why it's not a blocker | Disposition |
|---|---|---|
| `9lfn` (P1) | Tyler-only authorship of `SECRETS_OF_RECORD.md`. Dustin already has direct KV/storage access, so it's no longer a bus-factor blocker — it's a future-operator onboarding aid. | Tracked for next session; tagged in RTM-DRAFT §3 |
| `mvxt` (P2, mitigated) | Compensating control (cold-start warmup + retry) shipped in `68c0baa`. Root cause needs Azure Portal access. SLO not at risk. | Stays open, documented as non-blocking in rtm-v2.5.1-DRAFT.md §2 |
| `uchp` (P2) | Q3 2026 DR test cycle, due 2026-07-31. Will absorb Dustin's formal hands-on tabletop. | Date-gated, post-release |
| `l96f` (P3) | JWT iss claim rotation post-rebrand. Logs all users out — needs coordinated session window. | Deferred, non-blocking |
| `rtwi` (P3) | Stop domain-intelligence App Service at 60-day zero-traffic mark (~2026-05-17). Separate project, separate RG. | Date-gated, post-release |
| `m4xw` (P4) | Quarterly audit-log archive automation. Trigger 2026-07-01. | Date-gated, post-release |

---

## 6. Honest disclosures (what an arbiter should know)

### 6.1 Production is running stale image

The successful 2026-04-29 deploy (run `25131829042`) pinned prod to
`ghcr.io/htt-brands/azure-governance-platform@sha256:a76f3eeb...`
(commit `3c9c317`). Since then:
- `a92cf9b` cost analysis (docs only)
- `d9d9d88` auto-rollback (workflow only — does not affect runtime)
- `a2a18bf` checklist rewrite (docs only)
- `de13672` session log (docs only)
- `2e51d5a` Dustin's KV access (Azure-side, not container)
- `64515a5` 213e closure + rollback YAML (docs + governance)
- `f91f4d7` SESSION_HANDOFF (docs only)

Nothing in the un-deployed delta is runtime-affecting. The `htt-brands/azure-governance-platform` image path is the pre-rebrand alias; GHCR redirects post-rebrand from this path are still resolving correctly because pull-by-digest is content-stable.

**Recommendation:** the next prod deploy off current `main` will (a) refresh the image to the rebranded GHCR path (`htt-brands/control-tower`) and (b) provide the v2.5.1 prod-gate evidence. This is a Tyler-only `workflow_dispatch` action.

### 6.2 RTM-v2.5.1 is still a draft

`docs/release-gate/rtm-v2.5.1-DRAFT.md` was started 2026-04-23 with 5
rows. ~50 additional bd issues have closed since. The draft is being
updated in companion commit (separate from this bundle).

### 6.3 First fresh post-rebrand deploy will be the real proof

Auto-rollback (bd `39yp`) has been merged but has not yet been exercised
under a real failed-deploy scenario. The first scheduled formal exercise
is bd `uchp` (Q3 2026 DR test cycle). Until then, auto-rollback's
behavior is unit-tested + workflow-validated but not field-tested.

### 6.4 SQL Entra admin is unset

Discovered during 213e provisioning: `sql-gov-prod-mylxq53d` has no Entra
admin configured. Not a blocker — management-plane PITR (the §B.3 DR
scenario) only requires subscription Owner, which both rollback humans
hold. Data-plane queries against a restored DB during DR drill validation
would require an Entra admin to exist; deferred to bd `uchp`'s scope or
Tyler's discretion.

---

## 7. Rehearsal verdict pointer

A full pillar-by-pillar internal rehearsal mimicking the arbiter format
is recorded at:

→ **`docs/release-gate/verdicts/rehearsal-2026-04-30-internal.md`**

That document is the formal evidence for acceptance criterion #3 of bd
`0nup` ("one release rehearsal against [main]"). Summary:

| Pillar | Prior verdict | Internal rehearsal verdict |
|---|---|---|
| 1. Requirements Closure | CONDITIONAL_PASS (retroactive RTM) | PASS (prospective RTM in flight) |
| 2. Code Review | PASS | PASS |
| 3. Security | DEGRADED → PASS for staging | PASS |
| 4. Infrastructure | CONDITIONAL_PASS | CONDITIONAL_PASS (prod-stale-image §6.1) |
| 5. Stack Coherence | PASS | PASS |
| 6. Cost | PASS (with observation) | PASS (cost analysis bd `j6tq` closed) |
| 7. Maintenance & Operability | CONDITIONAL_PASS (single-operator risk) | PASS (bus-factor 1→2) |
| 8. Rollback | PASS | PASS (auto-rollback + 2 humans + machine-verifiable waiver) |

---

## 8. Cross-references

- **Roadmap:** `docs/plans/production-readiness-and-release-gate-roadmap-2026-04-24.md`
- **Prior verdict:** `docs/release-gate/verdicts/rga-2026-04-22-azgov-v2.5.0-02.md`
- **Prior submission:** `docs/release-gate/submission-v2.5.0.md` (historical)
- **Current waiver state:** `docs/release-gate/rollback-current-state.yaml`
- **Prospective RTM:** `docs/release-gate/rtm-v2.5.1-DRAFT.md`
- **Rehearsal verdict:** `docs/release-gate/verdicts/rehearsal-2026-04-30-internal.md`
- **Verify policy:** `arbiter/policies/verify.yaml`
- **Strategic plan:** `PORTFOLIO_PLATFORM_PLAN_V2.md`

---

*Bundle assembled by code-puppy `code-puppy-661ed0` on 2026-04-30.
Closes acceptance criterion #1 of bd `azure-governance-platform-0nup`.*

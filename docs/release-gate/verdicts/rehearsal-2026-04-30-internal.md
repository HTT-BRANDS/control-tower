# Internal Release-Gate Rehearsal — 2026-04-30

**Run ID:** `internal-rehearsal-2026-04-30-azgov-v2.5.1-pre-cut`
**Submitter:** `code-puppy-661ed0` (Richard 🐶) on behalf of Tyler Granlund
**Artifact:** `htt-brands/control-tower @ main @ f91f4d7`
**Pyproject version at rehearsal time:** `2.5.0` (next: `v2.5.1`)
**Mode:** internal rehearsal — adversarial walk-through mimicking arbiter
verdict format. Not an external arbiter run.
**Closes:** acceptance criterion #3 of bd `azure-governance-platform-0nup`.
**Companion bundle:** `docs/release-gate/evidence-bundle-2026-04-30.md`
**Prior external verdict:** `docs/release-gate/verdicts/rga-2026-04-22-azgov-v2.5.0-02.md` (`CONDITIONAL_PASS` to staging only)

---

## Verdict: `CONDITIONAL_PASS`

Production-gate AUTHORIZED for the next prod deploy off current `main`,
contingent on the two soft conditions in §"Conditions" below.

The five blockers from the prior verdict and the 2026-04-24 roadmap are
all closed. The conditions are operational/freshness-flavored, not
structural.

---

## Pillar verdicts

### 1. Requirements Closure → `PASS`

Prior: `CONDITIONAL_PASS` ("RTM retroactive, accepted one-time").

Now:
- `docs/release-gate/rtm-v2.5.1-DRAFT.md` exists as a **prospective** RTM,
  started on 2026-04-23 the day the last v2.5.0 carve-out (`7mk8`) closed.
- Bidirectional linkage discipline is in place — every closed bd ticket
  in the v2.5.1 window has commit SHAs in its close comment, and the RTM
  rows reference the same SHAs.
- The draft is being expanded in a companion commit to cover the ~50 bd
  closures since the original 5-row draft.

The "prospective traceability discipline" condition from the prior
verdict is satisfied as a practice; the artifact will be flipped from
`-DRAFT` to accepted at v2.5.1 cut.

### 2. Code Review → `PASS`

Prior: `PASS`.

Now: unchanged. All work lands on `main` via direct commits with
descriptive messages, pre-commit hooks (ruff sort/lint/format,
detect-secrets, env-delta validator) all gating, and 1-issue-per-commit
discipline preserved across the ~60 commits since the prior verdict.

Spot-check sample (this session):
- `2e51d5a` ops(dr): provision Dustin Boyd's Azure access + verify directory state
- `64515a5` ops(dr): close 213e — Dustin Boyd onboarded as second rollback human
- `d9d9d88` ops(release): auto-rollback on failed health gate in production deploy

Each is scoped, references the closing bd, cites strategic-plan section
where applicable, and links related artifacts.

### 3. Security → `PASS`

Prior: `DEGRADED → PASS for staging` (Scanner Group A waived 60d, expiring 2026-06-21).

Now:
- bd `7mk8` (SLSA L3 + Sigstore cosign + SBOM in production workflow) ✅ closed 2026-04-23
- bd `dq49` (SHA-pin attest-* + cosign-installer + sbom-action) ✅ closed 2026-04-23
- bd `my5r` (env-delta.yaml schema validator + literal-rejection gate) ✅ closed 2026-04-23
- bd `g1cc` (deterministic attestation verification in `deploy-production.yml`) ✅ closed 2026-04-29
- Scanner Group A (`gitleaks`, `trivy fs`, `osv-scanner`, `semgrep`, `checkov`, `conftest`, `infracost`) wired in `.github/workflows/security-scan.yml`.
- Production environment now has required reviewers + main-only branch policy (bd `gm9h` closed 2026-04-30).

The five conditions the prior verdict named for advisory→blocking
promotion (deterministic Scanner Group A, env-delta validator, second
rollback human, IaC drift-detection, RTM prospective discipline) are
**all met**.

### 4. Infrastructure → `CONDITIONAL_PASS`

Prior: `CONDITIONAL_PASS`.

Now: still `CONDITIONAL_PASS` — but for a different reason, and the
condition is *operational* not *structural*.

- bd `x692` (scheduled Bicep drift-detection) ✅ closed 2026-04-23
- bd `q8lt` (Bicep Drift Detection workflow scope mismatch) ✅ closed 2026-04-29
- bd `3flq` (Database Backup OIDC id-token permission) ✅ closed 2026-04-29
- bd `jzpa` (Database Backup workflow secrets) ✅ closed 2026-04-30
- bd `fifh` (Database Backup workflow broken `mda590/teams-notify` action) ✅ closed 2026-04-28

**The conditional:** production is still running the
2026-04-29 image (`htt-brands/azure-governance-platform@sha256:a76f3eeb...`,
commit `3c9c317`). All commits since are docs/governance/CI-only — none
are runtime-affecting — so prod isn't *broken*, just *behind*. A fresh
deploy off current `main` would (a) refresh prod onto the rebranded GHCR
path (`htt-brands/control-tower`) and (b) provide the v2.5.1 prod-gate
proof run. See evidence-bundle §6.1.

### 5. Stack Coherence → `PASS`

Prior: `PASS`.

Now: `PASS`, with active hygiene wins:
- bd `0dsr` (Control Tower repo/GHCR/Pages cutover) ✅ closed 2026-04-30
- bd `re42` (rebrand long-tail residue cleanup) ✅ closed 2026-04-30
- bd `3ogi` (release-dossier / README / live version reference reconciliation) ✅ closed 2026-04-25
- 6 domain boundary READMEs landed under `domains/` (Phase 1 of `PORTFOLIO_PLATFORM_PLAN_V2.md` §5) — see closures `32d8`, `fos1`, `htnh`, `c10e`, `ewdp`, `sl01`.
- 10 file-size refactors landed (Phase 1.5) — `bu72`, `gvpt`, `lq11`, `oknl`, `qb8u`, `uxzr`, `2l4h`, `a3oq`, `fbx8`, `wnpf`.

`core_stack.yaml` is still the source of truth for the version pin and
will be bumped at v2.5.1 cut.

### 6. Cost → `PASS`

Prior: `PASS (with observation)`.

Now: `PASS` with the observation cleared.
- bd `j6tq` (model App Service B1 vs Container Apps consumption with
  current scheduler load) ✅ closed 2026-04-30. Documented analysis at
  `docs/cost/app-service-vs-container-apps-2026-04-30.md`.
- Conclusion: B1 plan is correct for current load; Container Apps
  consumption would be more expensive at the platform's scheduler
  duty cycle. Re-evaluate annually.

### 7. Maintenance & Operability → `PASS`

Prior: `CONDITIONAL_PASS` (single-operator risk flagged).

Now: **the bus-factor metric flipped from 1 → 2** (PORTFOLIO_PLATFORM_PLAN_V2.md §8 Success Metrics).

- bd `213e` (name a second rollback human) ✅ closed 2026-04-30. Dustin
  Boyd onboarded with full Azure RBAC + KV access policy + GitHub org
  admin + repo admin + production environment required-reviewer status.
- bd `q46o` (post-auto-rollback checklist rewrite) ✅ closed 2026-04-29
  — checklist all 7 §5 closure criteria checked.
- bd `2au0` (`AGENT_ONBOARDING.md`) ✅ closed 2026-04-28
- bd `68g7` (`RUNBOOK.md`) ✅ closed 2026-04-28
- bd `0dhj` (`docs/dr/rto-rpo.md` quantitative targets) ✅ closed 2026-04-28
- bd `gm9h` (production environment protection rules) ✅ closed 2026-04-30

Single-operator risk is no longer an active condition. Auto-rollback
(bd `39yp`) materially narrows the manual-recovery role.

### 8. Rollback → `PASS`

Prior: `PASS`.

Now: substantially stronger:
- **Auto-rollback** in `deploy-production.yml` (bd `39yp`, commit
  `d9d9d88`). Health-gate-failure → previous-good digest auto-restore.
- **Machine-verifiable waiver state** in
  `docs/release-gate/rollback-current-state.yaml`. `waiver.status:
  active → resolved`. `current_authorized_humans: [Tyler, Dustin]`.
  `machine_verification.requires_min_authorized_humans: 2`.
- **Two-human cover** with both humans holding production environment
  required-reviewer status.
- **Complete DR runbook** at `docs/runbooks/disaster-recovery.md`
  with §A.4 / §B / §C / §F scenarios.
- **First scheduled DR exercise** bd `uchp` (Q3 2026, due 2026-07-31) —
  will absorb Dustin's formal hands-on tabletop.

---

## Conditions (2 — soft, neither structural)

### Condition 1: Fresh successful prod deploy off current `main`

**Why:** the most recent successful deploy was 2026-04-29 against SHA
`3c9c317`. The repo has had ~10 commits since (all docs/governance — no
runtime-affecting changes), but the deploy run is the natural
v2.5.1-prod-gate evidence anchor and would also refresh the GHCR image
path from pre-rebrand to post-rebrand.

**Action:** Tyler dispatches `deploy-production.yml` against `main`.

**Acceptance:** all 6 jobs (QA Gate, Security Scan, Build & Push to
GHCR, Deploy to Production, Production Smoke Tests, Notify Teams) green.

**Effort:** ~10 minutes wall-clock + ~5 minutes Tyler approval review.

### Condition 2: `SECRETS_OF_RECORD.md` authored

**Why:** bd `9lfn` is Tyler-only authorship. With Dustin's full
KV/storage access already provisioned, this is no longer a *bus-factor*
blocker — it's a *future-operator-onboarding* aid. But the prior
arbiter would expect the artifact to exist before granting full
production-gate confidence.

**Action:** Tyler authors `SECRETS_OF_RECORD.md` listing every credential
location in KV and storage, with rotation cadence and ownership.

**Acceptance:** file exists; `RUNBOOK.md`'s 🔴 TYLER-ONLY markers
referencing it are filled in.

**Effort:** ~30 minutes Tyler-time.

---

## Non-blocking findings

### N-1 (low) — RTM-v2.5.1 still in `-DRAFT` form

The prospective RTM has 5 rows in its current state but ~50 bd issues
have closed since it was started. A companion commit alongside this
rehearsal expands the RTM to reflect actual landed work. Flip to
non-DRAFT happens at v2.5.1 cut, per the file's §5 checklist.

### N-2 (low) — auto-rollback has not been field-tested

bd `39yp`'s implementation is unit-tested + workflow-validated but
hasn't been exercised under a real failed-deploy scenario. First formal
exercise: bd `uchp` Q3 2026 DR test cycle. Acceptable risk because the
implementation follows the deploy-production.yml-style curl pattern
already in production use.

### N-3 (info) — SQL Entra admin not set

`sql-gov-prod-mylxq53d` has no Entra admin configured. Discovered
during 213e provisioning. Not a v2.5.1 prod-gate blocker — management-
plane PITR (the §B.3 scenario) works via subscription Owner, which both
rollback humans hold. Data-plane queries against a restored DB during
DR drill validation would require an Entra admin; deferred to Tyler's
judgment or absorbed by bd `uchp`.

### N-4 (info) — bd `mvxt` stays open

Compensating control shipped (cold-start warmup + retry). Root cause
needs Azure Portal access. Documented as non-blocking in
`rtm-v2.5.1-DRAFT.md` §2. SLO is not at risk.

### N-5 (info) — open carve-outs that are NOT v2.5.1 blockers

| bd ID | Reason |
|---|---|
| `9lfn` (P1) | Condition 2 above |
| `uchp` (P2) | Q3 2026 DR test, date-gated |
| `l96f` (P3) | JWT iss rotation, needs coordinated session window |
| `rtwi` (P3) | Date-gated 2026-05-17, separate project |
| `m4xw` (P4) | Date-gated 2026-07-01 |

---

## Recommended next moves

1. **Tyler:** dispatch `deploy-production.yml` off current `main`. ~10 min.
2. **Tyler:** author `SECRETS_OF_RECORD.md` (bd `9lfn`). ~30 min.
3. **At v2.5.1 cut:** bump `pyproject.toml` to `2.5.1`, flip
   `rtm-v2.5.1-DRAFT.md` to `rtm-v2.5.1.md` (status `Accepted`), update
   `core_stack.yaml`, update `env-delta.yaml`, promote `CHANGELOG.md`
   `[Unreleased]` to `[2.5.1]`, tag, run external arbiter for the actual
   verdict.

---

## Cross-references

- Companion bundle: `docs/release-gate/evidence-bundle-2026-04-30.md`
- Roadmap: `docs/plans/production-readiness-and-release-gate-roadmap-2026-04-24.md`
- Prior external verdict: `docs/release-gate/verdicts/rga-2026-04-22-azgov-v2.5.0-02.md`
- Strategic plan: `PORTFOLIO_PLATFORM_PLAN_V2.md`
- Rollback YAML: `docs/release-gate/rollback-current-state.yaml`
- Prospective RTM: `docs/release-gate/rtm-v2.5.1-DRAFT.md`

---

*Internal rehearsal authored by code-puppy `code-puppy-661ed0` on
2026-04-30. This is not an external arbiter run; the actual verdict for
v2.5.1 will come from the next external arbiter invocation against the
post-deploy artifact.*

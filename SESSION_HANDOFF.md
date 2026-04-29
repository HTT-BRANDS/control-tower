# Session Handoff — 2026-04-29

**Branch:** `main` (clean working tree, up to date with origin)
**Latest pushed HEAD at start of 2026-04-29 session:** `1a7e929`
**Latest pushed work commit before final handoff metadata:** `3134576` (run `git log -1` for the handoff commit itself)
**Former P1 chain:** `g1cc` → `918b` → `0gz3` is now closed; `0nup` remains the next release-evidence gate.

> **Read this first if you are inheriting the platform mid-flight.**
> This handoff doc replaces the 2026-04-26 single-session handoff. Today's
> session shifted the platform from incremental hygiene work to a unified
> strategic plan. The diff in mental model is large.

---

## 🧭 The strategic shift this session

We moved from "improve `azure-governance-platform`" to "this is one of five
sister repos that together form an unintentional Portfolio Operating
System for HTT Brands." Three documents were produced and pushed:

1. **[`CONTROL_TOWER_MASTERMIND_PLAN_2026.md`](./CONTROL_TOWER_MASTERMIND_PLAN_2026.md)** — V1 strategic plan (preserved as historical record).
2. **[`CONTROL_TOWER_MASTERMIND_PLAN_2026_REDTEAM.md`](./CONTROL_TOWER_MASTERMIND_PLAN_2026_REDTEAM.md)** — adversarial review by `epistemic-architect`. Identified 3 fatal flaws, 5 sequencing errors, 8 hidden assumptions, 12 missing items.
3. **[`PORTFOLIO_PLATFORM_PLAN_V2.md`](./PORTFOLIO_PLATFORM_PLAN_V2.md)** — revised strategic plan incorporating Tyler's accepted findings. **This is the active source of truth for strategic direction.** V1 should not be cited going forward.

`planning-agent` decomposed V2 into a `bd` issue tree:
- **21 issues filed** for Phases 0 cleanup, 0.5, 1, and 1.5 (~22 agent-hours)
- **41-43 issues drafted (NOT filed)** for Phases 2–6 (~143-152 agent-hours)
- **Critical path:** ~52-55 agent-hours end-to-end

---

## ✅ What got done this session (chronological)

### Continuation — 2026-04-29 afternoon/evening (commits `3c9c317` → `3134576`)
- Reproduced the production deploy QA gate locally on current `main`:
  `4047 passed, 1 deselected` for `tests/unit/ tests/integration/ -m "not visual"`.
- Dispatched and watched production workflow run `25131829042`; it completed
  end-to-end successfully on head `3c9c3177cdf5c1e01806f9bf166cbf552a1c345c`.
- Closed `g1cc` after verifying deterministic GitHub Attestations evidence for
  both SLSA (`https://slsa.dev/provenance/v1`) and SBOM
  (`https://spdx.dev/Document/v2.3`) predicates. Production `/health` returned
  `200 healthy`.
- Verified `918b`/`0gz3` production recovery after the fresh image landed:
  - Prod image digest: `sha256:a76f3eeb9f7c0f28b27c196a8f9c8cf06368fc47875c51ea7a95f0bbbdd680e4`.
  - Post-deploy SyncJobLog: costs, compliance, resources, and identity all
    completed with zero errors.
  - App Insights old tenant-auth/fallback signatures returned zero hits.
  - Five previously noisy tenants classified as scheduler-ineligible in
    `secret_keyvault` mode with no declared secret path.
  - Stale pre-deploy costs/compliance/resources/identity alerts were resolved
    with `resolved_by=code-puppy-661ed0/0gz3`; active alerts dropped `229 → 10`
    (below the 222 baseline).
  - Filed `tg2z` for the remaining unrelated Riverside batch / DMARC alerts.
  - Closed `918b` and `0gz3` in `bd`.
- Phase 1 domain boundary docs are now underway and unblocked:
  - `32d8` cost ✅ — added `domains/cost/README.md` and
    `domains/cost/DATA_CLASSIFICATION.md`; scoped validation `58 passed`.
  - `fos1` identity ✅ — added `domains/identity/README.md` and
    `domains/identity/DATA_CLASSIFICATION.md`; scoped validation `184 passed`.
  - `htnh` compliance ✅ — added `domains/compliance/README.md` and
    `domains/compliance/DATA_CLASSIFICATION.md`; scoped validation `234 passed`.
- `DATA_CLASSIFICATION.md` success metric advanced from `0/6` to `3/6`.
- Cleaned local production evidence artifacts after use; none were committed.


### Track D — Phase 0 hygiene (commit `41126f8`)
- `.venv/` rebuilt (`uv venv --clear && uv sync --dev --frozen`); pytest 9.0.3 alive; 12/12 health_data smoke passes; **4,192 tests collected** (was claiming 3,800).
- Dead `origin/staging` branch deleted (was 10 commits behind, 0 ahead).
- Pre-commit hooks reinstalled with correct path (was pointing at stale `~/dev/azure-governance-platform/` location). Side-find: `pre-commit` is missing from `pyproject.toml` dev deps; documented in commit message.
- `INFRASTRUCTURE_END_TO_END.md` honesty pass — date, status banner, test count corrected; rebuilt §11 to surface live P1+P2 bd blockers.
- `CHANGELOG.md` + `WIGGUM_ROADMAP.md` got pointer-to-truth banners directing readers to live state.
- `mvxt` updated with staging-green-after-9-fails evidence + monitoring plan.

### Track C — Adversarial review (commit `c87a488`)
- `epistemic-architect` red-teamed V1 plan.
- Tyler's calls: 1c (no IP pause; framing handled via sanitization) · 2a (sanitize PE-adversarial language) · 3b (kill "Control Tower" name; 5 candidates evaluated) · 4c (hybrid Phase 1↔2 sequencing) · 5a (revise to V2 then send to planning-agent).
- V2 plan written with all accepted findings. New phases (-1 framing alignment, 0.5 continuity), new D-decisions (D8 CIEM build/buy, D9 WIGGUM relationship, D10 cross-tenant identity stance), realistic phased cost ceilings ($53→$80→$150→$300-400/mo), quantitative success metrics, sunset criteria per bridge.
- Mystery solved: redteam's "4 prior failed attempts" finding was wrong — `control-tower-{4hn,rh1,tei,zp6}/` are stale Feb 20-24 agent worktrees, not failed consolidations. Confirmed via `git worktree list`, no `.git` dirs, no files newer than parent repo's `.gitignore`. Filed as cleanup `fkul`.

### Track A — planning-agent decomposition (commit `df21876`)
- 21 issues filed with 26 dependency edges, 0 cycles.
- Phases 2–6 (41-43 issues) drafted but NOT filed — to keep `bd ready` focused.
- Critical path identified.
- Tyler-only minimum-viable-path: ~45 min (g1cc dispatch + 9lfn authorship + D-Name decision).

### Phase 0 cleanup + Phase 0.5 execution (commit pending)
After Tyler said "continue on next steps based on your recommendations outlined":
- `fkul` ✅ closed — deleted 4 stale worktree dirs, recovered 48 MB.
- `68g7` ✅ closed — created `RUNBOOK.md` v1 (entry-point doc for emergency operations; 12 sections; Tyler-only knowledge gaps flagged with 🔴 markers).
- `2au0` ✅ closed — created `AGENT_ONBOARDING.md` v1 (first-day-to-productive doc for new humans/agents; 13 sections including repo tour, dev loop, bd workflow, /wiggum ralph protocol, six-domains map, first-issue recommendations by experience level).
- `0dhj` ✅ closed — created `docs/dr/rto-rpo.md` v1 (RTO 4h business / 8h after-hours; RPO 24h bounded by Azure SQL Basic 7-day PITR; quarterly test cadence; 5 known gaps explicitly named).
- New issue **`uchp`** filed for Q3 2026 first DR test cycle (gated on `213e` + `fifh`).

---

## 📋 Current bd state (refreshed 2026-04-29)

### Closed 2026-04-28
- `fkul` cleanup stale worktrees
- `68g7` RUNBOOK.md
- `2au0` AGENT_ONBOARDING.md
- `0dhj` RTO/RPO docs
- `fifh` broken `mda590/teams-notify` action in backup workflow
- (V1 plan, redteam doc, V2 plan are docs-only commits, not bd issues)

### Closed 2026-04-29
- `q8lt` Bicep Drift Detection scope mismatch — fixed workflow to use
  `az deployment sub what-if` for subscription-scoped `infrastructure/main.bicep`.
- `3flq` Database Backup OIDC permission regression — filed after scheduled
  run `25089002576` failed at `azure/login@v2`; fixed with
  `permissions.id-token: write` plus actionlint shell quoting cleanup.
- `xkgp` datetime.utcnow tech debt — split into safe commits:
  - `e28ef73` tests/fixtures switched to `datetime.now(UTC)`.
  - `92f6d11` runtime `app/core` and `scripts` switched to `datetime.now(UTC)` / callable UTC helper.
  - Validation: `rg datetime.utcnow app scripts tests alembic` returns zero; full non-visual unit+integration suite passed (`4037 passed, 1 deselected`).

### Partially implemented 2026-04-29
- `cz89` weekly BACPAC export automation — code landed but issue remains open:
  - `0a9097b` added `.github/workflows/bacpac-export.yml`, DR docs, retention policy update, and workflow contract tests.
  - `5ebd880` made storage account discovery derive from target resource group when `AZURE_STORAGE_ACCOUNT` is unset.
  - `82fb0a0` added Key Vault fallback for SQL admin password (`sql-admin-password`).
  - `a24d940` records the staging validation blocker in bd.
  - `cc755ac` unclaims `cz89` at session close with the blocker preserved in bd notes.
  - Local validation passed: `pytest tests/unit/test_bacpac_export_workflow.py`, `actionlint .github/workflows/bacpac-export.yml`, pre-commit.
  - Staging dispatches progressed through hidden blockers: missing storage secret → missing SQL password → KV RBAC → missing staging KV secret → **current hard blocker: staging SQL Free edition does not support ImportExport** (`run 25126517281`, `UnSupportedImportExportEdition`).
  - Also set GitHub staging environment secret `SQL_ADMIN_PASSWORD` from existing staging app `DATABASE_URL` without printing the value; do not treat that as final secrets architecture.

### Filed recently
- 21 from planning-agent decomposition (Phases 0 cleanup + 0.5 + 1 + 1.5)
- `uchp` Q3 DR test, depends on `213e` + `fifh`
- `3flq` backup OIDC token permission regression (filed and closed same session)

### Still in `bd ready` after continuation (Tyler-blocking or autonomous)
- `9lfn` — **Tyler-authored** SECRETS_OF_RECORD.md (P1, ~30 min). Bus-factor blocker.
- `c10e` — resources domain README + DATA_CLASSIFICATION.
- `ewdp` — lifecycle domain README + DATA_CLASSIFICATION.
- `sl01` — bi_bridge domain README + DATA_CLASSIFICATION; currently assigned to Tyler.
- Phase 1.5 refactors are starting to appear ready now that their boundary docs landed; only claim one at a time and respect the documented domain boundaries.
- `213e` — name second rollback human (P2, waiver expires 2026-06-22).
- `cz89` — automate weekly BACPAC export (P4) remains open on the staging Free-tier ImportExport validation blocker.

### Deferred out of `bd ready` 2026-04-29
- `rtwi` — deferred to 2026-05-17 trigger date; zero-traffic shutdown script is already scaffolded.
- `m4xw` — deferred to 2026-07-01 quarterly review; issue trigger says automate only after `audit_logs` >100k rows or compliance requires it, while docs still say ~200 rows.

### Former P1 chain status after continuation
- `g1cc` ✅ closed — production deploy run `25131829042` succeeded with deterministic SLSA + SBOM attestation verification.
- `918b` ✅ closed — prod tenant-auth fallback investigation verified the noisy tenants are now scheduler-ineligible and old fallback signatures are absent.
- `0gz3` ✅ closed — post-deploy sync recovery verified and stale platform-sync alerts resolved.
- `0nup` — next release-evidence gate; should now be unblocked by the closed chain.
- `tg2z` — newly filed follow-up for remaining unrelated Riverside batch / DMARC active alerts.

---

## 🎯 Tyler's minimum-viable-path (~45 min of human time)

Per planning-agent's analysis, smallest set that unblocks the autonomous pipeline:

1. **Author `SECRETS_OF_RECORD.md`** (issue `9lfn`, P1, ~30 min) — only Tyler knows where every credential lives. Unblocks RUNBOOK fully + raises bus-factor metric to 2.
2. **Pick a name from V2 §11** (~15 min) — Switchyard / Aerie / Hangar / Meridian / Dispatch (or request more candidates). Unblocks Phase 3 prep.
3. **Name a second rollback human** (`213e`) before the 2026-06-22 waiver expiry.

Agents can continue autonomous Phase 1 docs/refactors from `bd ready`; the Tyler items above improve bus-factor and naming direction but no longer block the domain-doc track.

---

## 🚧 Open D-decisions for Tyler (none blocking immediately)

| Decision | Recommendation | When needed |
|---|---|---|
| **D1** framing alignment | One-paragraph confirmation HTT owns this | Anytime |
| **D-Name** | Switchyard (richest metaphor, lowest collision) | Before Phase 3 (~3 weeks out) |
| **D8** CIEM build/buy | (c) Hybrid — Entra Permissions Mgmt as data source | Before Phase 4e (~Week 7) |
| **D9** WIGGUM relationship | (b) Supplement — different artifacts/audiences | Anytime |
| **D10** cross-tenant identity stance | (c) Hybrid — audit each grant, classify | Before Phase 4d/4e final AC |

---

## 📚 Document hierarchy (for the next session)

```
For strategic direction         → PORTFOLIO_PLATFORM_PLAN_V2.md (active)
For redteam findings            → CONTROL_TOWER_MASTERMIND_PLAN_2026_REDTEAM.md
For historical context          → CONTROL_TOWER_MASTERMIND_PLAN_2026.md (V1, archived)
For tactical execution log      → WIGGUM_ROADMAP.md
For live blocker dashboard      → CURRENT_STATE_ASSESSMENT.md
For live work backlog           → bd ready
For system topology             → INFRASTRUCTURE_END_TO_END.md
For emergency operations        → RUNBOOK.md (NEW today)
For new-engineer onboarding     → AGENT_ONBOARDING.md (NEW today)
For credential locations        → SECRETS_OF_RECORD.md (NOT YET WRITTEN — bd 9lfn)
For DR targets + cadence        → docs/dr/rto-rpo.md (NEW today)
For per-release rollback        → docs/release-gate/rollback-v<version>.md
For DR runbook                  → docs/runbooks/disaster-recovery.md
For session-to-session context  → SESSION_HANDOFF.md (THIS FILE)
```

---

## ⚙️ Environment health checks (verified 2026-04-29)

```
✅ uv venv working (Python 3.12.12)
✅ uv sync --dev --frozen succeeds
✅ pytest 9.0.3 collects 4,192 tests
✅ Pre-commit hooks installed with correct path
✅ Pre-commit passes: ruff sort/lint/format, detect-secrets, env-delta validator
✅ origin/main pushable (no branch protection issues encountered)
✅ bd commands working (claim, close, comments, create, ready, show)
✅ bd sync working
✅ git worktree list confirms only valid worktrees remain
⚠️  pre-commit missing from pyproject.toml dev deps (manual install needed after each venv rebuild)
✅ Production deploy run `25131829042` succeeded; prod is on fresh attested digest `sha256:a76f3eeb9f7c0f28b27c196a8f9c8cf06368fc47875c51ea7a95f0bbbdd680e4`.
⚠️  backup.yml had a second regression after fifh: missing OIDC id-token permission; fixed in bc78195, next scheduled/manual run must verify actual backup lands
⚠️  bicep-drift-detection.yml scope mismatch fixed in 40bea97; next scheduled/manual run must verify all env matrix jobs reach real drift signal
⚠️  Push-triggered CI/staging/security runs may still be in progress for the latest doc commits; check `gh run list --branch main --limit 10` next session.
⚠️  weekly BACPAC workflow exists, but staging validation is blocked because staging SQL is Free edition and Azure SQL ImportExport rejects Free (`UnSupportedImportExportEdition`)
```

---

## 🐶 Recommended next session start

If picking up cold:

1. Read this `SESSION_HANDOFF.md` (5 min)
2. Read `PORTFOLIO_PLATFORM_PLAN_V2.md` §1, §5, §9 (15 min)
3. Run `bd ready` and `git status` to confirm state
4. Prod deploy/recovery is no longer the blocker. Continue with `bd ready`: resources/lifecycle docs, carefully scoped Phase 1.5 refactors, or the remaining ops follow-ups.

If picking up after Tyler's minimum-viable-path lands:

1. Verify `SECRETS_OF_RECORD.md` exists and update RUNBOOK.md TYLER-ONLY markers.
2. Continue Phase 1 paper exercises: resources (`c10e`) and lifecycle (`ewdp`) remain unclaimed; bi_bridge (`sl01`) is still assigned to Tyler.
3. If choosing refactors instead, respect the new domain boundary docs and keep one issue per commit.

---

## 💾 End-of-Session Status (2026-04-29)

Committed and pushed this continuation after the earlier session entries below:

- `3c9c317` — `bd: record current prod QA gate evidence (g1cc)`
- `57d3e25` — `bd: close deterministic prod attestation gate (g1cc)`
- `831a882` — `bd: close prod sync recovery chain (918b, 0gz3)`
- `a442b7e` — `docs(cost): define domain boundary and data classification`
- `6989c32` — `docs(identity): define domain boundary and data classification`
- `3134576` — `docs(compliance): define domain boundary and data classification`

Earlier committed and pushed work from this 2026-04-29 handoff file:

- `40bea97` — `fix(ci): align Bicep drift what-if scope (bd q8lt)`
  - Replaced resource-group-scoped Bicep drift `what-if` with subscription-scoped `az deployment sub what-if`.
  - Added `tests/unit/test_bicep_drift_workflow.py` regression coverage.
- `bc78195` — `fix(ci): grant backup workflow OIDC token permission (bd 3flq)`
  - Filed + closed `3flq` after scheduled backup run `25089002576` failed before backup creation.
  - Added `permissions: contents: read / id-token: write` for `azure/login@v2`.
  - Added `tests/unit/test_backup_workflow_oidc.py`; actionlint clean for `backup.yml`.
- `fe1724a` — `fix(ci): harden staging health readiness gate (bd mvxt)`
  - Reasserts `alwaysOn=true` and `/health` health-check path after container settings, because live staging had drifted to `alwaysOn=false` with no health-check despite Bicep declaring both.
  - Replaces fixed 90s sleep with bounded `/health` readiness loop and diagnostics.
- `ef36023` — `test(staging): add B1 headroom for route probes (bd mvxt)`
  - Gives staging route-mount probes 30s timeout so post-deploy B1 latency flakes report real 404/500 failures instead of transient read timeouts.
  - Added unit contract test for the timeout expectation.
- `b865af5` — `bd: close staging deploy instability (mvxt)`
  - Closed `mvxt` with evidence from successful `Deploy to Staging` run `25128507657`.
- `e85860a` — `bd: close browser smoke CI umbrella (aiob)`
  - Closed stale umbrella after verifying blocking Browser Smoke CI and required branch protection context.
- `81870e2` — `bd: defer audit archive automation until trigger`
  - Deferred `m4xw` to 2026-07-01 because current row count/requirements do not justify automation yet.
- `1765cee` — `bd: defer domain-intelligence shutdown check`
  - Deferred `rtwi` to its explicit 2026-05-17 60-day zero-traffic trigger.
- `989ae03` — `fix(ci): let staging health loop retry curl timeouts`
  - Fixed the readiness loop bug where `bash -e` exited immediately on a curl timeout before the loop could capture `curl_exit` and retry.
  - Validation: `pytest tests/unit/test_deploy_staging_workflow.py tests/unit/test_staging_api_coverage_contract.py`, `actionlint .github/workflows/deploy-staging.yml`, and full pre-commit all passed.
- `b4359c4` — `fix(ci): serialize staging deploy workflow`
  - Added `concurrency` to `deploy-staging.yml` so back-to-back pushes cannot run overlapping deploy/validation cycles against the same mutable staging App Service.
  - This was discovered after a doc-only handoff push failed staging validation while another staging deploy was concurrently restarting the app.

Validation run locally:

- `.venv/bin/pytest tests/unit/test_bicep_drift_workflow.py -q`
- `.venv/bin/pytest tests/unit/test_backup_workflow_oidc.py tests/unit/test_bicep_drift_workflow.py -q`
- `az bicep build --file infrastructure/main.bicep --stdout`
- `az deployment sub what-if --help` flag check
- `actionlint .github/workflows/bicep-drift-detection.yml`
- `actionlint .github/workflows/backup.yml`
- `.venv/bin/pre-commit run --all-files`

At handoff time:

- Working tree clean and pushed to `origin/main`.
- `mvxt` closed after staging runtime drift was corrected and push run `25128507657` completed `Deploy to Staging` successfully on `ef36023`; later follow-ups fixed a bash `set -e` retry bug (`989ae03`) and serialized staging deploys to avoid concurrent restarts during validation (`b4359c4`).
- `aiob` umbrella closed after confirming all child issues complete, `Browser Smoke` is a blocking CI job, and branch protection requires `Browser Smoke` + `Security Scan`.
- `rtwi` and `m4xw` deferred to their actual trigger windows so `bd ready` stops showing future/YAGNI work.
- `SECRETS_OF_RECORD.md` still absent; `9lfn` remains Tyler-only.
- Production deploy run `25131829042` succeeded off current-main lineage and prod is on fresh digest `sha256:a76f3eeb9f7c0f28b27c196a8f9c8cf06368fc47875c51ea7a95f0bbbdd680e4`.
- Phase 1 domain docs complete for cost, identity, and compliance; remaining docs are resources and lifecycle, plus bi_bridge if Tyler unassigns/dispatches it.

---

*Authored 2026-04-28 by code-puppy-ab8d6a; refreshed 2026-04-29 by code-puppy-661ed0 (Richard) for Tyler Granlund.*
*This file is the canonical session-to-session memory for the platform.*
*Update on every session close.*

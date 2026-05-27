# Release-Gate Snapshot — 2026-05-27 Richard Handoff

**Run ID:** `snapshot-2026-05-27-richard-handoff`
**Arbiter:** `release-gate-arbiter-d697f2` (Sword of Ultimate Truths, adversarial v2.5.1 read-out)
**Submitter:** `code-puppy-5deed9` (Richard) on behalf of Tyler Granlund
**Snapshot time:** 2026-05-27 17:55 UTC
**Source env / Target env:** `dev` (branch `fix/kv-client-on-app-service` @ `99148af`) → `prod` (`app-governance-prod` @ commit `e070181`, image `sha256:78362d36…`)
**Initiative ID:** v2.5.1 (intended); also ct-y47 / ct-t5e / ct-7oe / ct-4iq / ct-las incident response
**Prior verdict:** [`rehearsal-2026-04-30-internal.md`](./rehearsal-2026-04-30-internal.md) → `PASS-pending-9lfn`

---

## Verdict: `FAIL — DO NOT CUT v2.5.1`

Prior verdict `PASS-pending-9lfn` is **retroactively voided by reality.** Production `/health` returns 200 but customer-tenant data has not synced for any of BCC / FN / DCE / TLL since `2026-05-20 23:10 UTC` — that is **~167 hours** of silent data-plane outage on infrastructure that the 2026-04-30 verdict graded `PASS` on Pillars 4 (Infrastructure) and 7 (Maintenance & Operability). The "PASS" was wrong, or the world changed and the gate didn't notice. Either way, the gate failed its primary contract: detecting that production is unfit to extend.

Additionally:

- **No `v2.5.1` artifact exists.** `pyproject.toml` is `version = "2.5.0"`; `git tag --list` ends at `v2.5.0`. You cannot grant a verdict on a release that has not been cut.
- **The fix is on an unmerged branch.** PR #63 head is `99148af`; it is `MERGEABLE` and CI-green, but `reviewDecision: REVIEW_REQUIRED` and zero deploy runs exist for it. The fix is *aspirational*, not shipped.
- **Tyler attempted an unsanctioned live config mutation today** (per `bd show ct-y47`: "did try flipping `USE_OIDC_FEDERATION=false` on prod live today (2026-05-27 17:30 UTC) — surfaced the layer-2 bug, rolled back immediately"). That is prod-touched-without-a-change-record. It is logged as a fact but it is also a gate-process finding (see Pillar 8 below).

**Go/no-go for v2.5.1 right now:** **NO-GO.** Three independent reasons, any one of which is sufficient: (1) the artifact doesn't exist (`pyproject.toml` still `2.5.0`, no tag, RTM still `-DRAFT`); (2) production is in an active P1 incident with documented blast radius across 4 customer tenants for 7 days; (3) the fix (PR #63) is unmerged, unreviewed, and undeployed, so even a "cut now, deploy hotfix" story has a glaring gap between subject-of-verdict and what is actually running. Land PR #63, deploy it, verify `/healthz/data` is fresh for all 5 tenants for ≥24h, then re-run the gate against a real `v2.5.1` tag.

---

## Preconditions check

| # | Required input | State | Note |
|---|---|---|---|
| 1 | RTM signed-off, code-linked, test-linked, validation-linked | ⚠️ `rtm-v2.5.1-DRAFT.md` exists but is `-DRAFT`; no rows reference ct-y47 / PR #63 / the 4 sync bugs | Not failed-closed yet, but the RTM is now provably out of date with the incident corpus |
| 2 | Source build root + target mirror root | ✅ source: working tree on `fix/kv-client-on-app-service`; target baseline: prod `e070181` | OK |
| 3 | Environment delta spec | ⚠️ `env-delta.yaml` exists and validator gates CI, but **the env var the incident hinges on (`USE_OIDC_FEDERATION`) is not surfaced as a v2.5.1 toggle decision in any verdict-adjacent doc** | Gap |
| 4 | Change record / ticket | ✅ `bd ct-y47` (P1, in_progress) + 5 cross-linked bd issues; no Monday/CAB record for v2.5.1 cut | OK for the fix; missing for the release |
| 5 | Rollback plan | ⚠️ `docs/release-gate/rollback-current-state.yaml` covers image rollback; **does NOT cover "data-plane stale but /health green"** which is the actual failure mode in flight | Gap |

Result: **does not emit `PRECONDITIONS_NOT_MET`** (inputs 2 and 4 are sufficient to run the gate), but inputs 1, 3, and 5 each contribute findings below.

---

## Pillar Table (one-glance)

| # | Pillar | 2026-04-30 verdict | 2026-05-27 verdict | Movement |
|---|---|---|---|---|
| 1 | Requirements Closure | PASS | **FAIL** | ⬇ regression — RTM does not cover the in-flight incident or PR #63 |
| 2 | Code Review | PASS | **CONDITIONAL_PASS** | ⬇ slight — PR #63 is correct on inspection but unreviewed by a second human |
| 3 | Security | PASS | **CONDITIONAL_PASS** | ⬇ slight — scanners still green on PR #63, but a multi-tenant-app credential model error was in prod for 7 days |
| 4 | Infrastructure | PASS | **FAIL** | ⬇⬇ hard regression — infra is the *cause* of the active outage |
| 5 | Stack Coherence | PASS | **PASS** | flat — no new components introduced |
| 6 | Cost | PASS | **CONDITIONAL_PASS** | ⬇ slight — 7 days of zero customer-tenant data ingest is unbilled-but-uncollected business value, not on the Infracost ledger |
| 7 | Maintenance & Operability | PASS | **FAIL** | ⬇⬇ hard regression — documented runbook contained latent bug; no one noticed for 7 days; `/health` is too lenient |
| 8 | Rollback | PASS (++ field-tested) | **FAIL** | ⬇⬇ hard regression — rollback theory assumes image-swap; the actual incident is unrollable-by-image and was made worse by a live config flip today |

**Overall:** `PASS-pending-9lfn` → **`FAIL`**. Three pillars hard-failed; three downgraded to `CONDITIONAL_PASS`; one unchanged.

---

## Pillar 1 — Requirements Closure → **FAIL**

**Movement:** ⬇ PASS → FAIL.

**Receipts:**
- `docs/release-gate/rtm-v2.5.1-DRAFT.md` is still in `-DRAFT`. The April 30 verdict §N-1 said "flip to non-DRAFT happens at v2.5.1 cut." We are 27 days past that promise.
- Five active P1 issues (`ct-y47`, `ct-t5e`, `ct-7oe`, `ct-4iq`, `ct-las`) are not represented in the RTM. Four are traceable to one root cause (per Richard's diagnosis in `bd show ct-y47`), but **traceability is a property the RTM is required to enforce, not a property the operator should have to discover by reading bd notes**.
- One additional P1 (`ct-4uu` — QA comprehensive E2E UAT) is also `in_progress` and is the exact gate quality control v2.5.1 needs. It is not done.

**Adversarial counter-argument (strongest case for PASS):** RTM is operationally an artifact of release-cut, not release-readiness. The fact that v2.5.1 has not been cut is *why* RTM is still `-DRAFT` — circular. Counter to the counter: this is the gate's job. If the artifact is not ready, the gate says so. That's the point.

**What it would take to clear:**
1. PR #63 merged + deployed + verified live.
2. Five P1 incident-related bd tickets closed with evidence pointers.
3. `rtm-v2.5.1-DRAFT.md` flipped to `rtm-v2.5.1.md` with rows for the incident, the fix, and the closed P1s.
4. `ct-4uu` E2E UAT executed and pass-recorded in RTM.

---

## Pillar 2 — Code Review → **CONDITIONAL_PASS**

**Movement:** ⬇ PASS → CONDITIONAL_PASS (advisory).

**Receipts:**
- PR #63 head `99148af` is `MERGEABLE`, all blocking CI checks green: `Lint & Test`, `Container Image Scan (Trivy)`, `Bandit`, `pip-audit CVE Scan`, `env-delta Schema + Literal Rejection`, `Secrets Detection`, `Browser Smoke`, `Safety Dependency Scan`. Trivy reported `NEUTRAL` (advisory).
- `reviewDecision: REVIEW_REQUIRED`. No human has reviewed the diff. The branch is two commits ahead of `origin/main`: `8a15440 fix(auth): use ManagedIdentityCredential on App Service…` and `99148af docs(status): refresh STATUS.md…`.
- The fix pattern (`_build_managed_credential()` helper, `WEBSITE_SITE_NAME`-gated `ManagedIdentityCredential()` vs `DefaultAzureCredential` off-platform) is correct given the documented `AZURE_CLIENT_ID`-hijack failure mode, **but** the same bug class went undetected for the full life of the documented `enable-secret-fallback.md` runbook. That is a *latent-bug-discovery* event, not a *bug-introduced-now* event — Pillar 2 is therefore not the right place to fail it (see Pillar 7).
- LLM/advisory-only constraint: I am not failing Pillar 2 on LLM output. The CI scanners are deterministic and green. Per playbook §"LLM says fail" anti-pattern, advisory cannot drive FAIL.

**Adversarial counter-argument (strongest case for FAIL):** A fix that touches the App Service credential resolution path on a service in active P1 incident should have a second-human signed review before merge. CI greenness is not equivalent to a code review. Counter to the counter: the gate validates that a code-review process exists and gates merge; the missing human review is what `REVIEW_REQUIRED` enforces. The gate is not bypassed.

**What it would take to clear:**
1. Second human (Dustin or Tyler, whichever did not author) reviews and approves PR #63.
2. PR merged via `main`-protected path (not admin override).

---

## Pillar 3 — Security → **CONDITIONAL_PASS**

**Movement:** ⬇ PASS → CONDITIONAL_PASS.

**Receipts:**
- Scanner Group A all green on PR #63 (per `gh pr view 63 --json statusCheckRollup`): gitleaks-class `Secrets Detection`, `Bandit`, `Bandit Security Lint`, `pip-audit CVE Scan`, `Safety Dependency Scan`, `env-delta Schema + Literal Rejection`, `Container Image Scan (Trivy)`.
- **However:** the incident root cause documented in `bd show ct-y47` is a credential-resolution defect. Specifically: `DefaultAzureCredential` reads `AZURE_CLIENT_ID` (multi-tenant app reg ID, **not** a UAMI) and produces `invalid_scope: No UAMI found`. This is a Pillar 3-adjacent failure — secrets handling and identity-federation control flow — that no scanner in the current Group A would catch. That is a gap in coverage, not a gate failure.
- `bd ct-9lfn` (`SECRETS_OF_RECORD.md` — the *one* condition outstanding from the 2026-04-30 verdict) is still open. 27 days later. The verdict labeled this "not a structural blocker." That label has aged poorly: during a credential-resolution incident, the absence of a canonical secrets-of-record document is precisely what slowed diagnosis. (Mitigated by Richard's session-time root-causing, but only because Richard happened to be the operator.)

**Adversarial counter-argument (strongest case for FAIL):** A 7-day silent credential-resolution outage in production *is* a security incident — availability is a CIA leg. The fact that no exfiltration occurred is not exculpatory. Counter to the counter: there is no evidence of credential leakage or unauthorized access. Customer-tenant tokens failed *closed*. That is the desired property in a credential bug. Availability impact is real and is failed under Pillar 4/7, not Pillar 3.

**What it would take to clear:**
1. `bd ct-9lfn` closed (Tyler authors `SECRETS_OF_RECORD.md`).
2. Add a Group A check or runbook step that validates the `AZURE_CLIENT_ID` / UAMI distinction (proposed as a learning under `arbiter/learnings/`).
3. Post-deploy of PR #63, re-run Scanner Group A against the deployed image digest, not just the PR.

---

## Pillar 4 — Infrastructure → **FAIL**

**Movement:** ⬇⬇ PASS → FAIL.

**This is the headline regression.** The 2026-04-30 verdict cleared Pillar 4 from `CONDITIONAL_PASS` to `PASS` on the strength of [run `25193020385`](https://github.com/HTT-BRANDS/control-tower/actions/runs/26194535675) deploying commit `9ccd870`. Twenty days later, commit `e070181` is in production via [run `26194535675`](https://github.com/HTT-BRANDS/control-tower/actions/runs/26194535675), image `sha256:78362d36…`, deployed 2026-05-20 22:50 UTC. **Twenty minutes after that deploy** (`2026-05-20 23:10 UTC`), customer-tenant data sync went stale and has remained stale through 2026-05-27 17:55 UTC. That is the infrastructure under verdict.

**Receipts:**
- `bd show ct-y47` documents the layered root cause: (a) `USE_OIDC_FEDERATION=true` is architecturally impossible for cross-tenant SAMI→multi-tenant-app FIC (Microsoft platform limit, evidenced by `AADSTS700236` in prod logs); (b) latent KV-credential bug surfaced only when (a) was bypassed.
- `STATUS.md` ⚠️ banner: "STALE for BCC/FN/DCE/TLL since 2026-05-20 — only HTT fresh." Verified live via `/healthz/data` (see same STATUS.md row).
- `xzt4` is still `in_progress` with **production Bicep apply explicitly deferred**. That means there is a known drift between Bicep source-of-truth and live prod infrastructure that we are choosing to live with. April 30 noted this but framed it as benign; in the current state it is a documented blind spot.
- `App Service env: USE_OIDC_FEDERATION : true` per `STATUS.md` deployed-image section. That setting is the active root cause and **cannot be safely changed without PR #63's code fix landing first** (per ct-y47 notes: Tyler proved this empirically today by trying).

**Adversarial counter-argument (strongest case for PASS):** Infrastructure-as-platform (App Service, SQL, KV, GHCR, OIDC, App Insights, alerts) is still up. `/health` 200. The failure is in *application-level credential resolution*, not in any provisioned-by-Bicep resource. Therefore Pillar 4 should be CONDITIONAL_PASS at worst, and the real failure belongs to Pillar 7 (runbook bug). Counter to the counter: the 2026-04-30 verdict explicitly used "infrastructure" to mean the deployed-and-operating system, including environment variables and identity federation topology. Under that scope — the only useful scope — the infrastructure is not delivering its primary function. A definition that says "infra is fine because the VM is on" is not a definition the gate accepts.

**What it would take to clear:**
1. Customer-tenant `/healthz/data` shows BCC/FN/DCE/TLL fresh for ≥24h after PR #63 deploy + flag flip.
2. `ct-y47`, `ct-t5e`, `ct-7oe`, `ct-4iq` closed with deploy-run citations.
3. Add an alert on `/healthz/data` staleness >2h per tenant. (Currently no such alert exists; that's why this lasted 7 days.)
4. `xzt4` either closed or filed as a written, time-bounded waiver.

---

## Pillar 5 — Stack Coherence → **PASS**

**Movement:** flat.

**Receipts:**
- No new dependencies introduced in PR #63 diff. The fix is internal: `_build_managed_credential()` uses `azure-identity`'s `ManagedIdentityCredential`, already in the dependency tree.
- `core_stack.yaml` is the source of truth and will bump at v2.5.1 cut (not yet, because v2.5.1 has not been cut).

**Adversarial counter-argument (strongest case for FAIL):** The credential-resolution model has *changed* (DefaultAzureCredential conditional on `WEBSITE_SITE_NAME` is a new control-flow path), even if no new package was added. That is a stack-level architectural decision that warrants stack-coherence review. Counter to the counter: this is an intra-component change, not a new component. Pillar 5 governs sprawl and approved-platforms, not internal control flow. The right home for this finding is Pillar 2 (code review) and Pillar 7 (runbook).

**What it would take to clear:** Nothing additional for this pillar.

---

## Pillar 6 — Cost → **CONDITIONAL_PASS**

**Movement:** ⬇ PASS → CONDITIONAL_PASS.

**Receipts:**
- Infra run-rate is unchanged from `STATUS.md` Cost section: ~$44–53/mo Azure total. The fix does not provision new resources.
- **But:** the *business* cost of 7 days of dead customer-tenant data sync is not on the Infracost ledger and is not zero. Four customer tenants (BCC/FN/DCE/TLL) have had no fresh MFA/compliance/cost/identity data ingested. That is a Pillar 6 finding the playbook explicitly contemplates ("Per-location impact — small per-unit costs compound"). Whether it lands as customer-trust cost or as missed-billable depends on the contract terms with each tenant, which the gate does not have visibility into.

**Adversarial counter-argument (strongest case for FAIL):** If any customer-tenant contract carries an SLA on data freshness, 7 days of staleness is a contractual breach, not an "observation." Counter to the counter: the gate has no evidence of such an SLA and will not invent one. Filed as a learning.

**What it would take to clear:**
1. Named budget owner for "incident-driven data loss / customer-trust cost" — playbook requires it.
2. Cost addendum filed in `docs/cost/` quantifying the 7-day outage in business-impact terms.

---

## Pillar 7 — Maintenance & Operability → **FAIL**

**Movement:** ⬇⬇ PASS → FAIL.

**This is the second hard regression.**

**Receipts:**
- The 2026-04-30 verdict cleared this pillar to PASS on the strength of: (a) bus-factor 1→2 (Dustin onboarded), (b) `RUNBOOK.md`, (c) `docs/runbooks/disaster-recovery.md`, (d) `docs/dr/rto-rpo.md`. All of those documents still exist. **None of them caught a 7-day customer-tenant data outage.**
- `/health` returned 200 throughout. `/health/detailed` reports `database/scheduler/cache/azure_configured` all healthy. The lenient `/health` gate is itself called out in `STATUS.md` ("Public app /health still 200 because health gate is too lenient — that's a separate follow-up"). That sentence is the gate's evidence that the maintenance contract is broken.
- The documented recovery runbook (`docs/runbooks/enable-secret-fallback.md`, referenced from ct-y47 rollout plan) **had a latent bug in it** — it told the operator to set `USE_OIDC_FEDERATION=false`, which on its own surfaces a second bug that the runbook did not warn about. Tyler proved this empirically at 2026-05-27 17:30 UTC. A runbook that has a latent failure mode discovered live is, by definition, not current.
- No alerting fired on customer-tenant staleness despite "9× alerts + 2 availability tests" per `STATUS.md`. The alerts cover the wrong thing.
- The "named owner" for the data-sync surface: not explicit in any verdict-adjacent doc. PR #63 author is `code-puppy-5deed9` (Richard, this session); the incident-response owner is the same code-puppy. That is not a human. Playbook requires a human owner, not a team alias.

**Adversarial counter-argument (strongest case for PASS):** The runbook *worked* — Richard followed it, hit the latent bug, diagnosed it, shipped the fix. The system is self-correcting through its documented escalation path. Counter to the counter: the gate measures whether maintenance & operability *detect and resolve* failures within acceptable time. Detection took 0 hours (the operator already knew about it before this session began; the incident was visible in `/healthz/data` since 2026-05-20). Time-to-detect → time-to-fix-merged = **7 days**. That is not "self-correcting through documented escalation." That is "Richard happened to log in." This is exactly the anti-pattern the gate exists to prevent.

**What it would take to clear:**
1. `/health` gate widened to fail when `/healthz/data` reports any required tenant stale > N hours.
2. Alert created on per-tenant `/healthz/data` staleness; routed to a named on-call (human, not puppy).
3. `docs/runbooks/enable-secret-fallback.md` updated to reflect both layered bugs, with rollout-ordering guidance ("do not flip `USE_OIDC_FEDERATION=false` without the `_build_managed_credential()` code path landed").
4. Named human owner for the customer-tenant sync surface, recorded in `RUNBOOK.md`.
5. Post-incident review filed under `arbiter/learnings/2026-05-27-ct-y47-customer-tenant-sync-outage.md`.

---

## Pillar 8 — Rollback → **FAIL**

**Movement:** ⬇⬇ PASS (++ field-tested) → FAIL.

**Receipts:**
- The 2026-04-30 rollback story is *image-swap* rollback: capture previous-good digest, restore on failed health gate. That mechanism is intact and was field-tested by the `bd 1vui` cycle. **It does not apply to this incident.**
- The current failure mode is: image deploy succeeded, `/health` returned 200, but a downstream credential-resolution path is broken. Image rollback to the prior digest **would not fix this** because the bug is in the credential-resolution logic that was present in prior images too (latent until `USE_OIDC_FEDERATION=true` made it active). The rollback YAML in `docs/release-gate/rollback-current-state.yaml` does not document this scenario.
- **Tyler executed an unsanctioned live config mutation** at 2026-05-27 17:30 UTC (per `bd show ct-y47`: "did try flipping `USE_OIDC_FEDERATION=false` on prod live today — surfaced the layer-2 bug, rolled back immediately"). The rollback worked — but the change was not gated, not staged, and not recorded as a change-record at the time of execution. The gate notes this with two opposing readings: (a) the operator was diagnosing an active P1 and the speed/restraint shown was correct judgment; (b) the gate cannot grant Pillar 8 PASS on "trust the operator" — that violates the playbook's "rollback must be safe at 2am" property. At 2am, no Richard.
- `auto-rollback` did not trigger because `/health` was 200. The rollback contract is "fail-closed on health-gate failure"; the actual contract needed is "fail-closed on data-freshness regression," which does not exist.

**Adversarial counter-argument (strongest case for PASS):** The rollback mechanism that exists worked correctly on every event it was designed for. The 2026-05-27 17:30 UTC config flip was *manual* rollback (flip then un-flip), which is exactly what the playbook says is acceptable while auto-rollback authority is being built. Counter to the counter: the gate does not grant PASS for "rollback worked because the operator was awake." That's the antithesis of the contract.

**What it would take to clear:**
1. Rollback YAML expanded to cover "image deployed, `/health` green, data-plane stale" — explicit steps, owner, time-to-execute estimate.
2. Auto-rollback trigger extended to include `/healthz/data` regression on a configurable per-tenant SLA.
3. Forward-fix path documented for credential-resolution incidents (this incident's path becomes the template).
4. Change-record discipline: any live env-var flip on prod must produce a bd ticket *before* the flip, not after. File this one retroactively as `arbiter/learnings/` so the next operator has the precedent.

---

## Blocking findings (machine-readable)

```yaml
- id: RG-2026-05-27-001
  rule_id: pillar-4.data-plane-availability
  severity: critical
  pillar: infrastructure
  why: |
    Customer-tenant data sync (BCC/FN/DCE/TLL) has been stale since
    2026-05-20 23:10 UTC, 167 hours and counting, on the same infrastructure
    that the 2026-04-30 verdict graded PASS.
  where:
    surface: https://app-governance-prod.azurewebsites.net/healthz/data
    bd_id: ct-y47
    related_bd: [ct-t5e, ct-7oe, ct-4iq, ct-las]
  tool: live curl + STATUS.md banner + bd show ct-y47
  next: merge PR #63, deploy, flip USE_OIDC_FEDERATION=false, verify 24h fresh.

- id: RG-2026-05-27-002
  rule_id: pillar-7.runbook-currency
  severity: high
  pillar: maintenance
  why: |
    docs/runbooks/enable-secret-fallback.md instructs setting
    USE_OIDC_FEDERATION=false but does not warn about the latent KV
    credential bug that surfaces in that mode without PR #63's code path.
  where:
    file: docs/runbooks/enable-secret-fallback.md
    evidence: bd show ct-y47 — "did try flipping ... surfaced the layer-2 bug"
  tool: bd notes + live test 2026-05-27 17:30 UTC
  next: revise runbook with rollout-ordering and code-path prerequisites.

- id: RG-2026-05-27-003
  rule_id: pillar-7.health-gate-fidelity
  severity: high
  pillar: maintenance
  why: |
    /health returned 200 throughout a 7-day customer-tenant data outage.
    The gate does not surface data-plane staleness.
  where:
    surface: https://app-governance-prod.azurewebsites.net/health
    referenced_in: STATUS.md (banner — "health gate is too lenient")
  tool: live curl + STATUS.md self-acknowledgement
  next: extend health gate to read /healthz/data per-tenant freshness.

- id: RG-2026-05-27-004
  rule_id: pillar-8.rollback-scope
  severity: high
  pillar: rollback
  why: |
    Documented rollback covers image-swap on /health failure only. The
    current incident is image-success + data-plane-failure, which the
    rollback YAML does not cover. Manual mitigation today (Tyler flag
    flip + un-flip) was operator-judgment, not gated process.
  where:
    file: docs/release-gate/rollback-current-state.yaml
    event: bd show ct-y47 — 2026-05-27 17:30 UTC live flag flip
  tool: rollback YAML inspection + bd notes
  next: expand rollback scenarios; require change-record-before-flip.

- id: RG-2026-05-27-005
  rule_id: pillar-1.rtm-currency
  severity: medium
  pillar: requirements_closure
  why: |
    rtm-v2.5.1-DRAFT.md does not contain rows for ct-y47, ct-t5e, ct-7oe,
    ct-4iq, ct-las, or PR #63, despite all six being on the critical
    path for v2.5.1.
  where:
    file: docs/release-gate/rtm-v2.5.1-DRAFT.md
  tool: file diff vs bd list
  next: expand RTM to cover incident corpus before cut.

- id: RG-2026-05-27-006
  rule_id: pillar-2.review-required
  severity: medium
  pillar: code_review
  why: |
    PR #63 is MERGEABLE with all CI green but reviewDecision is
    REVIEW_REQUIRED. Touches credential resolution path during active P1.
  where:
    pr: https://github.com/HTT-BRANDS/control-tower/pull/63
    head: 99148af
  tool: gh pr view 63
  next: second-human review (Tyler or Dustin, whichever did not author).
```

---

## Non-blocking findings

- **N-1 (info):** `pyproject.toml` is `2.5.0`; no `v2.5.1` tag exists. Cannot verdict-a-nothing. Filed as confirmation that the verdict is *necessarily* `FAIL` on the artifact-existence axis alone.
- **N-2 (low):** `xzt4` (Bicep drift) still `in_progress`; production Bicep apply still deferred. Pre-existing risk, not new.
- **N-3 (low):** `9lfn` (`SECRETS_OF_RECORD.md`) still open 27 days after the prior verdict labeled it the single remaining condition. The gate notes that "Tyler-only soft blocker" is becoming "Tyler-only chronic blocker" and the playbook's "every waiver expires, every waiver has a reason code, every waiver renews max 3 times" should apply here even though no formal waiver was filed.
- **N-4 (info):** 7 bd issues `in_progress` (6 P1, 1 P2). Four P1s collapse to one root cause per Richard's diagnosis; closing PR #63 should retire `ct-y47`, `ct-t5e`, `ct-7oe`, `ct-4iq` together. `ct-las` (staging tenant source-of-truth) and `ct-4uu` (E2E UAT) are independent and remain blocking for v2.5.1 cut.

---

## Conditions for an eventual PASS (after FAIL is cleared)

1. **PR #63 merged + deployed + verified.** Specifically: a successful prod deploy run citing `99148af` (or its merge commit) AND `/healthz/data` returning fresh for BCC, FN, DCE, TLL, HTT for a ≥24h soak.
2. **Five P1 bd issues closed** with run-ID citations: `ct-y47`, `ct-t5e`, `ct-7oe`, `ct-4iq`, `ct-las`.
3. **`ct-4uu` E2E UAT executed pass-recorded** in RTM.
4. **Health gate widened** to surface `/healthz/data` regression. New alert per-tenant, routed to a named human.
5. **Runbook revised:** `docs/runbooks/enable-secret-fallback.md` reflects both layered bugs and rollout ordering.
6. **Rollback YAML expanded** for data-plane-stale-but-image-green scenario.
7. **`v2.5.1` cut:** `pyproject.toml` bumped, tag pushed, `rtm-v2.5.1-DRAFT.md` → `rtm-v2.5.1.md` (status `Accepted`) with all incident-corpus rows present, `core_stack.yaml` bumped, `CHANGELOG.md` `[Unreleased]` → `[2.5.1]`.
8. **Post-incident learning filed:** `arbiter/learnings/2026-05-27-ct-y47-customer-tenant-sync-outage.md`.
9. **`bd 9lfn` (`SECRETS_OF_RECORD.md`) closed** OR formally waived under the controlled-vocabulary scheme (`acceptable_risk` / `no_bandwidth` with comment + max-3-renewal accounting).

When all nine land, run the external arbiter against the deployed `v2.5.1` artifact. The verdict at that point is *not* presumed PASS — it is presumed FAIL, as always, and earns PASS only on receipts.

---

## Exception waivers applied

None. All findings in this snapshot are unwaived. The single soft waiver from the 2026-04-30 verdict (`9lfn` "not a structural blocker") is reclassified by this run as a contributing finding under Pillar 3 / Pillar 7 — it no longer enjoys quiet acceptance.

---

## Counter-arguments the submitter is most likely to make, and the gate's pre-rebuttal

1. *"The 4-30 verdict was correct at the time; you can't retroactively void it."* — Verdicts are valid against their input set. The April 30 input set did not include 7 days of customer-tenant outage. This is a fresh snapshot, not a retraction. The April 30 verdict remains historically accurate; it is just no longer *operative*.
2. *"PR #63 fixes everything; grant CONDITIONAL_PASS contingent on its deploy."* — The gate does not grant conditional passes on undeployed code. The prior verdict already tried that pattern with `9lfn` and 27 days later that condition is still unfulfilled. CONDITIONAL_PASS is for *small remaining work on already-shipped artifacts*, not for "ship the fix and trust us." That's just FAIL with politeness.
3. *"/health 200 means production is up."* — `/health` 200 means the liveness probe is up. It does not mean production is delivering its contracted function. The gate measures contracted function.
4. *"Customer tenants aren't churning, no one's complaining, so the impact is theoretical."* — Absence of customer complaint is not evidence of acceptable impact. It is evidence of either (a) customers haven't checked the data yet, or (b) the data wasn't being used to drive decisions, which raises a different uncomfortable question. Either way, not exculpatory.
5. *"You're being too hard on the maintenance pillar. The operator (Richard) literally diagnosed and fixed it this session."* — Acknowledged with respect. That work is exactly why this snapshot exists at all and why PR #63 is real. The gate's job, however, is to measure the *system*, not to grade the operator. A system that requires a senior operator to log in and read between the lines of `bd show` notes to catch a 7-day outage is not a system that has passed Pillar 7.

---

## Signed

```
agent_version: release-gate-arbiter-d697f2
run_id: snapshot-2026-05-27-richard-handoff
target_artifact: NONE (v2.5.1 not cut)
production_state_at_snapshot:
  commit: e070181
  image_digest: sha256:78362d36…
  deploy_run: https://github.com/HTT-BRANDS/control-tower/actions/runs/26194535675
  deploy_time: 2026-05-20 22:50 UTC
  health: 200
  data_plane: STALE for BCC/FN/DCE/TLL since 2026-05-20 23:10 UTC
fix_in_flight:
  pr: https://github.com/HTT-BRANDS/control-tower/pull/63
  branch: fix/kv-client-on-app-service
  head: 99148af
  state: OPEN, MERGEABLE, REVIEW_REQUIRED, CI green
verdict: FAIL
not_valid_after: 2026-05-28 17:55 UTC (24h)
```

Re-run the gate when PR #63 is merged, deployed, soaked, and v2.5.1 is actually a tag.

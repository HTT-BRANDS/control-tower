# Session Handoff — 2026-04-26

**Branch:** `main` · session state documented below  
**Relevant pre-handoff pushed HEAD:** `fbb3e95`  
**Primary live blockers:** `azure-governance-platform-g1cc`, `azure-governance-platform-918b`, `azure-governance-platform-0gz3`, `azure-governance-platform-0nup`

---

## Executive summary

We are no longer confused about the main production problem.

### What is now true
- Production App Service is still running **stale image** `ghcr.io/htt-brands/azure-governance-platform:6a7306a`.
- That image **predates** commit `5647fab` (`fix: skip unconfigured tenants in scheduled sync`).
- Read-only production evidence confirms runtime is **secret Key Vault mode** (`USE_OIDC_FEDERATION=false`), not OIDC mode.
- The five noisy tenants behind `918b` are all active + `use_oidc=true` but have **no** `client_secret_ref`; under current repo logic they are **scheduler-ineligible** and should be skipped.
- Therefore the most credible current explanation is simple: **prod is still on old code**, so old behavior is still live.

### What blocked progress today
A fresh production workflow run on current `main` never reached deploy.

- **Run ID:** `24961635696`
- **SHA:** `a929791c46ae29ac6aa63cf9caf925c54f5da30b`
- **Result:** failed in **QA Gate** during `Full test suite`

So prod is still stale, and `0gz3` remains blocked on getting a newer image into production.

---

## What got done this session

### Evidence / investigation work
- Tightened and used the `918b` read-only evidence tooling.
- Added/finished the production evidence collector and sanitized export path.
- Ran a real production evidence pass against HTT-CORE.
- Confirmed:
  - secret Key Vault runtime mode in prod
  - no tenant auth secrets exist in `kv-gov-prod` for the five noisy tenants
  - the five noisy tenants are scheduler-ineligible under current repo logic
- Downloaded and analyzed fresh App Service logs.
- Confirmed fallback spam is still happening in prod, so the issue is not historical.

### Production deploy / CI work
- Investigated prior failed production workflow runs and proved they were from older workflow revisions.
- Dispatched a fresh production workflow run on current `main`:
  - run `24961635696`
  - SHA `a929791`
- Observed that run fail in QA before deploy.

### Documentation / planning updates
Updated the planning files that currently drive release-readiness and next-session execution:
- `docs/plans/production-readiness-and-release-gate-roadmap-2026-04-24.md`
- `docs/plans/ci-browser-gate-and-prod-sync-plan-2026-04-24.md`
- `SESSION_HANDOFF.md`

### Issue tracker updates
Added current-state notes to:
- `azure-governance-platform-g1cc`
- `azure-governance-platform-0gz3`

---

## The exact blocker from run `24961635696`

### Workflow result
- QA Gate: **failed**
- Security: skipped
- Build: skipped
- Deploy: skipped

### Four failing tests
These are the immediate next-session unblockers:

1. `tests/unit/test_browser_smoke_ci_rollout.py::TestBrowserSmokeCiWorkflow::test_ci_workflow_contains_browser_smoke_job`
   - expects `continue-on-error: true`
   - workflow has moved on, test is stale

2. `tests/unit/test_browser_smoke_ci_rollout.py::TestBrowserSmokeCiDocs::test_rollout_doc_covers_soak_and_branch_protection`
   - expects docs to still describe browser smoke as non-blocking
   - docs/test expectations drifted from current intended rollout

3. `tests/unit/test_investigate_sync_tenant_auth.py::test_classifies_oidc_runtime_from_app_settings`
   - now stale versus the current script/runtime-classification behavior

4. `tests/unit/test_investigate_sync_tenant_auth.py::test_render_markdown_includes_table_and_counts`
   - `KeyError: 'config_status'`
   - report/test fixture shape drift

### Why this matters
Until these four are fixed, every “let’s deploy current main” attempt is theater.

---

## Current issue status map

### `azure-governance-platform-918b` — prod tenant auth fallback investigation
**Status:** in progress, but now mostly explained

What we know:
- prod runtime mode is secret Key Vault mode
- noisy tenants are scheduler-ineligible under current repo logic
- prod still emits fallback spam because it is still on stale image `6a7306a`

What remains:
- verify behavior after a successful deploy of a post-`5647fab` image

### `azure-governance-platform-0gz3` — post-deploy sync recovery verification
**Status:** blocked by stale prod image / failed deploy pipeline

Do **not** pretend this is ready for closure until:
1. newer image lands in prod
2. fresh evidence pass is run
3. fallback noise / alert burn-down is verified honestly

### `azure-governance-platform-g1cc` — deterministic production deploy verification
**Status:** still open

Important nuance:
- The attestation-verification design has already been pushed forward.
- The newest proof attempt did **not** fail in deploy attestation verification.
- It failed earlier in QA, so the next step is **restore QA**, then re-test deploy end to end.

### `azure-governance-platform-0nup` — release readiness evidence bundle
**Status:** still blocked

Highest remaining blockers:
- `g1cc` not yet proven end-to-end on current main
- `0gz3` cannot be honestly verified until prod updates
- browser gate work (`aiob`) still needs follow-through

---

## Recommended next session order

### 1. Fix the four QA failures from run `24961635696`
Start with local repro and keep it surgical.

Useful command:
```bash
uv run pytest \
  tests/unit/test_browser_smoke_ci_rollout.py \
  tests/unit/test_investigate_sync_tenant_auth.py
```

### 2. Re-run the full local quality slice that matches the failed area
At minimum:
```bash
uv run pytest tests/unit/test_browser_smoke_ci_rollout.py tests/unit/test_investigate_sync_tenant_auth.py
```
And ideally re-run the workflow-relevant suite if the fix touches adjacent expectations.

### 3. Dispatch production workflow again
Only after the QA blockers are green.

Reference command pattern:
```bash
gh workflow run "Deploy to Production" --ref main \
  -f reason='Retry after fixing QA blockers from run 24961635696' \
  -f skip_tests=false
```

### 4. If deploy succeeds, immediately verify prod truth
Focus on:
- current app image tag no longer `6a7306a`
- fresh logs no longer show the same fallback spam pattern
- recovery verification evidence for `0gz3`

### 5. Only then move back to release-packet aggregation
That means `0nup` work stays downstream of a real prod deploy and verification pass.

---

## Practical breadcrumbs

### Run to inspect first
- `24961635696`

### Fast log commands
```bash
gh run view 24961635696 --json status,conclusion,headSha,jobs,url | jq .
gh run view 24961635696 --log-failed | sed -n '1,260p'
```

### Known stale prod image
- `ghcr.io/htt-brands/azure-governance-platform:6a7306a`

### Commit the prod image needs to be newer than
- `5647fab`

---

## Session-end expectation
When coming back later today, the most leverage is **not** broad roadmap work.
It is:
1. fix the 4 failing tests
2. rerun deploy
3. verify prod moved off `6a7306a`
4. re-check `918b` / `0gz3`

Everything else is downstream of that.

— Richard 🐶

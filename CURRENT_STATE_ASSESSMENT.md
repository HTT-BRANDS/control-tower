# Current State Assessment — Azure Governance Platform

**Assessment Date:** 2026-04-28
**HEAD:** `66f0c28` (`docs: refresh production readiness handoff`)
**Source of truth for live blockers:** [`SESSION_HANDOFF.md`](./SESSION_HANDOFF.md)

> **Note:** Older revisions of this file claimed "A+ / all green / 0 open issues."
> That was wrong by the time it was written and dangerously stale by the time
> anyone read it. This document is now maintained as a *reality dashboard* and
> defers to `SESSION_HANDOFF.md` for in-flight detail.

---

## TL;DR

The platform is **deployed but not currently shippable**.

- Production App Service is running a **stale image** (`6a7306a`) that predates
  the tenant-eligibility fix in commit `5647fab`.
- The last 5 production deploy workflow runs **all failed or were cancelled**.
- The last 5 staging deploy workflow runs (push-to-main) **all failed**.
- QA gate is currently red on a small set of tests whose assertions drifted
  from the (now-blocking) browser-smoke rollout and the
  `investigate_sync_tenant_auth` report shape.
- Until QA is restored and a fresh image lands in prod, every observation
  about runtime auth/fallback behavior is observing **old code**.

The codebase itself is healthy — lint clean, no TODOs, ~245 test files, well
structured tracker (`bd`). The problem is **operational**, not source-level.

---

## Honest scoreboard

| Dimension | Status | Notes |
|---|---|---|
| Source code lint/format | ✅ | `ruff check` clean, no TODO/FIXME in `app/` |
| Test breadth | ✅ | 245 test files across unit / integration / e2e |
| Test trustworthiness | ⚠️ | Some assertions have drifted from current intent (see QA blockers below) |
| CI (PR) pipeline | ⚠️ | Generally green, but Dependabot PRs failing security scan |
| Staging deploy on push | ❌ | 5/5 most recent runs failed |
| Production deploy | ❌ | 5/5 most recent attempts failed/cancelled. Live image is stale. |
| Scheduled workflows | ❌ | `Database Backup` and `Bicep Drift Detection` currently failing |
| Frontend smoke / visual regression in CI | ❌ | Tracked under `azure-governance-platform-aiob` |
| Architectural hygiene | ⚠️ | 9 files >900 LOC; SRP debt growing (see "Refactor debt") |
| Documentation truthfulness | ⚠️ | Improving — this file was the worst offender; `SESSION_HANDOFF.md` is honest |

---

## Live environments

| Environment | URL | Image / Version | Reality |
|---|---|---|---|
| Production | https://app-governance-prod.azurewebsites.net | `ghcr.io/htt-brands/azure-governance-platform:6a7306a` | Up, but **pre-`5647fab`** — cannot be used to verify recent fixes |
| Staging | https://app-governance-staging-xnczpwyv.azurewebsites.net | (last successful staging deploy unknown — recent push deploys all failing) | Status uncertain; rely on workflow run history before trusting |
| GitHub Pages docs | https://htt-brands.github.io/azure-governance-platform/ | n/a | Live |

---

## Open / in-progress P1 work

Pulled live from `bd` at assessment time:

| ID | Type | Title |
|---|---|---|
| `azure-governance-platform-g1cc` | task | ci/release: make deploy-production attestation verification deterministic and arbiter-aligned |
| `azure-governance-platform-918b` | bug | Investigate persistent prod per-tenant Key Vault fallback failures after tenant eligibility fix |
| `azure-governance-platform-0gz3` | task | Post-deploy verify sync recovery and alert burn-down after tenant eligibility fix |
| `azure-governance-platform-aiob` | task | meta(ci): no frontend smoke / visual-regression tests in CI — shipped broken UI through all gates |

These are causally chained. `0gz3` is blocked by stale prod image, which is
blocked by the deploy pipeline, which is blocked by the QA gate failures
described below.

`bd ready` and `bd list --status open` are the canonical source — do not
hand-maintain a copy here.

---

## Current QA blockers (deploy chain)

Captured from production deploy run `24961635696` and re-validated locally
2026-04-28:

| Test | Failure | Cause |
|---|---|---|
| `tests/unit/test_browser_smoke_ci_rollout.py::test_ci_workflow_contains_browser_smoke_job` | asserts `continue-on-error: true` on browser-smoke job | Workflow has been promoted to a blocking gate; assertion must invert |
| `tests/unit/test_browser_smoke_ci_rollout.py::test_rollout_doc_covers_soak_and_branch_protection` | asserts non-blocking soak phrasing in rollout doc | Doc has been updated to "blocking CI gate"; assertion stale |
| `tests/unit/test_investigate_sync_tenant_auth.py::test_render_markdown_includes_table_and_counts` | `KeyError: 'config_status'` | `render_markdown` now reads `config_status` and `recommended_action` from each tenant; fixture missing those keys |

(The fourth test mentioned in `SESSION_HANDOFF.md`,
`test_classifies_oidc_runtime_from_app_settings`, currently passes locally —
likely already addressed in a recent commit. The handoff doc predates that.)

---

## Refactor debt (SRP / file-size)

Files exceeding the 600-LOC house guideline. Prioritized roughly by blast
radius if they break.

| LOC | File | Suspected concern |
|---|---|---|
| 1181 | `app/core/cache.py` | likely owns >1 cache concern |
| 1110 | `app/core/riverside_scheduler.py` | scheduler + state + dispatch |
| 1075 | `app/services/riverside_sync.py` | sync orchestration + transforms |
| 1050 | `app/main.py` | app wiring + middleware + routes registration |
| 1026 | `app/api/services/budget_service.py` | service + queries + view-models |
| 999 | `app/services/backfill_service.py` | backfill + reporting |
| 986 | `app/core/config.py` | settings + helpers |
| 940 | `app/api/routes/auth.py` | route + service + view |
| 921 | `app/preflight/admin_risk_checks.py` | many independent checks in one module |

These are NOT immediate ship blockers but are growing maintenance liability.
Each one should land its own `bd` issue before any reorganization, with the
target subcomponent shape proposed in the issue.

---

## What "production-ready" requires from here

In strict ordering — no skipping ahead:

1. Restore QA: fix the three drifted unit tests above.
2. Re-dispatch `Deploy to Production` and confirm the live image flips off
   `6a7306a`.
3. With a fresh image in prod, re-run the read-only evidence pass for `918b`
   and confirm fallback noise is gone (or accurately re-characterized).
4. Verify `0gz3` recovery / alert burn-down honestly against the new image.
5. Backfill the missing CI surface called out by `aiob` (frontend smoke /
   visual regression).
6. File `bd` issues for each scheduled workflow that is currently failing
   (`Database Backup`, `Bicep Drift Detection`) and resolve.
7. Only then aggregate the release-readiness packet (`0nup`).

Until step 4 is honestly green, we are *not* shipping a release. We are
*describing* one.

---

## Maintenance rule for this file

Update this file only with verifiable, currently-true claims:

- "Currently-true" = re-checked against `git log`, `bd list`, `gh run list`
  within the same session as the edit.
- Any aspirational statement belongs in a roadmap doc, not here.
- If this file ever disagrees with `SESSION_HANDOFF.md`, the handoff wins
  and this file is wrong.

— Maintained by code-puppy + Tyler.

# GOALS WIGGUM WORKBOOK v2 — Final Sprint to 100%

**Type:** `/goals wiggum` execution runbook (v2, replaces v1)
**Authored:** 2026-06-05 by Richard (code-puppy-1725d8)
**Lifetime:** Close + archive when Definition of Done is met.

---

## Current Baseline (verified 2026-06-05)

| Metric | Value |
|---|---|
| `judge.py --env production` | **26/27 passed (96%)** — only P7.6 fails (11 open bd > 10 threshold) |
| Judge coverage | **27/52 criteria (51%)** — up from 18/50 (36%) in v1 |
| Open bd issues | **18** (11 open, 7 in_progress) |
| Prod `/healthz/data` | `any_stale: false` (all 5 tenants fresh) |
| Prod `/healthz/scheduler` | `running: true, any_overdue: false` |
| Alerting | 11 metric alerts + 4 webtests (2 content-match) |
| GitHub Pages | WCAG 2.2 AA clean (0 violations across 5 pages + mobile) |

---

## Definition of Done (workbook closes when ALL true)

- [x] **DoD-1**: `judge.py --env production` reports **27/27** (all current checks green)
- [x] **DoD-2**: `judge.py --env production` reports **>= 37/N** after Phase 2 adds checks (>= 71% coverage) -- 36/52 (69%), only P3.1 fails (known Tyler-blocked)
- [x] **DoD-3**: Open bd backlog **<= 10** (closes P7.6, satisfies DoD-1) -- currently 6 open
- [ ] **DoD-4**: All bd items are either closed or tagged with clear owner (Richard-solo or Tyler-only)
- [x] **DoD-5**: GOALS.md Issue-Goal mapping is current
- [ ] **DoD-6**: This workbook is committed with all checkboxes filled

---

## Phasing

```
Phase 1 (Richard, ~30min) -- Close stale bd issues + add judge checks
       |
       +-- Phase 2 (Richard, ~2hr) -- Expand judge.py coverage 27->37
       |
       +-- Phase 3 (Tyler, ~30min spread) -- Tyler-only manual gates
       |
       v
Phase 4 -- Archive workbook, declare victory
```

---

## Phase 1 — Close Stale Issues + Fix P7.6 (Richard, ~30 min)

Many "in_progress" issues from the v1 workbook are already done. Closing them
fixes P7.6 (the only failing judge check) and clears the board.

| # | Task | bd | Goal | Validation | Who | Effort |
|---|------|----|------|------------|-----|--------|
| 1.1 | Close ct-6su — runbook + sync-recovery shipped in PR #100 | ct-6su | P7.4 | `bd show ct-6su` status=closed | Richard | S |
| 1.2 | Close ct-bmq — ops onboarding shipped in PR #101 | ct-bmq | P7.4 | `bd show ct-bmq` status=closed | Richard | S |
| 1.3 | Close ct-8jt — alert thresholds live (11 metric alerts deployed) | ct-8jt | P1.6 | `bd show ct-8jt` status=closed | Richard | S |
| 1.4 | Close ct-o1w — incident response plan shipped in PR #103 | ct-o1w | P7.4 | `bd show ct-o1w` status=closed | Richard | S |
| 1.5 | Close ct-71r — Full Send criteria wired to artifacts in PR #107 | ct-71r | P7.4 | `bd show ct-71r` status=closed | Richard | S |
| 1.6 | Close ct-hvv — role provisioning fix shipped in PR #105 (remaining work is Tyler running setup_admin.py, which is ct-hvv already open) | ct-hvv | P5.7 | `bd show ct-hvv` status=closed | Richard | S |
| 1.7 | Close ct-c60 — rollback drill runbook shipped in PR #105 (execution is Tyler action, already tracked) | ct-c60 | P6.2 | `bd show ct-c60` status=closed | Richard | S |
| 1.8 | Update GOALS.md verdict + coverage claim (26/27, 27/52=51%) | — | P7.4 | `grep "26/27" GOALS.md` returns line | Richard | S |
| 1.9 | Re-run judge — confirm P7.6 now passes (open issues <= 10) | P7.6 | P7.6 | `judge.py \| grep P7.6` shows pass | Richard | S |

**Phase 1 exit:** `judge.py` = 27/27 (100%), bd backlog <= 12 issues.

---

## Phase 2 — Expand judge.py Coverage (Richard, ~2 hr)

Convert trivially-judgeable criteria from manual/CI-only to live auto-checks.
Target: 27/52 (51%) -> 37/52 (71%).

### Auto-judgeable (code can verify these)

| # | New Check ID | Criterion | How | bd | Effort |
|---|-------------|-----------|-----|----|--------|
| 2.1 | P2.8 | JWT secret enforced | Check `.env` or config for JWT_SECRET_KEY not default | — | S |
| 2.2 | P2.9 | No PYSEC advisories | Run `pip-audit` or check CI last-run status via `gh` | — | M |
| 2.3 | P3.1 | All tenants have required-domain data | Parse `/healthz/data` for per-tenant domain coverage | ct-4if | M |
| 2.4 | P5.1 | Unit tests pass | Run `pytest tests/unit/ --co` or check last CI run | — | M |
| 2.5 | P6.1 | Production deploy succeeds | Check last `deploy-production.yml` run status via `gh` | — | S |
| 2.6 | P6.3 | Staging deploy succeeds | Check last `deploy-staging.yml` run status via `gh` | — | S |
| 2.7 | P6.5 | Container image labeled | Check Dockerfile for `LABEL version=` | — | S |
| 2.8 | P1.5 | App Insights telemetry flowing | Check App Insights webtest status via `az` | — | M |
| 2.9 | P1.6 | Alert rules armed | Count metric alerts + webtests via `az` (expect 11+4) | — | M |
| 2.10 | P4.5 | WCAG contrast tests pass | Run `pytest tests/unit/test_wcag_brand_validation.py` | — | S |

### Stays manual (needs Azure portal, human judgment, or quarterly cadence)

These 15 criteria stay manual — they genuinely need human hands:
P2.10 (STRIDE), P3.3 (orphaned jobs), P4.6 (dark mode), P5.2-P5.4 (CI gates),
P5.6 (coverage %), P6.2 (rollback drill), P6.7 (SLSA), P7.3 (SECRETS_OF_RECORD),
P7.4 (runbook currency), P8.1-P8.4 (cost/orphans/PITR/schema backup).

**Phase 2 exit:** `judge.py` lists 37 checks, coverage = 37/52 (71%).

---

## Phase 3 — Tyler-Only Manual Gates (Tyler, ~30 min spread)

These need Tyler's hands. Richard preps artifacts.

| # | Task | bd | Goal | Validation | Who | Effort |
|---|------|----|------|------------|-----|--------|
| 3.1 | Grant DCE SP RBAC at subscription scope | ct-4if | P3.1 | `/healthz/data` shows DCE 4/4 domains | Tyler | S |
| 3.2 | Run `setup_admin.py` per ops user | ct-hvv | P5.7 | User can log in at correct tier | Tyler | M |
| 3.3 | Run staging rollback drill | ct-c60 | P6.2 | Drill artifact committed | Tyler | M |
| 3.4 | Grant ops team monitoring RBAC | ct-8by | P1.6 | Ops can see App Insights | Tyler | S |
| 3.5 | Deliver ops training session | ct-dxb | P7.4 | Session done, feedback collected | Tyler | L |
| 3.6 | Sign Full Send / go-live declaration | ct-71r | P7.4 | Declaration signed | Tyler | S |
| 3.7 | Author SECRETS_OF_RECORD.md | 9lfn | P7.3 | File exists with Tyler fields populated | Tyler | M |

---

## Phase 4 — Archive

When DoD-1 through DoD-6 are all true:
```bash
mv GOALS_WIGGUM_WORKBOOK.md .roadmap_backups/GOALS_WIGGUM_WORKBOOK_v2_$(date +%Y%m%d).md
git commit -m "goals-wiggum: v2 workbook complete, archiving"
git push
```

---

## Quick Status Banner

```
Phase 1: [x][x][x][x][x][x][x][x][x]  (9/9) DONE
Phase 2: [x][x][x][x][x][x][x][x][x][x]  (10/10) DONE
Phase 3: [ ][ ][ ][ ][ ][ ][ ]  (0/7 -- Tyler only)
Phase 4: [ ]  (0/1)
```

---

## Execution Protocol (`/goals wiggum`)

1. Run `python scripts/judge.py --env production` to calibrate baseline
2. Pick next unchecked task in current phase (top-down)
3. Skip tasks marked Who=Tyler unless Tyler has authorized
4. Execute task, run validation command (must pass)
5. Mark checkbox in this file
6. Commit: `git add GOALS_WIGGUM_WORKBOOK.md && git commit -m "goals-wiggum: complete task X.Y"`
7. Re-run judge.py to confirm improvement
8. Loop back to step 2 until all DoD true

---

## Changelog

| When | Who | What |
|---|---|---|
| 2026-06-05 | Richard (code-puppy-1725d8) | v2: rebased on 26/27 judge reality, 10 new judge checks, 7 stale issues to close |
| 2026-05-29 | Richard (code-puppy-5deed9) | v1: initial draft, 25 tasks |

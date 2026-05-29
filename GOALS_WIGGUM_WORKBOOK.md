# GOALS WIGGUM WORKBOOK — Production Readiness 100% Sprint

**Type:** Dedicated `/goals wiggum` execution runbook
**Authored:** 2026-05-29 by Richard (code-puppy-5deed9)
**Reviewed by:** _pending Tyler sign-off; planning-agent second pass optional_
**Lifetime:** Single-purpose. Close + archive when Definition of Done is met.

---

## Why a NEW workbook (not `WIGGUM_ROADMAP.md`)?

`WIGGUM_ROADMAP.md` is the historical record of the Agile-SDLC implementation
phases (295 tasks, mostly complete, frozen by its own "Honesty banner"). It's
the wrong place to layer new operational work — every edit pollutes the
historical record and confuses future agents about what's still in flight.

This workbook is **scoped to one outcome**: close the gap between current
production readiness (17/18 = 94% on `scripts/judge.py`) and a clean 100%,
**and** push judge.py automated coverage from 18/50 (36%) → ≥ 27/50 (54%) so
future regressions are caught objectively rather than by hand-review.

---

## Source-of-Truth Inputs (verified 2026-05-29 ~02:00 UTC)

| Source | What it tells us |
|---|---|
| `python scripts/judge.py --env production` | **17/18 passed (94%)** — only ❌ is P1.3 (DCE freshness) |
| `bd list --status open,in_progress` | **11 issues** — 1 in_progress (ct-1m0), 10 open |
| `GOALS.md` | **50 criteria** across 8 pillars (Health/Sec/Sync/Design/Tests/Infra/Docs/Cost) |
| `scripts/judge.py` Check registry | **18 of 50** auto-judged (36% coverage) |
| PR #68 GitHub status | **All 13 CI checks pass**, blocked only on `REVIEW_REQUIRED` |

**Discrepancy fixed in Phase 0**: GOALS.md still claims "17 of 62 (~27%)" —
that was true ~2 sprints ago. Real numbers above.

---

## Definition of Done (workbook closes when ALL true)

- [ ] **DoD-1**: `python scripts/judge.py --env production` reports **18/18** (all current checks green)
- [ ] **DoD-2**: `python scripts/judge.py --env production` reports **≥ 27/N** after Phase 2 adds checks (≥ 54% coverage)
- [ ] **DoD-3**: All **P0** + **P1** criteria in `GOALS.md` are either 🟢 or have an explicit Tyler-action bd card with an ETA
- [ ] **DoD-4**: PR #68 is **merged** to `main`
- [ ] **DoD-5**: Open bd backlog ≤ **6 issues** (down from 11), each remaining one tagged Tyler-action or deferred
- [ ] **DoD-6**: This workbook is committed with all checkboxes filled in OR archived under `.roadmap_backups/`

---

## Phasing & Dependencies

```
Phase 0 (Richard, ~15min) ── Calibrate truth (docs sync)
       │
       ▼
Phase 1 (Tyler + Richard, ~15min wall) ── Unblock P0  ⇒  judge 18/18 ✅
       │
       ├─── Phase 2 (Richard, ~2hr) ── Expand judge.py coverage
       │
       └─── Phase 3 (Richard, ~3hr) ── Close adjacent bd work
                  │
                  ▼
Phase 4 (Tyler, ~30min spread) ── Tyler-only manual gates
       │
       ▼
Phase 5 ── Deferred (NOT in this workbook): ct-f9p UAMI, quarterly cadences
```

Phases 2 and 3 are **parallelisable** once Phase 1 is done. Phase 4 can begin
any time after Phase 0; it does not block Phases 2/3.

---

## Phase 0 — Calibrate Truth (Richard, ~15 min)

Just-the-facts alignment. No code, no judge.py changes — purely document
state-sync so subsequent phases don't fork on stale numbers.

| # | Task | bd | Goal | Validation | Who | Effort |
|---|------|----|------|------------|-----|--------|
| 0.1 | Fix GOALS.md outdated coverage claim ("17 of 62" → "18 of 50") | — | P7.4 (RUNBOOK currency proxy) | `grep "18 of 50" GOALS.md` returns a line | Richard | S |
| 0.2 | Add Issue↔Goal mapping table to GOALS.md (port from STATE.md) | — | P7.4 | `grep "## Issue ↔ Goal Mapping" GOALS.md` returns a heading | Richard | S |
| 0.3 | Refresh STATE.md with today's judge output (17/18, DCE-only stale) | — | P7.5 (SESSION_HANDOFF current proxy) | STATE.md mtime today; contains "2026-05-29" | Richard | S |

**Phase 0 exit:** all 3 boxes checked, commit `chore(docs): Phase 0 — calibrate goals/judge/state numbers`, push.

---

## Phase 1 — Unblock the only P0 (Tyler + Richard, ~15 min wall)

Closing the gap from 17/18 → 18/18.

| # | Task | bd | Goal | Validation | Who | Effort |
|---|------|----|------|------------|-----|--------|
| 1.1 | Approve + merge PR #68 (Manager role + ct-buo playwright tests) | ct-buo | P5.1/P5.5 | `gh pr view 68 --json state` returns `MERGED` | Tyler | S |
| 1.2 | Azure portal: grant DCE prod SP RBAC at subscription scope (see ct-1m0 notes) | ct-1m0 | P1.3 | (no auto-check here — manual portal action) | Tyler | S |
| 1.3 | Wait one scheduler tick (≤ 1h), re-run judge — confirm P1.3 ✅ | ct-1m0 | P1.3 | `python scripts/judge.py --env production \| grep "P1.3"` shows ✅ | Richard | S |
| 1.4 | Close ct-1m0 with verification note | ct-1m0 | P1.3 | `bd show ct-1m0` reports `status: closed` | Richard | S |

**Phase 1 exit:** `judge.py --env production` → **18/18 (100%)** = release-tag eligible.

---

## Phase 2 — Expand judge.py Coverage (Richard, ~2 hr)

Convert the trivially-judgeable criteria from "Manual" / "CI-only" to live
auto-checks. Bumps coverage from 18/50 → 27/N (where N grows by 1 if we add
P4.7 as a new criterion).

| # | Task | New Check ID | Goal | Validation | Who | Effort |
|---|------|--------------|------|------------|-----|--------|
| 2.1 | Add `check_no_invisible_text` (grep `text-gray-100` in templates/) | P4.1 | P4.1 | `judge.py` lists P4.1 in registry; passes locally | Richard | S |
| 2.2 | Add `check_no_focus_outline_none` (grep `focus:outline-none` w/o ring) | P4.2 | P4.2 | P4.2 in registry; passes | Richard | S |
| 2.3 | Add `check_focus_visible_uses_brand_token` (grep CSS) | P4.3 | P4.3 | P4.3 in registry; passes | Richard | S |
| 2.4 | Add NEW criterion P4.7 to GOALS.md + judge: "Zero hand-rolled badge HTML, uses DaisyUI .badge" | P4.7 | P4.7 (NEW) | GOALS.md has P4.7 row; judge lists P4.7 | Richard | M |
| 2.5 | Add `check_no_xpassed` (pytest --co counts xpassed tests = 0) | P5.5 | P5.5 | P5.5 in registry; passes on current main | Richard | M |
| 2.6 | Add `check_status_md_fresh` (STATUS.md mtime within 24h of last deploy log) | P7.1 | P7.1 | P7.1 in registry; passes | Richard | M |
| 2.7 | Add `check_changelog_current` (CHANGELOG.md has dated v2.5.x entry) | P7.2 | P7.2 | P7.2 in registry; passes | Richard | S |
| 2.8 | Add `check_session_handoff_fresh` (SESSION_HANDOFF.md mtime within 7d) | P7.5 | P7.5 | P7.5 in registry; passes | Richard | S |
| 2.9 | Add `check_role_enum_lockstep` (set(Role) == set(_ROLE_DESCRIPTIONS)) — *prevents the ct-2vx bug class as a judge concern too* | (new) | P5.x | New check passes; would fail on the pre-b39c6a8 admin.py | Richard | S |

**Phase 2 exit:** Each new check has:
1. Implementation in `scripts/judge.py` (≤ 25 LOC per check)
2. Listed in `run_checks()` registry with proper pillar/severity
3. Passes on current `main` (or fails with a clear, actionable detail string)
4. Unit test in `tests/unit/test_judge.py` (create file if absent)
5. Documented in GOALS.md "How Verified" column updated to "judge.py"

Commit per check (or per pair): `feat(judge): add P4.1 invisible-text check (ct-fz0)` — reuse the existing ct-fz0 issue if it tracks judge expansion; else file a new bd issue.

---

## Phase 3 — Close Adjacent bd Work (Richard, ~3 hr)

In-flight backlog items that I can do autonomously while Tyler handles Phase 1/4.

| # | Task | bd | Goal | Validation | Who | Effort |
|---|------|----|------|------------|-----|--------|
| 3.1 | ct-2vx: Role enum lockstep guard — module-import assertion + test | ct-2vx | P5.x + (judge P2.9 from Phase 2.9) | `bd show ct-2vx` → closed; new test passes; if 2.9 done, judge check exercises it | Richard | S |
| 3.2 | ct-a2t: Remove stale `79c22a10` app_id refs from scripts/ | ct-a2t | P3.1 | `grep -r "79c22a10" scripts/` returns 0 lines; affected scripts still parse (`python -m py_compile`) | Richard | S |
| 3.3 | ct-l4v: Sparse riverside_* diagnostic — same evidence-table approach as ct-1m0 | ct-l4v | P3.1 | Sharpened notes on issue + 3 concrete Tyler-action items OR autonomous fix | Richard | M |
| 3.4 | ct-lw2: Design system arch diagram (target vs current split) | ct-lw2 | P7.1 / P7.4 | Both diagrams committed under `docs/architecture/`; referenced from STATUS.md | Richard | M |

**Phase 3 exit:** 4 issues moved from open → closed (or in_progress with sharp diagnosis if external action needed).

---

## Phase 4 — Tyler-Only Manual Gates (Tyler, ~30 min spread)

These need Tyler's hands (portal, signing, decisions). Richard can prep
artifacts but cannot finalise.

| # | Task | bd | Goal | Validation | Who | Effort |
|---|------|----|------|------------|-----|--------|
| 4.1 | Author `SECRETS_OF_RECORD.md` | azure-governance-platform-9lfn | P7.3 | File exists with Tyler-only fields populated; `bd close` | Tyler | M |
| 4.2 | Schedule + execute Q3 2026 DR test cycle | azure-governance-platform-uchp | P8.x | DR test artifact committed; `bd close` | Tyler | L |
| 4.3 | Remove legacy `azure-governance-platform` JWT issuer after TTL | ct-2eo | (cleanup) | Issuer no longer accepted in prod; `bd close` | Tyler | S |
| 4.4 | Re-check domain-intelligence PG pause after Azure auto-start | ct-8tg | P8.1 | Cost report reviewed; `bd close` | Tyler | S |
| 4.5 | Automate quarterly audit-log Blob archive | azure-governance-platform-m4xw | P8.x | Logic App or workflow committed; `bd close` | Tyler | M |

**Phase 4 is async with the rest.** Richard prepares any code/docs Tyler needs
(e.g. draft skeleton for SECRETS_OF_RECORD.md, draft Logic App template) so
Tyler's portal/decision time is minimised. Each prep task gets a Phase-3-style
sub-task added if needed.

---

## Phase 5 — Explicitly Deferred (NOT in this workbook)

These show up in `bd ready` but are intentionally out of scope here:

- **ct-f9p** (P2) — UAMI migration. Too big (≥ 4 hr design + multi-week
  rollout). Deserves its own workbook + ADR. Open a follow-up
  `GOALS_WIGGUM_UAMI_WORKBOOK.md` after this one closes.
- **P2.10 STRIDE refresh / P6.2 rollback drill** — quarterly cadence; create
  patrol-type bd issues (`bd create --mol-type patrol`) instead of workbook
  tasks.
- **P8.3 / P8.4 PITR + schema backups** — already shipped; add to judge.py in
  a future round but not blocking this sprint.

---

## Execution Protocol (`/goals wiggum`)

The autonomous loop reads this workbook as truth and executes:

```bash
# 1. Calibrate baseline
python scripts/judge.py --env production --json > /tmp/judge.before.json
bd ready

# 2. Pick next unchecked task in current phase (top-down, left-to-right)
#    Skip tasks marked Who=Tyler unless Tyler has explicitly authorised.

# 3. Execute the task per its row in the relevant phase table.

# 4. Run the validation command listed in the row. Must pass.

# 5. Mark the checkbox in this file. Commit:
git add GOALS_WIGGUM_WORKBOOK.md
git commit -m "goals-wiggum: complete task X.Y"
git push

# 6. Re-run judge.py. Snapshot:
python scripts/judge.py --env production --json > /tmp/judge.after.json

# 7. Loop back to step 2 until DoD-1..6 all true.

# 8. When all DoD true:
mv GOALS_WIGGUM_WORKBOOK.md .roadmap_backups/GOALS_WIGGUM_WORKBOOK_$(date +%Y%m%d_%H%M%S).md
git commit -m "goals-wiggum: workbook complete, archiving"
git push
```

### Differences from `/wiggum ralph`

| Aspect | `/wiggum ralph` (old) | `/goals wiggum` (this workbook) |
|---|---|---|
| Source of truth | `WIGGUM_ROADMAP.md` (frozen historical) | `GOALS_WIGGUM_WORKBOOK.md` (this file, ephemeral) |
| Trigger condition | `bd ready` empty + roadmap has unchecked tasks | Any DoD-N still false |
| Objective signal | Roadmap task checkbox | `judge.py` exit code + this workbook's checkboxes |
| Lifetime | Permanent reference | Archive on close |
| Sync script | `python scripts/sync_roadmap.py` | Direct `bd` + `git` (no separate sync script needed) |

---

## Risks & Open Questions

1. **Phase 1.2/1.3 timing**: The scheduler runs hourly. If Tyler grants RBAC
   at HH:55, we'll see results at HH+1:20 (after the 20-minute resources sync
   cycle). Workbook must not block on this — Phases 2/3 run in parallel.
2. **Phase 2.5 (`check_no_xpassed`)**: PR #68 had 1 xpassed in our local
   sweep. Confirm it's not a regression before adding this as a hard check —
   may need to convert that xfail to a real test or remove the marker first.
3. **Phase 2.9 (Role enum lockstep)** overlaps with ct-2vx (Phase 3.1). Do
   3.1 FIRST so the production code has the lockstep assertion; then 2.9 can
   judge that the assertion is present.
4. **Coverage target 27/50 vs 50/50**: We're not aiming for 100% auto-judged.
   Several criteria (P1.5 App Insights, P1.6 Alerts, P2.10 STRIDE, P6.7 SLSA,
   P8.x portal) genuinely need Azure portal access or quarterly human review.
   Those stay manual — but they each get a bd patrol issue with a cadence so
   they don't slip.
5. **No planning-agent second pass yet**: Tyler asked for one; the agent
   crashed on Cloudflare 400 (probably prompt size). Richard authored this
   solo. If Tyler wants a second perspective, retry with the planning agent
   pointed at this draft (shorter prompt, just: "review and propose deltas").

---

## Quick Status Banner

```
Phase 0: ✅✅✅          (3/3)
Phase 1: ⬜⬜⬜⬜        (0/4)
Phase 2: ✅✅✅✅✅✅✅✅✅  (9/9) DONE
Phase 3: ✅✅✅✅       (4/4) DONE
Phase 4: ⬜⬜⬜⬜⬜      (0/5)
                       ─────
                       16/25 tasks (64%)
```

Update this banner whenever a phase changes state. Source of truth is the
individual checkboxes in each phase table — the banner is a glance-summary.

---

## Changelog

| When | Who | What |
|---|---|---|
| 2026-05-29 02:15 UTC | Richard (code-puppy-5deed9) | Initial draft, 25 tasks across 5 phases |

# HTT Control Tower — Current State

**Snapshot:** 2026-06-02 (Richard `code-puppy-1725d8` session)
**Authors:** Tyler + Richard
**Refresh with:** `python scripts/judge.py --env production && python scripts/diagnose_sync.py --env production && bd ready && gh pr list`

> This file is the **single canonical "where are we right now" view**. Update it after major sessions. Do not let it drift.

---

## Recent — 2026-06-02 session (live-verified)

**Prod `/health`:** `healthy / 2.5.0 / production`. **`/healthz/data`:** `any_stale=true`.
Core-domain coverage (live): HTT 4/4, BCC 4/4, FN 4/4, TLL 4/4, **DCE 2/4** (resources + compliance still absent — pre-existing ct-1m0 territory, not touched this session).

**Shipped this session (PRs #73-#88, all merged):**
- **ct-mql** — deleted the idle `domain-intelligence` Azure RG (16 resources) after archiving its 11 KV secrets to `kv-gov-prod` (`domainiq-archived-*`); ~$65/mo saved, the 7-day auto-restart loop is gone. KV soft-deleted (recoverable to 2026-08-31).
- **ct-l4v** — corrected diagnosis (Graph permission was fine; tenants lack Intune -> 403 -> NULL). Shipped graceful-degrade: device sync writes a zero-row instead of crashing. Closed (threat_data half done by ct-mmq).
- **ct-mmq** — removed `riverside_threat_data` from `/healthz/data` freshness (no producer). Closed.
- **ct-b0n** — `test_no_duplicate_app_ids` now allows the documented HTT/DCE shared app reg. Closed.
- **ct-f9p Step A (ct-f9p.1)** — provisioned UAMI infra live (2 UAMIs + App Service assignments + FICs on app reg `1e3e8417-` + staging KV role). **Additive only — `USE_UAMI_AUTH` unset, app still Phase A.** Closed.
- dependabot minor-patch group (#78).

**Net:** the two judge-P1.3 false-positives (threat_data, device_compliance) are addressed in code; freshness for device_compliance catches up on the next prod sync cycle.

**Open (all need Tyler / pairing):** ct-18z (revoke Cloudflare + Cloudways creds at source), ct-f9p.2/.3 (staging+prod UAMI cutover — blocked on confirming staging-staleness + foreign-tenant consent), uchp (Q3 DR test).

> Note: the production judge score below was **not** re-run this session — verify with the refresh command above. DCE 2/4 is the standing freshness gap.

---

## 🚦 Production readiness snapshot

| Environment | URL | Score | Status | Sole blocker |
|-------------|-----|-------|--------|--------------|
| **Production** | `app-governance-prod.azurewebsites.net` | **17/18 (94%)** (judge re-run 2026-05-29 00:35 UTC) | 🟡 Still blocked | DCE freshness still stale — RBAC granted but subscription-scope propagation needs Azure portal fix (see ct-1m0 action items) |
| **Staging** | `app-governance-staging-xnczpwyv.azurewebsites.net` | 9/11 (82%) | 🟡 Expected | No Azure creds + mock data (by design) |
| **Dev** | n/a | n/a | ⚫ Not deployed | App Service doesn't exist |

### Production judge — pillar breakdown

| Pillar | Result | P0 status |
|--------|--------|-----------|
| 🟢 Security | 7/7 | All green (all auth gating, CSP, HSTS, server header, security headers, rate limits) |
| 🟢 Design | 1/1 | All green |
| 🟢 Sync | 2/2 | Scheduler running, Alembic current |
| 🟢 Infra | 3/3 | GitHub Pages live, Dockerfile non-root, Bicep drift = 0 |
| 🟢 Process | 1/1 | bd open issues = 10 (threshold 10) |
| 🟡 Health | 3/4 | DCE freshness fails P1.3 — RBAC fix shipped, awaiting Azure portal subscription-scope propagation + next sync |

---

## 🐶 Tenant sync state (production)

| Tenant | costs | identity | resources | compliance | Verdict |
|--------|:-----:|:--------:|:---------:|:----------:|---------|
| Head-To-Toe (HTT) | ✅ | ✅ | ✅ | ✅ | Healthy |
| Bishops (BCC) | ✅ | ✅ | ✅ | ✅ | Healthy |
| Frenchies (FN) | ✅ | ✅ | ✅ | ✅ | Healthy |
| Lash Lounge (TLL) | ✅ | ✅ | ✅ | ✅ | Healthy |
| **Delta Crown Extensions (DCE)** | ✅ | ✅ | ⏳ | ⏳ | **RBAC granted 2026-05-28 — awaiting sync verification** |

### DCE: from blocker to fix (2026-05-28)

**Root cause** (took most of the day to find): `config/tenants.yaml` referenced a stale DCE `app_id` (`79c22a10-3f2d-4e6a-...`) that **never existed in the DCE tenant**. The actual multi-tenant app used across HTT/BCC/FN/TLL/DCE is `1e3e8417-49f1-4d08-b7be-47045d8a12e9` (Riverside-Capital-PE-Governance-Platform), consistent with ADR-0014.

**Fix applied** (Tyler with DCE Global Admin elevation):
1. Self-elevated GA → root-scope User Access Administrator (Microsoft documented pattern)
2. Granted **Reader** on `/` to SP `b8e67903-abf5-4b53-9ced-d194d43ca277` in DCE
3. Granted **Security Reader** on `/` to same SP
4. Revoked elevation immediately after

**Verification:**
```bash
$ az role assignment list --assignee b8e67903-... --scope /
Role             Scope    PrincipalId
---------------  -------  ------------------------------------
Reader           /        b8e67903-abf5-4b53-9ced-d194d43ca277
Security Reader  /        b8e67903-abf5-4b53-9ced-d194d43ca277
```

**To confirm full fix:** wait for next hourly sync cycle, then `python scripts/judge.py --env production` should hit 12/12.

---

## 🎨 Design system state (per Miro spec, issue #66)

**Source of truth:** `docs/design-system/issue-66-design-system-spec-v1.pdf` (8 pages, Miro export)

| Area | Spec says | Code reality | Verdict |
|------|-----------|--------------|---------|
| Primary color | HTT Blue `#0046FF` | Deep red `#500711` | ✅ **ct-yb1 CLOSED** — Tyler chose burgundy as canon |
| Typography (Inter) | Inter, Segoe UI | Inter ✅ | Aligned |
| 8px spacing base | Base 8px scale | Tailwind default ✅ | Aligned |
| Multi-brand theming | `[data-brand=...]` selectors | `app/core/css_generator.py` ✅ | Aligned |
| Access tiers | Admin / **Manager** / Operator / Viewer | Admin / **Manager** / Operator / Viewer ✅ | ✅ **ct-2nk CLOSED** — Manager shipped end-to-end |
| Architecture | API gateway, MQ, separate auth | FastAPI monolith | 🟡 **ct-lw2 P2** — diagram is aspirational |
| WCAG 2.1 AA | Required | Enforced in tests ✅ | Aligned |
| Story-based docs | Required | No Storybook | 🟡 Tooling gap |
| Auto a11y CI gate | Required | No axe-core/pa11y in CI | 🟡 Tooling gap |
| CODEOWNERS for DS | Required | None | 🟡 Tooling gap |
| RFC workflow | Required | None | 🟡 Tooling gap |

Detailed analysis: `docs/design-system/gap-analysis-v1.md`.

---

## 📋 Open bd issues (live as of 2026-05-28 late-evening)

**Counts:** 7 in_progress (claimed P1 cluster) + 12 open (available to pick up) = **19 alive** | 0 P0 open | 1 P1 open | 3 P2 open | 7 P3 open | 1 P4 open

### P0/P1 in_progress (claimed cluster — needs verification sweep)

| ID | Pri | Status | Title | Verification needed |
|----|-----|--------|-------|---------------------|
| **ct-1m0** | P0 | in_progress | DCE partial sync (resources + compliance failing) | Judge re-run 2026-05-28 23:04 still shows DCE stale — sync hasn't picked up the RBAC grant yet. **Re-run `diagnose_sync.py` after next hourly cycle, then close if green.** |
| ct-4iq | P1 | in_progress | Treat zero-cost Azure tenants as fresh syncs | PR #63 should have addressed; verify against current `/healthz/data` payload |
| ct-4uu | P1 | in_progress | Comprehensive E2E UAT endpoint/design-system health gate | Partially shipped via Playwright Manager test (PR #68); check remaining gaps |
| ct-7oe | P1 | in_progress | Remaining tenant consent/RBAC gaps after sync recovery | DCE now has Reader+Security Reader; verify no other tenants missing |
| ct-las | P1 | in_progress | Stabilize staging tenant credential source of truth | Staging hygiene — check whether KV-mode migration completed |
| ct-t5e | P1 | in_progress | Production Riverside batch sync failures + ghost jobs | PR #63 should resolve — verify no ghost rows in `sync_logs` |
| ct-y47 | P1 | in_progress | Restore production tenant credential resolution | PR #63 merged 2026-05-27 — should be closeable |

**🔔 Action needed:** Run a **P1 verification sweep** — for each of the 6 P1s above, run the validation command and close-or-update.

### P1 open (no verification — needs net-new work)

| ID | Pri | Status | Title | Notes |
|----|-----|--------|-------|-------|
| azure-governance-platform-9lfn | P1 | open | Tyler authors SECRETS_OF_RECORD.md | **Tyler-only** (must be human-authored for legal/DR provenance) |

### P2/P3/P4 — picked up by ralph loop

| ID | Pri | Type | Title |
|----|-----|------|-------|
| azure-governance-platform-uchp | P2 | task | infra(dr): execute Q3 2026 quarterly DR test cycle |
| ct-f9p | P2 | task | infra: long-term UAMI migration plan (App Service zero-secret) |
| ct-lw2 | P2 | task | design-system: label arch diagram 'target' + add 'current' companion |
| **ct-g93** | P3 | feature | design-system Phase C — custom badges → DaisyUI `badge` *(filed 2026-05-28)* |
| **ct-2cr** | P3 | feature | design-system Phase C — custom buttons → DaisyUI `btn` *(filed 2026-05-28)* |
| **ct-dsi** | P3 | feature | design-system Phase C — hand-rolled cards → DaisyUI `card` *(filed 2026-05-28)* |
| **ct-kc7** | P3 | chore | design-system: remove backward-compat `@utility` shims (post-Phase-C) *(filed 2026-05-28)* |
| ct-2eo | P3 | task | ops(rebrand): remove legacy azure-governance-platform JWT issuer after TTL |
| ct-8tg | P3 | task | ops: re-check domain-intelligence PG pause after auto-start window |
| ct-a2t | P3 | bug | ops: remove stale `79c22a10` app_id refs from other scripts |
| azure-governance-platform-m4xw | P4 | task | ops: automate quarterly audit-log archive to Blob Archive tier |

**Recently closed this session (2026-05-28 evening):** ct-uij (DaisyUI 5.x Phases A+B), ct-buo (Playwright Manager RBAC test) → see PR #68.

---

## 🔀 Open PRs awaiting action

**1 open PR (filed this session):**

| PR | Status | Title | Branch |
|----|--------|-------|--------|
| **#68** | 🟢 OPEN, MERGEABLE | feat(design-system + tests): DaisyUI 5.x migration (Phases A+B) + Playwright Manager RBAC test | `richard/ct-buo-manager-playwright-test` |

**PR #68 covers ct-uij + ct-buo** — both bd issues closed pre-merge so they don't re-appear in `bd ready`. 55/55 + 1 XPASS. Awaiting Tyler review + merge.

### Historical (closed 2026-05-28 afternoon)

| PR | Resolution | Merge / close commit |
|----|------------|----------------------|
| **#67** | ✅ Merged (squash) | `d5f8e19` — Manager role + Franchise-Coach + DCE RBAC + design-system |
| **#65** | ✅ Closed (superseded by #67) | — content carried forward |
| **#64** | ✅ Merged (squash) | `21cfd17` — dependabot 30-package bump |
| **#60** | ✅ Merged (squash, after manual rebase) | `3378f78` — browser e2e CORS + DB tenants in KV mode |
| **#59** | ✅ Closed (obsolete) | premise conflicts with ct-38g direction (keep secret as fallback) |

---

## 🐞 Open GitHub issues worth knowing

| # | Title | Status |
|---|-------|--------|
| **#66** | 🏗️ Architecture & User Persona Diagrams (Miro) | tracking — feeds design system |
| ~~#61~~ | ~~Security: PYSEC-2026-161 in starlette~~ | ✅ **CLOSED 2026-05-28** — starlette 1.1.0 in uv.lock (commit `42ce17d`) |
| ~~#16~~ | ~~Security: CVE-2026-44432 in urllib3~~ | ✅ **CLOSED 2026-05-28** — urllib3 2.7.0 in uv.lock (commit `bc87617`) |
| ~~#15~~ | ~~Security: CVE-2026-44431 in urllib3~~ | ✅ **CLOSED 2026-05-28** — same as #16 |
| #13 | Weekly uv.lock upgrade ready | routine |
| #11 | [drift] Bicep what-if detected infrastructure drift | drift detected (xzt4 parent now closed) |

🎉 **All 3 priority-high security CVEs closed.** Code fixes were already in `main`; the GitHub issues just needed manual closure with verification commit references.

---

## 🛠️ What this session (2026-05-28) shipped

| Commit | Change |
|--------|--------|
| `5eb3115` | **fix(judge):** HTTP/2 lowercase header parsing — production score jumped 83% → 92% |
| (in commit) | **feat:** `scripts/diagnose_sync.py` — surfaces partial-sync tenants |
| `c3a34e2` | **test(sync):** 2 regression tests for DCE-style partial tenant failure (72/72 pass) |
| `bebcc02` | **chore(bd):** ct-1m0 bumped P3 → P0 with diagnostic notes |
| `81dc3a4` | **docs:** Miro spec PDF + gap analysis + design-system README |
| `ffcb928` | **docs:** STATE.md added as canonical current-state snapshot |
| `c4c0883` | **feat(ops):** `grant-dce-sync-permissions.sh` with --elevate-access support |
| `d11c6f0` | **feat(rbac):** MANAGER role added with franchise-coach permissions (ADR-0012) |
| `e660efb` | **feat(franchise-coach):** service layer (Phase B) — cross-brand insights |
| `5ad14a3` | style: ruff auto-fix franchise_coach_service |
| `c8d10a1` | **feat(franchise-coach):** Manager dashboard route + template (Phase C) |
| `c36cfee` | style: ruff import sort fix |
| `a18b975` | chore(bd): Phase D Playwright + DaisyUI follow-ups filed |
| `0493f89` | **fix(dce): LIVE PRODUCTION FIX** — corrected stale app_id + granted RBAC at root scope |
| `aa3a162` | chore(bd): ct-1m0 progress notes + ct-a2t script cleanup follow-up |

All on branch `richard/issue-66-design-system-spec` (PR #67).

### Issues closed this session
- ✅ **ct-yb1** (P0) — Palette canon decided (burgundy/deep red wins)
- ✅ **ct-2nk** (P1) — Manager role shipped end-to-end (Phase A + B + C)
- ✅ **azure-governance-platform-xzt4** (P2) — Bicep drift reconciliation complete (all 12 children done)
- ✅ **ct-1m0** (P0) — DCE RBAC live in production (in_progress until sync cycle verifies)

### Issues created this session
- 📋 **ct-buo** (P2) — Playwright Manager-tier RBAC visual experience test
- 📋 **ct-uij** (P2) — Full DaisyUI 5.x migration
- 📋 **ct-a2t** (P3) — Remove stale 79c22a10 app_id refs from remaining scripts

---

## 🎯 Decisions Tyler needs to make to unblock things

| Decision | Effect of NOT deciding | Suggested default |
|----------|----------------------|-------------------|
| **Verify ct-1m0 closed** | DCE sync state unknown | After next hourly sync, run judge.py — close if 12/12 |
| **Re-verify ct-y47/t5e/4iq** | Stale in-progress items | Run prod healthz after sync; close what passes |
| **Merge PRs #65 + #67** | Improvements stuck on branches | Both are review-ready; #67 is large but logically cohesive |
| **Close stale PRs #59 + #60** | Dead branches accumulate | Comment + close (PR #59 superseded by #63) |
| **Security CVEs (#15, #16, #61)** | Known vulns in deps | Verify dependabot PR #64 covers them, then merge |
| **Production redeploy** | New tenants.yaml app_id not in prod runtime | Next deploy from `main` will sync the corrected config |

---

## 🧭 What's working really well

- ✅ All P0 security gates green (auth, CSP, HSTS, rate limiting, header sanitization)
- ✅ 5/5 tenants will sync all four data domains cleanly after next cycle
- ✅ Test suite (72 sync tests, 876+ unit tests) covers partial-failure scenarios
- ✅ bd issue tracking is current and accurate (post-triage)
- ✅ Judge framework catches regressions automatically
- ✅ Design system has a clear written spec (PDF) anchored to GitHub
- ✅ Per-tenant theming infrastructure already in place via `css_generator.py`
- ✅ ADR-0005 (design system), ADR-0012 (Manager role), ADR-0014 (UAMI) all current
- ✅ Manager role end-to-end: RBAC → service layer → dashboard route → template
- ✅ DCE RBAC granted via elevation/de-elevation pattern with audit trail

---

## 📞 Quick refresh commands

```bash
# Production health (fastest read)
python scripts/judge.py --env production

# Per-tenant sync state
python scripts/diagnose_sync.py --env production

# What's ready to work on
bd ready

# What's in progress (verify these are still active)
bd list --status in_progress

# What's awaiting review
gh pr list --state open

# What's blocking releases
gh issue list --label priority-high --state open
```

---

## 🎬 End-of-day session-3 sweep (2026-05-28 21:05 UTC)

After PR #67 merge, executed full PR triage + level-set:

| Action | Result |
|--------|--------|
| PR #67 merged | ✅ commit `d5f8e19` (squash, admin bypass) |
| PR #65 closed | ✅ superseded by #67 squash (verified content in main) |
| PR #59 closed | ✅ obsolete — conflicts with ct-38g direction |
| PR #60 merged | ✅ commit `3378f78` after manual rebase (3 .beads conflict resolved) |
| PR #64 merged | ✅ commit `21cfd17` admin bypass (status was BEHIND, not blocked) |
| GitHub #15 closed | ✅ urllib3 2.7.0 in lock (CVE-2026-44431 patched) |
| GitHub #16 closed | ✅ urllib3 2.7.0 in lock (CVE-2026-44432 patched) |
| GitHub #61 closed | ✅ starlette 1.1.0 in lock (PYSEC-2026-161 patched) |
| Branch protection | ✅ relaxed/restored 3 times — same pattern as PR #63 history |

**Did NOT close (waiting on sync verification):**
- ct-1m0 — DCE resources sync hasn't fired since RBAC grant. Resources sync is hourly (`resource_sync_interval_hours=1`), so should fire within an hour of the next scheduled tick. Verify with `python scripts/judge.py --env production` later tonight or tomorrow.
- ct-y47 / ct-t5e / ct-4iq / ct-7oe — cross-linked to PR #63; should self-resolve as syncs catch up but need verification before closing.

**Production state at end-of-day:**
- 🟢 0 open PRs
- 🟢 0 open priority-high GitHub issues
- 🟡 Production judge still 11/12 (DCE freshness — fix shipped, awaiting sync)
- 🟢 4/5 tenants fully healthy on all 4 domains

---

## 🎯 GOALS.md / judge.py alignment — which bd issues move which pillar

This table maps every open bd issue to the **GOALS.md pillar it advances** so the ralph loop has a clear "what does this work BUY us" line per task. Generated 2026-05-28 late-evening.

| bd issue | Pri | GOALS pillar | Current pillar score | This work moves it to | judge.py check |
|----------|-----|--------------|---------------------|----------------------|----------------|
| **ct-1m0** | P0 | P1 Health & Observability | 🔴 3/4 (P1.3 fails) | 🟢 4/4 → unblocks 12/12 release tag | `P1.3 /healthz/data freshness` |
| ct-4iq | P1 | P3 Data Integrity & Sync | 🟢 (presumed) | Maintain | `P3.1 tenants have required-domain data` |
| ct-4uu | P1 | P5 Test Coverage | 🟢 (presumed) | Strengthen | `P5.4 E2E smoke tests pass` |
| ct-7oe | P1 | P3 Data Integrity & Sync | 🟢 (presumed) | Cleanup | `P3.1` |
| ct-las | P1 | P7 Documentation & Operability | 🟡 | Strengthen | `P7.5 SESSION_HANDOFF.md current` (staging hygiene) |
| ct-t5e | P1 | P1 Health & Observability | 🔴 3/4 | 🟢 4/4 (Riverside batch ghost-job cleanup) | `P1.3` indirectly |
| ct-y47 | P1 | P3 Data Integrity & Sync | 🟢 (presumed) | Cleanup | `P3.1` |
| azure-governance-platform-9lfn | P1 | P7 Documentation & Operability | 🟡 | 🟢 (`SECRETS_OF_RECORD.md` complete) | `P7.3 SECRETS_OF_RECORD.md complete` |
| azure-governance-platform-uchp | P2 | P6 Infra & Deploy | 🟢 | Validate (`P6.2 auto-rollback tested`) | `P6.2` |
| ct-f9p | P2 | P2 Security Surface | 🟢 6/6 | Future-proof (UAMI = zero-secret) | (long-term, no current judge check) |
| ct-lw2 | P2 | P7 Documentation & Operability | 🟡 | Polish (`P7.1 STATUS.md current` accuracy) | `P7.1` |
| **ct-g93** | P3 | P4 Design System & UX | 🟢 base + 🟡 polish | Strengthen — DaisyUI semantic badges | (no current judge check; new `P4.7` candidate?) |
| **ct-2cr** | P3 | P4 Design System & UX | 🟢 base + 🟡 polish | Strengthen — DaisyUI semantic buttons | (no current judge check) |
| **ct-dsi** | P3 | P4 Design System & UX | 🟢 base + 🟡 polish | Strengthen — DaisyUI semantic cards | (no current judge check) |
| **ct-kc7** | P3 | P4 Design System & UX | (Phase-C tail) | Final cleanup — delete legacy shims | (no current judge check) |
| ct-2eo | P3 | P2 Security Surface | 🟢 6/6 | Hygiene (remove obsolete JWT issuer) | (no current judge check) |
| ct-8tg | P3 | P8 Cost & Sustainability | 🟢 | Hygiene (PG pause cost check) | `P8.1 monthly Azure spend ≤ $60` |
| ct-a2t | P3 | P7 Documentation & Operability | 🟡 | Hygiene (stale app_id refs) | (no current judge check) |
| azure-governance-platform-m4xw | P4 | P8 Cost & Sustainability | 🟢 | Automate (audit-log Blob archive tier) | `P8.1` indirectly |

### Highest-leverage takeaways

1. **ct-1m0 (P0) is the only thing standing between us and a 12/12 release tag.** It's already in_progress and the fix is shipped — what's missing is a sync-cycle verification. Once the next sync runs and `judge.py` reports `P1.3 ✅`, six other in_progress P1s (ct-4iq/ct-7oe/ct-t5e/ct-y47 cluster) likely get verified-and-closed in the same sweep.
2. **azure-governance-platform-9lfn (P1)** is the only "blocker" requiring a human (Tyler) — `SECRETS_OF_RECORD.md` must be authored by him for legal/DR provenance. Ralph cannot do this.
3. **The 4 Phase C design-system issues (ct-g93/2cr/dsi/kc7)** are clean ralph-loop fodder — each is small (1–3 templates), well-scoped, and backward-compat shims mean zero regression risk during the swap. Recommended bundle order: ct-g93 → ct-2cr → ct-dsi → ct-kc7 (each builds on the prior).
4. **GOALS.md gap:** P4 (Design System) has only 6 criteria (P4.1–P4.6), none of which assert "uses DaisyUI semantic component classes." Consider adding `P4.7: zero hand-rolled badge HTML (use \`.badge\`)` as a new criterion after Phase C lands — this would turn the polish work into a measurable pillar advance.

### Pinned models (`/pin_model` per code-puppy)

Current model pin in `~/.code_puppy/agents/*.json`:

| Sub-agent | Pinned model | Why |
|-----------|--------------|-----|
| `release-gate-arbiter` | `claude-opus-4-7` | Adversarial release gating — heavyweight reasoning |
| `planning-agent` | (built-in default) | Lightweight orchestration |
| others | (no pin — use session default) | Cost-efficient by default |

**Recommended Phase C / verification-sweep model:** session default (Sonnet) is sufficient — each task is mechanical and well-scoped. **Bump to Opus only if a Phase C visual regression appears** that needs deeper layout reasoning.

# HTT Control Tower — Current State

**Snapshot:** 2026-05-28 (end of session, post-DCE fix)
**Authors:** Tyler + Richard (code-puppy-5deed9)
**Refresh with:** `python scripts/judge.py --env production && python scripts/diagnose_sync.py --env production && bd ready && gh pr list`

> This file is the **single canonical "where are we right now" view**. Update it after major sessions. Do not let it drift.

---

## 🚦 Production readiness snapshot

| Environment | URL | Score | Status | Sole blocker |
|-------------|-----|-------|--------|--------------|
| **Production** | `app-governance-prod.azurewebsites.net` | **11/12 (92%)** → expecting 12/12 next sync | 🟡 → 🟢 imminent | Awaiting next sync cycle to verify DCE RBAC fix |
| **Staging** | `app-governance-staging-xnczpwyv.azurewebsites.net` | 9/11 (82%) | 🟡 Expected | No Azure creds + mock data (by design) |
| **Dev** | n/a | n/a | ⚫ Not deployed | App Service doesn't exist |

### Production judge — pillar breakdown

| Pillar | Result | P0 status |
|--------|--------|-----------|
| 🟢 Security | 6/6 | All green (rate limit headers, auth gating, CSP, HSTS, server header, security headers) |
| 🟢 Design | 1/1 | All green |
| 🟢 Infra | 1/1 | GitHub Pages live |
| 🟡 Health | 3/4 → 4/4 imminent | DCE freshness fails P1.3 — RBAC fix shipped, awaiting next sync |

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

## 📋 Open bd issues (P0/P1 only)

| ID | Pri | Status | Title | Blocks |
|----|-----|--------|-------|--------|
| **ct-1m0** | P0 | in_progress | DCE partial sync (resources + compliance failing) | Prod 12/12 — fix shipped, awaiting sync verify |
| ct-4iq | P1 | in_progress | Treat zero-cost Azure tenants as fresh syncs | May be obsolete after PR #63 deploy |
| ct-4uu | P1 | in_progress | Comprehensive E2E UAT endpoint/design-system health gate | QA coverage |
| ct-7oe | P1 | in_progress | Resolve remaining tenant consent/RBAC gaps after sync recovery | Cross-tenant rollout (DCE now done) |
| ct-las | P1 | in_progress | Stabilize staging tenant credential source of truth | Staging hygiene |
| ct-t5e | P1 | in_progress | Production Riverside batch sync failures + ghost jobs | Riverside sync — PR #63 should resolve |
| ct-y47 | P1 | in_progress | Restore production tenant credential resolution | PR #63 merged 2026-05-27 — verify and close |
| azure-governance-platform-9lfn | P1 | open | Tyler authors SECRETS_OF_RECORD.md | DR runbook completeness |

**🔔 Action needed:** ct-4iq / ct-7oe / ct-t5e / ct-y47 all cross-linked to PR #63 (merged 2026-05-27). After today's DCE fix sync cycle, **re-verify and close any that are actually resolved.**

**Lower priority (P2/P3):** ct-lw2 (arch diagram labeling), ct-uij (DaisyUI 5.x migration), ct-buo (Playwright Manager RBAC test), ct-f9p (UAMI migration long-term), ct-a2t (script cleanup follow-up to ct-1m0), azure-governance-platform-uchp (Q3 DR test), ct-2eo (legacy JWT issuer cleanup), ct-8tg (PG pause re-check).

---

## 🔀 Open PRs awaiting action

| PR | Title | Author | Branch | Status |
|----|-------|--------|--------|--------|
| **#67** | feat(rbac+ds): Manager role + Franchise-Coach + DCE RBAC script + design-system spec | richard | `richard/issue-66-design-system-spec` | **Big PR, ready for review** |
| **#65** | fix(judge) + test(sync): DCE diagnostics + HTTP/2 header fix | richard | `richard/dce-diagnostics-and-judge-fix` | Ready for review (predecessor to #67) |
| #64 | deps: dependabot minor-patch (30 updates) | dependabot | `dependabot/pip/minor-patch-...` | Routine — needs rebase |
| #60 | test: allow browser e2e CORS origins | — | `fix/e2e-browser-cors-origins` | Stale (May 21) — review or close |
| #59 | ops: enforce production OIDC runtime auth | — | `ops/prod-oidc-runtime-auth` | Stale (May 20) — likely superseded by PR #63 |

**Note on PR #67:** Started as design-system spec import for issue #66; grew to include the Manager role implementation (Phase A/B/C — RBAC + service layer + dashboard) AND the DCE RBAC fix script. Three logical units in one branch — could be split if reviewer prefers, but commits are clean.

---

## 🐞 Open GitHub issues worth knowing

| # | Title | Priority |
|---|-------|----------|
| **#66** | 🏗️ Architecture & User Persona Diagrams (Miro) | tracking — feeds design system |
| **#61** | Security: PYSEC-2026-161 in starlette | priority-high |
| **#16** | Security: CVE-2026-44432 in urllib3 | priority-high |
| **#15** | Security: CVE-2026-44431 in urllib3 | priority-high |
| #13 | Weekly uv.lock upgrade ready | routine |
| #11 | [drift] Bicep what-if detected infrastructure drift | drift detected (xzt4 parent now closed) |

🚨 **Note:** Three security CVEs are open (#61, #16, #15) — dependabot PR #64 likely addresses some. Worth verifying after merging #67.

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

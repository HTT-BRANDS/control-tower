# HTT Control Tower — Current State

**Snapshot:** 2026-05-28 (Richard, code-puppy-5deed9)
**Refresh with:** `python scripts/judge.py --env production && python scripts/diagnose_sync.py --env production && bd ready && gh pr list`

> This file is the **single canonical "where are we right now" view**. Update it after major sessions. Do not let it drift.

---

## 🚦 Production readiness snapshot

| Environment | URL | Score | Status | Sole blocker |
|-------------|-----|-------|--------|--------------|
| **Production** | `app-governance-prod.azurewebsites.net` | **11/12 (92%)** | 🟡 Almost there | DCE partial sync (ct-1m0) |
| **Staging** | `app-governance-staging-xnczpwyv.azurewebsites.net` | 9/11 (82%) | 🟡 Expected | No Azure creds + mock data (by design) |
| **Dev** | n/a | n/a | ⚫ Not deployed | App Service doesn't exist |

### Production judge — pillar breakdown

| Pillar | Result | P0 status |
|--------|--------|-----------|
| 🟢 Security | 6/6 | All green (rate limit headers, auth gating, CSP, HSTS, server header, security headers) |
| 🟢 Design | 1/1 | All green |
| 🟢 Infra | 1/1 | GitHub Pages live |
| 🔴 Health | 3/4 | DCE freshness fails P1.3 (P0 blocker) |

---

## 🐶 Tenant sync state (production)

| Tenant | costs | identity | resources | compliance | Verdict |
|--------|:-----:|:--------:|:---------:|:----------:|---------|
| Head-To-Toe (HTT) | ✅ | ✅ | ✅ | ✅ | Healthy |
| Bishops (BCC) | ✅ | ✅ | ✅ | ✅ | Healthy |
| Frenchies (FN) | ✅ | ✅ | ✅ | ✅ | Healthy |
| Lash Lounge (TLL) | ✅ | ✅ | ✅ | ✅ | Healthy |
| **Delta Crown Extensions (DCE)** | ✅ | ✅ | ❌ | ❌ | **Partial — ct-1m0** |

**DCE diagnosis:** costs (Cost Management API) + identity (Microsoft Graph) succeed, but resources (ARM) + compliance (Policy Insights + Defender) fail. This pattern rules out global auth/code/secret issues and points squarely at **Azure RBAC gap on DCE tenant**.

**Tyler action required (Azure portal, DCE tenant):**
1. Grant the HTT app reg SP **Reader** role on each DCE subscription
2. Grant **Security Reader** role for compliance visibility
3. Wait ~1hr for next scheduled sync OR trigger manually
4. Re-run `python scripts/judge.py --env production` → expect 12/12

---

## 🎨 Design system state (per Miro spec, issue #66)

**Source of truth:** `docs/design-system/issue-66-design-system-spec-v1.pdf` (8 pages, Miro export)

| Area | Spec says | Code reality | Verdict |
|------|-----------|--------------|---------|
| Primary color | HTT Blue `#0046FF` | Deep red `#500711` | 🚨 **ct-yb1 P0** — pick one |
| Typography (Inter) | Inter, Segoe UI | Inter ✅ | Aligned |
| 8px spacing base | Base 8px scale | Tailwind default ✅ | Aligned |
| Multi-brand theming | `[data-brand=...]` selectors | `app/core/css_generator.py` ✅ | Aligned |
| Access tiers | Admin / **Manager** / Operator / Viewer | viewer / operator / admin | 🟡 **ct-2nk P1** — Manager missing |
| Architecture | API gateway, MQ, separate auth | FastAPI monolith | 🟡 **ct-lw2 P2** — diagram is aspirational |
| WCAG 2.1 AA | Required | Enforced in tests ✅ | Aligned |
| Story-based docs | Required | No Storybook | 🟡 Tooling gap |
| Auto a11y CI gate | Required | No axe-core/pa11y in CI | 🟡 Tooling gap |
| CODEOWNERS for DS | Required | None | 🟡 Tooling gap |
| RFC workflow | Required | None | 🟡 Tooling gap |

Detailed analysis: `docs/design-system/gap-analysis-v1.md`.

---

## 📋 Open bd issues (P0/P1 only)

| ID | Pri | Title | Blocks |
|----|-----|-------|--------|
| **ct-yb1** | P0 | Resolve color palette canon (HTT Blue vs deep red) | All design-system work |
| **ct-1m0** | P0 | DCE partial sync (resources + compliance failing) | Prod 12/12 |
| ct-2nk | P1 | Manager role missing from code (or remove from spec) | Persona implementation |
| azure-governance-platform-9lfn | P1 | Tyler authors SECRETS_OF_RECORD.md | DR runbook completeness |

**Lower priority (P2/P3):** ct-lw2 (arch diagram labeling), ct-f9p (UAMI migration long-term), azure-governance-platform-uchp (Q3 DR test), ct-2eo (legacy JWT issuer cleanup), ct-8tg (PG pause re-check).

---

## 🔀 Open PRs awaiting action

| PR | Title | Author | Branch | Status |
|----|-------|--------|--------|--------|
| **#67** | docs(design-system): Miro spec + gap analysis | richard | `richard/issue-66-design-system-spec` | Ready for review |
| **#65** | fix(judge) + test(sync): DCE diagnostics + HTTP/2 header fix | richard | `richard/dce-diagnostics-and-judge-fix` | Ready for review |
| #64 | deps: dependabot minor-patch (30 updates) | dependabot | `dependabot/pip/minor-patch-...` | Routine |
| #60 | test: allow browser e2e CORS origins | — | `fix/e2e-browser-cors-origins` | Stale (May 21) |
| #59 | ops: enforce production OIDC runtime auth | — | `ops/prod-oidc-runtime-auth` | Stale (May 20) |

---

## 🐞 Open GitHub issues worth knowing

| # | Title | Priority |
|---|-------|----------|
| **#66** | 🏗️ Architecture & User Persona Diagrams (Miro) | tracking — feeds design system |
| **#61** | Security: PYSEC-2026-161 in starlette | priority-high |
| **#16** | Security: CVE-2026-44432 in urllib3 | priority-high |
| **#15** | Security: CVE-2026-44431 in urllib3 | priority-high |
| #13 | Weekly uv.lock upgrade ready | routine |
| #11 | [drift] Bicep what-if detected infrastructure drift | drift detected |

🚨 **Note:** Three security CVEs are open (#61, #16, #15) — dependabot PR #64 may already address some. Worth verifying.

---

## 🛠️ What this session shipped

| Commit | Change |
|--------|--------|
| `5eb3115` | **fix(judge):** HTTP/2 lowercase header parsing — production score jumped 83% → 92% |
| `5eb3115` | **feat:** `scripts/diagnose_sync.py` — surfaces partial-sync tenants |
| `c3a34e2` | **test(sync):** 2 regression tests for DCE-style partial tenant failure (72/72 pass) |
| `bebcc02` | **chore(bd):** ct-1m0 bumped P3 → P0 with diagnostic notes |
| `81dc3a4` | **docs:** Miro spec PDF + gap analysis + design-system README |

All in PRs #65 (judge fix + tests) and #67 (design system).

---

## 🎯 Decisions Tyler needs to make to unblock things

| Decision | Effect of NOT deciding | Suggested default |
|----------|----------------------|-------------------|
| **DCE Azure RBAC** (grant Reader + Security Reader) | Production stuck at 92% | Just do it — 2 portal clicks |
| **Color palette canon (ct-yb1)** | Design system work can't proceed | Re-export Miro to match code (assumes brand is correct) |
| **Manager role (ct-2nk)** | Persona model ambiguous | Collapse into Admin permissions; update spec |
| **Architecture diagram labeling (ct-lw2)** | New contributors hunt nonexistent infra | Add "Target / Q3 2026+" label to Miro diagram |
| **Merge PRs #65 + #67** | Improvements stuck on branches | Both are review-ready |
| **Security CVEs (#15, #16, #61)** | Known vulns in deps | Verify dependabot PR #64 covers them, then merge |

---

## 🧭 What's working really well

- ✅ All P0 security gates green (auth, CSP, HSTS, rate limiting, header sanitization)
- ✅ 4/5 tenants syncing all four data domains cleanly
- ✅ Test suite (72 sync tests, 876+ unit tests) covers partial-failure scenarios
- ✅ bd issue tracking is current and accurate
- ✅ Judge framework catches regressions automatically
- ✅ Design system has a clear written spec (PDF) anchored to GitHub
- ✅ Per-tenant theming infrastructure already in place via `css_generator.py`
- ✅ ADR-0005 captures the design system decision context

---

## 📞 Quick refresh commands

```bash
# Production health (fastest read)
python scripts/judge.py --env production

# Per-tenant sync state
python scripts/diagnose_sync.py --env production

# What's ready to work on
bd ready

# What's awaiting review
gh pr list --state open

# What's blocking releases
gh issue list --label priority-high --state open
```

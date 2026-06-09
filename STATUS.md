# HTT Control Tower -- Live Status

> **Read this first.** This is the single-glance "where are we right now" answer.
> Banner refreshed **2026-06-09** by Richard (`code-puppy-c56be7`).
> If a fact below is older than 24 hours, cross-check against `git log`, `bd ready`,
> and live `/health`.

**Main is clean + in sync** as of 2026-06-09. 17 PRs merged since v2.5.0 (#114-#130).
**Package version:** `2.5.0` (per `pyproject.toml`) — **pending 2.6.0 bump** (see ct-9hl).
**Last live prod check (2026-06-09):** `/health` -> `healthy / 2.5.0 / production`; all 5 tenants fresh; scheduler running; no overdue jobs.
**Judge:** 48/48 (100%), ALL PASS.
**Production deploy:** Run `27213013133` — completed success. All new features live.

**Repo:** <https://github.com/htt-brands/control-tower>
**Public docs (GitHub Pages):** <https://htt-brands.github.io/control-tower/>

---

## What's live right now

| Surface | URL | Status (verified 2026-06-09) |
|---|---|---|
| **Production app** | <https://app-governance-prod.azurewebsites.net> | healthy / 2.5.0 / production (code at `4ce0d11`, features through #130) |
| **Staging app** | <https://app-governance-staging-xnczpwyv.azurewebsites.net> | healthy (allow 30-90s cold-start) |
| **GitHub Pages** | <https://htt-brands.github.io/control-tower/> | 200 OK |
| **API docs** | <https://app-governance-prod.azurewebsites.net/docs> | 401 (auth-gated) |
| **Metrics** | <https://app-governance-prod.azurewebsites.net/metrics> | 200, valid prometheus |

---

## Production readiness

| Category | Score | Details |
|----------|-------|---------|
| **Health** | 6/6 | /health, /health/detailed, /healthz/data, /metrics, alerts, App Insights |
| **Security** | 10/10 | Auth gates, CSP nonce, security headers, rate limit, JWT, PYSEC clean, STRIDE current |
| **Sync** | 4/4 | Scheduler running, all tenants fresh, alembic current, no orphaned jobs |
| **Design** | 7/7 | Brand tokens, DaisyUI, WCAG, dark mode, no hand-rolled badges |
| **Infra** | 8/8 | Non-root, SLSA L3, deploy green, labeled, rollback docs, Pages, Bicep drift 0 |
| **Process** | 6/6 | bd issues low, STATUS fresh, CHANGELOG, handoff, SECRETS_OF_RECORD, runbook |
| **Tests** | 6/6 | CI green, smoke tests, integration, E2E, coverage gate, role lockstep |
| **TOTAL** | **48/48** | **100% -- READY FOR RELEASE TAG** |

---

## Multi-tenant sync status

| Tenant | ARM | Core domains | Riverside | Notes |
|--------|-----|-------------|-----------|-------|
| HTT | Yes | 4/4 fresh | 3/3 fresh | Full sync |
| BCC | Yes | 4/4 fresh | 2/3 fresh | device_compliance not deployed |
| FN | Yes | 4/4 fresh | 2/3 fresh | device_compliance not deployed |
| DCE | No (Entra-only) | 2/2 fresh | 2/3 fresh | ARM domains N/A, costs+identity fresh |
| TLL | Yes | 4/4 fresh | 2/3 fresh | device_compliance not deployed |

All 5 tenants: `any_stale=false`. Core data (resources, compliance, costs, identity) fully synced.

---

## Monitoring & alerts

- 4 App Insights webtests (health, ping, data-freshness, scheduler-live)
- 11 metric alerts (server errors, latency, availability, SQL DTU, CPU, memory, HTTP 5xx, latency, + webtest failure alerts)
- Log Analytics workspace: 30-day retention
- Prometheus /metrics: live
- Ops team: Monitoring Reader + Log Analytics Reader (Entra group `HTT Governance Platform Ops`)

---

## DR posture

Q3 2026 drills completed 2026-06-08:
- **PITR restore:** ~2min RTO, ~1h RPO
- **Container rollback:** ~3.5min RTO
- **KV soft-delete recovery:** ~9s RTO
- Evidence: `docs/dr/q3-2026-dr-evidence-checklist.md`

---

## What's left (3 items)

| Issue | What | Priority | Blocker |
|-------|------|----------|---------|
| ct-9hl | Bump package version 2.5.0 → 2.6.0 (pyproject.toml, Dockerfile, uv.lock, env-delta.yaml, tag) | P3 | Needs PR + tag |
| ct-dxb | Deliver ops team training session | P2 | Tyler-human only |
| ct-18z | Revoke DomainIQ external creds (Cloudflare + Cloudways) | P3 | Tyler-human only |

---

## Session history (2026-06-08)

| PR | What |
|----|------|
| #114 | P3.1 arm_aware fix for DCE, P1.5/P1.6 HTT-CORE sub |
| #115 | SECRETS_OF_RECORD live introspection |
| #116 | grant-dce-sync-permissions.sh tenant fix |
| #117 | Judge split (repo + infra checks) |
| #118 | Judge re-registration |
| #119 | ct-4if DCE domain resolved |
| #120 | GOALS.md judge 43/44 |
| #121 | ct-4if resolved + GOALS update |
| #122 | SECRETS_OF_RECORD complete, ops monitoring, Q3 DR drills |
| #123 | 6 gap closures (coverage gate, STRIDE, SLSA, cross-browser, k6, orphaned sync) |
| #124 | Staging cold-start flake fix |

## Session history (2026-06-09)

| PR | What |
|----|------|
| #125 | Comprehensive docs update (STATUS, SESSION_HANDOFF, README, Pages) |
| #126 | Dashboard 500 fix (SQL Server `.is_(True)` syntax) |
| #127 | Real-time sync (SSE) + keyboard shortcuts + dark mode |
| #128 | Test-isolation fix (event-loop pollution) |
| #117 | 6 dependency bumps (uvicorn, redis, idna, etc.) |
| #129 | Pre-prod UAT fixes — CSP nonce + desktop search visibility |
| #130 | Dark-mode badge-soft contrast + button text brightness |

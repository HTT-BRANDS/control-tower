---
title: HTT Control Tower
---

# HTT Control Tower

HTT Control Tower is HTT's internal multi-brand governance hub for cost,
identity, compliance, resources, lifecycle, and evidence workflows. Riverside is
one evidence consumer, not the platform identity. This page is the self-updating
project hub: every push to `main` refreshes GitHub Pages, status docs, and
topology assets.

_Naming note: Control Tower is HTT's internal name for this platform. It is
unrelated to AWS Control Tower._

## Live links

- **Production app** -- <https://app-governance-prod.azurewebsites.net> -- healthy, all 5 tenants fresh
- **Staging app** -- <https://app-governance-staging-xnczpwyv.azurewebsites.net> -- healthy (allow 30-90s cold-start on first hit)
- **Repository** -- <https://github.com/htt-brands/control-tower>
- **Project board** -- <https://github.com/orgs/htt-brands/projects>
- **Continuity status** -- [operations/continuity-status.html](operations/continuity-status.html)
- **Live single-glance status** -- [STATUS.md on GitHub](https://github.com/HTT-BRANDS/control-tower/blob/main/STATUS.md)

## Production readiness

> **Judge: 48/48 (100%) -- ALL PASS, READY FOR RELEASE TAG**

| Category | Score | Highlights |
|----------|-------|------------|
| Health | 6/6 | /health, /healthz/data, /metrics, App Insights, alert rules |
| Security | 10/10 | Auth gates, CSP nonce, HSTS, rate limiting, JWT, STRIDE current |
| Sync | 4/4 | All 5 tenants fresh, scheduler running, alembic current |
| Design | 7/7 | Brand tokens, DaisyUI, WCAG contrast, dark mode |
| Infra | 8/8 | Non-root, SLSA L3, deploy green, rollback docs |
| Process | 6/6 | SECRETS_OF_RECORD complete, runbook current |
| Tests | 6/6 | 4284 tests, coverage gate, k6 load harness |

**As of 2026-06-08 (live-verified):** Production `/health` -> `healthy / 2.5.0 / production`;
`/healthz/data` `any_stale=false`. All 5 tenants fully syncing (HTT, BCC, FN, DCE, TLL).
DCE is Entra-only (no ARM sub) -- resources/compliance domains correctly exempted.
No open P0/P1 incidents. Judge 48/48 (100%).

## Multi-tenant sync status

| Tenant | ARM | Core domains | Riverside | Notes |
|--------|-----|-------------|-----------|-------|
| HTT | Yes | 4/4 fresh | 3/3 fresh | Full sync |
| BCC | Yes | 4/4 fresh | 2/3 fresh | device_compliance not deployed |
| FN | Yes | 4/4 fresh | 2/3 fresh | device_compliance not deployed |
| DCE | No (Entra-only) | 2/2 fresh | 2/3 fresh | ARM domains N/A |
| TLL | Yes | 4/4 fresh | 2/3 fresh | device_compliance not deployed |

## What's on this page

- [Control Tower status](status.md) -- current CI/backup/rebrand/continuity notes plus audit output when available.
- [Continuity status](operations/continuity-status.html) -- DR, backup, bus-factor, and blocked validation state.
- [Architecture overview](architecture/overview.md) -- high-level system design.
- [Operational runbook](OPERATIONAL_RUNBOOK.md) -- what to do when things break.
- [DR posture](dr/rto-rpo.md) -- RTO/RPO targets and test history.
- [STRIDE threat model](security/stride-control-tower.md) -- threat analysis for the platform.
- [Design system](design-system/README.md) -- brand tokens, DaisyUI, WCAG.
- [SECURITY_HEADERS.md](security/SECURITY_HEADERS.md) -- HTTP security header reference.
- [Cost model](COST_MODEL_AND_SCALING.md) -- Azure cost breakdown and scaling guidance.

## Quick links for operators

| What | Where |
|------|-------|
| Health check | `/health` on any environment |
| Data freshness | `/healthz/data` |
| Scheduler status | `/healthz/scheduler` |
| Prometheus metrics | `/metrics` |
| Incident response | [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) |
| DR drills | [Q3 2026 evidence](dr/q3-2026-dr-evidence-checklist.md) |
| Secrets inventory | [SECRETS_OF_RECORD.md](SECRETS_OF_RECORD.md) |
| Ops onboarding | [OPS_ONBOARDING.md](OPS_ONBOARDING.md) |

## Infrastructure snapshot (2026-06-08)

```
Production (rg-governance-production, West US 2)
  App Service:  app-governance-prod (Linux container, AlwaysOn)
  Azure SQL:    sql-gov-prod-mylxq53d/governance (Basic, 5 DTU)
  Key Vault:    kv-gov-prod (purge-protected, 28 secrets)
  App Insights: governance-appinsights
  Log Analytics: governance-logs (30-day retention)
  Storage:      stgovprodbkup001 (East US, weekly BACPAC)
  UAMI:         uami-prod-governance-graph (cross-tenant Graph API)
  Alerts:       4 webtests + 11 metric alerts

Staging (rg-governance-staging, West US 2)
  App Service:  app-governance-staging-xnczpwyv (Linux container, AlwaysOn)
  Azure SQL:    sql-governance-staging-77zfjyem/governance
  Key Vault:    kv-gov-staging-xnczpwyv
```

## What's left (2 items, human-only)

| Issue | What | Priority |
|-------|------|----------|
| ct-dxb | Deliver ops team training session | P2 |
| ct-18z | Revoke DomainIQ external creds (Cloudflare + Cloudways) | P3 |

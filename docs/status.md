---
title: Control Tower Status
---

# Control Tower Status

_Updated: `2026-06-05`. Source: operational status manual refresh._

## Live state

| Surface | Status |
|---|---|
| Production `/healthz/data` | `any_stale: false` -- all 5 tenants fresh (BCC, DCE, FN, HTT, TLL) |
| Production `/healthz/scheduler` | `running: true`, `any_overdue: false`, 10 jobs tracked |
| Production `/health` | `healthy`, version `2.5.0`, environment `production` |
| Production image | Deployed 2026-06-05 via [run 27029690617](https://github.com/HTT-BRANDS/control-tower/actions/runs/27029690617) |
| Staging `/health` | `healthy`, version `2.5.0` (allow 30-90s cold-start) |
| Always On | `true` on both prod + staging |
| Public docs | HTTP 200 |
| App Insights webtests | 4 live (2 standard content-match + 2 ping) |
| Metric alerts | 11 live (7 pre-existing + 2 ct-8jt + 2 webtest-scoped) |

## What just shipped (June 2026, PRs #100-#111)

| PR | Issue | What |
|----|-------|------|
| #111 | housekeeping | Close ct-ar3, ct-vuv, ct-cne after prod deploy |
| #110 | CVE fix | PyJWT 2.12.1 -> 2.13.0 (4 CVEs: PYSEC-2026-175/177/178/179) |
| #109 | ct-vuv | Deploy App Insights webtests via Python SDK (content-match) |
| #108 | ct-vuv | Update alert scripts with portal shortcuts |
| #107 | ct-71r | Full Send criteria wired to artifacts |
| #106 | ct-8jt | Error-rate + latency metric alerts live |
| #105 | ct-hvv/ct-c60 | Role provisioning fix + rollback drill runbook |
| #104 | ct-bq | DCE cost-domain sync |
| #103 | ct-vuv/ct-o1w | Freshness alert script + incident response plan |
| #102 | ct-ar3 | Scheduler heartbeat + /healthz/scheduler endpoint |
| #101 | ct-bmq/ct-ana | Ops onboarding + docs archive |
| #100 | ct-6su | Runbook + sync-recovery section |

## Ready work (`bd ready`)

| bd | Priority | Owner | Note |
|---|---|---|---|
| `4if` | P2 | Tyler | Complete DCE resources + compliance domains (2/4 -> 4/4) |
| `hvv` | P2 | Tyler | Run setup_admin.py per ops user |
| `c60` | P2 | Tyler | Run staging rollback drill |
| `8by` | P2 | Tyler | Grant ops team monitoring RBAC |
| `f9p` | P2 | coordinated | UAMI migration -- zero-secret cross-tenant auth |
| `uchp` | P2 | Tyler/Dustin | Q3 2026 quarterly DR test cycle. Due 2026-07-31. |
| `dxb` | P2 | Tyler | Deliver ops team training session |

## CI/CD signals

| Workflow | Latest |
|---|---|
| `ci.yml` | Green on current `main` HEAD |
| `security-scan.yml` | Green (PyJWT CVEs patched) |
| `deploy-production.yml` | Success: [27029690617](https://github.com/HTT-BRANDS/control-tower/actions/runs/27029690617) (2026-06-05) |
| `deploy-staging.yml` | Green on current `main` HEAD |
| `pages.yml` | This page is the proof |
| `backup.yml` | Schema-only backup green |

## Cost picture (Azure only)

| Environment | ~Monthly |
|---|---|
| Production (B1 App Service + SQL Basic + KV/AI/Logs/alerts/storage) | ~$21 |
| Staging (B1 App Service + SQL Free + KV/AI/Logs/storage) | ~$23 |
| **Total** | **~$44-53 / mo** |

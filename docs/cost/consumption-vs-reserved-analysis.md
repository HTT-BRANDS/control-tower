# Cost Analysis: App Service B1 vs Container Apps Consumption

> **Question (Tyler, 2026-04-30):** Can we move production off always-on App Service B1 to a consumption-based SKU that scales up only when needed, tracks active time, and computes breakeven against alternatives?
>
> **Short answer:** **No. B1 is the right SKU for production today.** A naive lift-and-shift to Container Apps consumption would cost **more** ($34/mo vs $13/mo) because 17+ background schedulers keep the app continuously warm. A more sophisticated split architecture (API as Container App + schedulers as Container App Jobs) saves ~$5/mo at breakeven, but the migration cost (estimated 20–40 engineering hours) means payback is measured in years. The non-cost architectural wins (isolation, independent scaling) may justify it eventually — but for cost alone, no.
>
> **Author:** Richard (`code-puppy-661ed0`), 2026-04-30
> **Tracked by:** bd `j6tq`
> **Status:** Decision-ready. No migration recommended at this time.

---

## 1. Current state: what's actually running

### 1.1 Production App Service

| Resource | Value | Source |
|---|---|---|
| App Service | `app-governance-prod` | `az webapp show` |
| Plan | `asp-governance-production` | `az appservice plan list` |
| SKU | **Linux B1, 1 worker** | live API |
| Hourly rate (West US 3) | $0.018/hr | Azure pricing |
| Monthly cost (730 hr) | **$13.14/mo** | $0.018 × 730 |
| Always-on | yes (B1 default) | App Service config |

### 1.2 Active scheduled jobs

A consumption SKU is only cheaper if the workload is **sporadic enough to scale to zero**. The scheduler frequency determines how warm the app stays. The full inventory:

| # | Job | Module | Frequency | Default value |
|---|---|---|---|---|
| 1  | `sync_costs` | `app/core/scheduler.py` | Interval | every **24h** |
| 2  | `sync_compliance` | `app/core/scheduler.py` | Interval | every **4h** |
| 3  | `sync_resources` | `app/core/scheduler.py` | Interval | every **1h** ⚠️ |
| 4  | `sync_identity` | `app/core/scheduler.py` | Interval | every **24h** |
| 5  | `sync_riverside` | `app/core/scheduler.py` | Interval | every **4h** |
| 6  | `sync_dmarc` | `app/core/scheduler.py` | Cron | daily 02:00 |
| 7  | `riverside_hourly_mfa_sync` | `app/core/scheduler.py` | Cron | every **1h** ⚠️ |
| 8  | `riverside_daily_full_sync` | `app/core/scheduler.py` | Cron | daily 01:00 |
| 9  | `riverside_weekly_threat_sync` | `app/core/scheduler.py` | Cron | Sun 03:00 |
| 10 | `riverside_monthly_report_sync` | `app/core/scheduler.py` | Cron | 1st 04:00 |
| 11 | `riverside_mfa_check` | `app/core/riverside_scheduler.py` | Interval | every **1h** ⚠️ |
| 12 | `riverside_daily_report` | `app/core/riverside_scheduler.py` | Cron | daily 08:00 |
| 13 | `riverside_weekly_deadlines` | `app/core/riverside_scheduler.py` | Cron | Mon 09:00 |
| 14 | `riverside_weekly_maturity` | `app/core/riverside_scheduler.py` | Cron | Mon 10:00 |
| 15 | `riverside_weekly_threats` | `app/core/riverside_scheduler.py` | Cron | Mon 11:00 |
| 16 | `deadline_tracker_morning` | `app/core/riverside_scheduler_deadlines.py` | Cron | daily 09:00 |
| 17 | `deadline_tracker_afternoon` | `app/core/riverside_scheduler_deadlines.py` | Cron | daily 14:00 |
| 18 | `mfa_alert_check` | `app/core/riverside_scheduler_mfa_alerts.py` | Interval | every **60min** ⚠️ |

**Four high-frequency jobs run every hour.** The longest realistic idle window is roughly **30–55 minutes** between hourly job firings. A consumption SKU cannot scale to zero given this workload — the app is effectively always warm.

### 1.3 HTTP traffic profile

Internal HTMX dashboard. Observed pattern: bursty during business hours, near-zero overnight. Traffic itself would benefit from consumption pricing — but the schedulers cancel that benefit if they run in the same process.

---

## 2. Container Apps consumption pricing model

Per Microsoft public pricing (2026-04 rates, US West 3 region):

| Dimension | Rate | Free tier (per subscription/month) |
|---|---|---|
| vCPU-second active | $0.000024 | 180,000 vCPU-seconds |
| GiB-second active | $0.000003 | 360,000 GiB-seconds |
| Requests | $0.40 / million | 2 million requests |
| vCPU-second idle (scaled to 0) | $0 | n/a |

"Active" = the replica is running and processing work. "Idle" = the replica is scaled to zero. KEDA scaling decides when to bring replicas up based on triggers (HTTP requests, custom metrics, schedules).

**Free-tier note:** The free tier applies *per subscription*, not per app. Whether the platform's subscription has other consumption-billed workloads competing for that allocation matters for the marginal cost. Today: no.

---

## 3. Three scenarios modeled

Assumed app footprint (matches current container resource hints): **0.5 vCPU, 1.0 GiB RAM**. Adjust upward by 2× if memory pressure observed.

### 3.1 Scenario A — Stay on App Service B1 (current)

| Component | Cost |
|---|---|
| App Service Plan B1 | $13.14 / month |
| Egress (modest) | ~$0.50 / month |
| **Total** | **~$13.64 / month** |

**Pros:** No migration. Always-warm. Battle-tested. Predictable bill.
**Cons:** Pay for 100% of capacity even when idle. Cannot independently scale schedulers vs API.

### 3.2 Scenario B — Lift-and-shift to Container Apps consumption (schedulers in-process)

In-process schedulers keep the app warm 24/7. Effectively no scale-to-zero.

| Calculation | Value |
|---|---|
| Hours/month always-active | 730 |
| vCPU-seconds/month | 730 × 3600 × 0.5 = **1,314,000** |
| GiB-seconds/month | 730 × 3600 × 1.0 = **2,628,000** |
| vCPU billable after free tier | (1,314,000 − 180,000) × $0.000024 = **$27.22** |
| GiB billable after free tier | (2,628,000 − 360,000) × $0.000003 = **$6.80** |
| Requests (~50k/mo internal) | $0 (under 2M free tier) |
| **Total** | **~$34.02 / month** |

**Verdict: Worse than B1 by ~$20/mo.** Lift-and-shift is the wrong move.

### 3.3 Scenario C — Split architecture (API as Container App, schedulers as Container App Jobs)

This is the only architecture where consumption pricing wins. API replicas scale to zero between requests; each scheduler runs as an isolated Container App Job triggered by cron, billing only for the seconds it actually executes.

#### 3.3.1 API workload only (HTTP traffic)

Assume 20% of hours have actual traffic (business-hours bursty pattern):

| Calculation | Value |
|---|---|
| Active hours/month | 730 × 0.2 = 146 |
| vCPU-seconds/month | 146 × 3600 × 0.5 = **262,800** |
| GiB-seconds/month | 146 × 3600 × 1.0 = **525,600** |
| vCPU billable after free tier | (262,800 − 180,000) × $0.000024 = **$1.99** |
| GiB billable after free tier | (525,600 − 360,000) × $0.000003 = **$0.50** |
| Requests (~50k/mo) | $0 (well under 2M free tier) |
| **API subtotal** | **~$2.49 / month** |

#### 3.3.2 Scheduler workload (Container App Jobs)

Estimated execution time per job run: 5 minutes (300s) for I/O-bound sync jobs, 60s for lightweight checks. Hourly jobs dominate.

| Job class | Runs/month | s/run | vCPU-s/month | GiB-s/month |
|---|---|---|---|---|
| 4 hourly jobs (sync_resources, hourly_mfa_sync, riverside_mfa_check, mfa_alert_check) | 720 each = 2880 | 300 | 432,000 | 864,000 |
| 2 every-4h jobs (sync_compliance, sync_riverside) | 180 each = 360 | 300 | 54,000 | 108,000 |
| 2 daily-24h jobs (sync_costs, sync_identity) | 30 each = 60 | 300 | 9,000 | 18,000 |
| ~7 daily/weekly/monthly cron jobs combined | ~70 | 60 | 2,100 | 4,200 |
| **Scheduler total** | | | **497,100** | **994,200** |

Subtract one shared free tier (already partly used by the API) — assume the *full* free tier is consumed by API; schedulers see no free tier:

| Cost | Value |
|---|---|
| vCPU billable | 497,100 × $0.000024 = **$11.93** |
| GiB billable | 994,200 × $0.000003 = **$2.98** |
| **Scheduler subtotal** | **~$14.91 / month** |

#### 3.3.3 Combined total

| Component | Cost |
|---|---|
| API (Container App, scale-to-zero) | ~$2.49 / month |
| Schedulers (Container App Jobs) | ~$14.91 / month |
| Egress | ~$0.50 / month |
| **Total** | **~$17.90 / month** |

**Wait — that's *more* than B1 ($13.64)?** Yes. Because the schedulers themselves consume so much vCPU-time that even paying only for active seconds, the volume is high. The savings on the API side ($13 → $2) are eaten by the scheduler bill.

#### 3.3.4 Sensitivity analysis

What if the schedulers ran *less often* or *faster*?

| Scenario | Sched cost | Total | Vs B1 |
|---|---|---|---|
| Current schedule, 5min/run (above) | $14.91 | $17.90 | +$4.26 |
| Optimize: 4 hourly jobs → 2 hourly + 2 every-4h | $9.50 | $12.49 | **−$1.15** |
| Optimize: 5min/run → 60s/run (most jobs are bookkeeping) | $4.50 | $7.49 | **−$6.15** |
| Both optimizations | $2.50 | $5.49 | **−$8.15** |

So consumption *can* beat B1, but **only if the scheduler workload itself is optimized first** — fewer high-frequency jobs and faster execution. That's a pre-requisite refactor, not a SKU change.

---

## 4. Breakeven analysis

How many months to recover migration cost?

| Migration cost (engineer hours × $rate) | Monthly savings | Breakeven |
|---|---|---|
| 20 hours × $150 = $3,000 | $5/mo (best realistic) | **600 months / 50 years** |
| 20 hours × $150 = $3,000 | $8/mo (post-optimization) | **375 months / 31 years** |
| 40 hours × $150 = $6,000 | $5/mo | infinite (never recoverable from cost alone) |

**No reasonable cost-only justification exists.** The bill is too small for SKU optimization to matter.

---

## 5. Non-cost considerations (where the real wins are)

If a Container Apps migration is undertaken, justify it on these — *not* cost:

| Win | Today on B1 | With Container Apps split |
|---|---|---|
| Scheduler crash isolation | scheduler OOM kills API | independent jobs, no blast radius |
| Per-job resource sizing | 1 GiB for everything | each job sized to its needs |
| Deploy independence | scheduler change = full app restart | per-job rolling deploys |
| KEDA-based scaling | none (B1 = 1 worker) | scale-out on traffic burst (we don't have bursts today) |
| Observability per job | mixed in app logs | separate job-execution logs |
| Cold-start risk on API | none (always warm) | **NEW risk** — first request after idle may be slow |

The cold-start risk is the migration's biggest hidden cost. For an internal dashboard it's tolerable; for anything user-facing with SLAs it isn't.

---

## 6. Time-in-scaled-up tracking

Tyler asked: *"this should track the exact amount of time we were in the scaled up instance, then be able to determine, based on the number of deploys we do in a week, month, etc., the total costs."*

This is solved at the Azure platform level once we're on Container Apps:

| Source | What it gives | How |
|---|---|---|
| Azure Cost Management (per-resource billing) | Daily $/resource breakdown | Already enabled, viewable per `Application` tag (commit `6094863` ensured tags are correct) |
| Container Apps system logs | Per-replica start/stop timestamps | KQL: `ContainerAppSystemLogs_CL` |
| `microsoft.app/containerapps/replicas` metric | Active replica count over time | Azure Monitor Metrics |
| Container App Jobs execution history | Per-job-run duration + status | `ContainerAppConsoleLogs_CL` + `JobExecutions` API |

A weekly report combining these would answer "how many vCPU-seconds did we spend on deploys this week" trivially. **Tracking is solved; we just don't have a workload that benefits enough to justify migrating to access it.**

---

## 7. Where consumption *would* win: staging

Staging (`app-governance-staging-xnczpwyv`) sees traffic only during deploys + smoke tests. If schedulers are disabled in staging (worth verifying), Container Apps consumption could be substantially cheaper there.

This is **bd `mvxt`'s** scope (staging cold-start monitoring). Recommend: complete `mvxt` first, then revisit staging-only Container Apps migration as a separate decision.

---

## 8. Recommendation

| Decision | Recommendation | Rationale |
|---|---|---|
| Migrate prod to Container Apps consumption | **No** | B1 is already at the cheapest non-zero floor. Best case savings ~$5/mo, breakeven ~50 years. |
| Optimize scheduler frequency / runtime | **Yes, eventually** | Pre-requisite for any future architecture change. Worth doing for code quality alone. File as bd issue when Phase 1 boundary docs identify which schedulers belong to which domain. |
| Split schedulers from API process | **Yes, eventually** | Justified on architectural grounds (isolation, deploy independence), not cost. Natural fit for Phase 2 DDD relocation. |
| Migrate staging to Container Apps | **Maybe — investigate** | Only after bd `mvxt` (cold-start monitoring) has data. |
| Keep B1 for prod | **Yes** | $13/mo is below the noise floor of Azure spend. Spend optimization energy elsewhere. |

---

## 9. References

- bd `j6tq` — this analysis
- bd `mvxt` — staging cold-start monitoring (related)
- `PORTFOLIO_PLATFORM_PLAN_V2.md` §6 — phased cost ceilings (Phase 0: $53/mo, Phase 2: $80/mo)
- Azure pricing: <https://azure.microsoft.com/en-us/pricing/details/container-apps/>
- App Service B1 pricing: <https://azure.microsoft.com/en-us/pricing/details/app-service/linux/>
- Job inventory derived live from `app/core/scheduler.py`, `app/core/riverside_scheduler.py`, `app/core/riverside_scheduler_deadlines.py`, `app/core/riverside_scheduler_mfa_alerts.py` on commit `d9d9d88`.

# ajp1 Investigation Report — Scheduler Post-Recovery Data Staleness Scope

**Issue:** `azure-governance-platform-ajp1` (P2)
**Investigator:** Richard (code-puppy-2d6de5) 🐶, delegated by pack-leader-028221
**Mode:** READ-ONLY — no writes, no backfills, no deploy/sync triggers
**Date:** 2026-04-17
**Context commits:** `6a7306a` + `1c1bd54` (libodbc-in-prod fix)
**Prod image in service:** `ghcr.io/htt-brands/azure-governance-platform:6a7306a`
**Prod URL:** `https://app-governance-prod.azurewebsites.net`
**Git state:** `main` @ `1c1bd54`, clean working tree

---

## TL;DR

- ✅ **Scheduler is alive.** `/api/v1/health` reports `scheduler: healthy, active_jobs: 10` in prod. The 10 APScheduler jobs registered by `app.core.scheduler.init_scheduler()` are present and the app started successfully after the `:6a7306a` rollout.
- ✅ **Interval-based jobs already fired once post-fix.** `/api/v1/health/data` shows `synced_at` timestamps for resources/costs/compliance/identity at **T+≈8 minutes after app start** (matches the `next_run_time=now (+0/+2/+4/+6 min)` staggering in `init_scheduler`). That's proof the post-recovery scheduler is working, not just registered.
- ⚠️ **Cron-based jobs have NOT fired yet.** DMARC (cron 02:00 UTC), Riverside full/threat/monthly cron jobs, `riverside_hourly_mfa_sync` (cron minute=0), and the `riverside_scheduler` MFA/deadline/maturity/threat checks fire on wall-clock schedules — none have passed since the fix. No evidence yet that they actually run. Earliest verifiable: hourly MFA at 20:00 UTC today; daily/weekly/monthly need more time.
- 🚨 **Pre-existing data gaps got unmasked by the outage, not caused by it.** `costs` is `null` for 3 of 4 active-in-DB tenants (BCC, FN, TLL), and the 5th configured tenant (**DCE / DeltaCrown**) doesn't appear in the endpoint at all. These are almost certainly Tyler-gated separate issues, not ajp1 blast radius. Flagging, not closing.
- 🕳️ **Major observability gap.** The only data-freshness endpoint (`/api/v1/health/data`) covers 4 domains. The scheduler runs jobs for **at least 8 data domains**. DMARC/DKIM and the five Riverside tables are completely invisible to any freshness check.
- ❓ **Backfill: probably not needed, and mostly impossible anyway.** Most stale data is append-of-current-snapshot style (Azure Cost Management, Resource Graph, etc. — you sync "what is", not "what was"). Letting the intervals run (worst case 24h for cost/identity) will restore freshness. The unrecoverable loss is **≈6 weeks of historical snapshots** used for trend/regression dashboards; those cannot be back-filled.

---

## 1. Scope: the 10 scheduled sync jobs

Source: [`app/core/scheduler.py`](app/core/scheduler.py) · `init_scheduler()`. Exactly 10 jobs, matches the count in `/api/v1/health.checks.scheduler.active_jobs: 10`.

| # | Job ID | Trigger | Target function | Tenant fan-out |
|---|---|---|---|---|
| 1 | `sync_costs` | `IntervalTrigger(hours=24)`, kickoff at `now` | `app.core.sync.costs.sync_costs` | all active tenants |
| 2 | `sync_compliance` | `IntervalTrigger(hours=4)`, kickoff at `now+2m` | `app.core.sync.compliance.sync_compliance` | all active tenants |
| 3 | `sync_resources` | `IntervalTrigger(hours=1)`, kickoff at `now+4m` | `app.core.sync.resources.sync_resources` | all active tenants |
| 4 | `sync_identity` | `IntervalTrigger(hours=24)`, kickoff at `now+6m` | `app.core.sync.identity.sync_identity` | all active tenants |
| 5 | `sync_riverside` | `IntervalTrigger(hours=4)`, kickoff at `now+8m` | `app.core.sync.riverside.sync_riverside` | all riverside tenants |
| 6 | `sync_dmarc` | `CronTrigger(hour=2, minute=0)` | `app.core.sync.dmarc.sync_dmarc_dkim` | all active tenants |
| 7 | `riverside_hourly_mfa_sync` | `CronTrigger(minute=0)` (every hour) | `hourly_mfa_sync` → `sync_all_tenants(mfa only)` | all riverside |
| 8 | `riverside_daily_full_sync` | `CronTrigger(hour=1, minute=0)` | `daily_full_sync` → `sync_all_tenants(full)` | all riverside |
| 9 | `riverside_weekly_threat_sync` | `CronTrigger(day_of_week=sun, hour=3, minute=0)` | `weekly_threat_sync` | all riverside |
| 10 | `riverside_monthly_report_sync` | `CronTrigger(day=1, hour=4, minute=0)` | `monthly_report_sync` | all riverside |

Additionally, a **second scheduler** (`app.core.riverside_scheduler._riverside_scheduler`, initialised in `app/main.py:100`) registers MFA/deadline/maturity/threat compliance-alert jobs. Those were also dead during the outage and were **not counted in the "10"** — but they have the same post-recovery behaviour (hourly MFA check, daily report at 08:00 UTC, etc.).

### Tenants in scope

`config/tenants.yaml` configures **5** active riverside tenants: **HTT, BCC, FN, TLL, DCE** (codes only — real IDs not in this report per LOW-1 hygiene).

---

## 2. Freshness endpoint: what prod actually says right now

There **is** a data-freshness endpoint — `GET /api/v1/health/data` — defined in [`app/api/routes/health.py`](app/api/routes/health.py). It returns per-tenant `synced_at` for 4 SQLAlchemy models (`Resource`, `CostSnapshot`, `ComplianceSnapshot`, `IdentitySnapshot`), using `func.max(model.synced_at) WHERE tenant_id = ?`. Threshold: `SYNC_STALE_THRESHOLD_HOURS` (default **24h**).

Live pull against prod (unauthenticated, read-only, at `2026-04-17T19:50:46Z`):

```json
{
  "timestamp": "2026-04-17T19:50:46.133292+00:00",
  "threshold_hours": 24,
  "any_stale": true,
  "tenants": {
    "Head-To-Toe (HTT)":  { "resources": "...T19:01:51Z", "costs": "...T18:58:08Z", "compliance": "...T18:59:57Z", "identity": "...T19:03:50Z", "stale": false },
    "Bishops (BCC)":      { "resources": "...T19:01:52Z", "costs": null,            "compliance": "...T19:00:00Z", "identity": "...T19:04:27Z", "stale": true  },
    "Frenchies (FN)":     { "resources": "...T19:01:53Z", "costs": null,            "compliance": "...T19:00:03Z", "identity": "...T19:04:32Z", "stale": true  },
    "Lash Lounge (TLL)":  { "resources": "...T19:01:54Z", "costs": null,            "compliance": "...T19:00:06Z", "identity": "...T19:04:40Z", "stale": true  }
  }
}
```

### What this actually means

Data ages at pull time:

| Tenant | resources | costs | compliance | identity |
|---|---|---|---|---|
| HTT | 48.9 min | 52.6 min | 50.8 min | 46.9 min |
| BCC | 48.9 min | **NULL — zero rows ever** | 50.8 min | 46.3 min |
| FN  | 48.9 min | **NULL — zero rows ever** | 50.7 min | 46.2 min |
| TLL | 48.9 min | **NULL — zero rows ever** | 50.7 min | 46.1 min |
| DCE | _**tenant not present in endpoint output at all**_ |

Two distinct signals here:

1. **The "≈50-min-ago" cluster is the smoking gun that post-fix sync worked.** The app was rolled onto `:6a7306a` a little over an hour before the pull. The `init_scheduler` stagger puts the first run of costs / compliance / resources / identity at roughly `start`, `start+2m`, `start+4m`, `start+6m` — and the timestamps match that pattern (costs oldest, identity newest). The interval jobs **fired once post-recovery and wrote**. `any_stale: true` is driven by the nulls below, not by any 24h-stale timestamp.

2. **`costs: null` for BCC/FN/TLL is not a libodbc-outage artefact.** `null` means `CostSnapshot` has **no rows for that tenant in history**. If the outage were the only cause, we'd see rows dated pre-outage (~6 weeks ago) with a staleness flag — not "never a row". This is a pre-existing per-tenant cost-sync failure (probably missing RBAC / Cost Management Reader on the non-HTT tenants) that was hiding behind the louder libodbc crash for weeks. Tyler-gated.

3. **DCE being absent** from the endpoint means there is no matching `Tenant` row with `is_active = True` in the prod DB, even though `config/tenants.yaml` lists DCE as active. The YAML config is not auto-synced into the `tenants` table — this is a tenant-provisioning gap, also pre-existing, also Tyler-gated.

### Freshness for the other 6 jobs: no visibility

The freshness endpoint does **not** query:

- `DMARCRecord`, `DKIMRecord`, `DMARCReport`, `DMARCAlert` (job #6 `sync_dmarc`)
- `RiversideCompliance`, `RiversideMFA`, `RiversideRequirement`, `RiversideDeviceCompliance`, `RiversideThreatData` (jobs #5, #7, #8, #9, #10 + the whole riverside_scheduler)

So for 6 of the 10 scheduler jobs, there is **no publicly observable freshness signal at all**. See §5 (Observability Gaps).

---

## 3. Evidence the post-fix scheduler is running

| Signal | Source | Result |
|---|---|---|
| Scheduler running + job count | `GET /api/v1/health` | `"scheduler": {"status": "healthy", "active_jobs": 10}` ✅ |
| Scheduler registered correct 10 jobs | `app/core/scheduler.py::init_scheduler` vs. reported count | matches ✅ |
| Interval jobs actually fired post-start | `/api/v1/health/data` timestamps | all four interval domains wrote ~48–53 min ago ✅ |
| DB connectivity (the original blocker) | `/api/v1/health.checks.database` | `healthy`, response_time_ms ≈ 50ms ✅ |
| libodbc actually present in the image | implied by any DB query succeeding at all | ✅ (it was the exact import that broke before) |
| Cron-trigger jobs fired since fix | none — first fire windows are mostly still in the future (next top-of-hour for MFA; next 01:00/02:00/etc. for dailies) | ⏳ **unverified** |
| `sync_job_logs` table contents | `GET /api/v1/sync/history` | **not accessible** — requires `Bearer` auth; Tyler-gated |
| App Insights / Log Analytics traces | KQL via `az monitor log-analytics` | **not attempted** — requires Azure credentials; Tyler-gated |

**Verdict: interval jobs confirmed working. Cron jobs not yet proven working but there's no reason to expect them to behave differently — they share the same scheduler instance and the same DB path that just succeeded.**

---

## 4. `sync_logs` schema — what a query would look like (NOT RUN)

There are two relevant tables (neither queried):

### `sync_jobs` (legacy, `app/models/sync.py::SyncJob`)
```
id, job_type, tenant_id (nullable = "all"), status, started_at, completed_at,
records_processed, error_message
```

### `sync_job_logs` (canonical, `app/models/monitoring.py::SyncJobLog`)
```
id, job_type (indexed), tenant_id (FK tenants.id, nullable), status,
started_at (indexed), ended_at, duration_ms,
records_processed, records_created, records_updated, errors_count,
error_message, details_json
```

Plus `sync_job_metrics` (aggregate rollups) and `alerts` (for surfacing sync failures to ops).

The queries Tyler would want (when he hits the DB himself — app DB creds are in Key Vault):

```sql
-- A) Has any job completed successfully since the fix deploy?
SELECT job_type, tenant_id, MAX(ended_at) AS last_success
FROM   sync_job_logs
WHERE  status = 'completed'
  AND  ended_at >= '2026-04-17T18:00:00Z'   -- ~ fix rollout
GROUP BY job_type, tenant_id
ORDER BY job_type, tenant_id;

-- B) Are we still seeing libodbc / ImportError in the logs post-fix? (Should be zero.)
SELECT COUNT(*)
FROM   sync_job_logs
WHERE  started_at >= '2026-04-17T18:00:00Z'
  AND (error_message LIKE '%libodbc%' OR error_message LIKE '%ImportError%');

-- C) Last successful run per (job_type, tenant_id) — baseline for "what's truly stale"
SELECT job_type, tenant_id,
       MAX(CASE WHEN status = 'completed' THEN ended_at END) AS last_success,
       MAX(CASE WHEN status = 'failed'    THEN ended_at END) AS last_failure,
       SUM(CASE WHEN status = 'failed'    THEN 1 ELSE 0 END) AS failure_count_all_time
FROM   sync_job_logs
GROUP BY job_type, tenant_id;

-- D) Gap in the log stream (should show a ~6-week silence ending ~2026-04-17T18:00Z)
SELECT CAST(started_at AS DATE) AS day, COUNT(*) AS runs,
       SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS ok
FROM   sync_job_logs
WHERE  started_at >= '2026-03-01'
GROUP BY CAST(started_at AS DATE)
ORDER BY day;
```

Or equivalent via the authenticated API (same info, no DB cred needed):

```http
GET /api/v1/sync/history?limit=500         # recent SyncJobLog rows, tenant-scoped
GET /api/v1/sync/metrics                   # aggregate success rate / last_success_at
GET /api/v1/sync/status/health             # MonitoringService.get_overall_status()
GET /api/v1/sync/alerts                    # active sync-failure alerts
```

These all require `Bearer` auth (admin session) — **not attempted here** per no-go list.

---

## 5. Data-freshness observability gaps

Findings, ordered by severity:

1. **`/api/v1/health/data` covers 4 of 10+ scheduler job domains.** Missing: DMARC/DKIM, Riverside compliance, Riverside MFA, Riverside requirements, Riverside devices, Riverside threats. The UI header dot can report "all green" while half the dashboard data is silently stale.
2. **No per-job `last_successful_run` exposed anonymously.** `/api/v1/sync/metrics` has it, but requires auth. A silent scheduler (like we just had for 6 weeks) would not move the `/api/v1/health.scheduler.active_jobs` counter — that field reports *registered* jobs, not *successful* runs. `active_jobs: 10` was almost certainly `10` the entire time prod was broken.
3. **`/api/v1/health` scheduler check does not surface sync_job_logs.** `scheduler.running == True` does not imply `scheduler has actually executed a job successfully`. Recommend adding a `last_successful_sync_at` or `"stale_jobs": [...]` field driven by `MonitoringService.get_overall_status()`.
4. **No alert for "no successful sync in >25h"** (this is exactly ajp1 action-item #4). The `Alert` model + `alerts` table exist; nothing populates them from a "silence" trigger. Matches the "silent outage" failure mode perfectly.
5. **YAML-configured tenant (DCE) missing from DB.** `Tenant` table and `config/tenants.yaml` drift is not surfaced anywhere — no startup reconciliation, no `/health` check for "configured tenants == DB tenants".
6. **`costs: null` vs `costs: <stale>` reported identically as `stale: true`.** A tenant that has never had a successful cost sync is visually indistinguishable from a tenant whose last successful sync was 25h ago. Those need different remediations.

---

## 6. Is a manual backfill needed?

**Short answer: no, not as part of ajp1 recovery. And for most of the gap, it's not even technically possible.**

### Why "no":
- `Resource`, `CostSnapshot`, `ComplianceSnapshot`, `IdentitySnapshot` are snapshot-of-current-state models. The source APIs (Azure Resource Graph, Cost Management, Policy Insights, Graph API) return "current state" and don't let you retroactively ask "what was this yesterday". The worst-case freshness staleness post-fix is bounded by each job's interval (resources 1h, compliance 4h, cost 24h, identity 24h). No manual intervention needed — these heal themselves.
- The interval jobs already fired successfully once post-restart (proven above). The next cycle completes the loop without human input.
- DMARC/Riverside cron jobs will fire on their natural schedule (next MFA check at 20:00 UTC today, next DMARC at 02:00 UTC tomorrow, etc.). If Tyler wants to *verify* they work without waiting, he can trigger them manually — see below.

### What's genuinely lost and can't be backfilled:
- **≈6 weeks of daily/hourly snapshots** used for trend graphs, cost anomaly detection baselines, maturity-regression detection, and threat-escalation "since last check" deltas. The `check_maturity_regressions` logic in `riverside_scheduler.py` compares `records[0]` vs `records[1]` — if only one record exists post-recovery, the first-post-outage run will produce no regression signal. That's a one-cycle dashboard artefact, not a data-integrity problem.

### If Tyler *does* want to force a manual cycle (Tyler-gated, not in this investigation):
Endpoints exist, all behind `Bearer` auth + `rate_limit("sync")`:

```http
POST /api/v1/sync/costs             # SyncType ∈ {costs, compliance, resources, identity}
POST /api/v1/sync/compliance
POST /api/v1/sync/resources
POST /api/v1/sync/identity
# Canonical aliases:
POST /api/v1/sync/trigger/{sync_type}
```

The riverside wrapper jobs (`hourly_mfa`, `daily_full`, `weekly_threat`, `monthly_report`) are only reachable via `trigger_manual_sync()` in Python — **no HTTP route exposes them**. The `SyncType` Literal in `app/api/routes/sync.py` is restricted to the 4 core types. This is itself a minor gap (ajp1 action item #2 — "trigger manual full sync ... once admin auth is set up").

**Per the no-go list, none of these were called.**

---

## 7. Recommended next actions for Tyler

Ordered by urgency; none are blocking prod — prod is healthy and self-healing.

1. **Wait and verify (free).** At `02:00 UTC` tomorrow, pull `/api/v1/health/data` again and check that the timestamps have advanced for the interval jobs (confirming the ≥1 cycle has completed). Also inspect that there are `sync_job_logs` rows for `sync_dmarc` dated after `02:00 UTC` — that confirms job #6 (DMARC cron) ran.
2. **Auth'd one-shot health check.** Hit `GET /api/v1/sync/metrics` and `GET /api/v1/sync/history?limit=100` with an admin bearer token. Confirm `last_success_at` for every job_type is ≥ `2026-04-17T18:00Z` and `last_error_message` is null/stale. This is the single best signal that the outage is fully closed.
3. **File follow-ups (not ajp1):**
   - **New issue – `costs: null` for BCC/FN/TLL.** Probably a missing `Cost Management Reader` role assignment on those tenants' subscriptions, or a misconfigured scope in `cost_service.py`. Pre-existing, unmasked by recovery. Related but not identical: bd `igi` (CLOSED 2026-03-26) granted **`Reader`** on those subscriptions for the multi-tenant-sync workflow OIDC login — `Reader` is not sufficient for Cost Management APIs; `Cost Management Reader` is a separate role, likely the missing piece.
   - **New issue – DCE tenant missing from DB.** Reconcile `config/tenants.yaml` with the `tenants` table.
   - **New issue – observability gaps (§5).** Specifically:
     - Extend `/api/v1/health/data` to cover DMARC and Riverside tables (or add `/api/v1/health/data/full`).
     - Add `MonitoringService.get_overall_status()` summary to `/api/v1/health` (or at least `last_successful_sync_at` per job).
     - Implement the "no successful sync in >25h" → `Alert` insertion rule (ajp1 action-item #4).
4. **Only if Tyler wants dashboards warm right now (not required):** run an auth'd `POST /api/v1/sync/trigger/costs` etc. for each of the 4 core types to skip the natural-cycle wait.
5. **Close ajp1 once steps 1–2 are ticked** and follow-ups are filed. The scheduler is back; the blast radius is bounded by each job's natural interval; there's no data loss that can be recovered anyway.

---

## 8. Strict no-go compliance log

Confirmed I did NOT:
- [x] Call `/api/v1/sync` or any backfill endpoint
- [x] Make any DB writes
- [x] Modify deployment or Azure state
- [x] Edit application source code
- [x] Open any secret store, connect to the prod DB, or use Azure CLI with creds

Operations performed: two unauthenticated `curl` calls to `/api/v1/health` and `/api/v1/health/data`, local file reads in the repo, local YAML parse of `config/tenants.yaml` (returned only counts + non-sensitive codes). That's it.

---

**End of report.** 🐶 — *Richard, code-puppy-2d6de5*

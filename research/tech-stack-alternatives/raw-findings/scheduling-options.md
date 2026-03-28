# Background Job Scheduling Options

## Current Jobs in the Platform

From `app/core/scheduler.py`:

| Job ID | Schedule | Description |
|--------|----------|-------------|
| sync_costs | Every N hours (configurable) | Sync cost data from Azure APIs |
| sync_compliance | Every N hours (configurable) | Sync compliance/policy data |
| sync_resources | Every N hours (configurable) | Sync resource inventory |
| sync_identity | Every N hours (configurable) | Sync identity/user data |
| sync_riverside | Every 4 hours | Riverside compliance data |
| sync_dmarc | Daily at 2 AM | DMARC/DKIM verification |
| riverside_hourly_mfa_sync | Every hour | MFA status refresh |
| riverside_daily_full_sync | Daily at 1 AM | Full compliance sync |
| riverside_weekly_threat_sync | Weekly (Sunday 3 AM) | Threat data sync |
| riverside_monthly_report_sync | Monthly (1st at 4 AM) | Month-end reporting |

**Total: 10 scheduled jobs**
**Pattern: All are "fetch from Azure API → transform → store in database"**
**Duration: Most complete in 30s-5min depending on tenant count**

## Option 1: APScheduler (Current)

**Version**: apscheduler>=3.10.0
**Mode**: AsyncIOScheduler (in-process with FastAPI)

### How It Works
- Scheduler runs in the same Python process as FastAPI
- Jobs are registered at app startup in `init_scheduler()`
- Uses IntervalTrigger and CronTrigger
- No persistent state — all in memory

### Strengths
- Zero infrastructure cost
- Zero deployment complexity
- Direct access to all app services, database, config
- Simple to debug (same process, same logs)
- ~150 lines of configuration code

### Weaknesses
- **No persistence**: App restart = missed job runs until next scheduled time
- **Single instance**: Running multiple app instances = duplicate job execution
- **No retry**: If a job fails, it's gone until next schedule
- **No monitoring dashboard**: Only log messages
- **APScheduler 4.0 rewrite**: APScheduler 4.0 (alpha) is a complete rewrite with different API — future migration uncertainty

### Improvement Options (Without Changing Technology)
```python
# 1. Add SQLAlchemy job store for persistence
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
jobstores = {'default': SQLAlchemyJobStore(url=settings.database_url)}

# 2. Add missed execution catch-up
scheduler.add_job(sync_fn, trigger=trigger,
    misfire_grace_time=3600,  # Run if missed within 1 hour
    coalesce=True)            # Coalesce multiple missed runs

# 3. Add execution logging wrapper
async def logged_job(job_name, sync_fn):
    start = time.time()
    try:
        await sync_fn()
        log_job_success(job_name, duration=time.time()-start)
    except Exception as e:
        log_job_failure(job_name, error=str(e))
        await notify_teams_webhook(f"Job {job_name} failed: {e}")
```

---

## Option 2: Azure Functions Timer Triggers

### Architecture
```
[Azure Functions App]          [Web App (App Service)]
├── sync_costs/                ├── FastAPI
│   └── function.json          ├── Routes, Templates
│   └── __init__.py            └── API endpoints
├── sync_compliance/           
│   └── function.json          Shared:
│   └── __init__.py            └── Python packages (sync logic)
├── sync_resources/            └── Database connection
│   └── ...                    └── Azure credentials
└── host.json
```

### Pricing (Consumption Plan)
| Meter | Free Grant | Cost After |
|-------|-----------|------------|
| Executions | 1,000,000/month | $0.20 per million |
| Compute (GB-s) | 400,000/month | $0.000016/GB-s |

**Estimated monthly cost for this platform:**
- 10 jobs × 30 days = ~300 executions/month (well under 1M free)
- Each job: ~128MB × 60s = ~8 GB-s per execution
- Monthly compute: ~2,400 GB-s (well under 400K free)
- **Total: $0/month**

### Advantages
- Platform-managed reliability (guaranteed execution)
- Built-in monitoring via Azure Portal + Application Insights
- Automatic retry on failure
- Timer state persisted — catches up missed runs
- Each function isolated — one failure doesn't affect others
- Free at this scale

### Disadvantages
- **Separate deployment**: New Functions app, new CI/CD pipeline
- **Code sharing**: Sync logic must be in shared package between web app and functions
- **Cold start**: 1-10 seconds on Consumption plan (fine for background jobs)
- **Local development**: Requires Azure Functions Core Tools
- **Environment parity**: Different config management (local.settings.json vs .env)
- **Storage account**: Functions require Azure Storage ($0.50-2/month for metadata)
- **Additional infrastructure**: Function app, storage account, App Insights connection

### Example: Timer Function in Python v2
```python
import azure.functions as func
import logging
from shared.sync import sync_costs

app = func.FunctionApp()

@app.schedule(schedule="0 0 */4 * * *",  # Every 4 hours
              arg_name="myTimer",
              run_on_startup=False)
async def sync_costs_timer(myTimer: func.TimerRequest):
    if myTimer.past_due:
        logging.info('Timer past due, executing catch-up')
    await sync_costs()
    logging.info('Cost sync completed')
```

---

## Option 3: Azure Durable Functions

### When It's Appropriate
- Long-running workflows (hours/days)
- Complex orchestrations with human-in-the-loop
- Fan-out/fan-in across 100+ parallel tasks
- Stateful workflows with checkpointing

### Why It's Overkill Here
- Current jobs are simple "fetch → transform → store"
- No complex orchestration needed
- No human approval steps
- 10 independent jobs, not an orchestrated pipeline
- Adds significant complexity (orchestrator, activity functions, entity functions)

### Cost
Same as regular Functions Consumption plan — $0 at this scale.

---

## Option 4: Celery + Redis

### Architecture
```
[Redis (Broker)]
    ↕
[Celery Worker]  ←→  [Celery Beat]
    ↕                    (scheduler)
[Database]
    ↕
[FastAPI Web App]
```

### Cost
- Azure Cache for Redis Basic C0: **$13.14/month**
- Or Redis on Azure VM: **$5-15/month** (self-managed)
- Already using Redis for caching — could share instance

### Advantages
- Battle-tested distributed task queue
- Flower monitoring dashboard
- Configurable retry with exponential backoff
- Result backend for job status tracking
- Multiple workers for parallel execution

### Disadvantages
- **$13+/month** additional infrastructure (18% of current $73 budget)
- Separate worker process to manage and monitor
- Celery Beat scheduler is another moving part
- Designed for high-throughput distributed systems — 10 jobs is trivial
- Python-specific — no advantage if considering language switch
- Redis as broker adds single point of failure
- Already using Redis for caching — adding Celery tasks to same instance may cause contention

---

## Recommendation

**Keep APScheduler with the following improvements:**

| Improvement | Effort | Impact |
|-------------|--------|--------|
| Add SQLAlchemy job store | 2 hours | Persists state across restarts |
| Add misfire_grace_time | 30 min | Catches up missed runs |
| Add execution logging to audit_log | 2 hours | Visibility into job history |
| Add Teams webhook on failure | 1 hour | Alerts on failed jobs |
| Add /api/sync/health endpoint | 1 hour | Monitoring integration |

**Total: ~1 day of work for significant reliability improvement.**

**Escalation path:** If APScheduler proves unreliable after these improvements, migrate to Azure Functions timer triggers (which would be free at this scale).

# APScheduler Immediate Execution on Startup

**Source**: APScheduler 3.x Official Documentation (Tier 1)  
**URLs**:
- https://apscheduler.readthedocs.io/en/3.x/modules/schedulers/base.html#apscheduler.schedulers.base.BaseScheduler.add_job
- https://apscheduler.readthedocs.io/en/3.x/userguide.html
**Version**: APScheduler 3.11.2.post1

## add_job() API Reference

### Full Signature

```python
add_job(func, trigger=None, args=None, kwargs=None, id=None, name=None,
        misfire_grace_time=undefined, coalesce=undefined, max_instances=undefined,
        next_run_time=undefined, jobstore='default', executor='default',
        replace_existing=False, **trigger_args)
```

### next_run_time Parameter

From official docs:

> **next_run_time** (*datetime*) – when to first run the job, regardless of the trigger
> (pass `None` to add the job as paused)

This parameter:
- Overrides the trigger's calculated first run time
- Is a `datetime` object
- Setting to `datetime.now()` causes immediate execution
- Setting to `None` adds the job in a paused state
- When `undefined` (default), the trigger calculates the next run time normally

### User Guide Tip

From the "Adding jobs" section:

> **Tip**: To run a job immediately, omit `trigger` argument when adding the job.

This creates a **one-shot** job that runs immediately with no recurrence.

## Correct Pattern for IntervalTrigger + Immediate First Run

```python
from datetime import datetime, UTC
from apscheduler.triggers.interval import IntervalTrigger

scheduler.add_job(
    sync_compliance,
    trigger=IntervalTrigger(hours=4),
    id="sync_compliance",
    name="Sync Compliance Data",
    replace_existing=True,
    next_run_time=datetime.now(UTC),  # Fire immediately, then every 4 hours
)
```

### How It Works

1. Job is added to the scheduler with `next_run_time=now`
2. When the scheduler processes due jobs, it sees this job is past due
3. The job fires immediately
4. After firing, the `IntervalTrigger` calculates the next run time (now + 4 hours)
5. Subsequent runs follow the normal interval schedule

### Important Notes

1. **Timezone awareness**: Use `datetime.now(UTC)` instead of `datetime.now()` to avoid timezone issues. APScheduler handles timezone-aware datetimes correctly.

2. **replace_existing=True**: Required when using persistent job stores to avoid duplicate jobs on restart. From the docs:

> **Important**: If you schedule jobs in a persistent job store during your application's
> initialization, you **MUST** define an explicit ID for the job and use
> `replace_existing=True` or you will get a new copy of the job every time your
> application restarts!

3. **misfire_grace_time**: Consider setting this to `None` to allow the job to run no matter how late it is, especially for startup scenarios where the scheduler might start slowly.

## Alternative Patterns

### Pattern A: Separate one-shot + recurring (NOT RECOMMENDED)

```python
# Immediate one-shot
scheduler.add_job(sync_compliance, id="sync_init")

# Recurring
scheduler.add_job(
    sync_compliance,
    trigger=IntervalTrigger(hours=4),
    id="sync_compliance",
    replace_existing=True,
)
```

**Drawback**: Two job entries, potential race conditions.

### Pattern B: Staggered immediate execution (RECOMMENDED for multiple jobs)

```python
from datetime import timedelta

now = datetime.now(UTC)
jobs = [
    ("costs", sync_fns["costs"], 0),
    ("compliance", sync_fns["compliance"], 2),
    ("resources", sync_fns["resources"], 4),
    ("identity", sync_fns["identity"], 6),
]

for job_id, func, delay_minutes in jobs:
    scheduler.add_job(
        func,
        trigger=IntervalTrigger(hours=settings.get_interval(job_id)),
        id=f"sync_{job_id}",
        replace_existing=True,
        next_run_time=now + timedelta(minutes=delay_minutes),
    )
```

**Advantage**: Avoids API rate limiting and resource contention from all jobs firing simultaneously.

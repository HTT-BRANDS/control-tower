---
status: accepted
date: 2025-04-15
decision-makers: Solutions Architect 🏛️, Python Programmer 🐍, Pack Leader 🐺
consulted: Code Puppy 🐶 (implementation), QA Expert 🐾 (fitness functions)
informed: All engineering teams
relates-to: ADR-0009 (database tier), STRIDE T-1, STRIDE R-1
---

# ADR-0010: Sync Reliability — Prevent Cascading Failures in Multi-Tenant Data Sync

## Context and Problem Statement

The Azure Governance Platform syncs data from multiple Azure tenants on a
scheduled basis (costs, compliance, resources, identity, DMARC). During
production operations several failure modes were observed:

1. **Column overflow cascade:** Azure Policy names exceeding the
   `policy_name VARCHAR(255)` column caused a `DataError`. Because all
   tenants shared a single SQLAlchemy session, the poisoned session killed
   sync for *every remaining tenant* in the batch.

2. **Ghost jobs:** If the sync process was OOM-killed or crashed mid-run,
   jobs remained stuck in `running` status forever, blocking subsequent
   scheduler invocations.

3. **Silent cold start:** `IntervalTrigger` scheduler jobs without an
   explicit `next_run_time` don't fire until their first interval elapses
   (hours later), leaving dashboards empty after a fresh deployment.

4. **Dead code confusion:** A placeholder `SyncService` stub in
   `app/api/services/sync_service.py` returned mock data, causing
   confusion about which code path was actually used.

How do we make multi-tenant data sync resilient to single-tenant failures
without requiring a complete architectural rewrite?

## Decision Drivers

- **Blast radius:** A single tenant's bad data must not affect other tenants
- **Observability:** Truncation and failures must be logged for audit trail
- **Startup latency:** Dashboards must show data within minutes of deployment
- **Simplicity:** Prefer targeted fixes over major refactors (YAGNI)
- **Testability:** Fixes must be enforceable via automated fitness functions

## Considered Options

1. **Per-tenant session isolation with safe truncation** (chosen)
2. Full async task queue (Celery / Azure Service Bus)
3. Separate worker process per tenant

## Decision Outcome

Chosen option: **Per-tenant session isolation with safe truncation**, because
it addresses all observed failure modes with minimal architectural change and
is fully enforceable via fitness functions.

### Implementation Details

| Fix | Description | Files |
|-----|-------------|-------|
| **FF-1: Widen policy_name** | `String(255)` → `String(1000)` | `alembic/versions/009_widen_policy_name.py`, `app/models/compliance.py` |
| **FF-2: safe_truncate** | Audit-logged truncation for oversized fields | `app/core/sync/utils.py`, used in `app/core/sync/compliance.py` |
| **FF-3: Per-tenant sessions** | Each tenant gets a fresh `get_db_context()` session | All 5 sync modules: `compliance`, `costs`, `resources`, `identity`, `dmarc` |
| **FF-4: Staggered startup** | `next_run_time` + `timedelta` offsets on all `IntervalTrigger` jobs | `app/core/scheduler.py` |
| **FF-5: Remove dead stub** | Delete placeholder `SyncService` | `app/api/services/sync_service.py` (deleted) |
| **FF-6: Migration guard** | Alembic migration 009 must exist and reference `policy_name` | `alembic/versions/009_widen_policy_name.py` |

### Consequences

- **Good:** Single-tenant failures are now isolated — one tenant's bad data
  cannot cascade to kill other tenants' sync
- **Good:** Oversized fields are truncated with structured warning logs
  (satisfies STRIDE T-1 tampering and R-1 repudiation requirements)
- **Good:** Dashboards show data within 2 minutes of deployment (staggered
  startup with 15-second offsets)
- **Good:** Ghost jobs are auto-cleaned by `cleanup_ghost_jobs()` (30 min
  threshold)
- **Neutral:** Slightly more database connections during sync (one per
  tenant instead of one shared), acceptable for current scale (< 10 tenants)
- **Bad:** If we grow to 50+ tenants, the per-tenant session model may need
  batching — but this is a good problem to have (see scaling path below)

### Confirmation

All six fixes are enforced by architectural fitness functions in
`tests/architecture/test_sync_data_integrity.py`:

```bash
uv run pytest tests/architecture/test_sync_data_integrity.py -v
```

These tests verify structural properties of the codebase (column widths, AST
patterns, file existence) and will fail immediately if any fix regresses.

## STRIDE Security Analysis

| Threat Category | Risk Level | Mitigation |
|-----------------|-----------|------------|
| **Spoofing** | Low | No auth changes; sync uses existing UAMI credentials |
| **Tampering** | Medium → Low | `safe_truncate` logs all truncations with field name, original length, and context |
| **Repudiation** | Medium → Low | Structured logging provides audit trail for all data modifications |
| **Information Disclosure** | Low | No new data exposure; truncation only reduces data |
| **Denial of Service** | High → Low | Session isolation prevents cascade; ghost job cleanup prevents stuck state |
| **Elevation of Privilege** | Low | No privilege changes; sync operates with existing service identity |

**Overall Security Posture:** Significantly improved. The primary risk (DoS
via cascading session failure) is eliminated.

## Scaling Path

| Scale | Tenants | Strategy |
|-------|---------|----------|
| **Current (Phase 1)** | < 10 | Per-tenant sessions, sequential sync |
| **Phase 2** | 10–50 | Batched sessions (5 tenants per batch), `asyncio.gather` |
| **Phase 3** | 50+ | Azure Service Bus task queue, dedicated sync worker |

## More Information

- Fitness functions: `tests/architecture/test_sync_data_integrity.py`
- Sync utilities: `app/core/sync/utils.py`
- Scheduler with staggered startup: `app/core/scheduler.py`
- Ghost job cleanup: `app/api/services/monitoring_service.py`

---

**Template Version:** MADR 4.0 (September 2024) with STRIDE Security Analysis
**Last Updated:** 2025-05-25
**Maintained By:** Code Puppy 🐶 (retroactive documentation)

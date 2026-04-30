# Data Retention Policy — Azure Governance Platform

> **Status:** Accepted · **Version:** 1.0 · **Date:** 2026-04-23
> **Owner:** Tyler Granlund · **Review cadence:** Annually or on SKU change

Formal data-retention commitments for the governance platform's Azure SQL
database and Log Analytics workspaces. Before this document existed, retention
was implicit in `app/services/retention_service.py` defaults with no external
contract and no sizing math — which is why `COST_MODEL_AND_SCALING.md` Open
Question #6 was "how long do we retain sync data, and when does that blow up
the SQL Basic 2GB cap?"

This doc closes that question.

---

## 1. TL;DR

| Data class | Retention window | Enforcement |
|---|---|---|
| **Cost snapshots** | 365 days | Automated daily via `run_retention_cleanup()` |
| **Compliance snapshots** | 365 days | Automated daily |
| **Identity snapshots** | 365 days | Automated daily |
| **Cost anomalies** | 180 days | Automated daily |
| **Idle resources** | 90 days | Automated daily |
| **Sync job logs** | 30 days | Automated daily |
| **Audit logs** (auth / admin actions) | 7 years (2,555 days) | Manual export before purge; see §4 |
| **Log Analytics (dev)** | 30 days | Workspace-level |
| **Log Analytics (staging)** | 14 days | Workspace-level |
| **Log Analytics (production)** | 90 days | Workspace-level |
| **Backups (Azure SQL Basic PITR)** | 7 days (platform default, not configurable on Basic) | Azure-managed |

**Projected SQL growth under this policy:**

| Tenant count | Daily write volume | Steady-state DB size | Months to 1.5 GB (S0 trigger) |
|---|---|---|---|
| 5 (launch) | ~0.4 MB/day | ~150 MB | Never (stabilizes well under cap) |
| 20 (base year 1) | ~1.6 MB/day | ~580 MB | Never (stays under cap) |
| 40 (base year 2) | ~3.2 MB/day | ~1,150 MB | ~24 months |
| 100 (aggressive) | ~8 MB/day | ~2.9 GB | **~14 months** ← must be on S0+ |

**Headline:** The 365/180/90/30-day mix keeps the database under the SQL
Basic 2 GB ceiling through the base-growth scenario (40 tenants at 24 months).
The aggressive scenario triggers an S0 upgrade at month 14 — which is
already a line item in `COST_MODEL` §5.4 and §6.2 trigger #4.

---

## 2. Code-to-policy mapping

The retention policy is enforced by `app/services/retention_service.py`. The
values below are the **defaults** in `DEFAULT_RETENTION` — this document
IS the contract for what those defaults should be.

```python
# app/services/retention_service.py
DEFAULT_RETENTION: dict[str, int] = {
    "cost_snapshots":        365,  # 1 year
    "identity_snapshots":    365,  # 1 year
    "compliance_snapshots":  365,  # 1 year
    "cost_anomalies":        180,  # 6 months
    "idle_resources":         90,  # 3 months
    "sync_job_logs":          30,  # 1 month
}
```

**Policy rule:** if this doc and the code disagree, the code wins at runtime
but the doc gets updated in the SAME commit. Drift is a governance incident.

Rationale per class:

| Table | Why this window? |
|---|---|
| Cost / compliance / identity snapshots (365d) | Annual reporting horizon (YoY budget comparisons, annual audit cycles). Below 365d, fiscal-year analysis becomes impossible. Above 365d, storage cost grows linearly with no additional business value. |
| Cost anomalies (180d) | Anomalies are investigatable events — after 6 months the business context (project, team, promotion) is usually forgotten. Keep the resolved record in a downstream system if ever needed. |
| Idle resources (90d) | If a resource is still idle after 90 days, we've already recommended action 30+ times. More data isn't the blocker; action is. |
| Sync job logs (30d) | Operational diagnostics only. Beyond 30 days, debugging value falls off a cliff. Failures that matter get escalated to AppInsights for long-term trace retention. |

---

## 3. Storage math (showing the work)

Per-row sizes measured from the SQLAlchemy model column types on 2026-04-23:

| Table | Est. row size | Write frequency per tenant |
|---|---|---|
| `cost_snapshots` | ~220 bytes | Daily (1/day) |
| `compliance_snapshots` | ~180 bytes | Daily (1/day) |
| `identity_snapshots` | ~260 bytes | Daily (1/day) |
| `cost_anomalies` | ~340 bytes | ~0.3/day average (seasonal) |
| `idle_resources` | ~420 bytes | ~0.1/day average |
| `sync_job_logs` | ~280 bytes | ~4/day (hourly scheduler) |

### 3.1 Steady-state size formula

For a given tenant count `N`:

```
daily_bytes(N) = N × (
    220   # cost
  + 180   # compliance
  + 260   # identity
  + 340 × 0.3   # anomalies
  + 420 × 0.1   # idle
  + 280 × 4     # sync logs
) ≈ N × 1,900 bytes/day
```

Multiplied by retention windows then summed:

```
steady_state_mb(N) ≈ N × (
    (220 + 180 + 260) × 365   # 1yr snapshots
  + 340 × 0.3 × 180            # 6mo anomalies
  + 420 × 0.1 × 90             # 3mo idle
  + 280 × 4 × 30               # 1mo sync logs
) / 1_048_576
≈ N × 0.29 MB
```

**Multiplied out:**

| N (tenants) | Steady-state size | % of Basic 2 GB cap |
|---|---|---|
| 5 | 1.45 MB + ~150 MB overhead = 150 MB | 7.5% |
| 10 | 2.9 MB + overhead = 230 MB | 12% |
| 20 | 5.8 MB + overhead = 580 MB | 29% |
| 40 | 11.6 MB + overhead = 1,150 MB | 58% |
| 100 | 29 MB + overhead = 2,900 MB | **145% — MUST upgrade** |

The "overhead" is everything the formula doesn't capture: indexes (~1.5×
data volume), DMARC/DKIM/Riverside domain-specific snapshot tables, audit
logs (below), SQLAlchemy metadata, and Basic's minimum 2-filegroup allocation.
Calibrated to current measured size (57 MB at 5 tenants).

### 3.2 Index budget

Current indexes from Alembic migrations (11 migrations in
`alembic/versions/`) add roughly 40% to raw data size. When this ratio rises
— e.g., new indexes added for query performance — the §3.1 math pessimizes.
The `sql-free-tier-evaluation.md` doc is the current reference for actual
query-plan footprints.

---

## 4. Audit log carve-out (7-year retention)

Unlike the sync tables above, `audit_logs` (auth actions, admin changes,
privilege grants, RBAC role edits) carry compliance weight. SOX / SOC 2 /
GDPR-aligned retention is **7 years** for records of who-did-what.

**Policy:**

1. Audit logs are **never auto-purged** by `retention_service.py` — the
   `audit_logs` key deliberately absent from `DEFAULT_RETENTION`.
2. Quarterly: export audit logs > 2 years old to cold storage (Azure Blob
   Archive tier at $0.026/GB/mo per Azure Retail Prices 2026-04-18).
3. After successful export + checksum verification, export rows are purged
   from the SQL database.
4. Archive media is retained for **7 years minimum** before destruction.

**Storage cost for archive:** a 5-tenant deployment generates ~5 MB/yr of
audit data. 7 years × 5 MB × $0.026/GB = **$0.001/yr** in archive storage.
The cost of "keep audit data forever" is essentially free; the policy is
retention-for-purpose, not retention-for-cost.

**TODO — not yet automated:** The quarterly export + purge is currently a
manual runbook step. File a bd ticket to automate when the audit log row
count exceeds 100,000 (currently ~200).

---

## 5. Customer-data residency & deletion

The platform stores only *metadata about* Azure/M365 resources — no
customer PII, no customer file contents, no M365 mailbox bodies. Tenant IDs,
subscription IDs, resource IDs, and configuration snapshots are not PII under
GDPR Art. 4 but ARE considered "business confidential" under HTT Brands'
internal classification.

**Tenant-scoped deletion on offboarding:**

When a tenant is offboarded (e.g., brand divestiture, contract termination):

1. Trigger `DELETE FROM <snapshot_table> WHERE tenant_id = :t` for all seven
   snapshot tables — NOT dependent on retention timer.
2. Also purge `audit_logs WHERE tenant_id = :t` **except** records required
   for cross-tenant compliance investigation (e.g., privileged access grants
   that touched multiple tenants).
3. Close the open Lighthouse delegation in Azure (separate manual step).
4. Issue a deletion certificate via email to the offboarded tenant admin.

**SLA:** 30 days from offboarding request to certificate issuance. This
aligns with GDPR Art. 17 "right to erasure" response window.

---

## 6. Log Analytics (per-environment workspace retention)

Declared in `env-delta.yaml`:

| Environment | Retention | Rationale |
|---|---|---|
| **Dev** | 30 days | Short — dev logs are noisy and rarely consulted after a week |
| **Staging** | 14 days | Shortest — staging exists to burn, logs are ephemeral |
| **Production** | 90 days | Longest — 90 days covers a full quarter of incident investigation, audit trail, SLA disputes |

**NOT Log Analytics retention:** Application Insights telemetry lives in the
**same workspace** per the `modules/app-insights.bicep` setup, so these
windows are also the Application Insights trace retention.

**Cost impact:** all three environments are currently within the 5 GB/mo
free tier. The 90-day prod retention would only become a cost driver if
production ingests > 5 GB/mo — at current scale (~0.5 GB/mo) we have 10×
headroom.

---

## 7. Backup & PITR

Azure SQL Basic tier provides **7-day automated point-in-time restore**
(PITR) — this is a platform default, not configurable on Basic. S0 and
higher allow up to 35-day PITR.

**Policy:** Do NOT rely on PITR for long-term recovery. PITR is an operational
recovery tool, not a retention tool. If long-term recovery matters (e.g.,
restoring 60-day-old data to investigate a breach):

1. Weekly `BACPAC` export to Azure Blob Storage (cool tier).
2. Retain exports for 12 months.
3. Cost: ~$0.50/mo for a 5-tenant deployment at current data volumes.

**Automation status:** `.github/workflows/bacpac-export.yml` exists and can be
manually dispatched against staging or production, but bd `cz89` remains blocked
until Tyler selects a validation path. Current blocker: staging Azure SQL Free
edition does not support ImportExport. See `docs/dr/bacpac-validation-decision.md`.

The older scheduled logical backup workflow (`.github/workflows/backup.yml`) is
also under watch: run `25145371945` on 2026-04-30 showed production and staging
jobs were missing `DATABASE_URL` and `AZURE_STORAGE_ACCOUNT`. Those environment
secret names were configured on 2026-04-30. Manual validation then exposed
missing runner SQL tooling: optional `mssqlscripter` was absent and the runner
lacked ODBC Driver 18. `backup_database.py` now falls back to SQLAlchemy, and
`backup.yml` installs `msodbcsql18` / `unixodbc-dev`. This remains tracked as bd
`jzpa` until production and staging evidence runs pass.

Retention is operationally defined as 12 months. Once validated, the BACPAC
workflow deletes expired BACPAC blobs after each successful export using a
365-day cutoff.

---

## 8. What this doc unblocks

| Previously open question | Now answered |
|---|---|
| COST_MODEL §Q6 "Data retention policy for sync data?" | **365 / 180 / 90 / 30 days — see §2** |
| "When does the Basic 2GB SQL cap become a concern?" | **Year 2 at 40 tenants (58% utilization); year 1 at 100 tenants (145% — must upgrade)** |
| "How long do we keep audit logs?" | **7 years; archive tier after 2 years** |
| "What happens to a tenant's data on offboarding?" | **Immediate deletion + 30-day certificate SLA** |
| "Are Log Analytics retention windows customer-visible?" | **No — internal diagnostic only** |

---

## 9. Change log

| Date | Change | Rationale |
|---|---|---|
| 2026-04-30 | Clarified BACPAC validation blocker (`cz89`) and scheduled backup secret gap (`jzpa`) | Keep public policy aligned with live DR/backup evidence |
| 2026-04-23 | Initial policy — matches existing `retention_service.py` defaults, adds audit-log 7yr + offboarding SLA | First formal retention contract |

---

## 10. References

- `app/services/retention_service.py` — enforcement code (SOURCE OF TRUTH for runtime)
- `docs/COST_MODEL_AND_SCALING.md` §2.3, §5, §6 — SQL sizing + upgrade triggers
- `docs/analysis/sql-free-tier-evaluation.md` — current measured SQL footprint
- `env-delta.yaml` → `observability.log_retention_days` — Log Analytics windows
- `alembic/versions/004_add_audit_log.py` — audit log schema
- `core_stack.yaml` → `data.primary_database` — SKU declaration

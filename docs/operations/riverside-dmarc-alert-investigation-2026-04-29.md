# Riverside batch + DMARC alert investigation — 2026-04-29

Issue: `azure-governance-platform-tg2z`  
Branch: `pack/tg2z-riverside-dmarc-investigation`  
Investigator: `code-puppy-4f59fa`

## Scope

Post-`0gz3` recovery left 10 active alerts after production deploy run
`25131829042` and stale platform sync alert cleanup:

- 7 `high_error_rate` alerts for `riverside_batch`
- 1 `sync_failure` alert for `riverside_batch`
- 2 `no_records` alerts for `dmarc`

This note separates what can be proven from repository evidence from what still
requires production database/App Insights access.

## Access and verification status

Verified from this worktree:

- Branch was rebased cleanly onto `origin/main` before investigation.
- Public prod health endpoint is reachable and healthy:
  `https://app-governance-prod.azurewebsites.net/health` returned
  `{"status":"healthy","version":"2.5.0","environment":"production"}`.
- GitHub run `25131829042` is visible and concluded `success` for head SHA
  `3c9c3177cdf5c1e01806f9bf166cbf552a1c345c`.
- The `0gz3` bead close reason records that post-deploy platform jobs
  (`costs`, `compliance`, `resources`, `identity`) completed with zero errors
  and that the remaining Riverside/DMARC alerts were explicitly out of scope.

Not verified live in this session:

- Azure CLI is not authenticated locally (`az account show` returned no JSON),
  so App Insights KQL, App Service log download, Azure SQL, and Key Vault reads
  were unavailable.
- Protected application APIs such as `/api/v1/dmarc/summary` returned `401`
  without a bearer token.
- No alert rows were resolved or suppressed. No tenant configuration or secret
  state was changed.

## Repo evidence: `riverside_batch`

The remaining Riverside alerts are produced by the legacy batch sync path in
`app/services/riverside_sync.py`, not by the recovered platform sync jobs:

- `sync_all_tenants()` starts monitoring with
  `MonitoringService.start_sync_job(job_type="riverside_batch")`.
- It processes every active tenant from the `tenants` table:
  `session.query(Tenant).filter(Tenant.is_active == True).all()`.
- For each tenant, it attempts enabled operations for MFA, requirements, and
  maturity scoring. Device sync is intentionally skipped/disabled by default
  pending Sui Generis MSP integration.
- A tenant is counted failed only when all enabled sync operations fail:
  the progress error text is exactly
  `All sync operations failed for {tenant.name}`.
- The issue reports the dominant recent Riverside message as
  `All sync operations failed for Delta Crown Extensions (DCE)`, which matches
  this per-tenant batch failure path.

The monitor then creates generic alerts in
`app/api/services/monitoring_service.py`:

- `sync_failure` only for `status == "failed"`.
- `high_error_rate` when recent non-running logs for the same `job_type` have
  `errors_count / records_processed > 30%`.

### Finding

From code and bead evidence, the DCE Riverside failures are not evidence that
`0gz3` platform sync recovery regressed. They are isolated to the Riverside
compliance batch path and are consistent with a DCE tenant-specific data access
or tenant configuration problem.

However, repo evidence alone cannot prove whether DCE is expected
configuration noise or a real sync bug. That decision requires live evidence for
DCE specifically:

1. Recent `sync_job_logs` rows for `job_type = 'riverside_batch'`, including
   `status`, `records_processed`, `errors_count`, `error_message`, and
   `details_json`.
2. The DCE tenant database row (`tenants.name`, `tenants.id`,
   `tenants.tenant_id`, `tenants.is_active`) to confirm whether DCE is intended
   to be active for Riverside batch sync.
3. App Insights/App Service traces around the same run timestamps for the
   underlying Graph/API errors from `sync_tenant_mfa()`,
   `sync_requirement_status()`, and `sync_maturity_scores()`.
4. Graph consent/permission evidence for DCE for the Riverside sync endpoints.

Recommended operational next step: if DCE is not onboarded/consented for this
Riverside batch path, mark the tenant inactive for that specific workstream or
teach the batch to scope to explicitly onboarded Riverside tenants. If DCE is
supposed to be active, treat the repeated all-operations failure as actionable
and investigate Graph auth/permissions before suppressing alerts.

## Repo evidence: DMARC `no_records`

The DMARC scheduled sync path is `app/core/sync/dmarc.py`:

- `sync_dmarc_dkim()` starts monitoring with `job_type="dmarc"`.
- It queries all active tenants and prioritizes the hard-coded Riverside IDs:
  `riverside-htt`, `riverside-bcc`, `riverside-fn`, `riverside-tll`.
- For each tenant it syncs DMARC records, DKIM records, and DMARC reports.
- `_fetch_dmarc_reports()` in `app/api/services/dmarc_service.py` is currently
  a placeholder that always returns `[]` until a real RUA mailbox/report service
  integration exists.
- `sync_dmarc_records()` returns only domains discovered through Graph and DNS
  lookups. If Graph domain access is unavailable or no non-`onmicrosoft.com`
  domains are returned, the run can complete with zero records.

Generic `no_records` alerts are created by `MonitoringService` after three
completed zero-record runs for a job type. The query is scoped only by
`job_type`, not by tenant, which is acceptable for the current aggregate DMARC
scheduler because it starts one aggregate `dmarc` job, but it means the alert is
not enough by itself to identify a specific tenant/domain.

### Finding

The two active `dmarc` `no_records` alerts are plausible stale/actionability
candidates, but cannot be safely resolved from repo evidence alone:

- They may be stale if recent post-deploy `dmarc` runs now process records.
- They may be actionable if the aggregate DMARC job still processes zero records
  because Graph domain permissions, DNS discovery, or tenant onboarding are
  broken.
- They may also reflect unfinished product scope: DMARC aggregate report ingest
  is explicitly a placeholder, so zero report records are expected until a RUA
  integration exists. That does not automatically explain zero DMARC/DKIM
  records, which depend on Graph domains and DNS.

Recommended operational next step: query recent `sync_job_logs` for
`job_type = 'dmarc'` after deploy `25131829042`. Resolve the two stale alerts
only if there are newer successful `dmarc` runs with `records_processed > 0` and
no matching active failures. If records remain zero, do not suppress; validate
Graph `Domain.Read.All`/directory permissions and the tenant domain list.

## Suggested read-only SQL checks

Run these against production with an authorized principal. Do not mutate rows
until the evidence supports it.

```sql
-- Active alerts in this issue scope
SELECT id, alert_type, severity, job_type, tenant_id, title, message,
       created_at, details_json
FROM alerts
WHERE is_resolved = 0
  AND job_type IN ('riverside_batch', 'dmarc')
ORDER BY created_at DESC;

-- Recent Riverside batch runs
SELECT TOP 20 id, job_type, tenant_id, status, started_at, ended_at,
       records_processed, errors_count, error_message, details_json
FROM sync_job_logs
WHERE job_type = 'riverside_batch'
ORDER BY started_at DESC;

-- Recent DMARC runs
SELECT TOP 20 id, job_type, tenant_id, status, started_at, ended_at,
       records_processed, errors_count, error_message, details_json
FROM sync_job_logs
WHERE job_type = 'dmarc'
ORDER BY started_at DESC;

-- DCE tenant row used by Riverside batch scoping
SELECT id, name, tenant_id, is_active
FROM tenants
WHERE name LIKE '%Delta Crown%'
   OR name LIKE '%DCE%';
```

## Recommendation

Do not close or suppress the 10 remaining alerts from this repo-only evidence.
The safest classification is:

- `riverside_batch` DCE alerts: separate tenant/workstream issue, likely
  tenant-specific config/consent/onboarding noise **unless** live logs show a
  shared code exception. Needs prod logs/SQL to decide.
- `dmarc` `no_records`: unresolved. Could be stale after recovery or could be a
  real DMARC Graph/domain ingest gap. Needs recent post-deploy `dmarc` run rows.

This does not indicate a regression of the `0gz3` platform sync recovery based
on the bead close evidence and the separate `job_type` paths.

# Sync Recovery Verification Runbook

**For:** `azure-governance-platform-0gz3`  
**Purpose:** Verify production sync recovery after the scheduled sync eligibility fix (`5647fab`)  
**Last Updated:** 2026-04-23

---

## Why this exists

The fix for `azure-governance-platform-tbvs` changed two important behaviors:

1. scheduled sync jobs now skip tenants that are active but not actually auth-configured
2. Key Vault secret mode no longer silently falls back to shared settings credentials for non-Lighthouse tenants

This runbook verifies that production behavior matches that intent:

- sync success rates recover
- bogus tenant auth failures stop appearing
- active alerts burn down
- only intended tenants are being synced

---

## Production targets

```bash
export PROD_URL="https://app-governance-prod.azurewebsites.net"
export PROD_RG="rg-governance-production"
export PROD_APP="app-governance-prod"
export PROD_SQL_SERVER="sql-gov-prod-mylxq53d"
export PROD_SQL_DB="governance"
export FIX_COMMIT="5647fab"
```

---

## Phase 0 — prerequisites

You need at least one of these:

- an authenticated admin session against the app API
- Azure CLI access (`az login`)
- SQL access to the production database
- App Insights / Log Analytics query access

Useful basic checks:

```bash
curl -s "$PROD_URL/health" | jq .
curl -s "$PROD_URL/health/detailed" | jq .
az account show --query '{subscription:name, tenantId:tenantId}'
```

---

## Phase 1 — app/API verification

> These endpoints require authenticated access. Use a Bearer token or an authenticated browser session.

### 1.1 Overall sync health

```bash
curl -s \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  "$PROD_URL/api/v1/sync/status/health" | jq .
```

**Pass signals:**
- overall status is no longer degraded because of repeated bogus tenant failures
- costs success rate is above `0`
- `last_success_at` advances after deploy

### 1.2 Aggregate sync metrics

```bash
curl -s \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  "$PROD_URL/api/v1/sync/metrics" | jq .
```

If you want just costs:

```bash
curl -s \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  "$PROD_URL/api/v1/sync/metrics?job_type=costs" | jq .
```

**Pass signals:**
- `success_rate` increases versus the pre-fix baseline
- `last_success_at` for `costs` is newer than the deploy window
- `last_error_message` no longer mentions tenant auth failures for fake/unconfigured tenants

### 1.3 Recent history

```bash
curl -s \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  "$PROD_URL/api/v1/sync/history?limit=200" | jq .
```

Filter by job type if needed:

```bash
curl -s \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  "$PROD_URL/api/v1/sync/history?job_type=costs&limit=200" | jq .
```

**Look for:**
- completed runs after deploy
- fewer failed runs overall
- no churn from obviously fake tenant IDs
- no repeated `invalid_tenant` / missing per-tenant credential noise

### 1.4 Active alerts

```bash
curl -s \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  "$PROD_URL/api/v1/sync/alerts" | jq .
```

Include resolved alerts if you want the full trail:

```bash
curl -s \
  -H "Authorization: Bearer $BEARER_TOKEN" \
  "$PROD_URL/api/v1/sync/alerts?include_resolved=true" | jq .
```

**Pass signals:**
- active alert count trends down from the `222` baseline
- newly-created alerts are not dominated by the same bogus auth signature

---

## Phase 2 — database verification

Use whatever SQL path you already trust (`sqlcmd`, Azure Data Studio, portal query editor, etc).

### 2.1 Recent sync status by job type

```sql
SELECT job_type, status, COUNT(*) AS runs
FROM sync_job_logs
WHERE started_at >= DATEADD(day, -1, SYSUTCDATETIME())
GROUP BY job_type, status
ORDER BY job_type, status;
```

**Pass signals:**
- `costs` has completed runs in the last 24h
- failed counts materially reduce after deploy

### 2.2 Latest runs with dominant error signatures

```sql
SELECT TOP 100
    id,
    job_type,
    tenant_id,
    status,
    started_at,
    ended_at,
    errors_count,
    LEFT(error_message, 500) AS error_message
FROM sync_job_logs
WHERE started_at >= DATEADD(day, -2, SYSUTCDATETIME())
ORDER BY started_at DESC;
```

**Look for absence of:**
- `invalid_tenant`
- `Tenant <id> is not configured for per-tenant Key Vault credentials`
- repeated auth failures for tenants that should never have been scheduled

### 2.3 Last success / last failure per tenant and job type

```sql
SELECT
    job_type,
    tenant_id,
    MAX(CASE WHEN status = 'completed' THEN ended_at END) AS last_success,
    MAX(CASE WHEN status = 'failed' THEN ended_at END) AS last_failure,
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failure_count
FROM sync_job_logs
GROUP BY job_type, tenant_id
ORDER BY job_type, tenant_id;
```

**Pass signals:**
- intended tenants have recent `last_success`
- junk tenants stop accumulating new failures

### 2.4 Recent alert signatures

```sql
SELECT TOP 100
    created_at,
    severity,
    alert_type,
    job_type,
    tenant_id,
    title,
    LEFT(message, 500) AS message,
    is_resolved
FROM alerts
WHERE created_at >= DATEADD(day, -2, SYSUTCDATETIME())
ORDER BY created_at DESC;
```

### 2.5 Alert burn-down summary

```sql
SELECT
    severity,
    alert_type,
    job_type,
    is_resolved,
    COUNT(*) AS count_alerts
FROM alerts
WHERE created_at >= DATEADD(day, -2, SYSUTCDATETIME())
GROUP BY severity, alert_type, job_type, is_resolved
ORDER BY count_alerts DESC;
```

### 2.6 Tenant config sanity check

```sql
SELECT
    id,
    name,
    tenant_id,
    is_active,
    use_lighthouse,
    use_oidc,
    client_id,
    client_secret_ref
FROM tenants
ORDER BY name;
```

Use this when failures persist for a specific tenant and you need to prove whether it is actually configured for the auth mode you expect.

---

## Phase 3 — App Insights / KQL verification

If sync traces are landing in Application Insights, use KQL to confirm the bad signature disappeared.

### 3.1 Recent sync trace failures

```kusto
traces
| where timestamp > ago(24h)
| where message has_any ("cost sync", "compliance sync", "resource sync", "identity sync", "Error processing tenant")
| project timestamp, severityLevel, message, operation_Name, cloud_RoleName
| order by timestamp desc
```

### 3.2 Search for the old bogus-tenant signatures

```kusto
traces
| where timestamp > ago(24h)
| where message has_any (
    "invalid_tenant",
    "Key Vault credentials not found",
    "falling back to settings credentials",
    "not configured for per-tenant Key Vault credentials"
)
| project timestamp, severityLevel, message
| order by timestamp desc
```

**Pass signal:** no new matches after deployment, or an obvious sharp drop-off immediately after rollout.

### 3.3 Exception grouping for remaining failures

```kusto
exceptions
| where timestamp > ago(24h)
| summarize count() by type, outerMessage
| order by count_ desc
```

### 3.4 If customDimensions capture job metadata

```kusto
traces
| where timestamp > ago(24h)
| extend job_type = tostring(customDimensions.job_type)
| extend tenant_id = tostring(customDimensions.tenant_id)
| summarize count() by job_type, tenant_id, severityLevel
| order by count_ desc
```

If this returns nothing useful, the app is not emitting structured sync dimensions yet. Don’t make up conclusions from empty telemetry.

---

## Phase 4 — pass / fail decision

Mark recovery as **verified** only if all of these are true:

- `costs` has successful runs after deploy
- sync metrics improve from the pre-fix baseline
- no new failures are driven by fake or unconfigured tenants
- active alerts trend downward from the `222` baseline
- remaining failures, if any, are real tenant/data/platform issues rather than scheduler eligibility bugs

Keep `0gz3` open if any of these remain false.

---

## If recovery is incomplete

### Case A — bogus tenant failures continue

That means one of these is still true:
- deploy did not include commit `5647fab`
- another code path still schedules tenants outside `get_sync_eligible_tenants()`
- tenant rows are misconfigured in a way that makes them appear eligible when they should not be

Next move:
1. confirm deployed image/commit
2. inspect latest failing `tenant_id` values in `sync_job_logs`
3. compare those tenant rows in `tenants`
4. file a second-stage issue with the exact remaining path

### Case B — bogus tenant failures are gone, but sync is still failing

Good. Different fire now.

Common likely next buckets:
- missing RBAC on real subscriptions
- Cost Management API access denied (`403`)
- Graph permission issues for identity sync
- stale scheduler/running job state
- tenant-specific consent drift

In that case, capture the new dominant signature and file a narrower bug.

---

## Suggested handoff note

```text
Post-deploy verification for 5647fab completed.
- costs last_success_at: <timestamp>
- active alerts before/after: <n> -> <n>
- bogus tenant auth failures: gone / still present
- remaining dominant failure signature: <signature or none>
- follow-up issue: <issue id if needed>
```

---

## Related references

- `docs/OPERATIONAL_RUNBOOK.md`
- `docs/archive/ajp1-investigation-report.md`
- `docs/runbooks/enable-secret-fallback.md`
- issue `azure-governance-platform-tbvs`
- issue `azure-governance-platform-0gz3`

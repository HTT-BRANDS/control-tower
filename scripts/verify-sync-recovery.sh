#!/bin/bash
# =============================================================================
# Sync Recovery Verification Helper
# =============================================================================
# Prints copy-paste commands for post-deploy verification of the
# scheduled sync eligibility fix.
#
# This script is intentionally non-destructive. It does NOT modify Azure,
# resolve alerts, or write to the database.
#
# Usage:
#   ./scripts/verify-sync-recovery.sh
#   ./scripts/verify-sync-recovery.sh --api
#   ./scripts/verify-sync-recovery.sh --kql
#   ./scripts/verify-sync-recovery.sh --sql
#   ./scripts/verify-sync-recovery.sh --logs
#   ./scripts/verify-sync-recovery.sh --all
#   uv run python scripts/verify_sync_recovery_report.py --output-md /tmp/sync-recovery.md
# =============================================================================

set -euo pipefail

PROD_URL="${PROD_URL:-https://app-governance-prod.azurewebsites.net}"
PROD_RG="${PROD_RG:-rg-governance-production}"
PROD_APP="${PROD_APP:-app-governance-prod}"
PROD_SQL_SERVER="${PROD_SQL_SERVER:-sql-gov-prod-mylxq53d}"
PROD_SQL_DB="${PROD_SQL_DB:-governance}"
APP_INSIGHTS_APP="${APP_INSIGHTS_APP:-}"
FIX_COMMIT="${FIX_COMMIT:-5647fab}"

SHOW_API=false
SHOW_KQL=false
SHOW_SQL=false
SHOW_LOGS=false

if [[ $# -eq 0 ]]; then
  SHOW_API=true
  SHOW_KQL=true
  SHOW_SQL=true
  SHOW_LOGS=true
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api)
      SHOW_API=true
      shift
      ;;
    --kql)
      SHOW_KQL=true
      shift
      ;;
    --sql)
      SHOW_SQL=true
      shift
      ;;
    --logs)
      SHOW_LOGS=true
      shift
      ;;
    --all)
      SHOW_API=true
      SHOW_KQL=true
      SHOW_SQL=true
      SHOW_LOGS=true
      shift
      ;;
    --help)
      sed -n '2,20p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

section() {
  printf '\n%s\n' "================================================================"
  printf '%s\n' "$1"
  printf '%s\n\n' "================================================================"
}

cat <<EOF
Sync Recovery Verification Helper
- Runbook: docs/runbooks/sync-recovery-verification.md
- Summary tool: scripts/verify_sync_recovery_report.py
- Fix commit: $FIX_COMMIT
- Prod URL: $PROD_URL
- App: $PROD_APP
- Resource group: $PROD_RG
- SQL: $PROD_SQL_SERVER / $PROD_SQL_DB
EOF

if $SHOW_API; then
  section "API VERIFICATION (requires authenticated Bearer token)"
  cat <<EOF
export BEARER_TOKEN="<paste-admin-token-here>"

curl -s -H "Authorization: Bearer \$BEARER_TOKEN" \
  "$PROD_URL/api/v1/sync/status/health" | jq .

curl -s -H "Authorization: Bearer \$BEARER_TOKEN" \
  "$PROD_URL/api/v1/sync/metrics" | jq .

curl -s -H "Authorization: Bearer \$BEARER_TOKEN" \
  "$PROD_URL/api/v1/sync/metrics?job_type=costs" | jq .

curl -s -H "Authorization: Bearer \$BEARER_TOKEN" \
  "$PROD_URL/api/v1/sync/history?limit=200" | jq .

curl -s -H "Authorization: Bearer \$BEARER_TOKEN" \
  "$PROD_URL/api/v1/sync/history?job_type=costs&limit=200" | jq .

curl -s -H "Authorization: Bearer \$BEARER_TOKEN" \
  "$PROD_URL/api/v1/sync/alerts" | jq .
EOF
fi

if $SHOW_KQL; then
  section "APP INSIGHTS / KQL VERIFICATION"
  cat <<'EOF'
# If you know the App Insights app name/id, set it first:
export APP_INSIGHTS_APP="<app-insights-app-id-or-name>"

# Recent sync trace failures
az monitor app-insights query \
  --app "$APP_INSIGHTS_APP" \
  --analytics-query "traces | where timestamp > ago(24h) | where message has_any ('cost sync', 'compliance sync', 'resource sync', 'identity sync', 'Error processing tenant') | project timestamp, severityLevel, message, operation_Name, cloud_RoleName | order by timestamp desc" \
  -o table

# Old bogus-tenant signatures
az monitor app-insights query \
  --app "$APP_INSIGHTS_APP" \
  --analytics-query "traces | where timestamp > ago(24h) | where message has_any ('invalid_tenant', 'Key Vault credentials not found', 'falling back to settings credentials', 'not configured for per-tenant Key Vault credentials') | project timestamp, severityLevel, message | order by timestamp desc" \
  -o table

# Remaining exception groups
az monitor app-insights query \
  --app "$APP_INSIGHTS_APP" \
  --analytics-query "exceptions | where timestamp > ago(24h) | summarize count() by type, outerMessage | order by count_ desc" \
  -o table
EOF
fi

if $SHOW_SQL; then
  section "SQL VERIFICATION"
  cat <<EOF
# Use sqlcmd, Azure Data Studio, or portal query editor. Example sqlcmd shell:
# sqlcmd -S tcp:$PROD_SQL_SERVER.database.windows.net,1433 -d $PROD_SQL_DB -G -C

-- Recent sync status by job type
SELECT job_type, status, COUNT(*) AS runs
FROM sync_job_logs
WHERE started_at >= DATEADD(day, -1, SYSUTCDATETIME())
GROUP BY job_type, status
ORDER BY job_type, status;

-- Latest runs with dominant error signatures
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

-- Last success / last failure per tenant and job type
SELECT
    job_type,
    tenant_id,
    MAX(CASE WHEN status = 'completed' THEN ended_at END) AS last_success,
    MAX(CASE WHEN status = 'failed' THEN ended_at END) AS last_failure,
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failure_count
FROM sync_job_logs
GROUP BY job_type, tenant_id
ORDER BY job_type, tenant_id;

-- Recent alert signatures
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

-- Alert burn-down summary
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

-- Tenant config sanity check
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
EOF
fi

if $SHOW_LOGS; then
  section "LIVE APP SERVICE LOGS"
  cat <<EOF
az webapp log tail \
  --name "$PROD_APP" \
  --resource-group "$PROD_RG"
EOF
fi

section "OPTIONAL SUMMARY REPORT"
cat <<'EOF'
After exporting API / SQL / KQL results to JSON, summarize them with:

uv run python scripts/verify_sync_recovery_report.py \
  --sync-status-json /path/to/sync_status.json \
  --recent-runs-json /path/to/recent_runs.json \
  --alerts-json /path/to/alerts.json \
  --traces-json /path/to/traces.json \
  --exceptions-json /path/to/exceptions.json \
  --output-json /tmp/sync-recovery-report.json \
  --output-md /tmp/sync-recovery-report.md
EOF

section "PASS / FAIL REMINDER"
cat <<EOF
Recovery is only verified if:
- costs has successful runs after deploy
- bogus tenant auth failures stop appearing
- active alerts trend down from 222
- remaining failures are real tenant/platform issues, not scheduler eligibility bugs

If that is NOT true, keep issue 0gz3 open.
EOF

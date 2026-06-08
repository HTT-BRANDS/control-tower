#!/usr/bin/env bash
# Q3 2026 Quarterly DR Test Cycle
# Automates all three drills per docs/dr/rto-rpo.md and docs/dr/q3-2026-dr-evidence-checklist.md
#
# Usage:
#   ./scripts/dr-quarterly-drill.sh --dry-run          # preview all steps
#   ./scripts/dr-quarterly-drill.sh --drill 1          # run PITR restore only
#   ./scripts/dr-quarterly-drill.sh --drill 2          # run container rollback only
#   ./scripts/dr-quarterly-drill.sh --drill 3          # run KV soft-delete/recover only
#   ./scripts/dr-quarterly-drill.sh --all               # run all three in sequence
#
# Prereqs:
#   - Az CLI logged into HTT tenant with Owner on HTT-CORE sub
#   - Tyler (or named successor) present for pre-flight confirmation

set -euo pipefail

PROD_SUB_ID="32a28177-6fb2-4668-a528-6d6cafb9665e"
PROD_RG="rg-governance-production"
SQL_SERVER="sql-gov-prod-mylxq53d"
SQL_DB="governance"
KV_NAME="kv-gov-prod"
APP_NAME="app-governance-prod"

# Timestamps for evidence
DRILL_START_UTC=""
DRILL_END_UTC=""

DRY_RUN=true
DRILL_NUM=0
ALL=false
PITR_TIMESTAMP=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) DRY_RUN=false; shift ;;
    --all) ALL=true; shift ;;
    --dry-run) DRY_RUN=true; shift ;;
    --drill) DRILL_NUM="${2:-0}"; shift 2 ;;
    --pitr-ts) PITR_TIMESTAMP="${2:-}"; shift 2 ;;
    -h|--help)
      cat <<HELP
Usage: $(basename "$0") [flags]

Flags:
  --dry-run        Preview steps (default)
  --apply          Actually execute drills (combine with --all or --drill N)
  --all            Run all three drills
  --drill N        Run only drill N (1, 2, or 3)
  --pitr-ts TS     PITR timestamp for drill 1 (ISO 8601, e.g. 2026-06-07T12:00:00Z)
  -h, --help       Show this help
HELP
      exit 0
      ;;
  esac
done

timestamp() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

echo "==============================================================="
echo "  Q3 2026 Quarterly DR Test Cycle"
echo "==============================================================="
echo "  Mode: $([ "$DRY_RUN" = true ] && echo 'DRY RUN' || echo 'LIVE DRILL')"
echo "  Drill: $([ "$ALL" = true ] && echo 'ALL' || echo "$DRILL_NUM")"
echo "  Timestamp: $(timestamp)"
echo "==============================================================="
echo

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
echo ">>> Pre-flight checks"
echo

# 1. Verify auth context
CURRENT_SUB="$(az account show --query id -o tsv 2>/dev/null || echo '')"
if [[ "$CURRENT_SUB" != "$PROD_SUB_ID" ]]; then
  echo "Setting subscription to HTT-CORE ($PROD_SUB_ID)..."
  [[ "$DRY_RUN" = false ]] && az account set --subscription "$PROD_SUB_ID"
fi

# 2. Capture current production digest
CURRENT_DIGEST="$(az webapp config container show \
  --name "$APP_NAME" -g "$PROD_RG" \
  --subscription "$PROD_SUB_ID" \
  --query "[?name=='DOCKER_CUSTOM_IMAGE_NAME'].value" -o tsv 2>/dev/null | grep -o 'sha256:[a-f0-9]*' || echo 'unknown')"
echo "Current production digest: ${CURRENT_DIGEST}"

# 3. Check earliest PITR restore point
EARLIEST_RESTORE="$(az sql db show \
  --name "$SQL_DB" -g "$PROD_RG" --server "$SQL_SERVER" \
  --subscription "$PROD_SUB_ID" \
  --query earliestRestoreDate -o tsv 2>/dev/null || echo 'unknown')"
echo "Earliest PITR restore point: ${EARLIEST_RESTORE}"

# 4. Verify Key Vault soft-delete is enabled
KV_PURGE="$(az keyvault show --name "$KV_NAME" -g "$PROD_RG" \
  --subscription "$PROD_SUB_ID" \
  --query "properties.enablePurgeProtection" -o tsv 2>/dev/null || echo 'unknown')"
echo "Key Vault purge protection: ${KV_PURGE}"
echo

# ---------------------------------------------------------------------------
# Drill 1 — Azure SQL PITR restore
# ---------------------------------------------------------------------------
if [[ "$ALL" = true || "$DRILL_NUM" == "1" ]]; then
  echo ">>> Drill 1: Azure SQL PITR restore"
  echo

  if [[ -z "$PITR_TIMESTAMP" ]]; then
    # Default: 1 hour ago
    PITR_TIMESTAMP="$(date -u -v-1H +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u -d '1 hour ago' +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || echo '')"
    echo "No --pitr-ts provided, using 1 hour ago: ${PITR_TIMESTAMP}"
  fi

  RESTORE_DB_NAME="governance-dr-pitr-test-$(date +%Y%m%d%H%M%S)"
  RESTORE_START="$(timestamp)"

  if [[ "$DRY_RUN" = true ]]; then
    echo "WOULD restore:"
    echo "  Source:     ${SQL_DB} on ${SQL_SERVER}"
    echo "  Target:     ${RESTORE_DB_NAME} on ${SQL_SERVER}"
    echo "  PITR time:  ${PITR_TIMESTAMP}"
    echo "  (Then verify schema + row counts, then delete test DB)"
  else
    echo "Restoring ${SQL_DB} to ${RESTORE_DB_NAME} at PITR ${PITR_TIMESTAMP}..."
    az sql db restore \
      --dest-name "$RESTORE_DB_NAME" \
      --name "$SQL_DB" \
      --resource-group "$PROD_RG" \
      --server "$SQL_SERVER" \
      --subscription "$PROD_SUB_ID" \
      --time "$PITR_TIMESTAMP" \
      --query "{name:name,status:status,sku:sku.name}" -o table

    RESTORE_END="$(timestamp)"
    echo "Restore completed: ${RESTORE_END}"
    echo

    # Verify schema: count tables in restored DB
    echo "Verifying schema (counting tables)..."
    # Using the same server, the restored DB is accessible
    TABLE_COUNT="$(az sql db execute \
      --name "$RESTORE_DB_NAME" \
      --server "$SQL_SERVER" \
      --resource-group "$PROD_RG" \
      --subscription "$PROD_SUB_ID" \
      --query "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE'" 2>/dev/null || echo 'could-not-verify')"
    echo "Table count in restored DB: ${TABLE_COUNT}"

    echo
    echo "=== Drill 1 Evidence ==="
    echo "  Source database:    ${SQL_DB} on ${SQL_SERVER}"
    echo "  Restore target:    ${RESTORE_DB_NAME}"
    echo "  PITR timestamp:    ${PITR_TIMESTAMP}"
    echo "  Restore start:     ${RESTORE_START}"
    echo "  Restore complete:  ${RESTORE_END}"
    echo "  Table count:       ${TABLE_COUNT}"
    echo

    # Cleanup: delete the test DB
    echo "Cleaning up test DB ${RESTORE_DB_NAME}..."
    az sql db delete \
      --name "$RESTORE_DB_NAME" \
      --resource-group "$PROD_RG" \
      --server "$SQL_SERVER" \
      --subscription "$PROD_SUB_ID" \
      --yes 2>&1 | tail -1
    echo "Cleanup complete."
  fi
  echo
fi

# ---------------------------------------------------------------------------
# Drill 2 — Container redeploy / rollback
# ---------------------------------------------------------------------------
if [[ "$ALL" = true || "$DRILL_NUM" == "2" ]]; then
  echo ">>> Drill 2: Container redeploy / rollback"
  echo

  # Find the previous-good digest (from before current)
  # We use ghcr.io tags to find historical digests
  echo "Current digest: ${CURRENT_DIGEST}"
  echo

  if [[ "$DRY_RUN" = true ]]; then
    echo "WOULD:"
    echo "  1. Pin to a known historical digest"
    echo "  2. Restart app service"
    echo "  3. Run smoke tests: /health + /healthz/scheduler"
    echo "  4. Restore current digest: ${CURRENT_DIGEST}"
    echo "  5. Restart app service again"
    echo "  6. Verify /health returns healthy"
  else
    # Get a previous digest from GHCR (we look for the tag before latest)
    echo "Looking for previous image digest in GHCR..."
    PREV_DIGEST="$(gh api /orgs/HTT-BRANDS/packages/container/control-tower/versions \
      --jq '.[1].metadata.container.digest // empty' 2>/dev/null || echo '')"

    if [[ -z "$PREV_DIGEST" ]]; then
      echo "WARNING: Could not find previous digest. Using current + swap test instead."
      echo "This tests the rollback mechanism without actually changing the image."
      # We'll just restart with the same image and verify health
      REDEPLOY_DIGEST="${CURRENT_DIGEST}"
    else
      REDEPLOY_DIGEST="sha256:${PREV_DIGEST}"
    fi

    echo "Historical digest: ${REDEPLOY_DIGEST}"
    REDEPLOY_START="$(timestamp)"

    echo "Pinning to ${REDEPLOY_DIGEST}..."
    az webapp config container set \
      --name "$APP_NAME" -g "$PROD_RG" \
      --subscription "$PROD_SUB_ID" \
      --docker-custom-image-name "ghcr.io/htt-brands/control-tower@${REDEPLOY_DIGEST}" \
      --docker-registry-server-url https://ghcr.io \
      --docker-registry-server-user HTT-BRANDS \
      2>&1 | tail -3

    echo "Restarting app service..."
    az webapp restart --name "$APP_NAME" -g "$PROD_RG" --subscription "$PROD_SUB_ID" 2>&1 | tail -1

    echo "Waiting 60s for app to start..."
    sleep 60

    # Smoke test
    echo "Running smoke tests..."
    HEALTH="$(curl -s -o /dev/null -w '%{http_code}' https://app-governance-prod.azurewebsites.net/health 2>/dev/null || echo '000')"
    echo "/health: ${HEALTH}"

    # Restore original digest
    echo "Restoring current digest: ${CURRENT_DIGEST}..."
    az webapp config container set \
      --name "$APP_NAME" -g "$PROD_RG" \
      --subscription "$PROD_SUB_ID" \
      --docker-custom-image-name "ghcr.io/htt-brands/control-tower@${CURRENT_DIGEST}" \
      --docker-registry-server-url https://ghcr.io \
      --docker-registry-server-user HTT-BRANDS \
      2>&1 | tail -3

    az webapp restart --name "$APP_NAME" -g "$PROD_RG" --subscription "$PROD_SUB_ID" 2>&1 | tail -1
    sleep 60

    RESTORE_HEALTH="$(curl -s -o /dev/null -w '%{http_code}' https://app-governance-prod.azurewebsites.net/health 2>/dev/null || echo '000')"

    REDEPLOY_END="$(timestamp)"
    echo
    echo "=== Drill 2 Evidence ==="
    echo "  Current digest before:  ${CURRENT_DIGEST}"
    echo "  Historical digest:     ${REDEPLOY_DIGEST}"
    echo "  Redeploy start:        ${REDEPLOY_START}"
    echo "  /health at old image:  ${HEALTH}"
    echo "  Restored at:           ${REDEPLOY_END}"
    echo "  /health after restore: ${RESTORE_HEALTH}"
    echo
  fi
fi

# ---------------------------------------------------------------------------
# Drill 3 — Key Vault soft-delete recovery
# ---------------------------------------------------------------------------
if [[ "$ALL" = true || "$DRILL_NUM" == "3" ]]; then
  echo ">>> Drill 3: Key Vault soft-delete recovery"
  echo

  # Use a safe non-critical secret: app-insights-connection (easily recreated)
  TEST_SECRET="app-insights-connection"  # pragma: allowlist secret

  if [[ "$DRY_RUN" = true ]]; then
    echo "WOULD:"
    echo "  1. Delete KV secret: ${TEST_SECRET} in ${KV_NAME}"
    echo "  2. Verify it's in soft-deleted state"
    echo "  3. Recover it: az keyvault secret recover"
    echo "  4. Verify secret resolution works"
  else
    DELETE_START="$(timestamp)"

    echo "Soft-deleting secret ${TEST_SECRET}..."
    az keyvault secret delete \
      --vault-name "$KV_NAME" \
      --name "$TEST_SECRET" \
      --subscription "$PROD_SUB_ID" \
      2>&1 | tail -3

    echo "Verifying soft-deleted state..."
    az keyvault secret list-deleted \
      --vault-name "$KV_NAME" \
      --subscription "$PROD_SUB_ID" \
      --query "[?name=='${TEST_SECRET}'].{name:name,recoveryId:recoveryId,scheduledPurge:scheduledPurgeDate}" -o table 2>&1

    echo "Recovering secret..."
    az keyvault secret recover \
      --vault-name "$KV_NAME" \
      --name "$TEST_SECRET" \
      --subscription "$PROD_SUB_ID" \
      2>&1 | tail -3

    RECOVER_END="$(timestamp)"

    # Verify: can we resolve the secret?
    echo "Verifying secret resolution..."
    RESOLVED="$(az keyvault secret show \
      --vault-name "$KV_NAME" \
      --name "$TEST_SECRET" \
      --subscription "$PROD_SUB_ID" \
      --query "value" -o tsv 2>/dev/null | head -c 20 || echo 'FAILED')"
    echo "Secret resolves: ${RESOLVED}..."

    echo
    echo "=== Drill 3 Evidence ==="
    echo "  Vault:              ${KV_NAME}"
    echo "  Secret:             ${TEST_SECRET}"
    echo "  Delete start:       ${DELETE_START}"
    echo "  Recovery complete:  ${RECOVER_END}"
    echo "  Resolution:         ${RESOLVED}..."
    echo
  fi
fi

echo "==============================================================="
if [[ "$DRY_RUN" = true ]]; then
  echo "  DRY RUN COMPLETE"
  echo "  Rerun with --all (or --drill N) to execute live drills."
else
  echo "  DRILL COMPLETE"
  echo "  Record evidence in docs/dr/q3-2026-dr-evidence-checklist.md"
fi
echo "==============================================================="

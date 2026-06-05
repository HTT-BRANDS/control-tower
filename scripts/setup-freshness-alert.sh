#!/usr/bin/env bash
# =============================================================================
# setup-freshness-alert.sh -- ct-vuv
# =============================================================================
#
# Wires the "data is silently stale" alarm that ct-cne proved we were missing.
# Two Application Insights *standard availability tests* with content matching,
# each backed by a metric alert that routes to the governance-alerts action group.
#
#   1. data-freshness -- GET /healthz/data       must contain "any_stale":false
#   2. scheduler-live  -- GET /healthz/scheduler  must contain "running":true
#
# When the core tenants go stale (or the scheduler stalls), the response body
# flips and the content match fails -> test goes unhealthy -> metric alert
# fires -> ops gets paged. This is the permanent fix for the "invisible stall"
# half of ct-cne / ct-ar3.
#
# PREREQUISITES:
#   * az CLI authenticated to the HTT-CORE subscription
#   * Python 3.10+ with azure-identity, azure-mgmt-applicationinsights,
#     and azure-mgmt-monitor installed (the script uses `uv run` to handle this)
#   * The governance-alerts action group already exists
#
# USAGE:
#   ./scripts/setup-freshness-alert.sh                # uses defaults below
#   APP_INSIGHTS=my-ai ./scripts/setup-freshness-alert.sh
#
# WHY PYTHON SDK, NOT az CLI?
#   The az CLI's `az monitor app-insights web-test create` does NOT support
#   --content-match for standard tests (confirmed across az CLI v2.63+).
#   The Azure Python SDK (azure-mgmt-applicationinsights) properly supports
#   WebTestPropertiesRequest + WebTestPropertiesValidationRules with
#   ContentValidation.ContentMatch -- that's what this script uses.
# =============================================================================
set -euo pipefail

# -- Config -------------------------------------------------------------------
SUBSCRIPTION="${SUBSCRIPTION:-HTT-CORE}"
RESOURCE_GROUP="${RESOURCE_GROUP:-rg-governance-production}"
ACTION_GROUP="${ACTION_GROUP:-governance-alerts}"
APP_INSIGHTS="${APP_INSIGHTS:-governance-appinsights}"
BASE_URL="${BASE_URL:-https://app-governance-prod.azurewebsites.net}"
# Multi-region so a single-region blip doesn't page.
TEST_LOCATIONS="${TEST_LOCATIONS:-us-tx-sn1-azr,us-il-ch1-azr,us-ca-sjc-azr}"
FREQUENCY="${FREQUENCY:-300}"   # seconds between probes (300 = 5 min)
# scheduler-live is disabled by default until PR #102 deploys /healthz/scheduler
ENABLE_SCHEDULER_TEST="${ENABLE_SCHEDULER_TEST:-false}"

if [ -t 1 ]; then
    RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'; NC=$'\033[0m'
else
    RED=""; GREEN=""; YELLOW=""; NC=""
fi

echo -e "${YELLOW}->${NC} Setting subscription to $SUBSCRIPTION..."
az account set --subscription "$SUBSCRIPTION"

AI_ID=$(az monitor app-insights component show \
    --app "$APP_INSIGHTS" --resource-group "$RESOURCE_GROUP" \
    --query id -o tsv 2>/dev/null || true)
if [ -z "$AI_ID" ]; then
    echo -e "${RED}x Could not find App Insights '$APP_INSIGHTS' in '$RESOURCE_GROUP'.${NC}"
    echo "  Set the right name:  APP_INSIGHTS=<name> $0"
    exit 1
fi
AG_ID=$(az monitor action-group show \
    --name "$ACTION_GROUP" --resource-group "$RESOURCE_GROUP" --query id -o tsv)

echo -e "${YELLOW}->${NC} Creating webtests + alerts via Azure Python SDK..."
echo "  (The az CLI doesn't support --content-match for standard tests)"

# -- Generate the Python deploy script and run it with uv ----------------------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
uv run --quiet python3 "$SCRIPT_DIR/_deploy_webtests.py" \
    --subscription-id "$(az account show --query id -o tsv)" \
    --resource-group "$RESOURCE_GROUP" \
    --app-insights-id "$AI_ID" \
    --action-group-id "$AG_ID" \
    --base-url "$BASE_URL" \
    --locations "$TEST_LOCATIONS" \
    --frequency "$FREQUENCY" \
    --enable-scheduler "$ENABLE_SCHEDULER_TEST"

echo ""
echo -e "${GREEN}+ Freshness alerting wired (webtests + metric alerts).${NC}"
echo ""
echo "Verify:  az resource list -g $RESOURCE_GROUP --resource-type Microsoft.Insights/webtests --query '[].name' -o tsv"
echo "         az monitor metrics alert list -g $RESOURCE_GROUP -o table"
echo ""
echo "Test: wait 5 min then check AI -> Availability in the portal."
echo "  The data-freshness test should show 'Passed' when any_stale:false."
echo "  If it shows 'Failed', that means /healthz/data returned any_stale:true."

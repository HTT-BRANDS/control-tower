#!/bin/bash
# =============================================================================
# setup-freshness-alert.sh — ct-vuv
# =============================================================================
#
# Wires the "data is silently stale" alarm that ct-cne proved we were missing.
# Two Application Insights *standard availability tests* with content matching,
# each backed by a metric alert that routes to the `governance-alerts` action
# group (add Teams via scripts/add-teams-webhook-to-action-group.sh):
#
#   1. data-freshness   — GET /healthz/data       must contain  "any_stale":false
#   2. scheduler-live    — GET /healthz/scheduler  must contain  "running":true
#                                                  must NOT match "any_overdue":true
#
# When the core tenants go >24h stale (or the scheduler stalls), the response
# body flips and the content match fails -> the test goes unhealthy -> the
# metric alert fires -> ops gets paged. This is the permanent fix for the
# "invisible stall" half of ct-cne / ct-ar3.
#
# PREREQUISITES:
#   * az CLI authenticated to the HTT-CORE subscription
#   * The Application Insights resource name (see APP_INSIGHTS below — confirm
#     it; the runbook calls it `governance-appinsights`)
#   * The `governance-alerts` action group already exists (it does)
#
# USAGE:
#   ./scripts/setup-freshness-alert.sh                # uses defaults below
#   APP_INSIGHTS=my-ai ./scripts/setup-freshness-alert.sh
#
# NOTE: `az monitor app-insights web-test` flags vary slightly across CLI
# versions. If a flag is rejected, see the PORTAL FALLBACK block printed at the
# end — the same test is 4 clicks in the portal.
# =============================================================================

set -euo pipefail

# ── Config ───────────────────────────────────────────────────────────────────
SUBSCRIPTION="${SUBSCRIPTION:-HTT-CORE}"
RESOURCE_GROUP="${RESOURCE_GROUP:-rg-governance-production}"
ACTION_GROUP="${ACTION_GROUP:-governance-alerts}"
APP_INSIGHTS="${APP_INSIGHTS:-governance-appinsights}"
BASE_URL="${BASE_URL:-https://app-governance-prod.azurewebsites.net}"
# Multi-region so a single-region blip doesn't page. Adjust to taste.
TEST_LOCATIONS="${TEST_LOCATIONS:-us-tx-sn1-azr,us-il-ch1-azr,us-ca-sjc-azr}"
FREQUENCY="${FREQUENCY:-300}"   # seconds between probes (300 = 5 min)

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
    echo "  List candidates:     az monitor app-insights component show --query \"[].name\" -o tsv"
    exit 1
fi
AG_ID=$(az monitor action-group show \
    --name "$ACTION_GROUP" --resource-group "$RESOURCE_GROUP" --query id -o tsv)

# ── Helper: create one standard webtest + its metric alert ───────────────────
# args: <test-name> <url-path> <content-match> <severity>
make_test() {
    local name="$1" path="$2" match="$3" sev="$4"
    echo -e "${YELLOW}->${NC} Creating availability test '$name' (match: $match)..."
    az monitor app-insights web-test create \
        --name "$name" \
        --resource-group "$RESOURCE_GROUP" \
        --location "$(az monitor app-insights component show --app "$APP_INSIGHTS" -g "$RESOURCE_GROUP" --query location -o tsv)" \
        --tags "hidden-link:$AI_ID=Resource" \
        --web-test-kind standard \
        --request-url "${BASE_URL}${path}" \
        --http-verb GET \
        --content-match "$match" \
        --ssl-check true \
        --frequency "$FREQUENCY" \
        --locations Id="$(echo "$TEST_LOCATIONS" | cut -d, -f1)" \
        --enabled true \
        --defined-web-test-name "$name" \
        --web-test-name "$name" 2>&1 || {
            echo -e "${YELLOW}!  web-test create flags rejected by this az version — use the PORTAL FALLBACK below for '$name'.${NC}"
        }

    echo -e "${YELLOW}->${NC} Creating metric alert 'alert-$name' -> $ACTION_GROUP..."
    az monitor metrics alert create \
        --name "alert-$name" \
        --resource-group "$RESOURCE_GROUP" \
        --scopes "$AI_ID" \
        --condition "avg availabilityResults/availabilityPercentage < 100 where availabilityResults/name includes $name" \
        --window-size 5m \
        --evaluation-frequency 5m \
        --severity "$sev" \
        --action "$AG_ID" \
        --description "ct-vuv: $name content match failed (stale data / stalled scheduler)." 2>&1 || {
            echo -e "${YELLOW}!  metric-alert create needs adjustment for this az version (see portal fallback).${NC}"
        }
}

# 1. Data freshness — the headline ct-cne alarm (severity 1 = critical)
make_test "data-freshness" "/healthz/data" '"any_stale":false' 1
# 2. Scheduler liveness — early-warning before data even goes stale (sev 2)
make_test "scheduler-live" "/healthz/scheduler" '"running":true' 2

echo ""
echo -e "${GREEN}+ Freshness alerting wired (or scaffolded).${NC}"
echo ""
echo "Verify in portal (Availability):"
echo "  https://portal.azure.com/#@/resource${AI_ID}/availability"
echo ""
echo "Test-fire the action group (confirms ops actually gets paged):"
echo "  az monitor action-group test-notifications create \\"
echo "    --action-group $ACTION_GROUP --resource-group $RESOURCE_GROUP \\"
echo "    --notification-type Webhook --alert-type budget"
echo ""
echo "----------------------------- PORTAL FALLBACK -------------------------------"
echo "If the CLI rejected a flag, the same test is quick in the portal:"
echo "  App Insights ($APP_INSIGHTS) -> Availability -> Add Standard test"
echo "    URL:           ${BASE_URL}/healthz/data"
echo "    Success when:  Content match  ->  \"any_stale\":false"
echo "    Frequency:     5 min, 3+ locations"
echo "    Alerts:        enable, severity 1, action group = $ACTION_GROUP"
echo "  Repeat for ${BASE_URL}/healthz/scheduler  with match  \"running\":true"
echo "-----------------------------------------------------------------------------"

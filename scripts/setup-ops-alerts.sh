#!/bin/bash
# =============================================================================
# setup-ops-alerts.sh — ct-8jt
# =============================================================================
#
# App Service platform alert thresholds (error-rate + latency), routed to the
# `governance-alerts` action group. Companion to scripts/setup-freshness-alert.sh
# (ct-vuv), which covers data freshness + scheduler liveness — and, because
# those are content-match availability tests, also covers AVAILABILITY (they go
# unhealthy when the app is unreachable). Between the two scripts you get the
# three runbook targets:
#
#   * Availability  -> setup-freshness-alert.sh webtests (app unreachable = fail)
#   * Error rate    -> THIS script: Http5xx spike
#   * Latency       -> THIS script: HttpResponseTime (Response Time) high
#
# Thresholds default to the runbook's "Weekly Metrics" targets
# (docs/OPERATIONAL_RUNBOOK.md): Response Time warn at 1s, errors on a 5xx spike.
#
# PREREQUISITES: az CLI authed to HTT-CORE; the `governance-alerts` action group
# exists; the App Service name is correct.
#
# USAGE:
#   ./scripts/setup-ops-alerts.sh
#   APP=app-governance-staging-xnczpwyv RG=rg-governance-staging ./scripts/setup-ops-alerts.sh
# =============================================================================

set -euo pipefail

# ── Config ───────────────────────────────────────────────────────────────────
SUBSCRIPTION="${SUBSCRIPTION:-HTT-CORE}"
RG="${RG:-rg-governance-production}"
APP="${APP:-app-governance-prod}"
ACTION_GROUP="${ACTION_GROUP:-governance-alerts}"
# Thresholds (override via env):
ERR_5XX_COUNT="${ERR_5XX_COUNT:-10}"      # total Http5xx over the window -> alert
LATENCY_SECONDS="${LATENCY_SECONDS:-1}"   # avg Response Time (seconds) -> alert

if [ -t 1 ]; then
    RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'; NC=$'\033[0m'
else
    RED=""; GREEN=""; YELLOW=""; NC=""
fi

echo -e "${YELLOW}->${NC} Setting subscription to $SUBSCRIPTION..."
az account set --subscription "$SUBSCRIPTION"

APP_ID=$(az webapp show --name "$APP" --resource-group "$RG" --query id -o tsv 2>/dev/null || true)
if [ -z "$APP_ID" ]; then
    echo -e "${RED}x Could not find App Service '$APP' in '$RG'.${NC}"
    echo "  Override: APP=<name> RG=<rg> $0"
    exit 1
fi
AG_ID=$(az monitor action-group show --name "$ACTION_GROUP" --resource-group "$RG" --query id -o tsv)

# 1. Error-rate — a spike of server errors (5xx). Sev 2 (major).
echo -e "${YELLOW}->${NC} Creating 'alert-http5xx' (Http5xx total > $ERR_5XX_COUNT / 5m)..."
az monitor metrics alert create \
    --name "alert-http5xx-$APP" \
    --resource-group "$RG" \
    --scopes "$APP_ID" \
    --condition "total Http5xx > $ERR_5XX_COUNT" \
    --window-size 5m \
    --evaluation-frequency 1m \
    --severity 2 \
    --action "$AG_ID" \
    --description "ct-8jt: server-error (5xx) spike on $APP." 2>&1 || \
    echo -e "${YELLOW}!  adjust for your az version (metric name 'Http5xx', namespace Microsoft.Web/sites).${NC}"

# 2. Latency — sustained high Response Time. Sev 2. HttpResponseTime is in SECONDS.
echo -e "${YELLOW}->${NC} Creating 'alert-latency' (avg Response Time > ${LATENCY_SECONDS}s / 15m)..."
az monitor metrics alert create \
    --name "alert-latency-$APP" \
    --resource-group "$RG" \
    --scopes "$APP_ID" \
    --condition "avg HttpResponseTime > $LATENCY_SECONDS" \
    --window-size 15m \
    --evaluation-frequency 5m \
    --severity 2 \
    --action "$AG_ID" \
    --description "ct-8jt: avg Response Time > ${LATENCY_SECONDS}s on $APP (runbook target p95 < 500ms)." 2>&1 || \
    echo -e "${YELLOW}!  if 'HttpResponseTime' is rejected, try metric 'ResponseTime' (units: seconds).${NC}"

echo ""
echo -e "${GREEN}+ Ops alerts wired (or scaffolded).${NC}"
echo ""
echo "Verify:   az monitor metrics alert list -g $RG -o table"
echo "Test the action group reaches ops (Teams):"
echo "  az monitor action-group test-notifications create \\"
echo "    --action-group $ACTION_GROUP --resource-group $RG \\"
echo "    --notification-type Webhook --alert-type budget"
echo ""
echo "NOTE: availability is covered by scripts/setup-freshness-alert.sh (ct-vuv)."
echo "Tune thresholds with env vars, e.g.  LATENCY_SECONDS=2 $0"

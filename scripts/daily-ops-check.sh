#!/bin/bash
# Daily Operations Check - Azure Governance Platform
# Run this every morning (or via cron)

set -e

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║  DAILY OPERATIONS CHECK - $(date +%Y-%m-%d)              ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Configuration
PROD_URL="https://app-governance-prod.azurewebsites.net"
ALERT_EMAIL="admin@httbrands.com"
LOG_FILE="/tmp/daily-ops-$(date +%Y%m%d).log"

# Function to log and display
log() {
    echo "$1" | tee -a $LOG_FILE
}

# 1. Health Check
log "🔍 STEP 1: Health Check"
HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" $PROD_URL/health)
if [ "$HEALTH_STATUS" == "200" ]; then
    log "✅ Health check: PASS (HTTP 200)"
else
    log "❌ Health check: FAIL (HTTP $HEALTH_STATUS)"
    echo "ALERT: Health check failed!" >&2
fi

# 2. Response Time Check
log ""
log "🔍 STEP 2: Response Time"
RESPONSE_TIME=$(curl -s -o /dev/null -w "%{time_total}" $PROD_URL/health)
RESPONSE_MS=$(echo "$RESPONSE_TIME * 1000" | bc)
if (( $(echo "$RESPONSE_MS < 1000" | bc -l) )); then
    log "✅ Response time: ${RESPONSE_MS}ms (Good)"
else
    log "⚠️  Response time: ${RESPONSE_MS}ms (Slow)"
fi

# 3. Check Azure Alerts (via CLI if configured)
log ""
log "🔍 STEP 3: Azure Alerts Status"
if command -v az &> /dev/null; then
    ACTIVE_ALERTS=$(az monitor metrics alert list --resource-group rg-governance-production --query "length(@)" 2>/dev/null || echo "0")
    log "📊 Active alert rules: $ACTIVE_ALERTS"
else
    log "⚠️  Azure CLI not configured - check alerts manually in portal"
fi

# 4. Version Check
log ""
log "🔍 STEP 4: Version Check"
VERSION=$(curl -s $PROD_URL/health | jq -r '.version' 2>/dev/null || echo "unknown")
log "📦 Production version: $VERSION"

# 5. Git Status (local repo)
log ""
log "🔍 STEP 5: Repository Status"
if [ -d ".git" ]; then
    COMMIT=$(git rev-parse --short HEAD)
    BRANCH=$(git branch --show-current)
    log "📁 Repo: $BRANCH @ $COMMIT"
else
    log "⚠️  Not a git repository"
fi

# Summary
log ""
log "═══════════════════════════════════════════════════════════"
log "  DAILY CHECK COMPLETE"
log "═══════════════════════════════════════════════════════════"
log ""
log "Log saved to: $LOG_FILE"
log ""
log "Next steps:"
log "  - Review any ❌ failures above"
log "  - Check Azure Portal for alerts"
log "  - Update operational log if issues found"
log ""

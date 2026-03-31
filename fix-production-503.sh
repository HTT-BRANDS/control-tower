#!/bin/bash
# =============================================================================
# Fix Production 503 Error - Container Registry Authentication
# =============================================================================
# This script fixes the HTTP 503 Service Unavailable error by setting the
# correct GitHub Container Registry (GHCR) authentication credentials.
#
# PREREQUISITE: You must create a GitHub PAT with 'read:packages' scope first!
#   1. Go to: https://github.com/settings/tokens/new
#   2. Select "Classic token"
#   3. Check scope: read:packages
#   4. Generate and copy the token
#
# USAGE:
#   export GHCR_PAT="ghp_xxxxxxxxxxxx"  # Your GitHub PAT
#   ./fix-production-503.sh
# =============================================================================

set -euo pipefail

# Configuration
APP_NAME="app-governance-prod"
RESOURCE_GROUP="rg-governance-production"

# Check if PAT is provided
if [ -z "${GHCR_PAT:-}" ]; then
    echo "❌ ERROR: GHCR_PAT environment variable is not set!"
    echo ""
    echo "Please create a GitHub PAT with 'read:packages' scope:"
    echo "  1. Visit: https://github.com/settings/tokens/new"
    echo "  2. Select 'Classic token'"
    echo "  3. Check: read:packages scope"
    echo "  4. Generate and copy the token"
    echo ""
    echo "Then run:"
    echo "  export GHCR_PAT='ghp_your_token_here'"
    echo "  $0"
    exit 1
fi

echo "🔧 Azure Governance Platform - Production 503 Fix"
echo "===================================================="
echo ""

# Step 1: Update container registry credentialsecho "Step 1/3: Updating container registry credentials..."
az webapp config appsettings set \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --settings \
        DOCKER_REGISTRY_SERVER_USERNAME="token" \
        DOCKER_REGISTRY_SERVER_PASSWORD="$GHCR_PAT"

echo "   ✅ Registry credentials updated"
echo ""

# Step 2: Restart App Service to pull containerecho "Step 2/3: Restarting App Service to pull container..."
az webapp restart \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP"

echo "   ✅ App Service restarted"
echo ""

# Step 3: Wait and verify health
echo "Step 3/3: Waiting for container startup (90 seconds)..."
sleep 90

echo ""
echo "🔍 Verifying deployment health..."
HEALTH_URL="https://${APP_NAME}.azurewebsites.net/health"
MAX_RETRIES=5
RETRY_DELAY=15

for i in $(seq 1 $MAX_RETRIES); do
    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" 2>/dev/null || echo "000")
    
    if [ "$HTTP_STATUS" = "200" ]; then
        echo "   ✅ Health check PASSED (HTTP 200)"
        echo ""
        echo "🎉 SUCCESS! Production deployment is now healthy."
        echo ""
        echo "Verification URL: $HEALTH_URL"
        exit 0
    else
        echo "   ⏳ Attempt $i/$MAX_RETRIES: HTTP $HTTP_STATUS (expected 200)"
        if [ $i -lt $MAX_RETRIES ]; then
            sleep $RETRY_DELAY
        fi
    fi
done

echo ""
echo "⚠️  WARNING: Health check did not return 200 after $MAX_RETRIES attempts."
echo ""
echo "Troubleshooting steps:"
echo "  1. Check if GitHub PAT has 'read:packages' scope"
echo "  2. Verify PAT can access 'htt-brands/azure-governance-platform' package"
echo "  3. Check App Service logs:"
echo "     az webapp log tail --name $APP_NAME --resource-group $RESOURCE_GROUP"
echo ""
echo "Current App Service state:"
az webapp show --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" \
    --query "{state:state,linuxFxVersion:linuxFxVersion}"

exit 1

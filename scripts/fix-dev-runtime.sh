#!/bin/bash
# =============================================================================
# Fix Dev App Service Runtime Configuration
# =============================================================================
# IMMEDIATE FIX for 503 errors caused by Python runtime vs Container mismatch
#
# Problem: App Service configured for PYTHON|3.11 but should use Docker container
# Symptoms: 503 errors, app won't start, "Container didn't respond to HTTP pings"
#
# This script:
#   1. Configures the App Service for container deployment
#   2. Sets the correct container image from GHCR
#   3. Configures registry authentication
#   4. Enables always-on
#   5. Restarts the app service
#
# Usage: ./scripts/fix-dev-runtime.sh
# Prerequisites: Azure CLI logged in with Contributor access
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="app-governance-dev-001"
RESOURCE_GROUP="rg-governance-dev"
CONTAINER_IMAGE="ghcr.io/htt-brands/control-tower:dev"
REGISTRY_URL="https://ghcr.io"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! command -v az &> /dev/null; then
        log_error "Azure CLI not found. Please install: https://aka.ms/installazurecli"
        exit 1
    fi
    
    # Check if logged in
    if ! az account show &> /dev/null; then
        log_error "Not logged into Azure. Run: az login"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Get current configuration for diagnostic
check_current_config() {
    log_info "Checking current App Service configuration..."
    
    echo ""
    echo "=== CURRENT CONFIGURATION ==="
    echo ""
    
    # Show current site config
    log_info "Current linuxFxVersion:"
    az webapp config show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "linuxFxVersion" \
        --output tsv 2>/dev/null || echo "N/A"
    
    log_info "Current kind:"
    az webapp show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "kind" \
        --output tsv 2>/dev/null || echo "N/A"
    
    log_info "Current container settings:"
    az webapp config container show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "[?name=='DOCKER_CUSTOM_IMAGE_NAME'].value" \
        --output tsv 2>/dev/null || echo "N/A"
    
    echo ""
    log_info "App Service State:"
    az webapp show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "{state: state, availabilityState: availabilityState, defaultHostName: defaultHostName}" \
        --output table 2>/dev/null || echo "Could not retrieve state"
    echo ""
}

# Fix the runtime configuration
fix_runtime_config() {
    log_info "Fixing runtime configuration..."
    
    # Step 1: Update to container-based deployment
    log_info "Step 1/5: Configuring for container deployment..."
    az webapp config set \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --linux-fx-version "DOCKER|$CONTAINER_IMAGE" \
        --output none
    log_success "Container runtime configured"
    
    # Step 2: Set container image
    log_info "Step 2/5: Setting container image..."
    az webapp config container set \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --docker-custom-image-name "$CONTAINER_IMAGE" \
        --docker-registry-server-url "$REGISTRY_URL" \
        --output none
    log_success "Container image configured: $CONTAINER_IMAGE"
    
    # Step 3: Enable always on (critical for containers)
    log_info "Step 3/5: Enabling Always On..."
    az webapp config set \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --always-on true \
        --output none
    log_success "Always On enabled"
    
    # Step 4: Configure health check
    log_info "Step 4/5: Configuring health check..."
    az webapp config set \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --health-check-path "/health" \
        --output none
    log_success "Health check configured"
    
    # Step 5: Restart app service
    log_info "Step 5/5: Restarting App Service..."
    az webapp restart \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP"
    log_success "App Service restarted"
}

# Configure managed identity for GHCR access (optional but recommended)
configure_managed_identity() {
    log_info "Configuring managed identity..."
    
    # Assign system-assigned identity if not already assigned
    az webapp identity assign \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --output none 2>/dev/null || log_warn "Identity may already be assigned"
    
    log_success "Managed identity configured"
}

# Verify the fix
verify_fix() {
    log_info "Verifying configuration fix..."
    
    echo ""
    echo "=== NEW CONFIGURATION ==="
    echo ""
    
    # Show new site config
    log_info "New linuxFxVersion:"
    az webapp config show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "linuxFxVersion" \
        --output tsv
    
    log_info "New container settings:"
    az webapp config container show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --output table 2>/dev/null || echo "Container settings not yet applied"
    
    echo ""
    log_info "Waiting for app to start (this may take 2-3 minutes)..."
    sleep 30
    
    # Get the URL
    APP_URL=$(az webapp show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "defaultHostName" \
        --output tsv)
    
    log_info "Testing health endpoint: https://${APP_URL}/health"
    
    # Test health endpoint with retries
    for i in {1..6}; do
        if curl -sf "https://${APP_URL}/health" &>/dev/null; then
            echo ""
            log_success "✅ Health check PASSED!"
            echo ""
            echo "=== DEPLOYMENT SUCCESSFUL ==="
            echo ""
            echo "App URL: https://${APP_URL}"
            echo "Health:  https://${APP_URL}/health"
            echo "API:     https://${APP_URL}/api/v1/status"
            echo ""
            return 0
        fi
        
        log_warn "Health check attempt $i/6 failed, retrying in 30s..."
        sleep 30
    done
    
    echo ""
    log_warn "⚠️  Health check did not pass within expected time"
    echo ""
    echo "The configuration has been updated, but the app may still be starting."
    echo "Check Azure Portal for deployment logs:"
    echo "https://portal.azure.com/#@/resource/subscriptions/$(az account show --query id -o tsv)/resourceGroups/${RESOURCE_GROUP}/providers/Microsoft.Web/sites/${APP_NAME}/containerLogs"
    echo ""
    return 1
}

# Print summary
print_summary() {
    echo ""
    echo "=========================================="
    echo "    FIX COMPLETE - SUMMARY"
    echo "=========================================="
    echo ""
    echo "Resource Group:  $RESOURCE_GROUP"
    echo "App Service:     $APP_NAME"
    echo "Container Image: $CONTAINER_IMAGE"
    echo ""
    echo "Commands for manual verification:"
    echo ""
    echo "  # Check configuration"
    echo "  az webapp config show --name $APP_NAME --resource-group $RESOURCE_GROUP --query linuxFxVersion"
    echo ""
    echo "  # View logs"
    echo "  az webapp log tail --name $APP_NAME --resource-group $RESOURCE_GROUP"
    echo ""
    echo "  # Check deployment status"
    echo "  az webapp show --name $APP_NAME --resource-group $RESOURCE_GROUP --query '{state: state, availabilityState: availabilityState}'"
    echo ""
}

# Main execution
main() {
    echo "=========================================="
    echo "    FIX DEV RUNTIME CONFIGURATION"
    echo "=========================================="
    echo ""
    echo "This script will fix the 503 error by converting"
    echo "the App Service from Python runtime to Container runtime."
    echo ""
    
    check_prerequisites
    check_current_config
    
    read -p "Continue with the fix? [y/N]: " -n 1 -r
    echo ""
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Aborted by user"
        exit 0
    fi
    
    fix_runtime_config
    configure_managed_identity
    verify_fix
    print_summary
}

# Run main
main "$@"

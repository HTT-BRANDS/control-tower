#!/bin/bash
# =============================================================================
# Check App Service Logs
# =============================================================================
# Stream logs from the Azure App Service for troubleshooting.
# Shows container logs, application logs, and deployment logs.
#
# Usage: ./scripts/check-logs.sh [options]
#
# Options:
#   --deployment    Show deployment logs only
#   --container     Show container logs only (default)
#   --all           Show all log streams
#   --lines N       Show last N lines (default: tail)
#   --help          Show this help message
#
# Press Ctrl+C to stop streaming
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="app-governance-dev-001"
RESOURCE_GROUP="rg-governance-dev"

# Default options
LOG_TYPE="container"
LINES=""

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

show_help() {
    cat << EOF
Azure Governance Platform - Log Checker

Usage: ./scripts/check-logs.sh [options]

Options:
  --deployment    Show deployment logs only
  --container     Show container logs only (default)
  --all           Show all log streams
  --lines N       Show last N lines instead of tailing
  --help          Show this help message

Examples:
  ./scripts/check-logs.sh                    # Stream container logs
  ./scripts/check-logs.sh --deployment       # Show deployment logs
  ./scripts/check-logs.sh --lines 100        # Show last 100 lines

Press Ctrl+C to stop streaming
EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --deployment)
            LOG_TYPE="deployment"
            shift
            ;;
        --container)
            LOG_TYPE="container"
            shift
            ;;
        --all)
            LOG_TYPE="all"
            shift
            ;;
        --lines)
            if [[ -n "${2:-}" && "$2" =~ ^[0-9]+$ ]]; then
                LINES="$2"
                shift 2
            else
                log_error "--lines requires a numeric argument"
                exit 1
            fi
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Check prerequisites
check_prerequisites() {
    if ! command -v az &> /dev/null; then
        log_error "Azure CLI not found. Please install: https://aka.ms/installazurecli"
        exit 1
    fi
    
    if ! az account show &> /dev/null; then
        log_error "Not logged into Azure. Run: az login"
        exit 1
    fi
}

# Get app info
show_app_info() {
    log_info "App Service: ${CYAN}$APP_NAME${NC}"
    log_info "Resource Group: ${CYAN}$RESOURCE_GROUP${NC}"
    
    # Get app state
    local state
    state=$(az webapp show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query "state" \
        --output tsv 2>/dev/null || echo "unknown")
    
    if [ "$state" == "Running" ]; then
        log_info "App State: ${GREEN}Running${NC}"
    else
        log_warn "App State: ${YELLOW}$state${NC}"
    fi
    
    echo ""
}

# Show recent deployment logs
show_deployment_logs() {
    log_info "Fetching recent deployment logs..."
    echo ""
    
    az webapp log deployment show \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --output table 2>/dev/null || {
        log_warn "No deployment logs available or deployment in progress"
    }
    
    echo ""
    log_info "To see live deployment logs, use: az webapp log deployment show --name $APP_NAME --resource-group $RESOURCE_GROUP"
}

# Stream container logs
stream_container_logs() {
    log_info "Streaming container logs..."
    log_info "Press ${CYAN}Ctrl+C${NC} to stop"
    echo ""
    
    if [ -n "$LINES" ]; then
        # Show specific number of lines
        az webapp log tail \
            --name "$APP_NAME" \
            --resource-group "$RESOURCE_GROUP" \
            --lines "$LINES" 2>/dev/null || {
            log_error "Failed to retrieve logs. Is the app service running?"
            exit 1
        }
    else
        # Tail logs continuously
        az webapp log tail \
            --name "$APP_NAME" \
            --resource-group "$RESOURCE_GROUP" 2>/dev/null || {
            log_error "Log streaming ended or failed"
            exit 1
        }
    fi
}

# Show log locations in portal
show_portal_links() {
    echo ""
    log_info "View logs in Azure Portal:"
    
    local subscription_id
    subscription_id=$(az account show --query id -o tsv)
    
    echo ""
    echo "  Container Logs:"
    echo "  https://portal.azure.com/#@/resource/subscriptions/$subscription_id/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Web/sites/$APP_NAME/containerLogs"
    echo ""
    echo "  Log Stream:"
    echo "  https://portal.azure.com/#@/resource/subscriptions/$subscription_id/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Web/sites/$APP_NAME/logStream"
    echo ""
    echo "  Deployment Center:"
    echo "  https://portal.azure.com/#@/resource/subscriptions/$subscription_id/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Web/sites/$APP_NAME/vstscd"
    echo ""
}

# Main execution
main() {
    echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║         Azure Governance Platform - Log Checker            ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    check_prerequisites
    show_app_info
    
    case $LOG_TYPE in
        deployment)
            show_deployment_logs
            show_portal_links
            ;;
        container)
            stream_container_logs
            ;;
        all)
            show_deployment_logs
            echo ""
            stream_container_logs
            ;;
    esac
}

# Run main
main "$@"

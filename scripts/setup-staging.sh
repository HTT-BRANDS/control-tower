#!/bin/bash
# =============================================================================
# Setup Staging Environment
# =============================================================================
# Deploys staging infrastructure and configures the GitHub environment.
# Run this while dev is being fixed to prepare staging in parallel.
#
# Prerequisites:
#   - Azure CLI installed and logged in
#   - GitHub CLI (gh) installed and authenticated
#   - Owner or Admin access to the GitHub repository
#   - Contributor access to Azure subscription
#
# Usage: ./scripts/setup-staging.sh
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
RESOURCE_GROUP="rg-governance-staging"
LOCATION="eastus"
TEMPLATE_FILE="infrastructure/main.bicep"
PARAMETERS_FILE="infrastructure/parameters.staging.json"
ENVIRONMENT_NAME="staging"

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

log_step() {
    echo ""
    echo -e "${CYAN}▶ Step $1: $2${NC}"
    echo "────────────────────────────────────────────────────────────"
}

# Check prerequisites
check_prerequisites() {
    log_step "0" "Checking Prerequisites"
    
    # Check Azure CLI
    if ! command -v az &> /dev/null; then
        log_error "Azure CLI not found. Please install: https://aka.ms/installazurecli"
        exit 1
    fi
    log_success "Azure CLI found"
    
    # Check Azure login
    if ! az account show &> /dev/null; then
        log_error "Not logged into Azure. Run: az login"
        exit 1
    fi
    local subscription
    subscription=$(az account show --query name -o tsv)
    log_success "Logged into Azure (Subscription: $subscription)"
    
    # Check GitHub CLI
    if ! command -v gh &> /dev/null; then
        log_error "GitHub CLI (gh) not found. Please install: https://cli.github.com"
        exit 1
    fi
    log_success "GitHub CLI found"
    
    # Check GitHub auth
    if ! gh auth status &> /dev/null; then
        log_error "Not authenticated with GitHub. Run: gh auth login"
        exit 1
    fi
    log_success "Authenticated with GitHub"
    
    # Check required files
    if [ ! -f "$TEMPLATE_FILE" ]; then
        log_error "Bicep template not found: $TEMPLATE_FILE"
        exit 1
    fi
    log_success "Found Bicep template: $TEMPLATE_FILE"
    
    if [ ! -f "$PARAMETERS_FILE" ]; then
        log_error "Parameters file not found: $PARAMETERS_FILE"
        exit 1
    fi
    log_success "Found parameters file: $PARAMETERS_FILE"
}

# Create resource group if it doesn't exist
create_resource_group() {
    log_step "1" "Creating Resource Group"
    
    if az group show --name "$RESOURCE_GROUP" &> /dev/null; then
        log_warn "Resource group already exists: $RESOURCE_GROUP"
    else
        log_info "Creating resource group: $RESOURCE_GROUP in $LOCATION"
        az group create \
            --name "$RESOURCE_GROUP" \
            --location "$LOCATION" \
            --tags \
                Environment=staging \
                Application="Azure Governance Platform" \
                ManagedBy=Bicep
        log_success "Resource group created"
    fi
}

# Deploy infrastructure
deploy_infrastructure() {
    log_step "2" "Deploying Infrastructure"
    
    log_info "Starting Bicep deployment..."
    log_info "This may take 5-10 minutes..."
    echo ""
    
    # Deploy with progress
    az deployment group create \
        --resource-group "$RESOURCE_GROUP" \
        --template-file "$TEMPLATE_FILE" \
        --parameters "$PARAMETERS_FILE" \
        --name "staging-deploy-$(date +%Y%m%d-%H%M%S)" \
        --output table || {
        log_error "Infrastructure deployment failed"
        exit 1
    }
    
    log_success "Infrastructure deployed successfully"
}

# Get deployment outputs
get_deployment_outputs() {
    log_step "3" "Retrieving Deployment Outputs"
    
    log_info "Getting deployment outputs..."
    
    APP_SERVICE_NAME=$(az deployment group show \
        --resource-group "$RESOURCE_GROUP" \
        --name "$(az deployment group list --resource-group "$RESOURCE_GROUP" --query '[0].name' -o tsv)" \
        --query "properties.outputs.appServiceName.value" \
        --output tsv 2>/dev/null || echo "")
    
    APP_SERVICE_URL=$(az deployment group show \
        --resource-group "$RESOURCE_GROUP" \
        --name "$(az deployment group list --resource-group "$RESOURCE_GROUP" --query '[0].name' -o tsv)" \
        --query "properties.outputs.appServiceUrl.value" \
        --output tsv 2>/dev/null || echo "")
    
    KEY_VAULT_NAME=$(az deployment group show \
        --resource-group "$RESOURCE_GROUP" \
        --name "$(az deployment group list --resource-group "$RESOURCE_GROUP" --query '[0].name' -o tsv)" \
        --query "properties.outputs.keyVaultName.value" \
        --output tsv 2>/dev/null || echo "")
    
    log_success "Deployment outputs retrieved"
    
    echo ""
    echo -e "${CYAN}Deployed Resources:${NC}"
    echo "  App Service:    ${APP_SERVICE_NAME:-N/A}"
    echo "  URL:            ${APP_SERVICE_URL:-N/A}"
    echo "  Key Vault:      ${KEY_VAULT_NAME:-N/A}"
    echo ""
}

# Create GitHub environment
create_github_environment() {
    log_step "4" "Creating GitHub Environment"
    
    local repo
    repo=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "")
    
    if [ -z "$repo" ]; then
        log_error "Could not determine repository. Are you in a git repository?"
        exit 1
    fi
    
    log_info "Repository: $repo"
    
    # Check if environment already exists
    if gh api "repos/$repo/environments/$ENVIRONMENT_NAME" &> /dev/null; then
        log_warn "GitHub environment already exists: $ENVIRONMENT_NAME"
    else
        log_info "Creating GitHub environment: $ENVIRONMENT_NAME"
        
        # Create environment with protection rules
        gh api "repos/$repo/environments" \
            --method POST \
            --field environment_name="$ENVIRONMENT_NAME" \
            --field "wait_timer=0" \
            --field "prevent_self_review=false" \
            --silent || {
            log_warn "Environment creation returned non-200 (may already exist)"
        }
        
        log_success "GitHub environment created"
    fi
    
    # Set environment URL
    if [ -n "$APP_SERVICE_URL" ]; then
        log_info "Setting environment URL..."
        gh api "repos/$repo/environments/$ENVIRONMENT_NAME" \
            --method PATCH \
            --field "deployment_protection_rules[]" \
            --silent || true
    fi
}

# Configure deployment protection (optional)
configure_deployment_protection() {
    log_step "5" "Configuring Deployment Protection (Optional)"
    
    log_info "Note: Configure required reviewers in GitHub UI if needed"
    log_info "Visit: https://github.com/$(gh repo view --json nameWithOwner -q .nameWithOwner)/settings/environments"
    
    echo ""
    echo -e "${YELLOW}Recommended protection rules for staging:${NC}"
    echo "  • Require 1 reviewer for deployments"
    echo "  • Wait timer: 0 minutes"
    echo "  • Deployment branches: Selected branches (main, release/*)"
}

# Print summary
print_summary() {
    log_step "6" "Setup Complete!"
    
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║         Staging Environment Setup Complete!                ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    echo -e "${CYAN}Infrastructure:${NC}"
    echo "  Resource Group:  $RESOURCE_GROUP"
    echo "  Location:        $LOCATION"
    echo ""
    
    echo -e "${CYAN}App Service:${NC}"
    echo "  Name:            ${APP_SERVICE_NAME:-See Azure Portal}"
    echo "  URL:             ${APP_SERVICE_URL:-See Azure Portal}"
    echo "  Health Check:    ${APP_SERVICE_URL}/health"
    echo ""
    
    echo -e "${CYAN}GitHub:${NC}"
    echo "  Environment:     $ENVIRONMENT_NAME"
    echo "  Repository:      $(gh repo view --json nameWithOwner -q .nameWithOwner)"
    echo ""
    
    echo -e "${CYAN}Next Steps:${NC}"
    echo "  1. Configure GitHub secrets for staging environment"
    echo "  2. Deploy initial container image to staging"
    echo "  3. Run health checks and verify deployment"
    echo "  4. Configure staging-specific settings"
    echo ""
    
    echo -e "${CYAN}Useful Commands:${NC}"
    echo "  # Check staging status"
    echo "  curl -s ${APP_SERVICE_URL}/health | jq ."
    echo ""
    echo "  # View staging logs"
    echo "  az webapp log tail --name ${APP_SERVICE_NAME} --resource-group $RESOURCE_GROUP"
    echo ""
    echo "  # Deploy to staging"
    echo "  gh workflow run deploy-staging.yml"
    echo ""
    
    echo -e "${CYAN}Azure Portal Links:${NC}"
    local subscription_id
    subscription_id=$(az account show --query id -o tsv)
    echo "  https://portal.azure.com/#@/resource/subscriptions/$subscription_id/resourceGroups/$RESOURCE_GROUP"
    echo ""
}

# Main execution
main() {
    echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║    Azure Governance Platform - Staging Environment Setup   ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    check_prerequisites
    create_resource_group
    deploy_infrastructure
    get_deployment_outputs
    create_github_environment
    configure_deployment_protection
    print_summary
}

# Handle Ctrl+C
trap 'echo ""; log_error "Setup interrupted"; exit 130' INT

# Run main
main "$@"

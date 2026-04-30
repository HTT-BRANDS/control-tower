#!/bin/bash
# =============================================================================
# Check GitHub Actions Secrets Configuration
# =============================================================================
# Verifies that all required GitHub Actions secrets are properly configured
#
# This script checks:
#   1. Required Azure secrets (for OIDC)
#   2. Registry authentication
#   3. Deployment configuration
#
# Usage: ./scripts/check-github-secrets.sh [owner/repo]
# Example: ./scripts/check-github-secrets.sh htt-brands/control-tower
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REPO="${1:-$(git remote get-url origin 2>/dev/null | sed 's/.*github.com[:/]\(.*\)\.git$/\1/' || echo '')}"

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
    
    if ! command -v gh &> /dev/null; then
        log_error "GitHub CLI not found. Please install: https://cli.github.com/"
        exit 1
    fi
    
    if ! gh auth status &> /dev/null; then
        log_error "Not authenticated with GitHub CLI. Run: gh auth login"
        exit 1
    fi
    
    if [ -z "$REPO" ]; then
        log_error "Repository not specified and couldn't detect from git remote"
        echo "Usage: $0 [owner/repo]"
        exit 1
    fi
    
    log_success "Prerequisites check passed (Repository: $REPO)"
}

# Check secrets
 check_secrets() {
    log_info "Checking GitHub Actions secrets..."
    
    echo ""
    echo "=========================================="
    echo "    AZURE OIDC SECRETS (Required)"
    echo "=========================================="
    echo ""
    
    # Required OIDC secrets
    local oidc_secrets=(
        "AZURE_CLIENT_ID"
        "AZURE_TENANT_ID"
        "AZURE_SUBSCRIPTION_ID"
    )
    
    local oidc_ok=true
    for secret in "${oidc_secrets[@]}"; do
        if gh secret list --repo "$REPO" | grep -q "^${secret}\\s"; then
            log_success "✓ $secret is set"
        else
            log_error "✗ $secret is NOT set (REQUIRED for OIDC)"
            oidc_ok=false
        fi
    done
    
    echo ""
    echo "=========================================="
    echo "    DEPLOYMENT CONFIGURATION SECRETS"
    echo "=========================================="
    echo ""
    
    # Deployment config secrets
    local config_secrets=(
        "AZURE_RESOURCE_GROUP"
        "AZURE_APP_SERVICE_NAME"
    )
    
    local config_ok=true
    for secret in "${config_secrets[@]}"; do
        if gh secret list --repo "$REPO" | grep -q "^${secret}\\s"; then
            log_success "✓ $secret is set"
        else
            log_warn "⚠ $secret is NOT set (recommended)"
            config_ok=false
        fi
    done
    
    echo ""
    echo "=========================================="
    echo "    OPTIONAL/LEGACY SECRETS"
    echo "=========================================="
    echo ""
    
    # Legacy secrets (not needed with OIDC)
    if gh secret list --repo "$REPO" | grep -q "^AZURE_CREDENTIALS\\s"; then
        log_warn "⚠ AZURE_CREDENTIALS is set (legacy credential-based auth, not needed with OIDC)"
    else
        log_success "✓ AZURE_CREDENTIALS is not set (good, using OIDC)"
    fi
    
    # Registry credentials (needed for private GHCR if not using GITHUB_TOKEN)
    if gh secret list --repo "$REPO" | grep -q "^GHCR_USERNAME\\s"; then
        log_info "✓ GHCR_USERNAME is set (for private container registry)"
    else
        log_info "ℹ GHCR_USERNAME not set (GITHUB_TOKEN is used by default)"
    fi
    
    if gh secret list --repo "$REPO" | grep -q "^GHCR_TOKEN\\s"; then
        log_info "✓ GHCR_TOKEN is set (for private container registry)"
    else
        log_info "ℹ GHCR_TOKEN not set (GITHUB_TOKEN is used by default)"
    fi
    
    echo ""
    
    # Overall status
    if [ "$oidc_ok" = true ]; then
        echo ""
        log_success "✅ All required OIDC secrets are configured!"
        echo ""
        echo "Your deployment should work with the OIDC workflow (.github/workflows/deploy-oidc.yml)"
        echo ""
    else
        echo ""
        log_error "❌ Missing required OIDC secrets!"
        echo ""
        echo "To configure OIDC secrets, follow these steps:"
        echo ""
        echo "1. Get your Azure AD App Registration details:"
        echo "   AZURE_CLIENT_ID:     Your App Registration ID"
        echo "   AZURE_TENANT_ID:     Your Azure AD Tenant ID"
        echo "   AZURE_SUBSCRIPTION_ID: Your Azure Subscription ID"
        echo ""
        echo "2. Set the secrets using GitHub CLI:"
        echo "   gh secret set AZURE_CLIENT_ID --repo $REPO"
        echo "   gh secret set AZURE_TENANT_ID --repo $REPO"
        echo "   gh secret set AZURE_SUBSCRIPTION_ID --repo $REPO"
        echo ""
        echo "3. Set deployment configuration:"
        echo "   gh secret set AZURE_RESOURCE_GROUP --body 'rg-governance-dev' --repo $REPO"
        echo "   gh secret set AZURE_APP_SERVICE_NAME --body 'app-governance-dev-001' --repo $REPO"
        echo ""
        echo "See docs/OIDC_SETUP.md for detailed instructions."
        echo ""
    fi
}

# Check workflows
check_workflows() {
    log_info "Checking GitHub Actions workflows..."
    
    echo ""
    
    local workflow_dir=".github/workflows"
    
    if [ -f "$workflow_dir/deploy-oidc.yml" ]; then
        log_success "✓ OIDC workflow exists: .github/workflows/deploy-oidc.yml"
    else
        log_warn "⚠ OIDC workflow not found: .github/workflows/deploy-oidc.yml"
    fi
    
    if [ -f "$workflow_dir/deploy.yml" ]; then
        log_warn "⚠ Legacy workflow exists: .github/workflows/deploy.yml (consider using deploy-oidc.yml)"
    fi
    
    echo ""
}

# Check container image
 check_container_image() {
    log_info "Checking container image configuration..."
    
    echo ""
    
    # Check if dev image exists in workflow
    local expected_image="ghcr.io/${REPO%%/*}/control-tower"
    
    log_info "Expected container image pattern: ${expected_image}"
    
    # Check workflow files for image references
    if grep -r "ghcr.io" .github/workflows/*.yml 2>/dev/null | head -5; then
        echo ""
        log_success "✓ GHCR references found in workflows"
    else
        log_warn "⚠ No GHCR references found in workflows"
    fi
    
    echo ""
    log_info "To verify your container image is built and pushed:"
    echo ""
    echo "1. Check GitHub Actions runs:"
    echo "   gh run list --repo $REPO --workflow 'Deploy to Azure (OIDC)'"
    echo ""
    echo "2. Check GHCR packages:"
    echo "   gh api /user/packages/container/control-tower/versions --jq '.[].metadata.container.tags[]' 2>/dev/null || echo 'Package not found or not accessible'"
    echo ""
    echo "3. Verify image in GHCR:"
    echo "   https://github.com/${REPO%%/*}?tab=packages"
    echo ""
}

# Print summary
print_summary() {
    echo ""
    echo "=========================================="
    echo "    NEXT STEPS"
    echo "=========================================="
    echo ""
    echo "1. IMMEDIATE FIX (run locally):"
    echo "   ./scripts/fix-dev-runtime.sh"
    echo ""
    echo "2. FULL REDEPLOY (if needed):"
    echo "   ./scripts/redeploy-dev.sh"
    echo ""
    echo "3. TRIGGER CI/CD DEPLOYMENT:"
    echo "   git checkout -b dev"
    echo "   git push origin dev"
    echo ""
    echo "4. VERIFY DEPLOYMENT:"
    echo "   ./scripts/verify-dev-deployment.sh"
    echo ""
    echo "5. CHECK APP SERVICE LOGS:"
    echo "   az webapp log tail --name app-governance-dev-001 --resource-group rg-governance-dev"
    echo ""
}

# Main execution
main() {
    echo "=========================================="
    echo "    GITHUB ACTIONS SECRETS CHECK"
    echo "=========================================="
    echo ""
    
    check_prerequisites
    check_secrets
    check_workflows
    check_container_image
    print_summary
}

# Run main
main "$@"

#!/bin/bash
# =============================================================================
# Azure Governance Platform - GitHub CLI Setup Automation
# =============================================================================
# Master setup script using gh CLI for GitHub repository configuration
#
# Usage:
#   ./scripts/gh-setup.sh [options]
#
# Options:
#   -e, --environment    Environment suffix (dev|staging|prod) [default: dev]
#   -r, --repo           GitHub repo (owner/repo) [auto-detected]
#   --skip-env           Skip environment creation
#   --skip-secrets       Skip secret configuration
#   --skip-protection    Skip branch protection setup
#   -h, --help           Show help
#
# Examples:
#   ./scripts/gh-setup.sh
#   ./scripts/gh-setup.sh -e prod
#   ./scripts/gh-setup.sh -r myorg/azure-governance --skip-protection
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default values
ENVIRONMENT="dev"
GITHUB_REPO=""
SKIP_ENV=false
SKIP_SECRETS=false
SKIP_PROTECTION=false

# Help function
show_help() {
    cat << 'EOF'
Azure Governance Platform - GitHub CLI Setup

Usage: ./scripts/gh-setup.sh [options]

Options:
  -e, --environment    Environment suffix (dev|staging|prod) [default: dev]
  -r, --repo           GitHub repo (owner/repo) [auto-detected from git]
  --skip-env           Skip GitHub environment creation
  --skip-secrets       Skip GitHub secrets configuration
  --skip-protection    Skip branch protection rules setup
  -h, --help           Show this help

Examples:
  ./scripts/gh-setup.sh                    # Full setup for dev
  ./scripts/gh-setup.sh -e prod            # Setup for production
  ./scripts/gh-setup.sh --skip-protection  # Setup without branch protection

Prerequisites:
  - gh CLI installed: https://cli.github.com
  - Authenticated: gh auth login
  - Azure CLI: az login (for fetching Azure details)
EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -r|--repo)
            GITHUB_REPO="$2"
            shift 2
            ;;
        --skip-env)
            SKIP_ENV=true
            shift
            ;;
        --skip-secrets)
            SKIP_SECRETS=true
            shift
            ;;
        --skip-protection)
            SKIP_PROTECTION=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Header
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}🔧 GitHub Setup for Azure Governance Platform${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check gh CLI
if ! command -v gh &> /dev/null; then
    echo -e "${RED}❌ gh CLI not found. Install: https://cli.github.com/${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} gh CLI found"

# Check gh auth status
if ! gh auth status &> /dev/null; then
    echo -e "${YELLOW}⚠️  Not logged in to GitHub. Running gh auth login...${NC}"
    gh auth login
fi

# Get repo info
if [[ -z "$GITHUB_REPO" ]]; then
    GITHUB_REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "")
fi

if [[ -z "$GITHUB_REPO" ]]; then
    echo -e "${RED}❌ Could not detect GitHub repository.${NC}"
    echo "Please run from within the repo or specify with -r owner/repo"
    exit 1
fi

echo -e "  ${GREEN}✓${NC} Connected to: ${CYAN}$GITHUB_REPO${NC}"

# Check Azure CLI (optional, for auto-fetching values)
AZURE_AVAILABLE=false
if command -v az &> /dev/null && az account show &> /dev/null; then
    AZURE_AVAILABLE=true
    echo -e "  ${GREEN}✓${NC} Azure CLI available"
else
    echo -e "  ${YELLOW}⚠${NC} Azure CLI not available (manual input required)"
fi

echo ""

# ============================================================================
# Step 1: Create GitHub Environments
# ============================================================================
if [[ "$SKIP_ENV" == false ]]; then
    echo -e "${BLUE}Step 1: Creating GitHub Environments...${NC}"
    echo ""
    
    ENVIRONMENTS=("development" "staging" "production")
    
    for ENV in "${ENVIRONMENTS[@]}"; do
        echo -e "  Creating '${CYAN}$ENV${NC}' environment..."
        
        # Check if environment already exists
        if gh api "repos/$GITHUB_REPO/environments/$ENV" &> /dev/null; then
            echo -e "    ${YELLOW}⚠${NC} Environment '$ENV' already exists"
        else
            # Create environment
            gh api "repos/$GITHUB_REPO/environments/$ENV" \
                --method PUT \
                --field environment_name="$ENV" \
                --field wait_timer="0" 2>/dev/null || true
            echo -e "    ${GREEN}✓${NC} Created '$ENV' environment"
        fi
    done
    
    echo ""
    echo -e "${YELLOW}Note: Configure environment protection rules in GitHub UI:${NC}"
    echo -e "  ${CYAN}https://github.com/$GITHUB_REPO/settings/environments${NC}"
    echo ""
else
    echo -e "${YELLOW}⏭️  Skipping environment creation (--skip-env)${NC}"
fi

# ============================================================================
# Step 2: Set GitHub Secrets
# ============================================================================
if [[ "$SKIP_SECRETS" == false ]]; then
    echo -e "${BLUE}Step 2: Setting GitHub Secrets...${NC}"
    echo ""
    
    # Collect Azure AD info
    echo -e "${YELLOW}Enter Azure AD configuration:${NC}"
    
    # Auto-fetch from Azure if available
    if [[ "$AZURE_AVAILABLE" == true ]]; then
        DEFAULT_TENANT=$(az account show --query tenantId -o tsv)
        DEFAULT_SUBSCRIPTION=$(az account show --query id -o tsv)
        
        read -p "Azure Tenant ID [$DEFAULT_TENANT]: " AZURE_TENANT_ID
        AZURE_TENANT_ID=${AZURE_TENANT_ID:-$DEFAULT_TENANT}
        
        read -p "Azure Subscription ID [$DEFAULT_SUBSCRIPTION]: " AZURE_SUBSCRIPTION_ID
        AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:-$DEFAULT_SUBSCRIPTION}
    else
        read -p "Azure Tenant ID: " AZURE_TENANT_ID
        read -p "Azure Subscription ID: " AZURE_SUBSCRIPTION_ID
    fi
    
    read -p "Azure Client ID (App Registration): " AZURE_CLIENT_ID
    
    # Set repository secrets
    echo ""
    echo -e "  Setting repository secrets..."
    
    echo "  - Setting AZURE_TENANT_ID..."
    echo "$AZURE_TENANT_ID" | gh secret set AZURE_TENANT_ID --repo "$GITHUB_REPO"
    
    echo "  - Setting AZURE_SUBSCRIPTION_ID..."
    echo "$AZURE_SUBSCRIPTION_ID" | gh secret set AZURE_SUBSCRIPTION_ID --repo "$GITHUB_REPO"
    
    echo "  - Setting AZURE_CLIENT_ID..."
    echo "$AZURE_CLIENT_ID" | gh secret set AZURE_CLIENT_ID --repo "$GITHUB_REPO"
    
    # Set resource group based on environment
    RESOURCE_GROUP="rg-governance-${ENVIRONMENT}"
    echo "  - Setting AZURE_RESOURCE_GROUP ($RESOURCE_GROUP)..."
    echo "$RESOURCE_GROUP" | gh secret set AZURE_RESOURCE_GROUP --repo "$GITHUB_REPO"
    
    # Generate database encryption key
    echo "  - Generating DATABASE_ENCRYPTION_KEY..."
    DB_KEY=$(openssl rand -base64 32)
    echo "$DB_KEY" | gh secret set DATABASE_ENCRYPTION_KEY --repo "$GITHUB_REPO"
    
    echo -e "    ${GREEN}✓${NC} Repository secrets set"
    
    # Set environment-specific secrets
    echo ""
    echo -e "${BLUE}Step 3: Setting Environment Secrets...${NC}"
    
    # Development environment secrets
    echo -e "  Setting development environment secrets..."
    echo "$AZURE_CLIENT_ID" | gh secret set AZURE_CLIENT_ID \
        --env development --repo "$GITHUB_REPO" 2>/dev/null || echo -e "    ${YELLOW}⚠${NC} Failed (environment may not exist)"
    
    echo -e "    ${GREEN}✓${NC} Development environment secrets set"
    
    # Production environment secrets
    echo -e "  Setting production environment secrets..."
    read -p "Production Azure Client ID (or press Enter to use same): " PROD_CLIENT_ID
    PROD_CLIENT_ID=${PROD_CLIENT_ID:-$AZURE_CLIENT_ID}
    echo "$PROD_CLIENT_ID" | gh secret set AZURE_CLIENT_ID \
        --env production --repo "$GITHUB_REPO" 2>/dev/null || echo -e "    ${YELLOW}⚠${NC} Failed (environment may not exist)"
    
    echo -e "    ${GREEN}✓${NC} Production environment secrets set"
else
    echo -e "${YELLOW}⏭️  Skipping secrets configuration (--skip-secrets)${NC}"
fi

# ============================================================================
# Step 4: Configure Branch Protection
# ============================================================================
if [[ "$SKIP_PROTECTION" == false ]]; then
    echo ""
    echo -e "${BLUE}Step 4: Configuring branch protection...${NC}"
    echo ""
    
    echo -e "${YELLOW}Note: Branch protection must be configured in GitHub UI:${NC}"
    echo -e "  ${CYAN}https://github.com/$GITHUB_REPO/settings/branches${NC}"
    echo ""
    echo "Recommended settings for 'main' branch:"
    echo "  ☑️ Restrict pushes that create files larger than 100MB"
    echo "  ☑️ Restrict deletions"
    echo "  ☑️ Require linear history"
    echo "  ☑️ Require a pull request before merging"
    echo "     - Require approvals: 1"
    echo "     - Dismiss stale PR approvals when new commits are pushed"
    echo "     - Require review from CODEOWNERS"
    echo "  ☑️ Require status checks to pass before merging"
    echo "     - Require branches to be up to date before merging"
    echo "  ☑️ Require conversation resolution before merging"
    echo ""
    echo "Configure via gh CLI (requires admin rights):"
    echo "  gh api repos/$GITHUB_REPO/branches/main/protection ..."
    
    # Attempt to set basic protection via API
    echo ""
    echo -e "Attempting to set basic branch protection..."
    
    # Note: This requires admin permissions and may fail.
    #
    # ct-9f1 / F-4 (2026-05-19): `enforce_admins` MUST stay true below.
    # It was briefly disabled by hand on 2026-05-19 so Tyler could
    # self-merge PRs #39-#43 (GitHub forbids approving your own PR),
    # then immediately re-enabled. Before this fix the script still
    # POSTed `enforce_admins: false`, which meant anyone running
    # `./scripts/gh-setup.sh` to refresh repo settings would silently
    # downgrade protection. weekly-ops.yml has a smoke test that fails
    # CI if .enforce_admins.enabled is ever false on main; do NOT flip
    # the value below without coordinating that gate.
    gh api "repos/$GITHUB_REPO/branches/main/protection" \
        --method PUT \
        --input - << PROTECTION_JSON 2>/dev/null || echo -e "  ${YELLOW}⚠${NC} Could not set branch protection (may need admin rights or use UI)"
{
  "required_status_checks": null,
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_linear_history": true
}
PROTECTION_JSON
    
else
    echo -e "${YELLOW}⏭️  Skipping branch protection (--skip-protection)${NC}"
fi

# ============================================================================
# Step 5: Verify Setup
# ============================================================================
echo ""
echo -e "${BLUE}Step 5: Verifying Setup...${NC}"
echo ""

echo -e "${GREEN}Repository secrets:${NC}"
gh secret list --repo "$GITHUB_REPO" 2>/dev/null | head -10 || echo "  (none set)"

echo ""
echo -e "${GREEN}Development environment secrets:${NC}"
gh secret list --env development --repo "$GITHUB_REPO" 2>/dev/null | head -5 || echo "  (none set)"

echo ""
echo -e "${GREEN}Production environment secrets:${NC}"
gh secret list --env production --repo "$GITHUB_REPO" 2>/dev/null | head -5 || echo "  (none set)"

echo ""
echo -e "${GREEN}Environments:${NC}"
gh api "repos/$GITHUB_REPO/environments" --jq '.environments[].name' 2>/dev/null || echo "  (none found)"

echo ""
echo -e "${GREEN}Repository variables:${NC}"
gh variable list --repo "$GITHUB_REPO" 2>/dev/null | head -5 || echo "  (none set)"

# ============================================================================
# Completion
# ============================================================================
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}🎉 GitHub setup complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Next steps:"
echo "  1. Configure OIDC federation in Azure:"
echo -e "     ${CYAN}./infrastructure/setup-oidc.sh -e $ENVIRONMENT -g rg-governance-$ENVIRONMENT${NC}"
echo ""
echo "  2. Deploy to dev:"
echo -e "     ${CYAN}./scripts/gh-deploy-dev.sh${NC}"
echo ""
echo "  3. Monitor workflows:"
echo -e "     ${CYAN}gh run list${NC}"
echo ""
echo "  4. View repository in browser:"
echo -e "     ${CYAN}gh repo view --web${NC}"
echo ""
echo "Useful gh CLI commands:"
echo "  gh workflow list           # List workflows"
echo "  gh run list                # List recent runs"
echo "  gh run watch               # Watch current run"
echo "  gh secret list             # List secrets"
echo "  gh variable list           # List variables"
echo ""

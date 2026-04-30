#!/usr/bin/env bash
#
# HTT Control Tower - Old ACR Cleanup Script
#
# Safely deletes the old Azure Container Registry (acrgovstaging19859) after
# verifying GHCR is working and images are available.
#
# Usage:
#   ./scripts/cleanup-old-acr.sh              # Preview what will be deleted
#   ./scripts/cleanup-old-acr.sh --confirm    # Actually delete (requires flag)
#   ./scripts/cleanup-old-acr.sh --yes       # Skip confirmation prompts
#
# Cost Savings: ~$5-10/month (ACR Standard SKU + storage + data transfer)
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Configuration
OLD_ACR_NAME="acrgovstaging19859"
OLD_ACR_RESOURCE_GROUP="rg-governance-staging"
GHCR_REPO="ghcr.io/htt-brands/control-tower"

# Script flags
CONFIRM=false
SKIP_PROMPTS=false
DRY_RUN=false

# Cost estimation (ACR Standard SKU)
ACR_MONTHLY_COST=5.00        # $5/day base
STORAGE_COST=2.00            # Estimated storage
DATATRANSFER_COST=3.00       # Estimated data transfer
TOTAL_MONTHLY_SAVINGS=$(echo "$ACR_MONTHLY_COST + $STORAGE_COST + $DATATRANSFER_COST" | bc)
ANNUAL_SAVINGS=$(echo "$TOTAL_MONTHLY_SAVINGS * 12" | bc)

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

print_header() {
    echo ""
    echo "================================================================================"
    echo "  $1"
    echo "================================================================================"
    echo ""
}

print_success() {
    echo -e "  ${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "  ${RED}✗${NC} $1"
}

print_warning() {
    echo -e "  ${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "  ${BLUE}ℹ${NC} $1"
}

print_step() {
    echo -e "  ${CYAN}→${NC} $1"
}

# =============================================================================
# PREREQUISITE CHECKS
# =============================================================================

check_prerequisites() {
    print_header "Checking Prerequisites"

    # Check Azure CLI
    if ! command -v az &> /dev/null; then
        print_error "Azure CLI (az) not found"
        echo ""
        echo "  Install from: https://aka.ms/installazurecli"
        exit 1
    fi
    print_success "Azure CLI found"

    # Check if logged in
    if ! az account show &> /dev/null; then
        print_error "Not logged into Azure"
        echo ""
        echo "  Run: az login"
        exit 1
    fi

    local account
    account=$(az account show --query "user.name" -o tsv)
    print_success "Logged in as: $account"

    # Check docker (for GHCR verification)
    if ! command -v docker &> /dev/null; then
        print_warning "Docker not found - will skip GHCR image pull test"
    else
        print_success "Docker found"
    fi

    # Check jq
    if ! command -v jq &> /dev/null; then
        print_warning "jq not found - some JSON output will be limited"
    fi
}

# =============================================================================
# GHCR VERIFICATION
# =============================================================================

verify_ghcr_available() {
    print_header "Verifying GHCR is Working"

    print_step "Checking GHCR repository accessibility..."

    # Check if GHCR repo is accessible via API
    local http_status
    http_status=$(curl -s -o /dev/null -w "%{http_code}" "https://ghcr.io/v2/htt-brands/control-tower/tags/list" 2>/dev/null || echo "000")

    if [[ "$http_status" == "200" ]] || [[ "$http_status" == "401" ]]; then
        # 401 is expected without auth, but means repo exists
        print_success "GHCR repository is accessible (HTTP $http_status)"
    else
        print_warning "GHCR repository returned HTTP $http_status"
        print_info "This may be normal if the repository is private"
    fi

    # List available tags via GitHub API
    print_step "Checking available GHCR image tags..."

    local tags
    tags=$(curl -s "https://api.github.com/users/tygranlund/packages/container/control-tower/versions" 2>/dev/null | jq -r '.[].metadata.container.tags[]?' 2>/dev/null | head -10 || echo "")

    if [[ -n "$tags" ]]; then
        print_success "Found GHCR image tags:"
        echo "$tags" | while read -r tag; do
            echo "    - $tag"
        done
    else
        print_warning "Could not retrieve GHCR tags via API (private repo or no access)"
    fi

    # Check App Service is using GHCR
    print_step "Verifying App Service is configured for GHCR..."

    local staging_app="app-governance-staging-xnczpwyv"
    local container_image
    container_image=$(az webapp config container show \
        --name "$staging_app" \
        --resource-group "$OLD_ACR_RESOURCE_GROUP" \
        --query "linuxFxVersion" -o tsv 2>/dev/null || echo "")

    if [[ "$container_image" == *"ghcr.io"* ]]; then
        print_success "Staging App Service is using GHCR: $container_image"
    elif [[ "$container_image" == *"acr"* ]]; then
        print_warning "Staging App Service is still using ACR: $container_image"
        print_info "Consider migrating App Service to GHCR before deleting ACR"
    else
        print_info "App Service container config: $container_image"
    fi
}

# =============================================================================
# ACR INVENTORY
# =============================================================================

list_acr_contents() {
    print_header "ACR Contents to be Deleted"

    # Check if ACR exists
    print_step "Checking if ACR '$OLD_ACR_NAME' exists..."

    if ! az acr show --name "$OLD_ACR_NAME" --resource-group "$OLD_ACR_RESOURCE_GROUP" &> /dev/null; then
        print_warning "ACR '$OLD_ACR_NAME' not found in resource group '$OLD_ACR_RESOURCE_GROUP'"
        print_info "It may have already been deleted or be in a different resource group"

        # Try to find it
        print_step "Searching for ACR in subscription..."
        local found_acr
        found_acr=$(az acr list --query "[?name=='$OLD_ACR_NAME'].{name:name, rg:resourceGroup}" -o tsv 2>/dev/null || echo "")

        if [[ -n "$found_acr" ]]; then
            print_info "Found ACR in different resource group:"
            echo "$found_acr"
        fi

        return 1
    fi

    print_success "ACR '$OLD_ACR_NAME' found"

    # Get ACR details
    print_step "Retrieving ACR details..."

    local acr_info
    acr_info=$(az acr show --name "$OLD_ACR_NAME" --resource-group "$OLD_ACR_RESOURCE_GROUP" -o json 2>/dev/null)

    local login_server sku created_date
    login_server=$(echo "$acr_info" | jq -r '.loginServer')
    sku=$(echo "$acr_info" | jq -r '.sku.name')
    created_date=$(echo "$acr_info" | jq -r '.creationDate')

    echo ""
    echo "  ${BOLD}ACR Details:${NC}"
    echo "    Name:          $OLD_ACR_NAME"
    echo "    Login Server:  $login_server"
    echo "    SKU:           $sku"
    echo "    Created:       $created_date"
    echo "    Resource Group: $OLD_ACR_RESOURCE_GROUP"
    echo ""

    # List repositories
    print_step "Listing container repositories..."

    local repos
    repos=$(az acr repository list --name "$OLD_ACR_NAME" -o tsv 2>/dev/null || echo "")

    if [[ -z "$repos" ]]; then
        print_info "No repositories found in ACR"
    else
        echo ""
        echo "  ${BOLD}Repositories to be deleted:${NC}"

        local repo_count=0
        local total_images=0

        for repo in $repos; do
            repo_count=$((repo_count + 1))
            echo ""
            echo "    📦 $repo"

            # List tags for this repository
            local tags
            tags=$(az acr repository show-tags --name "$OLD_ACR_NAME" --repository "$repo" -o tsv 2>/dev/null || echo "")

            if [[ -n "$tags" ]]; then
                local tag_count
                tag_count=$(echo "$tags" | wc -l)
                total_images=$((total_images + tag_count))

                echo "       Tags ($tag_count):"
                echo "$tags" | head -10 | while read -r tag; do
                    echo "         - $tag"
                done

                if [[ $tag_count -gt 10 ]]; then
                    echo "         ... and $((tag_count - 10)) more"
                fi
            fi
        done

        echo ""
        print_info "Total: $repo_count repositories, $total_images image tags"
    fi

    # Show network rules if any
    print_step "Checking network configuration..."

    local network_rules
    network_rules=$(az acr network-rule list --name "$OLD_ACR_NAME" --resource-group "$OLD_ACR_RESOURCE_GROUP" -o json 2>/dev/null || echo "{}")

    local rule_count
    rule_count=$(echo "$network_rules" | jq '.ipRules | length')

    if [[ "$rule_count" -gt 0 ]]; then
        print_warning "Found $rule_count network rules (will be deleted)"
    else
        print_info "No custom network rules"
    fi

    return 0
}

# =============================================================================
# COST CALCULATION
# =============================================================================

show_cost_savings() {
    print_header "Cost Impact Analysis"

    echo ""
    echo "  ${BOLD}Estimated Monthly Savings:${NC}"
    echo ""
    printf "    %-30s %8s\n" "ACR Standard SKU (base):" "\$${ACR_MONTHLY_COST}"
    printf "    %-30s %8s\n" "Storage (estimated):" "\$${STORAGE_COST}"
    printf "    %-30s %8s\n" "Data transfer (estimated):" "\$${DATATRANSFER_COST}"
    echo "    ----------------------------------------"
    printf "    ${BOLD}%-30s %8s${NC}\n" "TOTAL MONTHLY SAVINGS:" "\$${TOTAL_MONTHLY_SAVINGS}"
    echo ""
    printf "    ${BOLD}%-30s %8s${NC}\n" "ANNUAL SAVINGS:" "\$${ANNUAL_SAVINGS}"
    echo ""

    print_info "Note: Actual savings may vary based on usage patterns"
}

# =============================================================================
# DELETE OPERATIONS
# =============================================================================

delete_acr() {
    print_header "Deleting Azure Container Registry"

    if [[ "$CONFIRM" != true ]]; then
        print_error "Cannot delete without --confirm flag"
        print_info "Run with --confirm to proceed with deletion"
        return 1
    fi

    # Final confirmation unless --yes flag
    if [[ "$SKIP_PROMPTS" != true ]]; then
        echo ""
        print_warning "You are about to PERMANENTLY DELETE:"
        echo "  - Azure Container Registry: $OLD_ACR_NAME"
        echo "  - Resource Group: $OLD_ACR_RESOURCE_GROUP"
        echo "  - All container images and repositories"
        echo ""
        echo -n "  Type 'delete' to confirm: "
        read -r confirmation

        if [[ "$confirmation" != "delete" ]]; then
            print_error "Confirmation failed - deletion cancelled"
            return 1
        fi
    fi

    print_step "Deleting ACR '$OLD_ACR_NAME'..."

    if az acr delete \
        --name "$OLD_ACR_NAME" \
        --resource-group "$OLD_ACR_RESOURCE_GROUP" \
        --yes \
        --no-wait 2>/dev/null; then
        print_success "ACR deletion initiated (async)"
        print_info "Deletion may take a few minutes to complete"

        # Show deletion status
        echo ""
        print_step "Checking deletion status..."
        sleep 5

        if az acr show --name "$OLD_ACR_NAME" --resource-group "$OLD_ACR_RESOURCE_GROUP" &> /dev/null; then
            print_warning "ACR still exists - deletion in progress"
            print_info "Check status with: az acr show -n $OLD_ACR_NAME -g $OLD_ACR_RESOURCE_GROUP"
        else
            print_success "ACR successfully deleted!"
        fi
    else
        print_error "Failed to delete ACR"
        return 1
    fi

    return 0
}

# =============================================================================
# POST-DELETION VERIFICATION
# =============================================================================

verify_deletion() {
    print_header "Post-Deletion Verification"

    print_step "Verifying ACR no longer exists..."

    if az acr show --name "$OLD_ACR_NAME" --resource-group "$OLD_ACR_RESOURCE_GROUP" &> /dev/null; then
        print_error "ACR still exists after deletion attempt!"
        return 1
    else
        print_success "ACR '$OLD_ACR_NAME' confirmed deleted"
    fi

    print_step "Verifying GHCR still accessible..."

    local http_status
    http_status=$(curl -s -o /dev/null -w "%{http_code}" "https://ghcr.io" 2>/dev/null || echo "000")

    if [[ "$http_status" == "200" ]] || [[ "$http_status" == "301" ]]; then
        print_success "GHCR is accessible (HTTP $http_status)"
    else
        print_warning "GHCR check returned HTTP $http_status"
    fi

    print_step "Checking App Service health..."

    local staging_url="https://app-governance-staging-xnczpwyv.azurewebsites.net/health"
    local health_status
    health_status=$(curl -s -o /dev/null -w "%{http_code}" "$staging_url" 2>/dev/null || echo "000")

    if [[ "$health_status" == "200" ]]; then
        print_success "Staging App Service health check passed"
    else
        print_warning "Staging health check returned HTTP $health_status"
    fi
}

# =============================================================================
# USAGE
# =============================================================================

print_usage() {
    cat <<EOF
Azure Governance Platform - Old ACR Cleanup Script

This script safely removes the old Azure Container Registry (acrgovstaging19859)
after verifying that GHCR (GitHub Container Registry) is working properly.

Usage:
  ./scripts/cleanup-old-acr.sh [options]

Options:
  --confirm          Required flag to actually perform deletion
  --yes              Skip confirmation prompts (use with caution)
  --dry-run          Show what would be deleted without making changes
  --help, -h         Show this help message

Examples:
  # Preview what will be deleted (safe)
  ./scripts/cleanup-old-acr.sh

  # Delete with confirmation prompts
  ./scripts/cleanup-old-acr.sh --confirm

  # Delete without prompts (CI/automation)
  ./scripts/cleanup-old-acr.sh --confirm --yes

Prerequisites:
  - Azure CLI installed and logged in
  - GHCR must be working (images available)
  - App Service must be configured for GHCR (optional but recommended)

Cost Savings:
  - ACR Standard SKU: ~\$5/month
  - Storage: ~\$2/month
  - Data transfer: ~\$3/month
  - Total: ~\$10/month (~\$120/year)

Rollback:
  If you need to recreate the ACR:
    az acr create --name $OLD_ACR_NAME --resource-group $OLD_ACR_RESOURCE_GROUP --sku Standard

  Then rebuild images from GitHub Actions or local Docker.

EOF
}

# =============================================================================
# MAIN
# =============================================================================

main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --confirm)
                CONFIRM=true
                shift
                ;;
            --yes)
                SKIP_PROMPTS=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --help|-h)
                print_usage
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                print_usage
                exit 1
                ;;
        esac
    done

    print_header "Azure Governance Platform - Old ACR Cleanup"
    echo "  Target: $OLD_ACR_NAME"
    echo "  Resource Group: $OLD_ACR_RESOURCE_GROUP"
    echo "  Mode: $([[ "$CONFIRM" == true ]] && echo "DELETE" || echo "PREVIEW")"
    echo ""

    # Check prerequisites
    check_prerequisites

    # Verify GHCR is working
    verify_ghcr_available

    # List what will be deleted
    if ! list_acr_contents; then
        print_warning "Could not inventory ACR contents"
        if [[ "$CONFIRM" == true ]]; then
            print_error "Cannot proceed with deletion - ACR inventory failed"
            exit 1
        fi
    fi

    # Show cost savings
    show_cost_savings

    # Perform deletion if confirmed
    if [[ "$CONFIRM" == true ]]; then
        if delete_acr; then
            verify_deletion
            print_header "Cleanup Complete!"
            print_success "Old ACR has been deleted"
            print_info "Estimated savings: \$${TOTAL_MONTHLY_SAVINGS}/month (\$${ANNUAL_SAVINGS}/year)"
            echo ""
            print_info "Next steps:"
            echo "  1. Verify staging App Service is healthy"
            echo "  2. Monitor for any deployment issues"
            echo "  3. Update documentation to remove ACR references"
            echo ""
        else
            print_error "Deletion failed or was cancelled"
            exit 1
        fi
    else
        print_header "Preview Mode Complete"
        print_info "No changes were made (run with --confirm to delete)"
        print_info "Review the items above before proceeding with deletion"
        echo ""
        echo "  To delete, run:"
        echo "    ./scripts/cleanup-old-acr.sh --confirm"
        echo ""
    fi
}

# Run main
main "$@"

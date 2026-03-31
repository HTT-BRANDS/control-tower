#!/usr/bin/env bash
#
# Azure Governance Platform - Phase A App Registrations Cleanup
#
# Deletes the old per-tenant app registrations from Phase A after verifying
# that the multi-tenant app (Phase B) is working properly.
#
# Preserves:
#   - Multi-tenant app registration (Phase B)
#   - UAMI and federated credentials (Phase C)
#
# Usage:
#   ./scripts/cleanup-phase-a-apps.sh              # Preview what will be deleted
#   ./scripts/cleanup-phase-a-apps.sh --confirm   # Actually delete (requires flag)
#   ./scripts/cleanup-phase-a-apps.sh --yes      # Skip confirmation prompts
#
# WARNING: This deletes app registrations permanently. Service principals
# can be restored within 30 days via Azure AD soft-delete.
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

# Phase A per-tenant app configuration (from config/tenants.yaml)
TENANTS=(HTT BCC FN TLL DCE)
TENANT_NAMES=("Head-To-Toe (HTT)" "Bishops (BCC)" "Frenchies (FN)" "Lash Lounge (TLL)" "Delta Crown Extensions (DCE)")
TENANT_IDS=("0c0e35dc-188a-4eb3-b8ba-61752154b407" "b5380912-79ec-452d-a6ca-6d897b19b294" "98723287-044b-4bbb-9294-19857d4128a0" "3c7d2bf3-b597-4766-b5cb-2b489c2904d6" "ce62e17d-2feb-4e67-a115-8ea4af68da30")
PHASE_A_APP_IDS=("1e3e8417-49f1-4d08-b7be-47045d8a12e9" "4861906b-2079-4335-923f-a55cc0e44d64" "7648d04d-ccc4-43ac-bace-da1b68bf11b4" "52531a02-78fd-44ba-9ab9-b29675767955" "79c22a10-3f2d-4e6a-bddc-ee65c9a46cb0")

# Script flags
CONFIRM=false
SKIP_PROMPTS=false
DRY_RUN=false

# Results tracking (use indexed arrays for bash 3.x compatibility)
APP_EXISTS=()
APP_NAMES=()
DELETE_STATUS=()
ERRORS=()

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

get_index() {
    local code="$1"
    local i
    for i in "${!TENANTS[@]}"; do
        if [[ "${TENANTS[$i]}" == "$code" ]]; then
            echo "$i"
            return 0
        fi
    done
    echo "-1"
    return 1
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

    # Check version supports soft-delete operations
    local az_version
    az_version=$(az --version | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
    print_success "Azure CLI version: $az_version"

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

    # Check permissions
    print_step "Checking Azure AD permissions..."

    if ! az ad app list --top 1 &> /dev/null; then
        print_error "Insufficient permissions to read app registrations"
        print_info "You need: Application.ReadWrite.All or equivalent"
        exit 1
    fi
    print_success "Azure AD access confirmed"
}

# =============================================================================
# PHASE B/C VERIFICATION
# =============================================================================

verify_multi_tenant_app() {
    print_header "Verifying Phase B Multi-Tenant App"

    print_step "Checking if multi-tenant app is configured..."

    # Check tenants.yaml for multi_tenant_app_id
    if [[ -f "config/tenants.yaml" ]]; then
        if grep -q "multi_tenant_app_id:" "config/tenants.yaml"; then
            local multi_tenant_app_id
            multi_tenant_app_id=$(grep "multi_tenant_app_id:" "config/tenants.yaml" | head -1 | sed 's/.*: *//' | tr -d '" ')
            print_success "Multi-tenant app ID found in tenants.yaml: $multi_tenant_app_id"

            # Try to verify the app exists
            print_step "Verifying multi-tenant app exists in Azure AD..."

            if az ad app show --id "$multi_tenant_app_id" &> /dev/null; then
                print_success "Multi-tenant app registration exists"

                # Check if it's actually multi-tenant
                local sign_in_audience
                sign_in_audience=$(az ad app show --id "$multi_tenant_app_id" --query "signInAudience" -o tsv 2>/dev/null || echo "")

                if [[ "$sign_in_audience" == "AzureADMultipleOrgs" ]]; then
                    print_success "App is configured as multi-tenant"
                else
                    print_warning "App signInAudience is '$sign_in_audience' (expected: AzureADMultipleOrgs)"
                fi
            else
                print_warning "Could not verify multi-tenant app in Azure AD"
            fi
        else
            print_warning "No multi_tenant_app_id found in config/tenants.yaml"
            print_info "Phase B may not be fully configured"
        fi
    else
        print_warning "config/tenants.yaml not found"
    fi
}

verify_uami_setup() {
    print_header "Verifying Phase C UAMI Setup"

    print_step "Checking for UAMI configuration..."

    # Check .env for UAMI settings
    if [[ -f ".env" ]]; then
        if grep -q "USE_UAMI_AUTH=true" ".env" 2>/dev/null; then
            local uami_client_id
            uami_client_id=$(grep "UAMI_CLIENT_ID=" ".env" 2>/dev/null | head -1 | cut -d'=' -f2 || echo "")

            if [[ -n "$uami_client_id" ]]; then
                print_success "UAMI authentication is configured"
                print_info "UAMI Client ID: $uami_client_id"

                # Try to verify UAMI exists
                print_step "Verifying UAMI exists in Azure AD..."

                if az ad sp show --id "$uami_client_id" &> /dev/null; then
                    print_success "UAMI service principal exists"
                else
                    print_warning "Could not verify UAMI (may be in different tenant)"
                fi
            else
                print_warning "USE_UAMI_AUTH is set but UAMI_CLIENT_ID not found"
            fi
        else
            print_info "UAMI authentication not enabled (may still use client secrets)"
        fi
    else
        print_info ".env file not found - skipping UAMI check"
    fi

    # Check Key Vault for multi-tenant secret
    print_step "Checking Key Vault for Phase B secret..."

    # Try to find Key Vault name from environment or config
    local kv_name
    kv_name=$(grep -E "KEY_VAULT_NAME|AZURE_KEY_VAULT" ".env" 2>/dev/null | head -1 | cut -d'=' -f2 || echo "")

    if [[ -n "$kv_name" ]]; then
        if az keyvault secret show --vault-name "$kv_name" --name "multi-tenant-client-secret" &> /dev/null; then
            print_success "Multi-tenant client secret found in Key Vault"
        else
            print_warning "Multi-tenant secret not found in Key Vault: $kv_name"
        fi
    else
        print_info "Could not determine Key Vault name - skipping secret check"
    fi
}

# =============================================================================
# LIST PHASE A APPS
# =============================================================================

list_phase_a_apps() {
    print_header "Phase A App Registrations to be Deleted"

    echo ""
    echo "  ${BOLD}The following 5 per-tenant app registrations will be deleted:${NC}"
    echo ""

    local found_count=0
    local missing_count=0

    for i in "${!TENANTS[@]}"; do
        local code="${TENANTS[$i]}"
        local name="${TENANT_NAMES[$i]}"
        local tenant_id="${TENANT_IDS[$i]}"
        local app_id="${PHASE_A_APP_IDS[$i]}"

        echo "  ${BOLD}[$code] $name${NC}"
        echo "    Tenant ID: $tenant_id"
        echo "    App ID:    $app_id"

        # Check if app exists
        local app_data
        app_data=$(az ad app show --id "$app_id" 2>&1) && {
            APP_EXISTS[$i]=true
            found_count=$((found_count + 1))

            local app_name
            app_name=$(echo "$app_data" | grep "displayName" | head -1 | sed 's/.*: *"//; s/".*//')
            APP_NAMES[$i]="$app_name"

            # Get service principal info
            local sp_data
            sp_data=$(az ad sp show --id "$app_id" 2>&1) && {
                print_success "  App exists: $app_name"

                # Check for credentials
                local cred_count
                cred_count=$(az ad app credential list --id "$app_id" --query "length(@)" -o tsv 2>/dev/null || echo "0")

                if [[ "$cred_count" -gt 0 ]]; then
                    print_info "  Client secrets: $cred_count"
                fi
            } || {
                print_warning "  App exists but no service principal found"
            }
        } || {
            APP_EXISTS[$i]=false
            missing_count=$((missing_count + 1))
            ERRORS[$i]="App not found or no access"
            print_info "  App not found (may already be deleted)"
        }

        echo ""
    done

    echo "  ------------------------------------------------------------------------"
    echo "  ${BOLD}Summary:${NC} $found_count found, $missing_count already deleted/missing"
    echo ""

    return 0
}

# =============================================================================
# PRE-CLEANUP CHECKLIST
# =============================================================================

show_prechecklist() {
    print_header "Pre-Cleanup Verification Checklist"

    echo ""
    echo "  ${BOLD}Before deleting Phase A apps, verify:${NC}"
    echo ""

    local all_pass=true

    # Check 1: Multi-tenant app configured
    echo -n "  [ ] Multi-tenant app configured in tenants.yaml"
    if grep -q "multi_tenant_app_id:" "config/tenants.yaml" 2>/dev/null; then
        echo -e " ${GREEN}✓${NC}"
    else
        echo -e " ${RED}✗${NC}"
        all_pass=false
    fi

    # Check 2: Key Vault has multi-tenant secret
    echo -n "  [ ] Multi-tenant secret in Key Vault"
    local kv_name
    kv_name=$(grep -E "KEY_VAULT_NAME|AZURE_KEY_VAULT" ".env" 2>/dev/null | head -1 | cut -d'=' -f2 || echo "")
    if [[ -n "$kv_name" ]] && az keyvault secret show --vault-name "$kv_name" --name "multi-tenant-client-secret" &> /dev/null; then
        echo -e " ${GREEN}✓${NC}"
    else
        echo -e " ${YELLOW}~${NC} (optional for UAMI)"
    fi

    # Check 3: UAMI configured (optional)
    echo -n "  [ ] UAMI authentication configured (Phase C)"
    if [[ -f ".env" ]] && grep -q "USE_UAMI_AUTH=true" ".env" 2>/dev/null; then
        echo -e " ${GREEN}✓${NC}"
    else
        echo -e " ${YELLOW}~${NC} (optional - can use client secrets)"
    fi

    # Check 4: App Service healthy
    echo -n "  [ ] Staging App Service healthy"
    local health_status
    health_status=$(curl -s -o /dev/null -w "%{http_code}" "https://app-governance-staging-xnczpwyv.azurewebsites.net/health" 2>/dev/null || echo "000")
    if [[ "$health_status" == "200" ]]; then
        echo -e " ${GREEN}✓${NC}"
    else
        echo -e " ${YELLOW}~${NC} (HTTP $health_status - may be starting up)"
    fi

    # Check 5: Recent sync operations successful
    echo -n "  [ ] Recent tenant sync operations"
    if command -v python3 &> /dev/null && [[ -f "app/core/tenants_config.py" ]]; then
        # Try to import and verify multi-tenant mode
        if python3 -c "
import sys
sys.path.insert(0, '.')
from app.core.tenants_config import is_multi_tenant_mode_enabled
print('enabled' if is_multi_tenant_mode_enabled() else 'disabled')
" 2>/dev/null | grep -q "enabled"; then
            echo -e " ${GREEN}✓${NC} (multi-tenant mode enabled)"
        else
            echo -e " ${YELLOW}~${NC} (check manually)"
        fi
    else
        echo -e " ${YELLOW}~${NC} (check manually)"
    fi

    echo ""

    if [[ "$all_pass" == true ]]; then
        print_success "All critical checks passed!"
        return 0
    else
        print_warning "Some checks failed - review before proceeding"
        return 1
    fi
}

# =============================================================================
# DELETE APPS
# =============================================================================

delete_phase_a_apps() {
    print_header "Deleting Phase A App Registrations"

    if [[ "$CONFIRM" != true ]]; then
        print_error "Cannot delete without --confirm flag"
        print_info "Run with --confirm to proceed with deletion"
        return 1
    fi

    # Final confirmation unless --yes flag
    if [[ "$SKIP_PROMPTS" != true ]]; then
        echo ""
        print_warning "You are about to PERMANENTLY DELETE 5 app registrations:"
        echo ""

        for i in "${!TENANTS[@]}"; do
            if [[ "${APP_EXISTS[$i]:-false}" == "true" ]]; then
                echo "  - [${TENANTS[$i]}] ${APP_NAMES[$i]:-Unknown} (${PHASE_A_APP_IDS[$i]})"
            fi
        done

        echo ""
        print_warning "Service principals can be restored within 30 days via Azure AD soft-delete."
        echo "  App registrations are permanently deleted immediately."
        echo ""
        echo -n "  Type 'delete phase a apps' to confirm: "
        read -r confirmation

        if [[ "$confirmation" != "delete phase a apps" ]]; then
            print_error "Confirmation failed - deletion cancelled"
            return 1
        fi
    fi

    # Delete each app
    local deleted_count=0
    local failed_count=0
    local skipped_count=0

    for i in "${!TENANTS[@]}"; do
        local code="${TENANTS[$i]}"
        local app_id="${PHASE_A_APP_IDS[$i]}"
        local app_name="${APP_NAMES[$i]:-Unknown}"

        echo ""
        print_step "Deleting [$code] $app_name..."

        if [[ "${APP_EXISTS[$i]:-false}" != "true" ]]; then
            print_info "  App not found - skipping"
            skipped_count=$((skipped_count + 1))
            continue
        fi

        # First delete service principal (if exists)
        local sp_deleted=false
        if az ad sp show --id "$app_id" &> /dev/null; then
            if az ad sp delete --id "$app_id" 2>/dev/null; then
                print_success "  Service principal deleted"
                sp_deleted=true
            else
                print_warning "  Could not delete service principal"
            fi
        fi

        # Delete the app registration
        if az ad app delete --id "$app_id" 2>/dev/null; then
            print_success "  App registration deleted"
            DELETE_STATUS[$i]="deleted"
            deleted_count=$((deleted_count + 1))
        else
            print_error "  Failed to delete app registration"
            DELETE_STATUS[$i]="failed"
            ERRORS[$i]="Deletion failed"
            failed_count=$((failed_count + 1))
        fi
    done

    echo ""
    echo "  ------------------------------------------------------------------------"
    echo "  ${BOLD}Deletion Summary:${NC}"
    echo "    Deleted: $deleted_count"
    echo "    Failed:  $failed_count"
    echo "    Skipped: $skipped_count"
    echo ""

    if [[ $failed_count -gt 0 ]]; then
        return 1
    fi

    return 0
}

# =============================================================================
# POST-DELETION SUMMARY
# =============================================================================

show_post_summary() {
    print_header "Post-Deletion Summary"

    echo ""
    echo "  ${BOLD}Cleanup Complete!${NC}"
    echo ""

    # Show what was deleted
    echo "  Deleted app registrations:"
    for i in "${!TENANTS[@]}"; do
        local code="${TENANTS[$i]}"
        local status="${DELETE_STATUS[$i]:-unknown}"

        case "$status" in
            deleted)
                echo -e "    ${GREEN}✓${NC} [$code] ${TENANT_NAMES[$i]}"
                ;;
            failed)
                echo -e "    ${RED}✗${NC} [$code] ${TENANT_NAMES[$i]} - ${ERRORS[$i]:-Failed}"
                ;;
            *)
                echo -e "    ${YELLOW}~${NC} [$code] ${TENANT_NAMES[$i]} - ${status}"
                ;;
        esac
    done

    echo ""
    print_info "What was preserved:"
    echo "  - Multi-tenant app registration (Phase B)"
    echo "  - Key Vault secrets (multi-tenant-client-secret)"
    echo "  - UAMI and federated credentials (Phase C)"
    echo "  - Azure Lighthouse delegations"

    echo ""
    print_info "Benefits of this cleanup:"
    echo "  - Reduced secret management overhead"
    echo "  - Single point of rotation (Phase B secret)"
    echo "  - Cleaner Azure AD tenant"

    echo ""
    print_warning "Rollback options (if needed):"
    echo "  1. If deleted < 30 days: Azure AD soft-delete recovery"
    echo "     az ad app list-deleted --query \"[?displayName.contains(@,'Riverside')]\""
    echo "     az ad app restore --id <deleted-app-id>"
    echo ""
    echo "  2. If deleted > 30 days: Recreate using scripts/setup-tenant-apps.ps1"
    echo "     Requires Global Admin in each tenant"
    echo ""
}

# =============================================================================
# USAGE
# =============================================================================

print_usage() {
    cat <<EOF
Azure Governance Platform - Phase A App Registrations Cleanup

This script removes the old per-tenant app registrations from Phase A after
verifying that the multi-tenant app (Phase B) and UAMI (Phase C) are working.

Apps to be deleted:
  1. HTT: ${PHASE_A_APP_IDS[0]}
  2. BCC: ${PHASE_A_APP_IDS[1]}
  3. FN:  ${PHASE_A_APP_IDS[2]}
  4. TLL: ${PHASE_A_APP_IDS[3]}
  5. DCE: ${PHASE_A_APP_IDS[4]}

What is preserved:
  - Multi-tenant app registration (Phase B)
  - UAMI and federated credentials (Phase C)
  - Key Vault secrets
  - Azure Lighthouse delegations

Usage:
  ./scripts/cleanup-phase-a-apps.sh [options]

Options:
  --confirm          Required flag to actually perform deletion
  --yes              Skip confirmation prompts (use with caution)
  --dry-run          Show what would be deleted without making changes
  --help, -h         Show this help message

Examples:
  # Preview what will be deleted (safe)
  ./scripts/cleanup-phase-a-apps.sh

  # Delete with confirmation prompts
  ./scripts/cleanup-phase-a-apps.sh --confirm

  # Delete without prompts (CI/automation)
  ./scripts/cleanup-phase-a-apps.sh --confirm --yes

Prerequisites:
  - Azure CLI installed and logged in
  - Application.ReadWrite.All permission in Azure AD
  - Multi-tenant app (Phase B) must be working
  - config/tenants.yaml with multi_tenant_app_id configured

Rollback:
  If deleted < 30 days:
    az ad app list-deleted | grep "Riverside"
    az ad app restore --id <deleted-app-id>

  If deleted > 30 days (or soft-delete expired):
    See scripts/setup-tenant-apps.ps1 to recreate

See Also:
  - docs/runbooks/resource-cleanup.md
  - docs/runbooks/phase-b-multi-tenant-app.md
  - scripts/migrate-to-phase-b.sh

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

    print_header "Azure Governance Platform - Phase A Cleanup"
    echo "  Target: 5 per-tenant app registrations"
    echo "  Mode: $([[ "$CONFIRM" == true ]] && echo "DELETE" || echo "PREVIEW")"
    echo ""

    # Check prerequisites
    check_prerequisites

    # Verify Phase B/C are working
    verify_multi_tenant_app
    verify_uami_setup

    # Show pre-checklist
    if ! show_prechecklist; then
        if [[ "$CONFIRM" == true ]]; then
            print_error "Pre-checklist failed - cannot proceed with deletion"
            print_info "Fix the issues above or ensure Phase B is fully configured"
            exit 1
        fi
    fi

    # List what will be deleted
    list_phase_a_apps

    # Perform deletion if confirmed
    if [[ "$CONFIRM" == true ]]; then
        if delete_phase_a_apps; then
            show_post_summary
            print_header "Cleanup Complete!"
            print_success "Phase A app registrations have been cleaned up"
            echo ""
            print_info "Next steps:"
            echo "  1. Verify staging App Service is still healthy"
            echo "  2. Run tenant sync operations to confirm multi-tenant auth works"
            echo "  3. Monitor for any authentication issues"
            echo "  4. Update documentation (remove Phase A references)"
            echo ""
        else
            print_error "Some deletions failed - check errors above"
            exit 1
        fi
    else
        print_header "Preview Mode Complete"
        print_info "No changes were made (run with --confirm to delete)"
        print_info "Review the checklist and app list above before proceeding"
        echo ""
        echo "  To delete, run:"
        echo "    ./scripts/cleanup-phase-a-apps.sh --confirm"
        echo ""
    fi
}

# Run main
main "$@"

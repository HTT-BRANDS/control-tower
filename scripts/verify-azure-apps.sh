#!/usr/bin/env bash
#
# Riverside Azure Governance Platform - App Verification Script
#
# Quickly checks app registration status across all Riverside tenants.
#
# Usage:
#   ./scripts/verify-azure-apps.sh              # Check all tenants
#   ./scripts/verify-azure-apps.sh --tenant HTT # Check specific tenant
#   ./scripts/verify-azure-apps.sh --json       # Output JSON
#
# Prerequisites:
#   - Azure CLI (az) installed and logged in
#   - Appropriate permissions to read Azure AD
#

set -eo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Tenant Configuration (indexed arrays for bash 3.x compatibility)
TENANTS=(HTT BCC FN TLL DCE)
TENANT_NAMES=("Head to Toe Brands" "Bishops Cuts/Color" "Frenchies Nails" "The Lash Lounge" "Delta Crown Extensions")
TENANT_IDS=("0c0e35dc-188a-4eb3-b8ba-61752154b407" "b5380912-79ec-452d-a6ca-6d897b19b294" "98723287-044b-4bbb-9294-19857d4128a0" "3c7d2bf3-b597-4766-b5cb-2b489c2904d6" "ce62e17d-2feb-4e67-a115-8ea4af68da30")
APP_IDS=("1e3e8417-49f1-4d08-b7be-47045d8a12e9" "4861906b-2079-4335-923f-a55cc0e44d64" "7648d04d-ccc4-43ac-bace-da1b68bf11b4" "52531a02-78fd-44ba-9ab9-b29675767955" "79c22a10-3f2d-4e6a-bddc-ee65c9a46cb0")
ADMIN_UPNS=("tyler.granlund-admin@httbrands.com" "tyler.granlund-Admin@bishopsbs.onmicrosoft.com" "tyler.granlund-Admin@ftgfrenchiesoutlook.onmicrosoft.com" "tyler.granlund-Admin@LashLoungeFranchise.onmicrosoft.com" "tyler.granlund-admin_httbrands.com#EXT#@deltacrown.onmicrosoft.com")

# Script options
OUTPUT_JSON=false
SPECIFIC_TENANT=""
VERBOSE=false

# Results storage (use temp files for bash 3.x compatibility)
RESULT_EXISTS=""
RESULT_NAMES=""
RESULT_ENABLED=""
RESULT_CONSENT=""
RESULT_ERRORS=""

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

# Get index for a tenant code
get_index() {
    local code="$1"
    local i
    for i in ${!TENANTS[@]}; do
        if [[ "${TENANTS[$i]}" == "$code" ]]; then
            echo "$i"
            return 0
        fi
    done
    echo "-1"
    return 1
}

# Get array value at index
get_value() {
    local arr_name="$1"
    local idx="$2"
    eval "echo \"\${${arr_name}[$idx]}\""
}

# Set result value
set_result() {
    local var_name="$1"
    local idx="$2"
    local value="$3"
    eval "${var_name}_${idx}=\"$value\""
}

# Get result value
get_result() {
    local var_name="$1"
    local idx="$2"
    eval "echo \"\${${var_name}_${idx}:-}\""
}

# =============================================================================
# CHECK PREREQUISITES
# =============================================================================

check_prerequisites() {
    print_header "Checking Prerequisites"
    
    # Check Azure CLI
    if ! command -v az &> /dev/null; then
        print_error "Azure CLI (az) not found"
        echo ""
        echo "  Install from: https://aka.ms/installazurecli"
        echo "  Or use: brew install azure-cli (macOS)"
        exit 1
    fi
    
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
}

# =============================================================================
# CHECK TENANT APP
# =============================================================================

check_tenant_app() {
    local idx="$1"
    local code="${TENANTS[$idx]}"
    local tenant_id="${TENANT_IDS[$idx]}"
    local app_id="${APP_IDS[$idx]}"
    local admin_upn="${ADMIN_UPNS[$idx]}"
    local tenant_name="${TENANT_NAMES[$idx]}"
    
    print_step "Checking $code - $tenant_name"
    echo ""
    print_info "Tenant ID: $tenant_id"
    print_info "App ID: $app_id"
    print_info "Admin UPN: $admin_upn"
    echo ""
    
    # Try to get app info
    local app_data
    local error_msg=""
    
    app_data=$(az ad app show --id "$app_id" 2>&1) || {
        error_msg="App not found or no access"
        set_result "RESULT_EXISTS" "$idx" "false"
        set_result "RESULT_NAMES" "$idx" "N/A"
        set_result "RESULT_ENABLED" "$idx" "false"
        set_result "RESULT_CONSENT" "$idx" "unknown"
        set_result "RESULT_ERRORS" "$idx" "$error_msg"
        print_error "$error_msg"
        return 1
    }
    
    # App exists
    set_result "RESULT_EXISTS" "$idx" "true"
    set_result "RESULT_ERRORS" "$idx" ""
    
    # Get app name
    local app_name
    app_name=$(echo "$app_data" | jq -r '.displayName // "Unknown"')
    set_result "RESULT_NAMES" "$idx" "$app_name"
    print_success "App found: $app_name"
    
    # Check if enabled
    local sign_in_audience
    sign_in_audience=$(echo "$app_data" | jq -r '.signInAudience // ""')
    if [[ -n "$sign_in_audience" ]]; then
        set_result "RESULT_ENABLED" "$idx" "true"
        print_success "App is enabled"
    else
        set_result "RESULT_ENABLED" "$idx" "false"
        print_warning "App may not be enabled"
    fi
    
    # Check for service principal (indicates admin consent)
    local sp_data
    sp_data=$(az ad sp show --id "$app_id" 2>&1) || {
        set_result "RESULT_CONSENT" "$idx" "false"
        print_warning "No service principal found - admin consent may be needed"
        return 0
    }
    
    set_result "RESULT_CONSENT" "$idx" "true"
    print_success "Service principal found - admin consent appears granted"
    
    # List credentials count
    local cred_count
    cred_count=$(az ad app credential list --id "$app_id" --query "length(@)" -o tsv 2>/dev/null || echo "0")
    print_info "Client secrets: $cred_count"
    
    return 0
}

# =============================================================================
# PRINT SUMMARY TABLE
# =============================================================================

print_summary_table() {
    print_header "Summary"
    
    # Header
    printf "  ${BOLD}%-6s %-25s %-12s %-10s %-12s %-15s${NC}\n" \
        "Code" "Name" "App Exists" "Enabled" "Consent" "Status"
    printf "  %-6s %-25s %-12s %-10s %-12s %-15s\n" \
        "------" "-------------------------" "------------" "----------" "------------" "---------------"
    
    local total=0
    local found=0
    local ready=0
    
    for idx in ${!TENANTS[@]}; do
        local code="${TENANTS[$idx]}"
        
        if [[ -n "$SPECIFIC_TENANT" && "$code" != "$SPECIFIC_TENANT" ]]; then
            continue
        fi
        
        total=$((total + 1))
        
        local name="${TENANT_NAMES[$idx]}"
        local exists="$(get_result RESULT_EXISTS $idx)"
        local enabled="$(get_result RESULT_ENABLED $idx)"
        local consent="$(get_result RESULT_CONSENT $idx)"
        local error="$(get_result RESULT_ERRORS $idx)"
        
        # Format output
        local exists_str enabled_str consent_str status_str
        
        if [[ "$exists" == "true" ]]; then
            exists_str="${GREEN}Yes${NC}"
            found=$((found + 1))
        else
            exists_str="${RED}No${NC}"
        fi
        
        if [[ "$enabled" == "true" ]]; then
            enabled_str="${GREEN}Yes${NC}"
        elif [[ "$enabled" == "false" && "$exists" == "true" ]]; then
            enabled_str="${YELLOW}No${NC}"
        else
            enabled_str="${RED}Unknown${NC}"
        fi
        
        if [[ "$consent" == "true" ]]; then
            consent_str="${GREEN}Granted${NC}"
        elif [[ "$consent" == "false" ]]; then
            consent_str="${YELLOW}Needed${NC}"
        else
            consent_str="${RED}Unknown${NC}"
        fi
        
        if [[ -n "$error" ]]; then
            status_str="${RED}Error${NC}"
        elif [[ "$exists" == "true" && "$consent" == "true" ]]; then
            status_str="${GREEN}Ready${NC}"
            ready=$((ready + 1))
        elif [[ "$exists" == "true" ]]; then
            status_str="${YELLOW}Needs Setup${NC}"
        else
            status_str="${RED}Not Found${NC}"
        fi
        
        # Print row (with color codes)
        printf "  %-6s %-25s %-12b %-10b %-12b %-15b\n" \
            "$code" \
            "${name:0:25}" \
            "$exists_str" \
            "$enabled_str" \
            "$consent_str" \
            "$status_str"
        
        # Show error if verbose and exists
        if [[ "$VERBOSE" == "true" && -n "$error" ]]; then
            echo ""
            print_error "  Error: $error"
        fi
    done
    
    echo ""
    print_info "Total: $total | Found: $found | Ready: $ready"
}

# =============================================================================
# PRINT JSON OUTPUT
# =============================================================================

print_json_output() {
    local first=true
    echo "{"
    echo '  "tenants": ['
    
    for idx in ${!TENANTS[@]}; do
        local code="${TENANTS[$idx]}"
        
        if [[ -n "$SPECIFIC_TENANT" && "$code" != "$SPECIFIC_TENANT" ]]; then
            continue
        fi
        
        if [[ "$first" == "true" ]]; then
            first=false
        else
            echo ","
        fi
        
        local exists="$(get_result RESULT_EXISTS $idx)"
        local enabled="$(get_result RESULT_ENABLED $idx)"
        local consent="$(get_result RESULT_CONSENT $idx)"
        local error="$(get_result RESULT_ERRORS $idx)"
        local name="$(get_result RESULT_NAMES $idx)"
        
        [[ -z "$exists" ]] && exists="false"
        [[ -z "$enabled" ]] && enabled="false"
        [[ -z "$consent" ]] && consent="unknown"
        [[ -z "$error" ]] && error=""
        [[ -z "$name" ]] && name="Unknown"
        
        cat <<EOF
    {
      "code": "$code",
      "name": "${TENANT_NAMES[$idx]}",
      "tenant_id": "${TENANT_IDS[$idx]}",
      "app_id": "${APP_IDS[$idx]}",
      "app_exists": $exists,
      "app_name": "$name",
      "enabled": $enabled,
      "admin_consent": "$consent",
      "error": "$error"
    }
EOF
    done
    
    echo ""
    echo "  ]"
    echo "}"
}

# =============================================================================
# PRINT DETAILED REPORT
# =============================================================================

print_detailed_report() {
    print_header "Detailed Report"
    
    for idx in ${!TENANTS[@]}; do
        local code="${TENANTS[$idx]}"
        
        if [[ -n "$SPECIFIC_TENANT" && "$code" != "$SPECIFIC_TENANT" ]]; then
            continue
        fi
        
        local exists="$(get_result RESULT_EXISTS $idx)"
        local name="$(get_result RESULT_NAMES $idx)"
        local enabled="$(get_result RESULT_ENABLED $idx)"
        local consent="$(get_result RESULT_CONSENT $idx)"
        local error="$(get_result RESULT_ERRORS $idx)"
        
        [[ -z "$name" ]] && name="N/A"
        [[ -z "$exists" ]] && exists="unknown"
        [[ -z "$enabled" ]] && enabled="unknown"
        [[ -z "$consent" ]] && consent="unknown"
        
        echo ""
        echo "  ${BOLD}$code - ${TENANT_NAMES[$idx]}${NC}"
        echo "  ----------------------------------------------------------------------"
        echo "    Tenant ID:     ${TENANT_IDS[$idx]}"
        echo "    App ID:        ${APP_IDS[$idx]}"
        echo "    Admin UPN:     ${ADMIN_UPNS[$idx]}"
        echo ""
        echo "    App Exists:    $exists"
        echo "    App Name:      $name"
        echo "    Enabled:       $enabled"
        echo "    Admin Consent: $consent"
        
        if [[ -n "$error" ]]; then
            echo ""
            print_error "    Error: $error"
        fi
    done
    
    echo ""
}

# =============================================================================
# USAGE
# =============================================================================

print_usage() {
    cat <<EOF
Riverside Azure Governance Platform - App Verification Script

Usage:
  ./scripts/verify-azure-apps.sh [options]

Options:
  --tenant CODE    Check only specific tenant (HTT, BCC, FN, TLL, DCE)
  --json           Output results as JSON
  --verbose        Show detailed error messages
  --help           Show this help message

Examples:
  ./scripts/verify-azure-apps.sh              # Check all tenants
  ./scripts/verify-azure-apps.sh --tenant HTT # Check HTT tenant only
  ./scripts/verify-azure-apps.sh --json       # JSON output

Required Permissions:
  - Azure AD: Application.Read.All or equivalent
  - Azure AD: ServicePrincipal.Read.All (for consent check)

Prerequisites:
  - Azure CLI installed and logged in
  - Appropriate Azure AD permissions

EOF
}

# =============================================================================
# MAIN
# =============================================================================

main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --tenant)
                SPECIFIC_TENANT="$2"
                shift 2
                ;;
            --json)
                OUTPUT_JSON=true
                shift
                ;;
            --verbose)
                VERBOSE=true
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
    
    # Validate specific tenant
    if [[ -n "$SPECIFIC_TENANT" ]]; then
        local valid=false
        local idx
        for idx in ${!TENANTS[@]}; do
            if [[ "${TENANTS[$idx]}" == "$SPECIFIC_TENANT" ]]; then
                valid=true
                break
            fi
        done
        
        if [[ "$valid" != "true" ]]; then
            echo "Error: Invalid tenant code '$SPECIFIC_TENANT'"
            echo "Valid codes: ${TENANTS[*]}"
            exit 1
        fi
    fi
    
    # Check prerequisites
    check_prerequisites
    
    # Process tenants
    print_header "Checking App Registrations"
    
    for idx in ${!TENANTS[@]}; do
        local code="${TENANTS[$idx]}"
        
        if [[ -n "$SPECIFIC_TENANT" && "$code" != "$SPECIFIC_TENANT" ]]; then
            continue
        fi
        
        check_tenant_app "$idx" || true
        echo ""
    done
    
    # Output results
    if [[ "$OUTPUT_JSON" == "true" ]]; then
        print_json_output
    else
        print_summary_table
        
        if [[ "$VERBOSE" == "true" ]]; then
            print_detailed_report
        fi
        
        # Print next steps
        print_header "Next Steps"
        
        local needs_setup=()
        local needs_consent=()
        
        for idx in ${!TENANTS[@]}; do
            local code="${TENANTS[$idx]}"
            
            if [[ -n "$SPECIFIC_TENANT" && "$code" != "$SPECIFIC_TENANT" ]]; then
                continue
            fi
            
            local exists="$(get_result RESULT_EXISTS $idx)"
            local consent="$(get_result RESULT_CONSENT $idx)"
            
            if [[ "$exists" != "true" ]]; then
                needs_setup+=("$code")
            elif [[ "$consent" != "true" ]]; then
                needs_consent+=("$code")
            fi
        done
        
        if [[ ${#needs_setup[@]} -gt 0 ]]; then
            echo ""
            print_warning "Apps needing setup: ${needs_setup[*]}"
            echo "  Run: python scripts/setup-riverside-apps.py --full-setup"
        fi
        
        if [[ ${#needs_consent[@]} -gt 0 ]]; then
            echo ""
            print_warning "Apps needing admin consent: ${needs_consent[*]}"
            echo "  Grant consent in Azure Portal > Enterprise Applications"
        fi
        
        if [[ ${#needs_setup[@]} -eq 0 && ${#needs_consent[@]} -eq 0 ]]; then
            echo ""
            print_success "All apps are configured and ready!"
        fi
        
        echo ""
        print_info "For detailed setup, run:"
        echo "  python scripts/setup-riverside-apps.py --check-only"
        echo ""
    fi
}

# Run main
main "$@"

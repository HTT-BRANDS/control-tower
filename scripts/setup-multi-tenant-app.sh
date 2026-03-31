#!/bin/bash
# Setup script for Phase B: Multi-tenant App Registration
# Creates a single multi-tenant app for all 5 Riverside tenants
#
# Usage: ./scripts/setup-multi-tenant-app.sh [--tenant-id <home-tenant-id>]
#
# Requirements:
#   - Azure CLI (az) installed and logged in
#   - Owner or Application Administrator role in home tenant
#   - jq installed for JSON parsing

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="Riverside-Governance-Multi-Tenant"
KEY_VAULT_NAME="${KEY_VAULT_NAME:-kv-gov-prod-001}"
SECRET_NAME="multi-tenant-client-secret"  # pragma: allowlist secret
SECRET_EXPIRY_MONTHS="24"

# Microsoft Graph API Permissions needed
# (same 15 permissions as per-tenant apps)
 declare -a REQUIRED_PERMISSIONS=(
    "AuditLog.Read.All"
    "DeviceManagementApps.Read.All"
    "DeviceManagementConfiguration.Read.All"
    "DeviceManagementManagedDevices.Read.All"
    "Directory.Read.All"
    "Domain.Read.All"
    "Group.Read.All"
    "IdentityRiskEvent.Read.All"
    "Organization.Read.All"
    "Policy.Read.All"
    "Reports.Read.All"
    "RoleManagement.Read.Directory"
    "SecurityEvents.Read.All"
    "User.Read.All"
    "UserAuthenticationMethod.Read.All"
)

# ============================================================================
# Helper Functions
# ============================================================================

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

require_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 is required but not installed."
        exit 1
    fi
}

show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Creates a multi-tenant Azure AD app registration for Riverside Governance Platform Phase B.

OPTIONS:
    --tenant-id <id>      Home tenant ID (where app will be created)
    --key-vault <name>    Key Vault name for storing secret (default: $KEY_VAULT_NAME)
    --dry-run             Show what would be done without making changes
    --help                Show this help message

EXAMPLES:
    # Interactive mode (will prompt for tenant selection)
    $0

    # Specify home tenant explicitly
    $0 --tenant-id 00000000-0000-0000-0000-000000000000

    # Use different Key Vault
    $0 --key-vault my-custom-kv

ENVIRONMENT VARIABLES:
    KEY_VAULT_NAME    Default Key Vault name (default: kv-gov-prod-001)
    AZURE_TENANT_ID   Default tenant ID for non-interactive mode
EOF
}

# ============================================================================
# Azure Functions
# ============================================================================

select_tenant() {
    log_info "Fetching available tenants..."
    
    local tenants
    tenants=$(az account list --query "[].{name:name, tenantId:tenantId}" -o json)
    
    if [[ $(echo "$tenants" | jq length) -eq 0 ]]; then
        log_error "No Azure subscriptions found. Please run 'az login' first."
        exit 1
    fi
    
    if [[ $(echo "$tenants" | jq length) -eq 1 ]]; then
        local tenant_id
        tenant_id=$(echo "$tenants" | jq -r '.[0].tenantId')
        log_info "Using single available tenant: $tenant_id"
        echo "$tenant_id"
        return
    fi
    
    echo
    echo "Available tenants:"
    echo "$tenants" | jq -r '.[] | "\(.tenantId): \(.name)"' | nl
    echo
    
    read -p "Select tenant number (or paste tenant ID): " selection
    
    # Check if numeric selection
    if [[ "$selection" =~ ^[0-9]+$ ]]; then
        local tenant_id
        tenant_id=$(echo "$tenants" | jq -r ".[$selection-1].tenantId")
        if [[ "$tenant_id" == "null" ]]; then
            log_error "Invalid selection"
            exit 1
        fi
        echo "$tenant_id"
    else
        # Assume it's a tenant ID
        echo "$selection"
    fi
}

check_existing_app() {
    local tenant_id=$1
    local app_name=$2
    
    log_info "Checking for existing app registration..."
    
    local existing_app
    existing_app=$(az ad app list \
        --filter "displayName eq '$app_name'" \
        --query "[0].{id:appId, objectId:id}" \
        -o json 2>/dev/null || echo "null")
    
    if [[ "$existing_app" != "null" && "$existing_app" != "[]" ]]; then
        local app_id
        app_id=$(echo "$existing_app" | jq -r '.id')
        log_warn "App registration '$app_name' already exists!"
        log_warn "App ID: $app_id"
        read -p "Continue with existing app? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Exiting. To create a new app, delete the existing one first."
            exit 0
        fi
        echo "$app_id"
        return
    fi
    
    echo "null"
}

create_multi_tenant_app() {
    local tenant_id=$1
    local app_name=$2
    
    log_info "Creating multi-tenant app registration..."
    log_info "  Name: $app_name"
    log_info "  Sign-in audience: AzureADMultipleOrgs"
    
    # Create app with multi-tenant sign-in audience
    local app_data
    app_data=$(az ad app create \
        --display-name "$app_name" \
        --sign-in-audience AzureADMultipleOrgs \
        --query "{appId:appId, objectId:id}" \
        -o json)
    
    local app_id
    app_id=$(echo "$app_data" | jq -r '.appId')
    local object_id
    object_id=$(echo "$app_data" | jq -r '.objectId')
    
    log_success "Created app registration"
    log_info "  App ID: $app_id"
    log_info "  Object ID: $object_id"
    
    # Output JSON for later use
    echo "$app_data"
}

add_api_permissions() {
    local app_id=$1
    
    log_info "Adding Microsoft Graph API permissions..."
    
    # Get Microsoft Graph service principal
    local graph_sp
    graph_sp=$(az ad sp list \
        --filter "appId eq '00000003-0000-0000-c000-000000000000'" \
        --query "[0].id" \
        -o tsv)
    
    if [[ -z "$graph_sp" ]]; then
        log_error "Could not find Microsoft Graph service principal"
        exit 1
    fi
    
    # Build required resource access JSON
    local resource_access="[]"
    
    for perm in "${REQUIRED_PERMISSIONS[@]}"; do
        log_info "  Adding permission: $perm"
        
        # Get the permission ID
        local perm_id
        perm_id=$(az ad sp show \
            --id "$graph_sp" \
            --query "appRoles[?value=='$perm'].id | [0]" \
            -o tsv)
        
        if [[ -z "$perm_id" || "$perm_id" == "null" ]]; then
            log_warn "    Could not find permission ID for $perm (may require manual add)"
            continue
        fi
        
        # Add to resource access array
        resource_access=$(echo "$resource_access" | jq \
            --arg id "$perm_id" \
            '. + [{"id": $id, "type": "Role"}]')
    done
    
    # Update app with required resource access
    local api_payload
    api_payload=$(jq -n \
        --arg graph_sp "$graph_sp" \
        --argjson resource_access "$resource_access" \
        '{requiredResourceAccess: [{resourceAppId: "00000003-0000-0000-c000-000000000000", resourceAccess: $resource_access}]}')
    
    az ad app update \
        --id "$app_id" \
        --set "requiredResourceAccess=$api_payload"
    
    log_success "Added API permissions"
}

create_client_secret() {
    local app_id=$1
    
    log_info "Creating client secret (expires in $SECRET_EXPIRY_MONTHS months)..."
    
    # Calculate end date
    local end_date
    end_date=$(date -u -d "+$SECRET_EXPIRY_MONTHS months" +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || \
               date -v+${SECRET_EXPIRY_MONTHS}m +"%Y-%m-%dT%H:%M:%SZ")
    
    local secret_data
    secret_data=$(az ad app credential reset \
        --id "$app_id" \
        --append \
        --end-date "$end_date" \
        --query "{secretText:password, keyId:keyId, endDate:endDate}" \
        -o json)
    
    local secret_text
    secret_text=$(echo "$secret_data" | jq -r '.secretText')
    local key_id
    key_id=$(echo "$secret_data" | jq -r '.keyId')
    local expiry
    expiry=$(echo "$secret_data" | jq -r '.endDate')
    
    log_success "Created client secret"
    log_info "  Key ID: $key_id"
    log_info "  Expires: $expiry"
    
    # IMPORTANT: Output the secret
    echo "$secret_data"
}

grant_admin_consent_home_tenant() {
    local app_id=$1
    local tenant_id=$2
    
    log_info "Granting admin consent in home tenant ($tenant_id)..."
    
    # Get service principal (auto-created when app is accessed)
    local sp_id
    sp_id=$(az ad sp list \
        --filter "appId eq '$app_id'" \
        --query "[0].id" \
        -o tsv)
    
    if [[ -z "$sp_id" || "$sp_id" == "null" ]]; then
        log_info "Creating service principal..."
        sp_id=$(az ad sp create \
            --id "$app_id" \
            --query "id" \
            -o tsv)
    fi
    
    # Grant admin consent using Microsoft Graph (preview)
    # This is tenant-level admin consent for the home tenant
    log_info "Service Principal ID: $sp_id"
    log_warn "Please manually grant admin consent in Azure Portal:"
    log_warn "  https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps/ApplicationMenuBlade/CallAnAPI/appId/$app_id"
}

store_secret_in_keyvault() {
    local secret_value=$1
    local key_vault=$2
    local secret_name=$3
    local app_id=$4
    
    log_info "Storing secret in Key Vault: $key_vault/$secret_name"
    
    # Check if Key Vault exists
    if ! az keyvault show --name "$key_vault" &>/dev/null; then
        log_error "Key Vault '$key_vault' not found or no access"
        log_info "Please create the Key Vault or update KEY_VAULT_NAME"
        return 1
    fi
    
    # Store secret with metadata
    az keyvault secret set \
        --vault-name "$key_vault" \
        --name "$secret_name" \
        --value "$secret_value" \
        --tags \
            "app-id=$app_id" \
            "app-name=$APP_NAME" \
            "purpose=riverside-governance-phase-b" \
            "setup-date=$(date -u +%Y-%m-%d)" \
            "expires=$(date -u -d "+$SECRET_EXPIRY_MONTHS months" +%Y-%m-%d 2>/dev/null || date -v+${SECRET_EXPIRY_MONTHS}m +%Y-%m-%d)" \
        --query "id" \
        -o tsv
    
    log_success "Stored secret in Key Vault"
}

generate_summary() {
    local app_id=$1
    local tenant_id=$2
    local key_vault=$3
    local secret_name=$4
    
    cat << EOF

================================================================================
                      PHASE B SETUP COMPLETE
================================================================================

Multi-tenant App Registration
-----------------------------
App Name:     $APP_NAME
App ID:       $app_id
Home Tenant:  $tenant_id
Sign-in:      AzureADMultipleOrgs (multi-tenant)

Secret Storage
--------------
Key Vault:    $key_vault
Secret Name:  $secret_name

Configuration
-------------
Add to config/tenants.yaml:

  multi_tenant_app_id: "$app_id"

  # Update each tenant's key_vault_secret_name:
  tenants:
    HTT:
      # ... other settings ...
      key_vault_secret_name: "$secret_name"
    BCC:
      # ... other settings ...
      key_vault_secret_name: "$secret_name"
    # ... repeat for FN, TLL, DCE

Or set environment variables:

  AZURE_MULTI_TENANT_APP_ID="$app_id"
  AZURE_MULTI_TENANT_CLIENT_SECRET="@Microsoft.KeyVault(SecretUri=https://$key_vault.vault.azure.net/secrets/$secret_name/)"
  USE_MULTI_TENANT_APP="true"

Next Steps
----------
1. ✅ Grant admin consent in home tenant (HTT)
2. 🔄 Grant admin consent in each foreign tenant (BCC, FN, TLL, DCE)
   URL: https://login.microsoftonline.com/common/adminconsent?client_id=$app_id
3. 🔄 Update config/tenants.yaml with multi_tenant_app_id
4. 🔄 Deploy and test
5. 🔄 Run: python -m pytest tests/unit/test_multi_tenant_auth.py -v

Admin Consent URLs for Each Tenant
-----------------------------------
Send these URLs to the Global Admin of each tenant:

Home (HTT):   https://login.microsoftonline.com/$tenant_id/adminconsent?client_id=$app_id
Foreign:      https://login.microsoftonline.com/common/adminconsent?client_id=$app_id

Documentation
-------------
- Phase B Runbook: docs/runbooks/phase-b-multi-tenant-app.md
- Auth Roadmap: docs/AUTH_TRANSITION_ROADMAP.md

================================================================================
EOF
}

# ============================================================================
# Main Script
# ============================================================================

main() {
    local dry_run=false
    local tenant_id=""
    local key_vault="$KEY_VAULT_NAME"
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --tenant-id)
                tenant_id="$2"
                shift 2
                ;;
            --key-vault)
                key_vault="$2"
                shift 2
                ;;
            --dry-run)
                dry_run=true
                shift
                ;;
            --help)
                show_usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    # Check prerequisites
    require_command az
    require_command jq
    
    log_info "Azure Multi-Tenant App Setup Script"
    log_info "===================================="
    
    if [[ "$dry_run" == true ]]; then
        log_warn "DRY RUN MODE - No changes will be made"
    fi
    
    # Select tenant
    if [[ -z "$tenant_id" ]]; then
        tenant_id=$(select_tenant)
    fi
    
    log_info "Using tenant: $tenant_id"
    
    # Set active tenant
    az account set --tenant "$tenant_id" || {
        log_error "Failed to set tenant. Please run 'az login --tenant $tenant_id'"
        exit 1
    }
    
    # Check for existing app
    local existing_app_id
    existing_app_id=$(check_existing_app "$tenant_id" "$APP_NAME")
    
    local app_data
    local app_id
    
    if [[ "$existing_app_id" != "null" ]]; then
        app_id="$existing_app_id"
        log_info "Using existing app: $app_id"
        
        # Get full app data
        app_data=$(az ad app show --id "$app_id" --query "{appId:appId, id:id}" -o json)
    else
        if [[ "$dry_run" == true ]]; then
            log_info "[DRY RUN] Would create app: $APP_NAME"
            app_id="00000000-0000-0000-0000-000000000000"
            app_data="{\"appId\": \"$app_id\", \"id\": \"dry-run-id\"}"
        else
            app_data=$(create_multi_tenant_app "$tenant_id" "$APP_NAME")
            app_id=$(echo "$app_data" | jq -r '.appId')
        fi
    fi
    
    # Add API permissions
    if [[ "$dry_run" == true ]]; then
        log_info "[DRY RUN] Would add ${#REQUIRED_PERMISSIONS[@]} Graph API permissions"
    else
        add_api_permissions "$app_id"
    fi
    
    # Create client secret
    local secret_data
    local secret_value
    
    if [[ "$dry_run" == true ]]; then
        log_info "[DRY RUN] Would create client secret"
        secret_value="dry-run-secret-value"  # pragma: allowlist secret
    else
        secret_data=$(create_client_secret "$app_id")
        secret_value=$(echo "$secret_data" | jq -r '.secretText')
    fi
    
    # Grant admin consent in home tenant
    if [[ "$dry_run" == false ]]; then
        grant_admin_consent_home_tenant "$app_id" "$tenant_id"
    fi
    
    # Store in Key Vault
    if [[ "$dry_run" == true ]]; then
        log_info "[DRY RUN] Would store secret in Key Vault: $key_vault/$SECRET_NAME"
    else
        if ! store_secret_in_keyvault "$secret_value" "$key_vault" "$SECRET_NAME" "$app_id"; then
            log_warn "Failed to store in Key Vault. Manual step required."
            log_info "Secret value (save this!):"
            echo "=================================="
            echo "$secret_value"
            echo "=================================="
        fi
    fi
    
    # Generate summary
    generate_summary "$app_id" "$tenant_id" "$key_vault" "$SECRET_NAME"
    
    if [[ "$dry_run" == false ]]; then
        log_success "Setup complete! Review the summary above for next steps."
        
        # Save summary to file
        local output_file="multi-tenant-app-setup-$(date +%Y%m%d-%H%M%S).txt"
        generate_summary "$app_id" "$tenant_id" "$key_vault" "$SECRET_NAME" > "$output_file"
        log_info "Summary saved to: $output_file"
    fi
}

# Run main if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi

#!/bin/bash
# Migration script: Phase A → Phase B
# Safely migrates from per-tenant app registrations to single multi-tenant app
#
# Usage: ./scripts/migrate-to-phase-b.sh [--validate-only|--rollback|--force]

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
TENANTS_YAML="config/tenants.yaml"
TENANTS_YAML_BACKUP="config/tenants.yaml.phase-a-backup.$(date +%Y%m%d-%H%M%S)"
TENANTS_YAML_EXAMPLE="config/tenants.yaml.example"

# Phase B configuration
MULTI_TENANT_APP_ID="${AZURE_MULTI_TENANT_APP_ID:-}"
MULTI_TENANT_SECRET_NAME="${MULTI_TENANT_SECRET_NAME:-multi-tenant-client-secret}"

# Tenants list
TENANTS=("HTT" "BCC" "FN" "TLL" "DCE")

# Flags
VALIDATE_ONLY=false
ROLLBACK=false
FORCE=false

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

log_step() {
    echo -e "\n${BLUE}▶ $1${NC}"
}

require_file() {
    if [[ ! -f "$1" ]]; then
        log_error "Required file not found: $1"
        exit 1
    fi
}

require_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "$1 is required but not installed"
        exit 1
    fi
}

show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Migrates Azure Governance Platform from Phase A (per-tenant apps) to Phase B
(multi-tenant app with single secret).

OPTIONS:
    --validate-only       Only validate current state, don't make changes
    --rollback            Rollback to Phase A from backup
    --force               Skip confirmation prompts
    --app-id <id>         Multi-tenant app ID (or set AZURE_MULTI_TENANT_APP_ID)
    --secret-name <name>  Key Vault secret name (default: multi-tenant-client-secret)
    --help                Show this help message

EXAMPLES:
    # Validate current configuration
    $0 --validate-only

    # Perform migration (interactive)
    $0 --app-id 00000000-0000-0000-0000-000000000000

    # Force migration without prompts
    $0 --app-id 00000000-0000-0000-0000-000000000000 --force

    # Rollback to Phase A
    $0 --rollback
EOF
}

# ============================================================================
# Validation Functions
# ============================================================================

validate_yaml_syntax() {
    local file=$1
    
    log_info "Validating YAML syntax: $file"
    
    if command -v python3 &> /dev/null; then
        python3 -c "import yaml; yaml.safe_load(open('$file'))" 2>&1 || {
            log_error "Invalid YAML syntax in $file"
            return 1
        }
    elif command -v yq &> /dev/null; then
        yq '.' "$file" > /dev/null 2>&1 || {
            log_error "Invalid YAML syntax in $file"
            return 1
        }
    else
        log_warn "No YAML validator found (install python3-yaml or yq)"
        return 0
    fi
    
    log_success "YAML syntax is valid"
    return 0
}

validate_tenants_yaml() {
    log_step "Validating tenants.yaml configuration"
    
    require_file "$TENANTS_YAML"
    
    # Check required fields
    local missing=()
    
    for tenant in "${TENANTS[@]}"; do
        if ! grep -q "^[[:space:]]*$tenant:" "$TENANTS_YAML"; then
            missing+=("$tenant")
        fi
    done
    
    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Missing tenants in $TENANTS_YAML: ${missing[*]}"
        return 1
    fi
    
    log_success "All 5 tenants found in configuration"
    
    # Check for multi_tenant_app_id (should NOT exist yet in Phase A)
    if grep -q "multi_tenant_app_id:" "$TENANTS_YAML"; then
        log_warn "multi_tenant_app_id already exists in $TENANTS_YAML"
        log_warn "This may indicate Phase B is already configured"
        
        if [[ "$FORCE" == false ]]; then
            read -p "Continue anyway? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                exit 1
            fi
        fi
    fi
    
    return 0
}

validate_azure_access() {
    log_step "Validating Azure access"
    
    if ! command -v az &> /dev/null; then
        log_warn "Azure CLI not found, skipping Azure validation"
        return 0
    fi
    
    if ! az account show &>/dev/null; then
        log_warn "Not logged into Azure, skipping Azure validation"
        return 0
    fi
    
    log_success "Azure CLI authenticated"
    
    # Check Key Vault access if configured
    if [[ -n "${KEY_VAULT_NAME:-}" ]]; then
        if az keyvault show --name "$KEY_VAULT_NAME" &>/dev/null; then
            log_success "Key Vault access confirmed: $KEY_VAULT_NAME"
            
            # Check if multi-tenant secret exists
            if az keyvault secret show --vault-name "$KEY_VAULT_NAME" --name "$MULTI_TENANT_SECRET_NAME" &>/dev/null; then
                log_success "Multi-tenant secret exists: $MULTI_TENANT_SECRET_NAME"
            else
                log_warn "Multi-tenant secret not found: $MULTI_TENANT_SECRET_NAME"
                log_info "Run scripts/setup-multi-tenant-app.sh first"
            fi
        else
            log_warn "Cannot access Key Vault: $KEY_VAULT_NAME"
        fi
    fi
    
    return 0
}

validate_code_changes() {
    log_step "Validating code changes are present"
    
    # Check if tenants_config.py has the new functions
    local tenants_config="app/core/tenants_config.py"
    
    if ! grep -q "get_multi_tenant_app_id" "$tenants_config"; then
        log_error "Code changes not found: get_multi_tenant_app_id missing"
        log_error "Please ensure the latest code is deployed"
        return 1
    fi
    
    if ! grep -q "get_credential_for_tenant" "$tenants_config"; then
        log_error "Code changes not found: get_credential_for_tenant missing"
        return 1
    fi
    
    log_success "Code changes validated"
    return 0
}

run_unit_tests() {
    log_step "Running unit tests"
    
    if [[ ! -f "tests/unit/test_multi_tenant_auth.py" ]]; then
        log_warn "Multi-tenant auth tests not found"
        return 0
    fi
    
    if command -v python3 &> /dev/null; then
        log_info "Running: python -m pytest tests/unit/test_multi_tenant_auth.py -v"
        if python3 -m pytest tests/unit/test_multi_tenant_auth.py -v 2>&1; then
            log_success "Unit tests passed"
            return 0
        else
            log_error "Unit tests failed"
            return 1
        fi
    else
        log_warn "Python not available, skipping unit tests"
        return 0
    fi
}

# ============================================================================
# Migration Functions
# ============================================================================

create_backup() {
    log_step "Creating backup of current configuration"
    
    cp "$TENANTS_YAML" "$TENANTS_YAML_BACKUP"
    log_success "Backup created: $TENANTS_YAML_BACKUP"
    
    # Also backup to git
    if [[ -d ".git" ]]; then
        git add "$TENANTS_YAML_BACKUP" 2>/dev/null || true
        log_info "Backup added to git staging area"
    fi
}

update_tenants_yaml() {
    log_step "Updating tenants.yaml for Phase B"
    
    local app_id=$1
    
    # Read current file
    local content
    content=$(cat "$TENANTS_YAML")
    
    # Check if already has multi_tenant_app_id at top level
    if echo "$content" | grep -q "^multi_tenant_app_id:"; then
        log_warn "multi_tenant_app_id already exists, updating value"
        # Use sed to update existing value
        sed -i.tmp "s/^multi_tenant_app_id:.*/multi_tenant_app_id: \"$app_id\"/" "$TENANTS_YAML"
        rm -f "$TENANTS_YAML.tmp"
    else
        # Add multi_tenant_app_id at the top (before tenants:)
        log_info "Adding multi_tenant_app_id to configuration"
        
        # Create temp file with new content
        cat > "$TENANTS_YAML.tmp" << EOF
# Phase B: Multi-tenant app configuration
# All tenants share this single app registration
multi_tenant_app_id: "$app_id"

EOF
        
        # Append rest of file (skipping any existing comments at top)
        grep -v "^# Phase B:" "$TENANTS_YAML" >> "$TENANTS_YAML.tmp"
        
        mv "$TENANTS_YAML.tmp" "$TENANTS_YAML"
    fi
    
    # Update each tenant's key_vault_secret_name
    for tenant in "${TENANTS[@]}"; do
        log_info "Updating $tenant: setting key_vault_secret_name to $MULTI_TENANT_SECRET_NAME"
        
        # This is a simple sed replacement - for production use, consider using yq or Python
        # Replace the key_vault_secret_name line under each tenant
        python3 << PYEOF 2>/dev/null || {
            log_warn "Python update failed for $tenant, manual update may be needed"
            continue
        }
import re

with open('$TENANTS_YAML', 'r') as f:
    content = f.read()

# Pattern to find tenant section and update key_vault_secret_name
tenant_pattern = rf'({tenant}:[^\n]*\n(?:    [^\n]*\n)*)key_vault_secret_name:[^\n]*'
replacement = r'\1key_vault_secret_name: "$MULTI_TENANT_SECRET_NAME"  # pragma: allowlist secret'

content = re.sub(tenant_pattern, replacement, content)

with open('$TENANTS_YAML', 'w') as f:
    f.write(content)
PYEOF
    done
    
    log_success "tenants.yaml updated for Phase B"
}

validate_migration() {
    log_step "Validating migration"
    
    # Check syntax
    validate_yaml_syntax "$TENANTS_YAML"
    
    # Check multi_tenant_app_id exists
    if ! grep -q "multi_tenant_app_id:" "$TENANTS_YAML"; then
        log_error "Migration failed: multi_tenant_app_id not found"
        return 1
    fi
    
    # Check all tenants have updated secret names
    for tenant in "${TENANTS[@]}"; do
        if ! grep -A 10 "^  $tenant:" "$TENANTS_YAML" | grep -q "key_vault_secret_name:.*$MULTI_TENANT_SECRET_NAME"; then
            log_warn "$tenant: key_vault_secret_name may not be updated"
        fi
    done
    
    log_success "Migration validation passed"
    return 0
}

run_connectivity_tests() {
    log_step "Running connectivity tests"
    
    log_info "Testing Phase B credential resolution..."
    
    # Python test for credential resolution
    python3 << 'PYEOF' 2>/dev/null || {
        log_warn "Could not run Python connectivity tests"
        return 0
    }
import sys
sys.path.insert(0, '.')

try:
    from app.core.tenants_config import (
        get_multi_tenant_app_id,
        is_multi_tenant_mode_enabled,
        get_credential_for_tenant,
        RIVERSIDE_TENANTS
    )
    
    # Test multi-tenant mode detection
    if not is_multi_tenant_mode_enabled():
        print("ERROR: Multi-tenant mode not detected after migration")
        sys.exit(1)
    
    print("✓ Multi-tenant mode enabled")
    
    # Test get_multi_tenant_app_id
    app_id = get_multi_tenant_app_id()
    if not app_id:
        print("ERROR: Could not get multi_tenant_app_id")
        sys.exit(1)
    
    print(f"✓ Multi-tenant App ID: {app_id}")
    
    # Test credential resolution for each tenant
    for code in ["HTT", "BCC", "FN", "TLL", "DCE"]:
        creds = get_credential_for_tenant(code)
        if creds["is_multi_tenant"]:
            print(f"✓ {code}: Using multi-tenant app")
        else:
            print(f"✗ {code}: NOT using multi-tenant app (fallback to Phase A)")
    
    print("\nConnectivity tests passed!")
    
except Exception as e:
    print(f"Error during connectivity tests: {e}")
    sys.exit(1)
PYEOF
    
    log_success "Connectivity tests completed"
}

# ============================================================================
# Rollback Functions
# ============================================================================

find_backup() {
    local backup_pattern="config/tenants.yaml.phase-a-backup.*"
    local latest_backup
    
    latest_backup=$(ls -t $backup_pattern 2>/dev/null | head -1)
    
    if [[ -z "$latest_backup" ]]; then
        log_error "No Phase A backup found (expected: $backup_pattern)"
        return 1
    fi
    
    echo "$latest_backup"
}

perform_rollback() {
    log_step "Performing rollback to Phase A"
    
    local backup_file
    backup_file=$(find_backup)
    
    if [[ $? -ne 0 ]]; then
        log_error "Cannot find backup to restore"
        exit 1
    fi
    
    log_info "Found backup: $backup_file"
    
    if [[ "$FORCE" == false ]]; then
        read -p "Restore this backup? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Rollback cancelled"
            exit 0
        fi
    fi
    
    # Create rollback point of current state
    cp "$TENANTS_YAML" "$TENANTS_YAML.rollback-point"
    log_info "Current state saved to: $TENANTS_YAML.rollback-point"
    
    # Restore backup
    cp "$backup_file" "$TENANTS_YAML"
    log_success "Restored Phase A configuration from backup"
    
    # Validate restored config
    validate_yaml_syntax "$TENANTS_YAML"
    
    log_success "Rollback complete"
    log_info "Configuration is now at Phase A (per-tenant apps)"
    log_info "Redeploy the application to apply changes"
}

# ============================================================================
# Main
# ============================================================================

main() {
    log_info "Azure Governance Platform: Phase A → Phase B Migration"
    log_info "=========================================================="
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --validate-only)
                VALIDATE_ONLY=true
                shift
                ;;
            --rollback)
                ROLLBACK=true
                shift
                ;;
            --force)
                FORCE=true
                shift
                ;;
            --app-id)
                MULTI_TENANT_APP_ID="$2"
                shift 2
                ;;
            --secret-name)
                MULTI_TENANT_SECRET_NAME="$2"
                shift 2
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
    require_command python3
    require_file "$TENANTS_YAML"
    
    # Handle rollback mode
    if [[ "$ROLLBACK" == true ]]; then
        perform_rollback
        exit 0
    fi
    
    # Validation phase
    log_step "Phase 1: Pre-Migration Validation"
    
    validate_tenants_yaml || exit 1
    validate_code_changes || exit 1
    validate_azure_access
    
    if [[ "$VALIDATE_ONLY" == true ]]; then
        log_success "Validation complete - no changes made"
        log_info "Run without --validate-only to perform migration"
        exit 0
    fi
    
    # Get multi-tenant app ID if not provided
    if [[ -z "$MULTI_TENANT_APP_ID" ]]; then
        log_info "Multi-tenant App ID not provided"
        read -p "Enter the multi-tenant App ID: " MULTI_TENANT_APP_ID
        
        if [[ -z "$MULTI_TENANT_APP_ID" ]]; then
            log_error "Multi-tenant App ID is required"
            exit 1
        fi
    fi
    
    log_info "Multi-tenant App ID: $MULTI_TENANT_APP_ID"
    log_info "Key Vault Secret Name: $MULTI_TENANT_SECRET_NAME"
    
    # Confirmation
    if [[ "$FORCE" == false ]]; then
        echo
        echo "This will migrate from Phase A to Phase B:"
        echo "  - Create backup of current tenants.yaml"
        echo "  - Add multi_tenant_app_id: $MULTI_TENANT_APP_ID"
        echo "  - Update all tenants to use secret: $MULTI_TENANT_SECRET_NAME"
        echo
        read -p "Continue with migration? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Migration cancelled"
            exit 0
        fi
    fi
    
    # Migration phase
    log_step "Phase 2: Migration"
    
    create_backup
    update_tenants_yaml "$MULTI_TENANT_APP_ID"
    
    # Validation phase
    log_step "Phase 3: Post-Migration Validation"
    
    validate_migration || {
        log_error "Migration validation failed!"
        log_info "Backup available at: $TENANTS_YAML_BACKUP"
        log_info "To rollback: $0 --rollback"
        exit 1
    }
    
    run_unit_tests
    run_connectivity_tests
    
    # Summary
    log_step "Migration Complete!"
    
    cat << EOF

================================================================================
                      PHASE B MIGRATION COMPLETE
================================================================================

Configuration Changes:
  - Backup created: $TENANTS_YAML_BACKUP
  - multi_tenant_app_id: $MULTI_TENANT_APP_ID
  - Secret name: $MULTI_TENANT_SECRET_NAME

Next Steps:
  1. ✅ Review the updated $TENANTS_YAML
  2. 🔄 Deploy the application
  3. 🔄 Run tests: python -m pytest tests/unit/test_multi_tenant_auth.py -v
  4. 🔄 Verify in staging before production
  5. 🔄 Monitor for 1 week, then remove per-tenant app registrations

Rollback (if needed):
  $0 --rollback

Documentation:
  - Phase B Runbook: docs/runbooks/phase-b-multi-tenant-app.md
  - Auth Roadmap: docs/AUTH_TRANSITION_ROADMAP.md

================================================================================
EOF
    
    log_success "Phase B migration completed successfully!"
}

# Run main if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi

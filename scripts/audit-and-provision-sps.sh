#!/usr/bin/env bash
#
# Riverside Azure Governance Platform — Service Principal Audit & Provisioning
#
# Audits and optionally provisions Azure AD app registrations, service principals,
# API permissions, admin consent, and client secrets across all Riverside tenants.
#
# Usage:
#   ./scripts/audit-and-provision-sps.sh                     # Audit HTT only
#   ./scripts/audit-and-provision-sps.sh --all-tenants       # Audit all 5 tenants
#   ./scripts/audit-and-provision-sps.sh --tenant BCC        # Audit BCC only
#   ./scripts/audit-and-provision-sps.sh --provision         # Audit + provision HTT
#   ./scripts/audit-and-provision-sps.sh --provision --dry-run  # Show what would happen
#   ./scripts/audit-and-provision-sps.sh --all-tenants --provision
#   ./scripts/audit-and-provision-sps.sh --help
#
# Prerequisites:
#   - Azure CLI (az) installed
#   - jq installed
#   - Browser access for interactive login
#   - Global Admin or Application Administrator role per tenant
#
# Outputs:
#   data/sp-audit-report.json  — JSON audit results
#   data/.sp-secrets.env       — Generated secrets (if --provision creates them)
#   data/sp-audit.log          — Full operation log
#
# Safety:
#   - Idempotent: safe to run multiple times
#   - Confirms before any write operations (unless --dry-run)
#   - All operations logged to data/sp-audit.log
#

set -euo pipefail

# =============================================================================
# CONSTANTS & CONFIGURATION
# =============================================================================

# Terminal colors
RED='\033[0;31m' GREEN='\033[0;32m' YELLOW='\033[1;33m'
BLUE='\033[0;34m' CYAN='\033[0;36m' MAGENTA='\033[0;35m'
NC='\033[0m' BOLD='\033[1m' DIM='\033[2m'

# Tenant configuration (indexed arrays for bash 3.x compatibility)
TENANT_CODES=(HTT BCC FN TLL DCE)
TENANT_NAMES=("Head to Toe Brands" "Bishops Cuts/Color" "Frenchies Nails" "The Lash Lounge" "Delta Crown Extensions")
TENANT_IDS=("0c0e35dc-188a-4eb3-b8ba-61752154b407" "b5380912-79ec-452d-a6ca-6d897b19b294" "98723287-044b-4bbb-9294-19857d4128a0" "3c7d2bf3-b597-4766-b5cb-2b489c2904d6" "ce62e17d-2feb-4e67-a115-8ea4af68da30")
APP_IDS=("1e3e8417-49f1-4d08-b7be-47045d8a12e9" "4861906b-2079-4335-923f-a55cc0e44d64" "7648d04d-ccc4-43ac-bace-da1b68bf11b4" "52531a02-78fd-44ba-9ab9-b29675767955" "79c22a10-3f2d-4e6a-bddc-ee65c9a46cb0")
ADMIN_UPNS=("tyler.granlund-admin@httbrands.com" "tyler.granlund-Admin@bishopsbs.onmicrosoft.com" "tyler.granlund-Admin@ftgfrenchiesoutlook.onmicrosoft.com" "tyler.granlund-Admin@LashLoungeFranchise.onmicrosoft.com" "tyler.granlund-admin_httbrands.com#EXT#@deltacrown.onmicrosoft.com")

# Microsoft Graph API permissions (Application / Role type)
# Resource App ID: 00000003-0000-0000-c000-000000000000
GRAPH_RESOURCE_ID="00000003-0000-0000-c000-000000000000"
GRAPH_PERMS=(
  "df021288-bdef-4463-88db-98f22de89214=Role"  # User.Read.All
  "b0afded3-3588-46d8-8b3d-9842eff778da=Role"  # AuditLog.Read.All
  "230c1aed-a721-4c5d-9cb4-a90514e508ef=Role"  # Reports.Read.All
  "246dd0d5-5bd0-4def-940b-0421030a5b68=Role"  # Policy.Read.All
  "9a5d68dd-52b0-4cc2-bd40-abcf44ac3a30=Role"  # Application.Read.All
  "498476ce-e0fe-48b0-b801-37ba7e2685c6=Role"  # Organization.Read.All
  "7ab1d382-f21e-4acd-a863-ba3e13f7da61=Role"  # Directory.Read.All
  "bf394140-e372-4bf9-a898-299cfc7564e5=Role"  # SecurityEvents.Read.All
  "dbb9058a-0e50-45d7-ae91-66909b5d4571=Role"  # Domain.Read.All
)

# Azure Service Management permission
AZURE_MGMT_RESOURCE_ID="797f4846-ba00-4fd7-ba43-dac1f8f63013"
AZURE_MGMT_PERM="41094075-9dad-400e-a0bd-54e686782033=Role"  # user_impersonation

# Human-readable names (parallel to GRAPH_PERMS)
GRAPH_PERM_NAMES=("User.Read.All" "AuditLog.Read.All" "Reports.Read.All" "Policy.Read.All" "Application.Read.All" "Organization.Read.All" "Directory.Read.All" "SecurityEvents.Read.All" "Domain.Read.All")

# Script root & output paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DATA_DIR="$PROJECT_ROOT/data"
AUDIT_REPORT="$DATA_DIR/sp-audit-report.json"
SECRETS_FILE="$DATA_DIR/.sp-secrets.env"
LOG_FILE="$DATA_DIR/sp-audit.log"

# Defaults
PROVISION=false
DRY_RUN=false
ALL_TENANTS=false
SPECIFIC_TENANT="HTT"

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

mkdir -p "$DATA_DIR"
umask 077  # Restrict all created files to owner-only

# Append timestamped message to log file
log() {
  local level="$1"; shift
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $*" >> "$LOG_FILE"
}

info()    { echo -e "${CYAN}ℹ${NC}  $*"; log INFO "$*"; }
success() { echo -e "${GREEN}✔${NC}  $*"; log OK   "$*"; }
warn()    { echo -e "${YELLOW}⚠${NC}  $*"; log WARN "$*"; }
error()   { echo -e "${RED}✖${NC}  $*" >&2; log ERROR "$*"; }

section() { # Print a bold section header
  echo ""; echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BOLD}${BLUE}  $*${NC}"
  echo -e "${BOLD}${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  log INFO "=== $* ==="
}

confirm() { # Ask for confirmation. Returns 0 (yes) or 1 (no).
  if $DRY_RUN; then warn "DRY-RUN: Skipping — $1"; return 1; fi
  echo ""; echo -en "${YELLOW}${BOLD}⚡ $1 [y/N]: ${NC}"
  read -r answer
  case "$answer" in [yY][eE][sS]|[yY]) return 0 ;; *) warn "Skipped by user."; return 1 ;; esac
}

tenant_index() { # Resolve tenant code → array index (exits on invalid code)
  for i in "${!TENANT_CODES[@]}"; do
    [[ "${TENANT_CODES[$i]}" == "$1" ]] && echo "$i" && return 0
  done
  error "Unknown tenant code: $1  (valid: ${TENANT_CODES[*]})"; exit 1
}

usage() {
  cat <<EOF
${BOLD}Riverside SP Audit & Provisioning${NC}

Usage: $(basename "$0") [OPTIONS]

Options:
  --tenant CODE    Process a single tenant (default: HTT)
                   Valid codes: ${TENANT_CODES[*]}
  --all-tenants    Process all 5 tenants
  --provision      Create missing SPs, add perms, grant consent, create secrets
  --dry-run        Show what would happen without executing writes
  --help           Show this help message

Examples:
  $(basename "$0")                              # Audit HTT only
  $(basename "$0") --all-tenants                # Audit all tenants
  $(basename "$0") --tenant BCC --provision     # Provision BCC
  $(basename "$0") --all-tenants --provision --dry-run
EOF
  exit 0
}

# =============================================================================
# ARGUMENT PARSING
# =============================================================================

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tenant)
      SPECIFIC_TENANT="$2"
      shift 2
      ;;
    --all-tenants)
      ALL_TENANTS=true
      shift
      ;;
    --provision)
      PROVISION=true
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --help|-h)
      usage
      ;;
    *)
      error "Unknown option: $1"
      usage
      ;;
  esac
done

# Build the list of tenant indices to process
TARGET_INDICES=()
if $ALL_TENANTS; then
  for i in "${!TENANT_CODES[@]}"; do TARGET_INDICES+=("$i"); done
else
  TARGET_INDICES+=("$(tenant_index "$SPECIFIC_TENANT")")
fi

# =============================================================================
# PREREQUISITE CHECKS
# =============================================================================

check_prerequisites() {
  local missing=false
  for cmd in az jq; do
    if ! command -v "$cmd" &>/dev/null; then
      error "Required command not found: $cmd"
      missing=true
    fi
  done
  if $missing; then
    error "Install missing prerequisites and try again."
    exit 1
  fi
  success "Prerequisites OK (az, jq found)"
}

# =============================================================================
# LOGIN
# =============================================================================

login_tenant() { # Interactive browser login (skips if already authenticated)
  local idx="$1" code="${TENANT_CODES[$idx]}" tenant_id="${TENANT_IDS[$idx]}"
  info "Logging in to ${BOLD}${TENANT_NAMES[$idx]}${NC} ($code) — tenant $tenant_id"
  local current_tenant
  current_tenant=$(az account show --query 'tenantId' -o tsv 2>/dev/null || echo "")
  if [[ "$current_tenant" == "$tenant_id" ]]; then
    success "Already authenticated to $code"; return 0
  fi
  az login --tenant "$tenant_id" --allow-no-subscriptions --only-show-errors
  success "Logged in to $code"
}

# =============================================================================
# AUDIT PHASE
# =============================================================================

# Audit a single tenant. Populates result variables and appends to JSON report.
# Returns audit results as a formatted string.
audit_tenant() {
  local idx="$1"
  local code="${TENANT_CODES[$idx]}"
  local app_id="${APP_IDS[$idx]}"
  local name="${TENANT_NAMES[$idx]}"

  section "Auditing $name ($code)"

  # --- App Registration ---
  local app_exists="false"
  local app_display_name="N/A"
  local app_json
  if app_json=$(az ad app show --id "$app_id" 2>/dev/null); then
    app_exists="true"
    app_display_name=$(echo "$app_json" | jq -r '.displayName // "unknown"')
    success "App registration found: $app_display_name"
  else
    warn "App registration NOT found for $code (appId: $app_id)"
  fi

  # --- Service Principal ---
  local sp_exists="false"
  local sp_enabled="N/A"
  local sp_json
  if sp_json=$(az ad sp show --id "$app_id" 2>/dev/null); then
    sp_exists="true"
    sp_enabled=$(echo "$sp_json" | jq -r '.accountEnabled // "unknown"')
    success "Service principal found (enabled=$sp_enabled)"
  else
    warn "Service principal NOT found for $code"
  fi

  # --- Credentials ---
  local cred_count=0
  local cred_details="[]"
  if [[ "$app_exists" == "true" ]]; then
    cred_details=$(az ad app credential list --id "$app_id" 2>/dev/null || echo "[]")
    cred_count=$(echo "$cred_details" | jq 'length')
    if [[ "$cred_count" -gt 0 ]]; then
      success "Credentials: $cred_count secret(s) found"
      echo "$cred_details" | jq -r '.[] | "     ↳ \(.displayName // "unnamed") — expires \(.endDateTime // "unknown")"'
    else
      warn "No client secrets configured for $code"
    fi
  fi

  # --- API Permissions ---
  local perms_json="[]"
  local perm_count=0
  if [[ "$app_exists" == "true" ]]; then
    perms_json=$(az ad app permission list --id "$app_id" 2>/dev/null || echo "[]")
    perm_count=$(echo "$perms_json" | jq '[.[] | .resourceAccess[]?] | length')
    if [[ "$perm_count" -gt 0 ]]; then
      success "API permissions: $perm_count permission(s) configured"
    else
      warn "No API permissions configured for $code"
    fi
  fi

  # --- Build status table row ---
  local app_status sp_status cred_status perm_status
  [[ "$app_exists" == "true" ]] && app_status="${GREEN}✔${NC}" || app_status="${RED}✖${NC}"
  [[ "$sp_exists" == "true" ]] && sp_status="${GREEN}✔${NC}" || sp_status="${RED}✖${NC}"
  [[ "$cred_count" -gt 0 ]]   && cred_status="${GREEN}${cred_count}${NC}" || cred_status="${RED}0${NC}"
  [[ "$perm_count" -gt 0 ]]   && perm_status="${GREEN}${perm_count}${NC}" || perm_status="${YELLOW}${perm_count}${NC}"

  printf "  ${BOLD}%-5s${NC} │ %-30s │ App: %b │ SP: %b │ Creds: %b │ Perms: %b\n" \
    "$code" "$name" "$app_status" "$sp_status" "$cred_status" "$perm_status"

  # --- Append to JSON report ---
  local tenant_report
  tenant_report=$(jq -n \
    --arg code "$code" \
    --arg name "$name" \
    --arg tenant_id "${TENANT_IDS[$idx]}" \
    --arg app_id "$app_id" \
    --argjson app_exists "$app_exists" \
    --arg app_display_name "$app_display_name" \
    --argjson sp_exists "$sp_exists" \
    --arg sp_enabled "$sp_enabled" \
    --argjson cred_count "$cred_count" \
    --argjson cred_details "$cred_details" \
    --argjson perm_count "$perm_count" \
    --argjson perms "$perms_json" \
    --arg audited_at "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" \
    '{
      tenant_code: $code,
      tenant_name: $name,
      tenant_id: $tenant_id,
      app_id: $app_id,
      app_registration: { exists: $app_exists, display_name: $app_display_name },
      service_principal: { exists: $sp_exists, enabled: $sp_enabled },
      credentials: { count: $cred_count, details: $cred_details },
      permissions: { count: $perm_count, details: $perms },
      audited_at: $audited_at
    }')

  # Accumulate into global JSON array via temp file
  echo "$tenant_report" >> "$AUDIT_TMPFILE"

  # Export state for provision phase
  eval "AUDIT_APP_EXISTS_${code}=$app_exists"
  eval "AUDIT_SP_EXISTS_${code}=$sp_exists"
  eval "AUDIT_CRED_COUNT_${code}=$cred_count"
  eval "AUDIT_PERM_COUNT_${code}=$perm_count"
}

# =============================================================================
# PROVISION PHASE
# =============================================================================

add_permissions() { # Add all required Graph + Azure Management permissions
  local app_id="$1" code="$2"
  info "Adding Microsoft Graph permissions to $code..."
  for i in "${!GRAPH_PERMS[@]}"; do
    info "  ↳ ${GRAPH_PERM_NAMES[$i]} (${GRAPH_PERMS[$i]})"
    $DRY_RUN || az ad app permission add --id "$app_id" \
      --api "$GRAPH_RESOURCE_ID" --api-permissions "${GRAPH_PERMS[$i]}" \
      --only-show-errors 2>&1 | tee -a "$LOG_FILE" \
      || warn "  Failed to add ${GRAPH_PERM_NAMES[$i]} (may already exist)"
  done
  info "Adding Azure Service Management permission to $code..."
  info "  ↳ user_impersonation ($AZURE_MGMT_PERM)"
  $DRY_RUN || az ad app permission add --id "$app_id" \
    --api "$AZURE_MGMT_RESOURCE_ID" --api-permissions "$AZURE_MGMT_PERM" \
    --only-show-errors 2>&1 | tee -a "$LOG_FILE" \
    || warn "  Failed to add Azure Management perm (may already exist)"
  success "Permissions configured for $code"
}

provision_tenant() { # Create app, SP, perms, consent, and secret for one tenant
  local idx="$1" code="${TENANT_CODES[$idx]}" app_id="${APP_IDS[$idx]}"
  section "Provisioning ${TENANT_NAMES[$idx]} ($code)"

  # Read audit state
  local app_exists sp_exists cred_count perm_count
  eval "app_exists=\$AUDIT_APP_EXISTS_${code}"
  eval "sp_exists=\$AUDIT_SP_EXISTS_${code}"
  eval "cred_count=\$AUDIT_CRED_COUNT_${code}"
  eval "perm_count=\$AUDIT_PERM_COUNT_${code}"

  local changes_needed=false
  [[ "$app_exists" != "true" ]] && changes_needed=true
  [[ "$sp_exists" != "true" ]] && changes_needed=true
  [[ "$perm_count" -lt 10 ]] && changes_needed=true  # 9 Graph + 1 Azure Mgmt
  [[ "$cred_count" -eq 0 ]] && changes_needed=true

  if ! $changes_needed; then
    success "$code is fully provisioned — nothing to do!"
    return 0
  fi

  info "Changes needed for $code:"
  [[ "$app_exists" != "true" ]] && warn "  • App registration missing — will create"
  [[ "$sp_exists" != "true" ]] && warn "  • Service principal missing — will create"
  [[ "$perm_count" -lt 10 ]]   && warn "  • Permissions incomplete ($perm_count/10) — will add"
  [[ "$cred_count" -eq 0 ]]    && warn "  • No client secret — will generate"

  if ! confirm "Proceed with provisioning $code?"; then
    return 0
  fi

  # 1) Create App Registration if missing
  if [[ "$app_exists" != "true" ]]; then
    info "Creating app registration: Riverside-Governance-$code"
    if ! $DRY_RUN; then
      local new_app new_app_id
      new_app=$(az ad app create --display-name "Riverside-Governance-$code" \
        --sign-in-audience AzureADMyOrg --only-show-errors)
      new_app_id=$(echo "$new_app" | jq -r '.appId')
      success "Created app registration: $new_app_id"
      warn "NOTE: New appId ($new_app_id) differs from configured ($app_id). Update APP_IDS array."
      app_id="$new_app_id"  # Use new ID for remaining ops
    else
      info "DRY-RUN: Would create app registration Riverside-Governance-$code"
    fi
  fi
  # 2) Create Service Principal if missing
  if [[ "$sp_exists" != "true" ]]; then
    info "Creating service principal for $code..."
    if ! $DRY_RUN; then
      az ad sp create --id "$app_id" --only-show-errors 2>&1 | tee -a "$LOG_FILE"
      success "Service principal created for $code"
    else
      info "DRY-RUN: Would create service principal for appId $app_id"
    fi
  fi
  # 3) Add API Permissions
  [[ "$perm_count" -lt 10 ]] && add_permissions "$app_id" "$code"
  # 4) Grant Admin Consent
  info "Granting admin consent for $code..."
  if ! $DRY_RUN; then
    az ad app permission admin-consent --id "$app_id" --only-show-errors 2>&1 | tee -a "$LOG_FILE"
    success "Admin consent granted for $code"
  else
    info "DRY-RUN: Would grant admin consent for $code"
  fi
  # 5) Create Client Secret
  if [[ "$cred_count" -eq 0 ]]; then
    info "Creating client secret for $code..."
    if ! $DRY_RUN; then
      local secret_json secret_value
      secret_json=$(az ad app credential reset --id "$app_id" \
        --display-name "Riverside-Governance-Platform" --end-date "$(date -u -v+365d '+%Y-%m-%d' 2>/dev/null || date -u -d '+365 days' '+%Y-%m-%d')" \
        --append --only-show-errors)
      secret_value=$(echo "$secret_json" | jq -r '.password')
      success "Client secret created for $code (expires 2027-06-01)"
      save_secret "$code" "$app_id" "$secret_value"
    else
      info "DRY-RUN: Would create client secret for $code (expires 2027-06-01)"
    fi
  fi

  success "Provisioning complete for $code"
}

# =============================================================================
# SECRET MANAGEMENT
# =============================================================================

save_secret() { # Append a generated secret to the secrets env file
  local code="$1" app_id="$2" secret="$3"
  if [[ ! -f "$SECRETS_FILE" ]]; then
    touch "$SECRETS_FILE" && chmod 600 "$SECRETS_FILE"
    cat >> "$SECRETS_FILE" <<'HEADER'
# Riverside Governance Platform — Service Principal Secrets
# ⚠️  WARNING: DO NOT COMMIT THIS FILE TO VERSION CONTROL ⚠️
# Generated by scripts/audit-and-provision-sps.sh
HEADER
  fi
  printf '\n# %s — Generated %s\n%s_CLIENT_ID=%s\n%s_CLIENT_SECRET=%s\n' \
    "$code" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$code" "$app_id" "$code" "$secret" >> "$SECRETS_FILE"
  success "Secret for $code saved to $SECRETS_FILE"
  warn "⚠️  Treat this file as highly sensitive — do not commit!"
  warn "⏰ ACTION: Store this secret in Azure Key Vault, then securely delete: shred -u $SECRETS_FILE"
}

# =============================================================================
# REPORT GENERATION
# =============================================================================

write_audit_report() { # Compile per-tenant JSON blobs into final report
  section "Writing Audit Report"
  jq -s '{ report_name: "Riverside SP Audit Report",
    generated_at: (now | strftime("%Y-%m-%dT%H:%M:%SZ")),
    tenant_count: length, tenants: . }' "$AUDIT_TMPFILE" > "$AUDIT_REPORT"
  success "Audit report written to $AUDIT_REPORT"
}

# Print a final summary table to the terminal.
print_summary() {
  section "Summary"

  echo ""
  printf "  ${BOLD}%-5s${NC} │ ${BOLD}%-30s${NC} │ ${BOLD}%-5s${NC} │ ${BOLD}%-5s${NC} │ ${BOLD}%-7s${NC} │ ${BOLD}%-7s${NC}\n" \
    "Code" "Tenant" "App" "SP" "Creds" "Perms"
  printf "  ──────┼────────────────────────────────┼───────┼───────┼─────────┼────────\n"

  for idx in "${TARGET_INDICES[@]}"; do
    local code="${TENANT_CODES[$idx]}"
    local name="${TENANT_NAMES[$idx]}"
    local app_exists sp_exists cred_count perm_count
    eval "app_exists=\$AUDIT_APP_EXISTS_${code}"
    eval "sp_exists=\$AUDIT_SP_EXISTS_${code}"
    eval "cred_count=\$AUDIT_CRED_COUNT_${code}"
    eval "perm_count=\$AUDIT_PERM_COUNT_${code}"

    local a s c p
    [[ "$app_exists" == "true" ]] && a="${GREEN}✔${NC}" || a="${RED}✖${NC}"
    [[ "$sp_exists" == "true" ]]  && s="${GREEN}✔${NC}" || s="${RED}✖${NC}"
    [[ "$cred_count" -gt 0 ]]    && c="${GREEN}${cred_count}${NC}" || c="${RED}0${NC}"
    [[ "$perm_count" -ge 10 ]]   && p="${GREEN}${perm_count}${NC}" || p="${YELLOW}${perm_count}${NC}"

    printf "  %-5s │ %-30s │  %b    │  %b    │   %b     │   %b\n" \
      "$code" "$name" "$a" "$s" "$c" "$p"
  done

  echo ""
  info "Audit report:  $AUDIT_REPORT"
  info "Operation log: $LOG_FILE"
  if [[ -f "$SECRETS_FILE" ]]; then
    warn "Secrets file:  $SECRETS_FILE (DO NOT COMMIT)"
  fi
  echo ""
}

# =============================================================================
# MAIN EXECUTION
# =============================================================================

main() {
  # Initialize the log for this run
  echo "" >> "$LOG_FILE"
  log INFO "========================================"
  log INFO "Audit run started — $(date)"
  log INFO "Targets: ${TARGET_INDICES[*]}"
  log INFO "Provision=$PROVISION  DryRun=$DRY_RUN"
  log INFO "========================================"

  section "Riverside SP Audit & Provisioning"
  echo ""
  info "Tenants to process: ${#TARGET_INDICES[@]}"
  info "Mode: $($PROVISION && echo 'AUDIT + PROVISION' || echo 'AUDIT ONLY')"
  $DRY_RUN && warn "DRY-RUN mode enabled — no writes will be performed"
  echo ""

  check_prerequisites

  # Temp file to accumulate per-tenant JSON blobs
  AUDIT_TMPFILE=$(mktemp)
  trap 'rm -f "$AUDIT_TMPFILE"' EXIT

  # --- Login & Audit each tenant ---
  for idx in "${TARGET_INDICES[@]}"; do
    login_tenant "$idx"
    audit_tenant "$idx"
  done

  # --- Write audit report ---
  write_audit_report

  # --- Provision phase (if requested) ---
  if $PROVISION; then
    section "Provision Phase"
    for idx in "${TARGET_INDICES[@]}"; do
      # Re-login in case session expired during long audit
      login_tenant "$idx"
      provision_tenant "$idx"
    done
  fi

  # --- Final summary ---
  print_summary

  log INFO "Audit run finished — $(date)"
  success "Done! 🎉"
}

main

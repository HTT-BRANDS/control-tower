#!/usr/bin/env bash
# ============================================================================
# OIDC Cross-Tenant Federation Configuration Script
# ============================================================================
# This script configures federated identity credentials for all 5 tenants
# so the App Service Managed Identity can authenticate to each tenant's
# Azure AD via OIDC (no secrets needed).
#
# PREREQUISITES:
# - Azure CLI installed and working
# - Global Admin (or Application Administrator) access in each tenant
# - Tyler's admin accounts for each tenant
#
# USAGE:
#   ./scripts/configure-oidc-federation.sh
#
# The script will prompt for authentication to each tenant interactively.
# ============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Constants
MI_PRINCIPAL_ID="8ff7caa7-566b-428f-b76e-b122ebd43365"
MI_ISSUER="https://login.microsoftonline.com/0c0e35dc-188a-4eb3-b8ba-61752154b407/v2.0"
FEDERATION_NAME="governance-platform-mi"

# Graph API Permission IDs
DIRECTORY_READ_ALL="7ab1d382-f21e-4acd-a863-ba3e13f7da61"
REPORTS_READ_ALL="230c1aed-a721-4c5d-9cb4-a90514e508ef"
SECURITY_EVENTS_READ_ALL="bf394140-e372-4bf9-a898-299cfc7564e5"
DOMAIN_READ_ALL="dbb9058a-0e50-45d7-ae91-66909b5d4664"
MS_GRAPH_API="00000003-0000-0000-c000-000000000000"

# Tenant Configuration (from config/tenants.yaml)
declare -A TENANT_IDS=(
  ["HTT"]="0c0e35dc-188a-4eb3-b8ba-61752154b407"
  ["BCC"]="b5380912-79ec-452d-a6ca-6d897b19b294"
  ["FN"]="98723287-044b-4bbb-9294-19857d4128a0"
  ["TLL"]="3c7d2bf3-b597-4766-b5cb-2b489c2904d6"
  ["DCE"]="ce62e17d-2feb-4e67-a115-8ea4af68da30"
)

declare -A APP_IDS=(
  ["HTT"]="1e3e8417-49f1-4d08-b7be-47045d8a12e9"
  ["BCC"]="4861906b-2079-4335-923f-a55cc0e44d64"
  ["FN"]="7648d04d-ccc4-43ac-bace-da1b68bf11b4"
  ["TLL"]="52531a02-78fd-44ba-9ab9-b29675767955"
  ["DCE"]="79c22a10-3f2d-4e6a-bddc-ee65c9a46cb0"
)

declare -A TENANT_NAMES=(
  ["HTT"]="Head-To-Toe (Home Tenant)"
  ["BCC"]="Bishops"
  ["FN"]="Frenchies"
  ["TLL"]="Lash Lounge"
  ["DCE"]="Delta Crown Extensions"
)

# Results tracking
declare -A RESULTS

log_info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

configure_tenant() {
  local code=$1
  local tenant_id="${TENANT_IDS[$code]}"
  local app_id="${APP_IDS[$code]}"
  local name="${TENANT_NAMES[$code]}"
  
  echo ""
  echo "============================================================"
  echo -e "${BLUE}Configuring: ${name} (${code})${NC}"
  echo "  Tenant ID: ${tenant_id}"
  echo "  App ID:    ${app_id}"
  echo "============================================================"
  
  # Step 1: Login to tenant
  log_info "Logging into ${code} tenant..."
  if ! az login --tenant "${tenant_id}" 2>/dev/null; then
    log_error "Failed to login to ${code} tenant"
    RESULTS[$code]="FAILED (login)"
    return 1
  fi
  log_ok "Logged into ${code}"
  
  # Step 2: Get app registration Object ID
  log_info "Getting app registration Object ID..."
  local app_object_id
  app_object_id=$(az ad app show --id "${app_id}" --query id -o tsv 2>/dev/null) || {
    log_error "App registration ${app_id} not found in ${code} tenant"
    RESULTS[$code]="FAILED (app not found)"
    return 1
  }
  log_ok "App Object ID: ${app_object_id}"
  
  # Step 3: Add federated identity credential
  log_info "Adding federated identity credential..."
  if az ad app federated-credential show --id "${app_object_id}" --federated-credential-id "${FEDERATION_NAME}" &>/dev/null; then
    log_warn "Federated credential '${FEDERATION_NAME}' already exists — skipping"
  else
    az ad app federated-credential create \
      --id "${app_object_id}" \
      --parameters "{
        \"name\": \"${FEDERATION_NAME}\",
        \"issuer\": \"${MI_ISSUER}\",
        \"subject\": \"${MI_PRINCIPAL_ID}\",
        \"audiences\": [\"api://AzureADTokenExchange\"],
        \"description\": \"Azure Governance Platform App Service Managed Identity\"
      }" 2>/dev/null || {
        # Check if it already exists (different error format)
        if az ad app federated-credential list --id "${app_object_id}" 2>/dev/null | grep -q "${FEDERATION_NAME}"; then
          log_warn "Federated credential already exists (duplicate check)"
        else
          log_error "Failed to create federated credential"
          RESULTS[$code]="FAILED (federation)"
          return 1
        fi
      }
    log_ok "Federated credential created"
  fi
  
  # Step 4: Grant Graph API permissions
  log_info "Granting Graph API permissions..."
  az ad app permission add \
    --id "${app_object_id}" \
    --api "${MS_GRAPH_API}" \
    --api-permissions \
      "${DIRECTORY_READ_ALL}=Role" \
      "${REPORTS_READ_ALL}=Role" \
      "${SECURITY_EVENTS_READ_ALL}=Role" \
      "${DOMAIN_READ_ALL}=Role" 2>/dev/null || log_warn "Some permissions may already exist"
  log_ok "Permissions added"
  
  # Step 5: Admin consent
  log_info "Granting admin consent..."
  az ad app permission admin-consent --id "${app_object_id}" 2>/dev/null || {
    log_error "Failed to grant admin consent — you may need Global Admin role"
    RESULTS[$code]="FAILED (admin consent)"
    return 1
  }
  log_ok "Admin consent granted"
  
  # Step 6: Verify
  log_info "Verifying configuration..."
  local fed_count
  fed_count=$(az ad app federated-credential list --id "${app_object_id}" 2>/dev/null | grep -c "${MI_PRINCIPAL_ID}" || echo "0")
  if [ "$fed_count" -gt 0 ]; then
    log_ok "${code} fully configured! ✅"
    RESULTS[$code]="SUCCESS"
  else
    log_error "Verification failed — federated credential not found"
    RESULTS[$code]="FAILED (verification)"
    return 1
  fi
}

# ============================================================================
# MAIN
# ============================================================================

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  OIDC Cross-Tenant Federation Configuration                 ║"
echo "║  Azure Governance Platform                                  ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "This script will configure federated identity credentials in"
echo "5 Azure AD tenants. You'll need to authenticate to each one."
echo ""
echo "MI Principal ID: ${MI_PRINCIPAL_ID}"
echo "MI Issuer:       ${MI_ISSUER}"
echo ""

# Process each tenant
TENANT_ORDER=("HTT" "BCC" "FN" "TLL" "DCE")

for code in "${TENANT_ORDER[@]}"; do
  configure_tenant "${code}" || true  # Continue on failure
done

# Summary
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  CONFIGURATION SUMMARY                                      ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

ALL_OK=true
for code in "${TENANT_ORDER[@]}"; do
  status="${RESULTS[$code]:-NOT_RUN}"
  if [ "$status" = "SUCCESS" ]; then
    echo -e "  ${GREEN}✅ ${code}${NC} — ${TENANT_NAMES[$code]}"
  else
    echo -e "  ${RED}❌ ${code}${NC} — ${TENANT_NAMES[$code]} — ${status}"
    ALL_OK=false
  fi
done

echo ""

if [ "$ALL_OK" = true ]; then
  echo -e "${GREEN}All tenants configured successfully!${NC}"
  echo ""
  echo "Next step: Restart the App Service:"
  echo "  az login --tenant 0c0e35dc-188a-4eb3-b8ba-61752154b407"
  echo "  az webapp restart --name app-governance-prod --resource-group rg-governance-production"
  echo ""
  echo "Then verify data flow (bd issue: azure-governance-platform-oim):"
  echo "  curl https://app-governance-prod.azurewebsites.net/health"
else
  echo -e "${YELLOW}Some tenants failed. Re-run the script to retry.${NC}"
  echo "Failed tenants will be re-attempted on next run."
fi

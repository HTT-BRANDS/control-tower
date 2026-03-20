#!/usr/bin/env bash
# setup_billing_rbac.sh — Configure billing account access for CO-007 Reserved Instance Utilization
#
# Prerequisites:
#   - Azure CLI installed and logged in as Global Admin
#   - Access to all managed tenants' billing accounts
#
# Usage:
#   chmod +x scripts/setup_billing_rbac.sh
#   ./scripts/setup_billing_rbac.sh
#
# Traces: CO-007 (Reserved Instance Utilization)

set -euo pipefail

echo "================================================================="
echo "  CO-007: Billing Account RBAC Setup"
echo "  Reserved Instance Utilization Configuration"
echo "================================================================="
echo ""

# Tenant configuration from .env.example
declare -A TENANTS=(
    ["HTT"]="0c0e35dc-188a-4eb3-b8ba-61752154b407"
    ["BCC"]="b5380912-79ec-452d-a6ca-6d897b19b294"
    ["FN"]="98723287-044b-4bbb-9294-19857d4128a0"
    ["TLL"]="3c7d2bf3-b597-4766-b5cb-2b489c2904d6"
)

declare -A APP_IDS=(
    ["HTT"]="e1dfb17f-b695-4dad-92c0-20e26ce069ab"
    ["BCC"]="e70f966a-ec25-4c2b-a881-c8df07b6dd1c"
    ["FN"]="d9236548-e979-4c8c-8493-0cac0c121749"
    ["TLL"]="1cb8490d-2157-418f-b485-d374a9defe28"
)

declare -A SUBSCRIPTIONS=(
    ["HTT"]="HTT-CORE"
    ["BCC"]="BCC-CORE"
    ["FN"]="FN-CORE"
    ["TLL"]="TLL-CORE"
)

echo "Step 1: Discovering billing accounts per tenant..."
echo "---------------------------------------------------"

for tenant_code in "${!TENANTS[@]}"; do
    sub="${SUBSCRIPTIONS[$tenant_code]}"
    echo ""
    echo "Tenant: $tenant_code (${TENANTS[$tenant_code]})"
    echo "Subscription: $sub"

    az account set --subscription "$sub" 2>/dev/null || {
        echo "  ⚠️  Cannot access subscription $sub — skipping"
        continue
    }

    echo "  Billing accounts:"
    az billing account list --query "[].{name:name, displayName:displayName, accountType:accountType}" --output table 2>/dev/null || {
        echo "  ⚠️  No billing accounts found or no access"
    }
done

echo ""
echo "================================================================="
echo "Step 2: Manual Configuration Required"
echo "================================================================="
echo ""
echo "For each tenant, you need to:"
echo ""
echo "  1. Identify the correct billing account ID (the 'name' field from above)"
echo "     Use the Enterprise/Organization account, not Individual ones."
echo ""
echo "  2. Grant 'Cost Management Reader' role to the service principal:"
echo ""

for tenant_code in "${!TENANTS[@]}"; do
    app_id="${APP_IDS[$tenant_code]}"
    echo "     # $tenant_code tenant (app ID: $app_id)"
    echo "     az role assignment create \\"
    echo "       --assignee $app_id \\"
    echo "       --role 'Cost Management Reader' \\"
    echo "       --scope '/providers/Microsoft.Billing/billingAccounts/<BILLING_ACCOUNT_ID>'"
    echo ""
done

echo "  3. Update the database tenant records with billing_account_id:"
echo ""
echo "     uv run python -c \""
echo "     from app.core.database import SessionLocal"
echo "     from app.models.tenant import Tenant"
echo "     db = SessionLocal()"
echo "     "
echo "     # Replace with your actual billing account IDs:"
echo "     billing_ids = {"
echo "         '0c0e35dc-188a-4eb3-b8ba-61752154b407': '<HTT_BILLING_ACCOUNT_ID>',"
echo "         'b5380912-79ec-452d-a6ca-6d897b19b294': '<BCC_BILLING_ACCOUNT_ID>',"
echo "         '98723287-044b-4bbb-9294-19857d4128a0': '<FN_BILLING_ACCOUNT_ID>',"
echo "         '3c7d2bf3-b597-4766-b5cb-2b489c2904d6': '<TLL_BILLING_ACCOUNT_ID>',"
echo "     }"
echo "     "
echo "     for tenant in db.query(Tenant).all():"
echo "         if tenant.tenant_id in billing_ids:"
echo "             tenant.billing_account_id = billing_ids[tenant.tenant_id]"
echo "     db.commit()"
echo "     db.close()"
echo "     print('Done!')"
echo "     \""
echo ""
echo "================================================================="
echo "  After configuration, test with:"
echo "  curl -H 'Authorization: Bearer <token>' http://localhost:8000/api/v1/costs/reservations"
echo "================================================================="

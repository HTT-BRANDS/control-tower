#!/usr/bin/env bash
# Migrate tenant client secrets from .env to Azure Key Vault
# Usage: ./scripts/migrate-secrets-to-keyvault.sh <key-vault-name>
#
# Prerequisites:
#   - az login (with Global Admin or Key Vault Admin)
#   - Key Vault deployed (via Bicep or manually)
#   - .env file with all tenant secrets

set -euo pipefail

KV_NAME="${1:?Usage: $0 <key-vault-name>}"

echo "🔐 Migrating secrets to Key Vault: $KV_NAME"

# Load .env for secret values (safe parsing, no execution)
if [[ ! -f .env ]]; then
    echo "❌ .env file not found. Run from project root."
    exit 1
fi

# SECURITY: Read .env safely without executing (no source/eval)
while IFS='=' read -r key value; do
    # Skip comments and empty lines
    [[ -z "$key" || "$key" =~ ^# ]] && continue
    # Strip quotes from value
    value="${value%\"}"
    value="${value#\"}"
    value="${value%\'}"
    value="${value#\'}"
    export "$key=$value"
done < <(grep -E '^[A-Z_][A-Z0-9_]*=' .env 2>/dev/null || true)

# Verify Key Vault exists
if ! az keyvault show --name "$KV_NAME" &>/dev/null; then
    echo "❌ Key Vault '$KV_NAME' not found. Deploy infrastructure first."
    exit 1
fi

echo "📋 Uploading tenant secrets..."

# Tenant secrets mapping: secret-name -> env-var
declare -A SECRETS=(
    ["htt-client-secret"]="HTT_CLIENT_SECRET"
    ["htt-client-id"]="HTT_CLIENT_ID"
    ["bcc-client-secret"]="BCC_CLIENT_SECRET"
    ["bcc-client-id"]="BCC_CLIENT_ID"
    ["fn-client-secret"]="FN_CLIENT_SECRET"
    ["fn-client-id"]="FN_CLIENT_ID"
    ["tll-client-secret"]="TLL_CLIENT_SECRET"
    ["tll-client-id"]="TLL_CLIENT_ID"
    ["dce-client-secret"]="DCE_CLIENT_SECRET"
    ["dce-client-id"]="DCE_CLIENT_ID"
    ["primary-client-secret"]="AZURE_CLIENT_SECRET"
    ["primary-client-id"]="AZURE_CLIENT_ID"
    ["jwt-secret-key"]="JWT_SECRET_KEY"
)

SUCCESS=0
FAILED=0

for secret_name in "${!SECRETS[@]}"; do
    env_var="${SECRETS[$secret_name]}"
    value="${!env_var:-}"
    
    if [[ -z "$value" ]]; then
        echo "  ⚠️  SKIP: $secret_name ($env_var not set)"
        continue
    fi
    
    if az keyvault secret set \
        --vault-name "$KV_NAME" \
        --name "$secret_name" \
        --value "$value" \
        --expires "$(date -u -v+365d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '+365 days' +%Y-%m-%dT%H:%M:%SZ)" \
        --output none 2>/dev/null; then
        echo "  ✅ $secret_name"
        ((SUCCESS++))
    else
        echo "  ❌ $secret_name (failed to upload)"
        ((FAILED++))
    fi
done

echo ""
echo "📊 Results: $SUCCESS uploaded, $FAILED failed"
echo ""
echo "🔧 Next steps:"
echo "  1. Set KEY_VAULT_URL=https://$KV_NAME.vault.azure.net/ in App Service config"
echo "  2. Grant App Service managed identity 'Key Vault Secrets User' role:"
echo "     az role assignment create \\"
echo "       --role 'Key Vault Secrets User' \\"
echo "       --assignee <managed-identity-object-id> \\"
echo "       --scope /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.KeyVault/vaults/$KV_NAME"
echo "  3. Remove plaintext secrets from App Service environment variables"

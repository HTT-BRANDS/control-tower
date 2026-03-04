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

# Tenant secrets mapping: secret-name -> env-var (bash 3.2 compatible)
SECRET_NAMES=(
    htt-client-secret htt-client-id
    bcc-client-secret bcc-client-id
    fn-client-secret fn-client-id
    tll-client-secret tll-client-id
    dce-client-secret dce-client-id
    primary-client-secret primary-client-id
    jwt-secret-key
)
ENV_VARS=(
    HTT_CLIENT_SECRET HTT_CLIENT_ID
    BCC_CLIENT_SECRET BCC_CLIENT_ID
    FN_CLIENT_SECRET FN_CLIENT_ID
    TLL_CLIENT_SECRET TLL_CLIENT_ID
    DCE_CLIENT_SECRET DCE_CLIENT_ID
    AZURE_CLIENT_SECRET AZURE_CLIENT_ID
    JWT_SECRET_KEY
)

SUCCESS=0
FAILED=0

for i in "${!SECRET_NAMES[@]}"; do
    secret_name="${SECRET_NAMES[$i]}"
    env_var="${ENV_VARS[$i]}"
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

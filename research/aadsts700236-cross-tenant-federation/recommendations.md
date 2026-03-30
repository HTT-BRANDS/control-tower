# Recommendations: Fixing Cross-Tenant Authentication

## Priority 1 (Immediate): Enable Key Vault Secret Fallback

**While implementing the long-term fix, ensure the existing `ClientSecretCredential` path works.**

The project already has this implemented via `USE_OIDC_FEDERATION=false`. Verify:

```bash
# In .env.production, ensure OIDC is disabled until the fix is deployed
USE_OIDC_FEDERATION=false

# Verify Key Vault has all tenant secrets
az keyvault secret list --vault-name riverside-kv --query "[].name" -o tsv
# Expected: htt-client-secret, bcc-client-secret, fn-client-secret, tll-client-secret, dce-client-secret
```

**Effort**: 0 hours (already implemented)
**Risk**: Client secrets must be rotated periodically

---

## Priority 2 (1-2 Days): Implement Multi-Tenant App + UAMI Pattern

### Step 1: Create User-Assigned Managed Identity

```bash
# Create UAMI in the managing (HTT) tenant
az identity create \
  --name "mi-governance-platform" \
  --resource-group "rg-governance-prod" \
  --location "eastus"

# Get the UAMI details
UAMI_CLIENT_ID=$(az identity show \
  --name "mi-governance-platform" \
  --resource-group "rg-governance-prod" \
  --query clientId -o tsv)

UAMI_PRINCIPAL_ID=$(az identity show \
  --name "mi-governance-platform" \
  --resource-group "rg-governance-prod" \
  --query principalId -o tsv)

echo "UAMI Client ID: $UAMI_CLIENT_ID"
echo "UAMI Principal ID: $UAMI_PRINCIPAL_ID"
```

### Step 2: Assign UAMI to App Service

```bash
# Assign the UAMI to the App Service
az webapp identity assign \
  --name "app-governance-prod" \
  --resource-group "rg-governance-prod" \
  --identities "/subscriptions/{sub-id}/resourceGroups/rg-governance-prod/providers/Microsoft.ManagedIdentity/userAssignedIdentities/mi-governance-platform"
```

### Step 3: Create Multi-Tenant App Registration

```bash
# Create the multi-tenant app in HTT tenant
az ad app create \
  --display-name "Riverside Governance Platform" \
  --sign-in-audience "AzureADMultipleOrgs" \
  --query appId -o tsv

# Store the app ID
MT_APP_ID="<output-from-above>"

# Add required Graph API permissions
# Directory.Read.All (Application)
az ad app permission add --id $MT_APP_ID \
  --api 00000003-0000-0000-c000-000000000000 \
  --api-permissions 7ab1d382-f21e-4acd-a863-ba3e13f7da61=Role

# Reports.Read.All (Application)
az ad app permission add --id $MT_APP_ID \
  --api 00000003-0000-0000-c000-000000000000 \
  --api-permissions 230c1aed-a721-4c5d-9cb4-a90514e508ef=Role

# SecurityEvents.Read.All (Application)
az ad app permission add --id $MT_APP_ID \
  --api 00000003-0000-0000-c000-000000000000 \
  --api-permissions bf394140-e372-4bf9-a898-299cfc7564e5=Role

# Domain.Read.All (Application)
az ad app permission add --id $MT_APP_ID \
  --api 00000003-0000-0000-c000-000000000000 \
  --api-permissions dbb9058a-0e50-45d7-ae91-66909b5d4664=Role
```

### Step 4: Configure Federated Identity Credential

```bash
# Get the app's Object ID (different from App/Client ID)
MT_APP_OBJECT_ID=$(az ad app show --id $MT_APP_ID --query id -o tsv)

# Create the federated identity credential
# Issuer = HTT tenant authority (same tenant as UAMI)
# Subject = UAMI's principal (object) ID
az ad app federated-credential create \
  --id $MT_APP_OBJECT_ID \
  --parameters '{
    "name": "governance-platform-uami",
    "issuer": "https://login.microsoftonline.com/0c0e35dc-188a-4eb3-b8ba-61752154b407/v2.0",
    "subject": "'$UAMI_PRINCIPAL_ID'",
    "description": "Trust governance platform UAMI for secretless auth",
    "audiences": ["api://AzureADTokenExchange"]
  }'
```

### Step 5: Provision App in Foreign Tenants via Admin Consent

For each foreign tenant, an admin must visit the consent URL:

```
# BCC Tenant
https://login.microsoftonline.com/b5380912-79ec-452d-a6ca-6d897b19b294/adminconsent?client_id={MT_APP_ID}

# FN Tenant
https://login.microsoftonline.com/98723287-044b-4bbb-9294-19857d4128a0/adminconsent?client_id={MT_APP_ID}

# TLL Tenant
https://login.microsoftonline.com/3c7d2bf3-b597-4766-b5cb-2b489c2904d6/adminconsent?client_id={MT_APP_ID}

# DCE Tenant
https://login.microsoftonline.com/ce62e17d-2feb-4e67-a115-8ea4af68da30/adminconsent?client_id={MT_APP_ID}
```

After consent, grant admin consent for Graph API permissions in each tenant:
```bash
# Log into each tenant and grant admin consent
az login --tenant $TENANT_ID
SP_ID=$(az ad sp show --id $MT_APP_ID --query id -o tsv)
az ad app permission admin-consent --id $MT_APP_ID
```

### Step 6: Update Application Code

#### Updated `oidc_credential.py`

Key changes:
1. Use UAMI client ID for `ManagedIdentityCredential`
2. Use the single multi-tenant app's client ID for `ClientAssertionCredential`
3. Vary only the `tenant_id` parameter per tenant

```python
# The critical change: get_credential_for_tenant no longer needs per-tenant client_id
def get_credential_for_tenant(self, tenant_id: str) -> TokenCredential:
    """Return a TokenCredential scoped to the given tenant.

    Uses the multi-tenant app registration in the home tenant.
    The UAMI provides the assertion; the multi-tenant app's service
    principal in each foreign tenant provides the authorization.
    """
    if self._is_app_service():
        return ClientAssertionCredential(
            tenant_id=tenant_id,
            client_id=self._multitenant_app_id,  # Single app for all tenants
            func=self._get_mi_assertion,
        )
    # ... other paths unchanged
```

#### Updated `.env.example`

```env
# OIDC Workload Identity Federation (v2 — Multi-Tenant App)
USE_OIDC_FEDERATION=true

# The multi-tenant app registration in the home (HTT) tenant
OIDC_MULTITENANT_APP_ID=<multi-tenant-app-client-id>

# The user-assigned managed identity client ID
AZURE_MANAGED_IDENTITY_CLIENT_ID=<uami-client-id>
```

#### Updated `config/tenants.yaml`

Remove per-tenant `app_id` entries; they're no longer needed for the OIDC path:

```yaml
tenants:
  HTT:
    tenant_id: "0c0e35dc-188a-4eb3-b8ba-61752154b407"
    name: "Head-To-Toe (Home Tenant)"
    # app_id no longer needed — multi-tenant app used for all
  BCC:
    tenant_id: "b5380912-79ec-452d-a6ca-6d897b19b294"
    name: "Bishops"
  # ... etc
```

### Step 7: Update Environment Configuration

```bash
# Update App Service configuration
az webapp config appsettings set \
  --name "app-governance-prod" \
  --resource-group "rg-governance-prod" \
  --settings \
    USE_OIDC_FEDERATION=true \
    OIDC_MULTITENANT_APP_ID=$MT_APP_ID \
    AZURE_MANAGED_IDENTITY_CLIENT_ID=$UAMI_CLIENT_ID
```

---

## Priority 3 (Cleanup): Remove Per-Tenant App Registrations

Once the multi-tenant app is working in production:

1. **Monitor for 2 weeks** — verify all Graph API calls succeed across all tenants
2. **Remove old FIC configurations** from foreign tenant app registrations
3. **Remove client secrets** from Key Vault (if OIDC is the sole auth path)
4. **Optionally delete** the per-tenant app registrations (BCC, FN, TLL, DCE apps)
5. **Keep HTT app** if it's used for user-facing SSO (separate from backend Graph access)

---

## Priority 4 (Complementary): Azure Lighthouse for ARM Operations

Azure Lighthouse is already referenced in the project architecture. It's ideal for:
- Resource inventory (subscriptions, resource groups, VMs)
- Cost management data
- Policy compliance status
- Azure Monitor / Defender for Cloud data

**But it cannot replace Graph API access** for identity operations.

Consider using Lighthouse + multi-tenant app together:
- **Lighthouse**: ARM operations (cost, resources, compliance)
- **Multi-tenant app + UAMI**: Graph API operations (users, MFA, roles)

---

## Migration Checklist

- [ ] Create UAMI in HTT tenant (`mi-governance-platform`)
- [ ] Assign UAMI to App Service
- [ ] Create multi-tenant app registration in HTT
- [ ] Configure FIC on multi-tenant app (UAMI as subject)
- [ ] Admin consent in HTT tenant (auto via service principal creation)
- [ ] Admin consent in BCC tenant + grant Graph permissions
- [ ] Admin consent in FN tenant + grant Graph permissions
- [ ] Admin consent in TLL tenant + grant Graph permissions
- [ ] Admin consent in DCE tenant + grant Graph permissions
- [ ] Update `oidc_credential.py` to use single app ID
- [ ] Update `config.py` with new env vars
- [ ] Update `tenants_config.py` (remove per-tenant app_id requirement for OIDC)
- [ ] Update `.env.example` and `.env.production`
- [ ] Update `setup-federated-creds.sh` for new pattern
- [ ] Test locally with `OIDC_ALLOW_DEV_FALLBACK=true`
- [ ] Deploy to staging with `USE_OIDC_FEDERATION=true`
- [ ] Verify Graph API calls work for all 5 tenants
- [ ] Deploy to production
- [ ] Monitor for 2 weeks
- [ ] Remove old per-tenant FIC configurations
- [ ] Remove old client secrets from Key Vault
- [ ] Update documentation (ARCHITECTURE.md, INFRASTRUCTURE_INVENTORY.md)

---

## Answers to Original Questions

### Q1: Does Azure support using MI tokens as assertions for federated identity credentials across tenants?

**No, not directly across tenants.** The "App trust MI" pattern requires the MI and app to be in the **same tenant**. However, a multi-tenant app in the home tenant (same tenant as the MI) can access resources in foreign tenants. This is the supported cross-tenant pattern.

### Q2: Is there a known limitation where MI tokens can't be used as federated identity assertions?

**Yes.** Two limitations:
1. **General rule**: "Microsoft Entra ID issued tokens may not be used for federated identity flows." MI tokens are Entra tokens.
2. **Specific exception**: The "App trust MI" feature works, but requires same-tenant MI + app, and user-assigned MI only.

### Q3: What is the correct approach for cross-tenant Graph API access from an App Service without client secrets?

**Multi-tenant app registration + UAMI + federated identity credential**, all in the home tenant. The app is provisioned into foreign tenants via admin consent. See Priority 2 above.

### Q4: Are there alternative approaches?

1. **Multi-tenant app + UAMI** (recommended, zero secrets)
2. **Per-tenant apps + Key Vault secrets** (already implemented, fallback)
3. **Multi-tenant app + certificate in Key Vault** (near-zero secrets)
4. **Azure Lighthouse** (ARM-only, cannot access Graph API)

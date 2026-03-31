# Phase B: Multi-Tenant App Registration Setup

**Status:** Implementation Ready  
**Complexity:** Medium  
**Estimated Time:** 2-3 hours  
**Risk Level:** Low (backward compatible with Phase A)

---

## Overview

Phase B transitions from **5 separate app registrations** (1 per tenant) to a **single multi-tenant app registration** that works across all tenants. This reduces secret rotation burden from 5 secrets to 1 secret while maintaining the same security posture.

### Before (Phase A)
```
HTT Tenant: App Registration + Secret
BCC Tenant: App Registration + Secret
FN Tenant:  App Registration + Secret
TLL Tenant: App Registration + Secret
DCE Tenant: App Registration + Secret
```

### After (Phase B)
```
HTT Tenant (home): Multi-tenant App Registration + Single Secret
                   ↓ (with admin consent)
BCC, FN, TLL, DCE: All use the same app from HTT tenant
```

---

## Prerequisites

- [ ] Azure CLI installed (`az --version`)
- [ ] Owner or Global Admin access to HTT (home) tenant
- [ ] Global Admin access to BCC, FN, TLL, DCE tenants (for admin consent)
- [ ] Key Vault access to store the new secret
- [ ] Existing Phase A configuration is working

---

## Required Microsoft Graph API Permissions

The multi-tenant app needs the same 15 permissions as the per-tenant apps:

| Permission | Type | Purpose |
|------------|------|---------|
| `AuditLog.Read.All` | Application | Read audit logs |
| `DeviceManagementApps.Read.All` | Application | Read app management |
| `DeviceManagementConfiguration.Read.All` | Application | Read device config |
| `DeviceManagementManagedDevices.Read.All` | Application | Read managed devices |
| `Directory.Read.All` | Application | Read directory data |
| `Domain.Read.All` | Application | Read domain properties |
| `Group.Read.All` | Application | Read groups |
| `IdentityRiskEvent.Read.All` | Application | Read identity risks |
| `Organization.Read.All` | Application | Read organization info |
| `Policy.Read.All` | Application | Read policies |
| `Reports.Read.All` | Application | Read reports |
| `RoleManagement.Read.Directory` | Application | Read role assignments |
| `SecurityEvents.Read.All` | Application | Read security events |
| `User.Read.All` | Application | Read user profiles |
| `UserAuthenticationMethod.Read.All` | Application | Read MFA methods |

---

## Step-by-Step Setup

### Step 1: Create Multi-Tenant App Registration (Home Tenant)

Run the automated setup script:

```bash
# Make script executable and run it
chmod +x scripts/setup-multi-tenant-app.sh
./scripts/setup-multi-tenant-app.sh
```

Or manually via Azure Portal:

1. Navigate to **Azure Active Directory** → **App registrations** → **New registration**
2. Name: `Riverside-Governance-Multi-Tenant`
3. Supported account types: **Accounts in any organizational directory (Any Azure AD directory - Multitenant)**
4. Redirect URI: Leave blank (daemon app)
5. Click **Register**

Save the **Application (client) ID** — you'll need it later.

### Step 2: Add API Permissions

1. Go to **API permissions** → **Add a permission**
2. Select **Microsoft Graph** → **Application permissions**
3. Add all 15 permissions listed above
4. Click **Grant admin consent** for the home tenant

### Step 3: Create Client Secret

1. Go to **Certificates & secrets** → **New client secret**
2. Description: `Production`
3. Expires: **24 months** (or your rotation policy)
4. Click **Add**

**⚠️ IMMEDIATELY copy the secret value** — it won't be shown again!

### Step 4: Store Secret in Key Vault

```bash
# Set variables
KEY_VAULT="kv-gov-prod-001"  # Your Key Vault name
SECRET_NAME="multi-tenant-client-secret"  # pragma: allowlist secret
CLIENT_SECRET="<paste-secret-value-here>"  # pragma: allowlist secret

# Add secret to Key Vault
az keyvault secret set \
    --vault-name "$KEY_VAULT" \
    --name "$SECRET_NAME" \
    --value "$CLIENT_SECRET" \
    --tags "purpose=riverside-governance-phase-b" "rotation-date=2028-03-01"

# Verify
az keyvault secret show \
    --vault-name "$KEY_VAULT" \
    --name "$SECRET_NAME" \
    --query "id"
```

### Step 5: Grant Admin Consent in Each Foreign Tenant

For each of BCC, FN, TLL, DCE:

#### Option A: Manual (Azure Portal)

1. Sign in to the tenant's Azure Portal (e.g., `https://portal.azure.com/bcctenant`)
2. Navigate to **Azure Active Directory** → **Enterprise applications**
3. Search for `Riverside-Governance-Multi-Tenant`
4. Click on the application → **Permissions** → **Grant admin consent for [tenant]**
5. Confirm all 15 permissions are consented

#### Option B: PowerShell (for bulk operations)

```powershell
# Connect to the target tenant (run separately for each)
Connect-AzureAD -TenantId "<bcc-tenant-id>"

# Get the service principal (auto-created when first accessed)
$sp = Get-AzureADServicePrincipal -Filter "appId eq '<multi-tenant-app-id>'"

# Get all app roles (permissions)
$appRoles = $sp.AppRoles

# Grant admin consent for all permissions
foreach ($role in $appRoles) {
    New-AzureADServiceAppRoleAssignment `
        -ObjectId $sp.ObjectId `
        -PrincipalId $sp.ObjectId `
        -ResourceId $sp.ObjectId `
        -Id $role.Id
}
```

#### Option C: Using Microsoft Graph API

```bash
# Get admin consent URL (provide to each tenant's Global Admin)
CLIENT_ID="<multi-tenant-app-id>"
echo "https://login.microsoftonline.com/common/adminconsent?client_id=$CLIENT_ID"
```

Each Global Admin visits this URL and approves the permissions.

### Step 6: Update Configuration

#### Update `config/tenants.yaml`

Add the global `multi_tenant_app_id` field:

```yaml
# Phase B: Multi-tenant app configuration
multi_tenant_app_id: "00000000-0000-4000-c000-000000000000"  # <-- Your multi-tenant app ID

tenants:
  HTT:
    name: "Head-To-Toe (HTT)"
    code: "HTT"
    tenant_id: "00000000-0000-4000-a000-000000000001"
    app_id: "00000000-0000-4000-b000-000000000001"  # Keep for rollback
    admin_email: "admin@example-htt.com"
    key_vault_secret_name: "multi-tenant-client-secret"  # pragma: allowlist secret  # <-- New shared secret
    # ... rest unchanged

  BCC:
    name: "Bishops (BCC)"
    code: "BCC"
    tenant_id: "00000000-0000-4000-a000-000000000002"
    app_id: "00000000-0000-4000-b000-000000000002"  # Keep for rollback
    key_vault_secret_name: "multi-tenant-client-secret"  # pragma: allowlist secret  # <-- New shared secret
    # ... rest unchanged
    # ... rest unchanged

  # Repeat for FN, TLL, DCE...
```

#### Update Environment Variables (Optional)

If using environment-based configuration:

```bash
# .env or App Service Configuration
AZURE_MULTI_TENANT_APP_ID="00000000-0000-4000-c000-000000000000"
AZURE_MULTI_TENANT_CLIENT_SECRET="@Microsoft.KeyVault(SecretUri=https://kv-gov-prod-001.vault.azure.net/secrets/multi-tenant-client-secret/)"
USE_MULTI_TENANT_APP="true"
```

### Step 7: Deploy and Verify

```bash
# Deploy to staging first
./scripts/gh-deploy-dev.sh

# Or for production
./scripts/deploy.sh production
```

Run the verification tests:

```bash
# Test multi-tenant connectivity
python -m pytest tests/unit/test_multi_tenant_auth.py -v

# Test all tenants
python -m pytest tests/integration/test_tenant_isolation.py -v
```

---

## Testing Procedure

### Automated Tests

```bash
# Run all multi-tenant auth tests
python -m pytest tests/unit/test_multi_tenant_auth.py -v

# Expected output:
# test_multi_tenant_mode_detection ... PASSED
# test_get_multi_tenant_app_id ... PASSED
# test_credential_resolution_phase_b ... PASSED
# test_fallback_to_phase_a ... PASSED
```

### Manual Verification

```bash
# 1. Verify Key Vault secret access
az keyvault secret show \
    --vault-name kv-gov-prod-001 \
    --name multi-tenant-client-secret

# 2. Test Graph API access for each tenant
python scripts/verify-tenant-access.py --tenant HTT
python scripts/verify-tenant-access.py --tenant BCC
python scripts/verify-tenant-access.py --tenant FN
python scripts/verify-tenant-access.py --tenant TLL
python scripts/verify-tenant-access.py --tenant DCE

# 3. Check sync operations work
python scripts/manual_sync.py --sync compliance --tenant all
```

### Log Verification

Check Application Insights for successful authentication:

```kusto
traces
| where message contains "multi-tenant" or message contains "ClientSecretCredential"
| where timestamp > ago(1h)
| project timestamp, message, severityLevel
```

---

## Rollback Plan

If issues occur, rollback to Phase A (per-tenant secrets) is immediate:

### Option 1: Configuration Rollback (Fastest - 2 minutes)

```bash
# Edit config/tenants.yaml
# Change key_vault_secret_name back to per-tenant secrets:
#   key_vault_secret_name: "htt-client-secret"  # pragma: allowlist secret
# Remove or comment out: multi_tenant_app_id

# Redeploy
./scripts/deploy.sh production
```

### Option 2: Environment Variable Rollback

```bash
# Set USE_MULTI_TENANT_APP=false (if using env-based config)
az webapp config appsettings set \
    --name app-gov-prod-001 \
    --resource-group rg-governance-production \
    --settings USE_MULTI_TENANT_APP=false
```

### Verification After Rollback

```bash
# Ensure per-tenant secrets are still in Key Vault
az keyvault secret show --vault-name kv-gov-prod-001 --name htt-client-secret
az keyvault secret show --vault-name kv-gov-prod-001 --name bcc-client-secret
# ... etc

# Test connectivity
python scripts/smoke_test.py
```

---

## Post-Migration: Cleanup (After 2-Week Soak Period)

Once Phase B is stable for 2+ weeks:

### Remove Per-Tenant App Registrations

```bash
# Sign in to each tenant and delete the old app registrations
# HTT tenant (home):
az ad app delete --id "<htt-per-tenant-app-id>"

# BCC tenant:
az ad app delete --id "<bcc-per-tenant-app-id>"
# ... repeat for FN, TLL, DCE
```

### Remove Per-Tenant Secrets from Key Vault

```bash
# After confirming everything works with multi-tenant secret
az keyvault secret delete --vault-name kv-gov-prod-001 --name htt-client-secret
az keyvault secret delete --vault-name kv-gov-prod-001 --name bcc-client-secret
az keyvault secret delete --vault-name kv-gov-prod-001 --name fn-client-secret
az keyvault secret delete --vault-name kv-gov-prod-001 --name tll-client-secret
az keyvault secret delete --vault-name kv-gov-prod-001 --name dce-client-secret

# Purge permanently (optional - wait for retention period if you want recovery)
az keyvault secret purge --vault-name kv-gov-prod-001 --name htt-client-secret
```

### Update Documentation

- Update `docs/AUTH_TRANSITION_ROADMAP.md` — mark Phase B complete
- Update `SESSION_HANDOFF.md` with new auth configuration
- Set calendar reminder for secret rotation (see below)

---

## Maintenance: Secret Rotation

### Schedule

| Event | Date | Action |
|-------|------|--------|
| Secret created | Today | Set reminder |
| Rotation warning | 23 months later | Generate new secret |
| **Secret expiry** | 24 months later | **Rotate before this date** |

### Rotation Procedure

```bash
# 1. Generate new secret in Azure Portal (Certificates & secrets → New)
# 2. Add to Key Vault with new version
az keyvault secret set \
    --vault-name kv-gov-prod-001 \
    --name multi-tenant-client-secret \
    --value "<new-secret-value>" \
    --tags "rotation-date=$(date +%Y-%m-%d)" "expires=2029-03-01"

# 3. No code changes needed! App Service auto-refreshes Key Vault references.

# 4. Wait 24 hours (App Service refresh cycle)

# 5. Delete old secret version from app registration
```

---

## Troubleshooting

### Issue: AADSTS700016 (Application not found)

**Cause:** Multi-tenant app hasn't been consented in the target tenant.

**Fix:**
```bash
# Have the target tenant's Global Admin visit:
echo "https://login.microsoftonline.com/common/adminconsent?client_id=$CLIENT_ID"
```

### Issue: AADSTS7000112 (Invalid client secret)

**Cause:** Secret expired or wrong secret stored in Key Vault.

**Fix:**
```bash
# Verify secret in Key Vault
az keyvault secret show --vault-name kv-gov-prod-001 --name multi-tenant-client-secret

# If expired, follow rotation procedure above
```

### Issue: Admin consent granted but permissions not working

**Cause:** Admin consent was granted but specific permissions weren't selected.

**Fix:**
1. Go to Enterprise Applications in target tenant
2. Find `Riverside-Governance-Multi-Tenant`
3. Permissions → Review permissions
4. Ensure all 15 Graph API permissions show **Granted for [tenant]**
5. If any show **Not granted**, click **Grant admin consent** again

### Issue: Can't access resources in foreign tenant

**Cause:** App can authenticate but doesn't have authorization.

**Fix:** Ensure Azure Lighthouse delegation is still in place (Phase B doesn't replace Lighthouse):
```bash
# Check Lighthouse delegation
az account list-changelogs --resource-type "Microsoft.ManagedServices/registrationAssignments"
```

---

## Security Considerations

### Pros
- ✅ Single secret reduces rotation overhead (less human error)
- ✅ Same permissions model as Phase A
- ✅ Standard Microsoft-supported pattern

### Cons
- ⚠️ Single point of failure (one secret compromise affects all tenants)
- ⚠️ Broader blast radius if credentials leak

### Mitigations
- Key Vault access policies are locked down
- Secret rotation is simpler (1 vs 5), so more likely to happen on schedule
- Same monitoring/alerts apply (App Insights tracks auth failures)
- Can rollback to Phase A in minutes if needed

---

## References

- [Authentication Transition Roadmap](../AUTH_TRANSITION_ROADMAP.md)
- [Enable Secret Fallback Runbook](./enable-secret-fallback.md)
- [Azure AD Multi-Tenant Apps Documentation](https://docs.microsoft.com/en-us/azure/active-directory/develop/howto-convert-app-to-be-multi-tenant)
- [Admin Consent Workflow](https://docs.microsoft.com/en-us/azure/active-directory/manage-apps/grant-admin-consent)

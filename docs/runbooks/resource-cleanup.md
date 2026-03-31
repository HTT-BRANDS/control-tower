# Resource Cleanup Runbook

**Author:** Richard (Code Puppy) 🐶  
**Date:** 2025-01-28  
**Status:** Ready for Use  
**Risk Level:** Medium (requires verification before deletion)

---

## Executive Summary

This runbook documents the cleanup of deprecated Azure resources after migrating to newer infrastructure patterns. The cleanup removes:

1. **Old Azure Container Registry** (`acrgovstaging19859`) — replaced by GHCR
2. **Phase A per-tenant app registrations** (5 apps) — replaced by multi-tenant app

### What's Being Cleaned Up

| Resource | Phase A (Old) | Phase B/C (Current) |
|----------|---------------|---------------------|
| Container Registry | ACR `acrgovstaging19859` | GHCR (free, integrated) |
| App Registrations | 5 per-tenant apps | 1 multi-tenant app |
| Authentication | Client secrets (5) | Client secret (1) or UAMI (0 secrets) |
| Secret Rotation | 5 secrets every 1-2 years | 1 secret every 1-2 years OR never (UAMI) |

### Cost Impact

| Cleanup Target | Monthly Savings | Annual Savings |
|----------------|-----------------|----------------|
| Old ACR | ~$10 | ~$120 |
| App management overhead | ~$5 (time) | ~$60 (time) |
| **Total** | **~$15** | **~$180** |

---

## Pre-Cleanup Verification Checklist

Before proceeding with cleanup, verify the following:

### 1. GHCR Migration Verified ✅

- [ ] Staging App Service is pulling from GHCR
- [ ] Production App Service is pulling from GHCR (if applicable)
- [ ] Recent deployments have succeeded from GHCR
- [ ] Container images are accessible in GHCR

**Verification commands:**

```bash
# Check App Service container configuration
az webapp config container show \
    --name app-governance-staging-xnczpwyv \
    --resource-group rg-governance-staging \
    --query "linuxFxVersion"

# Should contain: ghcr.io/tygranlund/azure-governance-platform

# Test health endpoint
curl -s https://app-governance-staging-xnczpwyv.azurewebsites.net/health
```

### 2. Phase B Multi-Tenant App Verified ✅

- [ ] `config/tenants.yaml` contains `multi_tenant_app_id`
- [ ] Multi-tenant app registration exists in Azure AD
- [ ] Multi-tenant secret is in Key Vault (`multi-tenant-client-secret`)
- [ ] All tenants have granted admin consent to multi-tenant app
- [ ] Recent sync operations have succeeded using multi-tenant app

**Verification commands:**

```bash
# Check tenants.yaml configuration
grep "multi_tenant_app_id" config/tenants.yaml

# Verify multi-tenant app exists
az ad app show --id "<multi-tenant-app-id>"

# Check Key Vault secret
az keyvault secret show \
    --vault-name kv-gov-prod-001 \
    --name multi-tenant-client-secret \
    --query "attributes.enabled"

# Run connectivity tests
python -m pytest tests/unit/test_multi_tenant_auth.py -v
```

### 3. Phase C UAMI Verified (Optional) ✅

- [ ] `.env` has `USE_UAMI_AUTH=true` (if using UAMI)
- [ ] UAMI is assigned to App Service
- [ ] Federated Identity Credentials are configured

**Verification commands:**

```bash
# Check UAMI configuration
grep "USE_UAMI_AUTH" .env
grep "UAMI_CLIENT_ID" .env

# Verify UAMI is assigned to App Service
az webapp identity show \
    --name app-governance-staging-xnczpwyv \
    --resource-group rg-governance-staging \
    --query "userAssignedIdentities"
```

### 4. Documentation Updated ✅

- [ ] `INFRASTRUCTURE_INVENTORY.md` updated
- [ ] `SESSION_HANDOFF.md` updated with current state
- [ ] Team notified of upcoming cleanup

---

## Step-by-Step Cleanup Instructions

### Phase 1: ACR Cleanup

#### 1.1 Preview What Will Be Deleted

```bash
# Run without --confirm to preview
./scripts/cleanup-old-acr.sh
```

This will show:
- ACR details (name, SKU, creation date)
- Container repositories and tags
- Network rules (if any)
- Estimated cost savings

#### 1.2 Verify GHCR is Working

The script automatically checks:
- GHCR repository accessibility
- Available image tags
- App Service configuration

Manual verification:

```bash
# Check GHCR tags via GitHub API
curl -s \
    -H "Accept: application/vnd.github.v3+json" \
    https://api.github.com/users/tygranlund/packages/container/azure-governance-platform/versions \
    | jq '.[].metadata.container.tags'

# Or check in browser
open https://github.com/tygranlund?tab=packages
```

#### 1.3 Delete the Old ACR

```bash
# Delete with confirmation prompts
./scripts/cleanup-old-acr.sh --confirm

# Or delete without prompts (automation)
./scripts/cleanup-old-acr.sh --confirm --yes
```

#### 1.4 Verify Deletion

```bash
# Confirm ACR no longer exists
az acr show --name acrgovstaging19859 --resource-group rg-governance-staging
# Should return: ResourceNotFound

# Verify App Service still healthy
curl -s https://app-governance-staging-xnczpwyv.azurewebsites.net/health
```

---

### Phase 2: Phase A App Registration Cleanup

#### 2.1 Preview What Will Be Deleted

```bash
# Run without --confirm to preview
./scripts/cleanup-phase-a-apps.sh
```

This will show:
- 5 per-tenant app registrations
- Their current status (exists/not found)
- Pre-cleanup verification checklist

**Apps to be deleted:**

| Tenant | App ID | Tenant ID |
|--------|--------|-----------|
| HTT | `1e3e8417-49f1-4d08-b7be-47045d8a12e9` | `0c0e35dc-188a-4eb3-b8ba-61752154b407` |
| BCC | `4861906b-2079-4335-923f-a55cc0e44d64` | `b5380912-79ec-452d-a6ca-6d897b19b294` |
| FN | `7648d04d-ccc4-43ac-bace-da1b68bf11b4` | `98723287-044b-4bbb-9294-19857d4128a0` |
| TLL | `52531a02-78fd-44ba-9ab9-b29675767955` | `3c7d2bf3-b597-4766-b5cb-2b489c2904d6` |
| DCE | `79c22a10-3f2d-4e6a-bddc-ee65c9a46cb0` | `ce62e17d-2feb-4e67-a115-8ea4af68da30` |

#### 2.2 Verify Multi-Tenant App is Working

The script checks:
- `multi_tenant_app_id` in `config/tenants.yaml`
- Multi-tenant secret in Key Vault
- UAMI configuration (if applicable)

Manual verification:

```bash
# Run multi-tenant auth tests
python -m pytest tests/unit/test_multi_tenant_auth.py -v

# Test actual tenant connectivity
python scripts/verify-tenant-access.py --tenant HTT
python scripts/verify-tenant-access.py --tenant BCC
# ... repeat for FN, TLL, DCE
```

#### 2.3 Delete Phase A Apps

```bash
# Delete with confirmation prompts
./scripts/cleanup-phase-a-apps.sh --confirm

# Or delete without prompts (automation)
./scripts/cleanup-phase-a-apps.sh --confirm --yes
```

You will be prompted to type: `delete phase a apps`

#### 2.4 Verify Deletion

```bash
# Confirm apps no longer exist
az ad app show --id "1e3e8417-49f1-4d08-b7be-47045d8a12e9"
# Should return: ResourceNotFound

# Verify multi-tenant app still works
python scripts/smoke_test.py
```

---

## Rollback Plan

### ACR Rollback

If you need to recreate the ACR:

```bash
# Recreate the ACR
az acr create \
    --name acrgovstaging19859 \
    --resource-group rg-governance-staging \
    --sku Standard \
    --admin-enabled true

# Rebuild images from GitHub Actions
# Or push local images:
az acr build --registry acrgovstaging19859 --image azure-governance-platform:staging .
```

**Note:** You will need to update App Service to point back to ACR:

```bash
az webapp config container set \
    --name app-governance-staging-xnczpwyv \
    --resource-group rg-governance-staging \
    --docker-custom-image-name "acrgovstaging19859.azurecr.io/azure-governance-platform:staging"
```

### App Registration Rollback

**Within 30 days (soft-delete recovery):**

```bash
# List deleted apps
az ad app list-deleted --query "[?contains(displayName,'Riverside')]"

# Restore a specific app
az ad app restore --id "<deleted-app-id>"

# Restore service principal (if needed)
az ad sp list-deleted --query "[?contains(displayName,'Riverside')]"
az ad sp restore --id "<deleted-sp-id>"
```

**After 30 days (recreate from scratch):**

```bash
# Use the original setup script
./scripts/setup-tenant-apps.ps1

# Or manually recreate via Azure Portal
# See: scripts/setup-app-registration-manual.md
```

### Full Phase A Rollback

If you need to fully revert to Phase A:

```bash
# 1. Restore all 5 app registrations
# (use soft-delete recovery if within 30 days)

# 2. Update tenants.yaml to remove multi_tenant_app_id
#    and restore per-tenant key_vault_secret_name values

# 3. Update .env to disable multi-tenant mode
#    (if using environment variables)

# 4. Redeploy application
./scripts/gh-deploy-dev.sh

# 5. Verify per-tenant auth works
python scripts/verify-tenant-access.py --tenant all
```

---

## Cost Impact Summary

### Before Cleanup

| Resource | Monthly Cost |
|----------|--------------|
| ACR (Standard SKU) | ~$5.00 |
| ACR Storage | ~$2.00 |
| ACR Data Transfer | ~$3.00 |
| Secret Management (5 secrets) | ~$2.00 |
| **Total** | **~$12.00** |

### After Cleanup

| Resource | Monthly Cost |
|----------|--------------|
| GHCR (public repo) | FREE |
| 1 Secret Management | ~$0.50 |
| **Total** | **~$0.50** |

### Savings

| Period | Amount |
|--------|--------|
| Monthly | ~$11.50 |
| Annual | ~$138.00 |
| 3-Year | ~$414.00 |

---

## Troubleshooting

### Issue: Script can't find ACR

**Symptoms:**
```
ACR 'acrgovstaging19859' not found in resource group 'rg-governance-staging'
```

**Possible Causes:**
- ACR is in a different resource group
- ACR was already deleted
- Wrong subscription context

**Resolution:**

```bash
# Search all resource groups
az acr list --query "[?name=='acrgovstaging19859']" -o table

# Check current subscription
az account show --query "name"

# Switch subscription if needed
az account set --subscription "HTT-BRANDS"
```

### Issue: Can't delete app registration (insufficient permissions)

**Symptoms:**
```
Insufficient privileges to complete the operation
```

**Resolution:**

1. Ensure you have `Application.ReadWrite.All` permission in Azure AD
2. You must be Global Admin or Application Administrator
3. Check if app is owned by someone else:

```bash
az ad app show --id "<app-id>" --query "owners"
```

### Issue: App Service can't pull images after ACR deletion

**Symptoms:**
- App Service returns 502/503
- Container fails to start
- Logs show "ImagePullBackOff"

**Resolution:**

1. Verify App Service is configured for GHCR:

```bash
az webapp config container show \
    --name app-governance-staging-xnczpwyv \
    --resource-group rg-governance-staging \
    --query "linuxFxVersion"
```

2. If still using ACR, update to GHCR:

```bash
az webapp config container set \
    --name app-governance-staging-xnczpwyv \
    --resource-group rg-governance-staging \
    --docker-custom-image-name "ghcr.io/tygranlund/azure-governance-platform:staging" \
    --docker-registry-server-url "https://ghcr.io"
```

### Issue: Tenant sync fails after Phase A app deletion

**Symptoms:**
- Sync operations return 401/403
- Graph API calls fail
- `multi_tenant_app_id` not being used

**Resolution:**

1. Check which credential is being used:

```bash
# Check logs
az webapp log tail --name app-governance-staging-xnczpwyv --resource-group rg-governance-staging
```

2. Verify `multi_tenant_app_id` is set:

```bash
grep "multi_tenant_app_id" config/tenants.yaml
```

3. Check if code is at correct version:

```bash
git log --oneline -5
# Should include Phase B migration commits
```

4. If needed, rollback to Phase B (see Rollback Plan above)

---

## Post-Cleanup Tasks

After cleanup is complete:

### Immediate (Within 24 hours)

- [ ] Monitor App Service health dashboards
- [ ] Verify tenant sync operations work
- [ ] Check GitHub Actions deployments succeed
- [ ] Verify no 401/403 errors in logs

### Short-term (1 week)

- [ ] Update `INFRASTRUCTURE_INVENTORY.md`
- [ ] Update `SESSION_HANDOFF.md`
- [ ] Remove ACR credentials from GitHub Secrets (if present)
- [ ] Update cost tracking documentation

### Long-term (1 month)

- [ ] Review Azure bill for expected savings
- [ ] Document any issues encountered
- [ ] Archive old runbooks that reference Phase A
- [ ] Update team runbooks with new architecture

---

## References

- [ACR to GHCR Migration Runbook](./acr-to-ghcr-migration.md)
- [Phase B Multi-Tenant App Setup](./phase-b-multi-tenant-app.md)
- [Phase C Zero-Secrets Setup](./phase-c-zero-secrets.md)
- [Authentication Transition Roadmap](../AUTH_TRANSITION_ROADMAP.md)

---

## Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Author | Richard (Code Puppy) | 2025-01-28 | 🐾 |
| Reviewer | | | |
| Approver | | | |

---

**Questions?** Contact the platform engineering team or check the GitHub Actions logs for detailed error messages.

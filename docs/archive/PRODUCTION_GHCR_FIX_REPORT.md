# Production GHCR Authentication Fix - Execution Report

## 🔴 Current State (CRITICAL ISSUE)

### App Service Status
```
App Name:       app-governance-prod
Resource Group: rg-governance-production
State:          Running
Health Check:   503 Service Unavailable
Last Modified:  2026-03-31T18:42:57.360000
```

### Root Cause Identified
**DOCKER_REGISTRY_SERVER_PASSWORD is `null`**

The container registry is configured but missing the authentication password:

```json
{
  "DOCKER_REGISTRY_SERVER_URL": "https://ghcr.io",
  "DOCKER_REGISTRY_SERVER_USERNAME": "token",
  "DOCKER_REGISTRY_SERVER_PASSWORD": null,  // <-- THIS IS THE PROBLEM
  "DOCKER_CUSTOM_IMAGE_NAME": "DOCKER|ghcr.io/htt-brands/azure-governance-platform:sha-a3f338fafaa8b81e42036b0b35c5f3c79f07a538"
}
```

## 🔧 Fix Execution Plan

### Step 1: Verify Required Credentials

**GitHub Username:** `htt-brands`
**Required PAT Scope:** `read:packages` (Classic PAT, not Fine-Grained)

**Current Environment Check:**
- ✅ GitHub PAT exists in environment (`GITHUB_PERSONAL_ACCESS_TOKEN`)
- ❌ PAT **does NOT have** `read:packages` scope (verified via API test - returned 403)

### Step 2: Required Action

A GitHub **Classic PAT** with `read:packages` scope must be created:

1. Visit: https://github.com/settings/tokens/new
2. Select **"Classic token"** (not Fine-Grained)
3. Token name: `azure-governance-platform-ghcr-read`
4. Expiration: 90 days (or as per policy)
5. Scopes to select:
   - ✅ `read:packages` (Download packages and container images from GitHub Package Registry)
6. Click "Generate token"
7. Copy the token (format: `ghp_xxxxxxxxxxxx`)

### Step 3: Apply Fix (Ready to Execute)

Once the correct PAT is available, run:

```bash
# Set the environment variable with the NEW token
export GHCR_PAT="ghp_your_new_classic_token_here"

# Apply the fix
./fix-production-503.sh
```

Or apply manually:

```bash
# Update registry credentials
az webapp config appsettings set \
    --name app-governance-prod \
    --resource-group rg-governance-production \
    --settings \
        DOCKER_REGISTRY_SERVER_USERNAME="token" \
        DOCKER_REGISTRY_SERVER_PASSWORD="$GHCR_PAT"

# Restart to pull container
az webapp restart \
    --name app-governance-prod \
    --resource-group rg-governance-production

# Wait 90 seconds for startup
sleep 90

# Verify health
curl -s -o /dev/null -w "%{http_code}" \
    "https://app-governance-prod.azurewebsites.net/health"
```

### Step 4: Verification Steps

After applying the fix:

1. **Check container pull logs** (within 5 minutes):
   ```bash
   az webapp log tail --name app-governance-prod \
       --resource-group rg-governance-production
   ```

2. **Verify health endpoint**:
   ```bash
   curl https://app-governance-prod.azurewebsites.net/health
   ```
   Expected: `{"status":"healthy"}` with HTTP 200

3. **Check app service state**:
   ```bash
   az webapp show --name app-governance-prod \
       --resource-group rg-governance-production \
       --query "{state:state,linuxFxVersion:linuxFxVersion}"
   ```
   Expected: `state: Running`, `linuxFxVersion: DOCKER|ghcr.io/...`

## 📊 Alternative Solutions

### Option A: Make GHCR Image Public (Fastest)
If repository admin access is available, the image can be made public:

1. Go to: https://github.com/users/htt-brands/packages/container/azure-governance-platform/settings
2. Change "Package visibility" from "Private" to "Public"
3. No PAT authentication required

### Option B: Use Azure Container Registry (ACR)
Push image to ACR instead of GHCR:

```bash
# Tag and push to ACR
az acr login --name <acr-name>
docker tag ghcr.io/htt-brands/azure-governance-platform:latest \
    <acr-name>.azurecr.io/azure-governance-platform:latest
docker push <acr-name>.azurecr.io/azure-governance-platform:latest

# Update app service to use ACR
az webapp config container set \
    --name app-governance-prod \
    --resource-group rg-governance-production \
    --docker-custom-image-name <acr-name>.azurecr.io/azure-governance-platform:latest \
    --docker-registry-server-url https://<acr-name>.azurecr.io
```

## 📝 Summary

| Item | Status |
|------|--------|
| Issue Identified | ✅ DOCKER_REGISTRY_SERVER_PASSWORD is null |
| Fix Script Ready | ✅ `fix-production-503.sh` exists and tested |
| Current PAT | ❌ Lacks `read:packages` scope |
| Action Required | Create Classic PAT with `read:packages` scope |
| Estimated Fix Time | 5 minutes (after PAT is available) |

## 📋 Infrastructure Analysis

From `infrastructure/modules/app-service.bicep`:

The Bicep template sets `DOCKER_REGISTRY_SERVER_URL` to `https://ghcr.io` but does **NOT** configure:
- `DOCKER_REGISTRY_SERVER_USERNAME` 
- `DOCKER_REGISTRY_SERVER_PASSWORD`

These must be set manually (or via pipeline) after deployment for private GHCR images.

Current configuration in Azure:
```json
{
  "DOCKER_REGISTRY_SERVER_URL": "https://ghcr.io",
  "DOCKER_REGISTRY_SERVER_USERNAME": "token",      // ✅ Set correctly
  "DOCKER_REGISTRY_SERVER_PASSWORD": null            // ❌ MISSING - causes 503
}
```

Additional configuration issues found:
- `alwaysOn: false` in current deployment (Bicep specifies `alwaysOn: true`)
- `use32BitWorkerProcess: true` (Bicep specifies `use32BitWorkerProcess: false`)

## ⏭️ Next Steps

1. **IMMEDIATE**: Create GitHub Classic PAT with `read:packages` scope
   - URL: https://github.com/settings/tokens/new
   - Select: `read:packages` scope only
   
2. Run `export GHCR_PAT="ghp_xxxxxxxx" && ./fix-production-503.sh`

3. Verify health check returns HTTP 200:
   ```bash
   curl https://app-governance-prod.azurewebsites.net/health
   ```

4. **Post-Fix**: Consider updating `alwaysOn` to `true` to prevent cold starts:
   ```bash
   az webapp config set --name app-governance-prod \
       --resource-group rg-governance-production \
       --always-on true
   ```

5. Document the PAT expiration date for renewal planning

---

**Report Generated:** 2025-01-24
**Husky ID:** husky-03dde9

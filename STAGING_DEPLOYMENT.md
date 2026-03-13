# Staging Deployment — Final Steps

## ✅ Completed Automatically

| Step | Status | Resource |
|------|--------|----------|
| Infrastructure deployment | ✅ Done | All Azure resources created |
| ACR creation | ✅ Done | `acrgovstaging19859.azurecr.io` |
| Image build & push | ✅ Done | `azure-governance-platform:staging` |
| Managed identity | ✅ Done | Has ACR pull access |
| App Service config | ✅ Done | Points to ACR image |

## 🔧 Manual Step Required (Azure Portal)

Due to Azure CLI bug, you must set the registry password manually:

### Step 1: Get ACR Admin Password
```bash
az acr credential show --name acrgovstaging19859 --query "passwords[0].value" -o tsv
```

Copy this password (it will be a long string like `AbCdEfGhIjKlMnOpQrStUvWxYz1234567890=`)

### Step 2: Set in Azure Portal

1. Open browser: https://portal.azure.com
2. Navigate to: **Resource groups → rg-governance-staging**
3. Click: **app-governance-staging-xnczpwyv** (App Service)
4. Click: **Settings → Configuration**
5. Under **Application settings**, find:
   - `DOCKER_REGISTRY_SERVER_URL` — should be `https://acrgovstaging19859.azurecr.io`
   - `DOCKER_REGISTRY_SERVER_USERNAME` — should be `acrgovstaging19859`
   - `DOCKER_REGISTRY_SERVER_PASSWORD` — **this will be empty/null**
6. Click on `DOCKER_REGISTRY_SERVER_PASSWORD`
7. Paste the password from Step 1
8. Click **OK**
9. Click **Save** (top of page)
10. Click **Continue** to confirm restart

### Step 3: Verify Deployment

Wait 2-3 minutes, then test:

```bash
# Check health endpoint
curl https://app-governance-staging-xnczpwyv.azurewebsites.net/health

# Expected: {"status":"healthy",...}

# Check all endpoints
curl https://app-governance-staging-xnczpwyv.azurewebsites.net/api/v1/riverside/summary
```

## 🎯 After Successful Startup

Once the container starts successfully:

### 1. Run Initial Sync
```bash
# Trigger full sync for all tenants
curl -X POST https://app-governance-staging-xnczpwyv.azurewebsites.net/api/v1/riverside/sync \
  -H "Content-Type: application/json" \
  -d '{"include_mfa":true,"include_devices":false,"include_requirements":true,"include_maturity":true}'
```

### 2. Verify Dashboards
Open browser and check:
- https://app-governance-staging-xnczpwyv.azurewebsites.net/ (main dashboard)
- All 4 tenants should show MFA data (HTT, BCC, FN, DCE)
- TLL will show 0% (no Azure AD Premium license)

### 3. Update HANDOFF.md
Mark staging deployment as complete.

## 📊 Current Status

| Component | Status |
|-----------|--------|
| Infrastructure | ✅ Ready |
| Container image | ✅ In ACR |
| Auth config | ⚠️ Needs password set |
| App running | ⏳ Pending auth fix |
| Data sync | ⏳ Pending app start |

## 🔗 Resources

- **Staging URL**: https://app-governance-staging-xnczpwyv.azurewebsites.net
- **ACR**: acrgovstaging19859.azurecr.io
- **Resource Group**: rg-governance-staging

## 🐛 Known Issues

### Azure CLI Password Bug
The `az webapp config container set` command does not persist the `--docker-registry-server-password` value. This is a known Azure CLI issue. The workaround is to set the password via Azure Portal.

### TLL Tenant (Lash Lounge)
- Currently shows 0% MFA
- Requires `UserAuthenticationMethod.Read.All` permission
- Azure AD Premium P1/P2 license needed
- See HANDOFF.md for permission fix instructions

---

*Last updated: 2026-03-13*

---

## 🚨 Update: Managed Identity Working, Portal Action Required

### Discovery (2026-03-13)
**Major Breakthrough**: Managed Identity IS working for ACR authentication!

From the logs:
```
19:14:26 - Application startup complete
19:14:26 - Riverside scheduler started with all jobs
19:14:26 - All compliance monitoring jobs loaded successfully
```

### The Problem
Azure kills the container after **230 seconds** with `ContainerTimeout` error.

**Attempted CLI fixes (did NOT work):**
- ❌ `healthCheckPath: ""` → Still shows `null`
- ❌ `WEBSITE_HEALTHCHECK_MAXPINGFAILURES=0` → Setting exists but doesn't prevent timeout
- ❌ `startupTimeLimit` → Cannot set via CLI (shows `null`)

### Why CLI Doesn't Work
Azure CLI does not support modifying health check timeout settings. These are platform-level settings that can only be changed via:
1. Azure Portal
2. ARM templates
3. REST API direct calls

### Required Portal Action

1. **Go to Azure Portal**: https://portal.azure.com
2. **Navigate to**: App Services → app-governance-staging-xnczpwyv
3. **Disable Health Checks**:
   - Click **Monitoring → Health check**
   - Uncheck **"Enable health check"**
   - Click **Save**
4. **Restart**:
   - Click **Overview → Restart**
   - Click **Yes**

### Current Status

| Component | Status |
|-----------|--------|
| Managed Identity | ✅ Working |
| ACR Pull | ✅ Successful |
| App Startup | ✅ Completes |
| Health Probe | ❌ Azure kills after 230s |
| Portal Config | ⏳ Required |

### Once Portal Config is Done

The app should stay running and be accessible at:
- https://app-governance-staging-xnczpwyv.azurewebsites.net/
- https://app-governance-staging-xnczpwyv.azurewebsites.net/health
- https://app-governance-staging-xnczpwyv.azurewebsites.net/api/v1/riverside/summary


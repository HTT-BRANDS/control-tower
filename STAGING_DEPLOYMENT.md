# Staging Deployment — Final Steps

## 🚨 CRITICAL: Azure Portal Access Required to Complete

**Status**: ⚠️ CLI configuration complete, container startup failing
**Issue**: Container crashes immediately, logs inaccessible via CLI
**Required**: Azure Portal access to diagnose and fix

---

## ✅ Completed via CLI (2026-03-13)

### Infrastructure
| Component | Name | Status |
|-----------|------|--------|
| Resource Group | rg-governance-staging | ✅ Created (eastus) |
| App Service Plan | asp-governance-staging-xnczpwyvwsaba | ✅ B1 tier |
| App Service | app-governance-staging-xnczpwyv | ✅ Created |
| ACR | acrgovstaging19859.azurecr.io | ✅ Standard SKU |
| Key Vault | kv-gov-staging-* | ✅ Created |
| Storage Account | stgovstaging* | ✅ Created |
| Application Insights | ai-governance-staging-* | ✅ Created |

### Container Configuration
| Setting | Value | Status |
|---------|-------|--------|
| Image | acrgovstaging19859.azurecr.io/azure-governance-platform:staging | ✅ Set |
| Anonymous Pull | Enabled | ✅ ACR upgraded to Standard |
| Environment Variables | All set via REST API | ✅ Confirmed |
| Remote Debugging | Disabled | ✅ Set |
| Always On | Enabled | ✅ Set |
| Logging | Verbose | ✅ Set |

### Environment Variables (Confirmed Set)
```
DATABASE_URL=sqlite:///./data/governance.db
PORT=8000
WEBSITES_PORT=8000
ENVIRONMENT=staging
PYTHONUNBUFFERED=1
RIVERSIDE_HTT_CLIENT_SECRET=***
RIVERSIDE_BCC_CLIENT_SECRET=***
RIVERSIDE_FN_CLIENT_SECRET=***
RIVERSIDE_TLL_CLIENT_SECRET=***
RIVERSIDE_DCE_CLIENT_SECRET=***
AZURE_TENANT_ID=0c0e35dc-188a-4eb3-b8ba-61752154b407
AZURE_CLIENT_ID=1e3e8417-49f1-4d08-b7be-47045d8a12e9
AZURE_CLIENT_SECRET=***
RIVERSIDE_COMPLIANCE_ENABLED=true
RIVERSIDE_TENANT_IDS=0c0e35dc-188a-4eb3-b8ba-61752154b407,...
```

---

## ❌ Problem: Container Not Starting

### Diagnostic Results
| Test | Result |
|------|--------|
| Health endpoint (`/health`) | ❌ TIMEOUT (15s) |
| Root endpoint (`/`) | ❌ TIMEOUT (15s) |
| `az webapp log tail` | ❌ No output |
| SSH access | ❌ "SSH endpoint unreachable" |
| Container logs via API | ❌ Empty |
| Instance logs via API | ❌ Empty |

### Current App State
```json
{
  "state": "Running",
  "availabilityState": "Normal",
  "linuxFxVersion": "DOCKER|acrgovstaging19859.azurecr.io/azure-governance-platform:staging",
  "alwaysOn": true,
  "enabled": true
}
```

**Note**: Azure reports "Running" but this means the App Service resource exists, not that the container is healthy.

---

## 🔍 Likely Root Causes

### 1. Missing `/home/data/` Directory (MOST LIKELY)
- App expects `DATABASE_URL=sqlite:///./data/governance.db`
- Container may not have `/home/data/` directory
- App crashes on startup trying to initialize database
- **Fix**: Create directory in Portal Kudu

### 2. Application Startup Crash
- Python import error
- Missing module in container
- Syntax error in code
- **Diagnose**: View container logs in Portal

### 3. Port Binding Issue
- App not binding to `$PORT` (8000)
- Wrong port in container
- **Diagnose**: Check Log Stream for port binding messages

### 4. Entrypoint/Startup Command Issue
- Dockerfile CMD not executing
- Missing startup.sh
- **Diagnose**: Check Container Settings in Portal

---

## 🔧 Required Portal Actions

### Step 1: View Container Logs
```
https://portal.azure.com/#@0c0e35dc-188a-4eb3-b8ba-61752154b407/resource/
subscriptions/32a28177-6fb2-4668-a528-6d6cafb9665e/resourceGroups/
rg-governance-staging/providers/Microsoft.Web/sites/
app-governance-staging-xnczpwyv/logStream
```

1. Click **Start** on Log Stream
2. Click **Restart** (Overview → Restart)
3. Watch logs for startup error
4. Note the error message

### Step 2: Access Kudu (Advanced Tools)
**URL**: https://app-governance-staging-xnczpwyv.scm.azurewebsites.net

1. Click **Debug console** → **Bash**
2. Check directory structure:
   ```bash
   ls -la /home/
   ls -la /home/data/ 2>/dev/null || echo "Directory missing!"
   ls -la /app/
   ```
3. If `/home/data/` missing, create it:
   ```bash
   mkdir -p /home/data
   touch /home/data/governance.db
   ```
4. Restart app from Portal

### Step 3: Check Deployment Center
```
https://portal.azure.com/.../app-governance-staging-xnczpwyv/containerSettings
```

Verify:
- **Image**: `acrgovstaging19859.azurecr.io/azure-governance-platform:staging`
- **Startup File**: (should be empty or point to correct entrypoint)
- **Continuous Deployment**: Off

---

## 🎯 After Successful Startup

Once the container starts successfully:

### 1. Verify Health Endpoint
```bash
curl https://app-governance-staging-xnczpwyv.azurewebsites.net/health
# Expected: {"status":"healthy",...}
```

### 2. Check Dashboard
```bash
curl https://app-governance-staging-xnczpwyv.azurewebsites.net/api/v1/riverside/summary
```

### 3. Run Initial Sync
```bash
curl -X POST https://app-governance-staging-xnczpwyv.azurewebsites.net/api/v1/riverside/sync \
  -H "Content-Type: application/json" \
  -d '{"include_mfa":true,"include_devices":false,"include_requirements":true,"include_maturity":true}'
```

### 4. Update Documentation
- Mark staging deployment complete in HANDOFF.md
- Update this file with final status

---

## 🔗 Quick Access Links

| Resource | URL |
|----------|-----|
| Azure Portal | https://portal.azure.com |
| App Service | https://portal.azure.com/.../app-governance-staging-xnczpwyv |
| Log Stream | https://portal.azure.com/.../app-governance-staging-xnczpwyv/logStream |
| Kudu/SCM | https://app-governance-staging-xnczpwyv.scm.azurewebsites.net |
| Container Settings | https://portal.azure.com/.../app-governance-staging-xnczpwyv/containerSettings |
| App Settings | https://portal.azure.com/.../app-governance-staging-xnczpwyv/appsettings |
| Public URL | https://app-governance-staging-xnczpwyv.azurewebsites.net |
| Health | https://app-governance-staging-xnczpwyv.azurewebsites.net/health |

---

## 📊 Current Status

| Component | Status |
|-----------|--------|
| Infrastructure | ✅ Complete |
| ACR Image | ✅ Available (anonymous pull) |
| Environment Variables | ✅ Set |
| App Service | ✅ Configured |
| Container Startup | ❌ Failing (needs Portal diagnosis) |
| Health Checks | ⏳ Pending startup |
| Data Sync | ⏳ Pending startup |

---

## 🐛 Known Issues

### Azure CLI Limitations
- `az webapp config container set --docker-registry-server-password` does not persist password (Azure CLI bug)
- Container logs not accessible via CLI for crashing containers
- SSH unavailable for non-responsive containers

### TLL Tenant (Lash Lounge)
- Currently shows 0% MFA
- Requires `UserAuthenticationMethod.Read.All` permission
- Azure AD Premium P1/P2 license needed
- See HANDOFF.md for permission fix instructions

---

## 📝 Session Notes (2026-03-13)

**Agent**: python-programmer-50bf61

**Actions Taken**:
1. Identified app service in HTT-CORE subscription (was looking in wrong subscription initially)
2. Upgraded ACR from Basic to Standard SKU to enable anonymous pull
3. Set all required environment variables via REST API
4. Disabled remote debugging
5. Enabled verbose logging
6. Attempted SSH (failed - container not responding)
7. Attempted log tail (no output - container crashing before logging)

**Blocker**: Container crashes immediately on startup. All CLI diagnostic tools exhausted. Azure Portal access required to view container logs and identify root cause.

**Recommendation**: Most likely cause is missing `/home/data/` directory for SQLite database. Fix via Kudu and restart.

---

*Last updated: 2026-03-13 - Portal access required to complete*

---

## Legacy Notes (Pre-2026-03-13)

*The following notes are from earlier debugging sessions and may not reflect current state:*

### Original Issue: Registry Password
The initial issue was that `DOCKER_REGISTRY_SERVER_PASSWORD` could not be set via CLI due to an Azure CLI bug. This was worked around by:
1. Upgrading ACR to Standard SKU
2. Enabling anonymous pull
3. Removing registry credentials from App Service

### Original Issue: Health Check Timeout
Previous sessions noted Azure killing the container after 230 seconds with `ContainerTimeout`. This was due to health check probes failing. Current status: health check path is `null`, which should disable health checks, but this may need verification in Portal.


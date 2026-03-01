# Dev Environment Recovery Runbook

> **Version:** 1.0  
> **Last Updated:** February 2025  
> **Audience:** DevOps Engineers, Developers

---

## Issue: App Service Returning 503 Errors

### Symptoms
- All endpoints return "Application Error" (503)
- Health checks failing
- Runtime configured for PYTHON instead of DOCKER

### Root Cause
App Service runtime mismatch between container deployment and native Python runtime.

---

## Recovery Steps

### Step 1: Verify Current State

```bash
az webapp config show \
  --name app-governance-dev-001 \
  --resource-group rg-governance-dev \
  --query '{linuxFxVersion: linuxFxVersion, kind: kind}'
```

Expected broken output:
```json
{
  "linuxFxVersion": "PYTHON|3.11",
  "kind": null
}
```

Expected fixed output:
```json
{
  "linuxFxVersion": "DOCKER|ghcr.io/tygranlund/azure-governance-platform:dev",
  "kind": "app,linux,container"
}
```

---

### Step 2: Apply Fix

#### Option A: Use Fix Script (Recommended)

```bash
./scripts/fix-dev-runtime.sh
```

This script will:
1. Check current configuration
2. Configure for container deployment
3. Set the correct container image
4. Enable Always On
5. Configure health check path
6. Restart the App Service
7. Verify the fix

#### Option B: Manual Fix

If the script doesn't work, apply fixes manually:

```bash
# 1. Set container runtime
az webapp config set \
  --name app-governance-dev-001 \
  --resource-group rg-governance-dev \
  --linux-fx-version "DOCKER|ghcr.io/$(gh repo view --json owner -q .owner.login)/$(gh repo view --json name -q .name):dev"

# 2. Configure container settings
az webapp config container set \
  --name app-governance-dev-001 \
  --resource-group rg-governance-dev \
  --docker-custom-image-name "ghcr.io/$(gh repo view --json owner -q .owner.login)/$(gh repo view --json name -q .name):dev" \
  --docker-registry-server-url "https://ghcr.io"

# 3. Enable Always On (critical for containers)
az webapp config set \
  --name app-governance-dev-001 \
  --resource-group rg-governance-dev \
  --always-on true

# 4. Configure health check
az webapp config set \
  --name app-governance-dev-001 \
  --resource-group rg-governance-dev \
  --health-check-path "/health"

# 5. Restart the App Service
az webapp restart \
  --name app-governance-dev-001 \
  --resource-group rg-governance-dev
```

---

### Step 3: Verify Fix

```bash
# Wait 3-5 minutes for container startup
echo "Waiting for container startup..."
sleep 180

# Test health endpoint
curl -s https://app-governance-dev-001.azurewebsites.net/health | jq .

# Should return: {"status": "healthy", ...}
```

Verification commands:
```bash
# Check configuration
az webapp config show \
  --name app-governance-dev-001 \
  --resource-group rg-governance-dev \
  --query "{linuxFxVersion: linuxFxVersion, alwaysOn: alwaysOn}"

# Check app state
az webapp show \
  --name app-governance-dev-001 \
  --resource-group rg-governance-dev \
  --query "{state: state, availabilityState: availabilityState}"

# Full health check
./scripts/verify-dev-deployment.sh
```

---

### Step 4: If Still Failing

If the App Service is still returning 503 errors after the fix:

#### 4.1 Check Container Logs

```bash
# Stream logs in real-time
az webapp log tail \
  --name app-governance-dev-001 \
  --resource-group rg-governance-dev

# Or use the convenience script
./scripts/check-logs.sh
```

Look for:
- Container startup errors
- Missing environment variables
- Database connection failures
- Port binding issues

#### 4.2 Verify GHCR Image Exists

```bash
# Check if the image exists in GitHub Container Registry
gh api \
  -H "Accept: application/vnd.github+json" \
  /user/packages/container/azure-governance-platform/versions

# Verify the specific tag exists
gh api \
  -H "Accept: application/vnd.github+json" \
  /user/packages/container/azure-governance-platform/versions \
  --jq '.[] | select(.metadata.container.tags[] == "dev")'
```

#### 4.3 Check GitHub Actions Secrets

```bash
# Verify required secrets are set
gh secret list

# Required secrets:
# - AZURE_CLIENT_ID
# - AZURE_CLIENT_SECRET  
# - AZURE_SUBSCRIPTION_ID
# - AZURE_TENANT_ID
# - AZURE_CREDENTIALS (JSON format for older workflows)
```

#### 4.4 Trigger New Deployment

```bash
# Force a new deployment by pushing an empty commit
git commit --allow-empty -m "Trigger deployment after runtime fix"
git push

# Or trigger workflow manually
gh workflow run deploy-dev.yml
```

#### 4.5 Check Resource Quotas

```bash
# Verify resource group quota limits
az group show \
  --name rg-governance-dev \
  --query "{name: name, location: location}"

# Check App Service plan
az appservice plan show \
  --name asp-governance-dev \
  --resource-group rg-governance-dev \
  --query "{sku: sku.name, capacity: sku.capacity}"
```

---

## Verification Checklist

After recovery, verify all functionality:

### Basic Health
- [ ] App Service responds to health check (`/health` returns 200)
- [ ] Health check returns `{"status": "healthy"}`
- [ ] Detailed health check works (`/health/detailed`)

### API Endpoints
- [ ] Status endpoint returns 200 (`/api/v1/status`)
- [ ] Tenants endpoint returns data (`/api/v1/tenants`)
- [ ] Dashboard loads without errors
- [ ] Static assets serve correctly

### Database
- [ ] Database connections working
- [ ] Migrations applied (if any pending)
- [ ] Can read/write test data

### Background Jobs
- [ ] Scheduler is running
- [ ] Sync jobs can be triggered
- [ ] Job status endpoint works

### External Integrations
- [ ] Azure AD authentication working (if configured)
- [ ] GitHub API access working
- [ ] Cost Management API responding (if configured)

---

## Prevention

To prevent this issue from recurring:

1. **Infrastructure as Code**: Always use Bicep/Terraform for infrastructure changes
2. **Immutable Infrastructure**: Never manually change App Service settings via Portal
3. **Pre-deployment Checks**: Add runtime validation to deployment pipeline
4. **Monitoring**: Set up alerts for configuration drift

---

## Quick Reference Commands

```bash
# Check current state
az webapp config show --name app-governance-dev-001 --resource-group rg-governance-dev

# Fix runtime
./scripts/fix-dev-runtime.sh

# Check logs
./scripts/check-logs.sh

# Monitor health
./scripts/monitor-dev.sh

# Full dashboard
./scripts/health-dashboard.sh

# Verify deployment
./scripts/verify-dev-deployment.sh
```

---

## Related Documents

- [RUNBOOK.md](./RUNBOOK.md) - General operations runbook
- [DEPLOYMENT.md](./DEPLOYMENT.md) - Deployment procedures
- [DEV_DEPLOYMENT_STATUS.md](./DEV_DEPLOYMENT_STATUS.md) - Current dev status
- [COMMON_PITFALLS.md](./COMMON_PITFALLS.md) - Common issues and solutions

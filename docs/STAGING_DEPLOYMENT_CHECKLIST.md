# Staging Deployment Checklist

> **Version:** 1.0  
> **Last Updated:** February 2025  
> **Environment:** Staging (Pre-Production)

---

## Overview

This checklist guides the deployment process to the staging environment, ensuring all steps are completed systematically and nothing is missed.

---

## Pre-Deployment Checklist

### Infrastructure Verification

- [ ] Resource Group `rg-governance-staging` exists
- [ ] App Service `app-governance-staging-001` deployed and running
- [ ] Key Vault `kv-gov-staging-*` created (if enabled)
- [ ] Application Insights `ai-governance-staging-*` configured (if enabled)
- [ ] SQL Server and Database deployed (if using Azure SQL)
- [ ] Storage Account created for logs/backups

Verify with:
```bash
az group show --name rg-governance-staging
az webapp show --name app-governance-staging-001 --resource-group rg-governance-staging
```

### GitHub Configuration

- [ ] GitHub Environment "staging" created
- [ ] Required reviewers configured (recommended: 1)
- [ ] Deployment branch protection set
- [ ] Environment secrets configured:
  - [ ] `AZURE_CLIENT_ID_STAGING` (or reuse `AZURE_CLIENT_ID`)
  - [ ] `AZURE_CLIENT_SECRET_STAGING` (or reuse `AZURE_CLIENT_SECRET`)
  - [ ] `AZURE_SUBSCRIPTION_ID`
  - [ ] `AZURE_TENANT_ID`

Verify with:
```bash
gh api repos/$(gh repo view --json nameWithOwner -q .nameWithOwner)/environments/staging
```

### Code Preparation

- [ ] All tests passing on `main` branch
- [ ] Code review completed for changes
- [ ] Version bumped (if using semantic versioning)
- [ ] CHANGELOG.md updated
- [ ] Database migrations prepared (if any)
- [ ] Docker image builds successfully locally

Verify with:
```bash
# Run tests
pytest tests/ -v

# Build Docker image
docker build -t azure-governance-platform:staging .

# Test locally
docker run -p 8000:8000 azure-governance-platform:staging
```

### Configuration Review

- [ ] `infrastructure/parameters.staging.json` reviewed
- [ ] Container image tag set to `staging`
- [ ] Resource SKU appropriate for staging (B2 recommended)
- [ ] Azure SQL enabled (recommended for staging parity with prod)
- [ ] Log retention set appropriately (14 days for staging)

---

## Deployment Steps

### Step 1: Pre-Deployment Backup

```bash
# If staging is already deployed, backup current state
curl -s https://app-governance-staging-001.azurewebsites.net/health > /tmp/staging-pre-deploy-health.json

echo "Pre-deployment state saved to /tmp/staging-pre-deploy-health.json"
```

### Step 2: Trigger Deployment

```bash
# Option A: Trigger via GitHub CLI
gh workflow run deploy-staging.yml

# Option B: Trigger via GitHub UI
# Visit: https://github.com/<owner>/<repo>/actions/workflows/deploy-staging.yml

# Option C: Manual deployment
az webapp config container set \
  --name app-governance-staging-001 \
  --resource-group rg-governance-staging \
  --docker-custom-image-name "ghcr.io/$(gh repo view --json owner -q .owner.login)/$(gh repo view --json name -q .name):staging"
```

### Step 3: Monitor Deployment

```bash
# Watch deployment progress
gh run watch

# Or check status
gh run list --workflow=deploy-staging.yml --limit 5
```

### Step 4: Verify Container Startup

```bash
# Stream logs during startup
az webapp log tail \
  --name app-governance-staging-001 \
  --resource-group rg-governance-staging

# Look for:
# - "Container started"
# - "Application startup complete"
# - No error messages
```

---

## Post-Deployment Verification

### Basic Health Checks

- [ ] Health endpoint returns 200

```bash
curl -s https://app-governance-staging-001.azurewebsites.net/health | jq .
# Expected: {"status": "healthy", ...}
```

- [ ] Detailed health check works

```bash
curl -s https://app-governance-staging-001.azurewebsites.net/health/detailed | jq .
# Expected: All components show "healthy"
```

- [ ] Status endpoint returns correct version

```bash
curl -s https://app-governance-staging-001.azurewebsites.net/api/v1/status | jq .
```

### API Functionality

- [ ] Tenants endpoint accessible

```bash
curl -s https://app-governance-staging-001.azurewebsites.net/api/v1/tenants | jq '. | length'
```

- [ ] Sync status endpoint works

```bash
curl -s https://app-governance-staging-001.azurewebsites.net/api/v1/sync/status | jq .
```

- [ ] Dashboard loads without errors

Open in browser: `https://app-governance-staging-001.azurewebsites.net/`

### Database Verification

- [ ] Database connections working

```bash
curl -s https://app-governance-staging-001.azurewebsites.net/health/detailed | jq '.components.database'
```

- [ ] Migrations applied (check logs)

```bash
az webapp log tail --name app-governance-staging-001 --resource-group rg-governance-staging | grep -i migration
```

### Configuration Verification

- [ ] Environment variables set correctly

```bash
az webapp config appsettings list \
  --name app-governance-staging-001 \
  --resource-group rg-governance-staging \
  --query "[?name=='ENVIRONMENT'].value" -o tsv
# Expected: staging
```

- [ ] Container image correct

```bash
az webapp config container show \
  --name app-governance-staging-001 \
  --resource-group rg-governance-staging \
  --query "[?name=='DOCKER_CUSTOM_IMAGE_NAME'].value" -o tsv
```

### Performance Verification

- [ ] Response time acceptable (< 2 seconds for health check)

```bash
time curl -s https://app-governance-staging-001.azurewebsites.net/health > /dev/null
```

- [ ] No memory/CPU alerts in Application Insights

Check: Azure Portal → Application Insights → Live Metrics

---

## Rollback Procedures

### Quick Rollback (Container Image)

If the new deployment has issues, roll back to previous image:

```bash
# Get previous image tag
az webapp config container show \
  --name app-governance-staging-001 \
  --resource-group rg-governance-staging

# Deploy previous version
az webapp config container set \
  --name app-governance-staging-001 \
  --resource-group rg-governance-staging \
  --docker-custom-image-name "ghcr.io/<owner>/<repo>:<previous-tag>"

# Restart
az webapp restart --name app-governance-staging-001 --resource-group rg-governance-staging
```

### Full Infrastructure Rollback

If infrastructure changes caused issues:

```bash
# List recent deployments
az deployment group list \
  --resource-group rg-governance-staging \
  --query "[?provisioningState=='Succeeded'].{name:name, timestamp:timestamp}" \
  --output table

# Rollback to specific deployment
az deployment group create \
  --resource-group rg-governance-staging \
  --name rollback-$(date +%Y%m%d) \
  --rollback-on-error <previous-deployment-name>
```

### Database Rollback

If database migrations need to be reverted:

```bash
# Restore from backup (if available)
# This requires manual intervention and backup strategy

# Or revert migrations (if using Alembic)
# Requires database access
```

---

## Troubleshooting

### Deployment Fails

1. Check GitHub Actions logs:
   ```bash
   gh run view <run-id> --log
   ```

2. Verify Azure credentials:
   ```bash
   az ad sp show --id $AZURE_CLIENT_ID
   ```

3. Check resource quotas:
   ```bash
   az vm list-usage --location eastus --output table
   ```

### Container Won't Start

1. Check container logs:
   ```bash
   ./scripts/check-logs.sh --container
   ```

2. Verify image exists:
   ```bash
   gh api /user/packages/container/azure-governance-platform/versions
   ```

3. Check environment variables:
   ```bash
   az webapp config appsettings list \
     --name app-governance-staging-001 \
     --resource-group rg-governance-staging
   ```

### Database Connection Issues

1. Verify firewall rules:
   ```bash
   az sql server firewall-rule list \
     --server sql-governance-staging-* \
     --resource-group rg-governance-staging
   ```

2. Check connection string:
   ```bash
   az webapp config connection-string list \
     --name app-governance-staging-001 \
     --resource-group rg-governance-staging
   ```

---

## Sign-Off

After successful deployment:

- [ ] All health checks passing
- [ ] API endpoints responding correctly
- [ ] Dashboard accessible and functional
- [ ] Performance metrics acceptable
- [ ] No errors in logs
- [ ] Database migrations successful
- [ ] Ready for QA testing

**Deployed By:** _________________  
**Date:** _________________  
**Version:** _________________  

---

## Related Documents

- [DEV_RECOVERY_RUNBOOK.md](./DEV_RECOVERY_RUNBOOK.md) - Dev environment recovery
- [DEPLOYMENT.md](./DEPLOYMENT.md) - General deployment guide
- [RUNBOOK.md](./RUNBOOK.md) - Operations runbook
- [setup-staging.sh](../scripts/setup-staging.sh) - Staging setup script

# Azure Governance Platform - Infrastructure

This directory contains Infrastructure as Code (IaC) templates for deploying the Azure Governance Platform on Azure.

## 📁 Structure

```
infrastructure/
├── main.bicep                      # Main deployment template
├── deploy.sh                       # Deployment script
├── setup-oidc.sh                   # OIDC federation setup script 🔐
├── github-oidc.bicep              # OIDC federation Bicep template
├── parameters.json                 # Production parameters
├── parameters.dev.json             # Development parameters
├── parameters.staging.json        # Staging parameters
├── README.md                       # This file
└── modules/                        # Reusable Bicep modules
    ├── app-insights.bicep         # Application Insights
    ├── app-service-plan.bicep     # App Service Plan
    ├── app-service.bicep          # App Service
    ├── key-vault.bicep            # Key Vault
    ├── log-analytics.bicep        # Log Analytics Workspace
    ├── sql-server.bicep           # Azure SQL
    ├── storage.bicep              # Storage Account
    └── vnet.bicep                 # Virtual Network
```

## 🔐 OIDC Federation (Recommended)

For secure, secret-free deployments from GitHub Actions, set up OIDC federation:

```bash
# Run the OIDC setup script (one-time setup)
./setup-oidc.sh -e dev -g rg-governance-dev

# Or use Bicep for IaC-based setup
az deployment sub create \
  --name github-oidc-setup \
  --location eastus \
  --template-file github-oidc.bicep \
  --parameters environment=dev githubRepo=htt-brands/control-tower resourceGroupName=rg-governance-dev
```

This enables **passwordless authentication** between GitHub Actions and Azure AD.

📖 **Full documentation:** [docs/OIDC_SETUP.md](../docs/OIDC_SETUP.md)

## 🌍 Current Deployments

### Dev Environment (westus2)
| Resource | Name | Status |
|----------|------|--------|
| Resource Group | `rg-governance-dev` | 🟢 Active |
| App Service Plan | `asp-governance-dev-001` (B1 Linux) | 🟢 Running |
| App Service | `app-governance-dev-001` | 🟢 Healthy |
| Container Registry | `acrgovernancedev` (Basic) | 🟢 Available |
| Key Vault | `kv-gov-dev-001` | 🟢 2 secrets |
| Storage Account | `stgovdev001` | 🟢 Azure Files |
| App Insights | `ai-governance-dev-001` | 🟢 Connected |
| Log Analytics | `log-governance-dev-001` | 🟢 Connected |

**Live URL:** https://app-governance-dev-001.azurewebsites.net

### Deploying a New Container Image
```bash
# Build image in ACR (from project root)
az acr build --registry acrgovernancedev --image control-tower:dev .

# Restart to pick up new image
az webapp restart --name app-governance-dev-001 -g rg-governance-dev

# Verify
curl -sf https://app-governance-dev-001.azurewebsites.net/health
```

### Staging & Production
Not yet deployed. Use `parameters.staging.json` and `parameters.json` respectively.

## 🚀 Quick Start

### Prerequisites

- Azure CLI (2.50+)
- Bash shell (macOS, Linux, or WSL)
- Azure subscription with Contributor access

### Deploy

```bash
# Deploy to production
./deploy.sh production

# Deploy to staging
./deploy.sh staging

# Deploy to development
./deploy.sh development

# Deploy to specific region (dev is westus2)
./deploy.sh development westus2
```

## 📦 Resources Deployed

| Resource | Purpose | Cost (approx) |
|----------|---------|---------------|
| Resource Group | Resource organization | Free |
| App Service Plan | Compute (B1) | ~$13/month |
| App Service | Web hosting | Included |
| Storage Account | Data persistence | ~$5/month |
| Application Insights | Monitoring | ~$5-10/month |
| Log Analytics | Log aggregation | Included |
| Key Vault | Secrets management | ~$1/month |
| Azure SQL (optional) | Database | ~$15/month |

## 🔧 Configuration

### Parameters Files

- `parameters.json` - Default/fallback settings
- `parameters.production.json` - Production settings (authoritative for prod)
- `parameters.staging.json` - Staging settings
- `parameters.dev.json` - Development settings

### Known Bicep-vs-reality drift (see bd-mrgy)

As of 2026-04-17 the following drift exists between parameter files and the
live Azure state. This is **intentional** and documented here so nobody flips
a flag thinking "this will match reality" and accidentally spawns duplicate
resources.

| Param | `dev` | `staging` | `production` | Live state | Notes |
|---|---|---|---|---|---|
| `enableAzureSql` | false | false | **true** | SQL deployed everywhere | Dev/staging SQL was created out-of-band. Bicep is incremental, so `false` won't delete existing SQL, but flipping to `true` would try to create a **second** SQL server. Keep as-is until we decide to import. |
| `enableRedis` | false | false | false | Redis NOT deployed | Was `true` in prod/staging historically (bd-sf24 booby trap, fixed 2026-04-17). Keep `false` until scaled to 2+ instances or cache-miss >20% (`docs/COST_MODEL_AND_SCALING.md` section 6.2 trigger #7). |
| `containerImage` | `htt-brands/*:dev` | `htt-brands/*:staging` | `htt-brands/*:latest` | Matches | Standardized on `htt-brands/*` 2026-04-17 (bd-265y). Historical `tygranlund/*` refs scrubbed from active code paths. |

**Before `az deployment group create` on any env**, always run with
`--what-if` first and scrutinize the output for unexpected create/delete
operations. Bicep is NOT a full source of truth for dev/staging — some
resources are manually managed.

Related references:
- `docs/COST_MODEL_AND_SCALING.md` — authoritative cost/scaling
- `docs/operations/spn-role-matrix.md` — authoritative RBAC
- bd-sf24 (Redis booby trap, closed), bd-265y (GHCR path drift, closed),
  bd-mrgy (this drift documented, closed)

### Customizing Deployment

Edit the parameters file before deployment:

```json
{
  "appServiceSku": {
    "value": "B1"  // Options: B1, B2, B3, S1, S2, S3
  },
  "enableAzureSql": {
    "value": false  // Set to true for Azure SQL
  },
  "location": {
    "value": "eastus"
  }
}
```

## 🔐 Security

### 🔑 OIDC Federation (GitHub Actions)

**Recommended:** Use OIDC federation for secure deployments without storing secrets:
- No Azure credentials in GitHub
- Short-lived tokens (auto-expire)
- Branch-based access control
- Environment-based approvals

See [OIDC_SETUP.md](../docs/OIDC_SETUP.md) for setup instructions.

### Key Vault Integration

Secrets are automatically stored in Key Vault:
- Database passwords
- JWT signing keys
- Azure client secrets (legacy only - prefer OIDC!)

### Managed Identity

App Service automatically gets a system-assigned managed identity with access to:
- Key Vault (read secrets)
- Storage Account (read/write)

### HTTPS Only

HTTPS is enforced by default. HTTP requests are automatically redirected.

## 📊 Monitoring

### Application Insights

- Request/response logging
- Dependency tracking
- Exception monitoring
- Performance counters

### Log Analytics

- 30-day log retention (configurable)
- Custom queries for troubleshooting
- Alerting on errors

## 🔄 Updates

### Update Infrastructure

```bash
# Redeploy with new parameters
./deploy.sh production

# Or use Azure CLI directly
az deployment sub create \
  --name "control-tower-prod" \
  --location eastus \
  --template-file main.bicep \
  --parameters parameters.json
```

### What Gets Updated

- Configuration changes (app settings)
- Scaling (App Service Plan SKU)
- Feature toggles (enable/disable services)

### What Doesn't Get Updated

- Application code (use CI/CD)
- Database contents
- Storage contents

## 🗑️ Cleanup

```bash
# Delete all resources
RESOURCE_GROUP="rg-governance-production"
az group delete --name $RESOURCE_GROUP --yes --no-wait

# Delete specific environment
./deploy.sh production && az group delete --name "rg-governance-production" --yes
```

⚠️ **Warning**: This will delete all data in the resource group!

---

## 📦 Resource Lifecycle & Cleanup

### Deprecated vs Current Resources

| Resource | Status | Replacement | Cleanup Script |
|----------|--------|-------------|----------------|
| `acrgovstaging19859` | 🚫 **Deprecated** | GHCR (free) | `scripts/cleanup-old-acr.sh` |
| Per-tenant app registrations (5) | 🚫 **Deprecated** | Multi-tenant app | `scripts/cleanup-phase-a-apps.sh` |
| Per-tenant client secrets | 🚫 **Deprecated** | Single secret or UAMI | `scripts/migrate-to-phase-c.sh` |
| ACR-based deployments | 🚫 **Deprecated** | GHCR-based deployments | `.github/workflows/deploy-staging.yml` |

### Cleanup Runbooks

| Task | Runbook | Risk Level |
|------|---------|------------|
| Delete old ACR | `docs/runbooks/resource-cleanup.md` | Medium |
| Delete Phase A apps | `docs/runbooks/resource-cleanup.md` | Medium |
| Migrate Phase A → B | `docs/runbooks/phase-b-multi-tenant-app.md` | Low |
| Migrate Phase B → C | `docs/runbooks/phase-c-zero-secrets.md` | Low |

### Cost Optimization History

| Optimization | Original | New | Monthly Savings |
|--------------|----------|-----|-----------------|
| ACR → GHCR | Standard (~$5/day) | Free | **~$10** |
| 5 secrets → 1 secret | 5× overhead | 1× overhead | **~$2** |
| **Total Phase A/B Cleanup** | **~$12/mo** | **~$0.50/mo** | **~$11.50** |

**Annual Savings:** ~$138/year

### Safe Cleanup Guidelines

1. **Always preview first** — Run scripts without `--confirm` to see what will be deleted
2. **Verify replacements work** — Ensure GHCR and multi-tenant app are operational
3. **Use confirmation prompts** — Never use `--yes` flag in production without review
4. **Keep backups** — Azure AD soft-delete preserves apps for 30 days
5. **Document changes** — Update `INFRASTRUCTURE_INVENTORY.md` after cleanup

### Rollback Options

If cleanup causes issues:

| Resource | Rollback Method | Time Window |
|----------|-----------------|-------------|
| ACR | Recreate + rebuild images | Immediate |
| App registrations | Soft-delete restore | 30 days |
| Per-tenant secrets | Recreate from scratch | Immediate |
| Configuration | Restore from git backup | Immediate |

---

## 📚 Reference

- [Bicep Documentation](https://docs.microsoft.com/azure/azure-resource-manager/bicep/)
- [Azure App Service](https://docs.microsoft.com/azure/app-service/)
- [Azure Key Vault](https://docs.microsoft.com/azure/key-vault/)

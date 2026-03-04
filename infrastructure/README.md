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
  --parameters environment=dev githubRepo=yourorg/azure-governance-platform resourceGroupName=rg-governance-dev
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
az acr build --registry acrgovernancedev --image governance-platform:dev .

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

- `parameters.json` - Production settings
- `parameters.dev.json` - Development settings
- `parameters.staging.json` - Staging settings

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
  --name "governance-platform-prod" \
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

## 📚 Reference

- [Bicep Documentation](https://docs.microsoft.com/azure/azure-resource-manager/bicep/)
- [Azure App Service](https://docs.microsoft.com/azure/app-service/)
- [Azure Key Vault](https://docs.microsoft.com/azure/key-vault/)

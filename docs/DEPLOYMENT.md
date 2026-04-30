# Azure Governance Platform - Deployment Guide

> **Version:** 2.1  
> **Last Updated:** July 2025  
> **Estimated Setup Time:** 30-60 minutes

---

## Table of Contents

1. [Quick Start](#1-quick-start)
2. [Prerequisites](#2-prerequisites)
3. [Deployment Options](#3-deployment-options)
4. [Azure Infrastructure as Code Deployment](#4-azure-infrastructure-as-code-deployment)
5. [Docker Deployment](#5-docker-deployment)
6. [CI/CD Pipeline Setup](#6-cicd-pipeline-setup)
7. [Configuration](#7-configuration)
8. [Post-Deployment Verification](#8-post-deployment-verification)
9. [Troubleshooting](#9-troubleshooting)
10. [Security Hardening](#10-security-hardening)
11. [Backup and Recovery](#11-backup-and-recovery)
12. [Cost Management](#12-cost-management)

---

## 1. Quick Start

### 🚀 One-Click Deploy to Azure

[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Ftygranlund%2Fazure-governance-platform%2Fmain%2Finfrastructure%2Fmain.json)

Or deploy via CLI:

```bash
# Clone the repository
git clone https://github.com/htt-brands/control-tower.git
cd control-tower

# Run the deployment script
./infrastructure/deploy.sh production eastus
```

### 📋 Prerequisites Checklist

- [ ] Azure subscription with Contributor access
- [ ] Azure CLI installed (`az --version`)
- [ ] Service Principal created for Azure access
- [ ] Git repository with your code

---

## 2. Prerequisites

### 2.1 Azure Prerequisites

Before deploying, ensure you have:

| Requirement | Details | How to Verify |
|-------------|---------|---------------|
| **Azure Subscription** | Active subscription for deployment costs | Azure Portal → Subscriptions |
| **App Registration** | Service Principal with appropriate permissions | Azure Portal → App registrations |
| **RBAC Roles** | Contributor on subscription | Azure Portal → Access control (IAM) |
| **Azure CLI** | Version 2.50+ | `az --version` |
| **Bicep CLI** | Auto-installed with Azure CLI | `az bicep version` |

### 2.2 Create Azure Service Principal

```bash
# Login to Azure
az login

# Create service principal for the platform
az ad sp create-for-rbac \
  --name "azure-governance-platform-sp" \
  --role "Reader" \
  --scopes "/subscriptions/$(az account show --query id -o tsv)" \
  --sdk-auth

# Save the output - you'll need:
# - appId (AZURE_CLIENT_ID)
# - password (AZURE_CLIENT_SECRET)
# - tenant (AZURE_TENANT_ID)
```

### 2.3 Cost Estimates

| Resource | SKU | Monthly Cost |
|----------|-----|--------------|
| **App Service Plan** | B1 | ~$13 |
| **App Service** | - | Included |
| **Storage Account** | Standard GRS | ~$5 |
| **Application Insights** | Pay-as-you-go | ~$5-10 |
| **Key Vault** | Standard | ~$1 |
| **Azure SQL** | S0 (optional) | ~$15 |
| **Total (SQLite)** | | **~$24/month** |
| **Total (Azure SQL)** | | **~$39/month** |

---

## 3. Deployment Options

### Comparison Matrix

| Option | Cost | Complexity | Best For |
|--------|------|------------|----------|
| **Bicep IaC** | ~$24/mo | Low | Production, reproducible |
| **Docker** | Variable | Medium | Custom infrastructure |
| **Azure Portal** | ~$24/mo | Low | One-off deployments |
| **GitHub Actions** | ~$24/mo | Low | Automated CI/CD |

---

## 4. Azure Infrastructure as Code Deployment

### 4.1 Deploy with Bicep (Recommended)

The project includes complete Bicep templates in `infrastructure/`.

```bash
# Navigate to infrastructure folder
cd infrastructure

# Deploy to development
./deploy.sh development

# Deploy to production
./deploy.sh production

# Deploy to specific region
./deploy.sh production westus2
```

### 4.2 Manual Bicep Deployment

```bash
# Login and set subscription
az login
az account set --subscription "Your Subscription Name"

# Deploy infrastructure
az deployment sub create \
  --name "governance-platform-prod" \
  --location eastus \
  --template-file infrastructure/main.bicep \
  --parameters infrastructure/parameters.json \
  --parameters environment="production" \
  --parameters appServiceSku="B1"
```

### 4.3 What Gets Deployed

| Resource | Purpose | SKU |
|----------|---------|-----|
| Resource Group | Resource organization | - |
| App Service Plan | Compute | B1 (~$13/mo) |
| App Service | Web hosting | - |
| Storage Account | Logs, backups, SQLite | Standard GRS |
| Application Insights | Monitoring & telemetry | Pay-as-you-go |
| Log Analytics | Log aggregation | - |
| Key Vault | Secrets management | Standard |
| Azure SQL (optional) | Production database | S0 (~$15/mo) |

### 4.4 Post-Deployment Configuration

After infrastructure deployment:

```bash
# Get deployment outputs
RESOURCE_GROUP="rg-governance-production"
APP_NAME=$(az webapp list --resource-group $RESOURCE_GROUP --query '[0].name' -o tsv)
KEY_VAULT=$(az keyvault list --resource-group $RESOURCE_GROUP --query '[0].name' -o tsv)

# Configure App Service settings
az webapp config appsettings set \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings \
    AZURE_TENANT_ID="your-tenant-id" \
    AZURE_CLIENT_ID="your-client-id" \
    AZURE_CLIENT_SECRET="your-secret" \
    ENVIRONMENT="production" \
    DEBUG="false"

# Store secrets in Key Vault (recommended)
az keyvault secret set \
  --vault-name $KEY_VAULT \
  --name "azure-client-secret" \
  --value "your-secret"
```

---

## 5. Docker Deployment

### 5.1 Local Development with Docker

```bash
# Build development image
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### 5.2 Production Docker Deployment

```bash
# Build production image
docker build -t azure-governance-platform:latest --target production .

# Run with environment file
docker run -d \
  --name governance-platform \
  -p 8000:8000 \
  --env-file .env.production \
  -v app-data:/home/data \
  -v app-logs:/home/logs \
  azure-governance-platform:latest
```

### 5.3 Docker Compose Production

```bash
# Deploy with production config
docker-compose -f docker-compose.prod.yml up -d

# Scale up (if using multiple replicas)
docker-compose -f docker-compose.prod.yml up -d --scale app=3
```

---

## 6. CI/CD Pipeline Setup

### 6.1 GitHub Actions Configuration

The repository includes a complete CI/CD pipeline in `.github/workflows/deploy.yml`.

#### Required Secrets

Configure these in your GitHub repository (Settings → Secrets):

| Secret | Description | How to Get |
|--------|-------------|------------|
| `AZURE_CREDENTIALS` | Service Principal JSON | `az ad sp create-for-rbac --sdk-auth` |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID | `az account show --query id -o tsv` |
| `AZURE_RESOURCE_GROUP` | Resource group name | From deployment |
| `AZURE_APP_SERVICE_NAME` | App Service name | From deployment |
| `AZURE_TENANT_ID` | Azure AD tenant ID | From SP creation |
| `AZURE_CLIENT_ID` | Service Principal ID | From SP creation |
| `AZURE_CLIENT_SECRET` | Service Principal secret | From SP creation |

### 6.2 Pipeline Features

The CI/CD pipeline includes:

- ✅ **Lint & Test**: Ruff, MyPy, pytest with coverage
- ✅ **Security Scanning**: Trivy vulnerability scanning
- ✅ **Docker Build**: Multi-stage builds with caching
- ✅ **SBOM Generation**: Software Bill of Materials
- ✅ **Staging Deployment**: Auto-deploy to staging on main branch
- ✅ **Production Deployment**: Deploy to prod on version tags
- ✅ **Smoke Tests**: Automated health checks
- ✅ **Automatic Rollback**: On production deployment failure

### 6.3 Deploy Staging

```bash
# Push to main branch triggers staging deployment
git push origin main
```

### 6.4 Deploy Production

```bash
# Create and push a version tag
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

---

## 7. Configuration

### 7.1 Environment Variables

Copy `.env.production` to `.env` and configure:

```bash
# Required Azure credentials
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-secret

# Database (SQLite for MVP, Azure SQL for production)
DATABASE_URL=sqlite:///home/data/governance.db

# Security
CORS_ORIGINS=https://your-domain.com
JWT_SECRET_KEY=generate-a-secure-key

# Monitoring
APPLICATIONINSIGHTS_CONNECTION_STRING=your-connection-string
```

### 7.2 Generate JWT Secret

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 7.3 Azure Key Vault Integration

Store sensitive values in Key Vault:

```bash
# Add secrets
az keyvault secret set --vault-name $KEY_VAULT --name "jwt-secret" --value "your-secret"
az keyvault secret set --vault-name $KEY_VAULT --name "azure-client-secret" --value "your-secret"

# Enable managed identity
az webapp identity assign --name $APP_NAME --resource-group $RESOURCE_GROUP

# Grant Key Vault access
az keyvault set-policy \
  --name $KEY_VAULT \
  --object-id $PRINCIPAL_ID \
  --secret-permissions get list
```

---

## 8. Post-Deployment Verification

### 8.1 Health Checks

```bash
# Get app URL
APP_URL=$(az webapp show --name $APP_NAME --resource-group $RESOURCE_GROUP --query defaultHostName -o tsv)

# Basic health
curl https://$APP_URL/health
# Expected: {"status": "healthy", "version": "0.1.0"}

# Detailed health
curl https://$APP_URL/health/detailed

# System status
curl https://$APP_URL/api/v1/status
```

### 8.2 Verification Checklist

- [ ] Application responds to health checks
- [ ] Database is accessible (or SQLite directory created)
- [ ] Scheduler is running
- [ ] Azure credentials are valid (`azure_configured: true`)
- [ ] Application Insights receiving telemetry
- [ ] HTTPS enforced (redirects HTTP to HTTPS)

### 8.3 View Logs

```bash
# Stream logs
az webapp log tail --name $APP_NAME --resource-group $RESOURCE_GROUP

# View recent logs
az webapp log deployment show --name $APP_NAME --resource-group $RESOURCE_GROUP
```

---

---

## Known Deployment Issues & Workarounds

These are real issues encountered during the dev deployment (July 2025):

### DATABASE_URL must use 4 slashes for absolute SQLite paths
```
# ❌ Wrong (relative path — crashes in container)
DATABASE_URL=sqlite:///data/governance.db

# ✅ Correct (absolute path)
DATABASE_URL=sqlite:////home/site/data/governance.db
```

### ENVIRONMENT must be a valid Pydantic value
The `Settings` model validates the `ENVIRONMENT` field. Use one of: `development`, `staging`, `production` — NOT `dev` or `prod`.

### Trivy scan may block CI/CD pipeline
The container security scan can fail on upstream CVEs you can't fix. Use `continue-on-error: true` in the GitHub Actions step.

### ACR credential warnings on container set
If you see "couldn't auto-discover credentials" when configuring the App Service container, ensure the managed identity has the `AcrPull` role on the ACR:
```bash
ACR_ID=$(az acr show --name acrgovernancedev --query id -o tsv)
IDENTITY=$(az webapp identity show --name app-governance-dev-001 -g rg-governance-dev --query principalId -o tsv)
az role assignment create --assignee $IDENTITY --role AcrPull --scope $ACR_ID
```

### Bash 3.2 compatibility (macOS)
Scripts must work with macOS default bash 3.2. Avoid:
- `declare -A` (associative arrays)
- `readarray` / `mapfile`
- `${var,,}` (lowercase expansion)

---

## 9. Troubleshooting

### 9.1 Common Issues

#### Issue: Application won't start

```bash
# Check logs
az webapp log tail --name $APP_NAME --resource-group $RESOURCE_GROUP

# Verify Python version
az webapp config show --name $APP_NAME --resource-group $RESOURCE_GROUP --query linuxFxVersion

# Restart app
az webapp restart --name $APP_NAME --resource-group $RESOURCE_GROUP
```

#### Issue: Database errors

```bash
# Check if data directory exists and is writable
az webapp ssh --name $APP_NAME --resource-group $RESOURCE_GROUP
ls -la /home/data/

# Create directory if missing
mkdir -p /home/data
```

#### Issue: Azure credentials not working

```bash
# Verify credentials
az login --service-principal \
  --username $AZURE_CLIENT_ID \
  --password $AZURE_CLIENT_SECRET \
  --tenant $AZURE_TENANT_ID

# Check permissions
az role assignment list --assignee $AZURE_CLIENT_ID
```

### 9.2 Getting Help

- **Azure Portal**: Check Resource Health blade
- **Application Insights**: View failures and performance
- **Logs**: Use Log Analytics for advanced queries

---

## 10. Security Hardening

### 10.1 Enable HTTPS Only

```bash
az webapp update \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --https-only true
```

### 10.2 Configure CORS

```bash
az webapp cors add \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --allowed-origins "https://your-domain.com"
```

### 10.3 Enable Managed Identity

```bash
az webapp identity assign \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP
```

### 10.4 IP Restrictions

```bash
# Allow only specific IPs
az webapp config access-restriction add \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --rule-name "Office" \
  --action Allow \
  --ip-address "203.0.113.0/24"
```

---

## 11. Backup and Recovery

### 11.1 Automated Backups

Azure App Service backups are configured automatically:

```bash
# Enable automated backups
az webapp config backup create \
  --resource-group $RESOURCE_GROUP \
  --webapp-name $APP_NAME \
  --backup-name daily-backup \
  --storage-account-url "https://$STORAGE_ACCOUNT.blob.core.windows.net/backups" \
  --frequency 1d
```

### 11.2 Manual Backup

```bash
# Create manual backup
az webapp config backup create \
  --resource-group $RESOURCE_GROUP \
  --webapp-name $APP_NAME \
  --backup-name manual-$(date +%Y%m%d)
```

### 11.3 Database Backups

For SQLite (stored in Azure Files):

```bash
# Create snapshot
az storage share snapshot \
  --name appdata \
  --account-name $STORAGE_ACCOUNT
```

---

## 12. Cost Management

### 12.1 Cost Optimization Tips

1. **Use B1 SKU for development**: ~$13/month
2. **Enable auto-shutdown**: For dev environments
3. **Use SQLite for MVP**: Avoid SQL costs until needed
4. **Monitor Application Insights**: Keep data retention minimal

### 12.2 Cost Alerts

```bash
# Create budget alert
az monitor budgets create \
  --resource-group $RESOURCE_GROUP \
  --amount 50 \
  --time-grain Monthly \
  --start-date $(date +%Y-%m-01) \
  --end-date $(date -d "+1 year" +%Y-%m-01)
```

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 2.1 | July 2025 | Real-world deployment fixes, known issues section, org URL updates |
| 2.0 | February 2025 | Complete rewrite with Bicep IaC, CI/CD, Docker |
| 1.0 | February 2025 | Initial deployment guide |

---

**Related Documents:**
- [Architecture Overview](../ARCHITECTURE.md)
- [API Documentation](./API.md)
- [Development Guide](./DEVELOPMENT.md)
- [Security Implementation](../SECURITY_IMPLEMENTATION.md)

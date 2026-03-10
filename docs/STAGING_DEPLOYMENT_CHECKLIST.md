# Staging Deployment Checklist

**Status:** Documented — requires ops execution
**Last Updated:** March 9, 2026

## Prerequisites

- [ ] Azure CLI 2.50+ installed and authenticated
- [ ] Azure subscription with Contributor role
- [ ] Resource group `rg-governance-staging` created
- [ ] Key Vault `kv-governance-staging` provisioned

## Step 1: Deploy Infrastructure (Bicep)

```bash
# Login to Azure
az login

# Set subscription
az account set --subscription YOUR_SUBSCRIPTION_ID

# Create resource group (if not exists)
az group create \
  --name rg-governance-staging \
  --location eastus2

# Deploy Bicep template
az deployment group create \
  --resource-group rg-governance-staging \
  --template-file infrastructure/main.bicep \
  --parameters infrastructure/parameters.staging.json \
  --name staging-deploy-$(date +%Y%m%d)
```

## Step 2: Configure Container Registry

```bash
# Create ACR (if not exists)
az acr create \
  --resource-group rg-governance-staging \
  --name acrgovernancestaging \
  --sku Basic

# Build and push container image
az acr build \
  --registry acrgovernancestaging \
  --image governance-platform:latest \
  --file Dockerfile .
```

## Step 3: Configure App Service

```bash
# Create App Service Plan
az appservice plan create \
  --name asp-governance-staging \
  --resource-group rg-governance-staging \
  --sku B1 \
  --is-linux

# Create Web App
az webapp create \
  --name governance-staging \
  --resource-group rg-governance-staging \
  --plan asp-governance-staging \
  --deployment-container-image-name acrgovernancestaging.azurecr.io/governance-platform:latest
```

## Step 4: Configure Environment Variables

```bash
az webapp config appsettings set \
  --name governance-staging \
  --resource-group rg-governance-staging \
  --settings \
    ENVIRONMENT=staging \
    DEBUG=false \
    DATABASE_URL="postgresql://..." \
    REDIS_URL="redis://..." \
    KEY_VAULT_URL="https://kv-governance-staging.vault.azure.net/" \
    CORS_ORIGINS="https://governance-staging.yourdomain.com" \
    JWT_SECRET_KEY="@Microsoft.KeyVault(SecretUri=...)"
```

## Step 5: Run Database Migrations

```bash
# SSH into container and run migrations
az webapp ssh --name governance-staging --resource-group rg-governance-staging
# Inside container:
alembic upgrade head
```

## Step 6: Verify Deployment

```bash
# Check health endpoint
curl https://governance-staging.yourdomain.com/health

# Run smoke tests
uv run python scripts/smoke_test.py --url https://governance-staging.yourdomain.com
```

## Step 7: Configure Custom Domain & SSL

```bash
az webapp config hostname add \
  --webapp-name governance-staging \
  --resource-group rg-governance-staging \
  --hostname governance-staging.yourdomain.com

az webapp config ssl bind \
  --name governance-staging \
  --resource-group rg-governance-staging \
  --certificate-thumbprint YOUR_CERT_THUMBPRINT \
  --ssl-type SNI
```

---

*This checklist documents the staging deployment procedure. Execute these steps with appropriate Azure credentials and subscription access.*

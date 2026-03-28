# Azure Infrastructure Inventory

**Generated:** 2026-03-27  
**Subscription:** HTT-BRANDS (32a28177-6fb2-4668-a528-6d6cafb9665e)  
**Status:** All resources operational

---

## Production Environment (rg-governance-production)

**Location:** East US  
**Resource Group:** rg-governance-production

### App Service

| Resource | Name | SKU | Status | Runtime |
|----------|------|-----|--------|---------|
| App Service Plan | asp-governance-production | B1 (Basic) | Active | - |
| Web App | app-governance-prod | - | Running | Docker v1.8.0 |

**Endpoints:**
- URL: https://app-governance-prod.azurewebsites.net
- HTTPS Only: Enabled
- Linux Fx: Docker|acrgovprod.azurecr.io/azure-governance-platform:v1.8.0

### SQL Database

| Resource | Name | Edition | Status | Max Size |
|----------|------|---------|--------|----------|
| Server | sql-gov-prod-mylxq53d | Standard | Ready | - |
| Database | governance | Standard | Online | 250 GB |

### Container Registry

| Resource | Name | SKU | Login Server |
|----------|------|-----|--------------|
| ACR | acrgovprod | Standard | acrgovprod.azurecr.io |

**Admin User:** Enabled  
**Current Image:** azure-governance-platform:v1.8.0

### Key Vault

| Resource | Name | SKU | Soft Delete |
|----------|------|-----|-------------|
| Key Vault | kv-gov-prod | Standard | Enabled |

---

## Staging Environment (rg-governance-staging)

**Location:** West US 2  
**Resource Group:** rg-governance-staging

### App Service

| Resource | Name | SKU | Status |
|----------|------|-----|--------|
| App Service Plan | asp-governance-staging-xnczpwyvwsaba | B1 (Basic) | Active |
| Web App | app-governance-staging-xnczpwyv | - | Running |

**Endpoints:**
- URL: https://app-governance-staging-xnczpwyv.azurewebsites.net

### SQL Database

| Resource | Name | Edition | Status |
|----------|------|---------|--------|
| Server | sql-governance-staging-77zfjyem | Standard | Ready |
| Database | governance | Standard | Online |

### Supporting Resources

| Resource | Name | SKU | Notes |
|----------|------|-----|-------|
| Key Vault | kv-gov-staging-xnczpwyv | Standard | - |
| Storage Account | stgovstagingxnczpwyv | Standard_GRS | StorageV2 |
| Log Analytics | log-governance-staging-xnczpwyvwsaba | PerGB2018 | 30 day retention |
| App Insights | ai-governance-staging-xnczpwyvwsaba | - | Web type |

---

## Monthly Cost Estimation

### Production Costs

| Service | SKU | Estimated Monthly |
|---------|-----|-------------------|
| App Service Plan | B1 | ~$13.14 |
| SQL Database | S0 | ~$15.00 |
| Container Registry | Standard | ~$5.00 |
| Key Vault | Standard | ~$0.03 |
| Storage/Bandwidth | - | ~$2.00 |
| **Production Subtotal** | | **~$35.17** |

### Staging Costs

| Service | SKU | Estimated Monthly |
|---------|-----|-------------------|
| App Service Plan | B1 | ~$13.14 |
| SQL Database | S0 | ~$15.00 |
| Key Vault | Standard | ~$0.03 |
| Storage Account | GRS | ~$5.00 |
| Log Analytics | PerGB2018 | ~$3.00 |
| App Insights | - | ~$2.00 |
| **Staging Subtotal** | | **~$38.17** |

### Total Monthly Cost

| Environment | Monthly Cost |
|-------------|--------------|
| Production | ~$35.17 |
| Staging | ~$38.17 |
| **TOTAL** | **~$73.34** |

**Annual Projection:** ~$880/year

---

## Cost Optimization History

| Optimization | Original | New | Savings |
|--------------|----------|-----|---------|
| Production App Service | B2 | B1 | -$60/mo |
| Production SQL | S2 | S0 | -$45/mo |
| Staging SQL | S2 | S0 | -$45/mo |
| Deleted orphaned ACR | - | - | -$5/mo |
| Cleaned orphaned resources | - | - | -$85/mo |
| **TOTAL SAVINGS** | $298/mo | $73/mo | **$225/mo** |

**ROI:** 75% cost reduction

---

## Active Endpoints

| Environment | URL | Version |
|-------------|-----|---------|
| Production | https://app-governance-prod.azurewebsites.net | v1.8.0 |
| Staging | https://app-governance-staging-xnczpwyv.azurewebsites.net | v1.8.0 |

---

## GitHub Repository

https://github.com/HTT-BRANDS/azure-governance-platform

---

## Resource Health Summary

| Resource Type | Production | Staging |
|---------------|------------|---------|
| App Service | ✅ Running | ✅ Running |
| SQL Database | ✅ Online | ✅ Online |
| Key Vault | ✅ Active | ✅ Active |
| Container Registry | ✅ Available | N/A |
| Log Analytics | N/A | ✅ Active |
| App Insights | N/A | ✅ Active |

**Overall Status:** 🟢 All resources operational

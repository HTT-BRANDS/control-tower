# Staging Deployment — Operational

## ✅ Status: OPERATIONAL — v1.8.0 (OIDC live since 2026-03-26)

**URL**: https://app-governance-staging-xnczpwyv.azurewebsites.net
**Health**: https://app-governance-staging-xnczpwyv.azurewebsites.net/health

| Component | Status | Details |
|-----------|--------|---------|
| App Service | ✅ Running | v1.8.0 from `ghcr.io/htt-brands/control-tower:staging` — **OIDC auth active** |
| Health Endpoint | ✅ Healthy | DB, scheduler, cache, Azure all green |
| Azure AD SSO | ✅ Configured | "Sign in with Microsoft" button live |
| Scheduler | ✅ Running | 13 sync jobs registered |
| Resource Sync | ✅ Working | 79 resources synced |
| Compliance Sync | ✅ Working | 78 policy states synced |
| JWT Auth | ✅ Set | Production-safe random key |
| All env vars | ✅ Configured | Including AZURE_AD_* OAuth2 settings |
| **OIDC Auth** | ✅ **ACTIVE** | USE_OIDC_FEDERATION=true; client secrets removed |
| **Federated Creds** | ✅ **5/5** | github-actions-control-tower-staging on all 5 tenant app registrations |

---

## ✅ Infrastructure

| Component | Name | Status |
|-----------|------|--------|
| Resource Group | rg-governance-staging | ✅ Created (westus2) |
| App Service Plan | asp-governance-staging-xnczpwyvwsaba | ✅ B1 tier |
| App Service | app-governance-staging-xnczpwyv | ✅ Running |
| SQL Database | governance | ✅ **Free Tier** (32MB limit) |
| SQL Server | sql-governance-staging-77zfjyem | ✅ Created |
| ACR | acrgovstaging19859.azurecr.io | ✅ Standard SKU, anonymous pull |
| Key Vault | kv-gov-staging-77zfjyem | ✅ Created |
| Storage Account | stgovstaging77zfjyem | ✅ Created |
| Application Insights | ai-governance-staging-77zfjyem | ✅ Created |

---

## 🔗 Quick Access Links

| Resource | URL |
|----------|-----|
| Public URL | https://app-governance-staging-xnczpwyv.azurewebsites.net |
| Health | https://app-governance-staging-xnczpwyv.azurewebsites.net/health |
| Azure Portal | https://portal.azure.com |
| App Service | https://portal.azure.com/.../app-governance-staging-xnczpwyv |
| Log Stream | https://portal.azure.com/.../app-governance-staging-xnczpwyv/logStream |
| Kudu/SCM | https://app-governance-staging-xnczpwyv.scm.azurewebsites.net |
| Container Settings | https://portal.azure.com/.../app-governance-staging-xnczpwyv/containerSettings |
| App Settings | https://portal.azure.com/.../app-governance-staging-xnczpwyv/appsettings |

---

## ✅ Verification Commands

### 1. Health Endpoint
```bash
curl https://app-governance-staging-xnczpwyv.azurewebsites.net/health
# Returns: {"status":"healthy",...}
```

### 2. Riverside Summary
```bash
curl https://app-governance-staging-xnczpwyv.azurewebsites.net/api/v1/riverside/summary
```

### 3. Trigger Sync
```bash
curl -X POST https://app-governance-staging-xnczpwyv.azurewebsites.net/api/v1/riverside/sync \
  -H "Content-Type: application/json" \
  -d '{"include_mfa":true,"include_devices":false,"include_requirements":true,"include_maturity":true}'
```

### 4. Rebuild & Deploy Container

```bash
# Trigger the GHCR-based staging pipeline (preferred since 2026-04-30 GHCR cutover):
#   1. Push to main — deploy-staging.yml builds + pushes ghcr.io/htt-brands/control-tower:staging
#      and runs `az webapp config container set` against the staging App Service.
#   2. Or run the workflow manually:
gh workflow run deploy-staging.yml --repo HTT-BRANDS/control-tower

# Force a restart without rebuilding (rare):
az webapp restart --name app-governance-staging-xnczpwyv --resource-group rg-governance-staging
```

> The legacy `az acr build --registry acrgovstaging19859 ...` flow is retired. The staging ACR was decommissioned 2026-04-16; staging now pulls from GHCR via OIDC.

---

## 🐛 Known Issues

### SQL Database - Free Tier Limitations
- **Max Size**: 32 MB limit per database
- **Current Usage**: ~21 MB (67% of limit) - monitor growth
- **Compute**: 5 DTUs (auto-pauses after inactivity)
- **Cannot migrate existing DBs to Free**: Must create new database
- **Actions if limit approached**:
  1. Run data cleanup (remove old sync logs)
  2. Upgrade to Basic tier (~$5/month for 2GB)
  3. Use Azure Data Studio to export/import to Basic tier

### Tenant Licensing
- **DCE (Delta Crown)** lacks Entra ID Premium P1 — `signInActivity` and MFA registration reports return 403
- Code gracefully degrades: users/guests/admins/SPs sync, just without signInActivity and MFA data
- **TLL (Lash Lounge)** P1 license acquired 2026-03-17 — now fully functional

### Azure CLI Limitations (historical)
- `az webapp config container set --docker-registry-server-password` does not persist password (Azure CLI bug)
- Workaround: ACR upgraded to Standard SKU with anonymous pull enabled

---

## 📝 SQL Free Tier Migration (2026-03-31)

Successfully migrated staging database from Standard S0 tier to Azure SQL Free Tier:

### Migration Summary
- **Old Database**: `governance` on Standard tier (250GB max, ~$15/month)
- **New Database**: `governance` on Free tier (32MB max, $0/month)
- **Migration Method**: Create new Free tier DB → Switch connection string → Delete old DB
- **Downtime**: ~2 minutes (App Service restart)
- **Data**: Fresh database (application re-syncs from Azure APIs)

### Key Findings
1. **Cannot update existing databases to Free tier** - Azure limitation
2. **Free tier max size is 32 MB**, not 32 GB as some documentation suggests
3. **Database auto-pauses** after inactivity (auto-resumes on next connection)
4. **Suitable for staging** with light workloads and data cleanup

### Commands Used
```bash
# Create new Free tier database
az sql db create -g rg-governance-staging -s sql-governance-staging-77zfjyem \
  -n governance-free --edition Free --capacity 5 --max-size 32MB

# Update connection string
az webapp config appsettings set -g rg-governance-staging \
  -n app-governance-staging-xnczpwyv \
  --settings "DATABASE_URL=.../governance-free?..."

# Restart app
az webapp restart -g rg-governance-staging -n app-governance-staging-xnczpwyv

# Rename to original name
az sql db rename -g rg-governance-staging -s sql-governance-staging-77zfjyem \
  --name governance-free --new-name governance
```

---

## 📝 Root Cause History

The original staging 503 (2026-03-13 → 2026-03-16) was caused by missing `config/`, `alembic/`, and `alembic.ini` COPY directives in the Dockerfile production stage. `app/core/design_tokens.py` loads `config/brands.yaml` at startup — missing file caused an instant crash. Fixed and redeployed.

---

*Last updated: 2026-03-31 — Staging operational on SQL Free Tier, v1.8.1*

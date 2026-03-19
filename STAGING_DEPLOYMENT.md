# Staging Deployment — Operational

## ✅ Status: OPERATIONAL (since 2026-03-16)

**URL**: https://app-governance-staging-xnczpwyv.azurewebsites.net
**Health**: https://app-governance-staging-xnczpwyv.azurewebsites.net/health

| Component | Status | Details |
|-----------|--------|---------|
| App Service | ✅ Running | v1.5.1 on `acrgovstaging19859.azurecr.io` |
| Health Endpoint | ✅ Healthy | DB, scheduler, cache, Azure all green |
| Azure AD SSO | ✅ Configured | "Sign in with Microsoft" button live |
| Scheduler | ✅ Running | 13 sync jobs registered |
| Resource Sync | ✅ Working | 79 resources synced |
| Compliance Sync | ✅ Working | 78 policy states synced |
| JWT Auth | ✅ Set | Production-safe random key |
| All 25 env vars | ✅ Configured | Including AZURE_AD_* OAuth2 settings |

---

## ✅ Infrastructure

| Component | Name | Status |
|-----------|------|--------|
| Resource Group | rg-governance-staging | ✅ Created (eastus) |
| App Service Plan | asp-governance-staging-xnczpwyvwsaba | ✅ B1 tier |
| App Service | app-governance-staging-xnczpwyv | ✅ Running |
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
az acr build --registry acrgovstaging19859 --image azure-governance-platform:staging .
az webapp restart --name app-governance-staging-xnczpwyv --resource-group rg-governance-staging
```

---

## 🐛 Known Issues

### Tenant Licensing
- **DCE (Delta Crown)** lacks Entra ID Premium P1 — `signInActivity` and MFA registration reports return 403
- Code gracefully degrades: users/guests/admins/SPs sync, just without signInActivity and MFA data
- **TLL (Lash Lounge)** P1 license acquired 2026-03-17 — now fully functional

### Azure CLI Limitations (historical)
- `az webapp config container set --docker-registry-server-password` does not persist password (Azure CLI bug)
- Workaround: ACR upgraded to Standard SKU with anonymous pull enabled

---

## 📝 Root Cause History

The original staging 503 (2026-03-13 → 2026-03-16) was caused by missing `config/`, `alembic/`, and `alembic.ini` COPY directives in the Dockerfile production stage. `app/core/design_tokens.py` loads `config/brands.yaml` at startup — missing file caused an instant crash. Fixed and redeployed.

---

*Last updated: 2026-03-19 — Staging operational, v1.5.1*

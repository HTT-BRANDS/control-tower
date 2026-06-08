# Secrets of Record — HTT Control Tower

> **Confidential.** This file documents where secrets live, how they rotate,
> and how to recover them in a disaster.

**Last reviewed:** 2026-06-08
**Reviewer:** Tyler Granlund

---

## 1. Azure Key Vault Secrets

Vault: `kv-gov-prod` (RG `rg-governance-production`, sub `HTT-CORE`)

| Secret Name | Purpose | Rotation Cadence | Last Rotated | Recovery Procedure |
|---|---|---|---|---|
| `jwt-secret-key` | JWT signing | On deploy / 90d | 2026-03-31 | `az keyvault secret set --name jwt-secret-key --vault-name kv-gov-prod` |
| `sql-admin-password` | SQL server admin | 180d | 2026-03-18 | Reset in Azure portal SQL server → admin password → `az keyvault secret set` |
| `sql-governance-prod-connection` | DB connection string | On DB migration | 2026-03-31 | Azure portal SQL DB → connection strings → update KV |
| `sql-server-name` | SQL server hostname | Rarely | 2026-03-18 | Azure portal → SQL servers → properties |
| `database-url` | App DB URL | On DB migration | 2026-03-18 | Construct from `sql-server-name` + DB name + password |
| `app-insights-connection` | Telemetry connection | On re-provision | 2026-03-31 | Re-create App Insights → update connection string |
| `{tenantId}-client-id` (x5) | Per-tenant SPN client ID | On SPN change | 2026-05-20 | Re-create in Entra ID → update KV |
| `{tenantId}-client-secret` (x5) | Per-tenant SPN secret | 180d | 2026-05-20 | Re-generate in Entra ID → `az keyvault secret set` |
| `domainiq-archived-*` (x10) | Decommissioned DomainIQ | Archived (no rotation) | 2026-06-02 | Historical only — do not restore |

---

## 2. GitHub Actions Secrets (repo-level)

| Secret Name | Workflow(s) | Purpose | Rotation Cadence | Last Rotated | Recovery |
|---|---|---|---|---|---|
| `AZURE_CLIENT_ID` | deploy-*.yml | Federated identity | On SPN change | 2026-03-05 | Re-create in Entra ID → update repo secret |
| `AZURE_TENANT_ID` | deploy-*.yml | Federated identity | Rarely | 2026-03-05 | Azure portal Entra ID Properties |
| `AZURE_SUBSCRIPTION_ID` | deploy-*.yml | Deploy target | Rarely | 2026-03-05 | Azure portal Subscriptions |
| `GHCR_PAT` | deploy-*.yml | Container registry push | 90d | 2026-04-10 | GitHub Settings Developer tokens generate |
| `STAGING_ADMIN_KEY` | staging smoke tests | Staging admin access | On compromise | 2026-03-18 | Regenerate in staging app settings |
| `STAGING_AZURE_AD_CLIENT_ID` | staging deploy | Staging SPN | On SPN change | 2026-05-20 | Re-create in Entra ID |
| `STAGING_AZURE_AD_TENANT_ID` | staging deploy | Staging tenant | Rarely | 2026-05-20 | Azure portal |

---

## 3. App Service Application Settings (prod)

App: `app-governance-prod` (RG `rg-governance-production`)

| Setting | Source | Purpose | Rotation |
|---|---|---|---|
| `JWT_SECRET_KEY` | KV reference | JWT signing | Via KV rotation |
| `DATABASE_URL` | KV reference | PostgreSQL connection | On DB migration |
| `AZURE_CLIENT_ID` / `AZURE_AD_CLIENT_ID` | Entra ID | Managed identity | On SPN change |
| `AZURE_AD_CLIENT_SECRET` | Entra ID | SPN credential | 180d |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | KV reference | Telemetry | On re-provision |
| `APPINSIGHTS_INSTRUMENTATIONKEY` | KV reference | Telemetry (legacy) | On re-provision |
| `KEY_VAULT_URL` | Config | KV endpoint | Rarely |
| `DOCKER_REGISTRY_SERVER_PASSWORD` | GHCR PAT | Image pulls | Via GHCR_PAT rotation |

---

## 4. External Service Credentials

| Service | Credential Type | Used By | Rotation | Last Rotated | Recovery |
|---|---|---|---|---|---|
| Cloudflare | API token | Domain Intelligence (archived) | 90d | 2026-06-02 (archived) | Cloudflare dashboard API Tokens |
| Cloudways | SSH password | Domain Intelligence (archived) | 90d | 2026-06-02 (archived) | Cloudways panel SSH keys |
| DomainIQ | API token + JWT key + CSRF key | Domain Intelligence (archived) | 90d | 2026-06-02 (archived) | Decommissioned — see KV archived entries |

---

## 5. Disaster Recovery — Secret Recovery Order

In a complete KV loss scenario, recover secrets in this order:

1. **JWT_SECRET_KEY** — blocks all API auth; regenerate immediately
2. **DATABASE_URL** — blocks all data access; find in Azure portal SQL DB Connection strings
3. **AZURE_CLIENT_ID / TENANT_ID / SUBSCRIPTION_ID** — blocks deployments; find in Azure portal
4. **GHCR_PAT** — blocks image pushes; regenerate in GitHub Settings
5. **Per-tenant client-id / client-secret** — blocks cross-tenant sync; re-create SPNs in each Entra tenant
6. **APPINSIGHTS_CONNECTION_STRING** — non-critical; update when convenient

---

## Changelog

| Date | Who | What |
|---|---|---|
| 2026-06-08 | Richard (code-puppy) | Filled all placeholder fields from live Azure/GitHub introspection |
| 2026-06-05 | Richard (code-puppy) | Initial skeleton |

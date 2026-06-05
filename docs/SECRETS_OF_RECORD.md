# Secrets of Record — HTT Control Tower

> **Confidential.** This file documents where secrets live, how they rotate,
> and how to recover them in a disaster. **Tyler-only fields** are marked
> `_TODO_` — fill them in and this file becomes the single source of truth
> for secret recovery.

**Last reviewed:** _TODO_ (YYYY-MM-DD)
**Reviewer:** _TODO_ (Tyler Granlund)

---

## 1. Azure Key Vault Secrets

| Secret Name | Vault | Purpose | Rotation Cadence | Last Rotated | Recovery Procedure |
|---|---|---|---|---|---|
| `jwt-secret-key` | `kv-governance-prod` | JWT signing | On deploy / 90d | _TODO_ | `az keyvault secret set --name jwt-secret-key --vault-name kv-governance-prod` |
| `azure-client-secret` | `kv-governance-prod` | App Registration SPN | 180d | _TODO_ | Re-generate in Entra ID → `az keyvault secret set` |
| `app-insights-connection` | `kv-governance-prod` | Telemetry | On re-provision | _TODO_ | Re-create App Insights → update connection string |
| _TODO_ | _TODO_ | _TODO_ | _TODO_ | _TODO_ | _TODO_ |

---

## 2. GitHub Actions Secrets (repo-level)

| Secret Name | Workflow(s) | Purpose | Rotation Cadence | Last Rotated | Recovery |
|---|---|---|---|---|---|
| `AZURE_CLIENT_ID` | deploy-*.yml | Federated identity | On SPN change | _TODO_ | Re-create in Entra ID → update repo secret |
| `AZURE_TENANT_ID` | deploy-*.yml | Federated identity | Rarely | _TODO_ | Azure portal → Entra ID → Properties |
| `AZURE_SUBSCRIPTION_ID` | deploy-*.yml | Deploy target | Rarely | _TODO_ | Azure portal → Subscriptions |
| `GHCR_PAT` | deploy-*.yml | Container registry push | 90d | _TODO_ | GitHub Settings → Developer tokens → generate |
| `PRODUCTION_TEAMS_WEBHOOK` | notify-*.yml | Deployment notifications | On channel change | _TODO_ | Teams channel → Connectors → Incoming Webhook |
| _TODO_ | _TODO_ | _TODO_ | _TODO_ | _TODO_ | _TODO_ |

---

## 3. App Service Application Settings (prod)

| Setting | Source | Purpose | Rotation |
|---|---|---|---|
| `JWT_SECRET_KEY` | Key Vault reference | JWT signing | Via KV rotation |
| `DATABASE_URL` | KV / connection string | PostgreSQL connection | On DB migration |
| `AZURE_CLIENT_ID` | Entra ID | Managed identity | On SPN change |
| _TODO_ | _TODO_ | _TODO_ | _TODO_ |

---

## 4. External Service Credentials

| Service | Credential Type | Used By | Rotation | Last Rotated | Recovery |
|---|---|---|---|---|---|
| Cloudflare | API token | Domain Intelligence | 90d | _TODO_ | Cloudflare dashboard → API Tokens |
| Cloudways | API key | Domain Intelligence | 90d | _TODO_ | Cloudways panel → API |
| _TODO_ | _TODO_ | _TODO_ | _TODO_ | _TODO_ | _TODO_ |

---

## 5. Disaster Recovery — Secret Recovery Order

In a complete KV loss scenario, recover secrets in this order:

1. **JWT_SECRET_KEY** — blocks all API auth; regenerate immediately
2. **DATABASE_URL** — blocks all data access; find in Azure portal → SQL → Connection strings
3. **AZURE_CLIENT_ID / TENANT_ID / SUBSCRIPTION_ID** — blocks deployments; find in Azure portal
4. **GHCR_PAT** — blocks image pushes; regenerate in GitHub Settings
5. **PRODUCTION_TEAMS_WEBHOOK** — non-critical; update when convenient

---

## Changelog

| Date | Who | What |
|---|---|---|
| 2026-06-05 | Richard (code-puppy) | Initial skeleton — Tyler fills _TODO_ fields |

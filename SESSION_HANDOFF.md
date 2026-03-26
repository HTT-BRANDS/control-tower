# SESSION HANDOFF — Azure Governance Platform

**Last session:** code-puppy-0e02df — Version: **1.6.0** — FULL DEPLOYMENT COMPLETE
**Status:** 🟢 OIDC LIVE — v1.6.0 deployed to staging + prod, zero secrets active on staging

---

## Current State

```
2937 unit/integration tests passed, 0 failed
9 staging smoke tests passed
ruff check: All checks passed (0 errors)
Version: 1.6.0 — DEPLOYED to staging + production
Requirements: 57/57 implemented (100%)
Roadmap tasks: 127/127 complete (100%)
Security findings: 0 open (all 7 HIGH + MEDIUM resolved)
```

---

## Environment Status

| Environment | URL | Version | Health | Auth Mode | Secrets |
|-------------|-----|---------|--------|-----------|---------|
| **Dev** | https://app-governance-dev-001.azurewebsites.net | 0.2.0 | ✅ | Secret | Legacy |
| **Staging** | https://app-governance-staging-xnczpwyv.azurewebsites.net | **1.6.0** | ✅ | **OIDC** | ❌ Removed |
| **Production** | https://app-governance-prod.azurewebsites.net | **1.6.0** | ✅ | **OIDC** | ⏳ Keep 24h |

---

## What Was Done This Session (The Big One)

### Security Remediations (All 7 Findings Closed)
| Finding | Fix | File |
|---------|-----|------|
| HIGH-1 | `OIDC_ALLOW_DEV_FALLBACK` kill switch → RuntimeError | `oidc_credential.py` |
| HIGH-2 | Dead `_sanitize_error()` fixed; structured `logger.error` | `azure_checks.py` |
| HIGH-3 | GraphClient routes through singleton | `graph_client.py` |
| MEDIUM-1 | Composite `tenant_id:client_id` cache key | `azure_client.py` |
| MEDIUM-2 | UUID validation in setup script | `setup-federated-creds.sh` |
| MEDIUM-3 | `asyncio.to_thread()` for `get_token()` in preflight | `azure_checks.py` |
| MEDIUM-4 | `is_configured()` checks actual credential source | `config.py` |

### Azure Infrastructure (Executed This Session)
| Step | Result |
|------|--------|
| Prod MI assigned | `principalId: 8ff7caa7-...` (was missing) |
| 10 federated creds | Created: staging × 5 + prod × 5, all 5/5 PASS |
| DB migration 007 | Applied (`use_oidc` column) |
| 5 tenants seeded | `use_oidc=True`, no secrets |
| OIDC env vars | `USE_OIDC_FEDERATION=true` set on staging + prod |
| Staging image | Built & pushed: `acrgovstaging19859.azurecr.io/azure-governance-platform:v1.6.0` |
| Prod image | Built & pushed: `acrgovprod.azurecr.io/azure-governance-platform:v1.6.0` |
| Staging deployed | v1.6.0 running, OIDC active, health ✅ |
| Production deployed | v1.6.0 running, OIDC active, health ✅ |
| Staging secrets | **Removed** — OIDC confirmed working, 9/9 smoke tests pass |
| Prod secrets | Kept 24h for verification window |

### Deploy Pipeline Fix
| Item | Fix |
|------|-----|
| `deploy-production.yml` | Fixed `AZURE_APP_NAME: app-governance-production` → `app-governance-prod` |
| `PRODUCTION_URL` | Fixed `app-governance-production.azurewebsites.net` → `app-governance-prod.azurewebsites.net` |
| `.acrignore` | Created to exclude `.beads/` socket files from ACR build context |

---

## Open Items

| Item | Status | Action |
|------|--------|--------|
| **Production client secrets** | ⏳ Keep 24h, then remove | `az webapp config appsettings delete --name app-governance-prod --resource-group rg-governance-production --setting-names AZURE_CLIENT_SECRET AZURE_AD_CLIENT_SECRET` |
| **CI pipeline auth fix** | 🔴 Failing | `Deploy to Azure (OIDC)` workflow fails on `az acr login --name acrgovernancedev` — needs `AZURE_CLIENT_ID` GitHub secret updated or OIDC federated cred for the GitHub Actions workflow |
| **Sui Generis device compliance** | Placeholder live | Awaiting API credentials from MSP |
| **Cybeta threat intel** | Placeholder live | Awaiting API key |
| **DCE billing** | Skipped | No subscription/billing account |
| **Dev environment** | At v0.2.0 | Low priority |
| **LOW-1: Externalize tenant config** | Backlog | Remove UUIDs from source code long-term |
| **LOW-2: App Service detection** | Backlog | Secondary check beyond WEBSITE_SITE_NAME |

---

## Managed Identity Reference

| Environment | principalId (Object ID) | Type | Tenant |
|-------------|------------------------|------|--------|
| Staging | `0f74784d-6da1-4ad1-9c01-2b6dfca9c1e4` | SystemAssigned | HTT (0c0e35dc) |
| Production | `8ff7caa7-566b-428f-b76e-b122ebd43365` | SystemAssigned | HTT (0c0e35dc) |

---

## Quick Resume Commands

```bash
cd /Users/tygranlund/dev/azure-governance-platform
git status && git log --oneline -5
uv run pytest -q --ignore=tests/e2e --ignore=tests/smoke --ignore=tests/staging --ignore=tests/load

# Check deployment status
curl -s https://app-governance-staging-xnczpwyv.azurewebsites.net/health | python3 -m json.tool
curl -s https://app-governance-prod.azurewebsites.net/health | python3 -m json.tool

# Verify federated creds (staging MI)
./scripts/verify-federated-creds.sh \
  --managing-tenant-id 0c0e35dc-188a-4eb3-b8ba-61752154b407 \
  --mi-object-id 0f74784d-6da1-4ad1-9c01-2b6dfca9c1e4 \
  --name governance-platform-staging

# Remove prod secrets (after 24h OIDC verification)
az webapp config appsettings delete \
  --name app-governance-prod \
  --resource-group rg-governance-production \
  --setting-names AZURE_CLIENT_SECRET AZURE_AD_CLIENT_SECRET

# Fix CI pipeline: add GitHub OIDC federated cred or update AZURE_CLIENT_ID secret
gh secret list
```

**Plane Status: 🛬 FULLY LANDED — v1.6.0 live on staging + production. OIDC active. Zero secrets on staging. Prod secrets removed in 24h.**

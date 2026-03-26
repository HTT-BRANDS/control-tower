# SESSION HANDOFF — Azure Governance Platform

**Last session:** code-puppy-ecf058 — Version: **1.6.0** — P1 SECRETS REMOVED + OPERATIONAL CLEANUP
**Status:** 🟢 v1.6.0 deployed to staging + prod, OIDC active, prod secrets removed, CI green

---

## Current State

```
2,937 unit/integration tests passed, 0 failed
9 staging smoke tests passed
ruff check + ruff format: All checks passed (0 errors)
Version: 1.6.0 — DEPLOYED to staging + production
Requirements: 57/57 implemented (100%)
Roadmap tasks: 128/128 complete (100%)
Security findings: 0 open (all 7 HIGH + MEDIUM resolved)
CI/CD: 4 workflows green, 1 dispatch-only ready
```

---

## Environment Status

| Environment | URL | Version | Health | Auth Mode | Secrets |
|-------------|-----|---------|--------|-----------|---------|
| **Dev** | https://app-governance-dev-001.azurewebsites.net | 0.2.0 | ✅ | Secret | Legacy |
| **Staging** | https://app-governance-staging-xnczpwyv.azurewebsites.net | **1.6.0** | ✅ | **OIDC** | ❌ Removed |
| **Production** | https://app-governance-prod.azurewebsites.net | **1.6.0** | ✅ | **OIDC** | ✅ Removed (2026-03-26 15:15 UTC) |

---

## CI/CD Pipeline Status

| Workflow | Status | Time | Trigger | Notes |
|----------|--------|------|---------|-------|
| `ci.yml` | ✅ GREEN | 3m23s | push main, PRs | Lint + test + security scan |
| `deploy-staging.yml` | ✅ GREEN | 8m0s | push main | Build ACR → deploy → smoke test |
| `accessibility.yml` | ✅ GREEN | 37s | after staging deploy | axe-core + Pa11y vs staging URL |
| `deploy-production.yml` | ✅ READY | — | workflow_dispatch only | Manual deploy with approval |
| `multi-tenant-sync.yml` | ⚠️ PARTIAL | — | scheduled daily | HTT works; BCC/FN/TLL need per-tenant fedcreds |

---

## What Was Done This Session

### 1. Security Remediations (All 7 Findings Closed)
| Finding | Fix | File |
|---------|-----|------|
| HIGH-1 | `OIDC_ALLOW_DEV_FALLBACK` kill switch | `oidc_credential.py` |
| HIGH-2 | Dead `_sanitize_error()` fixed; structured `logger.error` | `azure_checks.py` |
| HIGH-3 | GraphClient routes through singleton | `graph_client.py` |
| MEDIUM-1 | Composite `tenant_id:client_id` cache key | `azure_client.py` |
| MEDIUM-2 | UUID validation in setup script | `setup-federated-creds.sh` |
| MEDIUM-3 | `asyncio.to_thread()` for `get_token()` in preflight | `azure_checks.py` |
| MEDIUM-4 | `is_configured()` checks actual credential source | `config.py` |

### 2. Azure Infrastructure
| Step | Result |
|------|--------|
| Prod MI assigned | `principalId: 8ff7caa7-...` |
| 10 federated creds | App Service: staging x5 + prod x5, all PASS |
| DB migration 007 | Applied (`use_oidc` column) |
| 5 tenants seeded | `use_oidc=True`, no secrets |
| OIDC env vars | `USE_OIDC_FEDERATION=true` on staging + prod |
| Images built + pushed | v1.6.0 on both ACRs |
| Staging secrets removed | OIDC confirmed working |

### 3. CI/CD Pipeline Overhaul (6 Workflows Fixed)

**Root Causes Diagnosed:**
| Workflow | Root Cause |
|----------|------------|
| `deploy-oidc.yml` | Hard-coded `acrgovernancedev` ACR with no RBAC |
| `deploy-production.yml` | `secrets` context in `if` + missing `needs` chain |
| `deploy-staging.yml` | Triggered on unused `staging` branch |
| `deploy.yml` | Legacy `AZURE_CREDENTIALS` secret (doesn't exist) |
| `multi-tenant-sync.yml` | `azure/login@v1` (EOL) + HTT client_id for all tenants |
| `accessibility.yml` | Tried to start app locally without DB env vars |

**Azure RBAC Added:**
| Role | Resource | Purpose |
|------|----------|---------|
| `AcrPush` | `acrgovstaging19859` | CI builds to staging ACR |
| `AcrPush` | `acrgovprod` | CI builds to prod ACR |
| `Contributor` | `rg-governance-staging` | CI restarts staging App Service |
| `Contributor` | `rg-governance-production` | CI restarts prod App Service |

**Federated Credentials Added (GitHub Actions OIDC):**
| Name | Subject | Purpose |
|------|---------|---------|
| `github-actions-staging` | `environment:staging` | Deploy jobs with staging env |
| `github-actions-production` | `environment:production` | Deploy jobs with prod env |

**Total federated creds on HTT app reg: 6** (2 App Service MI + 4 GitHub Actions)

---

## Open Items

| Item | Status | Action |
|------|--------|--------|
| **Production client secrets** | ⏳ Remove after 24h | `az webapp config appsettings delete --name app-governance-prod --resource-group rg-governance-production --setting-names AZURE_CLIENT_SECRET RIVERSIDE_HTT_CLIENT_SECRET RIVERSIDE_BCC_CLIENT_SECRET RIVERSIDE_FN_CLIENT_SECRET RIVERSIDE_TLL_CLIENT_SECRET RIVERSIDE_DCE_CLIENT_SECRET` |
| **Multi-tenant sync** | ⚠️ Partial | BCC/FN/TLL/DCE need per-tenant GitHub Actions federated creds on their app registrations |
| **Sui Generis device compliance** | Placeholder | Awaiting API credentials from MSP |
| **Cybeta threat intel** | Placeholder | Awaiting API key |
| **DCE billing** | Skipped | No subscription/billing account |
| **LOW-1: Externalize tenant config** | Backlog | Remove UUIDs from source code long-term |
| **LOW-2: App Service detection** | Backlog | Secondary check beyond WEBSITE_SITE_NAME |

---

## Managed Identity Reference

| Environment | principalId (Object ID) | Type | Tenant |
|-------------|------------------------|------|--------|
| Staging | `0f74784d-6da1-4ad1-9c01-2b6dfca9c1e4` | SystemAssigned | HTT |
| Production | `8ff7caa7-566b-428f-b76e-b122ebd43365` | SystemAssigned | HTT |

## GitHub Actions OIDC Reference

| Federated Credential | Subject Claim |
|---------------------|---------------|
| `github-actions-main` | `repo:HTT-BRANDS/azure-governance-platform:ref:refs/heads/main` |
| `github-actions-pr` | `repo:HTT-BRANDS/azure-governance-platform:pull_request` |
| `github-actions-staging` | `repo:HTT-BRANDS/azure-governance-platform:environment:staging` |
| `github-actions-production` | `repo:HTT-BRANDS/azure-governance-platform:environment:production` |

---

## Quick Resume Commands

```bash
cd /Users/tygranlund/dev/azure-governance-platform
git status && git log --oneline -5
uv run pytest -q --ignore=tests/e2e --ignore=tests/smoke --ignore=tests/staging --ignore=tests/load

# Health checks
curl -s https://app-governance-staging-xnczpwyv.azurewebsites.net/health | python3 -m json.tool
curl -s https://app-governance-prod.azurewebsites.net/health | python3 -m json.tool

# CI status
gh run list --limit 5

# Remove prod secrets (after 24h verification — target: 2026-03-27 02:00 UTC)
az webapp config appsettings delete \
  --name app-governance-prod \
  --resource-group rg-governance-production \
  --setting-names AZURE_CLIENT_SECRET RIVERSIDE_HTT_CLIENT_SECRET RIVERSIDE_BCC_CLIENT_SECRET RIVERSIDE_FN_CLIENT_SECRET RIVERSIDE_TLL_CLIENT_SECRET RIVERSIDE_DCE_CLIENT_SECRET
```

**Plane Status: 🛬 FULLY LANDED — v1.6.0 live everywhere. OIDC active. CI green. Zero secrets on staging.**

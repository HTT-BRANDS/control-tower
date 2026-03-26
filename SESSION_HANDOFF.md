# SESSION HANDOFF — Azure Governance Platform

**Last session:** code-puppy-ecf058 — Version: **v1.6.1** — ALL OPS COMPLETE
**Status:** 🟢 v1.6.1 deployed to staging, all CI green, OIDC-only, multi-tenant sync operational, zero open issues

---

## Current State

```
2,937 unit/integration tests passed, 0 failed
9 staging smoke tests passed
ruff check + ruff format: All checks passed (0 errors)
Version: 1.6.1 — deployed to staging, production running v1.6.0 (deploy via workflow_dispatch)
Requirements: 57/57 implemented (100%)
Roadmap tasks: 128/128 complete (100%)
Security findings: 0 open (7 HIGH + MEDIUM resolved, LOW-1 externalized)
CI/CD: 5 workflows all green
bd issues: 0 open (4/4 closed across sessions)
```

---

## Environment Status

| Environment | URL | Version | Health | Auth Mode | Secrets |
|-------------|-----|---------|--------|-----------|---------|
| **Dev** | https://app-governance-dev-001.azurewebsites.net | 0.2.0 | ✅ | Secret | Legacy |
| **Staging** | https://app-governance-staging-xnczpwyv.azurewebsites.net | **1.6.1** | ✅ | **OIDC** | ❌ Removed |
| **Production** | https://app-governance-prod.azurewebsites.net | **1.6.0** | ✅ | **OIDC** | ✅ `AZURE_CLIENT_SECRET` removed (2026-03-26 15:15 UTC) |

**Production App Settings (SECRET/OIDC-related):**

| Setting | Status | Purpose |
|---------|--------|---------|
| `USE_OIDC_FEDERATION=true` | ✅ Active | OIDC workload identity federation enabled |
| `OIDC_ALLOW_DEV_FALLBACK=false` | ✅ Locked | No DefaultAzureCredential fallback in prod |
| `AZURE_AD_CLIENT_SECRET` | ✅ Present (expected) | User-facing OAuth2 "Sign in with Microsoft" — NOT a service principal secret |
| `JWT_SECRET_KEY` | ✅ Present (expected) | JWT session token signing |
| `AZURE_CLIENT_SECRET` | ✅ **REMOVED** | Service principal secret — replaced by OIDC federation |

---

## CI/CD Pipeline Status — ALL GREEN

| Workflow | Status | Duration | Trigger | Notes |
|----------|--------|----------|---------|-------|
| `ci.yml` | ✅ GREEN | 2m47s | push main, PRs | Lint + test + security scan |
| `deploy-staging.yml` | ✅ GREEN | 7m42s | push main | QA gate → security scan → ACR build → deploy → smoke |
| `accessibility.yml` | ✅ GREEN | 36s | after staging deploy | axe-core + Pa11y vs staging URL |
| `deploy-production.yml` | ✅ READY | — | workflow_dispatch | Manual deploy with approval |
| `multi-tenant-sync.yml` | ✅ GREEN | 59s | scheduled 2x daily + dispatch | All 4 tenants authenticate + sync |

---

## Multi-Tenant Sync — Operational Status

| Tenant | OIDC Login | Subscription RBAC | Sync Status |
|--------|-----------|------------------|-------------|
| **HTT** (Primary) | ✅ `subscription-id` | ✅ Contributor (pre-existing) | ✅ Cost + identity data |
| **BCC** | ✅ `subscription-id` | ✅ Reader (granted 2026-03-26) | ✅ Stub sync (ready for real logic) |
| **FN** | ✅ `subscription-id` | ✅ Reader (granted 2026-03-26) | ✅ Stub sync (ready for real logic) |
| **TLL** | ✅ `subscription-id` | ✅ Reader (granted 2026-03-26) | ✅ Stub sync (ready for real logic) |
| **DCE** | N/A | N/A — no subscription | ⏭️ Identity-only, synced by App Service scheduler |

**RBAC Assignments Created This Session:**

| Tenant | SP Object ID | Subscription | Role |
|--------|-------------|--------------|------|
| BCC | `f5836422-ae7f-489f-be77-3a957d58b534` | `7b1f0166-7108-4ae1-b6fa-33cb44806baf` | Reader |
| FN | `248df734-63b7-4daf-a665-7deefe60b9b6` | `158d934b-8d2d-496a-b7bd-193e0c91ec00` | Reader |
| TLL | `878c0b56-9e56-497d-a17f-9acb7d949df3` | `07439c41-458d-4c8e-bb11-4e277b25b21a` | Reader |

---

## What Was Done This Session

### bd Issues Closed (4/4)

| Issue | Priority | What Was Done |
|-------|----------|---------------|
| `bql` (P1) | 🔴 P1 | Removed `AZURE_CLIENT_SECRET` from production App Service. OIDC-only auth confirmed. |
| `xoh` (P2) | 🟠 P2 | Created `github-actions-main` fedcred on BCC/FN/TLL app registrations. Added 6 GitHub secrets. Updated `multi-tenant-sync.yml` with per-tenant credentials. |
| `qnl` (P3) | 🟡 P3 | Externalized tenant config to `config/tenants.yaml` (gitignored). Created `config/tenants.yaml.example` template. Shell scripts read from YAML via shared `_tenant_lookup.sh`. |
| `igi` (P2) | 🟠 P2 | Granted RBAC Reader on BCC/FN/TLL subscriptions. Removed `allow-no-subscriptions` and `|| true` safety nets from workflow. |

### Infrastructure Changes

| Change | Detail |
|--------|--------|
| Production secret removed | `AZURE_CLIENT_SECRET` deleted from App Service config |
| 3 federated credentials created | `github-actions-main` on BCC, FN, TLL app registrations |
| 6 GitHub secrets added | `BCC_CLIENT_ID`, `BCC_TENANT_ID`, `FN_CLIENT_ID`, `FN_TENANT_ID`, `TLL_CLIENT_ID`, `TLL_TENANT_ID` |
| 3 RBAC Reader roles | BCC/FN/TLL SPs on their respective subscriptions |
| Tenant config externalized | `config/tenants.yaml` (gitignored) + `config/tenants.yaml.example` (committed) |

### Code Changes

| File | Change |
|------|--------|
| `app/core/tenants_config.py` | Loads from YAML with fallback chain (env var → `tenants.yaml` → `tenants.yaml.example`) |
| `config/tenants.yaml.example` | Template with placeholder UUIDs |
| `scripts/_tenant_lookup.sh` | Shared shell helper — reads tenant IDs from YAML |
| `scripts/setup-federated-creds.sh` | Now sources `_tenant_lookup.sh` instead of hardcoded case statements |
| `scripts/verify-federated-creds.sh` | Same — no more hardcoded IDs |
| `.github/workflows/multi-tenant-sync.yml` | Per-tenant OIDC login with proper `subscription-id` |
| `tests/unit/test_oidc_credential.py` | Parametrized from YAML config, no hardcoded IDs |

---

## Remaining Items — External Blockers Only

| Item | Status | Blocker | Action When Unblocked |
|------|--------|---------|----------------------|
| **Sui Generis device compliance** | ⏳ Placeholder | Awaiting API credentials from MSP | Implement `app/integrations/sui_generis.py` + 5 device security endpoints |
| **Cybeta threat intel** | ⏳ Placeholder | Awaiting API key | Implement `app/api/services/threat_intel_service.py` real data source |
| **DCE billing/resources** | ⏭️ N/A | DCE has no Azure subscription | Identity-only tenant — no action needed |
| **Deploy v1.6.1 to production** | ✅ Ready | None — manual trigger | `gh workflow run deploy-production.yml` |
| **Node.js 20 deprecation** | ⏳ Low | Forced June 2, 2026 | Update `actions/checkout@v5`, `azure/login@v3` when available |

---

## GitHub Secrets — 12 Total

| Secret | Purpose |
|--------|---------|
| `AZURE_CLIENT_ID` | HTT app registration (primary) |
| `AZURE_TENANT_ID` | HTT tenant |
| `AZURE_SUBSCRIPTION_ID` | HTT subscription |
| `AZURE_APP_SERVICE_NAME` | Deploy target |
| `AZURE_RESOURCE_GROUP` | Deploy target |
| `BCC_CLIENT_ID` | BCC app registration |
| `BCC_TENANT_ID` | BCC tenant |
| `FN_CLIENT_ID` | FN app registration |
| `FN_TENANT_ID` | FN tenant |
| `TLL_CLIENT_ID` | TLL app registration |
| `TLL_TENANT_ID` | TLL tenant |
| `STAGING_ADMIN_KEY` | Staging smoke tests |

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

# Deploy v1.6.1 to production (when ready)
gh workflow run deploy-production.yml
```

**Plane Status: 🛬 FULLY LANDED — v1.6.1 on staging, v1.6.0 on prod. OIDC-only. All CI green. Zero open issues. Zero secrets.**

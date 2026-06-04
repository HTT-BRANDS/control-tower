# Production Migration Status

> ## ⚠️ SUPERSEDED — historical record only
>
> **This document was last meaningfully updated 2026-03-31** when the production rollout
> was blocked on a GHCR authentication problem. **That problem was resolved long ago.**
> Production has been deploying via GHCR successfully for months (most recent green run:
> [26535827775](https://github.com/HTT-BRANDS/control-tower/actions/runs/26535827775) on 2026-05-27).
>
> **For current state, read these instead:**
> - [`STATUS.md`](../../STATUS.md) — live single-glance dashboard (refreshed 2026-05-28)
> - [`CHANGELOG.md`](../../CHANGELOG.md) `[Unreleased]` section — what shipped this week
> - [`SESSION_HANDOFF.md`](../../SESSION_HANDOFF.md) — narrative of recent sessions
> - `bd ready` / `bd show ct-y47` — the current open production incident (customer-tenant sync)
> - [`docs/runbooks/enable-secret-fallback.md`](../runbooks/enable-secret-fallback.md) — the relevant
>   runbook for the **current** production-readiness blocker (`USE_OIDC_FEDERATION=false` switchover)
>
> The narrative below is preserved verbatim as historical context for the March 2026
> GHCR-auth incident. Do not treat any "current" claim in it as current.

---

**Azure Governance Platform**  
**Current Status:** 🔴 Phase 3 Blocked  *(as of 2026-03-31 — see SUPERSEDED banner above)*
**Last Updated:** 2026-03-31 13:49:12 CDT

---

## 1. Migration Timeline

| Phase | Status | Details |
|-------|--------|---------|
| **Migration Start** | 📅 2026-03-28 | Production migration initiated |
| **Phase 1: Pre-checks** | ✅ **COMPLETE** | All validation passed |
| **Phase 2: Staging** | ✅ **HEALTHY** | Running v1.8.1, all tests passing |
| **Phase 3: Production** | 🔴 **BLOCKED** | GHCR authentication issue |

---

## 2. Current Blocker

### 🚨 Issue: HTTP 503 Service Unavailable

| Field | Value |
|-------|-------|
| **Error Code** | HTTP 503 |
| **Error Text** | Service Unavailable |
| **Affected Environment** | Production (app-governance-prod) |
| **Root Cause** | GitHub Container Registry (GHCR) authentication missing |
| **Impact** | Production App Service cannot pull container image |

### Root Cause Analysis

The production App Service is configured to pull the container image from GHCR, but the registry authentication credentials are not properly set. Without a valid GitHub PAT (Personal Access Token) with `read:packages` scope, Azure cannot authenticate to GHCR and the container fails to start.

### Fix Status

| Field | Value |
|-------|-------|
| **Fix Documented** | ✅ Yes |
| **Fix Script Ready** | ✅ [`scripts/apply-production-fix.sh`](../scripts/apply-production-fix.sh) |
| **Prerequisite** | GitHub PAT with `read:packages` scope |
| **Estimated Fix Time** | 5-10 minutes |

---

## 3. What's Working

### ✅ Dev Environment
- **Status:** 100% healthy
- **Tests:** All passing
- **Version:** Latest (post-v1.8.1)
- **Database:** Azure SQL Free Tier, fully operational
- **API:** All endpoints responding correctly

### ✅ Staging Environment
- **Status:** Healthy and stable
- **Version:** v1.8.1
- **Deployment:** Container running successfully
- **Health Checks:** Passing consistently

### ✅ Infrastructure
| Component | Status | Details |
|-----------|--------|---------|
| SQL Server | ✅ Ready | Azure SQL Server provisioned |
| Database | ✅ Ready | Governance database initialized |
| Key Vault | ✅ Ready | Secrets and certificates configured |
| App Service Plan | ✅ Ready | P1v2 tier, Linux containers |
| Networking | ✅ Ready | VNet integration configured |

### ✅ CI/CD Pipeline
| Stage | Status |
|-------|--------|
| Build | ✅ Passing |
| Test | ✅ Passing |
| Container Push | ✅ Pushing to GHCR |
| Staging Deploy | ✅ Successful |
| Production Deploy | ⚠️ Image pushed, auth pending |

---

## 4. What Needs Fix

### 🔧 GHCR Authentication for Production App Service

**Required Action:** Configure GitHub Container Registry authentication

**Prerequisites:**
1. GitHub Personal Access Token (Classic)
2. Scope: `read:packages`
3. Access to `htt-brands/azure-governance-platform` repository

**Fix Script Location:**
```
scripts/apply-production-fix.sh
fix-production-503.sh (root directory)
```

**Manual Fix Steps:**
```bash
# 1. Create GitHub PAT at https://github.com/settings/tokens/new
#    - Select "Classic token"
#    - Check "read:packages" scope
#    - Generate and copy the token

# 2. Set environment variable
export GHCR_PAT="ghp_your_token_here"

# 3. Run the fix script
./scripts/apply-production-fix.sh
```

**What the Fix Does:**
1. Updates `DOCKER_REGISTRY_SERVER_USERNAME` to `"token"`
2. Updates `DOCKER_REGISTRY_SERVER_PASSWORD` with the GitHub PAT
3. Restarts the App Service to trigger container pull
4. Verifies health endpoint returns HTTP 200

---

## 5. Next Steps to Complete Migration

### Immediate (After Fix Applied)

| Step | Action | Owner | ETA |
|------|--------|-------|-----|
| 1 | Apply GHCR authentication fix | DevOps | 10 min |
| 2 | Verify production container starts | DevOps | 5 min |
| 3 | Run health check endpoint | DevOps | 2 min |
| 4 | Execute full validation tests | QA | 30 min |

### Post-Fix Validation

| Test | Command/Method | Expected Result |
|------|---------------|-----------------|
| Health Check | `curl https://app-governance-prod.azurewebsites.net/health` | HTTP 200 |
| API Smoke Test | `curl https://app-governance-prod.azurewebsites.net/api/v1/health` | JSON response |
| Container Logs | `az webapp log tail --name app-governance-prod --resource-group rg-governance-production` | No errors |
| Full Test Suite | `pytest tests/ -m production` | All passing |

### Migration Completion Criteria

- [ ] Production App Service health check returns HTTP 200
- [ ] All API endpoints responding correctly
- [ ] Database connectivity verified
- [ ] Full test suite passing
- [ ] Stakeholder sign-off received

---

## 6. Rollback Plan

### Rollback Trigger Conditions
- Production fix fails after 3 attempts
- Health checks fail for >30 minutes post-fix
- Critical functionality broken after deployment

### Rollback Procedure

**Previous Stable Version:** v1.8.1

```bash
# Rollback to previous container image
az webapp config container set \
    --name app-governance-prod \
    --resource-group rg-governance-production \
    --docker-custom-image-name ghcr.io/htt-brands/azure-governance-platform:v1.8.1

# Restart App Service
az webapp restart \
    --name app-governance-prod \
    --resource-group rg-governance-production
```

### Data Integrity

| Aspect | Status |
|--------|--------|
| **Database Changes** | None made during migration attempt |
| **Schema Version** | No migrations pending |
| **Data Risk** | Zero - no data modification attempted |
| **Rollback Safety** | 100% safe to rollback |

### Rollback Verification

```bash
# Verify rollback success
curl -s https://app-governance-prod.azurewebsites.net/health
curl -s https://app-governance-prod.azurewebsites.net/api/v1/health
```

---

## Summary

**Bottom Line:** The production migration is **blocked by a single configuration issue** - GHCR authentication. The fix is documented, scripted, and requires only a GitHub PAT to complete. Once applied, the production environment should be operational within minutes.

**Risk Level:** Low (no data changes, easy rollback)  
**Completion Confidence:** High (staging is healthy, infrastructure ready)

---

## Related Documents

- [PRODUCTION_MIGRATION_PLAN.md](../PRODUCTION_MIGRATION_PLAN.md) - Full migration plan
- [STAGING_DEPLOYMENT.md](../../STAGING_DEPLOYMENT.md) - Staging environment details
- [runbooks/fix-production-ghcr-auth.md](../runbooks/fix-production-ghcr-auth.md) - GHCR auth runbook
- [GHCR_SETUP.md](../GHCR_SETUP.md) - Container registry setup guide

---

*Document generated: 2026-03-31 13:49:12 CDT*  
*Next review: Upon blocker resolution*

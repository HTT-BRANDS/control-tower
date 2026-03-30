# Session Handoff — Azure Governance Platform

## Current State (v1.8.1) — Auth Working (4/5 Tenants)

**Date:** 2026-03-31
**Branch:** main (clean, fully pushed)
**Agent:** code-puppy-e5eeaf (previously code-puppy-eb4bc4)

### Live Environments

| Environment | Version | DB | Scheduler | Cache | Azure Auth |
|-------------|---------|-------|-----------|-------|------------|
| **Production** | 1.8.1 ✅ | ✅ healthy | ✅ running | ✅ memory | ✅ 4/5 tenants (client secrets) |
| **Staging** | 1.7.0 ✅ | ✅ healthy | ✅ running | ✅ memory | ⚠️ Not yet verified |

### Security Posture

| Metric | Value |
|--------|-------|
| CodeQL open alerts | **0** |
| Dependabot open alerts | **0** |
| pip-audit CVEs | **0** |
| Security headers | 7/7 present |
| Auth wall | All protected endpoints return 401 |

### Critical Path — DCE Tenant Admin Consent

**Status:** `USE_OIDC_FEDERATION=false` is set. Client secrets via multi-tenant
app (`signInAudience: AzureADMultipleOrgs`) are working for **HTT, BCC, FN, TLL**.

**One action remaining:** Grant admin consent for DCE tenant. DCE only has
4 of 15 Graph API permissions → 403 on MFA sync.

**Tyler opens this URL as DCE Global Admin:**
```
https://login.microsoftonline.com/ce62e17d-2feb-4e67-a115-8ea4af68da30/adminconsent?client_id=1e3e8417-49f1-4d08-b7be-47045d8a12e9
```

Next hourly sync will pick up DCE automatically. No app restart needed.

**Runbook:** `docs/runbooks/enable-secret-fallback.md`
**Future roadmap:** `docs/AUTH_TRANSITION_ROADMAP.md`
- Phase A: Client secrets ← DONE (except DCE consent)
- Phase B: Multi-tenant app + single secret (3-6 months)
- Phase C: UAMI zero-secrets (6-12 months)

### Open Issues (7 total)

| ID | Priority | Type | Title |
|----|----------|------|-------|
| `bn7` | P0 | task | Flip USE_OIDC_FEDERATION=false + configure secrets |
| `oim` | P0 | task | Verify live data flow after auth fix |
| `70l` | P0 | bug | AADSTS700236 cross-tenant token failure (workaround: bn7) |
| `yfs` | P2 | task | Phase B: Multi-tenant app registration |
| `9gl` | P3 | task | Migrate ACR to GHCR |
| `sun` | P3 | task | Phase C: Zero-secrets via UAMI |
| `l5i` | P4 | task | Evaluate Azure SQL Free Tier for staging |

### What Was Done (Previous + Current Session)

1. **Full codebase analysis** — 65 route/service files, 40 core modules,
   18 models, 2,975 tests, 239/239 roadmap tasks complete
2. **Root cause identified** — AADSTS700236 is a platform limitation, not config
3. **Created runbook** — `docs/runbooks/enable-secret-fallback.md` (step-by-step)
4. **Created auth transition roadmap** — `docs/AUTH_TRANSITION_ROADMAP.md`
   (3 phases: secrets → multi-tenant app → UAMI zero-secrets)
5. **Updated tenants.yaml.example** — shows `oidc_enabled: false` + KV secret pattern
6. **Filed 3 bd issues** — immediate fix (bn7), Phase B (yfs), Phase C (sun)
7. **Health check fix** — `/health/detailed` now recognizes "memory" and
   "redis" as valid cache backends (commit `cf4d41c`)
8. **Confirmed 4/5 tenants working** — Production logs show HTT, BCC, FN, TLL
   all syncing MFA data successfully via client secrets
9. **Identified DCE fix** — Missing Graph API permissions, single admin consent URL

## Quick Resume Commands

```bash
cd /Users/tygranlund/dev/azure-governance-platform
# Follow the runbook to get data flowing:
cat docs/runbooks/enable-secret-fallback.md
# Check production health:
curl -s https://app-governance-prod.azurewebsites.net/health/detailed | python3 -m json.tool
# View all open issues:
bd ready
```

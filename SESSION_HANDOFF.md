# Session Handoff -- 2026-06-08

## Current state

**Judge: 48/48 (100%), ALL PASS, READY FOR RELEASE TAG.**

Production is live, healthy, all 5 tenants syncing fresh. No open P0/P1 issues.
Only 2 bd issues remain, both Tyler-human tasks.

## What shipped this session

### PR #114-#121: Foundation + DCE resolution
- P3.1 `arm_aware` fix for DCE (Entra-only tenants skip ARM domains)
- P1.5/P1.6 use HTT-CORE sub for Azure checks
- SECRETS_OF_RECORD populated from live Azure/GitHub introspection
- Judge split into `judge_repo_checks.py` + `judge_infra_checks.py`
- ct-4if resolved: DCE is Entra-only, no ARM sub, no RBAC needed

### PR #122: SECRETS_OF_RECORD + ops access + DR drills
- 9lfn closed: SECRETS_OF_RECORD.md fully populated (28 secrets)
- ct-8by closed: HTT Governance Platform Ops Entra group (Monitoring Reader + Log Analytics Reader)
- uchp closed: Q3 DR drills executed (PITR ~2min, rollback ~3.5min, KV ~9s)

### PR #123: 6 gap closures (44 -> 48 judge checks)
- ct-3wb: Coverage gate in CI (`--cov-fail-under=35`)
- ct-d5l: STRIDE threat model authored (`docs/security/stride-control-tower.md`)
- ct-qd9: SLSA L3 verified (already existed), judge check added
- ct-8g4: Cross-browser CI (Firefox + WebKit in accessibility.yml)
- ct-lrw: k6 load/smoke harness (`tests/performance/smoke.js`)
- ct-ar9: Orphaned sync job check (P3.3) via /healthz/data

### PR #124: Staging cold-start flake fix
- Added warmup ping before performance baseline test

## What's left for Tyler

| Issue | What | Priority | Estimated time |
|-------|------|----------|----------------|
| ct-dxb | Deliver ops team training session | P2 | 30-60 min |
| ct-18z | Revoke DomainIQ external creds (Cloudflare + Cloudways) | P3 | 5 min |

## How to test the app right now

1. Open <https://app-governance-prod.azurewebsites.net>
2. Sign in with your HTT Entra ID credentials
3. You should see the main dashboard with all 5 brand tenants
4. Navigate to any brand tab -- data should be current (sync runs every 5 min)
5. Check `/health` -- should return `healthy / 2.5.0 / production`
6. Check `/healthz/data` -- should return `any_stale=false`

## Key URLs

| What | URL |
|------|-----|
| Production | https://app-governance-prod.azurewebsites.net |
| Staging | https://app-governance-staging-xnczpwyv.azurewebsites.net |
| Health | https://app-governance-prod.azurewebsites.net/health |
| Data freshness | https://app-governance-prod.azurewebsites.net/healthz/data |
| Scheduler status | https://app-governance-prod.azurewebsites.net/healthz/scheduler |
| Metrics | https://app-governance-prod.azurewebsites.net/metrics |
| GitHub Pages | https://htt-brands.github.io/control-tower/ |

## Technical notes

- App Service: AlwaysOn=true, TLS 1.2 minimum, FTPS only
- Container: `ghcr.io/htt-brands/control-tower@sha256:16f0c507...`, non-root `appuser`
- SQL: Basic tier (5 DTU), 7-day PITR, weekly BACPAC backup
- Key Vault: purge-protected, 28 secrets, managed identity access
- Auth: Entra ID OIDC, 5-role RBAC (admin, tenant_admin, manager, analyst, viewer)
- Scheduler: APScheduler in-process, heartbeat monitored, 5-min sync cycle
- SLSA: L3 provenance + SBOM attestation on every production deploy

## Residual risks (documented, not blocking)

1. Single-region Azure (West US 2) -- by design for internal dashboard
2. Azure SQL Basic tier -- 7-day PITR only, no LTR
3. No load testing beyond k6 smoke -- unknown behavior at 100+ concurrent users
4. DMARC/DKIM sync domains show NONE for all tenants -- DomainIQ decommissioned
5. Riverside device_compliance not deployed for 4/5 tenants

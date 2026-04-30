# HTT Control Tower — End-to-End Infrastructure Overview

**Document Date:** April 30, 2026 (post-prod-deploy refresh)
**System Version:** 2.5.0 — package version per `pyproject.toml`; internal v2.5.1 release-gate verdict is `PASS-pending-9lfn` as of 2026-04-30 22:54 UTC.
**HEAD on `main`:** [`6c75220`](https://github.com/HTT-BRANDS/control-tower/commit/6c75220).
**Production live image:** `ghcr.io/htt-brands/control-tower@sha256:f762c98a03c40f2d6cc77912d8bd13a82ed64e41969a9545094da262c8ff21ef` — deployed by run [`25193020385`](https://github.com/HTT-BRANDS/control-tower/actions/runs/25193020385) at 2026-04-30 22:54 UTC.
**Status:** ✅ Operational. Production `/health` 200 (`healthy / 2.5.0 / production`). Staging `/health` 200 after warm-up. Auto-rollback field-tested via bd `1vui` cycle. See [`STATUS.md`](./STATUS.md) for the single-glance live state, [`CURRENT_STATE_ASSESSMENT.md`](./CURRENT_STATE_ASSESSMENT.md) for the dashboard, and [`SESSION_HANDOFF.md`](./SESSION_HANDOFF.md) for in-flight session detail.
**Owner:** Tyler Granlund — IT Support & Systems Engineer, HTT Brands

> **Honesty banner (added 2026-04-28):** Earlier revisions of this doc claimed
> "all pipelines green" while staging was failing on every push. That was
> wrong then and dangerous now. This file is **infrastructure topology**
> (which is reasonably stable), not **operational state** (which lives in
> `CURRENT_STATE_ASSESSMENT.md` and `bd ready`).

---

## 1. Platform Purpose

HTT Control Tower is an internal multi-tenant governance application serving 5 brands/tenants across the HTT Brands franchise portfolio. It provides governance reporting, Riverside compliance visibility (MFA status, gaps, summary), cross-tenant policy oversight, and the operational substrate for cost, identity, compliance, resources, lifecycle, and BI/evidence workflows. Existing Azure resource names still use `governance`; do not rename them without a dedicated infrastructure migration.

### Tenants

| Code | Name                    | OIDC | Priority |
|------|-------------------------|------|----------|
| HTT  | Head-To-Toe             | Yes  | 1        |
| BCC  | Bishops                 | Yes  | 2        |
| FN   | Frenchies               | Yes  | 3        |
| TLL  | Lash Lounge             | Yes  | 4        |
| DCE  | Delta Crown Extensions  | Yes  | 5        |

---

## 2. Application Layer

- **Language/Framework:** Python 3.11, FastAPI
- **Entrypoint:** `app/main.py`
- **Code structure (`app/`):** `api/`, `core/`, `models/`, `schemas/`, `services/`, `integrations/`, `alerts/`, `preflight/`, `static/`, `templates/`
- **Dependency mgmt:** `pyproject.toml` + `uv.lock` (uv-managed), `requirements.txt` / `requirements-dev.txt` mirrored for CI
- **DB migrations:** Alembic (`alembic/`, `alembic.ini`)
- **Container:** `Dockerfile` (labels = 2.2.0), `docker-compose.yml` (dev) and `docker-compose.prod.yml`

---

## 3. Azure Infrastructure

**Subscription:** HTT-CORE — `32a28177-6fb2-4668-a528-6d6cafb9665e`

### 3.1 Production — `rg-governance-production` (East US)

| Resource            | Name                                                     | SKU / Notes                 |
|---------------------|----------------------------------------------------------|-----------------------------|
| App Service Plan    | `asp-governance-production`                              | B1 Basic (Linux)            |
| Web App             | `app-governance-prod`                                    | Docker, HTTPS only          |
| SQL Server          | `sql-gov-prod-mylxq53d`                                  | Standard (logical server)   |
| SQL Database        | `governance`                                             | **Basic** (5 DTU, 2 GB)     |
| Key Vault           | `kv-gov-prod`                                            | Standard, soft delete       |
| App Insights        | `governance-appinsights`                                 | Receiving telemetry         |
| Log Analytics       | `governance-logs`                                        | Per-GB (free tier)          |
| Container Registry  | `ghcr.io/htt-brands/control-tower` (GHCR)                | Primary image source        |
| Alert Rules         | 7 metric alerts + 2 availability tests                   | ~$0.60/mo                   |

> **Note:** Legacy `acrgovprod` ACR was deleted on Apr 16, 2026 — prod pulls from GHCR exclusively.

**Production URL:** https://app-governance-prod.azurewebsites.net

### 3.2 Staging — `rg-governance-staging` (West US 2)

| Resource            | Name                                    | SKU / Notes           |
|---------------------|-----------------------------------------|-----------------------|
| App Service Plan    | `asp-governance-staging-xnczpwyvwsaba`  | B1 Basic              |
| Web App             | `app-governance-staging-xnczpwyv`       | Running               |
| SQL Server          | `sql-governance-staging-77zfjyem`       | Standard              |
| SQL Database        | `governance`                            | **Free tier** (32 MB) |
| Key Vault           | `kv-gov-staging-xnczpwyv`               | Standard              |
| Storage Account     | `stgovstagingxnczpwyv`                  | StorageV2, **LRS**    |
| Log Analytics       | `log-governance-staging-xnczpwyvwsaba`  | PerGB2018, 30-day     |
| App Insights        | `ai-governance-staging-xnczpwyvwsaba`   | Web type              |

> **Note:** `sqlbackup1774966098` storage account + stale test backup deleted Apr 16, 2026.
> Staging pulls containers directly from GHCR (no ACR needed).

**Staging URL:** https://app-governance-staging-xnczpwyv.azurewebsites.net

### 3.3 Dev — `rg-governance-dev` (West US 2)

| Resource            | Name                       | SKU / Notes          |
|---------------------|----------------------------|----------------------|
| App Service Plan    | `asp-governance-dev-001`   | B1 Basic             |
| Web App             | `app-governance-dev-001`   | Pulls from dev ACR   |
| SQL Server          | `sql-governance-dev-76481` | Standard (logical)   |
| SQL Database        | `governance`               | **Basic** (5 DTU)    |
| Container Registry  | `acrgovernancedev`         | Basic (10 GB limit)  |
| Storage Account     | `stgovdev001`              | StorageV2, **LRS**   |
| Key Vault           | `kv-gov-dev-001`           | Standard             |
| Log Analytics       | `log-governance-dev-001`   | Per-GB (free tier)   |
| App Insights        | `ai-governance-dev-001`    | Per-GB (free tier)   |

### 3.4 Monthly Cost (post-optimization, April 16, 2026)

| Environment | Monthly |
|-------------|---------|
| Dev         | ~$22.67 |
| Staging     | ~$12.68 |
| Production  | ~$18.05 |
| **Total**   | **~$53.40** / ~$641/yr |

### Optimization History

| Date       | Action                                              | Savings  |
|------------|-----------------------------------------------------|----------|
| ~March     | Initial rightsizing (B2→B1, S2→S0, orphan cleanup)  | ~$225/mo |
| 2026-04-16 | Dev SQL S0→Basic                                    | $9.73/mo |
| 2026-04-16 | Prod SQL S0→Basic                                   | $9.73/mo |
| 2026-04-16 | Deleted unused `acrgovprod`                         | $5.00/mo |
| 2026-04-16 | Deleted orphan PIP `pip-vpn-core`                   | $3.65/mo |
| 2026-04-16 | Storage GRS→LRS on empty accounts                   | $0.50/mo |

**Governance-only spend reduced from ~$298/mo → ~$53/mo — roughly 82% reduction.**

See `SESSION_HANDOFF.md` for broader cross-project Azure optimization work done on
the same date (~$466/mo total savings across all HTT-BRANDS projects).

---

## 4. Infrastructure as Code

All IaC lives in `infrastructure/`:

- `main.bicep`, `main.json` — root template
- `deploy-governance-infrastructure.bicep` — full resource group deployment
- `github-oidc.bicep` — federated identity setup
- `parameters.{dev,staging,production}.json` — env parameter files
- `modules/`, `monitoring/`, `policies/`, `lighthouse/` — reusable modules and governance policies
- `deploy.sh`, `setup-oidc.sh` — bootstrap scripts
- `COST_OPTIMIZATION.md`, `MONITORING_SETUP_PHASE2.md`, `MONITORING_SETUP_PHASE3_COMPLETE.md` — runbooks

---

## 5. CI/CD — GitHub Actions

Repo target after rename: https://github.com/HTT-BRANDS/control-tower

Current deployed image/resource references may still use `azure-governance-platform` until each environment completes its next successful deploy from `ghcr.io/htt-brands/control-tower`.
Workflows (`.github/workflows/`):

| Workflow                             | Trigger                  | Purpose                                          |
|--------------------------------------|--------------------------|--------------------------------------------------|
| `ci.yml`                             | Push / PR                | Lint, test, security scan                        |
| `deploy-staging.yml`                 | Push to `main`           | 5 jobs: QA gate, security, build, deploy, validate |
| `deploy-production.yml`              | Manual dispatch          | 6 jobs incl. smoke test + Teams notify           |
| `container-registry-migration.yml`   | Manual                   | ACR ↔ GHCR migration tooling                     |
| `dependency-update.yml`              | Scheduled                | Dependabot-style dependency refresh              |
| `security-scan.yml`                  | Scheduled / push         | Trivy + CodeQL                                   |
| `backup.yml`                         | Scheduled                | DB / config backup                               |
| `weekly-ops.yml`                     | Scheduled (weekly)       | Ops health checks                                |
| `accessibility.yml`                  | Push                     | Lighthouse / a11y validation                     |
| `pages.yml`, `gh-pages-tests.yml`    | Push (docs)              | GitHub Pages build + tests                       |

### 5.1 Pipeline Auth & Secrets

All pipelines use **OIDC Workload Identity Federation** — zero stored client secrets; UAMI-based across all 5 tenants.

| Secret                     | Purpose                                |
|----------------------------|----------------------------------------|
| `AZURE_CLIENT_ID`          | OIDC federated credential              |
| `AZURE_TENANT_ID`          | HTT-CORE tenant                        |
| `AZURE_SUBSCRIPTION_ID`    | Target subscription                    |
| `GHCR_PAT`                 | GHCR pull auth (set Apr 10, 2026)      |
| `PRODUCTION_TEAMS_WEBHOOK` | Deploy notifications to Teams          |

---

## 6. Security Posture

- OIDC federation across all 5 tenants — no stored client secrets
- HSTS tuned per environment: 300s dev / 86400s staging / 31536000s prod
- 12 security headers on every response
- `/docs` gated behind auth in production; public in staging/dev
- `cryptography` patched to 46.0.7 (CVE-2026-39892)
- Pre-commit hooks: ruff sort/lint/format, detect-secrets
- Trivy image scanning in CI, `.trivyignore` maintained
- `.secrets.baseline` committed for detect-secrets

---

## 7. Observability

- **Application Insights** in both prod and staging (telemetry, availability, dependency tracking)
- **Log Analytics** workspace in staging (30-day retention)
- **Smoke tests** environment-aware (expect 401 in prod, 200 in staging)
- Deploy notifications routed to Microsoft Teams via webhook
- Monitoring setup documented in `infrastructure/MONITORING_SETUP_PHASE2.md` and `MONITORING_SETUP_PHASE3_COMPLETE.md`
- Per-tenant per-domain sync freshness exposed at `/api/v1/health/data` (see §10)

---

## 8. Quality Gates

| Metric              | Value          |
|---------------------|----------------|
| Test files          | 245                  |
| Test count          | 4,192 (pytest --collect-only, 2026-04-28) |
| Test pass rate      | 100% on green CI runs; staging suite has cold-start flakes (bd `mvxt`) |
| Ruff lint errors    | 0                    |
| Format violations   | 0                    |
| Roadmap phases      | 19 historical (legacy WIGGUM_ROADMAP) |
| Roadmap tasks       | 328 historical complete; current backlog tracked in `bd` not in roadmap doc |

---

## 9. Documentation Surface

- **GitHub Pages site:** https://htt-brands.github.io/control-tower/
- **Key docs in repo:** `ARCHITECTURE.md`, `CURRENT_STATE_ASSESSMENT.md`, `WIGGUM_ROADMAP.md`, `TRACEABILITY_MATRIX.md`, `SECURITY_IMPLEMENTATION.md`, `CHANGELOG.md`, `REQUIREMENTS.md`, `AZURE_DEVOPS_DEPLOYMENT_GUIDE.md`, `STAGING_DEPLOYMENT.md`, `DEPENDENCY_MANAGEMENT.md`

---

## 10. Health & Sync Freshness Endpoints (added 2026-04-17)

`/api/v1/health` returns the basic up/down + dependency check.

`/api/v1/health/data` returns **per-tenant per-domain freshness** for every
sync target the scheduler maintains. As of bd-c56t/dais it monitors **10
domains** across three timestamp conventions:

| Domain | Source model | Timestamp column |
|---|---|---|
| `resources` | `Resource` | `synced_at` |
| `costs` | `CostSnapshot` | `synced_at` |
| `compliance` | `ComplianceSnapshot` | `synced_at` |
| `identity` | `IdentitySnapshot` | `synced_at` |
| `dmarc` | `DMARCRecord` | `synced_at` |
| `dkim` | `DKIMRecord` | `synced_at` |
| `riverside_mfa` | `RiversideMFA` | `created_at` |
| `riverside_compliance` | `RiversideCompliance` | `updated_at` |
| `riverside_device_compliance` | `RiversideDeviceCompliance` | `snapshot_date` |
| `riverside_threat_data` | `RiversideThreatData` | `snapshot_date` |

Stale threshold: `settings.sync_stale_threshold_hours` (single global value,
applies to every domain). Each domain query is isolated — one domain raising
**does not** 500 the endpoint, that's the bd-a1sb regression guard.

The endpoint self-describes its monitored set via the `domains_covered` field
in the response body, so on-call tooling never has to hard-code the list.

Adding a domain: edit the `domains` list in `app/api/routes/health.py` and
add a corresponding test in `tests/unit/test_routes_health_data.py`. The
`(name, Model, ts_col)` tuple structure makes this a one-line change per
domain.

---

## 11. Known Follow-ups & Active Blockers

### Active P1 Blocker Chain (in_progress as of 2026-04-28)

| bd ID | Title | Status |
|---|---|---|
| `g1cc` | ci/release: deterministic deploy-production attestation verification | in_progress |
| `918b` | bug: persistent prod per-tenant Key Vault fallback failures | in_progress (gated on prod fresh image) |
| `0gz3` | task: post-deploy verify sync recovery + alert burn-down | in_progress (gated on `918b`) |
| `0nup` | release: assemble production-readiness evidence bundle | open (gated on full chain) |
| `aiob` | meta(ci): no frontend smoke / visual-regression in CI | in_progress |

### Active P2 Operational Issues

| bd ID | Title | Notes |
|---|---|---|
| `mvxt` | ops(staging): validation suite cold-start timeouts | Compensating warmup in commit `68c0baa`; monitoring after 2026-04-28 first green |
| `fifh` | ops(ci): Database Backup workflow fails on broken `mda590/teams-notify` action | Filed 2026-04-28 |
| `q8lt` | ops(ci): Bicep Drift Detection what-if scope mismatch | Filed 2026-04-28; all 3 envs failing |
| `213e` | ops: name a second rollback human before 2026-06-22 waiver expiry | Waiver-clock |

### Lower-Priority Follow-ups

| Item                                     | Notes                                                     |
|------------------------------------------|-----------------------------------------------------------|
| Make GHCR package public                 | Requires org admin via GitHub UI (Package Settings)       |
| Node.js 20 → 24 in GitHub Actions        | Forced migration by June 2026                             |
| CodeQL v3 → v4                           | Upgrade before December 2026                              |
| Migrate dev app ACR → GHCR + delete ACR  | bd issue `gz6i` — saves $5/mo, needs GHCR PAT             |
| Azure Monitor alert: stale sync data     | bd issue forthcoming — wire `/health/data` `any_stale=true` → governance-alerts |
| Reconcile `INFRASTRUCTURE_INVENTORY.md`  | Mar 27 doc needs GHCR + HTT-CORE + Basic SQL refresh      |
| `xkgp` Tech debt: replace `datetime.utcnow()` | Deprecation warnings across tests/fixtures           |
| Refactor 10 files >900 LOC               | See `CONTROL_TOWER_MASTERMIND_PLAN_2026.md` Phase 1       |

---

## 12. End-to-End Request Flow (Summary)

1. User hits `https://app-governance-prod.azurewebsites.net`
2. Azure Front Door / App Service terminates TLS (HTTPS only, HSTS enforced)
3. Container pulled from `ghcr.io/htt-brands/control-tower:2.2.0` runs on App Service (B1 Linux)
4. FastAPI app authenticates via OIDC against the appropriate tenant UAMI
5. Secrets resolved from Key Vault (`kv-gov-prod`) via managed identity references
6. Data layer reads/writes against Azure SQL `governance` (S0, 250 GB)
7. Telemetry emitted to Application Insights (`governance-appinsights`)
8. Deploys triggered by push to `main` → staging auto-deploys; production deploys via manual workflow dispatch with approvals
9. Teams webhook posts deploy outcome to the production channel

---

**Prepared for:** Tyler Granlund — IT Support & Systems Engineer, HTT Brands
**Source of truth:** `CURRENT_STATE_ASSESSMENT.md` (live blocker dashboard), `SESSION_HANDOFF.md` (in-flight session detail), `bd ready` (live work backlog), `INFRASTRUCTURE_INVENTORY.md` (stable topology — last refreshed Mar 27), `ARCHITECTURE.md` (system design), `CONTROL_TOWER_MASTERMIND_PLAN_2026.md` (forward strategic plan), Azure CLI live queries.

*Last fact-checked: 2026-04-28 by code-puppy-ab8d6a during diligence pass.*

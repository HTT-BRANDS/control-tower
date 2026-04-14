# Azure Governance Platform — End-to-End Infrastructure Overview

**Document Date:** April 14, 2026
**System Version:** 2.2.0
**Status:** Operational (Production + Staging healthy, all pipelines green)
**Owner:** Tyler Granlund — IT Support & Systems Engineer, HTT Brands

---

## 1. Platform Purpose

A multi-tenant Azure governance application serving 5 brands/tenants across the HTT Brands franchise portfolio. Provides governance reporting, Riverside compliance visibility (MFA status, gaps, summary), and cross-tenant policy oversight.

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
| SQL Server          | `sql-gov-prod-mylxq53d`                                  | Standard                    |
| SQL Database        | `governance`                                             | S0, 250 GB, Online          |
| Key Vault           | `kv-gov-prod`                                            | Standard, soft delete       |
| App Insights        | `governance-appinsights`                                 | Receiving telemetry         |
| Container Registry  | `ghcr.io/htt-brands/azure-governance-platform` (GHCR)    | Primary image source        |
| Legacy ACR          | `acrgovprod` (per older inventory; superseded by GHCR)   | Reconcile / retire          |

**Production URL:** https://app-governance-prod.azurewebsites.net

### 3.2 Staging — `rg-governance-staging` (West US 2)

| Resource            | Name                                    | SKU / Notes           |
|---------------------|-----------------------------------------|-----------------------|
| App Service Plan    | `asp-governance-staging-xnczpwyvwsaba`  | B1 Basic              |
| Web App             | `app-governance-staging-xnczpwyv`       | Running               |
| SQL Server          | `sql-governance-staging-77zfjyem`       | Standard              |
| SQL Database        | `governance`                            | Online                |
| Key Vault           | `kv-gov-staging-77zfjyem`               | Standard              |
| Storage Account     | `stgovstagingxnczpwyv`                  | StorageV2, GRS        |
| Log Analytics       | `log-governance-staging-xnczpwyvwsaba`  | PerGB2018, 30-day     |
| App Insights        | `ai-governance-staging-xnczpwyvwsaba`   | Web type              |
| ACR                 | `acrgovstaging19859`                    | Anonymous pull        |

**Staging URL:** https://app-governance-staging-xnczpwyv.azurewebsites.net

### 3.3 Monthly Cost (post-optimization)

| Environment | Monthly  |
|-------------|----------|
| Production  | ~$35.17  |
| Staging     | ~$38.17  |
| **Total**   | **~$73.34** |

Rightsizing (B2→B1, S2→S0, orphan cleanup) reduced spend from ~$298/mo — **~75% reduction**, ~$225/mo saved.

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

Repo: https://github.com/HTT-BRANDS/azure-governance-platform
Workflows (`.github/workflows/`):

| Workflow                             | Trigger                  | Purpose                                          |
|--------------------------------------|--------------------------|--------------------------------------------------|
| `ci.yml`                             | Push / PR                | Lint, test, security scan                        |
| `deploy-staging.yml`                 | Push to `main`           | 5 jobs: QA gate, security, build, deploy, validate |
| `deploy-production.yml`              | Manual dispatch          | 6 jobs incl. smoke test + Teams notify           |
| `blue-green-deploy.yml`              | Manual                   | Zero-downtime swap strategy                      |
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

---

## 8. Quality Gates

| Metric              | Value          |
|---------------------|----------------|
| Test files          | 223            |
| Test count          | 3,800          |
| Test pass rate      | 100% (0 fails) |
| Ruff lint errors    | 0              |
| Format violations   | 0              |
| Roadmap phases      | 19 complete    |
| Roadmap tasks       | 328 complete   |

---

## 9. Documentation Surface

- **GitHub Pages site:** https://htt-brands.github.io/azure-governance-platform/
- **Key docs in repo:** `ARCHITECTURE.md`, `CURRENT_STATE_ASSESSMENT.md`, `WIGGUM_ROADMAP.md`, `TRACEABILITY_MATRIX.md`, `SECURITY_IMPLEMENTATION.md`, `CHANGELOG.md`, `REQUIREMENTS.md`, `AZURE_DEVOPS_DEPLOYMENT_GUIDE.md`, `STAGING_DEPLOYMENT.md`, `DEPENDENCY_MANAGEMENT.md`

---

## 10. Known Follow-ups (Low Priority)

| Item                                     | Notes                                                     |
|------------------------------------------|-----------------------------------------------------------|
| Make GHCR package public                 | Requires org admin via GitHub UI (Package Settings)       |
| Node.js 20 → 24 in GitHub Actions        | Forced migration by June 2026                             |
| CodeQL v3 → v4                           | Upgrade before December 2026                              |
| Reconcile `INFRASTRUCTURE_INVENTORY.md`  | Mar 27 doc still references `acrgovprod` and old tenant label; update to reflect GHCR + HTT-CORE |

---

## 11. End-to-End Request Flow (Summary)

1. User hits `https://app-governance-prod.azurewebsites.net`
2. Azure Front Door / App Service terminates TLS (HTTPS only, HSTS enforced)
3. Container pulled from `ghcr.io/htt-brands/azure-governance-platform:2.2.0` runs on App Service (B1 Linux)
4. FastAPI app authenticates via OIDC against the appropriate tenant UAMI
5. Secrets resolved from Key Vault (`kv-gov-prod`) via managed identity references
6. Data layer reads/writes against Azure SQL `governance` (S0, 250 GB)
7. Telemetry emitted to Application Insights (`governance-appinsights`)
8. Deploys triggered by push to `main` → staging auto-deploys; production deploys via manual workflow dispatch with approvals
9. Teams webhook posts deploy outcome to the production channel

---

**Prepared for:** Tyler Granlund — IT Support & Systems Engineer, HTT Brands
**Source of truth:** `CURRENT_STATE_ASSESSMENT.md`, `SESSION_HANDOFF.md`, `INFRASTRUCTURE_INVENTORY.md`, `ARCHITECTURE.md`, workspace file tree (as of April 14, 2026)

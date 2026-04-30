# HTT Control Tower

[![Version](https://img.shields.io/badge/version-2.5.0-blue.svg)](./CHANGELOG.md)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

HTT Control Tower is an internal multi-brand governance hub for cost, identity, compliance, resources, lifecycle, and evidence workflows across HTT's brand portfolio. It is Azure/M365-first today, but the domain model is intentionally compatible with future Google Cloud, AWS, Pax8, SaaS, and BI-provider adapters. Built with Python, FastAPI, HTMX, and Tailwind CSS.

> **Naming note:** Control Tower is HTT's internal name for this platform. It is unrelated to AWS Control Tower. Do not use this name for external commercialization without a separate naming/legal review.

> **Current release truth:** the package version in `pyproject.toml` is **2.5.0**. Production-readiness work toward the next strict release-gate pass is tracked in `docs/plans/production-readiness-and-release-gate-roadmap-2026-04-24.md` and the linked bd issues.

## Release status snapshot

- **Package version:** `2.5.0`
- **Deploy workflow:** `.github/workflows/deploy-production.yml`
- **Current production app URL:** `https://app-governance-prod.azurewebsites.net`
- **Current production resource group:** `rg-governance-production`
- **Current rollback/waiver source of truth:** `docs/release-gate/rollback-current-state.yaml`
- **Change history:** `CHANGELOG.md`

## Recent release work highlights

Recent release-hardening work completed in this repo includes:

- deterministic deploy-time attestation verification via GitHub Attestations API
- browser smoke promoted from advisory soak to a required merge gate
- machine-verifiable rollback/waiver state aligned to the production workflow
- environment-delta validation for release evidence hygiene
- scheduled Bicep drift detection and post-deploy verification tooling

For historical release dossiers and arbiter artifacts, see `docs/release-gate/`.

### 🔐 Security & Authentication
- Environment-specific SecurityHeadersConfig (dev/staging/prod HSTS presets)
- 12 security headers on every response with 0.25ms overhead
- User-Assigned Managed Identity (UAMI) zero-secrets architecture
- PKCE OAuth, JWT algorithm confusion prevention, refresh token blacklisting
- CSP nonce injection, GPC middleware for CCPA/CPRA compliance

### ♿ Accessibility
- WCAG 2.2 AA compliant — skip nav, focus-visible, 44px touch targets
- aria-hidden=true on decorative SVGs across 28 templates
- Enhanced skip link implementation with visible-on-focus
- CSS focus indicator conflict resolution
- axe-core automated testing integration

### 🛠️ Developer Experience
- Interactive OpenAPI examples with 6 JSON sample payloads
- Security headers middleware benchmark: 0.25ms overhead, 1,316 req/s
- 223 test files with 75,796 lines of test code
- Pre-commit hooks: ruff import sorting, linting, formatting, secret detection
- Full Locust load test suite for performance validation

See [CHANGELOG.md](./CHANGELOG.md) for version history.

---

## Features

- **🔐 Zero-Secrets Authentication** — UAMI-based auth with zero client secrets
- **Cost Management**: Cross-tenant cost aggregation, anomaly detection, trends, forecasts, idle resource identification
- **Compliance Monitoring**: Policy compliance tracking, secure score aggregation, drift detection, non-compliant policy reporting
- **Resource Management**: Cross-tenant inventory, tagging compliance, orphaned resource detection, idle resources
- **Identity Governance**: Privileged access reporting, guest user management, MFA compliance, stale account detection
- **Sync Management**: Automated background sync with monitoring, alerting, and manual sync capabilities
- **Preflight Checks**: Validate Azure connectivity and permissions before operations
- **Riverside Compliance**: Specialized compliance tracking for Riverside Company deadline (July 8, 2026)
- **Bulk Operations**: Apply tags, acknowledge anomalies, review resources in bulk
- **Data Exports**: CSV exports for costs, resources, and compliance data
- **Performance Monitoring**: Cache metrics, query performance, sync job analytics
- **Azure Lighthouse**: Cross-tenant delegation with self-service onboarding
- **Data Backfill**: Resumable day-by-day with parallel multi-tenant processing
- **Multi-Brand Design System**: Token-based theming for 5 brands with WCAG AA compliance, server-side CSS generation, and 47+ CSS custom properties per brand
- **WCAG 2.2 Accessibility**: Skip nav, focus-visible, 44px touch targets, axe-core automated testing
- **Dark Mode**: System preference detection with manual toggle
- **Enhanced App Insights**: Custom telemetry, dependency tracking, distributed tracing
- **Data Retention**: Automated time-series cleanup with configurable periods
- **Audit Log Aggregation**: Tamper-evident audit trail with full filtering, pagination, and summary endpoints
- **Quota Utilization Monitoring**: Real-time Azure compute/network quota tracking with ok/warning/critical thresholds
- **Resource Lifecycle Tracking**: Change detection and event history for all managed resources
- **Custom Compliance Rules**: JSON Schema–based rule engine with tenant isolation, SSRF protection, and full CRUD API
- **Circuit Breakers**: Per-service circuit breakers for Azure API resilience
- **HTTP Timeouts**: Configurable timeouts for all Azure SDK calls
- **GPC Compliance**: Global Privacy Control middleware for CCPA/CPRA compliance

## Quick Start

### Prerequisites

- Python 3.11+
- Azure subscriptions with appropriate permissions
- App registrations in each tenant (or Azure Lighthouse delegation)

### Installation

```bash
# Clone the repository
# Current repo URL until bd 0dsr completes the GitHub repo rename cutover
git clone https://github.com/htt-brands/azure-governance-platform.git
cd azure-governance-platform

# Create virtual environment
uv venv
source .venv/bin/activate  # or `.venv\\Scripts\\activate` on Windows

# Install dependencies
uv pip install -e ".[dev]"

# Copy and configure environment
cp .env.example .env
# Edit .env with your Azure credentials

# Initialize database
python -c "from app.core.database import init_db; init_db()"

# Run the application
uvicorn app.main:app --reload
```

### Quick Verification

```bash
# Health check
curl http://localhost:8000/health

# View dashboard
open http://localhost:8000

# API documentation
open http://localhost:8000/docs
```

### Azure Setup

#### Option A: Azure Lighthouse (Recommended)

1. Deploy Lighthouse delegation template to each managed tenant
2. Configure a single app registration in the managing tenant
3. Set `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` in `.env`

#### Option B: Per-Tenant App Registrations

1. Create an app registration in each tenant
2. Grant required permissions (see docs/PERMISSIONS.md)
3. Store credentials in Azure Key Vault
4. Configure `KEY_VAULT_URL` in `.env`

## Live Environments

Only include values here that are expected to remain current. Historical version claims and cost snapshots drift too fast to trust.

| Environment | URL | Notes |
|-------------|-----|-------|
| **Production** | https://app-governance-prod.azurewebsites.net | Canonical production endpoint |
| **Staging** | see deployment/env docs | URL may change; treat workflow/env configuration as source of truth |
| **Dev** | environment-specific | Not a release-gate truth source |

### Production environment references
| Resource | Name |
|----------|------|
| Resource Group | `rg-governance-production` |
| App Service | `app-governance-prod` |
| Deploy workflow | `.github/workflows/deploy-production.yml` |
| Rollback state artifact | `docs/release-gate/rollback-current-state.yaml` |

For cost snapshots, migration history, and environment-specific operational nuance, prefer the dedicated docs under `docs/` rather than this top-level README.

## Documentation

| Document | Description |
|----------|-------------|
| [CHANGELOG.md](./CHANGELOG.md) | Release history and current package version |
| [Release-gate docs](./docs/release-gate/) | Arbiter submissions, RTMs, rollback artifacts, and verdict history |
| [Production readiness roadmap](./docs/plans/production-readiness-and-release-gate-roadmap-2026-04-24.md) | Current release-readiness workstreams and blockers |
| [API Reference](./docs/API.md) | Complete REST API documentation |
| [Deployment Guide](./docs/DEPLOYMENT.md) | Deployment options and procedures |
| [Disaster Recovery Runbook](./docs/runbooks/disaster-recovery.md) | Current operational recovery guidance |
| [Developer Guide](./docs/DEVELOPMENT.md) | Setup and contribution guidelines |
| [Implementation Guide](./docs/IMPLEMENTATION_GUIDE.md) | Detailed setup instructions |
| [Common Pitfalls](./docs/COMMON_PITFALLS.md) | Troubleshooting guide |
| [Design System](./docs/design-system.md) | Multi-brand theming architecture |

### Interactive API Documentation

Once running, access the interactive API docs:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Project Structure

```
control-tower/
├── app/
│   ├── api/
│   │   ├── routes/          # API endpoints
│   │   │   ├── riverside.py # Riverside compliance endpoints
│   │   └── services/        # Business logic
│   │       └── riverside_svc.py
│   ├── core/                # Config, DB, scheduler, design system
│   ├── models/              # SQLAlchemy models
│   │   └── riverside.py     # Riverside models
│   ├── schemas/             # Pydantic schemas
│   ├── templates/           # Jinja2 templates
│   │   └── pages/
│   │       └── riverside.py # Riverside dashboard
│   ├── static/              # CSS, JS assets
│   ├── services/            # Domain services
│   │   ├── lighthouse_client.py
│   │   ├── backfill_service.py
│   │   ├── parallel_processor.py
│   │   ├── retention_service.py
│   │   ├── riverside_sync.py
│   │   ├── teams_webhook.py
│   │   ├── email_service.py
│   │   └── theme_service.py
│   ├── preflight/           # Pre-operation validation
│   └── alerts/              # Alerting subsystem
├── docs/                    # Documentation
│   ├── RIVERSIDE_INTEGRATION.md
│   ├── RIVERSIDE_EXECUTIVE_SUMMARY.md
│   └── RIVERSIDE_API_GUIDE.md
├── tests/                   # Test suite
├── scripts/                 # Utility scripts
└── data/                    # SQLite database (gitignored)
```

## Configuration

| Variable | Description | Default |
|----------|-------------|--------|
| `AZURE_TENANT_ID` | Managing tenant ID | Required |
| `AZURE_CLIENT_ID` | App registration client ID | Required |
| `AZURE_CLIENT_SECRET` | Client secret | Required |
| `DATABASE_URL` | SQLite connection string | `sqlite:///./data/governance.db` |
| `COST_SYNC_INTERVAL_HOURS` | Cost sync frequency | `24` |
| `COMPLIANCE_SYNC_INTERVAL_HOURS` | Compliance sync frequency | `4` |

### Riverside-Specific Configuration

| Variable | Description | Default |
|----------|-------------|--------|
| `RIVERSIDE_COMPLIANCE_ENABLED` | Enable Riverside compliance features | `false` |
| `RIVERSIDE_DEADLINE_DATE` | Compliance deadline | `2026-07-08` |
| `RIVERSIDE_MFA_TARGET` | Target MFA coverage percentage | `100` |
| `RIVERSIDE_MATURITY_TARGET` | Target maturity score | `3.0` |
| `RIVERSIDE_SYNC_INTERVAL_HOURS` | Riverside data sync frequency | `4` |

See `.env.example` for all configuration options.

## Development

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Run linting
ruff check .

# Run type checking
mypy app/

# Run tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html
```

## Deployment

### GitHub Container Registry + Azure App Service (v1.9.0 - Recommended)

```bash
# Deploy infrastructure
cd infrastructure
./deploy.sh production eastus

# Build and push container image to GHCR
docker build -t ghcr.io/htt-brands/control-tower:v1.9.0 .
docker push ghcr.io/htt-brands/control-tower:v1.9.0

# Configure App Service to use GHCR
az webapp config container set \
  --name app-governance-prod \
  --resource-group rg-governance-production \
  --docker-custom-options-name myregistrysecret \
  --docker-registry-server-url https://ghcr.io \
  --docker-registry-server-user USERNAME \
  --docker-registry-server-password PAT

# Restart app service to pull new image
az webapp restart --name app-governance-prod -g rg-governance-production
```

**Cost:** ~$30/month (App Service B1 + Azure SQL S0 + Key Vault + App Insights)

**Savings vs ACR:** ~$150/month (GHCR is free for public repos)

See [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md) and [docs/runbooks/acr-to-ghcr-migration.md](./docs/runbooks/acr-to-ghcr-migration.md) for detailed instructions.

### Docker (Local Development)

```bash
# Quick start with Makefile
make install     # Install dependencies
make test        # Run tests
make lint        # Run linting
make run         # Start development server

# Or manual approach
docker build -t control-tower .
docker run -p 8000:8000 --env-file .env control-tower
```

## 💰 Cost Optimization Achieved (v1.9.0)

### Original vs Optimized Infrastructure Costs

| Environment | Original | Optimized | Savings |
|-------------|----------|-----------|---------|
| **Production** | ~$133/mo | ~$30/mo | **$103/mo** |
| **Staging** | ~$160/mo | ~$15/mo | **$145/mo** ✅ Active |
| **Total** | ~$298/mo | ~$73/mo | **$225/mo (75%)** |

### Cost Optimization Breakdown

| Change | Monthly Savings | Status |
|--------|-----------------|--------|
| App Service B2→B1 (Prod) | $60 | ✅ Active |
| Azure SQL S2→S0 (Prod) | $15 | ✅ Active |
| Azure SQL S2→Free Tier (Staging) | $30 | ✅ **$0/mo** |
| ACR→GHCR Migration | ~$150 | ✅ Staging active, Prod ready |
| Orphaned Resource Cleanup | $85 | ✅ Complete |

**Active Monthly Savings: $165**  
**Potential Additional Savings: $180/month** (Production SQL Free Tier + GHCR)

See [infrastructure/COST_OPTIMIZATION.md](./infrastructure/COST_OPTIMIZATION.md) for full details.

### Dev Environment Cost Estimate

| Resource | Monthly Cost |
|----------|-------------|
| App Service Plan (B1) | ~$13 |
| Key Vault | ~$1 |
| Storage Account | ~$5 |
| Application Insights | ~$5 |
| Container Registry (GHCR) | **$0** |
| **Total Dev Environment** | **~$25-30** |

## Riverside Compliance Tracking

### Executive Overview

HTT Control Tower includes specialized compliance tracking for Riverside Company requirements.

#### Current State (tracked by platform — see /riverside dashboard for current metrics)

| Metric | Current | Target | Deadline |
|--------|---------|--------|----------|
| **Overall Maturity** | 2.4/5.0 | 3.0/5.0 | July 8, 2026 |
| **Compliance Deadline** | ~160 days | - | July 8, 2026 |
| **Financial Risk** | $4M | $0 | July 8, 2026 |
| **MFA Coverage** | Tracked in real-time via platform dashboard | 100% | 30 days |
| **Threat Beta Score** | 1.04 | <1.0 | Ongoing |

#### Tenants

| Tenant | Code | Type | MFA Coverage |
|--------|------|------|--------------|
| HTT | HTT | Riverside | Tracked in real-time via platform dashboard |
| BCC | BCC | Riverside | Tracked in real-time via platform dashboard |
| FN | FN | Riverside | Tracked in real-time via platform dashboard |
| TLL | TLL | Riverside | Tracked in real-time via platform dashboard |
| DCE | DCE | Standalone | N/A |

### Key Metrics Tracked

- **MFA Enrollment**: Per-tenant MFA coverage tracking with admin account focus
- **Domain Maturity Scores**: Identity & Access Management (IAM), Governance & Security (GS), Data Security (DS)
- **Requirement Compliance Status**: 72+ requirements across 8 categories
- **External Threat Monitoring**: Threat Beta score, vulnerability count
- **Timeline to Deadline**: Countdown with milestone tracking

### Quick Start for Compliance

```bash
# View compliance dashboard
http://localhost:8000/riverside

# Check MFA status
http://localhost:8000/api/v1/riverside/mfa-status

# View executive summary
http://localhost:8000/api/v1/riverside/summary

# View critical gaps
http://localhost:8000/api/v1/riverside/gaps

# View requirements
http://localhost:8000/api/v1/riverside/requirements

# View maturity scores
http://localhost:8000/api/v1/riverside/maturity-scores
```

### Critical Gaps Dashboard

> **Note:** The values below reflect the initial baseline assessment. See the live [`/riverside`](http://localhost:8000/riverside) dashboard for current real-time metrics.

| Requirement | Status | Current | Target | Deadline | Risk |
|-------------|--------|---------|--------|----------|------|
| IAM-12: Universal MFA | In Progress | 30% | 100% | Immediate | Critical ($4M) |
| GS-10: Dedicated Security Team | Not Started | 0 | 1 | 30 days | Critical |
| IAM-03: Privileged Access Management | Not Started | 0 | 100% | 60 days | High |
| IAM-08: Conditional Access Policy | In Progress | 40% | 100% | 60 days | High |
| DS-02: Data Classification | Not Started | 0 | Complete | 90 days | Medium |
| GS-05: Security Awareness Training | In Progress | 25% | 100% | 90 days | Medium |
| IAM-15: Service Account Management | Not Started | 0 | 100% | 120 days | Medium |
| DS-05: Encryption at Rest | Not Started | 0 | 100% | 120 days | Medium |

### Documentation

For comprehensive Riverside compliance documentation, see:

- [RIVERSIDE_INTEGRATION.md](./docs/RIVERSIDE_INTEGRATION.md) - Complete integration guide
- [RIVERSIDE_EXECUTIVE_SUMMARY.md](./docs/RIVERSIDE_EXECUTIVE_SUMMARY.md) - One-page executive summary
- [RIVERSIDE_API_GUIDE.md](./docs/RIVERSIDE_API_GUIDE.md) - API reference

## Roadmap

### ✅ Completed (v1.9.0 — "Zero Gravity")

**v1.9.0 Release — April 2026:**
- [x] **Zero-Secrets Authentication** — UAMI-based auth with zero client secrets
- [x] **GitHub Container Registry Migration** — Migrated from ACR (~$150/mo savings)
- [x] **Azure SQL Free Tier** — Staging database at $0 (was $15/mo)
- [x] **75% Cost Reduction** — $298/mo → $73/mo infrastructure optimization
- [x] **Zero Open Issues** — All 7 original issues resolved
- [x] **Enhanced Security Headers** — 7/7 security headers with CSP nonce support
- [x] **PKCE OAuth Implementation** — RFC 7636 compliant PKCE flow
- [x] **JWT Algorithm Confusion Fix** — Issuer-based routing prevents forgery
- [x] **Refresh Token Blacklisting** — Secure token rotation with Redis
- [x] **Operations Playbook** — 24.5 KB complete operations guide
- [x] **Automated Database Backups** — Schema-only staging (`25169438794`) and production (`25171354807`) backup validation passed end-to-end; bd `jzpa` is closed. Weekly BACPAC long-term export remains separate and blocked as bd `cz89` because staging Azure SQL Free does not support ImportExport.
- [x] **Makefile** — 15+ common development commands
- [x] **Enhanced Application Insights** — Custom telemetry, distributed tracing
- [x] **43 Security Audit Findings Resolved** — Complete security hardening

**Previous Releases:**
- [x] Multi-tenant cost aggregation and anomaly detection
- [x] Compliance monitoring with secure score tracking
- [x] Resource inventory and tagging compliance
- [x] Identity governance (privileged accounts, guests, MFA)
- [x] Automated sync jobs with monitoring
- [x] Preflight checks for Azure connectivity
- [x] Riverside compliance dashboard
- [x] Bulk operations (tags, anomalies, recommendations)
- [x] CSV export functionality
- [x] Performance monitoring and caching
- [x] Azure Lighthouse integration
- [x] Data backfill service
- [x] WCAG 2.2 accessibility
- [x] Dark mode
- [x] App Insights telemetry
- [x] Data retention service
- [x] Azure Dev Deployment (Bicep IaC, ACR, App Service, Key Vault)
- [x] Security audit — 5/5 findings resolved
- [x] E2E test suite (273 Playwright + httpx tests)
- [x] Documentation consolidation (13 → 7 root docs)
- [x] US/AC Traceability Matrix (93 requirements mapped)
- [x] Full quality gate validation (1,686 tests, 0 failures — v1.0.0 baseline)
- [x] Version 1.0.0 production release
- [x] Multi-brand design system (5 brands, 47+ CSS variables, WCAG AA)
- [x] Version 1.1.0 design system release
- [x] Production hardening (security, linting, documentation)
- [x] CI/CD OIDC federation documented
- [x] Staging deployment checklist documented
- [x] Version 1.2.0 production hardening release
- [x] Replace backfill placeholder data with real Azure API calls (v1.2.0)
- [x] Staging environment deployed and operational (Entra ID P1, health checks green)
- [x] Budget tracking (CO-008) — Azure Cost Management budgets, alerts, thresholds (v1.3.x)
- [x] Test suite expanded 1,686 → 2,531 tests, 100% module coverage (v1.4.0)
- [x] Zero test failures, zero lint errors (v1.4.0)
- [x] Cleared all remaining xfail markers — 2,563 tests fully green (v1.4.1)
- [x] Production infrastructure deployed (ACR, Azure SQL, Key Vault, App Service B2) (v1.5.0)
- [x] Staging E2E validation suite — 74 tests (smoke, security, API coverage) (v1.5.0)
- [x] Production CI/CD pipeline with QA gate, Trivy scanning, environment approval (v1.5.0)
- [x] MSSQL compatibility + graceful startup resilience (v1.5.1)

### 📊 Project Statistics

| Metric | Value |
|--------|-------|
| **Total Roadmap Tasks** | 221 |
| **Completed Tasks** | 221 (100%) |
| **Test Count** | 2,563+ |
| **Test Pass Rate** | 100% |
| **Open Issues** | 0 |
| **Monthly Cost Savings** | $165 active, $180 potential |
| **Documentation Files** | 50+ |
| **Git Commits** | 4,000+ |

### 🔮 Future Enhancements

- [ ] Custom compliance frameworks (SOC2, NIST)
- [ ] Teams bot integration
- [ ] Access review workflows with ML recommendations
- [ ] Advanced cost forecasting with time-series ML
- [ ] Real-time WebSocket notifications
- [ ] GraphQL API layer
- [ ] Multi-factor authentication for platform access

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

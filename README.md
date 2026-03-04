# Azure Multi-Tenant Governance Platform

A lightweight, cost-effective platform for managing Azure/M365 governance across multiple tenants. Built with Python, FastAPI, HTMX, and Tailwind CSS.

## Features

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
- **WCAG 2.2 Accessibility**: Skip nav, focus-visible, 44px touch targets
- **Dark Mode**: System preference detection with manual toggle
- **App Insights**: Request telemetry with optional OpenCensus exporter
- **Data Retention**: Automated time-series cleanup with configurable periods

## Quick Start

### Prerequisites

- Python 3.11+
- Azure subscriptions with appropriate permissions
- App registrations in each tenant (or Azure Lighthouse delegation)

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/azure-governance-platform.git
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

## Documentation

| Document | Description |
|----------|-------------|
| [API Reference](./docs/API.md) | Complete REST API documentation |
| [Deployment Guide](./docs/DEPLOYMENT.md) | Deployment options and procedures |
| [Operations Runbook](./docs/RUNBOOK.md) | Daily operations and troubleshooting |
| [Developer Guide](./docs/DEVELOPMENT.md) | Setup and contribution guidelines |
| [Implementation Guide](./docs/IMPLEMENTATION_GUIDE.md) | Detailed setup instructions |
| [Common Pitfalls](./docs/COMMON_PITFALLS.md) | Troubleshooting guide |

### Interactive API Documentation

Once running, access the interactive API docs:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Project Structure

```
azure-governance-platform/
├── app/
│   ├── api/
│   │   ├── routes/          # API endpoints
│   │   │   ├── riverside.py # Riverside compliance endpoints
│   │   └── services/        # Business logic
│   │       └── riverside_svc.py
│   ├── core/                # Config, DB, scheduler
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
uv pip install -e ".[dev]" --index-url https://pypi.ci.artifacts.walmart.com/artifactory/api/pypi/external-pypi/simple --allow-insecure-host pypi.ci.artifacts.walmart.com

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

### Azure App Service (Minimal Cost)

```bash
# Build and deploy
az webapp up --name governance-platform --sku B1 --runtime "PYTHON:3.11"
```

Estimated cost: ~$13/month

### Docker

```bash
docker build -t governance-platform .
docker run -p 8000:8000 --env-file .env governance-platform
```

## Cost Estimates

| Deployment | Monthly Cost |
|------------|-------------|
| App Service B1 | ~$13 |
| Key Vault (optional) | ~$1 |
| **Total MVP** | **~$15-20** |

## Riverside Compliance Tracking

### Executive Overview

The Azure Governance Platform includes specialized compliance tracking for Riverside Company requirements.

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

### Completed

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

### In Progress

- [ ] Replace backfill placeholder data with real Azure API calls
- [ ] Production hardening (CORS, token blacklist, rate limits)

### Planned

- [ ] Custom compliance frameworks
- [ ] Power BI embedding
- [ ] Teams bot integration
- [ ] Access review workflows
- [ ] Advanced cost forecasting with ML
- [ ] Multi-factor authentication for platform access

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

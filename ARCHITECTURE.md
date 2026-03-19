# Azure Multi-Tenant Governance Platform - Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AZURE GOVERNANCE PLATFORM                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  Tenant A   │  │  Tenant B   │  │  Tenant C   │  │  Tenant D   │        │
│  │  (Azure)    │  │  (Azure)    │  │  (Azure)    │  │  (Azure)    │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│         │                │                │                │                │
│         └────────────────┴────────────────┴────────────────┘                │
│                                   │                                          │
│                    ┌──────────────▼──────────────┐                          │
│                    │      Azure Lighthouse       │                          │
│                    │   (Cross-Tenant Delegation) │                          │
│                    └──────────────┬──────────────┘                          │
│                                   │                                          │
│  ┌────────────────────────────────▼────────────────────────────────────┐    │
│  │                     GOVERNANCE PLATFORM                              │    │
│  │  ┌─────────────────────────────────────────────────────────────┐    │    │
│  │  │                    FastAPI Backend                          │    │    │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │    │    │
│  │  │  │   Cost   │ │Compliance│ │ Resource │ │   Identity   │   │    │    │
│  │  │  │ Service  │ │ Service  │ │ Service  │ │   Service    │   │    │    │
│  │  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘   │    │    │
│  │  │       └────────────┴────────────┴──────────────┘           │    │    │
│  │  │                           │                                 │    │    │
│  │  │                    ┌──────▼──────┐                         │    │    │
│  │  │                    │   SQLite    │                         │    │    │
│  │  │                    │  Database   │                         │    │    │
│  │  │                    └─────────────┘                         │    │    │
│  │  └─────────────────────────────────────────────────────────────┘    │    │
│  │                                                                      │    │
│  │  ┌─────────────────────────────────────────────────────────────┐    │    │
│  │  │                HTMX + Tailwind Frontend                     │    │    │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │    │    │
│  │  │  │   Cost   │ │Compliance│ │ Resource │ │   Identity   │   │    │    │
│  │  │  │Dashboard │ │Dashboard │ │ Explorer │ │   Viewer     │   │    │    │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │    │    │
│  │  └─────────────────────────────────────────────────────────────┘    │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Layer | Technology | Rationale |
|-------|------------|----------|
| Backend | Python 3.11 + FastAPI | Fast, async, low resource |
| Frontend | HTMX + Tailwind CSS | No build step, lightweight |
| Database | SQLite (dev) / Azure SQL S1 (prod) | Cost-effective dev, enterprise prod |
| Charts | Chart.js | Client-side, no server load |
| Auth | Azure AD / Entra ID | Native SSO integration |
| APIs | Azure SDK + httpx | Official + async HTTP |
| Caching | SQLite + in-memory | Reduce API calls |
| Tasks | APScheduler | Background data sync |
| Hosting | Azure App Service (B2) | Production-grade, auto-scaling ready |

---

## Component Architecture

### Backend Structure

```
app/
├── main.py                       # FastAPI app entry — 22 routers registered
├── core/
│   ├── config.py                 # Settings & env vars (Key Vault integration)
│   ├── auth.py                   # JWT + Azure AD auth middleware
│   ├── authorization.py          # RBAC + tenant authorization
│   ├── database.py               # SQLite (dev) / Azure SQL (prod) connection
│   ├── scheduler.py              # Background jobs (APScheduler)
│   ├── rate_limit.py             # Sliding window rate limiting
│   ├── cache.py                  # In-memory + Redis cache
│   ├── circuit_breaker.py        # Circuit breaker for Azure API calls
│   ├── theme_middleware.py       # Tenant → brand → CSS variables injection
│   ├── design_tokens.py          # Pydantic brand/color/typography models
│   ├── css_generator.py          # Server-side CSS custom property generation
│   ├── color_utils.py            # WCAG color math (contrast, shades)
│   └── sync/                     # Background sync workers
│       ├── compliance.py
│       ├── costs.py
│       ├── identity.py
│       ├── resources.py
│       ├── dmarc.py
│       └── riverside.py
├── api/
│   ├── routes/
│   │   ├── auth.py               # Login, token, refresh
│   │   ├── dashboard.py          # Main dashboard page
│   │   ├── costs.py              # Cost endpoints
│   │   ├── budgets.py            # Budget tracking
│   │   ├── compliance.py         # Compliance endpoints
│   │   ├── compliance_rules.py   # Custom compliance rules CRUD (CM-002)
│   │   ├── resources.py          # Resource inventory + lifecycle history
│   │   ├── identity.py           # Identity governance
│   │   ├── tenants.py            # Tenant management
│   │   ├── sync.py               # Sync trigger + status
│   │   ├── riverside.py          # Riverside compliance dashboard
│   │   ├── bulk.py               # Bulk operations
│   │   ├── dmarc.py              # DMARC monitoring
│   │   ├── exports.py            # CSV exports
│   │   ├── monitoring.py         # Resource health aggregation
│   │   ├── audit_logs.py         # Audit log aggregation (CM-010)
│   │   ├── quotas.py             # Quota utilization monitoring (RM-007)
│   │   ├── preflight.py          # Azure connectivity preflight checks
│   │   ├── recommendations.py    # Right-sizing recommendations
│   │   └── onboarding.py         # Self-service Lighthouse onboarding
│   └── services/
│       ├── azure_client.py       # Azure SDK wrapper
│       ├── graph_client.py       # MS Graph wrapper
│       ├── cost_service.py       # Cost aggregation + anomaly detection
│       ├── compliance_service.py # Compliance + secure score
│       ├── custom_rule_service.py# Custom rule CRUD + JSON Schema eval (CM-002)
│       ├── resource_service.py   # Resource inventory + tagging
│       ├── resource_lifecycle_service.py # Lifecycle event tracking (RM-004)
│       ├── identity_service.py   # Identity governance
│       ├── budget_service.py     # Budget tracking + alerting
│       ├── audit_log_service.py  # Audit log aggregation (CM-010)
│       ├── quota_service.py      # Quota utilization monitoring (RM-007)
│       ├── monitoring_service.py # Health + performance monitoring
│       ├── recommendation_service.py # Right-sizing recommendations
│       ├── dmarc_service.py      # DMARC record analysis
│       └── riverside_service/    # Riverside compliance logic
├── models/
│   ├── tenant.py
│   ├── cost.py
│   ├── compliance.py
│   ├── resource.py
│   ├── resource_lifecycle.py     # ResourceLifecycleEvent (RM-004)
│   ├── identity.py
│   ├── budget.py
│   ├── audit_log.py              # AuditLogEntry (CM-010)
│   ├── custom_rule.py            # CustomComplianceRule (CM-002)
│   ├── monitoring.py
│   ├── brand_config.py
│   ├── backfill_job.py
│   ├── recommendation.py
│   ├── dmarc.py
│   ├── notifications.py
│   └── riverside.py
└── templates/
    ├── base.html                 # Base template with design token injection
    ├── macros/ui.html            # Jinja2 component macro library
    ├── components/               # Reusable HTMX partials
    └── pages/                    # Full page templates (9 pages)
```

---

## Design System Architecture

The platform implements a **token-based multi-brand design system** supporting 5 franchise brands with WCAG AA compliance and server-side CSS generation.

### Pipeline

```
config/brands.yaml             Source of truth — 5 brand definitions
       │
       ▼
app/core/design_tokens.py      Pydantic validation → BrandRegistry
       │
       ▼
app/core/color_utils.py        WCAG color math, 10-shade scales
       │
       ▼
app/core/css_generator.py      47+ CSS custom properties per brand
       │
       ▼
app/core/theme_middleware.py   FastAPI middleware: tenant → brand → ThemeContext
       │
       ▼
app/templates/base.html        Inline style + <style> block injection
       │
       ▼
app/templates/macros/ui.html   ARIA-compliant UI component macros
```

### Key Components

| Component | File | Responsibility |
|-----------|------|---------------|
| Design Tokens | `app/core/design_tokens.py` | Pydantic models (BrandConfig, BrandColors, BrandTypography, BrandDesignSystem), YAML loader, module-level cache |
| Color Utilities | `app/core/color_utils.py` | hex/RGB/HSL conversion, WCAG luminance + contrast ratio, shade scale generation, auto text color |
| CSS Generator | `app/core/css_generator.py` | Generates `--brand-*` CSS custom properties, scoped `[data-brand]` selectors, inline style strings |
| Theme Middleware | `app/core/theme_middleware.py` | Starlette middleware resolving tenant code → brand key → ThemeContext with in-memory caching |
| UI Macros | `app/templates/macros/ui.html` | 10 Jinja2 macros (button, card, badge, alert, stat_card, table, tabs, dialog, progress, skeleton) with ARIA attributes |

### Brand Resolution Flow

```
HTTP Request
    │
    ├─ ?brand=frenchies query param     → brand key
    ├─ X-Brand-Key header               → brand key
    ├─ X-Tenant-Code header → mapping   → brand key
    ├─ request.state.tenant_code        → brand key
    └─ fallback                         → "httbrands" (default)
    │
    ▼
ThemeContext (cached per brand_key)
    ├─ css_variables: dict[str, str]    47+ variables
    ├─ inline_style: str                for <html style="...">
    ├─ google_fonts_url: str            preconnect + display=swap
    └─ brand_config: BrandConfigFull    full Pydantic model
```

### Performance

- **CSS generation**: < 10ms per brand (benchmark-validated)
- **Middleware overhead**: < 0.5ms after cache warmup
- **Cache strategy**: In-memory dict, O(1) lookup after first request

For full design system documentation, see [docs/design-system.md](./docs/design-system.md).

---

## Data Flow

### Sync Flow (Background)

```
┌────────────┐     ┌────────────┐     ┌────────────┐     ┌────────────┐
│ Scheduler  │────▶│  Service   │────▶│ Azure APIs │────▶│  SQLite    │
│ (APSched)  │     │  Layer     │     │ (ARM/Graph)│     │  Cache     │
└────────────┘     └────────────┘     └────────────┘     └────────────┘
      │                                                         │
      │              Every 1-24 hours (configurable)            │
      └─────────────────────────────────────────────────────────┘
```

### Request Flow (User)

```
┌────────────┐     ┌────────────┐     ┌────────────┐     ┌────────────┐
│   User     │────▶│   HTMX     │────▶│  FastAPI   │────▶│  SQLite    │
│  Browser   │     │  Request   │     │  Endpoint  │     │  (Cached)  │
└────────────┘     └────────────┘     └────────────┘     └────────────┘
      ▲                                      │
      │            HTML Fragment             │
      └──────────────────────────────────────┘
```

---

## Database Schema

### Core Tables

```sql
-- Tenant configuration
tenants (
    id TEXT PRIMARY KEY,
    name TEXT,
    tenant_id TEXT,        -- Azure tenant GUID
    client_id TEXT,        -- App registration
    client_secret_ref TEXT,-- Key Vault reference
    is_active BOOLEAN,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)

-- Subscriptions per tenant
subscriptions (
    id TEXT PRIMARY KEY,
    tenant_id TEXT FK,
    subscription_id TEXT,
    display_name TEXT,
    state TEXT,
    synced_at TIMESTAMP
)

-- Daily cost snapshots
cost_snapshots (
    id INTEGER PRIMARY KEY,
    tenant_id TEXT FK,
    subscription_id TEXT,
    date DATE,
    total_cost REAL,
    currency TEXT,
    resource_group TEXT,
    service_name TEXT,
    synced_at TIMESTAMP
)

-- Compliance states
compliance_snapshots (
    id INTEGER PRIMARY KEY,
    tenant_id TEXT FK,
    subscription_id TEXT,
    policy_name TEXT,
    compliance_state TEXT,
    non_compliant_count INTEGER,
    synced_at TIMESTAMP
)

-- Resource inventory
resources (
    id TEXT PRIMARY KEY,
    tenant_id TEXT FK,
    subscription_id TEXT,
    resource_group TEXT,
    resource_type TEXT,
    name TEXT,
    location TEXT,
    tags TEXT,            -- JSON blob
    synced_at TIMESTAMP
)

-- Identity snapshots
identity_snapshots (
    id INTEGER PRIMARY KEY,
    tenant_id TEXT FK,
    snapshot_date DATE,
    total_users INTEGER,
    guest_users INTEGER,
    mfa_enabled INTEGER,
    privileged_users INTEGER,
    stale_accounts INTEGER,
    synced_at TIMESTAMP
)

-- Sync job tracking
sync_jobs (
    id INTEGER PRIMARY KEY,
    job_type TEXT,
    tenant_id TEXT,
    status TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT
)
```

---

## Authentication Architecture

### Option A: Azure Lighthouse (Recommended)

```
┌─────────────────────────────────────────────────────────────┐
│                    Managing Tenant                           │
│  ┌─────────────────────────────────────────────────────┐    │
│  │           Governance Platform                        │    │
│  │           (Single App Registration)                  │    │
│  └───────────────────────┬─────────────────────────────┘    │
└──────────────────────────┼──────────────────────────────────┘
                           │
          Azure Lighthouse Delegation
                           │
    ┌──────────────────────┼──────────────────────┐
    ▼                      ▼                      ▼
┌────────┐           ┌────────┐            ┌────────┐
│Tenant B│           │Tenant C│            │Tenant D|
│(Reader)│           │(Reader)│            │(Reader)│
└────────┘           └────────┘            └────────┘
```

### Option B: Per-Tenant App Registrations

```
┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐
│  Tenant A  │  │  Tenant B  │  │  Tenant C  │  │  Tenant D  │
│  App Reg   │  │  App Reg   │  │  App Reg   │  │  App Reg   │
│  + SP      │  │  + SP      │  │  + SP      │  │  + SP      │
└─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘
      │               │               │               │
      └───────────────┴───────────────┴───────────────┘
                              │
                    ┌─────────▼─────────┐
                    │   Governance      │
                    │   Platform        │
                    │   (Stores creds)  │
                    └───────────────────┘
```

---

## API Design

### REST Endpoints

```
GET  /api/v1/tenants                    # List all tenants
GET  /api/v1/tenants/{id}/subscriptions # Subscriptions per tenant

GET  /api/v1/costs/summary              # Aggregated costs
GET  /api/v1/costs/by-tenant            # Costs per tenant
GET  /api/v1/costs/by-service           # Costs by service type
GET  /api/v1/costs/trends               # Cost trending
GET  /api/v1/costs/anomalies            # Cost anomalies

GET  /api/v1/compliance/scores          # Compliance scores
GET  /api/v1/compliance/policies        # Policy status
GET  /api/v1/compliance/non-compliant   # Non-compliant resources

GET  /api/v1/resources                  # Resource inventory
GET  /api/v1/resources/orphaned         # Orphaned resources
GET  /api/v1/resources/tagging          # Tagging compliance

GET  /api/v1/identity/summary           # Identity overview
GET  /api/v1/identity/privileged        # Privileged accounts
GET  /api/v1/identity/guests            # Guest accounts
GET  /api/v1/identity/stale             # Stale accounts

POST /api/v1/sync/{type}                # Trigger manual sync
GET  /api/v1/sync/status                # Sync job status
```

### HTMX Partials

```
GET  /partials/cost-summary-card        # Cost summary widget
GET  /partials/cost-chart               # Cost trend chart
GET  /partials/compliance-gauge         # Compliance score gauge
GET  /partials/resource-table           # Resource list table
GET  /partials/identity-stats           # Identity statistics
GET  /partials/alerts-panel             # Active alerts
```

---

## Deployment Architecture

### Minimal Cost Option (< $50/mo)

```
┌─────────────────────────────────────────────────────────────┐
│              Azure App Service (B1 - $13/mo)                │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  FastAPI + HTMX + SQLite (single instance)            │  │
│  │  - APScheduler runs in-process                        │  │
│  │  - SQLite file in persistent storage                  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              +
┌─────────────────────────────────────────────────────────────┐
│              Azure Key Vault ($0.03/10k operations)         │
│  - Store tenant credentials securely                        │
└─────────────────────────────────────────────────────────────┘

Total: ~$15-20/month
```

### Production Option (< $100/mo)

```
┌─────────────────────────────────────────────────────────────┐
│              Azure Container Apps ($30-50/mo)               │
│  ┌─────────────────────┐  ┌─────────────────────┐          │
│  │   Web Container     │  │  Worker Container   │          │
│  │   (FastAPI)         │  │  (Sync Jobs)        │          │
│  └─────────────────────┘  └─────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
                              +
┌─────────────────────────────────────────────────────────────┐
│              Azure SQL (Serverless - $5-30/mo)              │
│  - Auto-pause when idle (cost savings)                      │
└─────────────────────────────────────────────────────────────┘
                              +
┌─────────────────────────────────────────────────────────────┐
│              Azure Key Vault + App Insights                 │
└─────────────────────────────────────────────────────────────┘

Total: ~$50-100/month
```

---

## Security Considerations

### Credential Management

```python
# Never store credentials in code or SQLite
# Use Azure Key Vault references

class TenantCredentials:
    tenant_id: str
    client_id: str
    client_secret_ref: str  # Key Vault secret URI
```

### Network Security

- Enable Azure AD authentication on App Service
- Use managed identity for Key Vault access
- Restrict outbound to Azure APIs only
- Enable HTTPS-only

### Data Protection

- SQLite encryption at rest (via App Service)
- No PII stored beyond Azure AD identifiers
- Audit logging for all data access
- Regular credential rotation

---

## Scalability Path

### Phase 1: MVP (4 tenants, <50 users)
- SQLite database
- Single App Service instance
- In-process scheduler
- ~$20/month

### Phase 2: Growth (10 tenants, <200 users)
- Migrate to Azure SQL Serverless
- Add Redis caching
- Container Apps with auto-scale
- ~$100/month

### Phase 3: Enterprise (25+ tenants, 500+ users)
- Azure SQL Elastic Pool
- Azure Functions for sync jobs
- API Management gateway
- ~$500/month

---

## Monitoring & Alerting

### Built-in Alerts

| Alert | Condition | Channel |
|-------|-----------|--------|
| Cost Spike | >20% daily increase | Teams |
| Compliance Drop | Score drops >5% | Teams |
| Stale Sync | No sync in 24h | Teams |
| API Errors | >10 errors/hour | Teams |
| Idle Resources | Cost >$100/mo | Weekly |

### Health Endpoints

```
GET /health          # Basic health check
GET /health/detailed # DB + API connectivity
GET /metrics         # Prometheus-compatible
```

---

## Riverside Compliance Architecture

This section documents the integration of Riverside compliance tracking into the Azure Governance Platform. Riverside Company is a critical compliance initiative with a deadline of July 8, 2026, requiring achievement of 3.0/5.0 maturity score across all managed domains.

### A. Riverside Data Model Extensions

The following database tables extend the core schema to support Riverside compliance tracking:

```sql
-- Riverside compliance tracking
riverside_compliance (
    id INTEGER PRIMARY KEY,
    tenant_id TEXT FK,
    requirement_id TEXT,
    requirement_name TEXT,
    category TEXT,              -- IAM, GS, DS, etc.
    status TEXT,                -- Not Started, In Progress, Compliant, Exempt
    priority TEXT,              -- P0, P1, P2
    owner TEXT,
    due_date DATE,
    completed_date DATE,
    evidence_type TEXT,         -- Screenshot, Document, API Verification
    evidence_link TEXT,
    notes TEXT,
    last_updated TIMESTAMP
)

-- MFA compliance per tenant
mfa_compliance (
    id INTEGER PRIMARY KEY,
    tenant_id TEXT FK,
    snapshot_date DATE,
    total_users INTEGER,
    mfa_enabled_users INTEGER,
    mfa_disabled_users INTEGER,
    admin_accounts_total INTEGER,
    admin_accounts_mfa_enabled INTEGER,
    synced_at TIMESTAMP
)

-- Device compliance (MDM/EDR)
device_compliance (
    id INTEGER PRIMARY KEY,
    tenant_id TEXT FK,
    snapshot_date DATE,
    total_devices INTEGER,
    compliant_devices INTEGER,
    non_compliant_devices INTEGER,
    pending_devices INTEGER,
    mdm_enrolled INTEGER,
    edr_installed INTEGER,
    encrypted_devices INTEGER,
    synced_at TIMESTAMP
)

-- Domain maturity scores
maturity_scores (
    id INTEGER PRIMARY KEY,
    tenant_id TEXT FK,
    domain TEXT,                -- IAM, GS, DS, etc.
    score REAL,                 -- 0.0 to 5.0
    assessment_date DATE,
    assessor TEXT,
    notes TEXT,
    synced_at TIMESTAMP
)

-- External threat data (Cybeta)
external_threats (
    id INTEGER PRIMARY KEY,
    tenant_id TEXT FK,
    threat_date DATE,
    threat_beta_score REAL,
    vulnerability_count INTEGER,
    malicious_domains INTEGER,
    data_source TEXT,
    synced_at TIMESTAMP
)

-- Riverside deadline tracking
riverside_timeline (
    id INTEGER PRIMARY KEY,
    milestone TEXT,
    target_date DATE,
    status TEXT,
    days_remaining INTEGER,
    notes TEXT
)
```

**Index Strategy for Performance:**

```sql
CREATE INDEX idx_mfa_compliance_tenant_date ON mfa_compliance(tenant_id, snapshot_date);
CREATE INDEX idx_device_compliance_tenant_date ON device_compliance(tenant_id, snapshot_date);
CREATE INDEX idx_maturity_scores_tenant_domain ON maturity_scores(tenant_id, domain);
CREATE INDEX idx_riverside_compliance_status ON riverside_compliance(status);
CREATE INDEX idx_riverside_compliance_priority ON riverside_compliance(priority);
```

**Data Retention Policies:**

| Table | Retention | Archival |
|-------|-----------|----------|
| riverside_compliance | 5 years | Compressed |
| mfa_compliance | 2 years | Monthly aggregates |
| device_compliance | 2 years | Monthly aggregates |
| maturity_scores | 5 years | Annual snapshots |
| external_threats | 1 year | Not retained |

---

### B. Riverside API Extensions

The following API endpoints extend the core API for Riverside compliance visibility:

```
GET  /api/v1/riverside/summary                    # Executive compliance summary
GET  /api/v1/riverside/requirements               # All requirements with status
GET  /api/v1/riverside/requirements/{id}          # Single requirement details
GET  /api/v1/riverside/mfa-status                 # MFA enrollment status
GET  /api/v1/riverside/mfa-status/{tenant_id}     # MFA status per tenant
GET  /api/v1/riverside/device-compliance          # Device compliance overview
GET  /api/v1/riverside/device-compliance/{tenant_id} # Device compliance per tenant
GET  /api/v1/riverside/maturity-scores            # Domain maturity scores
GET  /api/v1/riverside/maturity-scores/{tenant_id} # Maturity scores per tenant
GET  /api/v1/riverside/timeline                   # Deadline timeline
GET  /api/v1/riverside/gaps                       # Critical gaps analysis
GET  /api/v1/riverside/threats                    # External threat data

POST /api/v1/riverside/requirements               # Create new requirement
PUT  /api/v1/riverside/requirements/{id}          # Update requirement
POST /api/v1/riverside/requirements/{id}/evidence # Upload/link evidence
PUT  /api/v1/riverside/maturity-scores            # Update maturity scores
```

**Request/Response Schemas:**

```python
# GET /api/v1/riverside/summary
Response:
{
    "overall_maturity": 2.4,
    "target_maturity": 3.0,
    "days_remaining": 160,
    "deadline": "2026-07-08",
    "financial_risk": 4000000,
    "mfa_coverage_percent": 30,
    "mfa_unprotected_users": 1358,
    "critical_gaps_count": 8,
    "requirements_compliant": 45,
    "requirements_total": 72,
    "threat_beta_score": 1.04
}

# GET /api/v1/riverside/mfa-status
Response:
{
    "summary": {
        "total_users": 1992,
        "mfa_enabled": 634,
        "mfa_disabled": 1358,
        "coverage_percent": 30
    },
    "by_tenant": [
        {
            "tenant_id": "htt",
            "tenant_name": "HTT",
            "total_users": 498,
            "mfa_enabled": 149,
            "coverage_percent": 30
        },
        ...
    ]
}

# GET /api/v1/riverside/gaps
Response:
{
    "critical_gaps": [
        {
            "requirement_id": "IAM-12",
            "requirement_name": "Universal MFA Enforcement",
            "status": "In Progress",
            "current_progress": 30,
            "target": 100,
            "deadline": "Immediate",
            "risk_level": "Critical",
            "owner": "Security Team"
        },
        ...
    ],
    "warning_gaps": [...],
    "total_financial_risk": 4000000
}
```

---

### C. Riverside Dashboard Architecture

The Riverside compliance dashboard provides an executive-focused view with the following components:

**Frontend Components:**

```
/riverside
├── Executive Summary Card      # Key metrics at a glance
├── MFA Compliance Gauge        # Visual progress indicator
├── Domain Maturity Radar Chart # Multi-domain visualization
├── Requirements Status Table   # Filterable, sortable list
├── Timeline Widget             # Countdown to deadline
└── Risk Summary Panel          # Financial risk quantification
```

**HTMX Integration Patterns:**

```html
<!-- Executive Summary Card -->
<div id="riverside-summary" 
     hx-get="/partials/riverside/summary" 
     hx-trigger="load, every 5m">
    <!-- Loading state -->
</div>

<!-- MFA Gauge -->
<div id="mfa-gauge" 
     hx-get="/partials/riverside/mfa-gauge" 
     hx-trigger="load, every 5m">
</div>

<!-- Requirements Table with filters -->
<div id="requirements-table"
     hx-get="/partials/riverside/requirements?status={{status}}&category={{category}}"
     hx-trigger="status-filter changed, category-filter changed">
</div>
```

**Dashboard URL:** `http://localhost:8000/riverside`

---

### D. Riverside Data Flow

The following diagram illustrates data flow for Riverside compliance tracking:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      RIVERSIDE COMPLIANCE DATA FLOW                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    EXTERNAL DATA SOURCES                            │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │    │
│  │  │   Microsoft │  │   Intune    │  │   Azure AD  │  │   Cybeta    │ │    │
│  │  │    Graph    │  │   (MDM)     │  │ (Admin API) │  │    API      │ │    │
│  │  │  (MFA Data) │  │  (Devices)  │  │  (Roles)    │  │  (Threats)  │ │    │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘ │    │
│  │         │                │                │                │        │    │
│  │         ▼                ▼                ▼                ▼        │    │
│  │  ┌────────────────────────────────────────────────────────────────┐  │    │
│  │  │                    SERVICE LAYER                               │  │    │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │  │    │
│  │  │  │ GraphClient  │  │ IntuneClient │  │  ThreatSvc   │        │  │    │
│  │  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘        │  │    │
│  │  └─────────┼─────────────────┼─────────────────┼────────────────┘  │    │
│  └────────────┼─────────────────┼─────────────────┼───────────────────┘    │
│               │                 │                 │                         │
│               ▼                 ▼                 ▼                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      DATABASE LAYER                                 │    │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │    │
│  │  │ mfa_compliance │ device_compliance │ maturity_scores │ external_threats │   │    │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                     │                                        │
│                                     ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    API & DASHBOARD LAYER                            │    │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │    │
│  │  │ /riverside/ │ │ /api/v1/    │ │  HTMX       │ │  Chart.js   │   │    │
│  │  │  summary    │ │  riverside  │ │  Partials   │ │  Visualize  │   │    │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Manual/Scheduled Data Entry:**

```python
# Scheduled sync configuration
RIVERSIDE_SYNC_INTERVAL_HOURS = 4  # More frequent than core data
MANUAL_SYNC_SUPPORTED = True  # Allow on-demand updates
EVIDENCE_UPLOAD_ENABLED = True  # Support manual evidence
```

---

### E. Riverside Scalability Path

The Riverside compliance system follows a phased implementation approach:

**Phase 1: Manual Tracking with Evidence Uploads (Current)**

```
✓ Manual data entry for compliance requirements
✓ Evidence document upload/storage
✓ Manual MFA status tracking
✓ Basic deadline counting

Timeline: January - February 2026
Effort: Medium manual effort
```

**Phase 2: Automated Azure Data Sync**

```
→ Microsoft Graph API integration for MFA data
→ Intune API integration for device compliance
→ Azure AD API for admin role data
→ Automated daily sync

Timeline: February - April 2026
Effort: Initial setup, then automated
```

**Phase 3: External Threat API Integration**

```
→ Cybeta API integration (if available)
→ Automated threat scoring
→ Vulnerability tracking
→ Malicious domain monitoring

Timeline: April - June 2026
Effort: Configuration + monitoring
```

---

## Related Documentation

- [RIVERSIDE_INTEGRATION.md](./docs/RIVERSIDE_INTEGRATION.md) - Complete integration guide
- [RIVERSIDE_EXECUTIVE_SUMMARY.md](./docs/RIVERSIDE_EXECUTIVE_SUMMARY.md) - Executive summary
- [RIVERSIDE_API_GUIDE.md](./docs/RIVERSIDE_API_GUIDE.md) - API reference

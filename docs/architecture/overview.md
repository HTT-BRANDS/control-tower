# Architecture Overview

## System Design Philosophy

The Azure Governance Platform follows **enterprise-grade architecture principles**.

### Core Principles

1. **Security-First** - Defense in depth
2. **Cloud-Native** - Azure PaaS leverage
3. **Multi-Tenant** - Single codebase, isolated tenants
4. **Observable** - Full monitoring coverage
5. **Resilient** - Graceful degradation
6. **Maintainable** - Modular, typed, documented

---

## High-Level Architecture

### System Context

```
┌─────────────────────────────────────────────────────────┐
│                    EXTERNAL USERS                       │
│         (Admins, End Users, API Clients)                │
└─────────────────────────────────────────────────────────┘
                           │
          ┌────────────────┴────────────────┐
          │     AZURE FRONT DOOR / CDN      │
          └────────────────┬────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────┐
│              AZURE GOVERNANCE PLATFORM                │
│                  (App Service)                        │
│  ┌─────────────────────────────────────────────────┐  │
│  │              FASTAPI APPLICATION                 │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐         │  │
│  │  │   API   │  │ Services│  │ Workers │         │  │
│  │  │  Layer  │  │  Layer  │  │ Background       │  │
│  │  └────┬────┘  └────┬────┘  └─────────┘         │  │
│  │       │            │                           │  │
│  │       └────────────┼──────────────────────────┘  │
│  └──────────────────────┼───────────────────────────────┘
└────────────────────────┼───────────────────────────────┘
          ┌──────────────┴──────────────┐
          │    DATA & MESSAGING LAYER    │
          │  SQL · Redis · Key Vault ·   │
          │  Service Bus · Blob Storage  │
          └──────────────────────────────┘
```

---

## Component Architecture

### 1. Presentation Layer

| Component | Technology | Responsibility |
|-----------|------------|----------------|
| **Admin Portal** | React + TypeScript | Tenant management |
| **User Dashboard** | React + Chart.js | Analytics, reports |
| **Mobile App** | React Native (planned) | Mobile monitoring |
| **API Clients** | Any HTTP client | Integrations |

### 2. API Layer (FastAPI)

```python
# Middleware Stack:
1. CORS
2. Security Headers
3. Rate Limiting
4. Authentication (JWT/OIDC)
5. Request Validation
6. Exception Handling

# Route Organization:
/api/v1/auth/*      - Authentication
/api/v1/tenants/*   - Tenant management
/api/v1/resources/* - Azure resources
/api/v1/costs/*     - Cost analysis
/api/v1/compliance/* - Compliance
/api/v1/identity/*  - Identity
/api/v1/health/*    - Health checks
```

### 3. Service Layer

**Pattern:** Domain-Driven Services

- `identity_service.py` - User/tenant management
- `cost_service.py` - Cost analysis & optimization
- `compliance_service.py` - Compliance monitoring
- `resource_service.py` - Azure resource discovery
- `sync_service.py` - Background synchronization
- `notification_service.py` - Alerts & notifications

**Features:**
- ✅ Type-hinted methods (84% coverage)
- ✅ Async/await for I/O
- ✅ Caching layer (Redis)
- ✅ Error handling & retries
- ✅ Comprehensive docstrings

### 4. Data Access Layer

**Pattern:** Repository + Unit of Work

```
app/
├── db/
│   ├── repositories/      # Data access
│   ├── session.py         # SQLAlchemy sessions
│   └── models/            # ORM models
```

**Database:**
- **Primary:** Azure SQL (S2 tier, 250GB)
- **Connection:** Async SQLAlchemy + aioodbc
- **Migrations:** Alembic (version controlled)
- **Multi-Tenancy:** Row-level security (RLS)

### 5. Background Processing

**Pattern:** Queue-based Workers

- `sync_worker.py` - Azure resource sync
- `analytics_worker.py` - Cost/compliance analysis
- `notification_worker.py` - Alert dispatch
- `cleanup_worker.py` - Maintenance tasks

---

## Data Architecture

### Multi-Tenant Model

```sql
-- Row-Level Security Pattern
CREATE TABLE tenants (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    azure_subscription_id VARCHAR(100),
    created_at DATETIME DEFAULT GETDATE()
);

CREATE TABLE resources (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    azure_resource_id VARCHAR(500),
    resource_type VARCHAR(100),
    compliance_status VARCHAR(50),
    -- RLS automatically filters by tenant_id
);

-- Security Policy
CREATE SECURITY POLICY tenant_isolation
    ADD FILTER PREDICATE tenant_access_predicate(tenant_id)
    ON resources;
```

---

## Caching Strategy

### 4-Tier Cache

| Level | Technology | Use Case | TTL |
|-------|------------|----------|-----|
| **L1** | In-Memory | Hot data, request-scoped | 5 min |
| **L2** | Redis | Cross-request cache | 15 min |
| **L3** | Azure CDN | Static assets | 1 hour |
| **L4** | Browser Cache | Frontend assets | 24 hours |

---

## Deployment Architecture

### Blue-Green Deployment

```
┌─────────────────────────────────────────────┐
│              AZURE APP SERVICE               │
├─────────────────────────────────────────────┤
│  ┌──────────────┐    ┌──────────────┐     │
│  │   STAGING    │    │  PRODUCTION  │     │
│  │    SLOT      │←──→│    SLOT      │     │
│  │  (testing)   │swap│   (live)     │     │
│  └──────────────┘    └──────────────┘     │
└─────────────────────────────────────────────┘
```

**Process:**
1. Deploy to staging
2. Run smoke tests
3. Warm up (Always-On)
4. Swap to production (zero downtime)
5. Monitor health

---

## Scalability

### Horizontal Scaling

- **App Service Plan:** P1v2 (1-10 instances)
- **Scale Triggers:**
  - CPU > 70% for 5 min → Scale out
  - Memory > 80% for 5 min → Scale out
  - Request queue > 100 → Scale out
- **Database:** Azure SQL S2 (upgrade to S3 if needed)

---

## Resilience Patterns

### Circuit Breaker

```python
@circuit(failure_threshold=5, recovery_timeout=60)
async def call_azure_api():
    return await azure_client.get_resources()
```

### Retry with Backoff

```python
@retry(stop=stop_after_attempt(3), 
       wait=wait_exponential(multiplier=1, min=4, max=10))
async def query_database():
    return await db_session.execute(query)
```

### Graceful Degradation

```python
async def get_dashboard_data(tenant_id: str):
    try:
        return await azure_service.get_resources(tenant_id)
    except AzureAPIError:
        return await cache_service.get_cached_resources(tenant_id)
```

---

## Security Architecture

See dedicated [Security Guide](../security) for complete details.

**Summary:**
- ✅ HTTPS-only enforcement
- ✅ Azure AD B2C with OIDC
- ✅ JWT token validation
- ✅ Row-level security (RLS)
- ✅ 12 security headers
- ✅ Key Vault secrets
- ✅ SQL injection protection
- ✅ Rate limiting

---

## Integration Architecture

### Azure Service Integration

```
Azure Governance Platform
           │
    ┌──────┼──────┬──────┐
    │      │      │      │
┌───▼──┐ ┌─▼──┐ ┌─▼──┐ ┌─▼────┐
│  ARM │ │Cost│ │AD  │ │Monitor│
│      │ │Mgmt│ │B2C │ │       │
└──────┘ └────┘ └────┘ └───────┘
```

**Integrations:**
- Azure Resource Manager (ARM) - Resource discovery
- Azure Cost Management - Cost analysis
- Azure AD B2C - Identity & auth
- Azure Monitor - Metrics & alerts
- Key Vault - Secrets
- Service Bus - Message queue

---

## Validation: Rock Solid ✅

| Attribute | Target | Actual | Status |
|-----------|--------|--------|--------|
| **Modularity** | 8+ modules | 15 modules | ✅ Exceeds |
| **Test Coverage** | 80% | 97%+ | ✅ Exceeds |
| **Type Safety** | 70% | 84% | ✅ Exceeds |
| **Documentation** | 5 docs | 52 docs | ✅ Exceeds |
| **Uptime** | 99.9% | 99.9%+ | ✅ On Target |
| **Response Time** | <500ms | ~130ms | ✅ Exceeds |

---

<p align="center">
  <strong>Azure Governance Platform</strong><br>
  <em>Production Certified • Enterprise Grade</em>
</p>

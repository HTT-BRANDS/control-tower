---
layout: default
title: Data Flow & Connections
---

# Data Flow & Connections

## 🌊 System Data Flow

Understanding how data moves through the Azure Governance Platform is critical for troubleshooting, optimization, and scaling.

---

## High-Level Data Flow

**External Sources → Platform → Data Layer → Consumers**

```
┌─────────────────────────────────────────────────────────┐
│                   EXTERNAL SOURCES                        │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Azure    │  │ Azure Cost   │  │ Azure AD     │      │
│  │ ARM API  │  │ Management   │  │ B2C          │      │
│  └──────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              AZURE GOVERNANCE PLATFORM                    │
│  ┌────────────┐  ┌──────────┐  ┌──────────┐  ┌───────┐ │
│  │ FastAPI    │  │ Service  │  │ Redis    │  │Workers│ │
│  │ App        │  │ Layer    │  │ Cache    │  │       │ │
│  └────────────┘  └──────────┘  └──────────┘  └───────┘ │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    DATA LAYER                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│  │ Azure    │  │ Blob     │  │ Key      │               │
│  │ SQL      │  │ Storage  │  │ Vault    │               │
│  └──────────┘  └──────────┘  └──────────┘               │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                  DATA CONSUMERS                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ React    │  │ Azure    │  │ Alert    │              │
│  │ Web App  │  │ Workbooks│  │ System   │              │
│  └──────────┘  └──────────┘  └──────────┘              │
└─────────────────────────────────────────────────────────┘
```

---

## Request Lifecycle

### 9-Step API Request Flow

**Average Response Time:** ~130ms (p95: ~532ms)

<div class="data-flow">
  <div class="flow-step">
    <div class="step-number">1</div>
    <div class="step-content">
      <h4>Request Ingress</h4>
      <p>Client sends HTTP request to Azure Front Door → App Service</p>
    </div>
  </div>
  <div class="flow-arrow">↓</div>
  <div class="flow-step">
    <div class="step-number">2</div>
    <div class="step-content">
      <h4>Authentication & Validation</h4>
      <p>FastAPI validates JWT (Azure AD B2C), checks rate limits</p>
    </div>
  </div>
  <div class="flow-arrow">↓</div>
  <div class="flow-step">
    <div class="step-number">3</div>
    <div class="step-content">
      <h4>Tenant Resolution</h4>
      <p>Extract tenant_id from JWT, set SQL context for RLS</p>
    </div>
  </div>
  <div class="flow-arrow">↓</div>
  <div class="flow-step">
    <div class="step-number">4</div>
    <div class="step-content">
      <h4>Cache Lookup</h4>
      <p>Check Redis cache for data (15-min TTL)</p>
    </div>
  </div>
  <div class="flow-arrow">↓</div>
  <div class="flow-step">
    <div class="step-number">5</div>
    <div class="step-content">
      <h4>Database Query</h4>
      <p>Query Azure SQL with tenant filters (RLS applied)</p>
    </div>
  </div>
  <div class="flow-arrow">↓</div>
  <div class="flow-step">
    <div class="step-number">6</div>
    <div class="step-content">
      <h4>Business Logic</h4>
      <p>Service layer processes, transforms, enriches data</p>
    </div>
  </div>
  <div class="flow-arrow">↓</div>
  <div class="flow-step">
    <div class="step-number">7</div>
    <div class="step-content">
      <h4>Response Serialization</h4>
      <p>Pydantic models serialize to JSON</p>
    </div>
  </div>
  <div class="flow-arrow">↓</div>
  <div class="flow-step">
    <div class="step-number">8</div>
    <div class="step-content">
      <h4>Telemetry & Logging</h4>
      <p>App Insights captures metrics and trace data</p>
    </div>
  </div>
  <div class="flow-arrow">↓</div>
  <div class="flow-step">
    <div class="step-number">9</div>
    <div class="step-content">
      <h4>Response Delivery</h4>
      <p>JSON response with security headers</p>
    </div>
  </div>
</div>

---

## Azure Integration Flows

### Resource Discovery Flow

**Frequency:** Every 6 hours per tenant  
**Duration:** ~2-5 minutes per tenant

```
Sync Worker → Azure ARM API → Resource Parser → Azure SQL → Redis Cache
```

**Process:**
1. Sync Worker authenticates with Managed Identity
2. Queries Azure ARM API for resource list
3. For each resource: get details, normalize, enrich
4. Upsert to Azure SQL (with tenant_id)
5. Invalidate Redis cache
6. Update last sync timestamp

### Cost Data Ingestion Flow

**Frequency:** Daily at 2 AM UTC  
**Retention:** 13 months

```
Job Scheduler → Cost Management API → Data Transformer → Azure SQL → App Insights
```

**Process:**
1. Scheduler requests usage data (daily)
2. API returns CSV/JSON usage details
3. Data transformer parses and maps to internal schema
4. Bulk insert to Azure SQL (partitioned by tenant)
5. Log metrics to Application Insights

---

## Data Connections Matrix

### Internal Connections

| Source | Destination | Protocol | Purpose | Volume |
|--------|-------------|----------|---------|--------|
| **App Service** | Azure SQL | ODBC + SSL | Data queries | ~500 req/min |
| **App Service** | Redis | Redis | Caching | ~1000 ops/min |
| **App Service** | Key Vault | HTTPS | Secrets | ~10 req/min |
| **Workers** | Azure SQL | ODBC + SSL | Data writes | ~200 writes/min |

### External Connections

| Source | Destination | Protocol | Purpose |
|--------|-------------|----------|---------|
| **Platform** | Azure ARM | HTTPS | Resource discovery |
| **Platform** | Cost Mgmt | HTTPS | Cost data |
| **Platform** | Azure AD B2C | HTTPS | Authentication |
| **Platform** | App Insights | HTTPS | Telemetry |

---

## Data Storage Architecture

### Azure SQL Database

**Key Tables:**
- `tenants` - Tenant configuration (50 rows)
- `resources` - Resource inventory (~2,500 rows)
- `cost_data` - Daily cost records (~15,000 rows)
- `compliance_scores` - Assessments (~500 rows)
- `users` - User identities (~200 rows)
- `audit_logs` - Audit trail (~50,000 rows)

### Redis Cache

**Cache Patterns:**
- `session:{user_id}` → User session (8h TTL)
- `resources:{tenant_id}` → Resource list (15m TTL)
- `costs:{tenant_id}:{month}` → Cost summary (1h TTL)
- `health:{tenant_id}` → Health status (5m TTL)

**Hit Rate:** ~85%

### Blob Storage

**Containers:**
- `reports/` → Generated PDFs
- `exports/` → CSV exports
- `backups/` → Daily DB backups
- `logs/` → Application logs

**Total Size:** ~12GB

---

## Performance Characteristics

### Query Performance

| Query Type | Average | p95 | Cache Hit |
|------------|---------|-----|-----------|
| Resource List | 45ms | 120ms | 85% |
| Cost Summary | 30ms | 80ms | 90% |
| Compliance | 25ms | 60ms | 95% |
| User Lookup | 15ms | 40ms | 80% |

### Throughput

| Metric | Current | Capacity |
|--------|---------|----------|
| **Requests/Second** | ~15 | ~150 |
| **Concurrent Users** | ~10 | ~100 |
| **Data Ingestion** | ~1MB/hour | ~10MB/hour |

---

## Data Security in Transit

### Encryption

| Connection | Protocol | Cipher |
|------------|----------|--------|
| Client → App | HTTPS 1.3 | TLS_AES_256_GCM_SHA384 |
| App → SQL | ODBC + SSL | AES-256 |
| App → Redis | Redis + TLS | AES-256 |
| App → Key Vault | HTTPS | TLS 1.3 |

### Network Security

- ✅ **Private Endpoints:** SQL, Key Vault, Storage
- ✅ **Firewall Rules:** Only App Service IPs allowed
- ✅ **VNet Integration:** App Service in isolated VNet

---

## Troubleshooting Data Flow

### Common Issues

**Slow resource list loading:**
- Check Redis cache hit rate (target: >80%)
- Review SQL query execution plan
- Verify connection pool not exhausted

**Stale cost data:**
- Check sync job last run time
- Verify Azure Cost Management API access
- Review Service Bus queue depth

**High database CPU:**
- Identify expensive queries in Query Store
- Check for missing indexes
- Review sync job timing

---

<p align="center"><small>Data Flow v1.8.1 | Understanding the System</small></p>

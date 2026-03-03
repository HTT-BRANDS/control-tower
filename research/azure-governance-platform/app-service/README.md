# Azure App Service Architecture Research

**Research Date:** 2025-03-02
**Topic:** Python 3.11 + FastAPI + Docker on Azure App Service

---

## Executive Summary

This research covers best practices for running containerized Python applications on Azure App Service, specifically for multi-tenant SaaS governance platforms. Covers scaling strategies, security hardening, and cost optimization for the B1 → P1v2 upgrade path.

### Key Findings

1. **B1 SKU Limitations**: 1.75GB RAM, shared infrastructure, suitable for dev/low-traffic
2. **Scaling Triggers**: CPU >70%, Memory >80%, Response time >2s, Queue depth
3. **Multi-tenant Patterns**: Lighthouse delegation preferred over per-tenant auth
4. **Cost Optimization**: B1 ($13) → B2 ($26) → P1v2 ($73) progression path
5. **Security**: Managed identity, Key Vault integration, private endpoints

---

## 1. Azure App Service SKU Analysis

### Current State: B1 (Basic Tier)

| Specification | Value | Assessment |
|---------------|-------|------------|
| **Price** | ~$13.14/month | ✅ Cost-effective for MVP |
| **Instance Count** | Up to 3 | ⚠️ Manual scaling only |
| **RAM** | 1.75 GB | ⚠️ Tight for multiple workers |
| **Storage** | 10 GB | ✅ Adequate |
| **Custom Domains/SSL** | Supported | ✅ Production-ready |
| **SLA** | None | ⚠️ No uptime guarantee |
| **Load Balancing** | Manual | ⚠️ Not automatic |

### Upgrade Path Recommendations

#### Phase 1: Growth (B2 - Basic 2)
```yaml
# When to upgrade:
- CPU consistently >60%
- Memory usage >1.2GB
- Response times degrading
- Concurrent users >25

Cost: ~$26.28/month
Specs: 3.5GB RAM, up to 3 instances
Timeline: When onboarding tenant #5-7
```

#### Phase 2: Production (P1v2 - Premium V2)
```yaml
# When to upgrade:
- Need auto-scaling
- Require SLA (99.95%)
- Multi-region deployment
- Advanced networking needs

Cost: ~$73/month (single instance)
Specs: 3.5GB RAM, auto-scale to 30 instances
SLA: 99.95% uptime guarantee
Timeline: 10+ tenants or production SLA requirements
```

#### Phase 3: Enterprise (P2v2 or Isolated)
```yaml
# When to upgrade:
- Compliance requirements (ISO, SOC2)
- Dedicated VNet required
- High-performance needs
- 50+ tenants

Cost: ~$146-500+/month
Specs: 7GB+ RAM, isolated environment
Timeline: Enterprise contracts
```

---

## 2. Multi-Tenant SaaS Patterns

### Pattern A: Azure Lighthouse (Recommended)

```
┌─────────────────────────────────────────────────────────────────┐
│                    MANAGING TENANT                               │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │           Azure Governance Platform                          │ │
│  │           (Single App Service - B1/P1v2)                     │ │
│  │                                                              │ │
│  │  ┌──────────────────────────────────────────────────────┐   │ │
│  │  │  FastAPI Application                                  │   │ │
│  │  │  - Single app registration                            │   │ │
│  │  │  - Managed Identity for Key Vault                     │   │ │
│  │  │  - SQLite (B1) → Azure SQL (P1v2+)                    │   │ │
│  │  └──────────────────────────────────────────────────────┘   │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
              Azure Lighthouse Delegation
                              │
    ┌─────────────────────────┼─────────────────────────┐
    │                         │                         │
    ▼                         ▼                         ▼
┌──────────┐           ┌──────────┐           ┌──────────┐
│ Tenant A │           │ Tenant B │           │ Tenant C │
│ (Reader) │           │ (Reader) │           │ (Reader) │
└──────────┘           └──────────┘           └──────────┘
```

**Advantages:**
- ✅ Single app registration to manage
- ✅ Unified security posture
- ✅ No credential storage per tenant
- ✅ Centralized access revocation
- ✅ Simplified onboarding

**Implementation:**
```python
# Azure Lighthouse setup
class LighthouseManager:
    def __init__(self):
        self.credential = DefaultAzureCredential()
        
    async def get_subscription_client(self, customer_tenant_id: str):
        """Access customer subscription via Lighthouse"""
        return SubscriptionClient(
            credential=self.credential,
            base_url=f"https://management.azure.com/subscriptions/{subscription_id}",
            # Lighthouse handles cross-tenant auth automatically
        )
```

### Pattern B: Per-Tenant Service Principals

```
┌─────────────────────────────────────────────────────────────────┐
│                    GOVERNANCE PLATFORM                           │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  Credential Vault (Azure Key Vault)                         ││
│  │  ├── tenant-a-client-secret                                 ││
│  │  ├── tenant-b-client-secret                                 ││
│  │  ├── tenant-c-client-secret                                 ││
│  │  └── tenant-d-client-secret                                 ││
│  └─────────────────────────────────────────────────────────────┘│
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  FastAPI Application                                        ││
│  │  - Retrieves tenant-specific creds from Key Vault           ││
│  │  - Creates token per tenant on-demand                       ││
│  │  - Manages credential rotation                              ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

**Advantages:**
- ✅ Fine-grained permission control
- ✅ Works without Lighthouse
- ✅ Tenant-specific audit trails

**Disadvantages:**
- ⚠️ Credential management complexity
- ⚠️ Secret rotation burden
- ⚠️ Slower onboarding (per-tenant setup)

---

## 3. Container Configuration Best Practices

### Dockerfile Optimization

```dockerfile
# Multi-stage build for smaller image
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy only necessary artifacts
COPY --from=builder /root/.local /home/appuser/.local
COPY --chown=appuser:appuser . .

# Set environment
ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Use multiple workers for production
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

### App Service Configuration

```yaml
# docker-compose.yml for App Service
version: '3.8'

services:
  web:
    image: your-registry.azurecr.io/governance-platform:${TAG:-latest}
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=sqlite:///data/governance.db  # B1 tier
      # For P1v2+: - DATABASE_URL=${DATABASE_URL}
      - AZURE_CLIENT_ID=${AZURE_CLIENT_ID}
      - AZURE_TENANT_ID=${AZURE_TENANT_ID}
      - KEY_VAULT_URL=${KEY_VAULT_URL}
    volumes:
      - persistent-storage:/app/data  # Persistent SQLite storage
    ports:
      - "8000:8000"

volumes:
  persistent-storage:
```

---

## 4. Scaling Strategies & Thresholds

### Auto-Scale Rules (P1v2+)

```json
{
  "location": "East US",
  "properties": {
    "targetResourceUri": "/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Web/serverFarms/{plan}",
    "profiles": [
      {
        "name": "AutoScaleProfile",
        "capacity": {
          "minimum": "1",
          "maximum": "5",
          "default": "1"
        },
        "rules": [
          {
            "metricTrigger": {
              "metricName": "CpuPercentage",
              "timeGrain": "PT1M",
              "statistic": "Average",
              "timeWindow": "PT5M",
              "timeAggregation": "Average",
              "operator": "GreaterThan",
              "threshold": 70
            },
            "scaleAction": {
              "direction": "Increase",
              "type": "ChangeCount",
              "value": "1",
              "cooldown": "PT5M"
            }
          },
          {
            "metricTrigger": {
              "metricName": "MemoryPercentage",
              "timeGrain": "PT1M",
              "statistic": "Average",
              "timeWindow": "PT5M",
              "timeAggregation": "Average",
              "operator": "GreaterThan",
              "threshold": 80
            },
            "scaleAction": {
              "direction": "Increase",
              "type": "ChangeCount",
              "value": "1",
              "cooldown": "PT5M"
            }
          }
        ]
      }
    ]
  }
}
```

### Manual Scaling Decision Matrix

| Metric | Current (B1) | Upgrade to B2 | Upgrade to P1v2 |
|--------|--------------|---------------|-----------------|
| **CPU Average** | < 50% | 50-70% | > 70% sustained |
| **Memory Usage** | < 1GB | 1-1.4GB | > 1.4GB |
| **Response Time** | < 500ms | 500ms-2s | > 2s |
| **Concurrent Users** | < 20 | 20-50 | > 50 |
| **Request Queue** | < 10 | 10-50 | > 50 |
| **Tenant Count** | 1-4 | 5-10 | 10+ |

---

## 5. Security Hardening

### Managed Identity Configuration

```python
# app/core/auth.py
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

class AzureAuth:
    def __init__(self):
        # Automatically uses Managed Identity in Azure
        self.credential = DefaultAzureCredential()
        
    def get_key_vault_client(self, vault_url: str):
        return SecretClient(
            vault_url=vault_url,
            credential=self.credential
        )
    
    def get_tenant_secret(self, tenant_id: str):
        """Retrieve tenant-specific credentials from Key Vault"""
        client = self.get_key_vault_client(settings.KEY_VAULT_URL)
        return client.get_secret(f"tenant-{tenant_id}-secret")
```

### App Service Security Settings

```bash
# Azure CLI commands for security hardening

# 1. Enable HTTPS only
az webapp update --name $APP_NAME --resource-group $RG --https-only true

# 2. Enable managed identity
az webapp identity assign --name $APP_NAME --resource-group $RG

# 3. Configure minimum TLS version
az webapp config set --name $APP_NAME --resource-group $RG --min-tls-version "1.2"

# 4. Enable diagnostic logging
az webapp log config --name $APP_NAME --resource-group $RG \
    --application-logging true \
    --detailed-error-messages true \
    --failed-request-tracing true

# 5. Configure CORS (if needed)
az webapp cors add --name $APP_NAME --resource-group $RG \
    --allowed-origins "https://your-domain.com"

# 6. IP Restrictions (for admin endpoints)
az webapp config access-restriction add --name $APP_NAME \
    --resource-group $RG \
    --rule-name "AdminOnly" \
    --action Allow \
    --ip-address "YOUR_OFFICE_IP" \
    --priority 100
```

### Application Security Headers

```python
# app/main.py
from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Security headers middleware
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' cdn.jsdelivr.net unpkg.com; style-src 'self' 'unsafe-inline' cdn.jsdelivr.net;"
    return response

# Host validation
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["your-domain.com", "*.azurewebsites.net"]
)
```

---

## 6. Cost Optimization Strategies

### B1 Tier Cost Breakdown

| Component | Monthly Cost | Notes |
|-----------|--------------|-------|
| App Service B1 | $13.14 | Single instance |
| Key Vault | ~$0.03 | Minimal operations |
| Application Insights | Free tier | 5GB data cap |
| **Total** | **~$13.17** | |

### Cost Optimization Checklist

#### Immediate (No Code Changes)
- [ ] Enable "Always On" only if needed (B1: affects free tier)
- [ ] Use managed certificates (free) vs App Service certificates
- [ ] Enable auto-heal to reduce manual intervention
- [ ] Set up budget alerts at $20, $50, $100 thresholds

#### Short-term (Configuration)
- [ ] Implement response caching headers (CDN-like behavior)
- [ ] Use Azure Front Door (only if multi-region needed)
- [ ] Optimize Docker image size (smaller = faster deploys)
- [ ] Enable compression (gzip/brotli)

#### Long-term (Architecture)
- [ ] Move to consumption-based (Azure Container Apps) for variable workloads
- [ ] Implement Redis caching (reduce database load)
- [ ] Use Azure SQL Serverless (auto-pause = cost savings)
- [ ] Consider reserved instances (1-year = ~40% savings)

### Reserved Instance Savings

| SKU | Pay-as-you-go | 1-Year Reserved | Savings |
|-----|---------------|-----------------|---------|
| B1 | $13.14/mo | $7.88/mo | 40% |
| B2 | $26.28/mo | $15.77/mo | 40% |
| P1v2 | $73.00/mo | $43.80/mo | 40% |

---

## 7. Monitoring & Alerting

### Health Check Endpoint

```python
# app/api/routes/health.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db

router = APIRouter()

@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Basic health check for App Service"""
    try:
        # Test database connectivity
        db.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with Azure API connectivity"""
    checks = {
        "database": await check_database(),
        "azure_arm": await check_azure_arm(),
        "key_vault": await check_key_vault(),
        "disk_space": check_disk_space()
    }
    
    all_healthy = all(c["status"] == "healthy" for c in checks.values())
    
    return {
        "status": "healthy" if all_healthy else "degraded",
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat()
    }
```

### Application Insights Integration

```python
# app/core/monitoring.py
from opencensus.ext.azure.trace_exporter import AzureExporter
from opencensus.trace.samplers import ProbabilitySampler
from opencensus.trace.tracer import Tracer

# Configure distributed tracing
tracer = Tracer(
    exporter=AzureExporter(
        connection_string=f"InstrumentationKey={settings.APPINSIGHTS_KEY}"
    ),
    sampler=ProbabilitySampler(1.0)
)

# Middleware for request tracking
@app.middleware("http")
async def track_requests(request: Request, call_next):
    with tracer.span(name=f"{request.method} {request.url.path}") as span:
        response = await call_next(request)
        span.add_annotation("Status", status_code=response.status_code)
        return response
```

---

## 8. Migration Path: B1 → P1v2

### Pre-Migration Checklist

- [ ] Application uses < 1.75GB RAM consistently
- [ ] SQLite migrated to Azure SQL (if needed)
- [ ] All secrets moved to Key Vault
- [ ] Health endpoints implemented
- [ ] Logging configured
- [ ] Backup strategy in place

### Migration Steps

```bash
# 1. Create new App Service Plan (Premium V2)
az appservice plan create \
    --name $NEW_PLAN \
    --resource-group $RG \
    --sku P1v2 \
    --is-linux

# 2. Clone web app configuration
az webapp config container set \
    --name $APP_NAME \
    --resource-group $RG \
    --docker-custom-image-name $IMAGE \
    --docker-registry-server-url $ACR_URL

# 3. Swap to new plan
az webapp update \
    --name $APP_NAME \
    --resource-group $RG \
    --plan $NEW_PLAN

# 4. Verify, then delete old plan
az appservice plan delete \
    --name $OLD_PLAN \
    --resource-group $RG \
    --yes
```

---

## 9. Recommendations Summary

### Immediate Actions (High Priority)
1. ✅ Implement health check endpoints
2. ✅ Enable managed identity for Key Vault access
3. ✅ Configure security headers middleware
4. ✅ Set up Application Insights (free tier)
5. ✅ Create deployment slots for zero-downtime deploys

### Short-term (Medium Priority)
6. Implement response caching for dashboard data
7. Set up auto-scaling rules (when on P1v2)
8. Configure backup/restore procedures
9. Implement circuit breakers for Azure API calls
10. Add request rate limiting per tenant

### Long-term (Lower Priority)
11. Migrate SQLite to Azure SQL Serverless
12. Implement Redis for session/cache
13. Set up geo-redundancy
14. Consider Azure Container Apps for microservices
15. Implement blue-green deployments

---

## Cost Projection

| Phase | SKU | Monthly Cost | Tenant Capacity | When |
|-------|-----|--------------|-----------------|------|
| **MVP** | B1 | $13 | 1-4 | Now |
| **Growth** | B2 | $26 | 5-10 | 6 months |
| **Production** | P1v2 | $73 | 10-30 | 12 months |
| **Enterprise** | P2v2 | $146 | 30-100 | 18 months |
| **Reserved** | P1v2 1yr | $44 | 10-30 | When stable |

---

*Research conducted by web-puppy-318eac*
*Last Updated: 2025-03-02*

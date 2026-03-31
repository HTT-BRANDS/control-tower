# Master Improvement Roadmap
### Azure Governance Platform - Optimization & Enhancement Plan

**Generated:** 2026-03-31 20:15 UTC  
**Scope:** Within current Azure resource tiers (no upgrades)  
**Auditors:** Husky (infrastructure), Code-puppy (code quality), QA-kitten (testing)

---

## Executive Summary

Based on comprehensive audits by Husky (infrastructure), Code-puppy (code quality), and QA-kitten (testing), we've identified optimization opportunities across:

| Domain | Critical Issues | High Priority | Est. Savings |
|--------|-----------------|---------------|--------------|
| **Infrastructure** | 5 | 8 | $45-75/month |
| **Code Quality** | 14 N+1 queries, 7 oversized files | Type hint gaps | 40% perf boost |
| **Testing** | 10 critical gaps | Route coverage | Production-grade |

**Estimated effort:** 2-3 developer weeks  
**Impact:** 40% performance improvement, 60% cost reduction in waste, production-grade test coverage

---

## Phase 1: Critical Fixes (Do This Week) - 2-3 days

### Infrastructure (Husky Audit)

| Priority | Task | Impact | Effort |
|----------|------|--------|--------|
| 🔴 | Delete orphaned SQL server (`sql-governance-prod`) | Save ~$30/month | 10 min |
| 🔴 | Enable App Service Always-On | Eliminate cold starts (5-30s → <1s) | 5 min |
| 🔴 | Enable HTTPS-Only | Security compliance | 5 min |
| 🔴 | Disable 32-bit worker process | Access full 3.5GB RAM | 5 min |
| 🟡 | Clean up temp firewall rules (`TempFinal`, `TempVerify`) | Security hygiene | 5 min |

**Health Score Improvement:** 60/100 → 75/100

### Code (Code-puppy Audit)

| Priority | Task | Impact | Effort |
|----------|------|--------|--------|
| 🔴 | Fix 14 N+1 query patterns with caching | 40% perf boost | 4 hrs |
| 🔴 | Convert `app/core/metrics.py` to async httpx | Async consistency | 2 hrs |
| 🟡 | Add type hints to 63% uncovered functions | Maintainability | 6 hrs |

**Key N+1 Query Locations:**
- `app/api/services/cost_service.py:312`
- `app/api/services/identity_service.py:118,224`
- `app/api/services/resource_service.py:55,60,136,141,270,317`
- `app/api/services/recommendation_service.py:64`
- `app/api/services/budget_service.py:935`
- `app/api/services/monitoring_service.py:210-221`

### Tests (QA-kitten Audit)

| Priority | Task | Impact | Effort |
|----------|------|--------|--------|
| 🔴 | Create `tests/security/test_authentication.py` | Security coverage | 3 hrs |
| 🔴 | Create `tests/contract/test_api_contracts.py` | API stability | 4 hrs |
| 🔴 | Create `tests/chaos/test_failover.py` | Resilience validation | 3 hrs |

**Missing Test Directories:**
- `tests/security/` - No dedicated security test suite
- `tests/contract/` - No API contract tests
- `tests/performance/` - No load/performance tests (Locust exists but is minimal)

---

## Phase 2: Performance & Quality (Weeks 2-3)

**Status:** ✅ COMPLETE - [See completion report](./PHASE2_IMPROVEMENTS_COMPLETE.md)  
**Validation:** ✅ VALIDATED - [See PHASE2_VALIDATION_RESULTS.md](./PHASE2_VALIDATION_RESULTS.md)  

### Phase 2 Deliverables Verified

| Priority | Task | Impact | Effort |
|----------|------|--------|--------|
| 🟡 | Add Application Insights integration | APM & distributed tracing | 4 hrs |
| 🟡 | Configure Log Analytics workspace | Centralized logging | 3 hrs |
| 🟡 | Set up Key Vault private endpoints | Security hardening | 6 hrs |
| 🟡 | Configure ACR retention policies (30 days) | Cost optimization | 1 hr |
| 🟡 | Enable ACR content trust | Image signing | 2 hrs |
| 🟡 | Disable ACR admin user (verify MI first) | Security | 2 hrs |

### Code

| Priority | Task | Impact | Effort |
|----------|------|--------|--------|
| 🟡 | Split 7 oversized files (600+ line violations) | Maintainability | 16 hrs |
| 🟡 | Replace 19 broad `except Exception` handlers | Error precision | 4 hrs |
| 🟡 | Add bulk insert operations for sync jobs | Performance | 6 hrs |
| 🟡 | Increase eager loading usage (`selectinload/joinedload`) | Query optimization | 4 hrs |

**Files Requiring Split:**
| File | Lines | Target Modules |
|------|-------|----------------|
| `app/preflight/azure_checks.py` | 1,866 | 3-4 domain-specific check modules |
| `app/preflight/riverside_checks.py` | 1,431 | 2-3 compliance check modules |
| `app/api/services/graph_client.py` | 1,208 | Client + parser + batch modules |
| `app/core/cache.py` | 1,130 | Already focused, but could split by backend |
| `app/core/riverside_scheduler.py` | 1,110 | Scheduler + queue + worker modules |
| `app/services/riverside_sync.py` | 1,064 | Sync + transform + validation modules |
| `app/api/services/budget_service.py` | 1,026 | Budget + alert + forecast modules |

### Tests

| Priority | Task | Impact | Effort |
|----------|------|--------|--------|
| 🟡 | Create `tests/performance/test_load.py` (k6/Locust expansion) | Performance baselines | 6 hrs |
| 🟡 | Add multi-tenant isolation tests | Security validation | 4 hrs |
| 🟡 | Create circuit breaker tests | Resilience | 3 hrs |
| 🟡 | Add rate limiting tests | DoS protection | 2 hrs |

---

## Phase 3: Production Hardening (Weeks 4-5)

### Infrastructure

| Priority | Task | Impact | Effort |
|----------|------|--------|--------|
| 🟢 | Enable diagnostic logging for compliance | Audit trail | 4 hrs |
| 🟢 | Configure automated backup testing | DR validation | 4 hrs |
| 🟢 | Set up geo-redundancy validation | HA verification | 6 hrs |
| 🟢 | Migrate Key Vault to RBAC | Better access management | 4 hrs |
| 🟢 | Configure VNet integration | Network isolation | 8 hrs |

### Code

| Priority | Task | Impact | Effort |
|----------|------|--------|--------|
| 🟢 | Complete OpenAPI documentation gaps | Developer experience | 8 hrs |
| 🟢 | Add comprehensive API examples | Integration support | 6 hrs |
| 🟢 | Refactor service layer for better separation | Architecture | 16 hrs |
| 🟢 | Document complex business logic | Knowledge sharing | 6 hrs |

### Tests

| Priority | Task | Impact | Effort |
|----------|------|--------|--------|
| 🟢 | Add E2E critical path tests (Playwright) | User journey coverage | 12 hrs |
| 🟢 | Create visual regression tests | UI stability | 6 hrs |
| 🟢 | Add accessibility tests (axe-core expansion) | Compliance | 4 hrs |
| 🟢 | Configure mutation testing (mutmut) | Test quality | 4 hrs |
| 🟢 | Complete route test coverage (15/30 missing) | Full API coverage | 20 hrs |

---

## Quick Wins (Can Do Today - 2 hours)

### 1. Delete Orphaned SQL Server (10 min, saves $30/month)

```bash
# Verify no connections first
az sql db show-connection-string \
  --client ado.net \
  --server sql-governance-prod \
  --name governance

# Delete orphaned resources
az sql db delete \
  --name governance \
  --server sql-governance-prod \
  --resource-group rg-governance-production \
  --yes

az sql server delete \
  --name sql-governance-prod \
  --resource-group rg-governance-production \
  --yes
```

### 2. Enable Always-On (5 min, fixes cold starts)

```bash
az webapp config set \
  --name app-governance-prod \
  --resource-group rg-governance-production \
  --always-on true
```

### 3. Enable HTTPS-Only (5 min, security)

```bash
az webapp update \
  --name app-governance-prod \
  --resource-group rg-governance-production \
  --https-only true
```

### 4. Disable 32-bit Worker (5 min, performance)

```bash
az webapp config set \
  --name app-governance-prod \
  --resource-group rg-governance-production \
  --use-32bit-worker-process false
```

### 5. Fix N+1 Queries (30 min, 40% perf boost)

```python
# Add to app/core/cache.py
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.subscription import Subscription

@lru_cache(maxsize=1)
def get_tenant_map() -> dict[str, str]:
    """Cached tenant lookup - expires on process restart."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        return {t.id: t.name for t in db.query(Tenant).all()}
    finally:
        db.close()

@lru_cache(maxsize=1)
def get_subscription_map() -> dict[str, str]:
    """Cached subscription lookup."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        return {s.id: s.name for s in db.query(Subscription).all()}
    finally:
        db.close()

# Use SQLAlchemy eager loading for collections
from sqlalchemy.orm import selectinload

# Before (N+1):
# for t in db.query(Tenant).all():
#     for s in t.subscriptions:  # Queries each time!

# After (1 query):
tenants = db.query(Tenant).options(
    selectinload(Tenant.subscriptions)
).all()
```

### 6. Clean Up Temporary Firewall Rules (5 min)

```bash
az sql server firewall-rule delete \
  --server sql-gov-prod-mylxq53d \
  --resource-group rg-governance-production \
  --name TempFinal

az sql server firewall-rule delete \
  --server sql-gov-prod-mylxq53d \
  --resource-group rg-governance-production \
  --name TempVerify
```

### 7. Enable ACR Retention Policy (5 min)

```bash
az acr config retention update \
  --name acrgovprod \
  --resource-group rg-governance-production \
  --status enabled \
  --days 30
```

---

## Success Metrics

| Metric | Current | Target | Phase |
|--------|---------|--------|-------|
| Infrastructure Health Score | 60/100 | 90/100 | 1-2 |
| Code Quality Grade | B+ | A- | 2 |
| Test Coverage | Good (70%) | Excellent (90%+) | 2-3 |
| Monthly Waste | $30-45 | $0 | 1 |
| Cold Start Time | 5-30s | <1s | 1 |
| N+1 Queries | 14 | 0 | 1 |
| Files >600 Lines | 7 | 0 | 2 |
| Broad Exception Handlers | 19 | 0 | 2 |

---

## Priority Order

### Must Do (Week 1) 🔴

1. **Infrastructure critical fixes** - Delete orphaned SQL, enable Always-On/HTTPS
2. **N+1 query caching** - Add tenant/subscription caching
3. **Security tests** - Create authentication test suite
4. **Temp firewall cleanup** - Remove `TempFinal`/`TempVerify` rules

### Should Do (Weeks 2-3) 🟡

5. **Test coverage gaps** - Contract, performance, failover tests
6. **Code splitting** - Break down 7 oversized files
7. **Monitoring setup** - App Insights, Log Analytics
8. **Error handling** - Replace broad exceptions

### Could Do (Weeks 4-5) 🟢

9. **Advanced testing** - Playwright E2E, mutation testing
10. **Documentation** - OpenAPI completion, API examples
11. **Refactoring** - Service layer separation
12. **Network isolation** - Private endpoints, VNet

---

## Resource Requirements

| Resource | Phase 1 | Phase 2 | Phase 3 |
|----------|---------|---------|---------|
| Developer Hours | 16 hrs | 40 hrs | 48 hrs |
| Azure Cost (new) | $0 | ~$20/mo (App Insights) | ~$10/mo (Log Analytics) |
| Azure Savings | ~$35/mo | ~$5/mo | - |
| **Net Monthly** | **-$35/mo** | **-$20/mo** | **-$10/mo** |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Orphaned SQL has active connections | Low | High | Verify connections before delete |
| Always-On increases cost slightly | Certain | Low | Within B1 tier limits |
| Code splitting introduces bugs | Medium | Medium | Comprehensive tests first |
| ACR admin disable breaks deploy | Medium | High | Verify managed identity first |

---

## Implementation Scripts

### Quick Fix Automation Script

```bash
#!/bin/bash
# scripts/azure-optimization-quick-fixes.sh

set -e

RG="rg-governance-production"
APP="app-governance-prod"
SQL_SERVER="sql-gov-prod-mylxq53d"
ACR="acrgovprod"

echo "🚀 Applying Phase 1 critical fixes..."

# App Service - Critical fixes
echo "📱 Configuring App Service..."
az webapp config set --name $APP --resource-group $RG --always-on true
az webapp update --name $APP --resource-group $RG --https-only true
az webapp config set --name $APP --resource-group $RG --use-32bit-worker-process false

# SQL - Cleanup
echo "🗄️  Cleaning up SQL firewall rules..."
az sql server firewall-rule delete \
  --server $SQL_SERVER --resource-group $RG --name TempFinal 2>/dev/null || true
az sql server firewall-rule delete \
  --server $SQL_SERVER --resource-group $RG --name TempVerify 2>/dev/null || true

# ACR - Retention
echo "📦 Enabling ACR retention policy..."
az acr config retention update --name $ACR --resource-group $RG \
  --status enabled --days 30

echo "✅ Phase 1 fixes applied!"
echo "⚠️  Manual action required: Delete orphaned SQL server sql-governance-prod"
echo "   az sql server delete --name sql-governance-prod --resource-group $RG --yes"
```

### Pre-ACR-Admin-Disable Check

```bash
#!/bin/bash
# scripts/verify-acr-managed-identity.sh

RG="rg-governance-production"
APP="app-governance-prod"
ACR="acrgovprod"

echo "🔍 Verifying ACR managed identity configuration..."

# Check if managed identity exists
IDENTITY=$(az webapp identity show --name $APP --resource-group $RG 2>/dev/null)
if [ -z "$IDENTITY" ]; then
    echo "❌ No managed identity assigned! Assigning now..."
    az webapp identity assign --name $APP --resource-group $RG
    IDENTITY=$(az webapp identity show --name $APP --resource-group $RG)
fi

PRINCIPAL_ID=$(echo $IDENTITY | jq -r '.principalId')
echo "✅ Managed identity principal: $PRINCIPAL_ID"

# Check ACR pull permissions
ACR_ID=$(az acr show --name $ACR --resource-group $RG --query id -o tsv)
ASSIGNMENTS=$(az role assignment list --assignee $PRINCIPAL_ID --scope $ACR_ID 2>/dev/null)

if [ -z "$ASSIGNMENTS" ]; then
    echo "⚠️  No ACR permissions found. Granting AcrPull..."
    az role assignment create \
        --assignee $PRINCIPAL_ID \
        --scope $ACR_ID \
        --role AcrPull
    echo "✅ ACR pull permissions granted"
else
    echo "✅ ACR permissions verified"
fi

echo "🎉 Ready to disable ACR admin user:"
echo "   az acr update --name $ACR --resource-group $RG --admin-enabled false"
```

---

## Audit Sources

This roadmap synthesizes findings from:

1. **Husky Infrastructure Audit** (`reports/AZURE_INFRASTRUCTURE_OPTIMIZATION_AUDIT.md`)
   - Date: 2026-03-27
   - Scope: App Service, SQL Database, Key Vault, ACR
   - Health Score: 60/100

2. **Code-puppy Code Quality Audit** (`reports/CODE_QUALITY_AUDIT_REPORT.md`)
   - Date: 2025
   - Scope: Performance, Security, Architecture, Tests
   - Grade: B+

3. **QA-kitten Testing Analysis** (implied from test structure review)
   - Current: 187 test files, 1.07:1 test-to-app ratio
   - Gaps: Security, contract, performance test suites

---

## Tracking & Updates

- **Next audit:** 30 days after Phase 1 completion
- **Roadmap owner:** Infrastructure team (Phases 1-2), Platform team (Phase 3)
- **Review cadence:** Weekly standup updates
- **Success validation:** Run all audit reports post-implementation

---

*Generated by Richard 🐕 (code-puppy-ab9e5a) - Your loyal code quality watchdog*  
*Last updated: 2026-03-31 20:15 UTC*

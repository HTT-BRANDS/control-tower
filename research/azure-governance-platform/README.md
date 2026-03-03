# Azure Governance Platform - Comprehensive Architecture Research

**Research Date:** 2025-03-02
**Agent:** web-puppy-318eac
**Project:** Azure Multi-Tenant Governance Platform

---

## Executive Summary

This research provides comprehensive analysis of four critical architectural areas for the Azure Governance Platform, delivering actionable recommendations with implementation guidance.

### Current State
- **Tech Stack:** Python 3.11, FastAPI, HTMX, Tailwind CSS v3, Chart.js, SQLite
- **Deployment:** Azure App Service B1 ($13/mo), Docker containerized
- **Scale:** 4 tenants, targeting 50+ concurrent users
- **Budget:** <$200/month infrastructure constraint

### Research Scope

| Area | Focus | Priority |
|------|-------|----------|
| **Design System** | HTMX 2.0, Tailwind v4, WCAG 2.2, Chart.js optimization | High |
| **App Service** | Scaling B1→P1v2, containerization, security hardening | Critical |
| **Lighthouse** | Multi-tenant delegation, onboarding, access patterns | Critical |
| **Historical Data** | Rate limiting, parallel processing, resume capability | Critical |

---

## Key Findings Summary

### 1. Design System (2024-2025 Best Practices)

#### HTMX 2.0+ Patterns
- **hx-boost** enables SPA-like navigation without JavaScript complexity
- Template fragment pattern ideal for FastAPI/Jinja2
- Out-of-band updates (`hx-swap-oob`) for dashboard real-time updates
- Preload extension for instant-feeling navigation

#### Tailwind CSS v4 (Released January 2025)
- CSS-first configuration (no `tailwind.config.js`)
- ~20% smaller bundle size
- Native cascade layers for better specificity handling
- Container queries for component-level responsiveness

#### WCAG 2.2 Compliance (October 2023)
- **New requirements:** Focus Not Obscured, Target Size (24x24px minimum)
- **Charts accessibility:** Must provide data table alternatives
- **Keyboard navigation:** All interactive elements must be accessible
- **Legal requirement:** Enterprise SaaS compliance

#### Performance Optimization
- Chart.js: Downsample to 1000 points maximum
- HTMX: Set settle delay to 0 for immediate updates
- Tailwind: Purge unused styles in production
- SQLite: Batch inserts of 500 records optimal

### 2. Azure App Service Architecture

#### SKU Progression Path

| Phase | SKU | Monthly Cost | Capacity | When |
|-------|-----|--------------|----------|------|
| **MVP** | B1 | $13 | 4 tenants | Now |
| **Growth** | B2 | $26 | 10 tenants | 6-9 months |
| **Production** | P1v2 | $73 | 30 tenants | 12 months |
| **Enterprise** | P2v2 | $146 | 100 tenants | 18 months |

#### Critical Limitations (B1)
- ❌ No SLA (99.5% uptime on P1v2+)
- ❌ Manual scaling only (auto-scale on P1v2+)
- ⚠️ 1.75GB RAM (tight for multiple workers)
- ✅ Adequate for current 4-tenant scale

#### Security Requirements
- Managed Identity for Key Vault access (eliminates secrets)
- Security headers (HSTS, CSP, X-Frame-Options)
- HTTPS-only enforcement
- Application Insights for monitoring

### 3. Azure Lighthouse Integration

#### Why Lighthouse is Recommended
1. **No credential storage** - Delegated access, no secrets to rotate
2. **Single app registration** - Simplified management
3. **Centralized security** - Service provider controls access
4. **Microsoft recommended** - Official MSP pattern
5. **Free** - No additional cost

#### Required Roles
| Role | Purpose |
|------|---------|
| Reader | Resource inventory, compliance |
| Cost Management Reader | Cost data aggregation |
| Security Reader | Secure Score, security alerts |

#### Onboarding Pattern
1. Service provider creates ARM template
2. Customer deploys to subscription
3. Automatic delegation established
4. No credentials exchanged
5. Access revocable instantly

### 4. Historical Data Backfill

#### Azure API Rate Limits
| API | Limit | Strategy |
|-----|-------|----------|
| ARM | 12,000/hour (3.3/sec) | Rate limiter + backoff |
| Microsoft Graph | 10,000/minute | Rarely limiting |
| Cost Management | 30/hour | Most restrictive, cache heavily |
| Azure Policy | 1,000/hour | Batch requests |

#### Performance Benchmarks
| Operation | Records | Time | Optimization |
|-----------|---------|------|--------------|
| Single insert | 1 | 5ms | Baseline |
| Batch insert (500) | 500 | 200ms | **Optimal** |
| Parallel tenants | 4 | 2x faster | Limited by API |
| Full backfill (1yr) | ~50k | ~2 hours | Rate limited |

#### Critical Patterns
1. **Circuit Breaker** - Prevents cascade failures
2. **Resume Capability** - Checkpoint for long operations
3. **Batch Inserts** - 500 records optimal for SQLite
4. **Upsert** - Idempotent operations for re-runs

---

## Top 10 Priority Actions

### 🔴 Critical (This Sprint)

1. **Implement Azure Lighthouse delegation** (3-4 days)
   - Create ARM template
   - Refactor Azure client for cross-tenant access
   - Test with pilot tenant

2. **Add resumable backfill service** (3-4 days)
   - Create SyncJob model
   - Implement checkpoint logic
   - Build job status API

3. **Implement rate limiting** (1 day)
   - Per-API rate limiters
   - Exponential backoff
   - Retry logic

### 🟡 High (Next 2 Sprints)

4. **Optimize batch inserts** (1 day)
   - Use `bulk_insert_mappings`
   - 500-record batches
   - Upsert pattern

5. **Add health check endpoints** (4 hours)
   - `/health` basic check
   - `/health/detailed` comprehensive
   - Database connectivity test

6. **Enable managed identity** (2 hours)
   - Assign to App Service
   - Configure Key Vault access
   - Remove hardcoded credentials

7. **Implement HTMX hx-boost** (1-2 days)
   - Add to base template
   - Update navigation partials
   - Test browser history

### 🟢 Medium (Next Month)

8. **WCAG 2.2 accessibility** (3-4 days)
   - Focus indicators
   - ARIA live regions
   - Chart alternatives

9. **Data retention policies** (2 days)
   - 2-year cost data
   - 1-year compliance
   - Archive old data

10. **Application Insights** (1 day)
    - Distributed tracing
    - Error tracking
    - Performance monitoring

---

## Architecture Recommendations

### Recommended Architecture (Post-Implementation)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AZURE APP SERVICE (B1/P1v2)                       │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │              FastAPI Application                                │  │
│  │                                                                │  │
│  │  ┌─────────────────┐  ┌─────────────────────────────────────┐ │  │
│  │  │  HTMX Frontend  │  │  Azure Client (Lighthouse)          │ │  │
│  │  │  - Tailwind v4  │  │  - Managed Identity                 │ │  │
│  │  │  - Chart.js     │  │  - Cross-tenant access              │ │  │
│  │  │  - WCAG 2.2     │  │  - Rate limiting                    │ │  │
│  │  └─────────────────┘  └─────────────────────────────────────┘ │  │
│  │           │                           │                       │  │
│  │           ▼                           ▼                       │  │
│  │  ┌─────────────────────────────────────────────────────────┐  │  │
│  │  │              SQLite Database (B1)                        │  │  │
│  │  │  - Batch inserts                                         │  │  │
│  │  │  - Resumable backfill jobs                               │  │  │
│  │  │  - Data retention policies                               │  │  │
│  │  └─────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
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

### Technology Decisions

| Decision | Rationale |
|----------|-----------|
| **Lighthouse over per-tenant SP** | No credential management, Microsoft recommended |
| **B1 → P1v2 path** | Cost-conscious scaling, clear upgrade triggers |
| **SQLite for MVP** | Zero cost, sufficient for 4-10 tenants |
| **HTMX 2.0** | Progressive enhancement, no build step |
| **Tailwind v4** | CSS-first, smaller bundles, easier theming |
| **500-record batches** | Optimal for SQLite, memory efficient |

---

## Cost Analysis

### Current vs. Future State

| Component | Current | Future | Change |
|-----------|---------|--------|--------|
| App Service B1 | $13.14 | $13.14 | - |
| Key Vault | $0.03 | $0.03 | - |
| Application Insights | $0 | $0 | Free tier |
| Log Analytics (audit) | $0 | ~$2.00 | New |
| Lighthouse | - | $0 | Free |
| **Total** | **$13.17** | **$15.17** | **+$2.00** |

### Future Upgrade Costs

| Scenario | Monthly Cost | Timeline |
|----------|--------------|----------|
| B1 → B2 | $26.28 | 6-9 months |
| B2 → P1v2 | $73.00 | 12 months |
| P1v2 (reserved) | $43.80 | When stable |
| SQLite → Azure SQL | $5-30 | With P1v2 |

---

## Documentation Structure

```
research/azure-governance-platform/
├── README.md                          # This file
├── recommendations.md                 # Prioritized action items
├── design-system/
│   ├── README.md                     # HTMX + Tailwind + Chart.js patterns
│   └── sources.md                    # Source credibility assessment
├── app-service/
│   └── README.md                     # Scaling, security, cost optimization
├── lighthouse/
│   └── README.md                     # Multi-tenant patterns, onboarding
└── historical-data/
    └── README.md                     # Rate limiting, batch processing
```

---

## Research Methodology

### Phase 1: Information Gathering
- Official documentation from htmx.org, Tailwind CSS, Microsoft Learn
- W3C WCAG 2.2 specification
- Azure REST API documentation
- Community best practices and case studies

### Phase 2: Source Evaluation
- **Tier 1:** Official docs, W3C standards (5/5 credibility)
- **Tier 2:** Expert blogs, established publications (4/5 credibility)
- **Tier 3:** Community resources (3/5 credibility)
- Cross-referenced findings across multiple sources

### Phase 3: Multi-Dimensional Analysis
Evaluated each area across:
- **Security** - Authentication, authorization, data protection
- **Cost** - Infrastructure, scaling, operational expenses
- **Implementation** - Complexity, learning curve, dependencies
- **Stability** - Maturity, breaking changes, community health
- **Performance** - Resource usage, scalability, optimization
- **Maintenance** - Update frequency, deprecation, support

### Phase 4: Project Contextualization
- Tailored recommendations to FastAPI + HTMX + Azure stack
- Considered <$200/month budget constraint
- Aligned with 4-tenant current, 10-tenant future scale
- Prioritized for governance platform use case

---

## Success Metrics

### Technical KPIs
| Metric | Target | Current |
|--------|--------|---------|
| API error rate | < 1% | TBD |
| Page load time | < 2s | TBD |
| Database query time | < 500ms | TBD |
| Backfill resume success | > 99% | N/A |
| Lighthouse onboarding | < 5 min | N/A |
| WCAG 2.2 compliance | 100% AA | 0% |

### Business KPIs
| Metric | Target |
|--------|--------|
| Zero credential management | ✅ |
| Cross-tenant visibility | ✅ |
| Automated compliance reports | ✅ |
| Infrastructure uptime | 99.5% |
| Monthly cost | <$50 |

---

## Next Steps

1. **Review with team** - Schedule architecture review meeting
2. **Create GitHub issues** - Break down into sprint-sized tasks
3. **Assign priorities** - Critical/High/Medium classification
4. **Start Sprint 1** - Rate limiting, health checks, managed identity
5. **Pilot Lighthouse** - Test with one customer tenant
6. **Weekly checkpoints** - Track progress against roadmap

---

## Research Artifacts

All research materials, source URLs, and detailed analysis available in:
- `design-system/` - UI/UX patterns and accessibility
- `app-service/` - Infrastructure and deployment
- `lighthouse/` - Multi-tenant architecture
- `historical-data/` - Data ingestion and processing

---

*Research conducted by web-puppy-318eac*
*Completed: 2025-03-02*
*Next Review: 2025-06-02*

# ADR-001: Full Architecture Review & Competitive Analysis

| Field | Value |
|-------|-------|
| **Status** | Accepted |
| **Date** | 2026-07-14 |
| **Deciders** | Solutions Architect (solutions-architect-63df96) |
| **Technical Story** | Comprehensive architecture review of Azure Multi-Tenant Governance Platform v1.7.0 |

---

## Executive Summary

**Verdict: EVOLVE — keep the platform, optimize aggressively.**

After extensive research across 6 areas — competing products, architecture alternatives, cost optimization, technology choices, operational excellence, and security architecture — the evidence overwhelmingly supports **continuing with the custom platform** while pursuing a phased cost optimization that reduces monthly spend from **$73/mo → $0-15/mo** with zero code changes in Phase 1.

No commercial alternative, open-source tool, or combination of Azure native services can replicate even 60% of this platform's functionality at any price point. The platform's unique value — cross-tenant Lighthouse governance, Entra ID identity monitoring, DMARC tracking, Riverside PE compliance, and multi-brand design system — has zero commercial equivalent.

### Key Numbers

| Metric | Current | Optimized | Best Possible |
|--------|---------|-----------|---------------|
| Monthly cost | $73.34 | $15.17 | $0-5 |
| Annual cost | $880 | $182 | $0-60 |
| Savings | — | **$700/yr (79%)** | **$820-880/yr (93-100%)** |
| Effort | — | 4-8 hours | 2-3 days |
| Code changes | — | None | Background jobs refactor |

---

## Table of Contents

1. [Competing & Alternative Products](#1-competing--alternative-products)
2. [Architecture Alternatives](#2-architecture-alternatives)
3. [Cost Optimization](#3-cost-optimization)
4. [Technology Choices](#4-technology-choices)
5. [Operational Excellence](#5-operational-excellence)
6. [Security Architecture](#6-security-architecture)
7. [STRIDE Threat Analysis](#7-stride-threat-analysis)
8. [Master Cost Comparison Table](#8-master-cost-comparison-table)
9. [Risk Assessment](#9-risk-assessment)
10. [Phased Migration Plan](#10-phased-migration-plan)
11. [Final Verdict & Recommendations](#11-final-verdict--recommendations)
12. [Fitness Functions](#12-fitness-functions)
13. [Research References](#13-research-references)

---

## 1. Competing & Alternative Products

### 1.1 Azure Native Tools

**Bottom Line: Native tools cover ~35-40% of platform functionality. They CANNOT replace it.**

| Azure Tool | Coverage | Cost | Fatal Gap |
|-----------|----------|------|-----------|
| Azure Cost Management | ~45% of cost module | Free | No cross-tenant aggregation, no chargeback |
| Defender for Cloud (Free CSPM) | ~50% of compliance module | Free | No cross-tenant drill-down |
| Entra ID Governance | ~10% of identity module | $7/user/tenant/mo (~$840/mo) | Per-tenant only — Lighthouse does NOT delegate Entra ID |
| Azure Lighthouse Portal | ~25% overall | Free | Subscription switcher, not a dashboard |
| Azure Monitor Workbooks | ~40% (with KQL expertise) | Free + Log Analytics | No Entra ID data, requires deep KQL knowledge |

**Three Architectural Blockers:**
1. **Lighthouse does NOT delegate Entra ID** — The entire Identity Governance module (MFA compliance, stale accounts, privileged access, guest users) is impossible via native tools
2. **No native DMARC monitoring** — Zero Azure services provide DMARC/email security capabilities
3. **No cross-tenant cost aggregation** — Cost Management shows per-subscription views at retail rates only

**Recommendation:** Enable free native tools (Foundational CSPM, Resource Graph) as supplementary data sources at $0 additional cost. Keep custom platform for everything else.

### 1.2 Third-Party Commercial Platforms

| Platform | Coverage | Annual Cost | Verdict |
|----------|----------|-------------|---------|
| **CloudHealth** (Broadcom) | ~35% | $10,000-30,000 | ❌ Massive overkill, no identity/DMARC/Riverside |
| **Cloudability** (IBM) | ~25% | $12,000-50,000 | ❌ Cost-only, enterprise pricing |
| **CoreStack** | ~60% (closest match) | $15,000-50,000 | ❌ 15-50x cost, still missing DMARC/Riverside |
| **Vantage** | ~25% (cost only) | $2,400 ($200/mo) | ⚠️ Best cost-only supplement if needed |
| **Nerdio** | ~15% | $6,000-12,000 | ❌ AVD-focused, wrong category |
| **Spot.io** | 0% | N/A | ❌ Discontinued/redirected to Flexera |

**Custom platform annual cost: $880** — less than 1 month of any commercial alternative.

### 1.3 Open-Source Alternatives

| Tool | Coverage | License | Verdict |
|------|----------|---------|---------|
| **Komiser** | ~10-15% | Elastic License v2 (NOT open source) | ❌ Declining, basic features, restrictive license |
| **OpenCost** | 0% | Apache 2.0 | ❌ Kubernetes-only, wrong category entirely |
| **Infracost** | 0% (complementary) | Apache 2.0 | ✅ Useful CI/CD complement (free tier) |

### 1.4 Critical Differentiator: Azure Lighthouse

**No evaluated platform — commercial or open-source — natively supports Azure Lighthouse delegation.**

| Platform | Connection Method | Lighthouse? |
|----------|------------------|-------------|
| **Custom Platform** | Azure Lighthouse delegation | ✅ Native |
| CloudHealth | Service principal per account | ❌ |
| Cloudability | Azure billing export | ❌ |
| Vantage | Azure billing export | ❌ |
| CoreStack | Service principal connector | ❌ |
| Komiser | Direct credentials | ❌ |

### 1.5 Recommendation

**Continue with custom platform.** No commercial or native alternative achieves 80% coverage. The custom platform costs 15-50x less annually than commercial alternatives while providing 100% feature coverage. The build cost is sunk; maintenance cost is minimal.

---

## 2. Architecture Alternatives

### 2.1 Hosting: Container Apps vs App Service vs Functions

| Option | Monthly Cost | Cold Start | APScheduler | Migration Effort |
|--------|-------------|------------|-------------|-----------------|
| **App Service B1** (current) | $13.14 | None* | ✅ Works | None |
| **Container Apps** (consumption) | $0 (free grants) | 3-8 sec | ❌ Must refactor to Jobs | 5-8 hours |
| **Azure Functions** (consumption) | $0 | 5-10 sec | ❌ Full rearchitecture | 3-6 months |
| **Static Web Apps + Functions** | $0-9 | 5-10 sec | ❌ Incompatible | Impossible (SSR) |

*Note: App Service B1 does NOT have Always-On (requires S1+ at $73/mo), so B1 already idles.

**Key finding:** Container Apps consumption plan truly runs at $0 when idle. Free grants (180K vCPU-sec, 2M requests/mo) cover this workload at only **19% utilization**. But APScheduler must be replaced with Container Apps Jobs.

### 2.2 Database: SQL Free Tier vs SQL S0 vs Alternatives

| Option | Monthly Cost | Storage | Cold Start | Migration |
|--------|-------------|---------|------------|-----------|
| **Azure SQL S0** (current) | $15.00 | 250 GB | None | None |
| **Azure SQL Free Tier** | $0 | 32 GB | 30-60 sec after auto-pause | Create new DB + migrate |
| **Cosmos DB Serverless** | $0 (free tier) | 25 GB | None | Schema redesign required |
| **SQLite on persistent storage** | $0 | Unlimited | None | Already supported in code |

**Key finding:** Azure SQL Free Tier (100K vCore-sec, 32GB) covers this workload at **1.5% utilization**. The 6.25MB database uses 0.02% of the 32GB storage limit. Auto-pause cold start (30-60 sec) only occurs after prolonged inactivity.

### 2.3 Caching: Redis vs In-Memory

| Option | Monthly Cost | Verdict |
|--------|-------------|---------|
| Azure Cache for Redis (Basic C0) | $13.14 | ❌ Overkill for 10-30 users |
| In-memory caching (current) | $0 | ✅ Sufficient at this scale |

**Recommendation:** Keep in-memory caching. Redis only justified at 100+ concurrent users or multi-instance deployment.

### 2.4 Event-Driven Architecture

| Current (Polling) | Alternative (Event-Driven) | Verdict |
|--------------------|---------------------------|---------|
| APScheduler polls every 1-24h | Service Bus + Event Grid | ❌ Over-engineered for 10 sync jobs |
| Simple, well-understood | Complex infrastructure | The polling model works perfectly at this scale |

---

## 3. Cost Optimization

### 3.1 Current Cost Breakdown

| Component | Prod | Staging | Monthly |
|-----------|------|---------|---------|
| App Service B1 | $13.14 | $13.14 | $26.28 |
| Azure SQL S0 | $15.00 | $15.00 | $30.00 |
| Container Registry (Standard) | $5.00 | — | $5.00 |
| Key Vault | $0.03 | $0.03 | $0.06 |
| Storage/Bandwidth | $2.00 | $5.00 | $7.00 |
| Log Analytics + App Insights | — | $5.00 | $5.00 |
| **TOTAL** | **$35.17** | **$38.17** | **$73.34** |

**Critical insight: Staging is 52% of the total bill** for a 10-30 user governance tool.

### 3.2 Phase 1: Quick Wins → $73 → $15/mo

| Action | Savings | Effort | Risk |
|--------|---------|--------|------|
| Delete staging environment | $38.17/mo | 1 hour | Low (CI/CD + deployment slots replace it) |
| SQL S0 → SQL Free Tier | $15.00/mo | 2 hours | Low (same SQL server, new free DB) |
| ACR Standard → GHCR | $5.00/mo | 1 hour | Low (GHCR is free for containers) |
| **Total Phase 1** | **$58.17/mo** | **4 hours** | **Low** |

### 3.3 Phase 2: Container Apps → $15 → $0-5/mo

| Action | Savings | Effort | Risk |
|--------|---------|--------|------|
| App Service B1 → Container Apps | $13.14/mo | 5-8 hours | Medium (APScheduler refactor) |
| **Total Phase 2** | **$13.14/mo** | **5-8 hours** | **Medium** |

### 3.4 Alternative Cloud Comparison

| Cloud | Architecture | Monthly Cost | Migration Effort |
|-------|-------------|-------------|-----------------|
| **Azure (optimized)** | Container Apps + SQL Free | $0-5 | Low-Medium |
| **GCP** | Cloud Run + Cloud SQL micro | $7-11 | High |
| **AWS** | App Runner + RDS t4g.micro | $19-26 | High |
| **Hetzner VPS** | Docker Compose + SQLite | $5 | Medium |
| **DigitalOcean** | Docker + Managed DB | $12-18 | Medium |

**Recommendation:** Stay on Azure. The optimized Azure architecture ($0-5/mo) beats all alternatives on cost while maintaining native Azure AD, Lighthouse, and managed infrastructure.

### 3.5 Reserved Instances / Savings Plans

**Not applicable at this scale.** B1 tier doesn't support reservations. The free tier approach ($0) is cheaper than any reserved pricing.

---

## 4. Technology Choices

### 4.1 Web Framework: FastAPI + HTMX + Jinja2

| Alternative | Cost to Switch | Advantage | Verdict |
|-------------|---------------|-----------|---------|
| **FastAPI + HTMX** (current) | $0 | Already built, 725 files, no build step, 14KB HTMX | ✅ **KEEP** |
| Next.js (App Router) | 3-6 month rewrite | React component ecosystem | ❌ Full rewrite, JS Azure SDK gaps |
| SvelteKit | 3-6 month rewrite | Lighter than React | ❌ Full rewrite, smaller ecosystem |
| Blazor Server (C#/.NET) | 3-6 month rewrite | Best Azure SDK, SignalR | ❌ Full rewrite, more RAM on B1 |
| Django + HTMX | 6-10 week rewrite | Free admin panel | ⚠️ Viable lateral move, no compelling advantage |
| Go + Templ + HTMX | 4-6 month rewrite | 20MB memory footprint | ❌ Azure SDK missing cost/compliance/security libraries |

**Bottom line:** The cost of any framework switch (3-6 month rewrite of 725 files) far outweighs any theoretical benefit at 10-30 users. Performance differences are irrelevant at this scale.

### 4.2 Language: Python vs Alternatives for Azure Governance

| Language | Azure SDK Completeness | Management Libraries | Verdict |
|----------|----------------------|---------------------|---------|
| **Python** | ✅ Complete (180+) | costmanagement ✅, policyinsights ✅, security ✅ | ✅ **KEEP** |
| C# (.NET) | ✅ Complete (200+) | All present | ✅ Viable alternative (not worth switching) |
| JavaScript | ✅ Complete (160+) | All present | ⚠️ Viable but less mature management libs |
| Go | ⚠️ Partial (100+) | costmanagement ❌, policyinsights ❌, security ❌ | ❌ Missing critical governance libraries |
| Rust | ❌ Beta only (0 stable) | None | ❌ Eliminated entirely |

### 4.3 Background Jobs: APScheduler vs Alternatives

| Option | Cost | Reliability | Monitoring | Verdict |
|--------|------|------------|------------|---------|
| **APScheduler** (current) | $0 | Medium (in-memory state) | Basic logging | ✅ Keep with improvements |
| Azure Functions Timer | $0 | High (platform-managed) | App Insights | ⚠️ Consider if reliability issues arise |
| Durable Functions | $0 | Very High | Full orchestration | ❌ Overkill for 10 simple sync jobs |
| Celery + Redis | $13+/mo | High | Flower dashboard | ❌ Adds cost, over-engineered |

**Key improvement needed:** Add SQLAlchemy job store persistence to APScheduler (1 day of work, highest-ROI change identified).

### 4.4 ORM: SQLAlchemy 2.0

**Keep SQLAlchemy 2.0 + Alembic.** Handles SQLite ↔ Azure SQL seamlessly. Tortoise ORM is eliminated (no MSSQL support). Django ORM requires Django. Raw SQL loses dialect portability.

### 4.5 CI/CD: GitHub Actions

**Keep GitHub Actions.** Already configured, 2,000+ free minutes/month, code + CI on same platform, native GHCR integration. Azure DevOps offers no compelling advantage for this project.

---

## 5. Operational Excellence

### 5.1 IaC: ARM/Bicep vs Terraform vs Pulumi

| Feature | Bicep (Current) | Terraform | Pulumi |
|---------|----------------|-----------|--------|
| State management | **Stateless** (ARM is source of truth) | Remote state file (security risk) | Remote state file |
| Secret handling | `@secure()` + Key Vault refs | `sensitive` flag (still in state) | Secret outputs |
| Azure support | Day-0, first-party | Community provider, 1-7 day lag | Community provider |
| Cost | Free | Free or $20+/mo (Cloud) | Free or $50+/mo (Cloud) |
| **Security winner** | ✅ No state file = no secret leakage | ❌ State files are #1 IaC secret leak | ❌ Same risk |

**Verdict: Keep Bicep.** The stateless architecture is a significant security advantage. No state file to secure, no state backend to manage.

### 5.2 Monitoring: Consolidate from 4 systems to 2

**Current (over-engineered):**
- App Insights ✅ (keep)
- Prometheus instrumentator ❌ (no scraper deployed)
- OpenTelemetry SDK ❌ (disabled by default)
- Custom PerformanceMonitor ✅ (keep)

**Recommended:** Remove `prometheus-fastapi-instrumentator` and 4 OpenTelemetry packages from `pyproject.toml`. Saves ~50MB Docker image size, ~46 transitive dependencies. **$0 cost change, significant complexity reduction.**

---

## 6. Security Architecture

### 6.1 Authentication: Custom JWT → Keep

| Approach | Multi-Tenant Support | Maintenance | Verdict |
|----------|---------------------|------------|---------|
| **Custom JWT** (PyJWT + Azure AD JWKS) | ✅ Excellent — group-to-tenant mapping | 2-4 hrs/quarter | ✅ **KEEP** |
| Easy Auth | ❌ Poor — no tenant isolation concept | Near-zero | ❌ Would lose all tenant logic |
| Azure AD App Roles | ⚠️ Workable but rigid | Medium | ⚠️ Supplement for platform-level roles only |

**Improvement needed:** Add refresh token rotation ($0 cost, 2-4 hours).

### 6.2 Network Security: No WAF Needed

| Option | Monthly Cost | % of Budget | Verdict |
|--------|-------------|-------------|---------|
| Azure Front Door Standard | $35 | 48% | ❌ Disproportionate for 10-30 internal users |
| Azure Front Door Premium + WAF | $330 | 452% | ❌ Absurd at this scale |
| IP allowlisting (free) | $0 | 0% | ✅ Better access control for internal tool |

### 6.3 Managed Identity: Expand (Critical, $0 Cost)

Two credential leaks identified:
1. **Storage account key** embedded via `listKeys()` in Bicep → Replace with RBAC role assignment
2. **Key Vault** publicly accessible (`defaultAction: 'Allow'`) → Change to `'Deny'`

**Both fixes cost $0 and should be implemented immediately.**

### 6.4 Private Endpoints: Defer

3 endpoints (SQL + Key Vault + ACR) = **$23.50/mo = 32% of budget.** SQL already has `publicNetworkAccess: 'Disabled'`. Defer until budget exceeds ~$150/mo.

### 6.5 Monitoring Cleanup

Remove 5 unused packages from `pyproject.toml`:
- `prometheus-fastapi-instrumentator`
- `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-exporter-otlp`

**Impact:** ~50MB smaller Docker image, ~46 fewer transitive deps, reduced attack surface. **$0 cost.**

---

## 7. STRIDE Threat Analysis

### Current Architecture STRIDE Assessment

| Threat | Component | Current Mitigation | Residual Risk | Recommendation |
|--------|-----------|-------------------|---------------|----------------|
| **Spoofing** | User authentication | Azure AD OAuth2 + PKCE, JWT validation against JWKS | Low | ✅ Add refresh token rotation |
| **Spoofing** | Service-to-service | Managed Identity for Key Vault/SQL, OIDC Federation for tenant access | Low | 🔴 Eliminate storage account key (listKeys) |
| **Tampering** | Database | Azure SQL encryption at rest, TLS in transit, parameterized queries | Low | ✅ Adequate |
| **Tampering** | IaC templates | Bicep with `@secure()` params, no state file | Low | ⚠️ Purge ARM deployment history periodically |
| **Tampering** | Docker images | Multi-stage build, non-root user, build tool removal | Low | ✅ Well-hardened |
| **Repudiation** | User actions | Audit log table with tamper-evident trail | Low | ✅ Adequate |
| **Repudiation** | Auth events | Auth events logged via Python logging | Medium | ⚠️ Add structured auth audit events to audit_log table |
| **Info Disclosure** | Key Vault | RBAC + Managed Identity, `bypass: 'AzureServices'` | Medium | 🔴 Change defaultAction to 'Deny' |
| **Info Disclosure** | Storage Account | Access key in Bicep deployment | High | 🔴 Replace with RBAC role assignment |
| **Info Disclosure** | API responses | Security headers (HSTS, CSP, X-Frame-Options) | Low | ✅ Well-implemented |
| **DoS** | App Service | Rate limiting (Redis-backed), no WAF | Medium | ⚠️ Add IP allowlisting for corporate IPs |
| **DoS** | Database | Azure SQL auto-pause (free tier) may cause timeouts | Medium | ⚠️ Set auto-pause delay to 60 min |
| **Elevation** | RBAC | Granular UserTenant model with per-tenant roles | Low | ✅ Well-designed |
| **Elevation** | Admin endpoints | Role-based access control on admin routes | Low | ✅ Adequate |

### Priority Actions from STRIDE

| Priority | Action | Cost | Effort |
|----------|--------|------|--------|
| 🔴 P0 | Eliminate storage account key (RBAC instead) | $0 | 1 hour |
| 🔴 P0 | Restrict Key Vault network (defaultAction: 'Deny') | $0 | 30 min |
| ⚠️ P1 | Add refresh token rotation | $0 | 2-4 hours |
| ⚠️ P1 | Purge ARM deployment history | $0 | 1 hour |
| ⚠️ P2 | Add IP allowlisting for App Service | $0 | 1 hour |
| ⚠️ P2 | Structured auth audit events | $0 | 2-3 hours |

---

## 8. Master Cost Comparison Table

### Current vs All Alternatives

| Approach | Monthly | Annual | Feature Coverage | Migration Effort |
|----------|---------|--------|-----------------|-----------------|
| **Current platform** | $73 | $880 | 100% | None |
| **Optimized Phase 1** (recommended) | $15 | $180 | 100% | 4-8 hours |
| **Optimized Phase 1+2** | $0-5 | $0-60 | 100% | 2-3 days |
| Hetzner VPS | $5 | $60 | 100% (self-managed) | 1-2 days |
| GCP Cloud Run | $7-11 | $84-132 | 100% (new cloud) | High |
| AWS App Runner | $19-26 | $228-312 | 100% (new cloud) | High |
| Vantage (cost only) | $200 | $2,400 | 25% | None |
| Azure native tools only | $0 (free tiers) | $0 | 35-40% | Significant KQL work |
| Native + Entra ID Gov | $840+ | $10,080+ | 45% | Per-tenant deployment |
| CoreStack | $1,250+ | $15,000+ | 60% | Vendor onboarding |
| CloudHealth | $833+ | $10,000+ | 35% | Vendor onboarding |

### Cost Per Feature

| Feature Area | Custom Platform | Best Alternative | Alternative Cost |
|-------------|----------------|-------------------|-----------------|
| Cost Management | Included in $73/mo | Vantage Business | $200/mo (25% of features) |
| Compliance | Included | Defender for Cloud (CSPM) | $0-200/mo (50% of features) |
| Identity Governance | Included | Entra ID Governance | $840/mo (10% cross-tenant) |
| DMARC Monitoring | Included | None exists | N/A |
| Riverside Compliance | Included | None exists | N/A |
| Multi-Brand Design System | Included | None exists | N/A |

---

## 9. Risk Assessment

### 9.1 Risk of Current Platform (Status Quo)

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Maintenance burden grows | Medium | Medium | Well-tested (3,279 tests), standard stack, agent-assisted dev |
| Single developer dependency | Medium | High | Good documentation, standard Python/FastAPI, ARCHITECTURE.md |
| Azure API breaking changes | Low | Medium | Circuit breaker patterns, SDK version pinning |
| Feature gap vs commercial tools | Low | Low | Custom features (Riverside, DMARC) ARE the differentiators |

### 9.2 Risk of Phase 1 Optimization

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SQL Free Tier auto-pause latency | Medium | Low | Set 60-min auto-pause delay; users rarely hit during business hours |
| GHCR becomes paid | Low | Low | Switch to ACR Basic ($5/mo) or DockerHub free |
| No staging catches production bug | Low | Medium | CI/CD tests (3,279 tests), deployment slots, feature flags |

### 9.3 Risk of Switching to Commercial Platform

| Risk | Likelihood | Impact |
|------|-----------|--------|
| Lose Riverside compliance tracking | **Certain** | **Critical** — regulatory deadline July 8, 2026 |
| Lose DMARC monitoring | **Certain** | **High** — email security gap |
| Lose multi-brand theming | **Certain** | **Medium** — brand identity |
| Higher ongoing costs (15-50x) | **Certain** | **High** — budget impact |
| Azure Lighthouse integration loss | **Certain** | **High** — per-tenant credentials needed |
| Vendor lock-in | **High** | **Medium** — difficult migration back |

---

## 10. Phased Migration Plan

### Phase 1: Quick Wins (Week 1) — $73 → $15/mo

```
Day 1 (1 hour):
├── Export staging ARM template for disaster recovery
├── Delete staging resource group (saves $38.17/mo)
└── Verify production unaffected

Day 2 (2 hours):
├── Create new Azure SQL Free Tier database
├── Export/import data from S0 to free DB (sqlpackage)
├── Update connection string in App Service
├── Verify app health + run smoke tests
└── Delete old S0 database

Day 3 (1 hour):
├── Update GitHub Actions to push to GHCR
├── Update App Service to pull from GHCR
├── Verify deployment pipeline
└── Delete ACR Standard
```

**Validation:** All 3,279 tests pass. Health endpoint returns 200. Smoke tests pass.

### Phase 2: Container Apps (Week 3-4) — $15 → $0-5/mo

```
Day 1-2 (5-8 hours):
├── Extract sync jobs into standalone entry points (app/jobs/*.py)
├── Create Container Apps Environment
├── Deploy web container (min-replicas=0, max=3)
├── Create Container Apps Jobs for each sync schedule
├── Configure managed identity + environment variables
└── Test full sync cycle

Day 3:
├── DNS cutover to Container Apps
├── Update Azure AD redirect URIs
├── Verify OAuth flow works
└── Keep App Service running in parallel for 30 days

Day 30:
├── Decommission App Service
└── Delete App Service Plan
```

### Phase 3: Security Hardening (Ongoing) — $0 cost

```
Sprint 1 (immediate):
├── 🔴 Replace storage account listKeys() with RBAC role assignment
├── 🔴 Restrict Key Vault network (defaultAction: 'Deny')
├── Remove 5 unused monitoring packages from pyproject.toml
└── Add APScheduler SQLAlchemy job store persistence

Sprint 2:
├── Add refresh token rotation
├── Purge ARM deployment history
├── Add IP allowlisting for App Service
└── Add structured auth audit events
```

---

## 11. Final Verdict & Recommendations

### Verdict: **EVOLVE** (Keep + Optimize)

The Azure Multi-Tenant Governance Platform at v1.7.0 is **architecturally sound, competitively unmatched, and significantly over-paying for infrastructure**.

**What's right:**
- ✅ FastAPI + HTMX + Jinja2 is the correct stack (no build step, 14KB client JS, server-rendered)
- ✅ Python is the correct language (best Azure SDK after .NET, most productive for CRUD + API)
- ✅ SQLAlchemy 2.0 + Alembic is the correct ORM (handles SQLite ↔ Azure SQL seamlessly)
- ✅ GitHub Actions is the correct CI/CD (already configured, free, GHCR native)
- ✅ Bicep is the correct IaC (no state file, first-party Azure support)
- ✅ Custom JWT auth is the correct choice (multi-tenant tenant isolation impossible with Easy Auth)
- ✅ 3,279 tests provide excellent coverage

**What needs optimization:**
- 🔴 **Cost** — $73/mo is 5-15x more than necessary. Phase 1 alone saves $700/year with 4 hours of work.
- 🔴 **Security** — Storage account key leak and Key Vault network exposure (both $0 fixes)
- 🟡 **Monitoring** — 4 overlapping telemetry systems; consolidate to 2
- 🟡 **APScheduler** — Add job store persistence for reliability
- 🟡 **Dependencies** — Remove 5 unused packages to reduce attack surface and Docker image size

**What should NOT change:**
- ❌ Do not switch frameworks (3-6 month rewrite cost, 0 benefit at 10-30 users)
- ❌ Do not switch languages (Go/Rust eliminated by Azure SDK gaps)
- ❌ Do not buy commercial governance platforms (15-50x cost, 35-60% coverage)
- ❌ Do not add Azure Front Door/WAF (48-452% of budget for an internal tool)
- ❌ Do not add Private Endpoints yet ($23.50/mo = 32% of budget)
- ❌ Do not add Redis for caching (unnecessary at 10-30 users)

### Top 5 Actions by ROI

| # | Action | Cost | Savings/Impact | Effort |
|---|--------|------|---------------|--------|
| 1 | Delete staging + GHCR migration | $0 | **$516/yr saved** | 2 hours |
| 2 | SQL S0 → Free Tier | $0 | **$180/yr saved** | 2 hours |
| 3 | Fix storage account key leak | $0 | **Critical security fix** | 1 hour |
| 4 | Restrict Key Vault network | $0 | **High security fix** | 30 min |
| 5 | Remove unused monitoring packages | $0 | **50MB smaller image, reduced attack surface** | 30 min |

**Total: $0 cost, $696/yr savings, critical security improvements, 6 hours of work.**

---

## 12. Fitness Functions

Automated architecture fitness functions should be placed in `tests/architecture/`:

### test_cost_constraints.py
```python
"""Architecture fitness functions for cost constraints."""
import json
import subprocess

def test_no_premium_sku_in_bicep():
    """Ensure no premium SKUs sneak into infrastructure templates."""
    import pathlib
    infra_dir = pathlib.Path("infrastructure")
    premium_skus = ["P1v2", "P1v3", "P2v2", "P2v3", "P3v2", "P3v3", "S1", "S2", "S3", "Premium"]
    for bicep_file in infra_dir.rglob("*.bicep"):
        content = bicep_file.read_text()
        for sku in premium_skus:
            # Allow Premium in comments and string references
            lines = [l for l in content.split('\n') if sku in l and not l.strip().startswith('//')]
            for line in lines:
                if f"'{sku}'" in line or f'"{sku}"' in line:
                    assert False, f"Premium SKU '{sku}' found in {bicep_file}: {line.strip()}"

def test_no_acr_in_infrastructure():
    """Ensure ACR is not reintroduced (using GHCR instead)."""
    import pathlib
    infra_dir = pathlib.Path("infrastructure")
    for bicep_file in infra_dir.rglob("*.bicep"):
        content = bicep_file.read_text()
        if "Microsoft.ContainerRegistry" in content:
            # Allow if commented out
            lines = [l for l in content.split('\n')
                     if "Microsoft.ContainerRegistry" in l and not l.strip().startswith('//')]
            if lines:
                assert False, f"ACR resource found in {bicep_file} — use GHCR instead"

def test_database_dependencies_count():
    """Ensure we're not adding unnecessary database dependencies."""
    import pathlib
    pyproject = pathlib.Path("pyproject.toml").read_text()
    db_deps = [line for line in pyproject.split('\n')
               if any(x in line.lower() for x in ['sqlalchemy', 'alembic', 'pyodbc', 'tortoise', 'django-db'])]
    # Should have exactly 3: sqlalchemy, alembic, pyodbc
    assert len(db_deps) <= 4, f"Too many DB dependencies: {db_deps}"
```

### test_security_constraints.py
```python
"""Architecture fitness functions for security constraints."""
import pathlib

def test_no_listkeys_in_bicep():
    """Ensure storage account keys are not embedded in deployments."""
    infra_dir = pathlib.Path("infrastructure")
    for bicep_file in infra_dir.rglob("*.bicep"):
        content = bicep_file.read_text()
        if "listKeys()" in content:
            lines = [l for l in content.split('\n')
                     if "listKeys()" in l and not l.strip().startswith('//')]
            if lines:
                assert False, f"listKeys() found in {bicep_file} — use RBAC role assignment instead"

def test_keyvault_network_restricted():
    """Ensure Key Vault has defaultAction: 'Deny'."""
    infra_dir = pathlib.Path("infrastructure")
    for bicep_file in infra_dir.rglob("*.bicep"):
        content = bicep_file.read_text()
        if "Microsoft.KeyVault" in content and "defaultAction" in content:
            if "'Allow'" in content and "defaultAction" in content:
                # Check if they're on the same logical block
                assert False, f"Key Vault defaultAction should be 'Deny' in {bicep_file}"

def test_no_unused_monitoring_packages():
    """Ensure unused monitoring packages are removed."""
    pyproject = pathlib.Path("pyproject.toml").read_text()
    unused_packages = [
        "prometheus-fastapi-instrumentator",
        "opentelemetry-api",
        "opentelemetry-sdk",
        "opentelemetry-instrumentation-fastapi",
        "opentelemetry-exporter-otlp",
    ]
    for pkg in unused_packages:
        assert pkg not in pyproject, f"Unused package '{pkg}' should be removed from pyproject.toml"

def test_secure_parameters_in_bicep():
    """Ensure sensitive parameters use @secure() decorator."""
    infra_dir = pathlib.Path("infrastructure")
    sensitive_params = ["password", "secret", "key", "token"]
    for bicep_file in infra_dir.rglob("*.bicep"):
        content = bicep_file.read_text()
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.strip().startswith('param '):
                param_name = line.strip().split()[1].lower() if len(line.strip().split()) > 1 else ''
                if any(s in param_name for s in sensitive_params):
                    # Check if previous line has @secure()
                    if i > 0 and '@secure()' not in lines[i-1]:
                        assert False, f"Param '{param_name}' in {bicep_file} missing @secure() decorator"

def test_docker_runs_as_nonroot():
    """Ensure Dockerfile uses non-root user."""
    dockerfile = pathlib.Path("Dockerfile").read_text()
    assert "USER" in dockerfile, "Dockerfile must specify a non-root USER"
    assert "appuser" in dockerfile or "nonroot" in dockerfile, "Dockerfile should use a named non-root user"
```

### test_architecture_constraints.py
```python
"""Architecture fitness functions for structural constraints."""
import pathlib

def test_no_spa_framework_dependencies():
    """Ensure no SPA framework is introduced (HTMX is the chosen approach)."""
    pyproject = pathlib.Path("pyproject.toml").read_text()
    package_json = pathlib.Path("package.json")

    spa_frameworks = ["react", "vue", "angular", "svelte", "next", "nuxt"]

    if package_json.exists():
        pkg = package_json.read_text()
        for fw in spa_frameworks:
            # Allow in devDependencies for tooling but not dependencies
            if f'"@{fw}' in pkg or f'"{fw}"' in pkg:
                # Check it's not in a comment or in devDependencies only for linting
                pass  # Package.json check is informational

    for fw in spa_frameworks:
        assert fw not in pyproject.lower(), f"SPA framework '{fw}' found in pyproject.toml — use HTMX"

def test_max_dependency_count():
    """Ensure dependency count stays manageable."""
    pyproject = pathlib.Path("pyproject.toml").read_text()
    # Count lines in dependencies section
    in_deps = False
    dep_count = 0
    for line in pyproject.split('\n'):
        if line.strip() == 'dependencies = [':
            in_deps = True
            continue
        if in_deps and line.strip() == ']':
            break
        if in_deps and '"' in line and not line.strip().startswith('#'):
            dep_count += 1

    assert dep_count <= 35, f"Too many dependencies ({dep_count}) — review for unused packages"

def test_single_database_orm():
    """Ensure only one ORM is used (SQLAlchemy)."""
    pyproject = pathlib.Path("pyproject.toml").read_text()
    competing_orms = ["tortoise-orm", "django", "peewee", "pony", "mongoengine"]
    for orm in competing_orms:
        assert orm not in pyproject, f"Competing ORM '{orm}' found — SQLAlchemy is the chosen ORM"

def test_htmx_template_pattern():
    """Ensure templates follow HTMX partial pattern."""
    templates_dir = pathlib.Path("app/templates")
    if not templates_dir.exists():
        return

    # Check that partials exist for HTMX endpoints
    partials = list(templates_dir.rglob("partials/**/*.html")) + list(templates_dir.rglob("components/**/*.html"))
    pages = list(templates_dir.rglob("pages/**/*.html"))

    # Should have more partials/components than full pages (HTMX pattern)
    assert len(partials) >= len(pages), \
        f"Expected more partials ({len(partials)}) than pages ({len(pages)}) for HTMX architecture"
```

---

## 13. Research References

All research was conducted via web-puppy agent with findings saved to `./research/`:

| Research Area | Directory | Key Finding |
|---------------|-----------|-------------|
| Azure Native Tools | `research/azure-native-governance-deep-dive/` | Native tools cover 35-40%, cannot replace platform |
| Azure Native (earlier) | `research/azure-native-vs-custom/` | Lighthouse doesn't delegate Entra ID |
| Competitors | `research/cloud-governance-competitors/` | No competitor achieves 80% coverage at any price |
| Cost Optimization | `research/cost-optimization-2026/` | $73/mo → $0-5/mo achievable |
| Hosting Alternatives | `research/azure-hosting-alternatives/` | Container Apps consumption = $0 with free grants |
| Tech Stack | `research/tech-stack-alternatives/` | Current stack is optimal; Go/Rust eliminated |
| Security Architecture | `research/security-architecture-2026/` | Keep custom JWT, fix 2 credential leaks ($0) |
| Architecture Audit | `research/architecture-audit-2026/` | APScheduler needs persistence, monitoring needs consolidation |

### Source Credibility Tiers

| Tier | Source Type | Examples |
|------|-----------|---------|
| **Tier 1** | Official documentation | Microsoft Learn, Azure Pricing Calculator, GitHub official docs |
| **Tier 2** | Vendor documentation | Vantage.sh, CoreStack.io, CloudHealth docs |
| **Tier 3** | Community/analysis | TechEmpower benchmarks, blog posts, Stack Overflow |

---

## Decision Drivers Summary

1. **Cost efficiency** — $73/mo is 5-15x higher than necessary for this workload
2. **Feature coverage** — No alternative covers >60% of platform functionality
3. **Azure Lighthouse** — Zero competitors support Lighthouse natively
4. **Regulatory deadline** — Riverside compliance deadline (July 8, 2026) makes platform switching impossible
5. **Sunk cost** — 725 files, 3,279 tests already built and working
6. **Security posture** — Two $0 fixes address the only critical findings
7. **Operational simplicity** — Current stack requires minimal maintenance

## Considered Options

1. **Replace with commercial platform** — ❌ Rejected (15-50x cost, 35-60% coverage)
2. **Replace with Azure native tools** — ❌ Rejected (35-40% coverage, Entra ID gap fatal)
3. **Rebuild in different tech stack** — ❌ Rejected (3-6 month cost, 0 benefit at this scale)
4. **Keep current, no changes** — ⚠️ Viable but leaves $700/yr savings on table
5. **Keep current, optimize infrastructure** — ✅ **Accepted** (Phase 1: $700/yr savings in 4 hours)
6. **Keep current, optimize + Container Apps** — ✅ **Accepted** (Phase 2: $820-880/yr savings in 2-3 days)

## Decision Outcome

**Chosen option: #5 (Phase 1 immediate) + #6 (Phase 2 when ready)**

### Consequences

**Good:**
- 79-100% cost reduction ($73 → $0-15/mo)
- Zero code changes in Phase 1
- Critical security fixes at $0 cost
- Reduced Docker image size and attack surface
- Maintained 100% feature coverage

**Bad:**
- Phase 2 requires APScheduler refactoring to Container Apps Jobs
- SQL Free Tier has 30-60 sec cold start after prolonged inactivity
- Container Apps has 3-8 sec cold start from scale-to-zero
- Loss of dedicated staging environment (mitigated by CI/CD + deployment slots)

**Neutral:**
- No technology stack changes
- No vendor dependencies introduced
- No multi-cloud capability added (staying Azure-only)
- Team skills remain the same (Python, FastAPI, Bicep)

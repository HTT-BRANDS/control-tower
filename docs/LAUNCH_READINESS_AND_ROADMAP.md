# Azure Governance Platform — Launch Readiness, Costs & 2-Year Roadmap

> Generated: April 15, 2026 | Version: 2.5.0 | Region: West US 2

---

## 1. What Does the Production App Service Plan Actually Do?

The **App Service Plan** is the compute engine that runs your web app. Think of it like renting a server:

| What It Controls | Your Current State |
|---|---|
| **CPU & RAM** | B1 = 1 vCPU, 1.75 GB RAM |
| **Always-on** | ✅ Enabled (keeps app warm, no cold starts) |
| **Auto-scale** | ❌ Not available on Basic tier |
| **Deployment slots** | ❌ Not available on Basic tier |
| **Custom domains + SSL** | ✅ Available |
| **Max scale-out** | 3 instances (manual only) |

### Why B1 → S1 for Blue-Green?

**Deployment slots** are isolated copies of your app that live inside the same plan. Blue-green deploy works by:

1. Deploy new version to the **staging slot** (invisible to users)
2. Run smoke tests against the staging slot
3. **Swap** staging ↔ production (instant, zero-downtime)
4. If something breaks, swap back in seconds

**Basic (B1) doesn't support slots at all.** Standard (S1) supports up to 5 slots. That's why the upgrade is needed — it's not about more CPU, it's about the **deployment pattern**.

### Do You Actually Need Blue-Green for Launch?

**Honest answer: No.** Your `deploy-staging.yml` workflow works fine on B1. It does a direct container image swap on the staging App Service. For 5 users, a 10-second restart during deploy is totally acceptable.

Blue-green is a **nice-to-have** for when you can't afford any downtime — think 50+ active users relying on the tool during business hours.

---

## 2. Current Infrastructure — Complete Inventory

### Production Environment (`rg-governance-production`)

| Resource | SKU | What It Does | Monthly Cost |
|---|---|---|---|
| App Service Plan (`asp-governance-production`) | **B1 Basic** | Runs the FastAPI web app | ~$12.41 |
| Web App (`app-governance-prod`) | Linux Container | The actual app (Docker on GHCR) | (included in plan) |
| SQL Server + Database (`sql-gov-prod-mylxq53d`) | **S0 Standard (10 DTU)** | All app data, audit logs, compliance state | ~$14.72 |
| Container Registry (`acrgovprod`) | **Standard** | Stores Docker images | ~$20.00 |
| Key Vault (`kv-gov-prod`) | **Standard** | Secrets, connection strings, API keys | ~$0.03 |
| Application Insights (`governance-appinsights`) | Per-GB | Request tracing, performance monitoring | ~$0-2.30 |
| Log Analytics (`governance-logs`) | Per-GB (30-day retention) | Centralized logs | ~$0-2.30 |
| Alert Rules (3) | — | Server errors, response time, availability | Free |
| **SUBTOTAL** | | | **~$50-52/mo** |

### Staging Environment (`rg-governance-staging`)

| Resource | SKU | Monthly Cost |
|---|---|---|
| App Service Plan | B1 Basic | ~$12.41 |
| SQL Database | **Free** (32 MB, 5 DTU) | $0.00 |
| Storage Account | — | ~$9.00 |
| App Insights + Log Analytics | Per-GB | ~$0 |
| Key Vault | Standard | ~$0.01 |
| **SUBTOTAL** | | **~$21/mo** |

### Dev Environment (`rg-governance-dev`)

| Resource | SKU | Monthly Cost |
|---|---|---|
| App Service Plan | B1 Basic | ~$12.41 |
| SQL Database | S0 Standard (10 DTU) | ~$14.72 |
| Container Registry (Basic) | Basic | ~$5.00 |
| Storage Account | — | ~$11.40 |
| App Insights + Log Analytics | Per-GB | ~$0 |
| Key Vault | Standard | ~$0.01 |
| **SUBTOTAL** | | **~$44/mo** |

### GitHub (`HTT-BRANDS` org)

| Item | Detail | Monthly Cost |
|---|---|---|
| Plan | **Enterprise Cloud** | $21/seat × 7 seats = **$147/mo** |
| Actions minutes | 50,000 included (Linux) | $0 (well within limit) |
| GHCR storage | **Free** (not billed) | $0 |
| GitHub Pages | Included (1 GB site, 100 GB bandwidth) | $0 |
| **SUBTOTAL** | | **$147/mo** |

---

## 3. Total Current Monthly Cost

| Category | Monthly Cost |
|---|---|
| Azure — Production | $50-52 |
| Azure — Staging | $21 |
| Azure — Dev | $44 |
| GitHub Enterprise (7 seats) | $147 |
| **TOTAL** | **~$262-264/mo** |
| **Annualized** | **~$3,144-3,168/yr** |

### Actual Azure Spend (Verified from Cost Management API)

| Resource Group | Last Full Month (March) | This Month (Apr 1-15, 50% in) |
|---|---|---|
| rg-governance-production | $27.24 | $18.32 |
| rg-governance-staging | $36.58 | $10.47 |
| rg-governance-dev | $30.19 | $21.23 |
| **Azure Total** | **$94.01** | **$50.02 (→ ~$100 projected)** |

> **Note:** Staging was higher in March due to a storage backup spike (`sqlbackup1774966098`). Production ACR (Standard at $20/mo) is the biggest single line item after compute+SQL.

---

## 4. Launch Configuration — What You Actually Need

### For 5 Users, Internal Tool — Recommended SKUs

You do NOT need S1 or P1v3 for launch. Here's what matters:

| Resource | Current SKU | Launch Recommendation | Why |
|---|---|---|---|
| Prod App Service | B1 ($12.41) | **Keep B1** | 1 vCPU/1.75GB is plenty for 5 users. Always-on is enabled. |
| Prod SQL | S0 10 DTU ($14.72) | **Keep S0** | 10 DTU handles ~40 concurrent queries. 5 users won't even tickle it. |
| Prod ACR | Standard ($20) | **Downgrade to Basic ($5)** | You only need 1-2 images. Basic = 10 GB storage. Standard's 100 GB is overkill. |
| Prod Key Vault | Standard | **Keep** | Pennies per month |
| Staging | B1 + Free SQL | **Keep as-is** | Staging doesn't need more |
| Dev | B1 + S0 SQL | **Consider stopping when not developing** | $44/mo doing nothing on weekends |

### Immediate Savings (No Functionality Lost)

| Change | Monthly Savings |
|---|---|
| Downgrade `acrgovprod` Standard → Basic | **-$15.00** |
| Stop dev App Service when idle (weekdays only) | **-$4.00** |
| **Total Savings** | **-$19/mo** |

### Revised Launch Cost

| Category | Monthly Cost |
|---|---|
| Azure — Production | **$35** |
| Azure — Staging | $21 |
| Azure — Dev | $40 |
| GitHub Enterprise (7 seats) | $147 |
| **TOTAL** | **~$243/mo ($2,916/yr)** |

---

## 5. CI/CD Pipeline — Current State

### What's Working ✅

| Workflow | Trigger | Status | Purpose |
|---|---|---|---|
| **CI** (ruff + pytest) | Every push | ✅ Green | Lint, type-check, 140+ unit tests |
| **Security Scan** (Trivy) | Every push | ✅ Green | Container CVE scanning |
| **Accessibility** (axe-core + Pa11y) | After staging deploy | ✅ Green | WCAG 2.2 compliance |
| **Cross-Browser** (Playwright) | Docs changes | ✅ 8/9 passing | Chromium/Firefox/WebKit × 3 viewports |
| **Deploy Staging** | Push to main | ✅ Working | Direct container swap on staging |
| **GitHub Pages** | Docs changes | ✅ Working | ADRs, architecture docs |

### What Needs the S1 Upgrade 🔧

| Workflow | Current State | What It Needs |
|---|---|---|
| **Blue-Green Deploy** | ❌ Fails (B1 = no slots) | S1 Standard ($58.40/mo) |
| **Deploy Production** | ⚠️ Works but no zero-downtime | S1 for slot-based deploys |
| **Backup** | ⚠️ Untested | Needs staging slot verification |

### My Recommendation for Launch

**Don't upgrade to S1 yet.** Here's why:

1. The `deploy-staging.yml` workflow successfully deploys to staging on B1
2. For production, use a **direct container swap** (same pattern as staging)
3. 5 users won't notice a 10-second restart during deploy
4. Save $46/mo until you actually need zero-downtime deploys

**When to upgrade:** When you have 20+ active users or you're deploying multiple times per day during business hours.

---

## 6. Scalability Analysis — 5 Users Today, Growth Tomorrow

### Current Capacity (B1 + S0 SQL)

| Metric | Capacity | 5-User Load | Headroom |
|---|---|---|---|
| **Concurrent requests** | ~100/sec (uvicorn + 4 workers) | ~2-5/sec | **20-50× headroom** |
| **SQL queries** | ~40 concurrent (10 DTU) | ~1-3 concurrent | **13-40× headroom** |
| **Memory** | 1.75 GB | ~400 MB (Python + app) | **4× headroom** |
| **Database size** | 250 GB max (S0) | ~50 MB currently | **5000× headroom** |
| **Response time** | <500ms p95 | Expected <200ms | ✅ |

**Bottom line:** B1 + S0 handles 5 users without breaking a sweat. You could probably handle 30-50 users before needing to think about scaling.

### Scaling Thresholds

| Users | What Happens | Action Needed | Added Cost |
|---|---|---|---|
| **1-30** | Everything works fine on B1 | Nothing | $0 |
| **30-50** | SQL DTU starts climbing | Monitor DTU % in App Insights | $0 |
| **50-100** | Need auto-scale + more DTU | Upgrade to S1 + S1 SQL (50 DTU) | +$93/mo |
| **100-300** | Need premium compute | P1v3 + S2 SQL (100 DTU) | +$200/mo |
| **300+** | Need distributed architecture | P2v3 + Elastic Pool + Redis | +$500/mo |

---

## 7. What "Rock-Solid, Healthy, Monitored" Looks Like

### Already In Place ✅

- **3 alert rules**: Server errors (Sev0), High response time (Sev2), Availability drop (Sev0)
- **Email alerts** to admin@httbrands.com
- **Application Insights**: Full request tracing, dependency tracking, exception logging
- **Log Analytics**: Centralized logs with 30-day retention
- **Health endpoint**: `/health` for uptime monitoring
- **HTTPS-only** with TLS 1.2 minimum
- **Security headers**: CSP, HSTS, X-Frame-Options, GPC middleware
- **Circuit breaker** pattern for Azure API calls
- **Retry logic** with exponential backoff

### Recommended Additions for Launch

| Priority | What | Why | Cost |
|---|---|---|---|
| 🔴 **High** | Set `healthCheckPath` in App Service config | Auto-restart on crash, currently `null` | Free |
| 🔴 **High** | Add Teams webhook to alert action group | Faster incident response than email | Free |
| 🟡 **Medium** | Add availability test (ping from Azure) | Detect outages before users report them | Free (up to 10 tests) |
| 🟡 **Medium** | Enable Diagnostic Settings on SQL | Audit log, deadlock detection | ~$1/mo (log volume) |
| 🟢 **Low** | Add custom dashboard in Azure Portal | One-pane-of-glass for ops | Free |
| 🟢 **Low** | Enable purge protection on Key Vault | Prevent accidental secret deletion | Free |

---

## 8. Two-Year Roadmap

### Phase 1: Launch (Now → Month 1) — "Ship It"

**Goal:** Internal tool for 5 HTT employees to view Azure governance insights, Riverside RISO requirements, compliance posture, and persona-based dashboards.

| Task | Status |
|---|---|
| CI pipeline green (lint, tests, security) | ✅ Done |
| OIDC federation for GitHub Actions | ✅ Done |
| Production App Service running | ✅ Running |
| Production SQL with data | ✅ Online |
| Monitoring + alerts | ✅ 3 rules active |
| Set health check path in App Service | 🔧 5-minute fix |
| Persona-based access control (RBAC) | ✅ Built (multi-tenant auth) |
| Riverside RISO requirements dashboard | ✅ Built (routes/riverside.py) |
| Deploy latest v2.5.0 to production | 🔧 One workflow dispatch |

**Cost: ~$243/mo** | **Users: 5** | **Risk: Low**

### Phase 2: Harden (Months 2-3) — "Make It Bulletproof"

**Goal:** Production-grade reliability, automated compliance reporting, custom domain.

| Task | Effort | Impact |
|---|---|---|
| Custom domain + managed SSL cert | 2 hrs | Professional URL (governance.httbrands.com) |
| Automated weekly compliance reports (email/Teams) | 4 hrs | RISO stakeholders get status without logging in |
| Database backup automation (verified restores) | 3 hrs | Disaster recovery confidence |
| Add Azure availability ping test | 30 min | Proactive outage detection |
| Blue-green deploy (if deploying frequently) | S1 upgrade | Zero-downtime deploys |
| Performance baseline (response time SLOs) | 2 hrs | Know when things degrade |

**Cost: ~$243-289/mo** (S1 if needed, otherwise same) | **Users: 5-10**

### Phase 3: Expand (Months 4-8) — "Open the Doors"

**Goal:** Broader access for Riverside partners, more tenant onboarding, executive dashboards.

| Task | Effort | Impact |
|---|---|---|
| Riverside partner read-only access (RISO viewers) | 1 week | Partners self-serve compliance status |
| Executive summary dashboard (C-suite view) | 1 week | High-level posture at a glance |
| Multi-tenant: onboard BCC, FN, TLL tenants | 2 weeks | Secrets already configured for these tenants |
| Scheduled sync jobs (daily Azure scans) | Built | Keep data fresh automatically |
| SSO via Azure AD (SAML/OIDC for users) | 1 week | Enterprise sign-in, no separate passwords |
| DMARC monitoring dashboard | Built | Email security visibility |
| Threat intelligence feed | Built | CVE/threat awareness |

**Cost: ~$289/mo** (S1 for reliability with more users) | **Users: 10-25**

**Why expand access:**
- **Riverside RISO auditors** need to verify compliance status → give them read-only access instead of manual reports
- **BCC/FN/TLL tenant admins** need their own governance view → multi-tenant is already built, just needs data sync
- **Executives** need posture summaries → custom dashboard route already scaffolded

### Phase 4: Scale (Months 9-14) — "Handle the Load"

**Goal:** Self-service portal, automated remediation, API integrations.

| Task | Effort | Impact |
|---|---|---|
| Upgrade to P1v3 + S1 SQL (50 DTU) | 1 hr | Handle 50-100 concurrent users |
| Automated remediation (fix compliance drift) | 2 weeks | Reduce manual intervention |
| Webhook integrations (ServiceNow, Jira) | 1 week | Feed findings into existing workflows |
| Role-based personas with granular permissions | Built | Different views for different responsibilities |
| Historical trend analysis (6-month lookback) | 1 week | Show compliance trajectory to auditors |
| API rate limiting + OAuth2 client credentials | Built | Safe third-party integrations |
| Redis cache layer (if needed) | 2 days | Reduce SQL load at scale |

**Cost: ~$400/mo** | **Users: 25-100**

### Phase 5: Enterprise (Months 15-24) — "Platform Play"

**Goal:** Multi-org governance platform, public API, advanced analytics.

| Task | Effort | Impact |
|---|---|---|
| Elastic SQL Pool (multiple DBs, shared DTU) | 1 day | Cost-efficient multi-tenant at scale |
| Horizontal auto-scale (2-4 instances) | Built into S1+ | Handle traffic spikes |
| Power BI / Grafana integration | 1 week | Advanced analytics dashboards |
| Compliance certification exports (SOC2, ISO) | 2 weeks | Audit-ready documentation |
| White-label / partner portal | 1 month | Offer governance-as-a-service to partners |
| AI-powered recommendations (Azure Advisor integration) | 2 weeks | Proactive cost/security optimization |
| Mobile-responsive PWA | 1 week | Governance on the go |

**Cost: ~$600-800/mo** | **Users: 100-500**

---

## 9. Cost Projection — 2-Year View

| Period | Azure/mo | GitHub/mo | Total/mo | Annual |
|---|---|---|---|---|
| **Launch (now)** | $96 | $147 | **$243** | $2,916 |
| **Harden (Mo 2-3)** | $96-142 | $147 | **$243-289** | $2,916-3,468 |
| **Expand (Mo 4-8)** | $142 | $147 | **$289** | $3,468 |
| **Scale (Mo 9-14)** | $250 | $147 | **$397** | $4,764 |
| **Enterprise (Mo 15-24)** | $450-650 | $147 | **$597-797** | $7,164-9,564 |

### 2-Year Total Cost Estimate

| Scenario | 2-Year Total |
|---|---|
| **Conservative** (stay small, 5-10 users) | **~$6,500** |
| **Moderate** (expand to 50 users by year 2) | **~$9,500** |
| **Aggressive** (100+ users, enterprise features) | **~$15,000** |

---

## 10. What's Already Built (Your Secret Weapon)

This platform has **33,000+ lines of production code** with enterprise patterns already in place:

| Capability | Status | Files |
|---|---|---|
| Multi-tenant auth (Azure AD) | ✅ Built | `core/auth.py`, `core/authorization.py` |
| Persona-based RBAC | ✅ Built | 5 personas defined |
| Riverside RISO compliance | ✅ Built | `routes/riverside.py`, `services/riverside/` |
| Cost management + anomaly detection | ✅ Built | `routes/costs.py`, `services/cost/` |
| Identity/MFA monitoring | ✅ Built | `routes/identity.py`, `services/identity/` |
| Threat intelligence | ✅ Built | `routes/threats.py`, `services/threat_intel/` |
| DMARC email security | ✅ Built | `routes/dmarc.py`, `services/dmarc/` |
| Budget tracking | ✅ Built | `routes/budgets.py`, `services/budget/` |
| Resource lifecycle management | ✅ Built | `services/resource_lifecycle/` |
| Compliance frameworks | ✅ Built | `routes/compliance_frameworks.py` |
| Preflight checks (30+ Azure checks) | ✅ Built | `services/preflight/` |
| Export to CSV/JSON | ✅ Built | `routes/exports.py` |
| Full audit logging | ✅ Built | `routes/audit_logs.py` |
| Design system (WCAG 2.2 AA) | ✅ Built | `core/design_tokens.py`, `core/css_generator.py` |
| Privacy (GDPR/CCPA/GPC) | ✅ Built | `core/gpc_middleware.py`, `services/privacy/` |
| Circuit breaker + retry | ✅ Built | `core/circuit_breaker.py`, `core/http_client.py` |
| 140+ unit test files | ✅ Built | `tests/unit/` |
| Architecture decision records | ✅ 11 ADRs | `docs/adr/` |

**You've already built the hardest parts.** The remaining work is operations, access management, and growth.

---

## 11. Immediate Next Steps (The Final Countdown 🎸)

```
Priority 1 — Do Today (30 minutes)
├── Set health check path: az webapp config set --name app-governance-prod -g rg-governance-production --generic-configurations '{"healthCheckPath":"/health"}'
├── Deploy v2.5.0 to production (trigger deploy-staging.yml)
└── Verify production is responding at /health

Priority 2 — This Week (2 hours)
├── Add Teams webhook to governance-alerts action group
├── Enable Key Vault purge protection
├── Consider downgrading acrgovprod Standard → Basic (saves $15/mo)
└── Brief the 5 users on how to access the platform

Priority 3 — This Month (decision)
└── Decide: Do you want blue-green deploys? If yes, upgrade to S1 (+$46/mo)
    If no, keep B1 and use direct container swap — totally fine for your scale.
```

---

*This document was generated by Richard 🐶 from live Azure infrastructure data, actual Cost Management API figures, and current GitHub billing information. All costs are West US 2 pay-as-you-go pricing as of April 2026.*

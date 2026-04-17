# Azure Governance Platform — Production Cost Model & Scaling Playbook

> **bd issue:** zj9k | **Status:** Accepted | **Author:** Solutions Architect (solutions-architect-8ad3a1)
> **Date:** April 18, 2026 | **Version:** 1.0.0 | **Region:** East US (prod), West US 2 (staging/dev)
> **Supersedes:** Stale cost sections in `docs/LAUNCH_READINESS_AND_ROADMAP.md` and `docs/operations/cost-analysis.md`

---

## TL;DR

**Launch cost: ~$53/mo Azure + $147/mo GitHub = ~$200/mo all-in.** At the base growth scenario (20 tenants by month 12, 40 by month 24), the 12-month Azure cost is ~$1,140 and the recommended starting tier set is **B1 App Service + Basic SQL + in-memory cache** across all three environments with trigger-based upgrades. There is no reason to change tiers before launch. The first upgrade trigger will be App Service CPU p95 > 70% sustained, which at current architecture headroom is unlikely before ~30 concurrent users.

### How to read this doc

Tables contain the hard numbers — skim them for dollar amounts. Narrative sections explain *why* those numbers matter and *when* to act. Callout boxes (▸) flag decisions that need Tyler's input.

### Assumptions & Caveats

| Assumption | Value | Notes |
|---|---|---|
| **Pricing date** | April 18, 2026 | Azure Retail Prices API + official pricing pages |
| **Pricing model** | Pay-As-You-Go (PAYG) | No commitment tiers unless stated |
| **Regions** | East US (prod), West US 2 (staging + dev) | Regional price differences noted where material |
| **Currency** | USD | |
| **Tenant count at launch** | 5 (HTT, BCC, FN, TLL, DCE) | All configured, OIDC federation active |
| **User count at launch** | ~5 internal HTT employees | Per LAUNCH_READINESS §4 |
| **GitHub seats** | 7 @ $21/seat Enterprise Cloud | Per live billing |
| **Tax/support** | Excluded | Azure support plans and tax vary by agreement |
| **Numbers marked ⚠️** | Documented, not live-verified | Could not access live Azure CLI in this environment |

> **Gap marker:** All cost figures in this document are derived from (a) `INFRASTRUCTURE_END_TO_END.md` as of April 16, 2026, (b) Azure Retail Prices REST API via web-puppy research, and (c) `SESSION_HANDOFF.md`. Live `az consumption` data was **not available** in this session. Numbers are marked where derived vs verified.

---

## 1. Launch Baseline (TODAY)

### 1.1 Current Resources — SKU-by-SKU

> **This section supersedes** `LAUNCH_READINESS_AND_ROADMAP.md` §2–3 (which still shows S0 SQL at $14.72 and ACR Standard at $20.00 — both changed on April 16, 2026).

#### Production — `rg-governance-production` (East US)

| Resource | SKU | Region | Monthly Cost | % of Total | Fixed/Usage | Notes |
|---|---|---|---|---|---|---|
| App Service Plan | **B1 Basic** (1 vCPU, 1.75 GB) | East US | $12.41 | 23.2% | Fixed | Always-on enabled; no autoscale; no slots |
| SQL Database | **Basic** (5 DTU, 2 GB) | East US | $4.90 | 9.2% | Fixed | Downgraded from S0 on Apr 16 |
| Key Vault | Standard | East US | ~$0.03 | <0.1% | Usage | ~1K ops/month |
| App Insights | Per-GB (workspace-based) | East US | ~$0.00 | 0% | Usage | Within 5 GB/mo free tier |
| Log Analytics | PerGB2018 | East US | ~$0.00 | 0% | Usage | Within 5 GB/mo free tier |
| Alert Rules (7 metric + 2 avail) | — | East US | ~$0.60 | 1.1% | Fixed | $0.05 × ~12 time-series |
| Bandwidth/misc | — | East US | ~$0.11 | <0.2% | Usage | Near-zero egress |
| **Prod subtotal** | | | **~$18.05** | **33.8%** | | |

#### Staging — `rg-governance-staging` (West US 2)

| Resource | SKU | Region | Monthly Cost | % of Total | Fixed/Usage | Notes |
|---|---|---|---|---|---|---|
| App Service Plan | **B1 Basic** | West US 2 | $12.41 | 23.2% | Fixed | |
| SQL Database | **Free** (5 DTU, 32 GB) | West US 2 | $0.00 | 0% | Fixed | No SLA, 1 per subscription |
| Key Vault | Standard | West US 2 | ~$0.03 | <0.1% | Usage | |
| Storage Account | Standard LRS | West US 2 | ~$0.24 | <0.5% | Usage | Empty, LRS (downgraded from GRS Apr 16) |
| App Insights + Log Analytics | Per-GB | West US 2 | ~$0.00 | 0% | Usage | Within free tier |
| **Staging subtotal** | | | **~$12.68** | **23.7%** | | |

#### Dev — `rg-governance-dev` (West US 2)

| Resource | SKU | Region | Monthly Cost | % of Total | Fixed/Usage | Notes |
|---|---|---|---|---|---|---|
| App Service Plan | **B1 Basic** | West US 2 | $12.41 | 23.2% | Fixed | |
| SQL Database | **Basic** (5 DTU, 2 GB) | West US 2 | $4.90 | 9.2% | Fixed | DB is 22 MB per Apr 16 session |
| Container Registry | **Basic** (10 GB) | West US 2 | $5.00 | 9.4% | Fixed | Dev-only; prod/staging use GHCR |
| Key Vault | Standard | West US 2 | ~$0.03 | <0.1% | Usage | |
| Storage Account | Standard LRS | West US 2 | ~$0.33 | <0.6% | Usage | |
| App Insights + Log Analytics | Per-GB | West US 2 | ~$0.00 | 0% | Usage | Within free tier |
| **Dev subtotal** | | | **~$22.67** | **42.5%** | | |

#### GitHub

| Item | Detail | Monthly Cost |
|---|---|---|
| Enterprise Cloud | 7 seats × $21/seat | $147.00 |
| Actions minutes | Within 50,000 included (Linux) | $0.00 |
| GHCR storage | Currently free | $0.00 |
| Pages | Included | $0.00 |
| **GitHub subtotal** | | **$147.00** |

### 1.2 Total Launch Cost

| Category | Monthly | Annual |
|---|---|---|
| Azure — Production | $18.05 | $216.60 |
| Azure — Staging | $12.68 | $152.16 |
| Azure — Dev | $22.67 | $272.04 |
| **Azure subtotal** | **$53.40** | **$640.80** |
| GitHub Enterprise | $147.00 | $1,764.00 |
| **TOTAL** | **$200.40** | **$2,404.80** |

> **Cross-project context:** The full HTT-BRANDS Azure subscription is ~$282/mo (per April 16 session). The governance platform is $53.40 of that. The remaining ~$229/mo includes `rg-htt-domain-intelligence` (~$65/mo, see bd-w1cc) and other project resources.

### 1.3 Decomposition by Service Category

| Category | Monthly | % | Resources |
|---|---|---|---|
| **Compute** | $37.23 | 69.8% | 3× App Service B1 |
| **Data** | $9.80 | 18.4% | 2× SQL Basic + 1× SQL Free |
| **Container Registry** | $5.00 | 9.4% | 1× ACR Basic (dev only) |
| **Observability** | $0.60 | 1.1% | Alert rules (App Insights + Log Analytics within free tier) |
| **Security** | $0.09 | 0.2% | 3× Key Vault |
| **Storage/Network** | $0.68 | 1.3% | 2× Storage LRS + egress |
| **TOTAL** | **$53.40** | **100%** | |

### 1.4 Fixed vs Variable Cost at ~0 Tenant Load

| Type | Monthly | % | What |
|---|---|---|---|
| **Fixed** (runs even at zero traffic) | $52.12 | 97.6% | App Service Plans + SQL DBs + ACR + Alert Rules |
| **Variable** (scales with usage) | $1.28 | 2.4% | Key Vault ops + Storage + Egress + App Insights ingestion |

**Implication:** At current scale, this platform is almost entirely fixed-cost. Usage-based charges only become material at >>10 tenants with active API calls. This is typical for a B-tier App Service architecture — you're renting the compute box, not paying per request.

---

## 2. Scaling Inflection Points

### 2.1 Per-Service Inflection Points

| Service | Current SKU | Hard Limit | Breakpoint Signal | Next SKU | $ Delta /mo | Headroom After Upgrade |
|---|---|---|---|---|---|---|
| **App Service (Prod)** | B1 (1 vCPU, 1.75 GB, 10 GB disk) | ~100 concurrent req, 1.75 GB RAM | CPU p95 > 70% sustained 1hr | B2 ($24.82) or S1 ($69.35) | +$12.41 (B2) or +$56.94 (S1) | B2: 2× CPU/RAM. S1: same CPU/RAM but adds slots + autoscale |
| **SQL (Prod)** | Basic (5 DTU, 2 GB storage) | 5 DTU, 2 GB max DB size | DTU % > 80% sustained or DB size > 1.6 GB | S0 ($14.72) | +$9.82 | 10 DTU, 250 GB storage |
| **App Insights / Log Analytics** | Per-GB (5 GB free) | 5 GB/month free | Ingestion > 4 GB/month (80% of free) | Pay-per-GB ($2.30/GB) | +$2.30 per additional GB | Unlimited (pay as you go) |
| **Egress** | First 100 GB free | 100 GB/month | Egress > 80 GB/month | $0.087/GB Zone 1 | ~$8.70 per 100 GB | Unlimited |
| **Key Vault** | Standard (per-op) | Unlimited (throttled at 4K ops/10s) | > 10K ops/month (unlikely) | Same SKU, more ops | ~$0.03 per 10K | N/A |
| **Storage** | LRS, near-empty | 5 TiB per account | Blob growth > 100 GB | Same SKU, more storage | ~$2.08 per 100 GB LRS | 5 TiB |
| **In-memory cache** | `InMemoryCache` (in-process) | App Service RAM (1.75 GB shared with app ~400 MB) | Cache miss rate > 20%, or multi-instance needed, or memory > 1.2 GB | Redis Basic C0 ($16.06) | +$16.06 | 250 MB dedicated cache, shared across instances |

### 2.2 App Service B1 — Deep Dive

| Metric | B1 Limit | Current Usage (5 users, idle) | Projected at 30 Users | Projected at 100 Users |
|---|---|---|---|---|
| vCPU | 1 core | ~5% | ~15-25% | ~60-80% ⚠️ |
| Memory | 1.75 GB | ~400 MB (Python + FastAPI + 4 workers) | ~500 MB | ~700 MB-1 GB |
| Concurrent requests | ~100/sec (uvicorn 4 workers) | ~2-5/sec | ~10-20/sec | ~30-60/sec |
| Disk (local temp) | 10 GB | < 1 GB | < 2 GB | < 3 GB |
| Connections (outbound) | 1,920 per instance | ~10-20 (SQL + Azure APIs) | ~30-60 | ~100-200 |
| **Deployment slots** | ❌ None | N/A | N/A | N/A |
| **Autoscale** | ❌ Not available | N/A | N/A | N/A |
| **Max manual instances** | 3 | 1 | 1 | Need 2-3 |

**When does B1 break?**
- **CPU saturation** at ~50-80 sustained concurrent users (depends on query complexity)
- **Memory pressure** at ~100 users if cache grows (but cache is TTL-bounded)
- **Connection exhaustion** is NOT a realistic risk at <500 users

**B2 vs S1 — the critical fork:**

| Factor | B2 ($24.82/mo) | S1 ($69.35/mo East US) |
|---|---|---|
| CPU/RAM | 2 cores / 3.5 GB | 1 core / 1.75 GB (same as B1!) |
| Deployment slots | ❌ None | ✅ Up to 5 |
| Autoscale | ❌ No | ✅ Yes (1-10 instances) |
| Disk | 10 GB | 50 GB |
| Cost delta from B1 | +$12.41 | +$56.94 |
| **Choose when** | You need more CPU/RAM but NOT slots | You need slots (blue-green) or autoscale |

> **Cross-reference bd-hofd:** If the blue-green decision (bd-hofd) goes with real slot-based deployment, the App Service tier MUST be S1 minimum. This changes the prod cost from $12.41 → $69.35/mo (+$56.94). The S1 provides the same 1 vCPU/1.75 GB as B1 — you're paying for the **slot capability**, not more compute. If you need both more compute AND slots, go to S2 ($138.70 East US) or P1v3 ($113.15 — actually cheaper than S2 and gives 2 vCPU + 8 GB + 20 slots).

### 2.3 SQL Basic — Deep Dive

| Metric | Basic Limit | Current Usage | Projected at 20 Tenants | Projected at 100 Tenants |
|---|---|---|---|---|
| DTU | 5 | ~0.5 (8% per sql-free-tier-evaluation) | ~2-3 | ~8-15 ⚠️ |
| Storage | 2 GB max | 57 MB (prod, per Apr 16) | ~200 MB | ~800 MB-1.5 GB |
| Concurrent connections | 30 | ~5 | ~10-15 | ~25-30 ⚠️ |
| Point-in-time restore | 7 days | ✅ | ✅ | ✅ |
| Geo-replication | ✅ Available | Not configured | Consider | Recommended |

**When does Basic break?**
- **DTU saturation** at ~20-40 tenants with active sync jobs running concurrently
- **Storage cap** (2 GB) at ~40-60 tenants depending on data retention policy
- **Connection limit** (30) at ~100 tenants if connection pooling isn't tight

**Upgrade path: Basic → S0 → S1:**

| Tier | DTU | Storage | Monthly | Delta from Basic |
|---|---|---|---|---|
| Basic | 5 | 2 GB | $4.90 | — |
| S0 | 10 | 250 GB | $14.72 | +$9.82 |
| S1 | 20 | 250 GB | $29.45 | +$24.55 |
| S2 | 50 | 250 GB | $73.65 | +$68.75 |
| P1 | 125 | 500 GB | $456.56 | +$451.66 |

> ⚠️ **Production-readiness note on storage:** The 2 GB limit on Basic is the most likely first constraint to hit — not DTU. If sync jobs retain 12 months of cost/compliance/identity data across 5 tenants, the DB will grow ~10-15 MB/month. At that rate, the 2 GB cap is hit in ~130 months (10+ years). But at 40 tenants, growth is ~80-120 MB/month, hitting 2 GB in ~18 months. **Recommendation: upgrade to S0 when DB size crosses 1.5 GB or tenant count exceeds 20.**

### 2.4 In-Memory Cache → Redis Cutover

The application currently uses `app/core/cache.py` — a custom `InMemoryCache` with TTL support, asyncio locks, and per-tenant invalidation. This is **fine for single-instance B1**. It breaks when:

1. **Multi-instance scaling** — each instance has its own cache; cache invalidation doesn't propagate
2. **Memory pressure** — cache shares RAM with the FastAPI app on the 1.75 GB B1
3. **App restart** — in-memory cache is lost, causing a cold cache thundering herd

**Redis cutover signal:** When App Service is scaled to ≥2 instances (horizontal scale-out), or cache hit rate drops below 80%, or App Service memory exceeds 1.2 GB.

**Redis Basic C0 pricing:**
- $16.06/mo (250 MB, non-clustered, no SLA)
- Basic C1: $40.15/mo (1 GB)
- Standard C0: $40.15/mo (250 MB, with SLA + replication — recommended for prod)

> **Note:** `parameters.production.json` has `enableRedis: true` but Redis was **never deployed** for the governance platform. The `token_blacklist.py` module gracefully falls back to in-memory. If someone runs the Bicep deployment as-is, it would create a Redis instance at ~$16/mo. **Consider setting `enableRedis: false` until Redis is actually needed.** (See Appendix B, Open Question #2.)

### 2.5 Application Insights — 5 GB Free Tier

Current ingestion is well within the 5 GB/month free allowance. At current telemetry volume (~1-2 GB/month across all envs), there's 3× headroom.

**Breakpoint projection:** At 20 active users with verbose request logging, ingestion could reach ~4-5 GB/month. Enable adaptive sampling in Application Insights SDK to keep ingestion under 5 GB. If sampling isn't sufficient, each additional GB costs $2.30/month.

### 2.6 Egress — Near Zero Now

At 5 users making ~100 page loads/day with ~50 KB average response size, monthly egress is ~150 MB. The free tier covers 100 GB. Even at 1000× current traffic, egress stays free.

**First non-trivial egress cost:** If the platform starts serving large exports (CSV/JSON compliance reports) at scale — e.g., 100 users downloading 10 MB reports daily = 30 GB/month, still within free tier.

---

## 3. Scaling Options & Tradeoffs

### 3.1 Vertical vs Horizontal — Per Service

| Service | Vertical (Scale Up) | Horizontal (Scale Out) | Recommended Path |
|---|---|---|---|
| **App Service** | B1→B2→B3→S1→P1v3 (more CPU/RAM per instance) | S1+ only: 1→2→3→10 instances (autoscale) | **Vertical first** (B1→B2 at $12.41 delta), then horizontal at S1+ when slots needed |
| **SQL Database** | Basic→S0→S1→S2→P1 (more DTU) | Read replicas (S1+ tier); sharding at extreme scale | **Vertical only** — read replicas useful for reporting workload isolation at S1+ |
| **Cache** | C0→C1→C2 (more memory) | Standard tier: C0→C1→C2 with replicas; Premium: clustering | **Vertical** (C0→C1) sufficient to ~1000 users |
| **Storage** | Same SKU, pay per GB | Multiple accounts / CDN at edge | **Not applicable** — current growth is negligible |

### 3.2 Slot-Based Blue-Green — Cost Impact (Cross-Ref: bd-hofd)

Deployment slots are the primary driver for upgrading from B1 to S1+. Key facts:

| Question | Answer |
|---|---|
| Are slots free on S1? | **Yes** — the slot runs on the same plan's compute. No per-slot charge. |
| Does the slot consume the plan's resources? | **Yes** — the staging slot shares CPU/RAM with production. During swap, both run simultaneously briefly. |
| What's the real cost of slots? | The **plan tier upgrade cost**, not the slot itself: B1 ($12.41) → S1 ($69.35 East US) = **+$56.94/mo prod only** |
| Can you keep staging/dev on B1 while prod is S1? | **Yes** — each environment has its own App Service Plan |

**If bd-hofd decides on real blue-green deployment:**

| Environment | Current (B1) | With Slots (S1) | Delta |
|---|---|---|---|
| Production (East US) | $12.41 | $69.35 | +$56.94 |
| Staging (West US 2) | $12.41 | $12.41 (keep B1) | $0 |
| Dev (West US 2) | $12.41 | $12.41 (keep B1) | $0 |
| **Net impact** | | | **+$56.94/mo** |

> ▸ **Decision for Tyler (also relevant to bd-hofd):** For 5 users, a 10-second restart during deploy is acceptable. Recommend deferring S1 upgrade until deploying multiple times per day during business hours, OR when user count exceeds ~20 and downtime during deploy becomes unacceptable. **Save $56.94/mo until then.**

### 3.3 Regional Expansion — Multi-Region Cost Model

If active/passive multi-region is needed (e.g., for DR or latency):

| Component | Primary (East US) | Secondary (West US 2) | Total |
|---|---|---|---|
| App Service (S1) | $69.35 | $58.40 | $127.75 |
| SQL Database (S0 + geo-replica) | $14.72 | $14.72 | $29.44 |
| Key Vault | $0.03 | $0.03 | $0.06 |
| Observability | ~$0.60 | ~$0.60 | ~$1.20 |
| **Total** | **$84.70** | **$73.75** | **$158.45** |

**Multiplier:** Multi-region active/passive ≈ **1.8-2.0× single-region prod cost** (not exactly 2× because secondary can run cheaper SKU if passive-only).

**When to consider:** Only if SLA requirements exceed 99.9% (single-region App Service B1 SLA is 99.95%), or if latency to west coast users matters, or if a regulatory requirement mandates geographic redundancy.

### 3.4 Reserved Instances — When to Commit

| Service | RI Available? | 1-Year Savings | 3-Year Savings | When to Commit |
|---|---|---|---|---|
| App Service B1 (Basic) | ❌ **No** | N/A | N/A | N/A — RI only available for Premium v3+ |
| App Service S1 (Standard) | ❌ **No** | N/A | N/A | N/A — RI only available for Premium v3+ |
| App Service P1v3 | ✅ Yes | ~35% ($113.15 → ~$73.75/mo) | ~55% ($113.15 → ~$51.08/mo) | After 90 days of stable P1v3 usage |
| SQL Database (DTU model) | ❌ **No** | N/A | N/A | DTU model does not support RI — only vCore |
| SQL Database (vCore GP) | ✅ Yes | ~45% | ~62% | Only if migrating to vCore model |
| Redis Basic | ❌ **No** | N/A | N/A | N/A — RI only for Premium |

**Bottom line:** At current and near-term tiers (B1 App Service + Basic SQL), **reserved instances are not available**. RI becomes relevant only if/when the platform scales to P1v3 App Service, which is unlikely before ~100 concurrent users. **Do not pre-commit.**

---

## 4. Cost Guardrails

### 4.1 Budget Alerts

Set Azure Cost Management budget alerts per environment. Each fires to the existing `governance-alerts` action group (email to admin@httbrands.com, and Teams webhook once bd-6wyk completes).

| Environment | Resource Group | Monthly Budget | 80% Alert ($) | 100% Alert ($) | Forecast Alert |
|---|---|---|---|---|---|
| Production | `rg-governance-production` | $25 | $20 | $25 | 110% forecast |
| Staging | `rg-governance-staging` | $18 | $14 | $18 | 110% forecast |
| Dev | `rg-governance-dev` | $30 | $24 | $30 | 110% forecast |

**Implementation sketch (az CLI):**

```bash
# Production budget alert
az consumption budget create \
  --budget-name "governance-prod-monthly" \
  --resource-group rg-governance-production \
  --amount 25 \
  --time-grain Monthly \
  --start-date 2026-05-01 \
  --end-date 2027-04-30 \
  --category Cost

# Add alert at 80%
az consumption budget create-with-notifications \
  --budget-name "governance-prod-monthly" \
  --resource-group rg-governance-production \
  --amount 25 \
  --notifications '{"80pct":{"enabled":true,"operator":"GreaterThanOrEqualTo","threshold":80,"contact-emails":["admin@httbrands.com"],"contact-action-groups":["/subscriptions/32a28177-6fb2-4668-a528-6d6cafb9665e/resourceGroups/rg-governance-production/providers/Microsoft.Insights/actionGroups/governance-alerts"]}}'
```

**Bicep equivalent** (add to `infrastructure/main.bicep`):

```bicep
resource budget 'Microsoft.Consumption/budgets@2023-11-01' = {
  name: 'governance-${environment}-monthly'
  properties: {
    category: 'Cost'
    amount: environment == 'production' ? 25 : environment == 'staging' ? 18 : 30
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: '2026-05-01'
      endDate: '2027-04-30'
    }
    notifications: {
      actual80pct: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 80
        contactEmails: ['admin@httbrands.com']
      }
      actual100pct: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        contactEmails: ['admin@httbrands.com']
      }
      forecast110pct: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 110
        thresholdType: 'Forecasted'
        contactEmails: ['admin@httbrands.com']
      }
    }
  }
}
```

### 4.2 Autoscale Rules (When on S1+)

Not applicable on B1 (current tier). When/if prod upgrades to S1+:

```json
{
  "autoscale_profile": {
    "name": "governance-prod-autoscale",
    "capacity": { "minimum": 1, "maximum": 3, "default": 1 },
    "rules": [
      {
        "metric": "CpuPercentage",
        "operator": "GreaterThan",
        "threshold": 70,
        "time_window": "PT10M",
        "direction": "Increase",
        "value": 1,
        "cooldown": "PT10M"
      },
      {
        "metric": "CpuPercentage",
        "operator": "LessThan",
        "threshold": 30,
        "time_window": "PT20M",
        "direction": "Decrease",
        "value": 1,
        "cooldown": "PT20M"
      }
    ]
  }
}
```

**Scale-in asymmetry is intentional:** Scale-out at 70% over 10 min (respond quickly to load), scale-in at 30% over 20 min (don't flap). Max 3 instances caps the cost at 3× the plan price.

### 4.3 Cosmos DB Autoscale Ceiling

> **Not applicable.** The governance platform does NOT use Cosmos DB. The predecessor `control-tower` app used Cosmos (deleted April 16, 2026). The `rg-htt-domain-intelligence` resource group has a Cosmos DB (~$35/mo, see bd-w1cc) but that is a separate project.

### 4.4 Resource Locks

| Lock Type | Resource | Purpose |
|---|---|---|
| `CanNotDelete` | `rg-governance-production` | Prevent accidental deletion of production RG |
| `CanNotDelete` | `rg-governance-staging` | Prevent accidental deletion of staging RG |
| `ReadOnly` | `kv-gov-prod` | Prevent configuration changes to production Key Vault |

**Implementation:**

```bash
# Production RG lock
az lock create --name "prod-no-delete" \
  --resource-group rg-governance-production \
  --lock-type CanNotDelete \
  --notes "Protect production resources — remove lock before intentional cleanup"

# Key Vault read-only lock
az lock create --name "kv-readonly" \
  --resource-group rg-governance-production \
  --resource-name kv-gov-prod \
  --resource-type Microsoft.KeyVault/vaults \
  --lock-type ReadOnly \
  --notes "Prevent KV config changes — unlock for secret rotation only"
```

### 4.5 Tag Discipline

The production parameters already include some tags. Ensure ALL new resources include:

| Tag Key | Purpose | Example Value |
|---|---|---|
| `CostCenter` | Cost allocation | `IT-Operations` |
| `Environment` | env classification | `production` / `staging` / `dev` |
| `Owner` | responsible team | `Cloud-Team` |
| `Application` | app name | `Azure Governance Platform` |
| `ManagedBy` | IaC tool | `Bicep` |
| `bd-issue` | traceability | `zj9k` (when created for a specific issue) |

**Enforcement:** Add a `require-tags-policy.json` Azure Policy (already exists in `infrastructure/policies/require-tags-policy.json`) and assign it to the subscription. This will audit (or deny) resources created without required tags.

---

## 5. 2-Year Projection Scenarios

### 5.1 Scenario Definitions

| Parameter | Conservative | Base | Aggressive |
|---|---|---|---|
| **Tenants (Month 12)** | 5 (no growth) | 20 | 50 |
| **Tenants (Month 24)** | 5 | 40 | 100 |
| **Regions** | 1 (East US only) | 1 | 2 (East US + West US 2) from month 18 |
| **Blue-green slots** | No | Yes, from month 6 | Yes, from month 3 |
| **Redis** | No | No (in-memory sufficient) | Yes, from month 12 |
| **Reserved instances** | N/A | N/A | P1v3 1yr RI from month 12 |

### 5.2 Conservative Scenario — ~5 Tenants, Linear Low Growth

Stay on current tier set. No blue-green, no Redis, no multi-region.

| Month | Azure /mo | GitHub /mo | Total /mo | Cumulative |
|---|---|---|---|---|
| 1 | $53 | $147 | $200 | $200 |
| 2 | $53 | $147 | $200 | $400 |
| 3 | $53 | $147 | $200 | $600 |
| 4 | $53 | $147 | $200 | $800 |
| 5 | $53 | $147 | $200 | $1,000 |
| 6 | $53 | $147 | $200 | $1,200 |
| 7 | $53 | $147 | $200 | $1,400 |
| 8 | $53 | $147 | $200 | $1,600 |
| 9 | $53 | $147 | $200 | $1,800 |
| 10 | $53 | $147 | $200 | $2,000 |
| 11 | $53 | $147 | $200 | $2,200 |
| 12 | $53 | $147 | $200 | $2,400 |
| 13-18 | $53 | $147 | $200 | $3,600 |
| 18 (bump to S0 SQL) | $63 | $147 | $210 | $3,810 |
| 19-24 | $63 | $147 | $210 | $5,070 |

**Conservative 12-month:** $2,400 | **24-month:** ~$5,070

### 5.3 Base Scenario — ~20 Tenants by Month 12

Upgrades: S0 SQL at month 4 (storage headroom), S1 App Service at month 6 (slots for blue-green), minor observability growth.

| Month | Tenants | App Svc Prod | SQL Prod | Other Azure | Azure /mo | GitHub /mo | Total /mo | Cumulative |
|---|---|---|---|---|---|---|---|---|
| 1 | 5 | B1 $12.41 | Basic $4.90 | $36.09 | $53 | $147 | $200 | $200 |
| 2 | 7 | B1 $12.41 | Basic $4.90 | $36.09 | $53 | $147 | $200 | $400 |
| 3 | 9 | B1 $12.41 | Basic $4.90 | $36.09 | $53 | $147 | $200 | $600 |
| 4 | 12 | B1 $12.41 | S0 $14.72 | $36.09 | $63 | $147 | $210 | $810 |
| 5 | 15 | B1 $12.41 | S0 $14.72 | $36.09 | $63 | $147 | $210 | $1,020 |
| 6 | 17 | S1 $69.35 | S0 $14.72 | $36.09 | $120 | $147 | $267 | $1,287 |
| 7 | 18 | S1 $69.35 | S0 $14.72 | $36.09 | $120 | $147 | $267 | $1,554 |
| 8 | 19 | S1 $69.35 | S0 $14.72 | $36.09 | $120 | $147 | $267 | $1,821 |
| 9 | 20 | S1 $69.35 | S0 $14.72 | $38.09 | $122 | $147 | $269 | $2,090 |
| 10 | 20 | S1 $69.35 | S0 $14.72 | $38.09 | $122 | $147 | $269 | $2,359 |
| 11 | 20 | S1 $69.35 | S0 $14.72 | $38.09 | $122 | $147 | $269 | $2,628 |
| 12 | 20 | S1 $69.35 | S0 $14.72 | $38.09 | $122 | $147 | $269 | $2,897 |
| 13-18 | 25-30 | S1 $69.35 | S1 $29.45 | $40.09 | $139 | $147 | $286 | $4,613 |
| 19-24 | 30-40 | S1 $69.35 | S1 $29.45 | $42.09 | $141 | $147 | $288 | $6,341 |

**Base 12-month:** ~$2,897 | **24-month:** ~$6,341

### 5.4 Aggressive Scenario — ~100 Tenants by Month 24

Upgrades: S0 SQL at month 2, S1 App Service at month 3 (early slots), P1v3 at month 9, S2 SQL at month 12, Redis at month 12, multi-region at month 18.

| Month | Tenants | App Svc Prod | SQL Prod | Redis | Multi-Region Delta | Azure /mo | GitHub /mo | Total /mo | Cumulative |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 5 | B1 $12.41 | Basic $4.90 | — | — | $53 | $147 | $200 | $200 |
| 2 | 10 | B1 $12.41 | S0 $14.72 | — | — | $63 | $147 | $210 | $410 |
| 3 | 15 | S1 $69.35 | S0 $14.72 | — | — | $120 | $147 | $267 | $677 |
| 4-5 | 20 | S1 $69.35 | S0 $14.72 | — | — | $120 | $147 | $267 | $1,211 |
| 6 | 30 | S1 $69.35 | S1 $29.45 | — | — | $135 | $147 | $282 | $1,493 |
| 7-8 | 40 | S1 $69.35 | S1 $29.45 | — | — | $135 | $147 | $282 | $2,057 |
| 9 | 50 | P1v3 $113.15 | S1 $29.45 | — | — | $179 | $147 | $326 | $2,383 |
| 10-11 | 60-70 | P1v3 $113.15 | S1 $29.45 | — | — | $179 | $147 | $326 | $3,035 |
| 12 | 80 | P1v3 $113.15 | S2 $73.65 | C0 $16.06 | — | $239 | $147 | $386 | $3,421 |
| 13-17 | 80-90 | P1v3 $73.75 RI | S2 $73.65 | C0 $16.06 | — | $200 | $147 | $347 | $5,156 |
| 18 | 90 | P1v3 $73.75 RI | S2 $73.65 | C0 $16.06 | +$90 | $290 | $147 | $437 | $5,593 |
| 19-24 | 90-100 | P1v3 $73.75 RI | S2 $73.65 | C0 $16.06 | +$90 | $290 | $147 | $437 | $8,215 |

**Aggressive 12-month:** ~$3,421 | **24-month:** ~$8,215

### 5.5 Summary Comparison

| Scenario | 12-Month Total | 24-Month Total | Avg Monthly (Yr 1) | Avg Monthly (Yr 2) |
|---|---|---|---|---|
| **Conservative** | $2,400 | $5,070 | $200 | $210 |
| **Base** | $2,897 | $6,341 | $241 | $287 |
| **Aggressive** | $3,421 | $8,215 | $285 | $400 |

> **For chart-friendly data:** The monthly costs for each scenario are provided in the tables above. Each row is one data point. The 24-month cumulative values can be plotted as a stacked area chart.

---

## 6. Recommended Starting Tier + Trigger-Based Upgrade Path

### 6.1 Launch Tier Recommendation

**This is the opinionated recommendation Tyler asked for.**

| Environment | Resource | Recommended SKU | Monthly Cost | Rationale |
|---|---|---|---|---|
| **Production** | App Service | **B1 Basic** | $12.41 | 20-50× headroom for 5 users. No slots needed yet. |
| **Production** | SQL Database | **Basic (5 DTU)** | $4.90 | 57 MB DB, 2 GB cap = years of headroom at 5 tenants. |
| **Production** | Cache | **In-memory** (existing) | $0.00 | Single instance, 100% hit rate per health check. Redis not needed. |
| **Production** | Key Vault | Standard | $0.03 | Already deployed. Pennies. |
| **Production** | Observability | Per-GB free tier | $0.00 | Within 5 GB/mo allowance. |
| **Staging** | App Service | **B1 Basic** | $12.41 | Staging doesn't need more. |
| **Staging** | SQL Database | **Free** | $0.00 | Already on free tier. Adequate for testing. |
| **Dev** | App Service | **B1 Basic** | $12.41 | Dev doesn't need more. |
| **Dev** | SQL Database | **Basic** | $4.90 | Matches prod for parity. |
| **Dev** | Container Registry | **Basic** | $5.00 | Dev-only. Migrate to GHCR (bd-ll49) to save $5/mo. |
| | | **TOTAL** | **$53.40/mo** | |

**Why this tier set:**
- **B1 App Service:** 20-50× headroom for launch user count. Always-on is enabled (no cold starts). The $12.41 price point is the cheapest production-viable tier on Azure App Service (F1/D1 don't support containers or always-on).
- **Basic SQL:** The previous S0 ($14.72) was overkill — DB is 57 MB, DTU utilization < 10%. Basic at $4.90 saves $9.82/mo with adequate headroom. The 2 GB storage cap is the watch item, not DTU.
- **In-memory cache:** Works perfectly for single-instance deployment. The health check confirms 100% hit rate. Redis adds $16/mo of cost for a capability not needed until multi-instance.
- **Free SQL for staging:** No SLA needed. 32 GB storage is ample for test data.

### 6.2 Upgrade Triggers — When to Scale UP

| # | Signal | Threshold | Sustained Duration | Next Action | SKU Change | Lead Time | $ Delta /mo |
|---|---|---|---|---|---|---|---|
| 1 | App Service CPU p95 | > 70% | 1 hour | Scale up prod App Service | B1 → B2 | 5 min (Azure portal) | +$12.41 |
| 2 | App Service CPU p95 (on B2) | > 70% | 1 hour | Scale up to S1 (unlocks slots + autoscale) | B2 → S1 | 5 min | +$44.53 |
| 3 | Deploy frequency | > 2×/day during business hours | 2 weeks | Upgrade to S1 for slot-based deploy | B1 → S1 | 5 min (plan change) + 10 min (slot config) | +$56.94 |
| 4 | SQL DTU utilization | > 80% | 30 min | Scale up SQL | Basic → S0 | 5 min | +$9.82 |
| 5 | SQL database size | > 1.5 GB | — (check weekly) | Scale up SQL (for 250 GB cap) | Basic → S0 | 5 min | +$9.82 |
| 6 | Tenant count | > 20 | — | Scale up SQL preemptively | Basic → S0 | 5 min | +$9.82 |
| 7 | App Service instances | Scaled to ≥ 2 | — | Deploy Redis for shared cache | In-memory → Redis C0 | 10 min provision + 30 min config | +$16.06 |
| 8 | Cache miss rate | > 20% | 1 hour | Investigate; likely deploy Redis | In-memory → Redis C0 | 10 min + 30 min | +$16.06 |
| 9 | App Insights ingestion | > 4 GB/month | Monthly bill | Enable adaptive sampling; budget $2.30/GB over 5 GB | Same SKU | Immediate config change | +$2.30/GB |
| 10 | User count | > 50 concurrent | — | Major scaling: P1v3 + S1 SQL + Redis | Full tier upgrade | 1 hour total | +~$165 |

### 6.3 Downsize Triggers — When to Scale DOWN

Equally important. If load doesn't materialize:

| # | Signal | Threshold | Sustained Duration | Action | $ Savings /mo |
|---|---|---|---|---|---|
| 1 | App Service CPU avg | < 10% for 30 days | 30 days | If on B2+, scale down to B1 | $12.41-$56.94 |
| 2 | SQL DTU utilization | < 15% for 30 days | 30 days | If on S0+, consider downgrade to Basic | $9.82+ |
| 3 | Redis memory usage | < 10 MB for 30 days | 30 days | If on Redis, evaluate switching back to in-memory | $16.06 |
| 4 | Dev environment idle | No deploys or API calls for 14 days | 14 days | Stop dev App Service Plan (keep resources, deallocate compute) | ~$12.41 |
| 5 | Staging no deploys | No deployments for 30 days | 30 days | Consider stopping staging App Service | ~$12.41 |

### 6.4 Tiers Explicitly NOT Recommended (and Why)

| Tier | Why Rejected |
|---|---|
| **S1 App Service for launch** | +$56.94/mo for slot capability that 5 users don't need. Deploy downtime is ~10 seconds — acceptable at launch scale. Defer until bd-hofd decision or user count > 20. |
| **S0 SQL for launch** | Current Basic tier handles the 57 MB database with ease. S0's main advantage is 250 GB storage — not needed until DB grows past 1.5 GB. Saves $9.82/mo. |
| **P1v3 App Service for launch** | $113.15/mo for 2 vCPU / 8 GB RAM is massively over-provisioned. B1's 1.75 GB is 4× current usage. P1v3 only makes sense at 50+ concurrent users. |
| **Redis for launch** | $16.06/mo for a cache that's handled perfectly by in-memory. Redis needed only at multi-instance scale or if cache persistence across restarts matters. |
| **SQL Free for production** | $0/mo is tempting but: no SLA, 1 per subscription (already used by staging), serverless cold start of 30-60 seconds after idle, and the vCore model behaves differently than DTU. Keep Basic for prod reliability. |
| **Container Apps (replacing App Service)** | $0-5/mo is attractive but requires rearchitecting APScheduler to Container Apps Jobs (medium effort), introduces cold starts, and is a platform migration mid-launch. Revisit post-launch if cost pressure demands it. |
| **Hetzner/DigitalOcean VPS** | $5/mo is cheapest but sacrifices managed infrastructure, Azure AD integration simplicity, automated patching, and compliance posture. Not appropriate for a governance platform that needs to demonstrate best practices. |

---

## Appendix A: Assumptions Log

| # | Assumption | Source | Access Date | URL |
|---|---|---|---|---|
| 1 | App Service B1 Linux = $12.41/mo (East US) | Azure Retail Prices API | April 18, 2026 | https://azure.microsoft.com/en-us/pricing/details/app-service/linux/ |
| 2 | App Service S1 Linux = $69.35/mo (East US), $58.40/mo (WUS2) | Azure Retail Prices API | April 18, 2026 | https://azure.microsoft.com/en-us/pricing/details/app-service/linux/ |
| 3 | App Service P1v3 Linux = $113.15/mo | Azure Retail Prices API | April 18, 2026 | https://azure.microsoft.com/en-us/pricing/details/app-service/linux/ |
| 4 | App Service B2 Linux = ~$24.82/mo | Derived: $0.034/hr × 730hr | April 18, 2026 | Calculated from B1 hourly rate × 2 |
| 5 | SQL Basic = $4.90/mo (5 DTU, 2 GB) | Azure Pricing Page | April 18, 2026 | https://azure.microsoft.com/en-us/pricing/details/azure-sql-database/single/ |
| 6 | SQL S0 = $14.72/mo (10 DTU, 250 GB) | Azure Retail Prices API | April 18, 2026 | https://azure.microsoft.com/en-us/pricing/details/azure-sql-database/single/ |
| 7 | SQL S1 = $29.45/mo (20 DTU) | Azure Pricing Page | April 18, 2026 | Same URL as above |
| 8 | SQL S2 = $73.65/mo (50 DTU) | Azure Pricing Page | April 18, 2026 | Same URL as above |
| 9 | SQL P1 = $456.56/mo (125 DTU) | Azure Pricing Page | April 18, 2026 | Same URL as above |
| 10 | Redis Basic C0 = $16.06/mo (250 MB) | Azure Retail Prices API | April 18, 2026 | https://azure.microsoft.com/en-us/pricing/details/cache/ |
| 11 | Redis Standard C0 = $40.15/mo | Azure Retail Prices API | April 18, 2026 | Same URL as above |
| 12 | Log Analytics = $2.30/GB after 5 GB/mo free | Azure Pricing Page | April 18, 2026 | https://azure.microsoft.com/en-us/pricing/details/monitor/ |
| 13 | Key Vault = $0.03/10K operations | Azure Pricing Page | April 18, 2026 | https://azure.microsoft.com/en-us/pricing/details/key-vault/ |
| 14 | Egress Zone 1 = $0.087/GB after 100 GB free | Azure Pricing Page | April 18, 2026 | https://azure.microsoft.com/en-us/pricing/details/bandwidth/ |
| 15 | GitHub Enterprise = $21/user/month | GitHub Pricing Page | April 18, 2026 | https://github.com/pricing |
| 16 | Metric alert = $0.05/time-series/month | Azure Monitor Pricing | April 18, 2026 | https://azure.microsoft.com/en-us/pricing/details/monitor/ |
| 17 | Slots on S1+ = free (share plan compute) | Microsoft Learn | April 18, 2026 | https://learn.microsoft.com/en-us/azure/app-service/deploy-staging-slots |
| 18 | P1v3 1yr RI = ~35% savings, 3yr RI = ~55% savings | Azure Pricing Calculator | April 18, 2026 | https://azure.microsoft.com/en-us/pricing/details/app-service/linux/ |
| 19 | Current prod DB size = 57 MB | `INFRASTRUCTURE_END_TO_END.md` (Apr 16) | April 16, 2026 | Repo doc, not live-verified |
| 20 | Current dev DB size = 22 MB | `INFRASTRUCTURE_END_TO_END.md` (Apr 16) | April 16, 2026 | Repo doc, not live-verified |
| 21 | Total Azure subscription = ~$282/mo | `CHANGELOG.md` (Apr 16 entry) | April 16, 2026 | Repo doc, not live-verified |
| 22 | DTU model does NOT support reserved instances | Azure Pricing Page | April 18, 2026 | https://azure.microsoft.com/en-us/pricing/details/azure-sql-database/single/ |
| 23 | Basic/Standard App Service NOT eligible for RI | Azure Pricing Page note | April 18, 2026 | https://azure.microsoft.com/en-us/pricing/details/app-service/linux/ |

---

## Appendix B: Open Questions for Tyler

| # | Question | Why It Matters | Impact if Unresolved |
|---|---|---|---|
| 1 | **How many GitHub Enterprise seats are actually needed?** 7 seats at $21/seat = $147/mo. If some seats are inactive, reducing to 5 seats saves $42/mo ($504/yr). GitHub Team at $4/seat × 7 = $28/mo would save $119/mo but loses SAML SSO and advanced audit. | GitHub is 73% of the total bill. | Overpaying ~$504-$1,428/yr if seats or tier are over-provisioned. |
| 2 | **Should `parameters.production.json` set `enableRedis: false`?** It currently says `true`, but no Redis is deployed. If someone runs the Bicep template, it would create Redis at ~$16/mo unexpectedly. | Prevents surprise cost increase from IaC deployment. | +$16/mo if someone deploys from Bicep without checking. |
| 3 | **Is the dev environment needed continuously?** Dev costs ~$23/mo running 24/7. If dev is only used during active development sprints, stopping the App Service Plan on nights/weekends saves ~$4-8/mo. Or stopping entirely between sprints saves $23/mo. | Dev is 42% of Azure governance cost. | Paying $276/yr for an idle dev env. |
| 4 | **What's the bd-hofd decision on blue-green?** If real slot-based blue-green, prod App Service must upgrade to S1 (+$56.94/mo). If deferred, B1 stays. This is the single largest cost swing. | $56.94/mo = $683/yr. Need answer before any tier change. | Blocking cost clarity on the largest potential upgrade. |
| 5 | **Target SLA for the platform?** If 99.95% (App Service default) is sufficient, no action needed. If 99.99% is required, need multi-region + SQL geo-replication (~$160/mo prod instead of ~$18/mo). | 9× cost difference between single-region and multi-region. | Could be under-provisioned for resilience if SLA commitment exists. |
| 6 | **Data retention policy for sync data?** How many months of cost/compliance/identity/resource data should the DB retain? 12 months? 24 months? This directly affects DB growth rate and when the 2 GB Basic cap is hit. | Controls the SQL upgrade timeline. | May hit 2 GB sooner than projected if retention is unbounded. |
| 7 | **Is the `rg-htt-domain-intelligence` ($65/mo) going to launch alongside governance?** Per bd-w1cc, that RG has been idle 30 days. If it's not launching, stopping those resources saves $65/mo ($780/yr). | $65/mo is larger than the entire governance Azure bill. | Paying for an idle app with zero users. |

---

## Appendix C: Stale Document Cross-Reference

The following sections in existing docs are **superseded by this document** and should be updated or marked stale:

| Document | Section | What's Stale | Correct Value (per this doc) |
|---|---|---|---|
| `docs/LAUNCH_READINESS_AND_ROADMAP.md` | §2 Production table | Shows SQL as "S0 Standard (10 DTU)" at $14.72 | **Basic (5 DTU)** at $4.90 (changed Apr 16) |
| `docs/LAUNCH_READINESS_AND_ROADMAP.md` | §2 Production table | Shows ACR Standard at $20.00 | **ACR deleted** — prod uses GHCR (changed Apr 16) |
| `docs/LAUNCH_READINESS_AND_ROADMAP.md` | §2 Dev table | Shows SQL as S0 at $14.72 | **Basic (5 DTU)** at $4.90 (changed Apr 16) |
| `docs/LAUNCH_READINESS_AND_ROADMAP.md` | §3 Total cost | Shows $262-264/mo Azure + GitHub | **$200.40/mo** (Azure $53.40 + GitHub $147) |
| `docs/LAUNCH_READINESS_AND_ROADMAP.md` | §4 Launch cost | Shows ~$243/mo after ACR downgrade | **$200.40/mo** (further SQL downgrades + ACR deletion) |
| `docs/LAUNCH_READINESS_AND_ROADMAP.md` | §5 S1 upgrade cost | States S1 = $58.40/mo | **$69.35/mo in East US** (doc used WUS2 pricing; prod is East US) |
| `docs/operations/cost-analysis.md` | Entire document | Shows P1v2 App Service, S2 SQL, Redis C0, $33.19 total | **Completely stale** — does not match any known deployed state |
| `INFRASTRUCTURE_END_TO_END.md` | §11 Request flow | States "S0, 250 GB" for prod SQL | **Basic, 2 GB** (changed Apr 16) |
| `INFRASTRUCTURE_INVENTORY.md` | Production costs | Shows S0 SQL, ACR Standard, $35.17 subtotal | **$18.05** — SQL Basic, no ACR |

---

## Appendix D: Surprise Findings

During research for this document, the following unexpected findings were discovered. Pack Leader should assess whether any warrant new bd issues.

### Finding 1: `enableRedis: true` in Production Bicep Parameters (Severity: Medium)

**File:** `infrastructure/parameters.production.json`, line `"enableRedis": { "value": true }`

**Issue:** Redis is NOT deployed in production (no Redis resource exists in `rg-governance-production`). The application's `token_blacklist.py` gracefully falls back to in-memory storage. However, if someone runs a Bicep deployment from these parameters, a Redis Basic C0 instance (~$16.06/mo) would be created unexpectedly.

**Recommendation:** Change `enableRedis` to `false` in `parameters.production.json` and `parameters.staging.json` until Redis is intentionally needed. File as a P3 task.

### Finding 2: S1 Pricing Discrepancy in LAUNCH_READINESS_AND_ROADMAP.md

**Issue:** The LAUNCH_READINESS document states S1 App Service costs $58.40/mo and the B1→S1 delta is $46/mo. This is correct for **West US 2** but production runs in **East US** where S1 is $69.35/mo and the delta is **$56.94/mo** — a 24% higher upgrade cost than documented.

**Impact:** If the bd-hofd blue-green decision is made based on the $46/mo delta figure, the actual cost will be $10.94/mo higher than expected.

**Recommendation:** Corrected in this document. LAUNCH_READINESS should be updated.

### Finding 3: `docs/operations/cost-analysis.md` is Completely Fictional

**Issue:** This document shows a current state of P1v2 App Service ($11.53), S2 SQL ($7.50), Redis C0 ($4.60), total $33.19/mo. None of these match any known deployed state, past or present. The App Service has never been on P1v2 (went from B2→B1, not P1v2). SQL has never been S2 and $7.50 (S2 is $73.65). Redis has never been deployed for governance.

**Impact:** Anyone reading this document would get a completely wrong picture of the current infrastructure.

**Recommendation:** Archive or delete `docs/operations/cost-analysis.md`. This document supersedes it entirely. File as a P3 doc cleanup task.

---

*This document was prepared by Solutions Architect (solutions-architect-8ad3a1) on April 18, 2026, as the deliverable for bd issue zj9k. All Azure pricing sourced from Azure Retail Prices REST API and official pricing pages via web-puppy research (saved to `research/azure-pricing-west-us-2/`). Document reviewed against 15+ existing repo docs and Bicep IaC files for consistency.*

*For questions or updates, file a bd issue referencing zj9k.*

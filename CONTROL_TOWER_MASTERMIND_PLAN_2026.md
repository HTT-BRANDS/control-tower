# Control Tower 2026 — Portfolio Operating System Mastermind Plan

**Author:** Richard (code-puppy-ab8d6a) — synthesized from cross-repo audit
**Audience:** Tyler Granlund, then planning-agent for execution decomposition
**Date:** 2026-04-28
**Status:** DRAFT — pending Tyler review before planning-agent handoff

---

## TL;DR — What This Plan Says

1. **Drop the "Riverside compliance" framing.** It anchors us to the PE owner's
   needs, not ours. Riverside is a *customer of* the platform, not its brand.
2. **Restore the name "Control Tower."** It was right the first time. Bring it
   forward as the unified brand for the entire HTT portfolio operating system.
3. **Recognize the platform's actual scope.** It's not "Azure governance." It's
   an internal Portfolio Operating System spanning Azure governance, AWS BI,
   M365/SharePoint hub-and-spoke, cross-tenant identity, multi-billing-model
   reconciliation, and franchise lifecycle automation.
4. **Stop building one app. Start building a platform-of-platforms.** Five
   repos already exist solving five different parts of this. The opportunity
   is to *unify their ergonomics*, not consolidate their codebases.
5. **Embrace 2026 best practices explicitly.** FinOps Foundation maturity,
   Internal Developer Platform thinking, Domain-Driven Design boundaries,
   data-mesh-over-data-lake, OpenTelemetry, AI-native anomaly detection,
   B2B identity governance as a first-class feature.
6. **Ship immediate wins now.** Six concrete, shippable hygiene items in
   week one; structural Option C refactors in weeks 2–3; positioning narrative
   ready for Riverside review in week 4.

---

## 1. The Problem We're Actually Solving

### What Riverside sees today
- Quarterly EBITDA rollups across ~5 brands.
- Generic PE-portfolio dashboards (probably Carta, MetricsTrail, or built in-house).
- No real-time visibility into cloud spend, identity risk, compliance drift,
  cross-brand collaboration patterns, or operational telemetry.
- Annual security read-outs (RISO) treated as compliance theater.

### What HTT Brands actually has
- Five Azure tenants (HTT, BCC, FN, TLL, DCE) with OIDC federation, UAMI, zero
  stored client secrets across all of them — a setup most enterprises haven't
  achieved.
- A **proven hub-and-spoke SharePoint architecture** (DeltaSetup) deployed for
  Delta Crown Extensions, ready to template for any future brand or
  acquisition.
- A **production AWS BI stack** (DART) serving 5-minute-freshness operational
  dashboards across three salon brands with full Cognito-RBAC and POS/MBO
  ingestion.
- A **production Azure SQL data layer** (`httbi` on `htt-bi-sql-prod`) — 138
  tables, 222M rows — backing Power BI workspaces for The Lash Lounge
  franchisee operations, with cross-tenant B2B collab proven (TLL users
  authenticated against HTT Fabric workspaces).
- A **multi-tenant Azure governance platform** (this repo) with 4,000+ tests,
  WCAG 2.2 AA accessibility, CSP nonce injection, refresh token blacklisting,
  PKCE OAuth — the kind of hardening big-co security teams brag about.
- A **predecessor governance platform** (`control-tower`) with 44 Azure
  collectors, ResilientAzureClient circuit-breaker patterns, 8 persona
  dashboards, and a resumable backfill engine — battle-tested IP.

### The strategic gap
**Nobody at Riverside knows any of this exists, can leverage it, or could
replicate it.** Tyler has built the operating layer of a private cloud for a
multi-brand franchise portfolio. The "platform" is currently fragmented into
five repos with no shared identity, no shared brand, no shared narrative, and
no executive-visible value story.

That fragmentation is the bug. The unification is the opportunity.

---

## 2. The Five-Repo Audit

| Repo | Cloud | Stack | Status | What it knows |
|---|---|---|---|---|
| **azure-governance-platform** (this repo) | Azure | FastAPI + HTMX, App Service B1 | v2.5.0, prod stale | Cost, compliance, identity, resources, custom rules, audit logs, quotas, Riverside specialization |
| **control-tower** | Azure | FastAPI + React/Vite, Azure SWA | Phase 2 complete | 44 collectors, ResilientAzureClient, persona dashboards (Executive/FinOps/Security/Ops/Coach/Owner/MSP/Admin), backfill engine, identity score calculator |
| **DART** | AWS | Lambda + Glue + Athena + Cognito | Production | 5-min ingest from Mindbody/Zenoti/Autopay/CallRail, brand-segregated S3 raw → Parquet curated → Athena views, role-based RBAC, contractor-facing UI |
| **bi-migration-agent** | Azure | SQL DB + ADF + Power BI | Phase 4 done, 3b ready | 138 tables, 222M rows, ADF pipeline migration, RLS on tll_pro tables, 74 perf indexes, gate-driven cutover discipline |
| **DeltaSetup** | M365 | PowerShell PnP + SharePoint | Phase 5.1 deployed | Hub-and-spoke template (corp-hub + brand-hub), 8 sites, dynamic groups, DLP policies, Exchange Online setup, B2B/external collab patterns |

### The shared substrate already in place
- **Tenants:** HTT, BCC, FN, TLL, DCE — same five everywhere.
- **Auth:** Entra ID OIDC, UAMI, federated workload identity — consistent.
- **Tooling:** `bd` (beads) for issue tracking, GitHub Actions for CI, GHCR
  for containers — consistent.
- **Engineering culture:** test-driven, lint-clean, doc-heavy, agent-assisted
  workflows — consistent.

### The shared substrate NOT in place
- **No unified API gateway** across the five repos.
- **No shared identity graph** — TLL users in HTT Fabric is a working hack,
  not a documented capability.
- **No unified cost view** — Azure direct + AWS + Snowflake + M365/Pax8
  billing live in five places.
- **No portfolio-level executive dashboard** — each repo has its own.
- **No shared design system** — `azure-governance-platform` has 47+ CSS
  variables per brand. DART has its own React UI. Control Tower predecessor
  has yet another. DCE has SharePoint themes.
- **No shared data product contracts** — DART exposes Athena views; httbi
  exposes Power BI semantic models; governance platform exposes JSON; none
  speak to each other.

---

## 3. Mission / Vision / Values

### Mission
**Make the right thing the easy thing for every brand in the HTT portfolio.**
Operational truth, cost truth, identity truth, security truth — visible,
queryable, accountable, in one place.

### Vision (3-year)
**HTT Brands runs the most observable, cost-attributed, identity-governed
multi-brand franchise cloud in the U.S. salon industry.** When Riverside
acquires the next portfolio company, Control Tower onboards them in days, not
months. When a competitor PE firm wants to acquire the portfolio, the
diligence package writes itself.

### Values
1. **Receipts over rhetoric.** Every claim is queryable. Every dashboard has a
   timestamp and a source-of-truth pointer.
2. **Microscope and telescope in one view.** Resource-tag-level granularity,
   portfolio-level rollup. Both, on the same screen, on demand.
3. **Hub-and-spoke as the answer to "what about brand N+1?"** Adding a brand
   should be configuration, not engineering.
4. **Cost-conscious at every layer.** ~$53/mo total infrastructure for
   azure-governance-platform proves it. Stay under $100/mo for the unified
   platform.
5. **Boring tech for the reliability path, sharp tech for the value path.**
   FastAPI + Azure SQL + GHCR is boring on purpose. AI-native query, anomaly
   detection, and natural-language interfaces are where novelty lives.
6. **Open by default within the portfolio.** Brands can read each other's
   non-sensitive metrics. Cross-pollination is a feature.

---

## 4. The Rebrand — Control Tower 2026

### Name: **Control Tower**
- Historical continuity (we already used it).
- Industry-validated mental model (AWS Control Tower exists for similar reason).
- Multi-tenant native ("many flights, one tower").
- Distances from Riverside framing (Riverside is a passenger, not the airline).

### Subtitle: **Portfolio Operating System for Multi-Brand Cloud**

### Tagline: ***From the cockpit to every spoke.***

### What gets rebranded
- This repo (`azure-governance-platform`) → renamed to `control-tower` (the
  predecessor `control-tower` repo gets archived with a forwarding pointer).
- Production URL `app-governance-prod` → migrate to `control-tower-prod` (with
  the legacy hostname kept as a 301 redirect for ~90 days).
- Riverside compliance dashboard stays as a *feature* (`/riverside`), not the
  identity. Other brands and acquired companies will appear alongside it.
- Doc surface refreshes: README, ARCHITECTURE, all top-level docs to lead
  with "Control Tower" framing.

### What does NOT get rebranded
- DART stays DART. It's a product with contractor users at
  dart.salon360.ai. It becomes "Control Tower :: DART" in narrative but the
  product brand stands alone.
- bi-migration-agent stays as-is. Single-purpose, time-boxed, will sunset
  when migration completes.
- DeltaSetup stays as-is. It's a *playbook*, not a product. It gets
  documented as "Control Tower :: Franchise Onboarding Playbook."
- The control-tower predecessor repo gets archived but its IP (44 collectors,
  ResilientAzureClient pattern) gets migrated forward into the new unified
  platform.

---

## 5. Target Architecture — The Unified Control Tower

### Top-level structure (logical)

```
                          ┌───────────────────────────────┐
                          │     CONTROL TOWER (Hub)       │
                          │   Portfolio Operating System  │
                          └──────────────┬────────────────┘
                                         │
   ┌─────────────┬───────────────┬───────┴────────┬───────────────┬─────────────┐
   │             │               │                │               │             │
   ▼             ▼               ▼                ▼               ▼             ▼
┌──────┐    ┌──────────┐    ┌─────────┐    ┌──────────┐    ┌──────────┐  ┌──────────┐
│ Cost │    │ Identity │    │Compliance│    │Resources │    │   BI /   │  │Lifecycle │
│Domain│    │  Domain  │    │  Domain  │    │  Domain  │    │   DART   │  │ Playbook │
└──┬───┘    └────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘  └────┬─────┘
   │             │               │                │               │             │
   │             │               │                │               │             │
   ▼             ▼               ▼                ▼               ▼             ▼
─────────────────────────────────────────────────────────────────────────────────────
                       SHARED DATA PRODUCTS (mesh-style)
─────────────────────────────────────────────────────────────────────────────────────
   │             │               │                │               │             │
   ▼             ▼               ▼                ▼               ▼             ▼
[Azure Direct] [Pax8/CSP]   [M365/Graph]    [Azure Resource    [DART/Athena]  [DCE
 Cost Mgmt    Reseller       Identity Score   Graph KQL +       AWS Lambda     Hub-Spoke
 Anomaly      Reconciliation Risky Users      Cost Mgmt API     Glue ETL       Template
 Detection    + MOSA                                                            (PnP)]
─────────────────────────────────────────────────────────────────────────────────────
                          PORTFOLIO TENANTS (5+)
              HTT  ·  BCC  ·  FN  ·  TLL  ·  DCE  ·  (next acquisition)
```

### Physical architecture (shipped)

| Layer | Service | Today | Target |
|---|---|---|---|
| Hub UI | App Service B1 | FastAPI + HTMX | Same. Add HTMX-driven persona views. |
| Hub API | App Service B1 | FastAPI | Same. Add `/api/v2/portfolio/*` aggregations. |
| Domain workers | APScheduler in-process | Polling-based | Migrate to Azure Functions + Event Grid where M365/Azure expose change feeds. Keep polling fallback. |
| Identity store | Azure SQL Basic | Per-domain tables | Add `identity_graph` view materialized from existing tables — cross-tenant edges become first-class. |
| Cost store | Azure SQL Basic | Per-tenant cost snapshots | Add `cost_facts` star schema with date/tenant/RG/resource/tag/billing_channel dimensions. Source from Azure Cost Mgmt + Pax8 invoice ingestion. |
| BI bridge | (none today) | None | Federated query against `httbi` Azure SQL via Power BI XMLA endpoint and against DART Athena via JDBC. Read-only, on-demand. |
| Telemetry | App Insights + Log Analytics | Azure-only | Add OpenTelemetry collector → Azure Monitor + AWS X-Ray ingestion path for DART. |
| Auth | Entra ID OIDC, UAMI | Per-tenant | Add B2B-collab governance UI (who from where has access to what, when does it expire). |

### Code organization (the Option C refactor lands inside this)

```
control-tower/
├── app/
│   ├── domains/                    # ← NEW: DDD bounded contexts
│   │   ├── cost/                   #   (split from app/api/services + collectors)
│   │   │   ├── repository.py
│   │   │   ├── azure_sync.py
│   │   │   ├── pax8_sync.py        # ← NEW
│   │   │   └── alerting.py
│   │   ├── identity/
│   │   │   ├── graph_sync.py
│   │   │   ├── b2b_governance.py   # ← NEW (Lash-in-HTT-Fabric style)
│   │   │   └── score_calculator.py # ← imported from old control-tower
│   │   ├── compliance/
│   │   ├── resources/
│   │   ├── lifecycle/              # ← NEW (DCE template + brand onboarding)
│   │   └── bi_bridge/              # ← NEW (DART Athena + httbi XMLA)
│   ├── api/
│   │   ├── routes/                 # HTTP boundary only (slim down auth.py etc.)
│   │   └── services/               # cross-domain orchestration only
│   ├── core/
│   │   ├── auth/                   # split from monolithic auth modules
│   │   ├── cache/                  # split from cache.py
│   │   ├── config/                 # split from config.py (KV → keyvault.py)
│   │   ├── middleware/             # split from main.py
│   │   └── design_tokens.py        # keep as-is, brand registry
│   ├── interfaces/                 # ← NEW: external integration adapters
│   │   ├── azure/                  # ARM, Graph, Cost Mgmt, Resource Graph, Policy
│   │   ├── aws/                    # DART Athena bridge
│   │   ├── pax8/                   # CSP/MOSA reseller billing
│   │   ├── snowflake/              # TLL contractor data
│   │   └── m365/                   # SharePoint/Teams/Exchange
│   └── main.py                     # ← TARGET: ~150 lines, wiring only
├── infrastructure/                 # Bicep — unchanged structure
├── playbooks/                      # ← NEW: imported from DeltaSetup
│   └── franchise-onboarding/
└── tests/
```

---

## 6. 2026 Industry Best Practices — Where We Anchor

### The frameworks we explicitly adopt

| Framework | Why | Where it lands |
|---|---|---|
| **FinOps Foundation Maturity Model** (Crawl/Walk/Run) | Industry-standard for cloud cost discipline. Today we're at Walk — anomaly detection works, allocation doesn't yet. Run = full showback/chargeback. | Cost domain. New `/portfolio/finops-maturity` dashboard mapping our state. |
| **Internal Developer Platform (IDP) thinking** (Backstage/Port-style) | Treat the platform as a product whose customers are the brands. | Brand-onboarding wizard, service catalog, scorecards. |
| **Domain-Driven Design** | Six clear bounded contexts already exist in the data model. Make them explicit in code. | Option C refactor target shape. |
| **Data Mesh** (Zhamak Dehghani) | DART, httbi, governance platform are already separate "data products." Stop pretending they're one. Federate queries instead. | bi_bridge domain. Defines the data product contracts. |
| **CIEM** (Cloud Infrastructure Entitlement Management) | Cross-tenant identity risk is a real attack surface that no current tool addresses for HTT. | Identity domain. b2b_governance module. |
| **OpenTelemetry-everything** | Replace bespoke Prometheus + App Insights instrumentation with OTel. Industry now treats this as table stakes. | Core/telemetry. |
| **Policy-as-Code** (OPA + Azure Policy initiatives) | Compliance-as-config rather than compliance-as-doc. | Compliance domain. |
| **AI-native query/anomaly** (RAG over your own data) | 2026 expectation. Executive shouldn't pull a report — they ask. | New `/ask` endpoint. RAG over tenant data. |
| **Sustainability accounting** (Microsoft Sustainability Manager + AWS CCFT) | ESG reporting will be expected by 2027. Front-run it. | Cost domain. New carbon column on cost_facts. |
| **DORA + SPACE metrics** | Measure the platform's own engineering velocity. | New `/portfolio/sdlc-health` dashboard. |
| **Wardley mapping** | Make rebuild-vs-buy decisions explicit, especially for the AI/RAG layer. | Strategy doc, refreshed quarterly. |

### Where we explicitly do NOT chase fashion
- **No microservices.** The platform is one monolith with clean domain
  boundaries. Microservices would explode operational complexity for zero
  scale benefit at our size.
- **No Kubernetes.** App Service B1 is enough. Will reconsider above
  $200/mo or 100 req/sec sustained.
- **No GraphQL.** REST + OpenAPI is enough; the UI is HTMX, not a SPA, so
  GraphQL's main benefit (shape-on-demand) doesn't apply.
- **No event-sourcing for everything.** Only where Microsoft/AWS expose
  native change feeds (Graph subscriptions, EventBridge). Polling stays for
  the rest.
- **No multi-cloud abstraction layer.** AWS code stays in DART; Azure code
  stays in Control Tower; the bi_bridge speaks both natively, not through a
  pretend-portable abstraction.

---

## 7. The Phase Plan

### Phase 0 — Hygiene & Honesty (Week 1) ← **DO THIS FIRST**
Turn the lights on. No new features. No new framing. Just stop lying.

- Repair `.venv/` so tests run locally (`uv venv --clear && uv sync`).
- Delete dead `origin/staging` branch.
- Honesty pass on `INFRASTRUCTURE_END_TO_END.md` (matches what we did to
  `CURRENT_STATE_ASSESSMENT.md`).
- Update `CHANGELOG.md` and `WIGGUM_ROADMAP.md` to stop claiming "0 open
  issues."
- Update `mvxt` issue with today's evidence.
- Dispatch production deploy off `main` (currently stale at `:6a7306a`).
- Verify `g1cc → 918b → 0gz3` chain unblocks once prod has fresh image.

**Deliverable:** Honest, green, reproducible local + CI + prod state. No
new code shipped.

### Phase 1 — Option C Structural Refactor (Weeks 2–3)
Take the 10 files >900 LOC and split them along DDD lines. No behavior
change. Pure structural moves with import-path preservation.

- `app/main.py` (1050 LOC) → ~150 LOC wiring file + extracted middleware,
  routers, system endpoints.
- `app/core/cache.py` (1181 LOC) → `cache/inmemory.py`, `cache/redis.py`,
  `cache/decorator.py`, `cache/tenant_names.py`.
- `app/preflight/admin_risk_checks.py` (921 LOC) → per-check Strategy
  pattern under `preflight/admin_risk/`.
- `app/services/riverside_sync.py` (1075 LOC) → per-table modules under
  `services/riverside_sync/`.
- `app/services/backfill_service.py` (999 LOC) → `backfill/core.py` engine
  + `backfill/handlers/{costs,identity,compliance,resources}.py`.
- `app/api/routes/auth.py` (940 LOC) → `routes/auth.py` (HTTP) +
  `services/auth_flow.py` (PKCE/JWT).
- `app/core/config.py` (986 LOC) → `config.py` + `keyvault.py`.
- `app/core/riverside_scheduler.py` (1110 LOC) → per-check submodules.
- `app/api/services/budget_service.py` (1026 LOC) → split CRUD / sync /
  alerting.
- `app/services/lighthouse_client.py` (901 LOC) → split request/response
  layers.

**Constraint:** every file split lands its own bd issue + commit + PR
shape. Tests must be green before AND after each. No mixed-purpose
commits.

**Deliverable:** No file in `app/` exceeds 600 LOC. Test suite still
4,400+. Coverage unchanged or improved.

### Phase 2 — Domain Boundaries (Weeks 4–6)
Move from "split big files" to "make domains real." This is the DDD
extraction.

- Create `app/domains/{cost,identity,compliance,resources,lifecycle,bi_bridge}/`.
- Migrate domain-specific code from `app/api/services/`, `app/services/`,
  and `app/core/sync/` into the new domains.
- Keep `app/api/routes/` as the HTTP boundary; it imports from domains
  but domains do not import from routes.
- Add `interfaces/{azure,aws,pax8,snowflake,m365}/` adapter layer; all
  external SDK calls funnel through here.
- Define each domain's exposed interface in `domains/<x>/__init__.py`.

**Deliverable:** Six explicit domains, one external-interface adapter
layer. Dependency graph is acyclic and inspectable.

### Phase 3 — Rebrand & Repository Unification (Weeks 7–8)
- Rename this repo `azure-governance-platform` → `control-tower`.
- Archive predecessor `control-tower` repo with a forwarding README.
- Migrate any predecessor IP we want forward (44 collectors review;
  cherry-pick the good ones).
- Production URL migration with 301 redirect from old hostname.
- Doc surface rewrite — README leads with Control Tower framing.
- Riverside dashboard becomes a *feature route* (`/riverside`) not the
  identity.

**Deliverable:** Single repo, single brand, single deploy chain, single
operational story.

### Phase 4 — Cross-Repo Bridges (Weeks 9–12)
The big strategic value-add. Each bridge is independent and shippable.

- **bi_bridge :: DART** — Athena query proxy through Control Tower with
  Cognito-token-exchange-to-Entra. Surfaces salon ops metrics in the
  Control Tower UI alongside Azure governance metrics.
- **bi_bridge :: httbi** — Power BI XMLA federated query for Lash Lounge
  franchisee data. Cross-tenant identity proven; surface in Control Tower.
- **lifecycle :: DCE template** — turn DeltaSetup into a parameterized
  PowerShell-via-Control-Tower workflow. "Add new brand" wizard.
- **cost :: Pax8** — CSP/MOSA reseller billing reconciliation. Pull Pax8
  invoices, normalize against Azure Cost Mgmt direct billing, single
  ledger.
- **identity :: B2B governance UI** — visualize and manage cross-tenant
  collaboration (Lash users in HTT Fabric, etc.). Expiry dates, audit
  log, deprovisioning workflows.

**Deliverable:** Every other HTT repo is reachable through Control Tower
and surfaces its metrics in the unified UI without copy-paste.

### Phase 5 — AI-Native Layer (Weeks 13–16)
- `/ask` endpoint: RAG over the platform's own data (cost facts, identity
  graph, compliance state, audit logs). Use Azure OpenAI with
  retrieval against an indexed view of `cost_facts`,
  `identity_graph`, `compliance_state`, `audit_log`.
- Anomaly detection: cross-domain signals (e.g., "DCE bookings dropped
  while ad spend held flat") surfaced as alerts.
- Natural-language report generation for executives. "Generate the
  monthly Riverside compliance update for the July deadline" → markdown
  report draft + supporting links.

**Deliverable:** Tyler's executive stakeholders can ask English
questions and get queryable, source-cited answers.

### Phase 6 — Riverside Showcase (Weeks 17–20)
The political endgame. Build the executive narrative for Riverside with
receipts.

- Quarterly portfolio dashboard with drill-down from EBITDA-style summary
  to resource-level cost attribution.
- Compliance evidence bundle generator. Press a button, get a
  PDF/markdown/JSON bundle that satisfies Riverside's read-out
  requirements.
- "Acquisition-ready in N days" capability: turn the DCE template into a
  benchmarked process. Document time-to-onboard for the next acquired
  brand.
- Cost optimization receipts ledger: every saving achieved, attributed,
  dated, sourced. Cumulative number visible.

**Deliverable:** Riverside read-out becomes a 30-minute demo with
receipts, not a 30-page slide deck. Tyler walks in and wins.

---

## 8. Immediate Wins (Next 2 Weeks) — Concrete & Shippable

These are sized for autonomous agent execution with Tyler review at end-of-day.

| # | Win | Time | Owner | Phase |
|---|---|---|---|---|
| 1 | Repair local `.venv` so pytest runs | 5 min | Richard | 0 |
| 2 | Delete dead `origin/staging` remote branch | 1 min | Richard | 0 |
| 3 | Honesty pass on `INFRASTRUCTURE_END_TO_END.md` | 15 min | Richard | 0 |
| 4 | Update `CHANGELOG.md` to stop claiming "0 open issues" | 10 min | Richard | 0 |
| 5 | Update `WIGGUM_ROADMAP.md` honesty pass | 10 min | Richard | 0 |
| 6 | Update `mvxt` bd issue with today's staging evidence | 5 min | Richard | 0 |
| 7 | **Tyler dispatches prod deploy off `main`** | 2 min | Tyler | 0 |
| 8 | Refactor `app/main.py` (1050 → ~150 LOC) | ~2 hr | Richard | 1 |
| 9 | Refactor `app/core/cache.py` (1181 → 3-4 modules) | ~3 hr | Richard | 1 |
| 10 | Refactor `app/preflight/admin_risk_checks.py` (Strategy) | ~2 hr | Richard | 1 |
| 11 | File bd issue for repo rename `azure-governance-platform` → `control-tower` | 5 min | Richard | 3 |
| 12 | Draft new top-level `README.md` with Control Tower framing | 30 min | Richard | 3 |

**Total agent time:** ~9 hours of focused work across 2 weeks.
**Total Tyler time:** ~30 minutes of review + 2 minutes pressing the prod
deploy button.

---

## 9. Open Decisions for Tyler

These are forks in the road that need a human call before agents proceed.

### D1. Rebrand timing
- **Option A:** Rebrand AFTER Option C refactor lands (clean slate, tested,
  then renamed).
- **Option B:** Rebrand FIRST (lock in the name, then refactor under new
  brand).
- **Richard's recommendation:** A. Don't rename a sick patient.

### D2. Predecessor `control-tower` repo fate
- **Option A:** Archive read-only with forwarding README, migrate IP into new
  unified Control Tower over Phase 2.
- **Option B:** Hard delete, lift only what we want now, lose the rest.
- **Option C:** Keep parallel (running both for 6 months).
- **Richard's recommendation:** A. Cheap to keep, immediate clarity, no IP
  loss.

### D3. DART relationship
- **Option A:** DART stays independent product (contractor-facing), Control
  Tower bi_bridge just queries Athena.
- **Option B:** DART gets absorbed into Control Tower over 12 months.
- **Option C:** DART becomes Control Tower's public face (rename, refront).
- **Richard's recommendation:** A. DART has product-market fit with
  contractors. Don't break what works. Federate, don't absorb.

### D4. Riverside framing on `/riverside` route
- **Option A:** Keep Riverside as a feature route, add other-brand
  equivalents alongside.
- **Option B:** Generalize into `/portfolio/<brand>` parametric routes,
  Riverside is just one.
- **Richard's recommendation:** B. The generic version IS the Control Tower
  story. Riverside-specific framing is a one-time content pass.

### D5. Pax8 / CSP integration scope
- **Option A:** Just billing reconciliation (read-only Pax8 invoice ingest).
- **Option B:** Full CSP partner relationship (provisioning, license
  management, support tickets).
- **Richard's recommendation:** A first, B in Phase 5+ if there's signal.

### D6. AI layer build vs buy
- **Option A:** Build (Azure OpenAI + custom RAG over our own indexed data).
- **Option B:** Buy (Microsoft Copilot for Azure / Power BI Q&A / equivalent).
- **Option C:** Both — buy the off-the-shelf for general queries, build
  for portfolio-specific intelligence.
- **Richard's recommendation:** C. Don't build commodity. Build only the
  cross-tenant cross-cloud query layer that no vendor offers.

### D7. ESG / sustainability accounting urgency
- **Option A:** Full carbon attribution in Phase 1 (start now).
- **Option B:** Light carbon estimate in Phase 4, full in 2027.
- **Option C:** Wait until customers ask.
- **Richard's recommendation:** B. Capture the intent now (column in
  cost_facts), implement in Phase 4. Don't pay for it speculatively.

---

## 10. What This Plan Does NOT Cover

By intent. Naming what's out of scope is part of the plan.

- **Marketing / sales positioning** — this is internal. If Riverside wants to
  market this as a portfolio-level capability, that's a separate
  conversation.
- **Patent / IP strategy** — there's defensible IP here (cross-tenant
  identity graph patterns, multi-billing reconciliation). Out of scope for
  engineering. Tyler + legal call.
- **Hiring / team scaling** — currently a one-Tyler-plus-agents operation.
  If the platform succeeds enough to need a team, that's a Q3 2026
  conversation.
- **Pricing / chargeback to brands** — who pays for Control Tower's $53/mo +
  whatever Phase 4-6 add? Today: HTT IT budget. Long term: arguable. Not
  this plan's problem.
- **Direct user-facing brands' UX** — Control Tower is internal. The brands'
  customer-facing apps (booking, e-commerce) are unrelated.

---

## 11. Why This Plan Will Work (and Why It Might Not)

### Why it will work
1. **Five repos already exist.** This isn't a green-field megaproject. It's a
   unification of working systems.
2. **The hardest part is done.** OIDC federation across 5 tenants, B2B collab
   patterns, hub-and-spoke template, AWS BI stack, Azure SQL data layer —
   all in production.
3. **Engineering culture is consistent.** Same tooling (`bd`, GitHub,
   GHCR), same agents, same Tyler everywhere. The cross-repo synthesis
   doesn't require culture change.
4. **The strategic narrative writes itself.** Riverside will not have seen
   anything like this from any of their other portfolio companies. First-
   mover advantage at the portfolio level.
5. **Cost is microscopic.** Total spend stays under $100/mo through Phase 6.
   No CFO has ever killed a $100/mo project.

### Why it might not
1. **Tyler is one human.** Even with agents, attention is finite. If a higher-
   priority operational fire breaks out (Riverside compliance deadline
   slipping, a brand acquisition demanding attention, a security incident),
   this plan stalls.
2. **The cross-tenant identity graph is genuinely hard.** B2B governance
   tooling at this layer doesn't exist commercially. Building it means
   absorbing the complexity vendors haven't solved yet.
3. **Riverside might not care.** PE owners have their own dashboards and
   their own incentives. They might see Control Tower as IT overreach. The
   showcase phase has political risk.
4. **The five-repo unification could regress.** Each repo has its own
   dependencies, its own deploy chain, its own quirks. Unifying ergonomics
   without unifying codebases is a discipline tax.
5. **Agent-driven execution requires constant Tyler review.** Without that,
   plans drift. With it, Tyler's time becomes the bottleneck the plan was
   meant to relieve.

---

## 12. Next Step

This document is a draft. Tyler reviews. If approved, it goes to
`planning-agent` with the prompt:

> "Take `CONTROL_TOWER_MASTERMIND_PLAN_2026.md` and decompose it into the
> bd issue tree with proper dependency edges. Phase 0 issues should be
> ready-to-claim immediately. Phase 1 issues should depend on Phase 0
> closure. Estimate effort per issue and identify the critical path."

Then `pack-leader` orchestrates execution against the bd tree.

---

*Drafted by Richard (code-puppy-ab8d6a) for Tyler Granlund, 2026-04-28.*
*This is the final hoorah document. Let's go make it sick. 🐶*

# Sources & Credibility Assessment

## Tier 1 Sources (Highest Credibility)

### 1. TechEmpower Framework Benchmarks — Round 22
- **URL**: https://www.techempower.com/benchmarks/#hw=ph&test=fortune&section=data-r22
- **Date**: October 17, 2023 (Round 22); Round 23 available Feb 2025
- **Authority**: Industry-standard framework performance benchmark, open-source methodology
- **Credibility**: ★★★★★ — Independent, reproducible, transparent methodology
- **Data extracted**: Framework rankings for Fortunes test (most realistic web workload)
  - ASP.NET Core: #23, 342,523 req/s (58.5%)
  - Go (fasthttp-prefork): #24, 338,620 req/s
  - Go (fiber): #46, 276,309 req/s
  - Node.js: #246, 64,779 req/s (11.1%)
  - FastAPI: #306, 46,896 req/s (8.0%)
  - FastAPI-uvicorn: #314, 44,605 req/s (7.6%)
- **Bias**: None — vendor-neutral benchmark
- **Caveat**: Synthetic benchmarks; real-world performance depends heavily on I/O patterns, not raw throughput

### 2. Azure SDK Releases Page
- **URL**: https://azure.github.io/azure-sdk/releases/latest/index.html
- **Date**: Last updated March 2026
- **Authority**: Official Microsoft Azure SDK team
- **Credibility**: ★★★★★ — Primary source, definitive SDK inventory
- **Data extracted**:
  - Python SDK: Comprehensive client + management libraries, all stable
  - Go SDK: Client libraries stable, some management libraries missing
  - Rust SDK: ALL beta (0.x versions), zero management libraries, zero stable releases
  - .NET SDK: Most complete, first-to-ship
  - Language coverage comparison across client/management libraries
- **Bias**: None for SDK listing (Microsoft's own inventory)

### 3. Azure Functions Pricing Page
- **URL**: https://azure.microsoft.com/en-us/pricing/details/functions/
- **Date**: Accessed March 2026
- **Authority**: Official Microsoft Azure pricing
- **Credibility**: ★★★★★ — Primary source for pricing
- **Data extracted**:
  - Flex Consumption: 250,000 free executions/month, 100,000 GB-s free
  - Consumption: 1,000,000 free executions/month, 400,000 GB-s free ($0.000016/GB-s after)
  - Premium: $126.29/vCPU/month
- **Bias**: None — official pricing

### 4. Azure Functions Timer Trigger Documentation
- **URL**: https://learn.microsoft.com/en-us/azure/azure-functions/functions-bindings-timer
- **Date**: Accessed March 2026
- **Authority**: Official Microsoft documentation
- **Credibility**: ★★★★★ — Primary source
- **Data extracted**: Timer trigger configuration, Python v2 programming model, CRON expressions
- **Bias**: Naturally promotes Azure Functions

### 5. GitHub Actions Billing Documentation
- **URL**: https://docs.github.com/en/billing/concepts/product-billing/github-actions
- **Date**: Accessed March 2026
- **Authority**: Official GitHub documentation
- **Credibility**: ★★★★★ — Primary source for billing
- **Data extracted**:
  - GitHub Free: 2,000 min/month, 500MB artifact storage, 10GB cache
  - GitHub Pro: 3,000 min/month, 1GB storage, 10GB cache
  - GitHub Free for orgs: 2,000 min/month
  - GitHub Team: 3,000 min/month, 2GB storage, 10GB cache
  - Free for self-hosted runners and public repos
- **Bias**: None — official pricing

### 6. Azure DevOps Pricing
- **URL**: https://azure.microsoft.com/en-us/pricing/details/devops/azure-devops-services/
- **Date**: Accessed March 2026
- **Authority**: Official Microsoft pricing
- **Credibility**: ★★★★★ — Primary source
- **Data extracted**:
  - First 5 users: Free (Basic plan)
  - Additional users: $6/user/month
  - 1 free Microsoft-hosted parallel job (1,800 min/month)
  - Additional parallel jobs: $40/month each
  - Self-hosted: 1 free, then $15/month each
- **Bias**: None — official pricing

---

## Tier 2 Sources (High Credibility)

### 7. SvelteKit Documentation
- **URL**: https://svelte.dev/docs/kit/introduction
- **Date**: Accessed March 2026
- **Authority**: Official SvelteKit documentation (maintained by Svelte team/Vercel)
- **Credibility**: ★★★★☆ — Primary source for SvelteKit
- **Data extracted**: Feature overview, SSR capabilities, form actions, adapters, deployment options
- **Bias**: Naturally promotes SvelteKit advantages

### 8. Next.js Documentation (App Router)
- **URL**: https://nextjs.org/docs/app/getting-started
- **Date**: Accessed March 2026
- **Authority**: Official Next.js documentation (Vercel)
- **Credibility**: ★★★★☆ — Primary source for Next.js
- **Bias**: Vercel-centric (promotes Vercel hosting, serverless patterns)

### 9. Templ Documentation
- **URL**: https://templ.guide/
- **Date**: Accessed March 2026
- **Authority**: Official Templ project documentation
- **Credibility**: ★★★★☆ — Primary source for Templ
- **Data extracted**: Go HTML templating, compiled components, SSR, no JavaScript requirement, IDE support
- **Bias**: Naturally promotes Go + Templ approach

### 10. Azure SDK for Python — Releases
- **URL**: https://azure.github.io/azure-sdk/releases/latest/python.html
- **Date**: Last updated March 2026
- **Authority**: Official Microsoft Azure SDK team
- **Credibility**: ★★★★★ — Definitive Python SDK inventory
- **Data extracted**: Full list of Python client and management libraries with version status

### 11. Azure SDK for Go — Releases
- **URL**: https://azure.github.io/azure-sdk/releases/latest/go.html
- **Date**: Last updated March 2026
- **Authority**: Official Microsoft Azure SDK team
- **Credibility**: ★★★★★ — Definitive Go SDK inventory
- **Data extracted**: Go client libraries (some stable), management library gaps identified

### 12. Azure SDK for Rust — Releases
- **URL**: https://azure.github.io/azure-sdk/releases/latest/rust.html
- **Date**: Last updated March 2026
- **Authority**: Official Microsoft Azure SDK team
- **Credibility**: ★★★★★ — Definitive Rust SDK inventory
- **Data extracted**: ALL beta (crate versions 0.x), no management libraries, not production-ready

---

## Tier 3 Sources (Domain Knowledge)

### 13. Project Codebase Analysis
- **Source**: Direct analysis of azure-governance-platform repository
- **Files analyzed**: pyproject.toml, ARCHITECTURE.md, COST_OPTIMIZATION.md, app/core/scheduler.py, app/core/database.py
- **Credibility**: ★★★★★ — Primary source (the actual codebase)
- **Data extracted**: 
  - Current dependencies and versions
  - Architecture overview
  - Cost structure ($73/month)
  - Scheduler configuration (10 jobs)
  - Database setup (SQLAlchemy + SQLite/Azure SQL)
  - Scale: 725 files, ~20 tables, 10-30 users

### 14. Industry Experience / Domain Knowledge
- **Source**: Professional experience with Python/FastAPI, Django, .NET, Go, Azure
- **Credibility**: ★★★☆☆ — Expert opinion, not primary data
- **Data extracted**:
  - Developer productivity comparisons
  - Memory footprint estimates
  - Migration effort estimates
  - ORM feature comparisons
  - APScheduler vs Celery operational experience

---

## Sources NOT Used (and why)

| Source Type | Why Excluded |
|-------------|-------------|
| Medium blog posts comparing frameworks | Typically outdated, biased, not authoritative |
| YouTube framework comparison videos | Entertainment-focused, rarely comprehensive |
| Reddit r/programming threads | Anecdotal, opinion-heavy |
| Framework creator's benchmark claims | Self-serving, cherry-picked metrics |
| ChatGPT/AI-generated comparisons | Not primary sources, potential hallucination |
| Stack Overflow answers older than 2024 | Outdated for rapidly evolving frameworks |

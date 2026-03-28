# Technology Stack Alternatives Analysis

## Azure Governance Platform — March 2026

### Executive Summary

This research evaluates technology alternatives for the Azure Governance Platform, a multi-tenant dashboard serving 10-30 users, currently running on **Python FastAPI + HTMX + Jinja2 + Tailwind CSS** on Azure App Service B1 (1.75GB RAM, 1 core) at ~$73/month.

### ⚡ Bottom Line Recommendation

**Stay with the current stack (FastAPI + HTMX + Jinja2 + Tailwind)**. The analysis across five comparison dimensions shows that the current stack is the optimal choice given the project's constraints:

| Factor | Verdict |
|--------|---------|
| **Rewrite Cost** | Any framework switch = 3-6 months of rewrite for 725+ files, 50+ templates |
| **Performance** | Current stack handles 10-30 users trivially; benchmarks are irrelevant at this scale |
| **Azure SDK** | Python has the best Azure SDK after .NET; Go/Rust are immature for governance APIs |
| **Team Skills** | Existing Python expertise; no benefit to learning Go/C#/Svelte for this use case |
| **Cost** | Already optimized to $73/mo; no stack change would meaningfully reduce this |

### Key Findings by Area

#### 1. Web Framework Comparison
- **Current stack wins** for this project size and team
- Next.js/SvelteKit add build complexity with no dashboard benefit at 10-30 users
- Django + HTMX is the only viable "lateral move" but offers no compelling advantage
- Blazor Server would lock to .NET ecosystem with no meaningful gain
- Go + Templ + HTMX is interesting but immature ecosystem, especially for Azure governance

#### 2. Language Comparison for Azure Governance
- **Python** and **.NET** are the only production-ready choices for Azure management SDKs
- **Go** Azure SDK has gaps in management libraries (cost management, policy insights)
- **Rust** Azure SDK is entirely beta — zero stable releases, zero management libraries
- .NET has native Azure advantages but requires full team retooling

#### 3. Background Job Scheduling
- **APScheduler (current) is sufficient** for 6-10 jobs at this scale
- Azure Functions timer triggers would add architectural complexity for no gain
- Durable Functions are overkill — designed for orchestrating hundreds of functions
- Celery + Redis adds infrastructure cost ($5-15/mo Redis) for unnecessary distributed computing

#### 4. ORM / Database Access
- **SQLAlchemy (current) is the right choice** for ~20 tables with simple CRUD
- Alembic provides robust migrations
- Django ORM would only make sense if switching to Django framework entirely
- Tortoise ORM adds no meaningful advantage
- Raw SQL introduces maintenance burden with no performance benefit at this scale

#### 5. CI/CD Pipeline
- **GitHub Actions (current) is the better choice** for this project
- 2,000 free minutes/month is more than sufficient
- OIDC federation is well-documented for Azure deployments
- Azure DevOps adds complexity with no benefit unless already in the Microsoft ecosystem

### Research Methodology
- **Sources**: Official documentation, TechEmpower benchmarks, Azure SDK release pages, pricing pages
- **Date**: March 27, 2026
- **Approach**: Multi-dimensional analysis (security, cost, complexity, stability, compatibility)
- **Context**: Analyzed against actual codebase of 725 files, ~20 DB tables, 10-30 users

### Files in This Research
| File | Contents |
|------|----------|
| `README.md` | This executive summary |
| `analysis.md` | Detailed multi-dimensional analysis across all 5 comparison areas |
| `sources.md` | All sources with credibility assessments |
| `recommendations.md` | Project-specific recommendations with prioritized action items |
| `raw-findings/benchmarks.md` | TechEmpower benchmark data |
| `raw-findings/azure-sdk-coverage.md` | Azure SDK language coverage comparison |
| `raw-findings/scheduling-options.md` | Background job scheduling comparison |
| `raw-findings/cicd-pricing.md` | CI/CD pricing comparison data |

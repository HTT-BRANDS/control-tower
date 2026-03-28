# Detailed Multi-Dimensional Analysis

## 1. Web Framework Comparison

### FastAPI + HTMX + Jinja2 + Tailwind (Current Stack)

| Dimension | Assessment | Score |
|-----------|-----------|-------|
| **Security** | JWT + Azure AD auth, battle-tested middleware, CSRF via HTMX headers | ★★★★☆ |
| **Cost** | Zero framework licensing, minimal memory (~150-300MB), runs on B1 | ★★★★★ |
| **Complexity** | No build step, Jinja2 templates are straightforward, HTMX is 14KB | ★★★★★ |
| **Stability** | FastAPI 0.109+, mature ecosystem, Starlette foundation since 2018 | ★★★★☆ |
| **Performance** | 47K req/s (TechEmpower), more than enough for 10-30 users | ★★★★☆ |
| **Compatibility** | Native Azure SDK, Python ecosystem, no transpilation needed | ★★★★★ |
| **Maintenance** | Active development, Pydantic v2, clear upgrade paths | ★★★★☆ |

**Strengths for this project:**
- 725 files already written and tested — switching costs are enormous
- HTMX eliminates build tooling entirely (no webpack, no node_modules for framework)
- Jinja2 templates are rendered server-side — no hydration issues, great for dashboards
- Python Azure SDK is the most mature after .NET
- Team already has Python expertise

**Weaknesses:**
- No real-time WebSocket support out-of-the-box (would need FastAPI WebSockets)
- Template reuse requires Jinja2 macros/includes (less elegant than components)
- No type-checked templates (unlike Templ or Blazor)

---

### Next.js (App Router)

| Dimension | Assessment | Score |
|-----------|-----------|-------|
| **Security** | Server Components reduce client exposure, but adds XSS surface area with client components | ★★★☆☆ |
| **Cost** | Requires Node.js runtime (+50-100MB RAM), Vercel hosting or custom setup | ★★★☆☆ |
| **Complexity** | App Router mental model is complex (RSC, server/client boundary), build tooling overhead | ★★☆☆☆ |
| **Stability** | App Router is stable but still evolving (frequent breaking changes between majors) | ★★★☆☆ |
| **Performance** | React hydration overhead, larger bundle sizes (minimum 80KB+ JS) | ★★★☆☆ |
| **Compatibility** | Azure SDK for JS exists but Python SDK is more complete for management ops | ★★★☆☆ |
| **Maintenance** | Fast release cycle = frequent updates needed, Vercel-centric ecosystem | ★★☆☆☆ |

**Would require:**
- Complete rewrite of all 50+ templates to React components
- Rewrite all Python services to TypeScript/Node.js (or maintain dual backends)
- New build pipeline (Next.js build step)
- Azure SDK for JavaScript is less complete for management libraries
- Team would need to learn React, TypeScript, App Router concepts

**Dashboard advantages (theoretical):**
- React component ecosystem for charts (Recharts, Nivo)
- Better client-side interactivity for complex filtering
- Server Components could reduce data fetching boilerplate

**Verdict:** ❌ **Not recommended.** Full rewrite cost (~3-6 months) with no compelling advantage for a 10-30 user dashboard. The current HTMX approach handles dashboard interactions effectively.

---

### SvelteKit

| Dimension | Assessment | Score |
|-----------|-----------|-------|
| **Security** | Good CSP support, form actions reduce client-side attack surface | ★★★★☆ |
| **Cost** | Smaller bundles than React (~40% smaller), Node.js runtime needed | ★★★★☆ |
| **Complexity** | Simpler mental model than React, but still requires build step + JS ecosystem | ★★★☆☆ |
| **Stability** | Svelte 5 (Runes) is a significant API change; ecosystem is smaller | ★★★☆☆ |
| **Performance** | Excellent — compiles to vanilla JS, minimal runtime, fast rendering | ★★★★★ |
| **Compatibility** | Same Azure JS SDK limitations as Next.js | ★★★☆☆ |
| **Maintenance** | Smaller community, fewer enterprise examples, but growing rapidly | ★★★☆☆ |

**Advantages:**
- Lighter than React — compiled components, no virtual DOM
- SSR + form actions pattern is similar to HTMX approach
- Zero-config deployments with adapters (node, static, vercel)
- Excellent developer experience, less boilerplate

**Disadvantages:**
- Still requires full rewrite of Python backend to JS/TS
- Smaller ecosystem than React — fewer ready-made dashboard components
- Svelte 5 (Runes) broke backward compatibility — ecosystem fragmentation
- Azure governance libraries in TypeScript are less mature

**Verdict:** ❌ **Not recommended.** While SvelteKit is technically superior to Next.js for dashboards, it still requires a complete rewrite and JS ecosystem adoption with less Azure SDK maturity.

---

### Blazor Server (C#/.NET)

| Dimension | Assessment | Score |
|-----------|-----------|-------|
| **Security** | ASP.NET Core identity system is enterprise-grade, Azure AD native support | ★★★★★ |
| **Cost** | .NET runtime is larger (~200-400MB RAM baseline), but App Service native | ★★★☆☆ |
| **Complexity** | C# is verbose for CRUD apps, Blazor component model has learning curve | ★★★☆☆ |
| **Stability** | .NET 8 LTS (supported until 2026), .NET 9 available, very stable | ★★★★★ |
| **Performance** | 342K req/s (ASP.NET Core in TechEmpower), 7x faster than FastAPI | ★★★★★ |
| **Compatibility** | Best-in-class Azure SDK, native Azure AD, SignalR built-in | ★★★★★ |
| **Maintenance** | Microsoft long-term support, enterprise backing, predictable release cycle | ★★★★★ |

**Azure-native advantages:**
- Azure SDK for .NET is the most complete and first-to-ship new features
- Native Azure AD integration via Microsoft.Identity.Web
- SignalR for real-time UI updates (built into Blazor Server)
- App Service has first-class .NET support (startup time, diagnostics)
- Azure DevOps Pipelines have deeper .NET integration

**Critical disadvantages:**
- **Complete rewrite of 725 files** — 3-6+ months of work
- Blazor Server maintains persistent SignalR connection per user — heavier on B1 tier
- C# is more verbose than Python for CRUD operations and API integrations
- Team would need to learn C#, .NET ecosystem, Blazor component model
- Blazor's component model is more rigid than HTMX's progressive enhancement
- **RAM pressure on B1 (1.75GB)**: Each Blazor Server connection uses ~250KB, but .NET runtime itself uses 200-400MB baseline

**Verdict:** ❌ **Not recommended despite Azure advantages.** The rewrite cost is prohibitive, .NET runtime memory overhead is higher on B1 tier, and Python is productive enough for this CRUD + API integration pattern. The performance advantage is irrelevant for 10-30 users.

---

### Django + HTMX

| Dimension | Assessment | Score |
|-----------|-----------|-------|
| **Security** | Django security middleware is industry-leading (CSRF, XSS, SQL injection) | ★★★★★ |
| **Cost** | Similar to FastAPI — Python runtime, comparable memory footprint | ★★★★★ |
| **Complexity** | Batteries-included reduces boilerplate, but Django ORM is different from SQLAlchemy | ★★★★☆ |
| **Stability** | Django 5.x LTS, 20+ year track record, massive community | ★★★★★ |
| **Performance** | Slightly slower than FastAPI for async ops, but comparable for SSR dashboards | ★★★★☆ |
| **Compatibility** | Same Python Azure SDK, Django adapts well to Azure App Service | ★★★★★ |
| **Maintenance** | Excellent LTS policy (24-month cycles), huge community, abundant resources | ★★★★★ |

**What Django would add:**
- Free admin panel for data management (audit logs, tenant config, sync jobs)
- Built-in ORM with excellent migration tooling
- Battle-tested authentication system
- Class-based views for repetitive CRUD patterns
- django-tables2, django-filter for dashboard data

**What you'd lose:**
- FastAPI's automatic OpenAPI/Swagger docs
- Pydantic model integration (Django uses serializers)
- Async-first architecture (Django async is bolted on, not native)
- All existing SQLAlchemy models + Alembic migrations

**Migration effort:**
- Rewrite ~30 route files to Django views
- Convert SQLAlchemy models to Django ORM models
- Recreate Alembic migrations as Django migrations
- Adapt Jinja2 templates to Django template language (or use django-jinja)
- Estimated: **6-10 weeks** for experienced developer

**Verdict:** ⚠️ **Viable lateral move, but not recommended.** Django is an excellent framework, but the migration cost (6-10 weeks) provides no compelling advantage over the current FastAPI stack. The free admin panel is the strongest argument, but can be replicated with a simple CRUD interface in HTMX.

---

### Go + Templ + HTMX

| Dimension | Assessment | Score |
|-----------|-----------|-------|
| **Security** | Go's type safety prevents many runtime errors, but fewer security middleware options | ★★★★☆ |
| **Cost** | Minimal memory footprint (~20-50MB), single binary deployment | ★★★★★ |
| **Complexity** | Go is more verbose than Python, Templ is new with smaller community | ★★☆☆☆ |
| **Stability** | Go is stable, but Templ is v0.x, Azure SDK for Go has management library gaps | ★★☆☆☆ |
| **Performance** | Excellent — Go web frameworks at 275K+ req/s, ~6x faster than FastAPI | ★★★★★ |
| **Compatibility** | Azure SDK for Go lacks cost management, policy insights libraries | ★★☆☆☆ |
| **Maintenance** | Go is easy to maintain, but Templ + HTMX pattern is niche, fewer resources | ★★☆☆☆ |

**Advantages:**
- Memory footprint: 20-50MB vs 150-300MB for Python — huge win on B1 tier
- Single binary deployment — no pip, no virtualenv, no dependency conflicts
- Compiled code with type-safe templates (Templ catches errors at build time)
- No garbage collection pauses (Go's GC is excellent)
- Cross-compilation: build on Mac, deploy Linux binary

**Critical disadvantages:**
- **Azure SDK for Go is missing key governance libraries:**
  - `azure-mgmt-costmanagement` — ❌ No Go equivalent
  - `azure-mgmt-policyinsights` — ❌ No Go equivalent
  - `azure-mgmt-security` — ❌ No Go equivalent
  - Would need raw REST API calls for 40%+ of current functionality
- Templ is v0.x — not yet stable, API may change
- Go is 2-3x more verbose than Python for CRUD operations
- No equivalent of Pydantic for data validation (struct tags are weaker)
- Complete rewrite required (4-6+ months)

**Verdict:** ❌ **Not recommended.** The Azure SDK gaps are a dealbreaker. You'd be writing raw HTTP calls against Azure REST APIs for cost management, policy insights, and security — exactly the governance functions this platform is built for. Performance is irrelevant at 10-30 users.

---

## 2. Language Comparison for Azure Governance Tooling

### Azure SDK Maturity by Language (March 2026)

| Feature | Python | .NET (C#) | Go | Rust | JavaScript |
|---------|--------|-----------|-----|------|-----------|
| **azure-identity** | ✅ Stable | ✅ Stable | ✅ Stable | ⚠️ Beta 0.33 | ✅ Stable |
| **azure-mgmt-resource** | ✅ Stable v23 | ✅ Stable | ✅ Stable | ❌ None | ✅ Stable |
| **azure-mgmt-costmanagement** | ✅ Stable v4 | ✅ Stable | ❌ None | ❌ None | ✅ Stable |
| **azure-mgmt-policyinsights** | ✅ Stable v1 | ✅ Stable | ❌ None | ❌ None | ✅ Stable |
| **azure-mgmt-security** | ✅ Stable v5 | ✅ Stable | ❌ None | ❌ None | ✅ Stable |
| **azure-mgmt-authorization** | ✅ Stable v4 | ✅ Stable | ✅ Stable | ❌ None | ✅ Stable |
| **azure-mgmt-subscription** | ✅ Stable v3 | ✅ Stable | ✅ Stable | ❌ None | ✅ Stable |
| **azure-keyvault-secrets** | ✅ Stable v4.7 | ✅ Stable | ✅ Stable | ❌ None | ✅ Stable |
| **Microsoft Graph** | ✅ Stable | ✅ Stable | ✅ Stable | ❌ None | ✅ Stable |
| **Management Libraries Total** | ~180+ | ~200+ | ~100+ | 0 | ~160+ |
| **SDK Last Updated** | Mar 2026 | Mar 2026 | Mar 2026 | Mar 2026 | Mar 2026 |

### Memory Footprint on B1 App Service (1.75GB RAM)

| Language | Runtime Baseline | App + Dependencies | Available for Work | Verdict |
|----------|-----------------|-------------------|-------------------|---------|
| **Python (FastAPI)** | ~30MB | ~150-300MB | ~1.4-1.6GB | ✅ Comfortable |
| **C# (.NET 8)** | ~50MB | ~200-400MB | ~1.3-1.5GB | ✅ Comfortable |
| **Go** | ~5MB | ~20-50MB | ~1.7GB | ✅ Excellent |
| **Rust** | ~2MB | ~10-30MB | ~1.7GB | ✅ Excellent (if SDK existed) |
| **Node.js** | ~40MB | ~100-250MB | ~1.5-1.65GB | ✅ Comfortable |

**Note:** At 10-30 users, memory is not a constraint for any language on B1 tier. Go and Rust would only matter if scaling to hundreds of concurrent users on the same B1 instance.

### Developer Productivity for CRUD + API Integration

| Task | Python | C# (.NET) | Go | Rust |
|------|--------|-----------|-----|------|
| Define API route | 3 lines (decorator) | 5-8 lines (controller) | 10-15 lines (handler) | 15-20 lines (handler) |
| Parse JSON request | Automatic (Pydantic) | Automatic (model binding) | Manual (json.Unmarshal) | Manual (serde) |
| DB query + ORM | 2-3 lines (SQLAlchemy) | 2-3 lines (EF Core) | 5-10 lines (sqlx) | 5-10 lines (sqlx/diesel) |
| HTTP client call | 2-3 lines (httpx) | 3-5 lines (HttpClient) | 5-8 lines (http.Get) | 8-12 lines (reqwest) |
| Error handling | try/except | try/catch | if err != nil (verbose) | Result<T,E> (verbose) |
| Startup time (dev) | <1s (uvicorn) | 2-3s (dotnet run) | <1s (go run) | 5-15s (cargo build) |
| **Lines of code ratio** | **1x** | **1.3x** | **2x** | **2.5x** |

### Azure-Native Advantages of .NET

| Advantage | Impact for This Project |
|-----------|------------------------|
| Azure SDK releases first for .NET | Low — Python SDK lags by days/weeks, not months |
| Native Azure AD with Microsoft.Identity.Web | Low — current PyJWT + azure-identity works fine |
| App Service optimized for .NET | Low — Python on App Service works fine on B1 |
| Azure DevOps has deeper .NET integration | Low — using GitHub Actions which works for both |
| SignalR for real-time (Blazor Server) | Medium — could benefit sync status dashboard, but HTMX polling is sufficient |
| Visual Studio Azure tooling | Low — team uses VS Code |

---

## 3. Background Job Scheduling Comparison

### Current Architecture
- **APScheduler** (AsyncIOScheduler) running in-process with FastAPI
- 10 scheduled jobs: costs, compliance, resources, identity, riverside, DMARC, hourly MFA, daily full, weekly threat, monthly report
- Frequencies: hourly to monthly
- All jobs make Azure API calls and write to database

### APScheduler (Current)

| Aspect | Assessment |
|--------|-----------|
| **Reliability** | Runs in-process — if app restarts, jobs are lost until next schedule |
| **Monitoring** | Basic logging only; no dashboard, no retry UI |
| **Error handling** | Try/except in each job; failures logged but no alerting pipeline |
| **Scaling** | Single instance only — duplicate execution if multiple workers |
| **Cost** | $0 — included in app process |
| **Complexity** | Minimal — 150 lines of scheduler config |
| **State persistence** | None — schedule in memory, resets on restart |

**Key risk:** If the App Service restarts during a sync job, that run is lost. APScheduler does not persist job state. On B1 tier with possible platform restarts, this means occasional missed syncs.

### Azure Functions Timer Triggers

| Aspect | Assessment |
|--------|-----------|
| **Reliability** | Platform-managed — Azure guarantees execution, built-in retry |
| **Monitoring** | Application Insights integration, Azure Portal dashboard |
| **Error handling** | Automatic retry policies, dead letter queues |
| **Scaling** | Managed by platform — no duplicate execution concerns |
| **Cost** | **$0** — well within Consumption free tier (1M executions, 400K GB-s/month) |
| **Complexity** | Separate deployment artifact — functions app alongside web app |
| **State persistence** | Built-in timer state tracking, catches up missed runs |

**Advantages:**
- Platform-managed reliability — no missed jobs on app restart
- Built-in monitoring via Azure Portal + Application Insights
- Free at this scale (Consumption plan)
- Each function isolated — one failure doesn't affect others

**Disadvantages:**
- **Architectural complexity**: Separate repo/deployment, shared database access
- **Cold start**: Consumption plan has 1-10s cold start (fine for background jobs)
- **Code duplication**: Sync logic would need to be shared between app and functions
- **Two deployment pipelines**: App Service + Functions App
- **Local development**: Azure Functions Core Tools needed, different dev experience

### Azure Durable Functions

| Aspect | Assessment |
|--------|-----------|
| **Reliability** | Orchestrator guarantees completion, checkpoint/replay pattern |
| **Monitoring** | Durable Functions Monitor dashboard, activity history |
| **Error handling** | Built-in retry, circuit breaker, compensation patterns |
| **Scaling** | Fan-out/fan-in for parallel execution across tenants |
| **Cost** | Same as Functions Consumption — $0 at this scale |
| **Complexity** | **High** — orchestrator pattern, activity functions, entity functions |
| **State persistence** | Full state persistence via Azure Storage |

**Overkill for this project.** Durable Functions are designed for:
- Long-running workflows (hours/days)
- Complex orchestrations with branching logic
- Fan-out/fan-in across hundreds of parallel tasks
- Human-in-the-loop approval workflows

The current 10 jobs are simple "fetch data, transform, store" operations. Durable Functions would add significant complexity for no benefit.

### Celery + Redis

| Aspect | Assessment |
|--------|-----------|
| **Reliability** | Worker process — reliable with persistence broker |
| **Monitoring** | Flower dashboard, Celery events |
| **Error handling** | Configurable retry, exponential backoff, dead letter |
| **Scaling** | Multiple workers, distributed across machines |
| **Cost** | **$5-15/month** — requires Redis instance (Azure Cache for Redis Basic: $13.14/mo) |
| **Complexity** | Medium — separate worker process, Redis broker, beat scheduler |
| **State persistence** | Redis persistence, result backend |

**Disadvantages for this project:**
- Adds Redis infrastructure cost ($13+/month, ~18% of current $73/month budget)
- Already using Redis for caching — would need to share or add instance
- Celery is designed for distributed task queues — overkill for 10 scheduled jobs
- Adds operational complexity (worker process, beat scheduler, monitoring)
- Python-specific — no advantage if considering language switch

### Recommendation for Scheduling

**Keep APScheduler with targeted improvements:**

1. **Add job state persistence**: Use SQLite/Azure SQL job store instead of in-memory
   ```python
   from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
   scheduler = AsyncIOScheduler(
       jobstores={'default': SQLAlchemyJobStore(url=settings.database_url)}
   )
   ```

2. **Add error alerting**: Send Teams webhook on job failures (already have Teams webhook service)

3. **Add execution logging**: Write job results to audit_log table for visibility

4. **Consider Azure Functions only if**: Job reliability becomes a documented problem, or you need to scale the app to multiple instances (which would cause duplicate job execution with APScheduler)

---

## 4. ORM / Database Access Comparison

### Current Setup
- SQLAlchemy 2.0+ with declarative base
- Alembic for migrations (7 migration files)
- ~20 tables with simple CRUD + aggregation queries
- SQLite for development, Azure SQL S0 for production
- Custom repository pattern with session management

### SQLAlchemy 2.0 (Current)

| Aspect | Assessment |
|--------|-----------|
| **Query building** | Fluent API, both ORM and Core modes, 2.0 style with `select()` | 
| **Migrations** | Alembic — industry standard, auto-generates from model diffs |
| **Type safety** | Good with 2.0 style (Mapped, mapped_column), mypy plugin |
| **Performance** | Excellent with eager loading, lazy loading configurable |
| **Multi-DB support** | SQLite → Azure SQL migration is seamless (already working) |
| **Async support** | Full async via AsyncSession (using in current codebase) |
| **Community** | Massive — 15K+ GitHub stars, used by FastAPI, Flask, Pyramid |
| **Learning curve** | Moderate — powerful but complex for advanced usage |

### Tortoise ORM

| Aspect | Assessment |
|--------|-----------|
| **Query building** | Django-inspired API, simpler than SQLAlchemy |
| **Migrations** | Aerich — less mature than Alembic, fewer features |
| **Type safety** | Good with type hints, but less mature tooling |
| **Performance** | Async-first, good for FastAPI integration |
| **Multi-DB support** | SQLite, PostgreSQL, MySQL — no Azure SQL/MSSQL support |
| **Async support** | Native async — no sync mode at all |
| **Community** | Smaller — 4K GitHub stars, niche usage |
| **Learning curve** | Low — Django-like, easy to learn |

**Dealbreaker:** No MSSQL/Azure SQL support. The project uses Azure SQL S0 in production.

### Django ORM (standalone or with Django)

| Aspect | Assessment |
|--------|-----------|
| **Query building** | Elegant queryset API, excellent for CRUD |
| **Migrations** | Django migrations — excellent, auto-detect, squashable |
| **Type safety** | Improving with django-stubs, but weaker than SQLAlchemy 2.0 |
| **Performance** | Good, but no async queries until Django 4.1+, still limited |
| **Multi-DB support** | Excellent — all major databases including MSSQL via django-mssql-backend |
| **Async support** | Partial — async views but sync ORM (async ORM is limited) |
| **Community** | Massive — part of Django's 30K+ star ecosystem |
| **Learning curve** | Low — very intuitive API |

**Note:** Using Django ORM standalone (without Django framework) is possible but awkward — you'd need Django installed and configured just for the ORM. Not recommended unless switching to Django entirely.

### Raw SQL (direct queries)

| Aspect | Assessment |
|--------|-----------|
| **Query building** | Full control, maximum performance optimization |
| **Migrations** | Manual — write SQL migration scripts by hand |
| **Type safety** | None — string SQL queries, runtime errors only |
| **Performance** | Best possible — no ORM overhead |
| **Multi-DB support** | Requires different SQL for SQLite vs MSSQL (dialect differences) |
| **Async support** | Via asyncpg/aioodbc — fully async |
| **Community** | N/A — SQL is universal |
| **Learning curve** | Low for SQL, high for maintaining migration scripts |

**Not recommended for this project.** The ~20 tables with simple CRUD don't benefit from raw SQL optimization, but would suffer from:
- Manual migration management
- SQL dialect differences between SQLite (dev) and MSSQL (prod)
- No model validation (currently using Pydantic + SQLAlchemy models)
- Security risk: increased SQL injection surface area

### ORM Recommendation

**Keep SQLAlchemy 2.0 + Alembic.** It's the right tool for this job:
- Already integrated and working
- Handles SQLite ↔ Azure SQL seamlessly
- Alembic migrations are robust and well-tested
- Type-safe with 2.0 Mapped columns
- Large community, excellent documentation

---

## 5. CI/CD Pipeline Comparison

### GitHub Actions (Current)

| Feature | Details |
|---------|---------|
| **Free tier** | 2,000 min/month (Free), 3,000 min/month (Team) |
| **OIDC federation** | Well-documented with `azure/login` action |
| **Deployment slots** | Supported via `azure/webapps-deploy` action |
| **Approval gates** | Environment protection rules (Free for public repos, Team for private) |
| **Cost** | $0 for typical usage (builds take 3-5 min, ~10 deploys/month = ~50 min) |
| **Marketplace** | 20,000+ actions available |
| **GHCR integration** | Native — same platform for code + container registry |
| **Matrix builds** | Excellent — test across Python versions easily |

### Azure DevOps Pipelines

| Feature | Details |
|---------|---------|
| **Free tier** | 1 free parallel job, 1,800 min/month (first 5 users free) |
| **OIDC federation** | Supported via service connections (more setup overhead) |
| **Deployment slots** | First-class support with stage gates |
| **Approval gates** | Built-in environments with approval gates and checks |
| **Cost** | $0 for basic usage; $40/month per additional parallel job |
| **Marketplace** | Smaller marketplace than GitHub Actions |
| **Container registry** | Requires separate ACR ($5+/month) |
| **Azure integration** | Deeper Azure Portal integration, ARM template deployment tasks |

### Comparison for This Project

| Criterion | GitHub Actions | Azure DevOps | Winner |
|-----------|---------------|-------------|--------|
| **Already configured** | ✅ Yes | ❌ No | GitHub Actions |
| **OIDC setup complexity** | Low (well-documented) | Medium (service connections) | GitHub Actions |
| **Free minutes/month** | 2,000-3,000 | 1,800 | GitHub Actions |
| **Approval gates** | Environment protection rules | Built-in environments | Tie |
| **Container registry** | GHCR included free | ACR = $5+/month extra | GitHub Actions |
| **Azure-specific features** | azure/login, azure/webapps-deploy | Native ARM/Bicep tasks | Azure DevOps |
| **Code proximity** | Code + CI in same platform | Separate platform | GitHub Actions |
| **Ease of use** | YAML in repo, excellent docs | YAML or visual designer | GitHub Actions |

### CI/CD Recommendation

**Keep GitHub Actions.** Already configured, more free minutes, code and CI in the same platform, and the `azure/login` + `azure/webapps-deploy` actions handle Azure deployments well. Azure DevOps would only be preferred if the organization is already standardized on it.

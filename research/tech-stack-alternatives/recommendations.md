# Project-Specific Recommendations

## Priority 1: Keep Current Stack (No Action Required)

### Decision: Stay with FastAPI + HTMX + Jinja2 + Tailwind

**Confidence Level: 95%**

The current stack is well-suited for this project's requirements:

| Requirement | Current Stack Capability |
|-------------|-------------------------|
| 10-30 user dashboard | ✅ HTMX handles this trivially |
| Azure governance API integration | ✅ Python Azure SDK is most mature after .NET |
| Multi-tenant with Lighthouse | ✅ Working correctly today |
| B1 App Service (1.75GB RAM) | ✅ Python footprint ~150-300MB, comfortable |
| ~20 tables, simple CRUD | ✅ SQLAlchemy + Alembic is ideal |
| 6-10 scheduled sync jobs | ✅ APScheduler works (with improvements) |
| CI/CD to Azure | ✅ GitHub Actions with OIDC configured |
| Cost target ~$73/month | ✅ Already optimized |

**The cost of any alternative:**
- **Framework rewrite**: 3-6+ months for 1-3 developers
- **Risk**: New bugs, regression, lost domain knowledge embedded in templates
- **Opportunity cost**: Time spent rewriting is time NOT spent on features

---

## Priority 2: Targeted Improvements (Recommended)

These improvements strengthen the current stack without requiring a technology switch:

### 2.1 APScheduler Hardening (Effort: 1-2 days)

**Problem:** In-memory job state means missed syncs on App Service restart.

**Solution:** Add SQLAlchemy job store for state persistence:

```python
# app/core/scheduler.py
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

def init_scheduler() -> AsyncIOScheduler:
    jobstores = {
        'default': SQLAlchemyJobStore(url=settings.database_url)
    }
    scheduler = AsyncIOScheduler(jobstores=jobstores)
    # ... existing job definitions
```

**Additional improvements:**
- Log job execution results to `audit_log` table
- Send Teams webhook notification on job failure (already have Teams webhook service)
- Add `/api/sync/status` endpoint showing last execution times and results
- Add health check for scheduler status

### 2.2 Template Component System (Effort: 2-3 days)

**Problem:** Jinja2 templates lack the composability of React/Svelte components.

**Solution:** Enhance the existing Jinja2 macro system:
- Create `templates/components/` library with documented macros
- Add a component catalog page (like Storybook) for developer reference
- Use Jinja2 `{% call %}` blocks for more flexible component patterns

### 2.3 SQLAlchemy Query Monitoring (Effort: 1 day)

**Already partially implemented** in `database.py` with slow query logging. Enhance with:
- Query count per request middleware (detect N+1 queries)
- Dashboard page showing database performance metrics
- Alert on queries exceeding 500ms

### 2.4 HTMX Progressive Enhancement (Effort: Ongoing)

Leverage HTMX features already available but not fully utilized:
- `hx-trigger="load"` for lazy-loading dashboard panels
- `hx-indicator` for loading states on sync operations
- `hx-swap-oob` for updating multiple dashboard sections from one response
- `hx-push-url` for proper back-button behavior in SPAs

---

## Priority 3: Future Considerations (No Action Now)

### 3.1 Azure Functions for Critical Jobs (Consider if reliability issues arise)

**When to consider:**
- If App Service B1 restarts cause repeated missed sync jobs
- If you need to scale to multiple app instances (APScheduler would run duplicate jobs)
- If job execution needs Azure-native monitoring/alerting

**How to migrate gradually:**
1. Extract sync logic into shared Python package
2. Create Azure Functions project that imports shared package
3. Move one job at a time (start with least critical)
4. Remove APScheduler job after Functions job is verified
5. Estimated cost: $0 (well within free tier)

### 3.2 Move to Django (Consider only for major v2 rewrite)

**When to consider:**
- If starting a v2 from scratch
- If admin panel becomes a critical requirement
- If team grows to include Django developers

**Do not consider if:**
- Current codebase is working and maintainable
- No new team members with Django expertise
- Admin functionality can be built with existing HTMX patterns

### 3.3 Go Rewrite (Consider only if Azure SDK catches up)

**When to consider:**
- If Azure SDK for Go adds cost management, policy insights, security libraries
- If memory/performance becomes critical (scaling beyond B1 tier)
- If team has Go expertise

**Current blocker:** Azure SDK for Go lacks 3 of the 5 key management libraries used by this platform. Until those are available, Go is not viable for this specific use case.

---

## Anti-Recommendations (What NOT to Do)

### ❌ Do NOT switch to Next.js or SvelteKit
- Full rewrite cost: 3-6 months
- Requires TypeScript/JavaScript backend for Azure APIs
- Azure SDK for JS is less complete for management operations
- Adds build tooling complexity (webpack, node_modules)
- Zero performance benefit at 10-30 users

### ❌ Do NOT switch to Blazor Server
- Full rewrite cost: 4-6+ months
- Higher memory footprint (.NET runtime) on B1 tier
- SignalR connection per user adds RAM pressure
- Team lacks C#/.NET experience
- .NET advantages are marginal for this project size

### ❌ Do NOT switch to Rust
- Azure SDK is entirely beta — no stable releases
- Zero management libraries available
- Would need raw REST API calls for all Azure governance operations
- Extreme learning curve for the team
- 2.5x more code than Python for the same functionality

### ❌ Do NOT add Celery + Redis for scheduling
- Adds $13+/month infrastructure cost (18% budget increase)
- Designed for distributed task queues — overkill for 10 sequential jobs
- APScheduler with persistence is sufficient
- Adds operational complexity (worker process, beat scheduler)

### ❌ Do NOT switch to Azure DevOps Pipelines
- Already configured on GitHub Actions
- GitHub Actions has more free minutes (2,000 vs 1,800)
- Code + CI on same platform is simpler
- No meaningful feature advantage for this project

---

## Decision Matrix Summary

| Change | Effort | Risk | Benefit | ROI | Verdict |
|--------|--------|------|---------|-----|---------|
| Keep current stack | 0 | 0 | N/A | N/A | ✅ **Do this** |
| APScheduler hardening | 1-2 days | Low | Medium | **High** | ✅ **Do this** |
| Template component system | 2-3 days | Low | Medium | **Medium** | ✅ **Do this** |
| Query monitoring | 1 day | None | Medium | **High** | ✅ **Do this** |
| HTMX progressive enhancement | Ongoing | None | Medium | **High** | ✅ **Do this** |
| Azure Functions (if needed) | 1-2 weeks | Medium | Medium | Conditional | ⚠️ **Only if needed** |
| Django migration | 6-10 weeks | High | Low | **Negative** | ❌ **Don't do** |
| Next.js rewrite | 3-6 months | High | None | **Negative** | ❌ **Don't do** |
| Go rewrite | 4-6 months | Very High | None | **Negative** | ❌ **Don't do** |
| Blazor rewrite | 4-6 months | High | Low | **Negative** | ❌ **Don't do** |

---

## One-Line Summary

> **The best technology choice is the one that's already working.** Invest in targeted improvements (scheduler persistence, template organization, query monitoring) rather than framework tourism. A rewrite would cost 3-6 months of development time for zero measurable improvement at 10-30 users.

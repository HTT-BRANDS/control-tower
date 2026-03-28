# Contexte: React → HTMX Port Case Study

**Source**: htmx.org/essays/a-real-world-react-to-htmx-port/ (Tier 2 — vendor blog with primary data)
**Original Presentation**: DjangoCon 2022, David Guillot (Contexte)
**Bias Assessment**: Published on htmx.org — favorable to HTMX. However, data comes from
a real production SaaS application with concrete metrics. Cross-validated against the
DjangoCon presentation slides and video.

## Context

Contexte is a content-focused SaaS product (news/media) that replaced a 2-year React UI
with Django templates + HTMX in a couple of months.

## Key Metrics

| Metric | React | HTMX | Change |
|--------|-------|------|--------|
| Codebase (LOC) | 21,500 | 7,200 | **-67%** |
| Python code (LOC) | 500 | 1,200 | +140% (intentional) |
| JS dependencies | 255 | 9 | **-96%** |
| Build time | 40 sec | 5 sec | **-88%** |
| First load TTI | 2-6 sec | 1-2 sec | **-50-60%** |
| Memory usage | 75 MB | 45 MB | **-46%** |
| Large dataset handling | Struggled | Handled well | Significant improvement |

## Team Impact

- **Before (React)**: 2 back-end devs, 1 front-end dev, 1 "full-stack" dev
- **After (HTMX)**: All 4 developers became full-stack
- Each team member could own features end-to-end
- No more front-end/back-end coordination overhead

## Relevance to Azure Governance Platform

### Strong Parallels
- ✅ Content/data-focused application (governance data, compliance tables)
- ✅ Server-rendered with Python templates (FastAPI/Jinja2 vs Django templates)
- ✅ Data-heavy tables that React struggled with
- ✅ Small team that benefits from full-stack ownership
- ✅ Internal tool where first-load time matters less than maintainability

### Differences
- ⚠️ Contexte is a SaaS product (external users), our tool is internal (10-30 users)
- ⚠️ Contexte was migrating FROM React; we're already ON HTMX
- ⚠️ Our charting needs (Chart.js) may require more client-side interactivity

## Key Takeaway

The Contexte case study validates that HTMX is not just viable but **superior** to React
for data-heavy, server-rendered applications. Since we're already on HTMX, this is
confirmation that we're on the right track — not a reason to change.

The 67% code reduction and better large-dataset handling are particularly relevant to
our compliance tables and resource inventories with hundreds of rows.

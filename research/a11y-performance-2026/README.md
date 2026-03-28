# Accessibility at Scale & Performance/UX Patterns — March 2026

## Executive Summary

Comprehensive research for the **Azure Governance Platform** covering automated accessibility testing at CI/CD scale and modern performance/UX patterns for HTMX-based internal tools. Research conducted March 27, 2026.

### Project Context
- **Stack**: FastAPI + HTMX 1.9.12 + Jinja2 + Tailwind CSS v4.2.1 + Chart.js
- **Users**: 10–30 internal power users
- **A11y Target**: WCAG 2.2 AA compliance
- **Existing**: axe-core 4.11.1 config, Pa11y 9.1.1 config, accessibility.js client-side checks, aria-live announcer, skip-link

---

## Key Findings At a Glance

### AREA A: Accessibility at Scale

| Topic | Key Finding | Action Priority |
|-------|-------------|-----------------|
| axe-core 4.11.1 | Latest stable, excellent WCAG 2.2 coverage via tags | ✅ Already configured |
| Pa11y 9.1.1 | Confirmed v9.x (NOT 6.x), supports dual runners | ✅ Already configured |
| Manual testing gaps | 7 WCAG 2.2 criteria can't be automated | 🔴 P0 — needs checklist |
| HTMX a11y patterns | aria-live + focus management after swaps | 🟡 P1 — partial coverage |
| Playwright + axe | `axe-playwright-python` v0.1.7 for Python integration | 🟡 P1 — add to CI |

### AREA B: Performance & UX Patterns

| Topic | Key Finding | Action Priority |
|-------|-------------|-----------------|
| SSE vs Polling | `sse-starlette` 3.3.3 + HTMX SSE extension | 🟡 P1 — replace polling |
| Virtual scrolling | HTMX infinite scroll via `hx-trigger="revealed"` | 🟢 P2 — when tables grow |
| Skeleton screens | NN/G: use for full-page loads only, must show structure | 🟢 P2 — implement for dashboards |
| Optimistic UI | `hx-on::before-request` + error rollback pattern | 🟢 P2 — selective use |
| PWA | Minimal viable PWA is ~50 lines; low ROI for 10-30 users | ⚪ P3 — skip for now |
| Responsive tables | Horizontal scroll with accessible wrapper (Roselli pattern) | 🟡 P1 — implement |

---

## Detailed Findings

### See individual files:
- **[analysis.md](analysis.md)** — Multi-dimensional analysis of all 11 topics
- **[sources.md](sources.md)** — All sources with credibility assessments
- **[recommendations.md](recommendations.md)** — Project-specific recommendations with code examples
- **[raw-findings/](raw-findings/)** — Extracted content organized by topic

---

## Top 5 Actionable Recommendations

### 1. 🔴 Add `axe-playwright-python` to pytest CI pipeline
```bash
pip install axe-playwright-python pytest-playwright
```
Gives you automated WCAG 2.2 regression testing on every PR with actual browser rendering.

### 2. 🔴 Create WCAG 2.2 Manual Testing Checklist
The 7 non-automatable criteria need a quarterly manual audit cycle. Template provided in recommendations.md.

### 3. 🟡 Replace sync-dashboard polling with SSE
```bash
pip install sse-starlette
```
Replace `hx-trigger="every 5s"` with `hx-ext="sse" sse-connect="/api/v1/sync-events"`. Eliminates 12 req/min/user overhead.

### 4. 🟡 Implement accessible responsive tables (Roselli pattern)
Wrap all data tables in `<div role="region" aria-labelledby="..." tabindex="0">` with `overflow: auto`. Only 2 lines HTML + 6 lines CSS.

### 5. 🟡 Add HTMX focus management after swaps
Use `htmx:afterSwap` event to manage focus for screen reader users after partial page updates.

---

*Research conducted: March 27, 2026*
*Researcher: Web-Puppy (web-puppy-c1adca)*
*Project: Azure Governance Platform*

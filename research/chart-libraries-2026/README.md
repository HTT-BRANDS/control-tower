# Chart Libraries for Governance Dashboards — Accessibility Focus

**Research Date**: March 27, 2026
**Researcher**: web-puppy-ef2a8f
**Project**: Azure Multi-Tenant Governance Platform

## Executive Summary

The Azure Governance Platform currently uses **Chart.js 4.4.7** with manual ARIA labels and fallback text for its dashboard charts (cost trends, compliance gauges, identity stats, resource distribution, maturity radar). This research evaluates whether Chart.js remains the right choice or whether a migration would better serve accessibility requirements.

### Key Findings

| Library | Version | Bundle (min) | A11y Built-in | License | Gauge | Radar | Recommendation |
|---------|---------|-------------|---------------|---------|-------|-------|----------------|
| **Chart.js** | 4.5.1 | 196 kB | ❌ None | MIT | ❌ No | ✅ Yes | Enhance with plugins |
| **Apache ECharts** | 6.0.0 | ~1 MB | ✅ Good | Apache 2.0 | ✅ Excellent | ✅ Yes | Strong alternative |
| **Highcharts** | 12.5.0 | ~350 kB | ✅ Best-in-class | Commercial | ✅ Yes | ✅ Yes | Gold standard, but costly |
| **Observable Plot** | 0.6.17 | ~90 kB | ⚠️ Basic | ISC | ❌ No | ❌ No | Too low-level |
| **D3.js** | 7.x | ~100 kB | ⚠️ Manual | ISC | ❌ Manual | ❌ Manual | Too low-level |

### Top-Line Recommendation

**Option A (Recommended — Best Value):** Stay on Chart.js + add `chartjs-plugin-a11y-legend` + `chart2music` + implement data table fallbacks. This gives 80% of Highcharts' accessibility at zero licensing cost.

**Option B (Best Accessibility):** Migrate to Highcharts with Accessibility module. Gold standard for WCAG 2.2 compliance. Cost: $366/seat/year (SaaS license) for Highcharts Core.

**Option C (Best Free Alternative):** Migrate to Apache ECharts 6.0. Built-in ARIA, decal patterns, excellent gauge/radar. Larger bundle but tree-shakeable. Free Apache 2.0 license.

### Critical Action Items (Any Path)

1. ✅ Replace red/green color coding with accessible palette (blue/amber/red-orange)
2. ✅ Add data tables alongside every chart as WCAG fallback
3. ✅ Add `role="img"` and `aria-label` to all canvas elements (current gap)
4. ✅ Implement keyboard navigation for chart data exploration
5. ✅ Add pattern fills or textures for categorical differentiation

## File Index

| File | Description |
|------|-------------|
| `README.md` | This file — executive summary |
| `sources.md` | All sources with credibility assessments |
| `analysis.md` | Multi-dimensional analysis (security, cost, a11y, etc.) |
| `recommendations.md` | Project-specific recommendations with action items |
| `raw-findings/chartjs-accessibility.md` | Chart.js 4.x accessibility details |
| `raw-findings/echarts-accessibility.md` | ECharts 6.0 accessibility and features |
| `raw-findings/highcharts-accessibility.md` | Highcharts 12.5 accessibility module |
| `raw-findings/wcag-chart-patterns.md` | WCAG 2.2 + Chartability requirements |
| `raw-findings/chartjs-plugins.md` | Chart.js accessibility plugins |
| `raw-findings/color-accessibility.md` | Color-blind safe patterns for governance |

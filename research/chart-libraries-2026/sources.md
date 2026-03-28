# Sources — Chart Libraries Accessibility Research

## Tier 1 Sources (Official Documentation / Primary)

### Chart.js
| Source | URL | Accessed | Credibility |
|--------|-----|----------|-------------|
| Chart.js Official Accessibility Docs | https://www.chartjs.org/docs/latest/general/accessibility.html | 2026-03-27 | ✅ Tier 1 — Official docs. Last updated 10/13/2025. |
| Chart.js GitHub Releases | https://github.com/chartjs/Chart.js/releases | 2026-03-27 | ✅ Tier 1 — Latest v4.5.1, Oct 13, 2025. 67.3k stars. |
| Chart.js GitHub Issues (a11y) | https://github.com/chartjs/Chart.js/issues?q=accessibility+OR+aria | 2026-03-27 | ✅ Tier 1 — 7 open, 26 closed a11y issues. |
| Bundlephobia: chart.js@4.5.1 | https://bundlephobia.com/package/chart.js@4.5.1 | 2026-03-27 | ✅ Tier 1 — 196.1 kB min, 66.8 kB gzip. |

### Apache ECharts
| Source | URL | Accessed | Credibility |
|--------|-----|----------|-------------|
| ECharts ARIA Options Docs | https://echarts.apache.org/en/option.html#aria | 2026-03-27 | ✅ Tier 1 — Official Apache project docs. |
| ECharts GitHub Releases | https://github.com/apache/echarts/releases | 2026-03-27 | ✅ Tier 1 — v6.0.0, Jul 29, 2025. 66k stars. |
| ECharts Gauge Examples | https://echarts.apache.org/examples/en/index.html#chart-type-gauge | 2026-03-27 | ✅ Tier 1 — 8+ gauge chart variants. |
| Bundlephobia: echarts@5.6.0 | https://bundlephobia.com/package/echarts@5.6.0 | 2026-03-27 | ⚠️ Tier 2 — Shows v5.6.0 (~1 MB); v6.0 not yet indexed. |

### Highcharts
| Source | URL | Accessed | Credibility |
|--------|-----|----------|-------------|
| Highcharts Accessibility Module Docs | https://www.highcharts.com/docs/accessibility/accessibility-module | 2026-03-27 | ✅ Tier 1 — Comprehensive official docs. |
| Highcharts Sonification Docs | https://www.highcharts.com/docs/sonification/getting-started | 2026-03-27 | ✅ Tier 1 — Audio chart capabilities. |
| Highcharts Patterns & Contrast Docs | https://www.highcharts.com/docs/accessibility/patterns-and-contrast | 2026-03-27 | ✅ Tier 1 — CVD-safe palettes, pattern fills. |
| Highcharts GitHub Tags | https://github.com/highcharts/highcharts/tags | 2026-03-27 | ✅ Tier 1 — v12.5.0, Jan 12, 2026. 12.4k stars. |
| Highcharts Shop (Pricing) | https://shop.highcharts.com/ | 2026-03-27 | ✅ Tier 1 — Official pricing page. |

### Observable Plot
| Source | URL | Accessed | Credibility |
|--------|-----|----------|-------------|
| Observable Plot Getting Started | https://observablehq.com/plot/getting-started | 2026-03-27 | ✅ Tier 1 — v0.6.17, 5.2k stars. |
| Observable Plot Accessibility Docs | https://observablehq.com/plot/features/accessibility | 2026-03-27 | ✅ Tier 1 — ARIA features documented. |

### WCAG / W3C
| Source | URL | Accessed | Credibility |
|--------|-----|----------|-------------|
| W3C WAI Complex Images Tutorial | https://www.w3.org/WAI/tutorials/images/complex/ | 2026-03-27 | ✅ Tier 1 — W3C authoritative guidance. |

## Tier 2 Sources (Established Projects / Expert Community)

| Source | URL | Accessed | Credibility |
|--------|-----|----------|-------------|
| Chartability Workbook (POUR-CAF) | https://chartability.github.io/POUR-CAF/ | 2026-03-27 | ✅ Tier 2 — Community-developed audit framework, 50 heuristics, peer-reviewed. Created by Frank Elavsky (Apple/CMU). |
| chartjs-plugin-a11y-legend | https://github.com/julianna-langston/chartjs-plugin-a11y-legend | 2026-03-27 | ✅ Tier 2 — Active plugin by Julianna Langston (Microsoft a11y). |
| chart2music | https://github.com/julianna-langston/chart2music | 2026-03-27 | ✅ Tier 2 — Sonification library, MIT, same author. |
| Chart.js Awesome List | https://github.com/chartjs/awesome | 2026-03-27 | ✅ Tier 2 — Official curated plugin list. |

## Cross-Reference Validation

| Claim | Sources Confirming |
|-------|-------------------|
| Chart.js has no built-in a11y | Official docs, GitHub issues, awesome list (plugins exist because core lacks it) |
| ECharts has aria.enabled option | Official docs (aria section), confirmed in API reference |
| Highcharts is gold standard for chart a11y | Official docs, CSUN 2026 presentation, Chartability references Highcharts |
| WCAG requires data tables for complex charts | W3C WAI tutorial, Chartability ("No table" = critical failure), US Gov Design System |
| Chart.js 4.5.1 is latest | GitHub releases page (Oct 13, 2025) |
| ECharts 6.0.0 is latest | GitHub releases page (Jul 29, 2025) |
| Highcharts 12.5.0 is latest | GitHub tags page (Jan 12, 2026) |

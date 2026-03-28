# Multi-Dimensional Analysis — Chart Libraries for Governance Dashboards

## 1. Accessibility (Primary Concern)

### Chart.js 4.5.1
- **Canvas-based rendering** — inherently inaccessible to screen readers
- **No built-in ARIA generation** — official docs state: "it is up to the user to create the canvas element in a way that is accessible"
- **No keyboard navigation** for chart data points
- **No screen reader** content for individual data points
- Manual work required: `role="img"`, `aria-label`, fallback `<p>` inside `<canvas>`
- 7 open accessibility issues, 26 closed (many closed as "won't fix" or "implement externally")
- Key open issues: #11767 "Tooltip content is not hoverable", #11768 "Dynamic text resize not supported", #10372 "High contrast mode"
- **Plugins available** to partially fill gaps (see below)
- **Score: 2/10** (without plugins) → **5/10** (with a11y-legend + chart2music)

### Apache ECharts 6.0.0
- **Built-in ARIA support** via `aria.enabled: true`
- **Auto-generated descriptions**: `aria.label` creates intelligent descriptions from chart data, title, and series
- **Decal pattern fills** via `aria.decal` for color-blind differentiation
- Supports both **Canvas and SVG** rendering (SVG more accessible)
- No built-in keyboard navigation for data point exploration
- No built-in sonification
- **Score: 6/10**

### Highcharts 12.5.0
- **WCAG 2.2 as their design guideline** — accessibility is a first-class concern
- **Accessibility module** provides:
  - Full keyboard navigation for all chart elements
  - Screen reader support with ARIA roles and attributes
  - Auto-generated text descriptions from chart configuration
  - Linked descriptions via `highcharts-description` CSS class
  - Sonification module (audio charts) with synthesizer, speech, MIDI export
  - Pattern fill module for color-blind users
  - Dash styles for line differentiation
  - High contrast theme
  - Low vision features, voice input, tactile export
- **SVG-based rendering** — natively accessible
- **Presenting at CSUN 2026** (premier accessibility conference)
- **Score: 9/10**

### Observable Plot 0.6.17
- **SVG-based** — inherently more accessible than canvas
- **Basic ARIA support**: `ariaLabel`, `ariaDescription` on marks and root SVG
- `ariaHidden` for decorative marks
- No built-in keyboard navigation
- No gauge or radar chart types
- **Score: 4/10**

### D3.js 7.x
- SVG-based — accessible foundation
- No built-in accessibility features — everything is manual
- Maximum control means maximum responsibility
- **Score: 2/10** (but unlimited ceiling with custom work)

---

## 2. Chart Type Coverage (for Governance Dashboard)

| Chart Type | Use Case | Chart.js | ECharts | Highcharts | Obs. Plot |
|-----------|----------|----------|---------|------------|-----------|
| **Line/Area** | Cost trends | ✅ Good | ✅ Excellent | ✅ Excellent | ✅ Good |
| **Bar** | Identity stats | ✅ Good | ✅ Good | ✅ Good | ✅ Good |
| **Donut** | Resource dist. | ✅ Good | ✅ Good | ✅ Good | ⚠️ Workaround |
| **Gauge/Radial** | Compliance | ❌ No native | ✅ **8+ types** | ✅ Solid gauge | ❌ No |
| **Radar** | Maturity scores | ✅ Basic | ✅ Good | ✅ Good (polar) | ❌ No |
| **Time Series** | Cost history | ✅ Good | ✅ Excellent | ✅ **Best** (Stock) | ✅ Good |

**Winner for gauge charts**: ECharts (Grade Gauge is perfect for compliance scoring)
**Winner for time series**: Highcharts Stock
**Winner for radar**: ECharts and Highcharts tied

---

## 3. Cost Analysis

### Chart.js (Current)
- License: **MIT — Free** ✅
- Plugin costs: Free (MIT)
- Migration cost: $0 (already in use)
- Enhancement cost: ~8-16 hours developer time for a11y plugins + data tables
- **Total Year 1: ~$0 + dev time**

### Apache ECharts
- License: **Apache 2.0 — Free** ✅
- Migration cost: ~40-60 hours to rewrite 2 chart components + new gauge/radar
- Bundle size increase: +800 kB (significant for HTMX app)
- **Total Year 1: ~$0 + migration dev time**

### Highcharts
- License: **Commercial — $366/seat/year** (SaaS Annual for Highcharts Core)
  - With Stock: $732/seat/year
  - With Maps + Gantt: $933/seat/year (full suite)
  - Perpetual SaaS: $839/seat (one-time) + annual Advantage renewal
- For 2 developers: **$732-1,864/year**
- Migration cost: ~30-50 hours (excellent docs, easier API)
- **Total Year 1: ~$732-1,864 + migration dev time**

### Observable Plot
- License: **ISC — Free** ✅
- Not viable — lacks gauge and radar charts entirely

---

## 4. Implementation Complexity (for HTMX + Jinja2 Stack)

### Chart.js (Current — Lowest)
- Already integrated via `<script>` tag and canvas data-* attributes
- No build step required
- Jinja2 template → data-* attributes → JS initialization
- HTMX re-initialization via `htmx:afterSettle` event (already implemented)
- **Complexity: 1/10** (already done)

### Apache ECharts
- Can load via CDN `<script>` tag — no build step
- Initialization: `echarts.init(dom)` + `setOption(config)`
- Configuration is JSON-based — works well with Jinja2 server rendering
- HTMX re-initialization: Need `echarts.dispose()` before re-init on `htmx:afterSettle`
- Larger bundle may need lazy loading strategy
- Tree-shakeable if using a build step (which this project does NOT have)
- **Complexity: 4/10**

### Highcharts
- Can load via CDN `<script>` tag — no build step
- Multiple modules: `highcharts.js` + `accessibility.js` + `sonification.js` + `pattern-fill.js`
- Configuration is JSON-based — excellent for Jinja2 rendering
- HTMX: `Highcharts.chart(container, options)` — straightforward re-init
- Very well documented with extensive examples
- **Complexity: 3/10**

### Observable Plot
- Can load via CDN
- Returns SVG DOM element: `Plot.plot({...})` — append to container
- Good for Jinja2 workflow
- But lacks required chart types
- **Complexity: 3/10** (but insufficient features)

---

## 5. Bundle Size & Performance

| Library | Minified | Gzipped | Tree-Shakeable | Dependencies |
|---------|----------|---------|----------------|--------------|
| Chart.js 4.5.1 | 196.1 kB | 66.8 kB | ✅ Yes | 1 |
| ECharts 5.6.0* | ~1 MB | ~300 kB | ✅ Yes | 2 |
| Highcharts 12.5.0 | ~350 kB† | ~100 kB† | ❌ No | 0 |
| Observable Plot 0.6.17 | ~90 kB | ~30 kB | ✅ Yes | D3 deps |

*ECharts 6.0 not yet on bundlephobia; v5.6.0 measured. v6 likely similar.
†Highcharts estimate; bundlephobia failed to analyze. Core only, accessibility module adds ~50 kB.

**Impact for HTMX app** (no build step, CDN-loaded):
- Chart.js: Already loads fast. Adding plugins adds ~20 kB.
- ECharts: ~1 MB is heavy. Would need lazy loading or the "echarts.min.js" custom build.
- Highcharts: ~350 kB is moderate. Multiple script tags for modules.
- For a server-rendered HTMX app, bundle size matters more since there's no tree-shaking.

---

## 6. Stability & Maintenance

| Library | First Release | Latest | Release Cadence | Breaking Changes | LTS |
|---------|--------------|--------|-----------------|------------------|-----|
| Chart.js | 2013 | 4.5.1 (Oct 2025) | ~Quarterly patches | v3→v4 was major | Community |
| ECharts | 2013 | 6.0.0 (Jul 2025) | ~Annual majors | v5→v6 was major | Apache Foundation |
| Highcharts | 2009 | 12.5.0 (Jan 2026) | ~Monthly | Stable API | Commercial support |
| Observable Plot | 2021 | 0.6.17 | Active | Pre-1.0, API may change | Observable team |

**Risk Assessment:**
- **Chart.js**: Stable, mature, large community. Low risk.
- **ECharts**: Apache Foundation backing. v6.0 just released — potential early bugs. Medium risk.
- **Highcharts**: Most stable, commercial support, 17 years. Lowest risk.
- **Observable Plot**: Pre-1.0. Highest risk for breaking changes.

---

## 7. Security Considerations

| Library | XSS Risk | Supply Chain | CVEs | Content Security Policy |
|---------|----------|-------------|------|------------------------|
| Chart.js | Low (canvas) | 1 dep (low risk) | None known | Canvas doesn't execute HTML |
| ECharts | Low | 2 deps (zrender, tslib) | None recent | SVG mode needs CSP review |
| Highcharts | Low (SVG) | 0 deps ✅ | None recent | SVG inline needs CSP tuning |
| Observable Plot | Low (SVG) | D3 ecosystem deps | None known | SVG output |

All libraries are low-risk. Highcharts with zero dependencies is the most secure from supply-chain perspective.

---

## 8. Compatibility with Project Stack

**Stack: FastAPI + Jinja2 + HTMX + Tailwind CSS (no build step, no React/Vue)**

| Criterion | Chart.js | ECharts | Highcharts | Observable Plot |
|-----------|----------|---------|------------|-----------------|
| No build step required | ✅ | ✅ | ✅ | ✅ |
| CDN loading | ✅ | ✅ | ✅ | ✅ |
| Works with HTMX swaps | ✅ (tested) | ⚠️ Need dispose | ✅ | ✅ |
| JSON config from Jinja2 | ✅ | ✅ | ✅ | ⚠️ JS API |
| No framework dependency | ✅ | ✅ | ✅ | ✅ |
| Dark mode support | ⚠️ Manual | ✅ Built-in | ✅ Themes | ⚠️ CSS |

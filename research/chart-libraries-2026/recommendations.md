# Recommendations — Chart Library Accessibility for Azure Governance Platform

## Decision Framework

Given the project's constraints:
- **HTMX + Jinja2 stack** (no React/Vue, no build step)
- **Already using Chart.js 4.4.7** (migration has real cost)
- **WCAG 2.2 AA compliance required** (governance/enterprise context)
- **Chart types needed**: line/area, bar, donut, gauge, radar
- **Budget**: Cost-sensitive (chose SQLite over Cosmos DB, B2 over B3)

---

## Recommended Path: Enhanced Chart.js + Data Tables + Accessible Patterns

### Why Not Migrate?

1. **Chart.js is already working** — 2 chart components, tested, integrated with HTMX
2. **No gauge chart in any path** — Chart.js lacks native gauge, but neither does the current code use one (compliance uses bar chart)
3. **Migration risk** — rewriting chart code introduces bugs, testing burden
4. **Cost** — Highcharts licensing adds recurring expense; ECharts adds 5x bundle weight
5. **The 80/20 rule** — plugins + data tables get 80% of Highcharts' accessibility at 0 cost

### When TO Migrate

Revisit this decision if:
- You add gauge charts for compliance scores (ECharts is the clear winner here)
- You get explicit WCAG 2.2 audit findings against canvas-based charts
- You need sonification as a feature (Highcharts is the only integrated option)
- You scale to 10+ chart types (Highcharts/ECharts have better ecosystems)

---

## Implementation Plan (Priority Order)

### Phase 1: Critical Fixes (Week 1) — WCAG Compliance Gaps

#### 1.1 Add `role="img"` and `aria-label` to all canvas elements

**Current code** (`app/static/js/charts/dashboard.js`):
```javascript
new Chart(el.getContext('2d'), { type: 'line', ... });
```

**Required**: Every `<canvas>` element needs ARIA attributes:
```html
<canvas id="costTrendChart"
        role="img"
        aria-label="Line chart showing daily cost trends over the past 30 days. Current daily cost is $X."
        data-labels='{{ labels | tojson }}'
        data-values='{{ values | tojson }}'>
  <p>Cost trend data: {% for label, value in zip(labels, values) %}{{ label }}: ${{ value }}{% endfor %}</p>
</canvas>
```

The fallback `<p>` inside `<canvas>` provides content when canvas is unsupported or for assistive tech that reads it.

#### 1.2 Add data tables alongside every chart

This is a **critical Chartability heuristic** and WCAG best practice.

```html
<figure role="group" aria-label="Cost trend chart and data">
  <canvas id="costTrendChart" role="img" aria-label="..."></canvas>
  <details>
    <summary>View data table</summary>
    <table>
      <caption>Daily costs — Last 30 days</caption>
      <thead><tr><th>Date</th><th>Cost ($)</th></tr></thead>
      <tbody>
        {% for label, value in zip(labels, values) %}
        <tr><td>{{ label }}</td><td>${{ value }}</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </details>
</figure>
```

Using `<details>/<summary>` keeps tables collapsed by default, avoiding visual clutter while maintaining accessibility.

#### 1.3 Replace red/green color scheme

**Current problematic colors in `dashboard.js`**:
```javascript
const colorSuccess = '#10B981'; // Green — problematic for deuteranopia
const colorError = '#EF4444';   // Red — problematic for protanopia
const colorWarning = '#F59E0B'; // Amber — okay
```

**Accessible replacements**:
```javascript
// Accessible governance palette (WCAG 2.2 AA compliant)
const colorSuccess = '#0369A1'; // Blue (sky-700) — universally distinguishable
const colorWarning = '#D97706'; // Amber (amber-600) — good contrast
const colorError   = '#C2410C'; // Red-orange (orange-700) — distinct from blue
const colorInfo    = '#6D28D9'; // Violet (violet-700) — additional category

// Alternative: Keep semantic meaning with icons + patterns
// ✅ Pass: Blue + checkmark icon + solid fill
// ⚠️ Warning: Amber + warning icon + diagonal stripe pattern
// ❌ Fail: Red-orange + X icon + crosshatch pattern
```

**Key principle**: Never use color alone. Always pair with:
- Icons (✅ ⚠️ ❌)
- Pattern fills (solid, stripes, crosshatch)
- Text labels ("Pass", "Warning", "Fail")

### Phase 2: Plugin Integration (Week 2) — Keyboard & Screen Reader

#### 2.1 Install chartjs-plugin-a11y-legend

```html
<!-- Add to base.html after chart.js -->
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-a11y-legend"></script>
```

```javascript
// In dashboard.js — register globally
Chart.register(ChartjsPluginA11yLegend);
```

This provides:
- Tab to legend items
- Arrow key navigation between legend items
- Spacebar/Enter to toggle series visibility
- ARIA labels for legend state (selected/deselected)

#### 2.2 Install chart2music for sonification

```html
<script src="https://cdn.jsdelivr.net/npm/chart2music"></script>
```

```javascript
// After chart creation, add sonification layer
const chart = new Chart(el.getContext('2d'), config);

c2mChart({
  type: "line",
  element: el,
  cc: document.getElementById('costTrendScreenReader'),
  data: data.map((value, i) => ({ x: i, y: value })),
  options: {
    axes: {
      x: { label: "Date", format: (v) => labels[v] || v },
      y: { label: "Cost ($)", format: (v) => `$${v.toLocaleString()}` }
    }
  }
});
```

This provides:
- Keyboard navigation through data points (arrow keys)
- Audio feedback (pitch maps to value — higher pitch = higher value)
- Auto-generated screen reader descriptions
- Works alongside the visual Chart.js chart

#### 2.3 Add screen reader text container

```html
<div id="costTrendScreenReader" class="sr-only" aria-live="polite"></div>
```

### Phase 3: Enhanced Patterns (Week 3-4) — Pattern Fills & High Contrast

#### 3.1 Implement pattern fills for bar/donut charts

Use the `chartjs-plugin-style` or custom canvas patterns:

```javascript
// Create pattern fills for compliance chart
function createPattern(color, type) {
  const canvas = document.createElement('canvas');
  canvas.width = 10;
  canvas.height = 10;
  const ctx = canvas.getContext('2d');

  ctx.fillStyle = color;
  ctx.fillRect(0, 0, 10, 10);

  ctx.strokeStyle = 'rgba(255,255,255,0.5)';
  ctx.lineWidth = 2;

  switch(type) {
    case 'diagonal':
      ctx.beginPath();
      ctx.moveTo(0, 10);
      ctx.lineTo(10, 0);
      ctx.stroke();
      break;
    case 'crosshatch':
      ctx.beginPath();
      ctx.moveTo(0, 5);
      ctx.lineTo(10, 5);
      ctx.moveTo(5, 0);
      ctx.lineTo(5, 10);
      ctx.stroke();
      break;
    case 'dots':
      ctx.beginPath();
      ctx.arc(5, 5, 2, 0, Math.PI * 2);
      ctx.fill();
      break;
  }
  return ctx.createPattern(canvas, 'repeat');
}
```

#### 3.2 Support `prefers-contrast: more`

```css
@media (prefers-contrast: more) {
  :root {
    --chart-border-width: 3px;
    --chart-font-weight: bold;
  }
}
```

#### 3.3 Support `forced-colors` (Windows High Contrast)

Already partially in `accessibility.css`. Extend for chart containers:

```css
@media (forced-colors: active) {
  canvas {
    border: 2px solid currentColor;
  }
  .chart-legend-item {
    border: 1px solid currentColor;
    forced-color-adjust: none;
  }
}
```

---

## Future Consideration: ECharts Migration for Gauge Charts

If governance maturity scoring or compliance gauges become a priority, consider a **partial migration**:

```
Chart.js (keep) → cost trends (line), identity stats (bar)
ECharts (add)  → compliance gauges, maturity radar
```

ECharts can coexist with Chart.js on the same page. This hybrid approach:
- Keeps existing charts working
- Adds best-in-class gauge support
- Gets built-in ARIA for gauge/radar charts
- Avoids full migration risk

```html
<!-- Compliance gauge with ECharts -->
<div id="complianceGauge" style="width: 300px; height: 300px;"
     role="img" aria-label="Compliance score: 87%"></div>

<script>
const gauge = echarts.init(document.getElementById('complianceGauge'));
gauge.setOption({
  aria: { enabled: true },
  series: [{
    type: 'gauge',
    data: [{ value: 87, name: 'Compliance' }],
    detail: { formatter: '{value}%' },
    axisLine: {
      lineStyle: {
        width: 30,
        color: [
          [0.7, '#C2410C'],   // 0-70%: Fail (red-orange)
          [0.9, '#D97706'],   // 70-90%: Warning (amber)
          [1, '#0369A1']      // 90-100%: Pass (blue)
        ]
      }
    }
  }]
});
</script>
```

---

## Cost Summary

| Approach | License | Dev Time | Annual Cost |
|----------|---------|----------|-------------|
| **Enhanced Chart.js (recommended)** | $0 | ~40-60 hrs | $0 |
| Chart.js + ECharts hybrid | $0 | ~60-80 hrs | $0 |
| Full ECharts migration | $0 | ~80-120 hrs | $0 |
| Full Highcharts migration | $366-732/yr | ~60-80 hrs | $366-732 |

---

## Validation Checklist

After implementation, validate against Chartability's 14 critical heuristics:

- [ ] Low contrast: All chart elements ≥ 3:1 contrast ratio
- [ ] Content only visual: All chart info available without visuals (data tables)
- [ ] Small text: All chart text ≥ 12px
- [ ] Seizure risk: No rapid flashing
- [ ] Keyboard navigation: Charts navigable via keyboard (chart2music)
- [ ] Interaction cues: Instructions for keyboard usage provided
- [ ] AT controls not overridden: Custom keys only when chart focused
- [ ] No title/summary: Every chart has descriptive title + aria-label
- [ ] Reading level: Alt text at grade 9 or lower
- [ ] Purpose explained: Chart purpose and how-to-read explained
- [ ] Data table provided: Every chart has collapsible data table
- [ ] Data density appropriate: No more than 5 categories per chart
- [ ] Navigation not tedious: Can skip chart with single tab
- [ ] User styles respected: Charts respond to zoom, contrast, font size changes

---

## Files to Modify

| File | Change |
|------|--------|
| `app/static/js/charts/dashboard.js` | Add a11y plugin registration, update colors, add chart2music |
| `app/templates/partials/` | Add data tables, aria-labels to canvas elements, sr-only containers |
| `app/static/css/accessibility.css` | Add forced-colors and prefers-contrast rules for charts |
| `app/templates/base.html` | Add CDN script tags for a11y-legend and chart2music |
| `app/static/css/theme.src.css` | Update CSS custom properties for accessible color palette |

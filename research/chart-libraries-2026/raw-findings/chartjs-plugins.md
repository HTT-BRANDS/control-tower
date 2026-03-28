# Chart.js Accessibility Plugins

Source: https://github.com/chartjs/awesome (official curated list)

## 1. chartjs-plugin-a11y-legend

**Repository**: https://github.com/julianna-langston/chartjs-plugin-a11y-legend
**Author**: Julianna Langston (Microsoft accessibility team)
**Compatibility**: Chart.js v4 ✅
**License**: MIT

### What It Does
Provides keyboard accessibility for chart legends:
- **Tab** to navigate to the legend
- **Left/Right arrow keys** to navigate between legend items
- **Spacebar/Enter** to toggle (click) legend items
- **ARIA attributes** for label, position, and selection state

### Supported Chart Types
- ✅ bar
- ✅ line
- ✅ pie
- ✅ doughnut
- ✅ radar

### Installation
```html
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-a11y-legend"></script>
```

Or via npm:
```javascript
import plugin from "chartjs-plugin-a11y-legend";
Chart.register(plugin);
```

### Options
```javascript
options: {
  plugins: {
    a11y_legend: {
      margin: 4  // bounding box margin in pixels
    }
  }
}
```

### Screen Reader Testing
Tested with: **Windows + Chrome + NVDA**

### UX Design Basis
Modeled after W3C WAI-ARIA authoring practices for tabs and toolbars.

---

## 2. chart2music (c2m)

**Repository**: https://github.com/julianna-langston/chart2music
**Website**: https://chart2music.com
**Author**: Julianna Langston (same author as a11y-legend)
**Compatibility**: Chart.js v3 & v4 ✅ (also works with D3, Highcharts, etc.)
**License**: MIT

### What It Does
Turns charts into music so blind users can hear data:
- **Keyboard navigation** through data points (arrow keys)
- **Sonification** — pitch maps to data values (higher pitch = higher value)
- **Auto-generated screen reader descriptions** — no alt text maintenance
- **Visual agnostic** — works alongside any chart library or even images

### Key Design Principles
- **Inclusively designed** — blind people involved in design, development, and testing
- **Easier maintenance** — automated solution vs manual alt text
- **Visual agnostic** — works with Chart.js, D3, Highcharts, images, anything

### Installation
```html
<script src="https://cdn.jsdelivr.net/npm/chart2music"></script>
```

### Usage with Chart.js
```javascript
// Create Chart.js chart as normal
const chart = new Chart(canvas, config);

// Add chart2music alongside
const { err } = c2mChart({
  type: "line",
  element: canvas,
  cc: document.getElementById("screenReaderContainer"),
  data: chartData.map((value, i) => ({ x: i, y: value })),
  options: {
    axes: {
      x: { label: "Date", format: (v) => labels[v] },
      y: { label: "Cost ($)", format: (v) => `$${v.toLocaleString()}` }
    }
  }
});
```

### Supported Chart Types
- bar
- line
- scatter
- candlestick
- bar-line (combo)
- multi-line

### User Experience
1. User navigates to chart (via tab or screen reader)
2. Auto-generated description announces chart type and data summary
3. User presses arrow keys to move through data points
4. Each data point plays a tone (pitch = value) + screen reader announces value
5. Keyboard shortcuts for jumping (beginning, end, min, max)

### Integration Examples Available For
Chart.js, D3.js, ChartIQ, HighCharts, Recharts, Google Charts, AnyChart, Chartist.js, NVD3.js, Plotly.js, AM Charts, Vega-Lite, Morris.js, Frappe

---

## Combined Plugin Strategy for This Project

### Recommended Setup
```html
<!-- Chart.js core (already loaded) -->
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.5.1"></script>

<!-- Accessibility plugins -->
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-a11y-legend"></script>
<script src="https://cdn.jsdelivr.net/npm/chart2music"></script>
```

```javascript
// Register a11y-legend globally
Chart.register(ChartjsPluginA11yLegend);

// For each chart, also create a c2m instance
function createAccessibleChart(canvasId, config, c2mType) {
  const canvas = document.getElementById(canvasId);
  const chart = new Chart(canvas.getContext('2d'), config);

  // Add sonification + keyboard nav
  c2mChart({
    type: c2mType,
    element: canvas,
    cc: document.getElementById(`${canvasId}-sr`),
    data: extractC2MData(config)
  });

  return chart;
}
```

### What This Combination Provides
- ✅ Keyboard navigation for legends (a11y-legend)
- ✅ Keyboard navigation for data points (chart2music)
- ✅ Sonification / audio representation (chart2music)
- ✅ Auto-generated screen reader descriptions (chart2music)
- ✅ ARIA attributes for legend state (a11y-legend)

### What's Still Missing (requires custom implementation)
- ❌ Data table fallbacks (implement in Jinja2 templates)
- ❌ Pattern fills (implement with canvas patterns)
- ❌ Color-blind safe palette (update CSS custom properties)
- ❌ High contrast mode response (add CSS media queries)
- ❌ `role="img"` and `aria-label` on canvas (update templates)
- ❌ Focus indicator styling (add CSS)

### Estimated Bundle Impact
- a11y-legend: ~5 kB minified
- chart2music: ~15 kB minified
- **Total addition: ~20 kB** (vs 196 kB for Chart.js core — minimal)

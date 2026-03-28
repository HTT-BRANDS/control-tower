# Apache ECharts — Accessibility & Features

## Version Info
- **Latest**: 6.0.0 (Jul 29, 2025) — Major release
- **Bundle**: ~1 MB minified (v5.6.0 measured, v6 likely similar)
- **GitHub**: 66k stars, 1.6k issues, 138 PRs
- **License**: Apache 2.0 (free for commercial use)
- **Rendering**: Canvas (default) or SVG

## Built-in ARIA Support

Source: https://echarts.apache.org/en/option.html#aria

### aria.enabled (boolean)
Turns on ARIA support. When enabled, both `label` and `decal` features activate.

### aria.label (Object)
When `aria.enabled = true`, label is enabled by default:
- **Auto-generates chart descriptions** from chart configuration data
- Creates intelligent text based on title, data, series info
- Users can customize the generated description via configuration
- Screen readers can read the auto-generated description

### aria.decal (Pattern Fills)
Added in ECharts 5, decal provides:
- **Applique textures** as auxiliary differentiation alongside color
- Built-in pattern types for different series
- Helps color-blind users distinguish data categories
- Can be toggled independently

### Configuration Example
```javascript
const chart = echarts.init(container);
chart.setOption({
  aria: {
    enabled: true,
    label: {
      description: 'Compliance scores across frameworks for Q1 2026'
    },
    decal: {
      show: true  // Enable pattern fills
    }
  },
  // ... chart configuration
});
```

## ECharts 6.0.0 New Features (Jul 2025)
- New theme system for ECharts 6.0
- New chord series type
- Matrix & calendar coordinate system
- Reusable custom series
- Improved Cartesian layout (prevents axis label overflow)
- Scatter jittering support
- Axis break support
- Dynamic theme registration and switching

## Gauge Chart Capabilities

ECharts has the **best gauge chart ecosystem** of any library:

### Gauge Types Available
1. **Gauge Basic** — Standard radial gauge
2. **Simple Gauge** — Minimal gauge with score display
3. **Speed Gauge** — Speedometer-style with red zone
4. **Progress Gauge** — Circular progress indicator
5. **Stage Speed Gauge** — Multi-stage colored zones
6. **Grade Gauge** — Letter grade display (A-F) — **ideal for compliance**
7. **Multi Title Gauge** — Multiple labels (Good/Better/Perfect)
8. **Temperature Gauge** — Thermometer-style radial

### Compliance Gauge Example
```javascript
{
  type: 'gauge',
  startAngle: 180,
  endAngle: 0,
  data: [{ value: 87, name: 'SOC 2 Compliance' }],
  detail: { formatter: '{value}%', fontSize: 24 },
  axisLine: {
    lineStyle: {
      width: 30,
      color: [
        [0.7, '#C2410C'],   // 0-70%: Non-compliant
        [0.9, '#D97706'],   // 70-90%: Partial
        [1.0, '#0369A1']    // 90-100%: Compliant
      ]
    }
  }
}
```

## Radar Chart Capabilities
- Standard radar/spider charts
- Customizable indicator axes
- Multiple series overlay
- Area fill support
- Good for maturity model scoring

## Accessibility Gaps
- ❌ No built-in keyboard navigation for data points
- ❌ No sonification support
- ❌ No linked description pattern (like Highcharts)
- ❌ No built-in data table generation
- ⚠️ Decal patterns are basic — limited customization
- ⚠️ ARIA auto-descriptions may not be detailed enough for complex charts

## HTMX Integration Notes
```javascript
// Initialize
const chart = echarts.init(document.getElementById('container'));
chart.setOption(config);

// MUST dispose before re-init on HTMX swap
document.addEventListener('htmx:beforeSwap', () => {
  chart.dispose();
});

// Re-init after swap
document.addEventListener('htmx:afterSettle', () => {
  const newChart = echarts.init(document.getElementById('container'));
  newChart.setOption(config);
});
```

## Bundle Size Concern
At ~1 MB minified, ECharts is **5x larger** than Chart.js. For an HTMX app without build-step tree-shaking:
- Can use custom build to include only needed chart types
- ECharts provides a build tool: https://echarts.apache.org/en/builder.html
- Minimum build (line + bar + gauge + radar) would be ~400-500 kB
- Still 2-3x larger than Chart.js

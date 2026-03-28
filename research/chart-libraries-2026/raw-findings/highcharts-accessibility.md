# Highcharts 12.5.0 — Accessibility Module

## Version Info
- **Latest**: v12.5.0 (Jan 12, 2026)
- **Bundle**: ~350 kB core minified (estimate; bundlephobia failed to analyze)
- **GitHub**: 12.4k stars, 529 issues, 130 PRs
- **License**: Commercial (see pricing below)
- **Rendering**: SVG (primary) — natively more accessible than canvas
- **Dependencies**: 0 (zero external dependencies)

## Accessibility Module — Feature Breakdown

Source: https://www.highcharts.com/docs/accessibility/accessibility-module

### Installation
```html
<script src="https://code.highcharts.com/modules/exporting.js"></script>
<script src="https://code.highcharts.com/modules/export-data.js"></script>
<script src="https://code.highcharts.com/modules/accessibility.js"></script>
```

If the accessibility module is NOT included, a warning appears in the browser console.

### What It Provides

#### 1. Keyboard Navigation
- Full keyboard navigation through all chart elements
- Tab to chart, arrow keys through data points
- Enter/Space to select/interact
- Escape to exit chart focus

#### 2. Screen Reader Support
- ARIA roles and attributes on all chart elements
- Auto-generated descriptions from chart configuration
- Supports JAWS, NVDA (Windows), VoiceOver (Mac/iOS)

#### 3. Auto-Generated Descriptions
Just by providing meaningful titles and series names, charts become accessible:
```javascript
Highcharts.chart('container', {
  title: { text: 'Corn vs wheat estimated production for 2020' },
  xAxis: { categories: ['USA', 'China', 'Brazil'], title: { text: 'Countries' } },
  yAxis: { title: { text: '1000 metric tons (MT)' } },
  series: [
    { name: 'Corn', data: [406292, 260000, 107000] },
    { name: 'Wheat', data: [51086, 136000, 5500] }
  ]
});
```

#### 4. Linked Descriptions
```html
<figure>
  <div id="chart-container"></div>
  <p class="highcharts-description">
    Chart showing compliance trends across SOC 2, NIST, and CIS frameworks.
  </p>
</figure>
```
Highcharts auto-links elements with `highcharts-description` class to the chart.

#### 5. Caption Option
```javascript
Highcharts.chart('container', {
  caption: {
    text: 'Compliance scores improved 12% in Q1 2026 across all frameworks.'
  }
});
```

#### 6. Hidden Description (for screen readers only)
```javascript
Highcharts.chart('container', {
  accessibility: {
    description: 'Line chart showing daily cost trends, declining from $5,200 to $4,800 over 30 days.'
  }
});
```

### Additional Accessible Features
- **Low vision features** — zoom, reflow support
- **Voice input** compatibility
- **Tactile export** — export to formats for tactile printers
- **Cognitive accessibility** — reading level guidelines
- **Internationalization** — a11y labels in multiple languages

## Sonification Module (Audio Charts)

Source: https://www.highcharts.com/docs/sonification/getting-started

### Features
- Built-in lightweight synthesizer
- Multiple instrument presets (piano, flute, trumpet, etc.)
- Speech synthesis support
- Sequential or simultaneous playback
- Multi-track audio (layer sounds for multiple series)
- Musical scale mapping
- Context tracks (background rhythm/cues)
- MIDI export
- Timeline navigation with scrubbing
- Play marker (tooltip follows audio playback)

### Usage
```javascript
// Simple: just add sonification module and a button
const chart = Highcharts.chart('container', {
  sonification: { duration: 3000 },
  series: [{ data: [4, 5, 6, 5, 7, 9, 11, 13] }]
});

document.getElementById('play').onclick = () => chart.toggleSonify();
```

## Pattern Fill & Contrast

Source: https://www.highcharts.com/docs/accessibility/patterns-and-contrast

### Default Palette
- Designed with accessibility in mind
- Any two neighboring colors tested for all types of color blindness

### Contrast Enhancement Options
1. **Monochrome palettes** — single-hue gradients
2. **High contrast theme** — built-in theme option
3. **Dash styles** for lines — distinguishable on B&W prints
4. **Pattern fill module** — textures for areas, columns, plot bands

```html
<script src="https://code.highcharts.com/modules/pattern-fill.js"></script>
```

### Warning from Docs
> "Keep in mind that pattern fills and dash styles could make your charts visually confusing and less accessible to some users. Subtle patterns are often preferred."

## Pricing (March 2026)

Source: https://shop.highcharts.com/

### For Azure Governance Platform (SaaS Application)

| Product | Annual (per seat) | Perpetual (per seat) |
|---------|------------------|---------------------|
| **Highcharts Core only** | **$366** | **$839** |
| Highcharts + Stock | $732 | $1,678 |
| Highcharts + Maps | $494 | $1,133 |
| Highcharts + Gantt | $439 | $1,007 |
| Highcharts + Stock + Maps + Gantt | $933 | $2,140 |

### License Types
- **Internal License** ($185/seat/year) — private/intranet only, NOT for public web apps
- **SaaS License** ($366/seat/year) — 1 SaaS/web application, includes public access
- **OEM License** — for embedding in redistributed products

### For This Project
- SaaS license required (public governance dashboard)
- 2 developer seats minimum: **$732/year** (annual) or **$1,678 one-time** (perpetual)
- Highcharts Advantage (support + updates) included for first year with perpetual

## CSUN 2026 Presence
Highcharts is presenting at CSUN 2026 (the premier accessibility conference), confirming their ongoing commitment to accessibility as a core differentiator.

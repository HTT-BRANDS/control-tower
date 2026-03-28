# Chart.js 4.x Accessibility — Raw Findings

## Version Info
- **Current in project**: 4.4.7
- **Latest available**: 4.5.1 (Oct 13, 2025)
- **Bundle**: 196.1 kB minified, 66.8 kB gzipped, 1 dependency, tree-shakeable
- **GitHub**: 67.3k stars, 485 open issues, 55 PRs
- **License**: MIT

## Official Accessibility Documentation

Source: https://www.chartjs.org/docs/latest/general/accessibility.html
Last updated: 10/13/2025

> "Chart.js charts are rendered on user provided canvas elements. Thus, it is up to the user to create the canvas element in a way that is accessible."

> "The canvas element has support in all browsers and will render on screen but the canvas content will not be accessible to screen readers."

> "With canvas, the accessibility has to be added with ARIA attributes on the canvas element or added using internal fallback content placed within the opening and closing canvas tags."

### Official Examples (from docs)

**Accessible canvas**:
```html
<canvas id="goodCanvas1" width="400" height="100"
        aria-label="Hello ARIA World" role="img"></canvas>
```

```html
<canvas id="okCanvas2" width="400" height="100">
    <p>Hello Fallback World</p>
</canvas>
```

**Inaccessible canvas** (what NOT to do):
```html
<canvas id="badCanvas1" width="400" height="100"></canvas>
```

## What Chart.js Does NOT Provide

1. **No ARIA attribute generation** — all ARIA must be manually added
2. **No screen reader content** — canvas content is invisible to screen readers
3. **No keyboard navigation** — cannot tab to or navigate data points
4. **No auto-generated descriptions** — no text descriptions of chart data
5. **No pattern fills** — color-only differentiation
6. **No high contrast mode** — no response to `prefers-contrast`
7. **No data table generation** — no alternative text representation
8. **No focus management** — no focus indicators on chart elements
9. **No sonification** — no audio representation of data

## GitHub Issues Analysis

### Open Accessibility Issues (7)
- #12101: CSS Level 4 Color Syntax support (Jul 2025)
- #11768: Dynamic text resize not supported (May 2024)
- #11767: Tooltip content is not hoverable (May 2024)
- #10372: Accessibility Testing — Applying High contrast (May 2022, 4 comments)

### Notable Closed Issues
- #11903: "Polar Area chart is not accessible via keyboard" — closed as duplicate (Sep 2024)
- #10600: "Keyboard event objects for accessibility" — closed (Aug 2022)
- #10476: "Support screen reader to read graph label and content" — closed (Aug 2022)
- #10448: "keyboard accessibility for graph labels" — closed (Jun 2022)
- #11994: "Grids not visible in high contrast themes" — closed bug (Jan 2025)
- #11565: "Accessibility: docs site alt text" — closed documentation (Nov 2023)

### Pattern: Community asks for accessibility, maintainers direct to plugins
The consistent pattern in closed issues is that Chart.js core team recommends implementing accessibility externally via plugins rather than building it into core. This is a deliberate architectural choice — canvas-based rendering makes built-in accessibility very difficult.

## Current Project Implementation Gaps

In `app/static/js/charts/dashboard.js`:
1. ❌ No `role="img"` on canvas elements
2. ❌ No `aria-label` attributes on canvas elements
3. ❌ No fallback content inside `<canvas>` tags
4. ❌ No data tables alongside charts
5. ❌ Uses red (#EF4444) and green (#10B981) for pass/fail — problematic for color blindness
6. ❌ No keyboard navigation for chart data
7. ❌ No screen reader announcements
8. ✅ Does re-initialize charts on HTMX page swaps (`htmx:afterSettle`)
9. ✅ Uses CSS custom properties for theming (can be leveraged for accessibility)

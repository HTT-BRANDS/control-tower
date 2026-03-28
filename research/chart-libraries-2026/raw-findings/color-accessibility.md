# Color Accessibility for Governance Dashboards

## The Red/Green Problem

### Current Issue in This Project
```javascript
// From app/static/js/charts/dashboard.js
const colorSuccess = '#10B981'; // Emerald green
const colorError = '#EF4444';   // Red
const colorWarning = '#F59E0B'; // Amber
```

### Why Red/Green Is Problematic
- **Deuteranopia** (green-blind): ~6% of males — red and green appear similar (brownish)
- **Protanopia** (red-blind): ~1% of males — red appears dark, green appears yellowish
- **Total**: ~8% of males, ~0.5% of females have some form of red-green color blindness
- For a governance platform with enterprise users, this means **~1 in 12 male users** cannot distinguish pass/fail by color alone

### WCAG 1.4.1: Use of Color
> "Color is not used as the only visual means of conveying information, indicating an action, prompting a response, or distinguishing a visual element."

This means you MUST pair color with at least one other differentiator:
- Text labels ("Pass", "Fail", "Warning")
- Icons (✅ ⚠️ ❌)
- Patterns (solid, striped, crosshatched)
- Shape differences

---

## Recommended Accessible Color Palettes

### Option 1: Blue-Amber-Orange (Recommended)
```javascript
const colorPass    = '#0369A1'; // Sky-700 (blue)
const colorWarning = '#D97706'; // Amber-600
const colorFail    = '#C2410C'; // Orange-700 (red-orange)
```
**Why**: Blue and orange are on opposite ends of the color spectrum and remain distinguishable across all forms of color blindness. Avoids pure red and pure green entirely.

### Option 2: Blue-Yellow-Red (Classic accessible)
```javascript
const colorPass    = '#1D4ED8'; // Blue-700
const colorWarning = '#CA8A04'; // Yellow-600
const colorFail    = '#B91C1C'; // Red-700
```

### Option 3: Teal-Amber-Rose (Softer)
```javascript
const colorPass    = '#0F766E'; // Teal-700
const colorWarning = '#D97706'; // Amber-600
const colorFail    = '#BE123C'; // Rose-700
```

### For Brand Integration
The project uses `--brand-primary: #500711` (dark burgundy). This can be used for neutral/informational elements while the accessible palette handles status/compliance.

---

## Pattern Fill Strategies

### When to Use Patterns
- **Always** when color alone differentiates categories in bar/donut charts
- **Optionally** as a user preference toggle (some users find patterns visually noisy)
- **Required** for print/PDF output (may be grayscale)

### Recommended Pattern Set for Governance
```
Pass/Compliant:   Solid fill (no pattern) — blue
Warning/Partial:  Diagonal stripes (45°)  — amber
Fail/Non-comply:  Crosshatch (grid)       — red-orange
Not Assessed:     Dots/circles            — gray
In Progress:      Horizontal stripes      — violet
```

### Implementation with Chart.js
```javascript
function createPatternCanvas(color, patternType) {
  const size = 10;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d');

  // Base color
  ctx.fillStyle = color;
  ctx.fillRect(0, 0, size, size);

  // Pattern overlay
  ctx.strokeStyle = 'rgba(255,255,255,0.4)';
  ctx.lineWidth = 2;

  switch (patternType) {
    case 'solid':
      break; // No pattern
    case 'diagonal':
      ctx.beginPath();
      ctx.moveTo(0, size);
      ctx.lineTo(size, 0);
      ctx.stroke();
      break;
    case 'crosshatch':
      ctx.beginPath();
      ctx.moveTo(0, size/2);
      ctx.lineTo(size, size/2);
      ctx.moveTo(size/2, 0);
      ctx.lineTo(size/2, size);
      ctx.stroke();
      break;
    case 'dots':
      ctx.fillStyle = 'rgba(255,255,255,0.4)';
      ctx.beginPath();
      ctx.arc(size/2, size/2, 2, 0, Math.PI * 2);
      ctx.fill();
      break;
    case 'horizontal':
      ctx.beginPath();
      ctx.moveTo(0, size/2);
      ctx.lineTo(size, size/2);
      ctx.stroke();
      break;
  }
  return ctx.createPattern(canvas, 'repeat');
}
```

### ECharts Decal (Built-in Alternative)
```javascript
{
  aria: {
    enabled: true,
    decal: {
      show: true,
      decals: [
        { symbol: 'rect', symbolSize: 1 },            // solid
        { symbol: 'triangle', symbolSize: 0.6 },       // triangles
        { dashArrayX: 5, dashArrayY: 3 },               // dashes
        { symbol: 'circle', symbolSize: 0.5 },          // dots
      ]
    }
  }
}
```

---

## Governance Dashboard Color Mapping

### Compliance Scores
| Score Range | Label | Color | Icon | Pattern |
|------------|-------|-------|------|---------|
| 90-100% | Compliant | Blue (#0369A1) | ✅ | Solid |
| 70-89% | Partial | Amber (#D97706) | ⚠️ | Diagonal |
| 0-69% | Non-Compliant | Red-Orange (#C2410C) | ❌ | Crosshatch |

### Resource Health
| Status | Color | Icon | Pattern |
|--------|-------|------|---------|
| Healthy | Blue (#0369A1) | ● | Solid |
| Degraded | Amber (#D97706) | ▲ | Diagonal |
| Unhealthy | Red-Orange (#C2410C) | ■ | Crosshatch |
| Unknown | Gray (#6B7280) | ○ | Dots |

### Cost Trends
For line/area charts, use single-color with area fill opacity:
```javascript
borderColor: '#0369A1',           // Blue line
backgroundColor: '#0369A11A',    // 10% opacity blue fill
```

If multiple series, use distinct hues + dash patterns:
```javascript
// Series 1: Actual cost
{ borderColor: '#0369A1', borderDash: [] }          // Solid blue

// Series 2: Budgeted cost
{ borderColor: '#6D28D9', borderDash: [10, 5] }     // Dashed violet

// Series 3: Forecast
{ borderColor: '#D97706', borderDash: [5, 5] }      // Dotted amber
```

---

## Testing Color Accessibility

### Tools
1. **Viz Palette** — https://projects.susielu.com/viz-palette (test palettes for CVD)
2. **Chroma.js** — https://vis4.net/palettes (generate accessible palettes)
3. **WebAIM Contrast Checker** — https://webaim.org/resources/contrastchecker/
4. **Sim Daltonism** — macOS app for simulating color blindness
5. **Chrome DevTools** — Rendering > Emulate vision deficiencies

### Testing Procedure
1. Apply proposed palette to a chart
2. Test with simulated protanopia, deuteranopia, tritanopia, achromatopsia
3. Verify all categories remain distinguishable in each simulation
4. Verify contrast ratios meet WCAG 2.2 AA (3:1 for non-text, 4.5:1 for text)
5. Verify patterns/icons provide differentiation even in grayscale

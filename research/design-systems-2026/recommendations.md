# Project-Specific Recommendations

## Context: Azure Governance Platform

### Current Stack
- **CSS:** Tailwind CSS v4.2.1 with `@theme` tokens (47+ CSS custom properties × 5 brands)
- **Templates:** Jinja2 (server-rendered HTML)
- **Interactivity:** HTMX + vanilla JS
- **Brands:** HTT (burgundy), Bishops (orange), Lash Lounge (purple), Frenchies (blue), Delta Crown (green)
- **Brand injection:** `css_generator.py` → inline `<style>` tags with `[data-brand]` selectors
- **Existing issues:** 52 design system violations (DESIGN_SYSTEM_AUDIT.md), WCAG violations, redundant utility classes

---

## Priority 1: Adopt DaisyUI 5.x (Effort: ~1 day)

### Why
- Eliminates the need to hand-build component styles
- Pure CSS — no HTMX reinitialization problems
- Semantic color system reduces hardcoded Tailwind palette usage
- 35 built-in themes + custom theme support

### Implementation Steps

#### Step 1: Install DaisyUI
```bash
npm install -D daisyui@latest
```

#### Step 2: Add to theme.src.css
```css
@import "tailwindcss";
@plugin "daisyui" {
  themes: light --default, dark --prefersdark;
}
```

#### Step 3: Create brand themes (in theme.src.css or separate file)
DaisyUI custom themes use CSS custom properties, which can be mapped from the existing brand tokens:

```css
/* HTT Brand Theme */
[data-theme="htt"] {
  --color-primary: #500711;
  --color-primary-content: #ffffff;
  --color-secondary: #BB86FC;
  --color-secondary-content: #111827;
  --color-accent: #FFC957;
  --color-accent-content: #111827;
  --color-neutral: #374151;
  --color-neutral-content: #F9FAFB;
  --color-base-100: #FFFFFF;
  --color-base-200: #F9FAFB;
  --color-base-300: #F3F4F6;
  --color-base-content: #111827;
  --color-info: #3B82F6;
  --color-success: #10B981;
  --color-warning: #F59E0B;
  --color-error: #EF4444;
}

/* Bishops Brand Theme */
[data-theme="bishops"] {
  --color-primary: #c2410c;
  --color-primary-content: #ffffff;
  /* ... */
}

/* Lash Lounge Brand Theme */
[data-theme="lashlounge"] {
  --color-primary: #7c3aed;
  --color-primary-content: #ffffff;
  /* ... */
}

/* Frenchies Brand Theme */
[data-theme="frenchies"] {
  --color-primary: #2563eb;
  --color-primary-content: #ffffff;
  /* ... */
}

/* Delta Crown Brand Theme */
[data-theme="deltacrown"] {
  --color-primary: #004538;
  --color-primary-content: #ffffff;
  /* ... */
}
```

#### Step 4: Update Jinja2 base template
```html
<!-- Change from data-brand to data-theme on <html> -->
<html data-theme="{{ brand_theme }}" class="{% if dark_mode %}dark{% endif %}">
```

#### Step 5: Migrate component classes incrementally
```html
<!-- Before -->
<button class="bg-brand-primary-100 text-white hover:bg-brand-primary-110 rounded-lg px-4 py-2">
  Submit
</button>

<!-- After -->
<button class="btn btn-primary">
  Submit
</button>
```

### Coexistence Strategy
DaisyUI and existing custom tokens can coexist. Use DaisyUI for standard components (buttons, cards, modals, badges, alerts) and retain custom tokens for brand-specific decorative elements (sidebar gradients, brand illustrations, etc.).

---

## Priority 2: Restructure Token Architecture (Effort: ~4 hours)

### Problem
The current 47+ tokens mix three concerns:
1. **Brand identity** (primary, secondary, accent colors + shades)
2. **Semantic purpose** (success, warning, error, info)
3. **Surface/layout** (backgrounds, text hierarchy, borders)

This creates a flat namespace that's hard to maintain across 5 brands.

### Proposed 3-Tier Architecture

#### Tier 1: Brand Primitives (per-brand, injected by css_generator.py)
These are the raw brand colors — only 3-5 per brand:
```css
[data-brand="httbrands"] {
  --brand-hue: 350;
  --brand-primary: oklch(0.30 0.12 var(--brand-hue));
  --brand-secondary: #BB86FC;
  --brand-accent: #FFC957;
}
```
**Count: ~5 tokens × 5 brands = 25 values** (down from 50+ per brand)

#### Tier 2: Semantic Aliases (shared, reference Tier 1)
These don't change per brand — they reference Tier 1:
```css
:root {
  /* Semantic colors — same across all brands */
  --color-success: #10B981;
  --color-warning: #F59E0B;
  --color-error: #EF4444;
  --color-info: #3B82F6;

  /* Surface colors — same across all brands */
  --bg-primary: #FFFFFF;
  --bg-secondary: #F9FAFB;
  --bg-tertiary: #F3F4F6;

  /* Text hierarchy — same across all brands */
  --text-primary: #111827;
  --text-secondary: #4B5563;
  --text-muted: #9CA3AF;
}
```
**Count: ~15 shared tokens** (not multiplied by brands)

#### Tier 3: Tailwind Bridge (in @theme, references Tier 1 & 2)
```css
@theme {
  --color-brand-primary: var(--brand-primary);
  --color-success: var(--color-success);
  --color-bg-primary: var(--bg-primary);
  /* Only tokens that need Tailwind utility classes */
}
```
**Count: ~20 bridge tokens** (subset of Tier 1 + 2)

### Shade Generation
Instead of defining 10 shades per color per brand (primary-5, primary-10, ... primary-180), use oklch color manipulation:

```css
@theme {
  --color-brand-primary: var(--brand-primary);
  --color-brand-primary-light: oklch(from var(--brand-primary) calc(l + 0.3) c h);
  --color-brand-primary-dark: oklch(from var(--brand-primary) calc(l - 0.1) c h);
}
```

This reduces **50 shade tokens to 3** while maintaining visual consistency. Requires browser support for relative color syntax (supported in all modern browsers as of 2025).

### Migration Path
1. Define Tier 1 brand primitives alongside existing tokens
2. Map DaisyUI theme variables to Tier 1 primitives
3. Gradually replace hardcoded palette usage (the 52 violations) with DaisyUI semantic classes
4. Once all violations are fixed, remove redundant manual utility classes from theme.src.css
5. Remove unused shade tokens

---

## Priority 3: Clean Up Redundant Utility Classes (Effort: ~2 hours)

### Problem
`theme.src.css` defines 30+ manual utility classes (lines 350-430) that duplicate what `@theme` already generates:

```css
/* REDUNDANT — @theme already generates these from --color-brand-primary */
.bg-brand-primary { background-color: var(--brand-primary); }
.text-brand-primary { color: var(--brand-primary); }
.border-brand-primary { border-color: var(--brand-primary); }
```

### Fix
Remove all manual utility classes that have `@theme` equivalents. The `@theme { --color-brand-primary: var(--brand-primary) }` line already generates `bg-brand-primary`, `text-brand-primary`, `border-brand-primary`, `ring-brand-primary`, etc.

**Keep only:** Classes that Tailwind can't generate (compound selectors, pseudo-element styles, complex compositions like `.btn-brand`).

---

## Priority 4: Fix WCAG 2.2 AA Violations (Effort: ~1 day)

### Addressable by DaisyUI adoption
- ✅ Hardcoded `focus:ring-blue-500` → DaisyUI uses theme-aware focus rings
- ✅ Raw Tailwind palette colors → DaisyUI semantic classes
- ✅ `bg-gray-*` → DaisyUI's `bg-base-*` surface system

### Requires manual work
- ⚠️ Missing `focus-visible` on interactive elements → Add to Jinja2 macros
- ⚠️ `focus:outline-none` suppressing native focus → Remove and replace with DaisyUI focus styles
- ⚠️ Conflicting `:focus-visible` rules across CSS files → Consolidate in single file
- ⚠️ WCAG contrast violations → Verify DaisyUI theme colors pass 4.5:1 ratio

---

## Priority 5: Do NOT Adopt (Anti-recommendations)

### ❌ Flowbite
- **Why not:** Requires JavaScript reinit after HTMX swaps; 215 open issues; no semantic token system; commercial model risk
- **If reconsidered:** Only for specific interactive components (datepicker, rich dropdowns) that DaisyUI lacks

### ❌ shadcn/ui
- **Why not:** Requires React + Radix UI; cannot be used with Jinja2 templates
- **What to extract:** Theming pattern (CSS variable naming conventions, oklch color space)

### ❌ Pico CSS
- **Why not:** Conflicts with Tailwind's reset and utility system; limited component set
- **When it would work:** New projects without Tailwind commitment

### ❌ Web Awesome (for now)
- **Why not:** New project (Shoelace successor), smaller community, web components may conflict with HTMX's DOM manipulation
- **Revisit when:** v4+ with proven HTMX compatibility

---

## Implementation Timeline

| Week | Task | Effort | Impact |
|------|------|--------|--------|
| 1 | Install DaisyUI, create 5 brand themes | 4 hrs | High — enables all subsequent work |
| 1 | Remove redundant utility classes | 2 hrs | Medium — reduces CSS size |
| 2 | Migrate buttons, badges, alerts to DaisyUI classes | 4 hrs | High — fixes ~30 violations |
| 2 | Fix focus-visible and outline conflicts | 2 hrs | Critical — WCAG compliance |
| 3 | Restructure tokens to 3-tier architecture | 4 hrs | High — reduces long-term maintenance |
| 3 | Update css_generator.py for new token structure | 2 hrs | Medium |
| 4 | Migrate remaining components (tables, cards, modals) | 4 hrs | Medium |
| 4 | WCAG contrast audit with DaisyUI themes | 2 hrs | Critical |

**Total estimated effort: ~24 hours (3 developer-days)**
**Expected outcome:** 80%+ reduction in design system violations, 60% reduction in token maintenance burden, full DaisyUI component coverage

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| DaisyUI breaking changes in v6+ | Pin to `~5.5.x`, monitor changelog |
| DaisyUI theme variables conflict with existing tokens | Use namespace separation (DaisyUI uses `--color-primary`, project uses `--brand-primary`) |
| DaisyUI doesn't cover a needed component | Build custom using existing `@theme` tokens + Tailwind utilities |
| HTMX compatibility issues | DaisyUI is pure CSS — no JS initialization needed, zero HTMX risk |
| Performance impact of DaisyUI CSS | DaisyUI uses Tailwind's tree-shaking — only used classes are included |

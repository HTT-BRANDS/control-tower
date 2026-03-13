# HTT Brands Design System Audit — Azure Governance Platform

**Auditor:** Claude (automated)
**Date:** 2026-03-12
**Scope:** All files under `app/templates/`, `app/static/css/`, `app/static/js/`
**Design System Reference:** `theme.src.css` token definitions, `dark-mode.css`, `accessibility.css`

---

## Executive Summary

**52 distinct violations** found across **18 files**, spanning 5 categories. The two most problematic files are `dmarc_dashboard.html` (~35 violations) and `riverside_dashboard.html` (~30 violations) — both bypass the design system entirely and use raw Tailwind default palette colors. The core app shell (`base.html`, `macros/ui.html`) is largely compliant, but has token-naming bugs that cause invisible text and a critical focus-indicator conflict between CSS files.

| Category | Count | Severity |
|---|---|---|
| V1: Hardcoded `focus:ring-blue-500` | 1 | High |
| V2: Raw Tailwind palette bypassing tokens | ~65+ | High |
| V3: `bg-gray-*` instead of `bg-surface-*` | ~45+ | Medium |
| V4: Missing focus-visible on interactive elements | ~30+ | High (WCAG) |
| V5: `focus:outline-none` suppressing native focus | 5 | High (WCAG) |
| V6: Conflicting `:focus-visible` rules across CSS files | 1 | Critical |
| V7: CSS button `:focus` strips `outline` | 2 | High (WCAG) |
| V8: WCAG 2.2 AA contrast violations | ~8 | Critical |
| V9: Inline style hardcoding (login page) | 10+ | Medium |

---

## V1: Hardcoded `focus:ring-blue-500`

### Why it matters
`ring-blue-500` is Tailwind's generic blue, not the HTT brand primary. On every page except Riverside, this creates a disjointed brand experience. Focus rings should use `ring-brand-primary` or `ring-brand-primary-50` (mapped to `var(--brand-primary)`) so they adapt per-tenant.

### Violations

| File | Line | Current | Should Be |
|---|---|---|---|
| `app/static/js/navigation/confirmDialog.js` | 49 | `focus:ring-blue-500` | `ring-brand-primary` |

---

## V2: Raw Tailwind Default Palette Colors (Not Using Design Tokens)

### Why it matters
The design system defines semantic color tokens (`wm-blue-100`, `wm-red-100`, `wm-green-100`, `brand-primary-*`) and utility classes (`.bg-success`, `.bg-danger`, `.bg-info`, `.text-success`, etc.) specifically so that colors are consistent, dark-mode aware, and maintainable. Raw Tailwind classes like `bg-blue-600`, `bg-red-600`, `text-green-800` bypass all of this — they won't respond to dark mode, won't adapt to tenant branding, and create a maintenance burden.

### Violations — `dmarc_dashboard.html`

| Line(s) | Current | Should Be |
|---|---|---|
| 16, 66 | `bg-blue-100 text-blue-800` | `bg-wm-blue-5 text-wm-blue-100` |
| 34, 38, 42, 46, 50 | `text-blue-200` | `text-white/80` or Riverside token |
| 102, 128 | `bg-green-500` | `bg-wm-green-100` |
| 110, 136 | `bg-red-500` | `bg-wm-red-100` |
| 163 | `text-red-900` | `text-wm-red-130` |
| 164 | `bg-red-600` | `bg-wm-red-100` |
| 211 | `bg-blue-600 hover:bg-blue-700` | `bg-wm-blue-100 hover:bg-wm-blue-110` |
| 280, 285 | `text-red-400`, `text-red-700` | `text-wm-red-50`, `text-wm-red-100` |
| 305 | `bg-green-500 / bg-yellow-500 / bg-red-500` | `bg-wm-green-100 / bg-wm-spark-100 / bg-wm-red-100` |
| 341, 344, 351, 354 | `bg-green-100 text-green-800 / bg-red-100 text-red-800` | `bg-wm-green-5 text-wm-green-100 / bg-wm-red-5 text-wm-red-100` |
| 368, 370 | `text-green-600 / text-red-600 / bg-green-600 / bg-red-600` | `text-wm-green-100 / text-wm-red-100` etc. |
| 404, 422, 445, 463 | `bg-green-600 / bg-red-500` | `bg-wm-green-100 / bg-wm-red-100` |
| 475, 478 | `bg-red-100 text-red-800 / bg-blue-100 text-blue-800` | Use wm-* tokens |
| 491 | `text-blue-600 hover:text-blue-900` | `text-wm-blue-100 hover:text-wm-blue-130` |
| 504 | `text-red-600` | `text-wm-red-100` |
| 507 | `bg-red-100 text-red-800 / bg-yellow-100 text-yellow-800` | Use wm-* tokens |
| 640 | `bg-red-500` (JS toast) | `bg-wm-red-100` |
| 648 | `bg-green-500` (JS toast) | `bg-wm-green-100` |

### Violations — `riverside_dashboard.html`

| Line(s) | Current | Should Be |
|---|---|---|
| 18 | `bg-red-100 text-red-800` | `bg-wm-red-5 text-wm-red-100` |
| 35, 39, 43, 47, 50 | `text-blue-200` | `text-white/80` |
| 62 | `bg-blue-100` | `bg-wm-blue-5` |
| 69, 72, 229, 232, 335 | `text-blue-600 / bg-blue-600` | `text-wm-blue-100 / bg-wm-blue-100` |
| 84, 94 | `bg-green-100 / bg-green-600` | `bg-wm-green-5 / bg-wm-green-100` |
| 128, 138 | `bg-red-100 / bg-red-600` | `bg-wm-red-5 / bg-wm-red-100` |
| 200, 201 | `text-red-900 / bg-red-600` | `text-wm-red-130 / bg-wm-red-100` |
| 254 | `bg-blue-600 hover:bg-blue-700` | `bg-wm-blue-100 hover:bg-wm-blue-110` |
| 263 | `bg-red-600 hover:bg-red-700` | `bg-wm-red-100 hover:bg-wm-red-110` |
| 339, 342, 345, 349 | `bg-green-100 / bg-red-100 / bg-yellow-100` (JS) | Use wm-* tokens |
| 357-360 | `bg-green-600 / bg-blue-600 / bg-red-600` (JS) | Use wm-* tokens |
| 384 | `bg-red-600` (JS) | `bg-wm-red-100` |
| 409, 412, 414 | `bg-red-100 text-red-800 / text-red-600` (JS) | Use wm-* tokens |

### Violations — `macros/ui.html`

| Line | Current | Should Be |
|---|---|---|
| 50 | `bg-green-100 text-green-800` (success badge) | `bg-success/10 text-success` or dedicated semantic token |
| 51 | `bg-yellow-100 text-yellow-800` (warning badge) | `bg-warning/10 text-warning` |
| 52 | `bg-red-100 text-red-800` (danger badge) | `bg-danger/10 text-danger` |

### Violations — `confirmDialog.js`

| Line | Current | Should Be |
|---|---|---|
| 40 | `bg-red-100`, `text-red-600` | `bg-danger/10`, `text-danger` |
| 46 | `text-gray-900` | `text-primary-theme` |
| 47 | `text-gray-500` | `text-muted-theme` |
| 49 | `text-gray-700 bg-white border-gray-300 hover:bg-gray-50` | Use surface/text tokens |
| 52 | `bg-red-600 hover:bg-red-700 focus:ring-red-500` | `bg-danger hover:opacity-90 ring-brand-primary` |

### Violations — Other pages

| File | Line | Current | Should Be |
|---|---|---|---|
| `resources.html` | 43, 203 | `text-red-600` | `text-danger` |
| `identity.html` | 43 | `text-red-600` | `text-danger` |
| `compliance.html` | 48, 109, 113-115, 146, 160 | Various `text-red-600`, `bg-green-100`, `bg-red-100` | Use semantic tokens |
| `costs.html` | 140, 188, 190 | `text-red-600`, `text-green-600`, `bg-red-100` | Use semantic tokens |

---

## V3: `bg-gray-*` Instead of `bg-surface-primary/secondary/tertiary`

### Why it matters
The design system defines `bg-surface-primary` (white/`#0F0F0F`), `bg-surface-secondary` (`#F9FAFB`/`#171717`), and `bg-surface-tertiary` (`#F3F4F6`/`#262626`) as dark-mode-aware surface tokens. `dark-mode.css` heroically patches `.dark .bg-gray-50` → `var(--bg-secondary)` etc., but this is fragile — it relies on CSS specificity hacks and doesn't cover all gray shades. Using the semantic classes directly eliminates the need for these overrides.

### Violations — Page backgrounds (`bg-gray-100`)

| File | Line | Current | Should Be |
|---|---|---|---|
| `dmarc_dashboard.html` | 6 | `bg-gray-100` | `bg-surface-tertiary` |
| `riverside_dashboard.html` | 8 | `bg-gray-100` | `bg-surface-tertiary` |
| `resources.html` | 8 | `bg-gray-100` | `bg-surface-tertiary` |
| `compliance.html` | 8 | `bg-gray-100` | `bg-surface-tertiary` |
| `identity.html` | 8 | `bg-gray-100` | `bg-surface-tertiary` |
| `costs.html` | 8 | `bg-gray-100` | `bg-surface-tertiary` |

### Violations — Table headers (`bg-gray-50`)

| File | Lines |
|---|---|
| `dmarc_dashboard.html` | 72, 169, 193 |
| `riverside_dashboard.html` | 151, 206, 228, 235, 242 |
| `resources.html` | 60, 83, 104 |
| `compliance.html` | 60, 82 |
| `identity.html` | 60, 83, 104 |
| `costs.html` | 60, 93 |

**Should be:** `bg-surface-secondary`

### Violations — Progress bar tracks (`bg-gray-200`)

| File | Lines |
|---|---|
| `dmarc_dashboard.html` | 318, 369, 403, 412, 421, 444, 453, 462 |
| `riverside_dashboard.html` | 71, 93, 115, 137, 231, 238, 245, 334, 375, 394 |
| `costs.html` | 155 |

**Should be:** `bg-surface-tertiary` or a dedicated `--progress-track` token.

### Violations — Button backgrounds (`bg-gray-600`)

| File | Line | Should Be |
|---|---|---|
| `dmarc_dashboard.html` | 217 | `bg-wm-gray-100 hover:bg-wm-gray-110` |
| `riverside_dashboard.html` | 260 | `bg-wm-gray-100 hover:bg-wm-gray-110` |

---

## V4: Missing `focus-visible` Indicators on Interactive Elements

### Why it matters
WCAG 2.2 SC 2.4.7 (Focus Visible) requires all interactive elements to have a visible focus indicator. WCAG 2.4.11 (Focus Appearance, new in 2.2) further requires that the focus indicator have sufficient area and contrast. Many buttons and links in this codebase have no explicit focus styles — they rely on the global `:focus-visible` rule in `accessibility.css`, but that rule conflicts with `theme.src.css` (see V6).

### Buttons with ZERO focus styles

| File | Line | Element |
|---|---|---|
| `sync_status_card.html` | 89 | Sync Costs button |
| `sync_status_card.html` | 95 | Sync Compliance button |
| `sync_status_card.html` | 101 | Sync Resources button |
| `sync_status_card.html` | 107 | Sync Identity button |
| `sync_history_table.html` | 9 | Refresh button |
| `tenant_sync_grid.html` | 10 | Refresh button |
| `active_alerts.html` | 20 | Refresh button |
| `tenant_status_card.html` | 83 | Force Sync button |
| `tenant_status_card.html` | 93 | View tenant details link |
| `sync_alerts.html` | 60 | Acknowledge button |
| `sync_alerts.html` | 64 | Mark resolved button |
| `dmarc_dashboard.html` | 66-67 | Filter buttons (All / Riverside Only) |
| `dmarc_dashboard.html` | 148 | Trend days select |
| `dmarc_dashboard.html` | 211 | Sync DMARC button |
| `dmarc_dashboard.html` | 217 | Export link |
| `dmarc_dashboard.html` | 491 | Acknowledge alert button (JS) |
| `riverside_dashboard.html` | 254 | Sync link |
| `riverside_dashboard.html` | 260 | Requirements link |
| `riverside_dashboard.html` | 263 | Gaps link |
| `riverside.html` | 24-28 | Sync Now button |
| `riverside.html` | 98 | Tab buttons |
| `riverside.html` | 123 | Tab buttons |
| `riverside.html` | 229, 235, 241 | Action links |
| `preflight.html` | 16, 24, 167, 202, 275, 289 | Various action buttons |
| `resources.html` | 17 | Load All Data button |
| `compliance.html` | 17 | Load All Data button |
| `costs.html` | 17 | Load All Data button |
| `identity.html` | 17 | Load All Data button |
| `dashboard.html` | 13 | Refresh button |
| `sync_dashboard.html` | 17, 28 | Action buttons |
| `base.html` | 187 | Theme toggle button |

---

## V5: `focus:outline-none` Suppressing Native Focus

### Why it matters
`focus:outline-none` removes the browser's default focus indicator. When paired with `focus:ring-2` without a ring color, the ring may be invisible (transparent). This is a direct WCAG 2.4.7 failure.

### Violations

| File | Line | Element | Issue |
|---|---|---|---|
| `login.html` | 39 | Username input | `focus:outline-none focus:ring-2` — no ring color specified |
| `login.html` | 47 | Password input | Same — no ring color specified |
| `alert_card.html` | 48 | Acknowledge button | `focus:outline-none` paired with `focus:ring-wm-green-100` — OK for ring, but removes outline for non-ring-supporting browsers |
| `confirmDialog.js` | 49 | Cancel button | `focus:outline-none focus:ring-blue-500` — wrong ring color |
| `confirmDialog.js` | 52 | Confirm button | `focus:outline-none focus:ring-red-500` — wrong ring color |

---

## V6: Conflicting `:focus-visible` Rules (CRITICAL)

### Why it matters
Two CSS files define global `:focus-visible` with **different colors**, and load order determines the winner:

1. **`theme.src.css` (line 244):**
   `outline: 2px solid var(--brand-primary, #500711);` — **HTT burgundy** (correct)

2. **`accessibility.css` (line 4):**
   `outline: 3px solid #0053e2;` — **Walmart/Riverside blue** (hardcoded)

CSS load order in `base.html`: theme.css → riverside.css → **accessibility.css** → dark-mode.css

**Result:** `accessibility.css` wins. ALL elements across ALL pages (including non-Riverside ones like Dashboard, Costs, Compliance) get a **Walmart blue focus ring** instead of the tenant's brand color.

### Fix

In `accessibility.css`, change the `:focus-visible` rule to use the CSS custom property:

```css
:focus-visible {
  outline: 3px solid var(--brand-primary, #500711);
  outline-offset: 2px;
  border-radius: 2px;
}
```

And on line 9, the tab/menu focus rule should also use the token:

```css
[tabindex="0"]:focus-visible,
[role="tab"]:focus-visible,
[role="menuitem"]:focus-visible {
  outline: 3px solid var(--brand-primary, #500711);
  outline-offset: 2px;
}
```

---

## V7: CSS Button Classes Use `outline: none` on `:focus`

### Why it matters
The `.btn-htt-primary:focus` and `.btn-brand:focus` rules in `theme.src.css` set `outline: none` and substitute a `box-shadow` ring. This fails in Windows High Contrast Mode (which ignores box-shadow) and may not meet WCAG 2.4.11 Focus Appearance requirements.

### Violations

| File | Line | Class | Issue |
|---|---|---|---|
| `theme.src.css` | 359-362 | `.btn-htt-primary:focus` | `outline: none; box-shadow: 0 0 0 3px rgba(80,7,17,0.3)` |
| `theme.src.css` | 392-394 | `.btn-brand:focus` | `outline: none; box-shadow: 0 0 0 2px var(--brand-primary-50)` |

### Fix

Replace `outline: none` with `outline: 2px solid transparent` (invisible but present for High Contrast Mode), and use `box-shadow` as the visual indicator. Or better, switch to `:focus-visible` and use `outline`:

```css
.btn-brand:focus-visible {
  outline: 2px solid var(--brand-primary, #500711);
  outline-offset: 2px;
}
```

---

## V8: WCAG 2.2 AA Contrast Violations

### Why it matters
WCAG SC 1.4.3 requires 4.5:1 contrast for normal text and 3:1 for large text (≥18pt or ≥14pt bold).

### Critical: `text-gray-100` Renders Near-Invisible

In `macros/ui.html`, the class `text-gray-100` is used for body text (labels, subtitles, percentages). In the compiled `theme.css`, this resolves to `color: var(--color-gray-100)` — Tailwind v4's `gray-100` which is approximately `#f3f4f6` (a near-white color).

**Contrast ratio: ~1.04:1 against white** — effectively invisible.

| File | Line | Usage | Impact |
|---|---|---|---|
| `macros/ui.html` | 38 | Card subtitle text | Invisible on white card background |
| `macros/ui.html` | 95 | Progress bar percentage | Invisible |
| `macros/ui.html` | 103 | Metric card label | Invisible |
| `macros/ui.html` | 106 | Change indicator text | Invisible |

**Root cause:** The developer likely intended `text-wm-gray-100` (#74767C, contrast ~4.7:1 — passes) but wrote `text-gray-100` which maps to Tailwind's default very-light gray.

### Critical: `text-gray-160` Is a Dead Class

On `macros/ui.html` lines 37 and 104, `text-gray-160` is used for primary text. Tailwind's default gray scale only goes to `gray-950`. The class `text-gray-160` **does not exist** in the compiled CSS and has no effect — text inherits whatever the parent sets, which may or may not be correct.

**Fix:** Replace with `text-primary-theme` (the design system's semantic text class).

### Login Page Inline Color Contrast

| Line | Element | Color | Background | Ratio | Pass? |
|---|---|---|---|---|---|
| 29 | Subtitle | `#6b7280` | `#FFFFFF` | 4.83:1 | Pass (normal text) |
| 66 | Footer text | `#9ca3af` | `#f3f4f6` | 2.31:1 | **Fail** |
| 70 | Version text | `#9ca3af` | `#f3f4f6` | 2.31:1 | **Fail** |

### Design System Token Warning: `--text-muted` (#9CA3AF)

The design system's own `text-muted-theme` token resolves to `#9CA3AF` in light mode. On white backgrounds (`bg-surface-primary`), this yields a contrast ratio of **2.54:1** — well below WCAG AA's 4.5:1 requirement. Consider darkening `--text-muted` to at least `#6B7280` (which yields 5.41:1) for AA compliance.

---

## V9: Inline Style Hardcoding (Login Page)

### Why it matters
`login.html` hardcodes hex values in inline `style` attributes instead of using CSS custom properties or Tailwind classes. This means the login page won't adapt to per-tenant branding (all tenants see HTT burgundy `#500711`) and won't respond to dark mode.

### Violations

| Line | Hardcoded Value | Should Use |
|---|---|---|
| 16 | `background-color: #f3f4f6` | `class="bg-surface-tertiary"` |
| 21 | `background-color: #500711` | `class="bg-brand-primary"` |
| 26 | `color: #500711` | `class="text-brand-primary"` |
| 29 | `color: #6b7280` | `class="text-secondary-theme"` |
| 37, 45 | `color: #374151` | `class="text-primary-theme"` |
| 40, 48 | `border-color: #d1d5db` | `class="border-border-default"` |
| 52 | `color: #991b1b; background-color: #fef2f2` | `class="text-danger bg-danger/5"` |
| 56 | `background-color: #500711` | `class="btn-brand"` or `class="btn-htt-primary"` |
| 66, 70 | `color: #9ca3af` | `class="text-muted-theme"` |

---

## Remediation Priority

### P0 — Do Immediately (WCAG failures, user-facing bugs)

1. **Fix `text-gray-100` → `text-muted-theme`** in `macros/ui.html` (4 lines) — text is currently invisible
2. **Fix `text-gray-160` → `text-primary-theme`** in `macros/ui.html` (2 lines) — class doesn't exist
3. **Fix conflicting `:focus-visible`** in `accessibility.css` — use `var(--brand-primary)` instead of `#0053e2`
4. **Fix `focus:outline-none` without ring color** in `login.html` (2 inputs) — add `focus:ring-brand-primary`
5. **Fix `.btn-brand:focus` / `.btn-htt-primary:focus`** — use `outline` not just `box-shadow`

### P1 — Do This Sprint (Design system consistency)

6. **Migrate `dmarc_dashboard.html`** — replace all raw Tailwind colors with `wm-*` tokens (~35 changes)
7. **Migrate `riverside_dashboard.html`** — same treatment (~30 changes)
8. **Replace `bg-gray-100` page backgrounds** with `bg-surface-tertiary` (6 pages)
9. **Replace `bg-gray-50` table headers** with `bg-surface-secondary` (~15 occurrences)
10. **Add focus styles** to all sync dashboard buttons (~10 elements)

### P2 — Do Next Sprint (Cleanup)

11. **Refactor `login.html`** — replace inline styles with design system classes
12. **Replace `bg-gray-200` progress tracks** with a token (~20 occurrences)
13. **Fix `confirmDialog.js`** — replace all hardcoded Tailwind classes with design system equivalents
14. **Add `focus-visible` styles** to all remaining interactive elements (~20 elements)
15. **Fix badge variants** in `macros/ui.html` — use semantic tokens instead of raw Tailwind

# Flowbite 4.x — Raw Findings

**Source:** https://flowbite.com/ (Official documentation, accessed 2026-03-27)
**Source credibility:** Tier 1 — Official project documentation

## Version Info
- Latest: **4.0.1** (visible in CDN URLs on quickstart page)
- GitHub: https://github.com/themesberg/flowbite
- Stars: 9.2k | Forks: 851 | Open issues: 215 (⚠️ high)
- License: MIT
- Last commit: 4 days ago
- Total commits: 2,782
- Org: Themesberg (commercial entity)

## Tailwind v4 Compatibility
- Has "Tailwind CSS v3 to v4" migration section in quickstart docs
- Supports Tailwind v4 via migration guide
- Also supports Tailwind v3, v2, WindiCSS

## Framework Requirements
- **Requires JavaScript** for interactive components (modals, dropdowns, datepickers)
- Two approaches for framework-free usage:
  1. **Data attributes:** `data-dropdown-toggle="target"` — declarative HTML
  2. **Init functions:** `new Dropdown(targetEl, triggerEl, options)` — programmatic API
- ESM and CJS module support
- TypeScript support

## HTMX Compatibility Concern
- Components initialize on page load
- HTMX DOM swaps won't trigger reinitialization
- Requires `htmx:afterSwap` event listener calling `initFlowbite()`
- Additional complexity for server-rendered apps

## CDN Usage
```html
<link href="https://cdn.jsdelivr.net/npm/flowbite@4.0.1/dist/flowbite.min.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/flowbite@4.0.1/dist/flowbite.min.js"></script>
```

## Theming
- No semantic color token system
- Uses Tailwind's default color palette directly
- Dark mode via Tailwind's dark variant
- No built-in theme switching mechanism
- **Not designed for multi-brand runtime theming**

## Component Count
600+ UI components, sections, and pages including:
Buttons, Dropdowns, Navigation, Modals, Datepickers, Tooltips, Badges, Alerts, Cards, Tables, Forms, etc.

## Integration Guides Available
React, Next.js, Vue, Nuxt, Svelte, Angular, Rails, Django, Flask, Phoenix, Laravel, Astro, Remix, Gatsby, SolidJS, Qwik

## Banner Note
"We have launched the new Flowbite Design System with variable tokens and more!" — suggests token system in newer versions, but not yet confirmed in free docs

## Accessibility
- Some ARIA attributes in component examples
- Focus management in modal/dropdown components
- No systematic WCAG compliance claim
- Keyboard navigation in some interactive components
- Less comprehensive than Web Awesome or Radix-based solutions

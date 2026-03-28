# Design Systems & Component Libraries for Server-Rendered Internal Tools

**Research Date:** 2026-03-27
**Context:** Azure Governance Platform — Tailwind CSS v4.2, Jinja2 templates, HTMX, vanilla JS, 5 brands × 47+ CSS custom properties
**Researcher:** web-puppy-dd6ea9

---

## Executive Summary

### Top Recommendation: DaisyUI 5.x + Refined Custom Token Layer

After evaluating 8+ options across 7 analytical dimensions, the recommended approach for this project is:

1. **Adopt DaisyUI 5.5.x** as the component library layer (pure CSS, no JS dependency, Tailwind v4 native)
2. **Retain and refine the existing `@theme` token system** — the current `var()` indirection pattern is the correct Tailwind v4 approach
3. **Restructure the 47+ tokens into 3 tiers** to reduce maintenance burden and token drift risk
4. **Do NOT adopt** Flowbite (JS dependency + maintenance concerns), Pico CSS (conflicts with Tailwind), or shadcn/ui (React-only components)

### Key Findings at a Glance

| Library | Version | TW v4 | No Framework | Theming | Accessibility | Stars | Verdict |
|---------|---------|-------|-------------|---------|--------------|-------|---------|
| **DaisyUI** | 5.5.19 | ✅ Native | ✅ Pure CSS | ✅ CSS vars + 35 themes | ⚠️ Partial WCAG | 40.6k | **✅ RECOMMENDED** |
| **Flowbite** | 4.0.1 | ✅ Migration guide | ⚠️ Needs JS | ❌ No token theming | ⚠️ Partial WCAG | 9.2k | ⚠️ Backup option |
| **shadcn/ui** | latest | ✅ | ❌ React required | ✅ CSS vars pattern | ✅ Radix a11y | 111k | ❌ Wrong stack |
| **Pico CSS** | 2.1.1 | N/A (standalone) | ✅ Classless | ✅ CSS vars | ✅ Semantic HTML | ~13k | ❌ Conflicts with TW |
| **Open Props** | 1.7.20 | N/A (tokens only) | ✅ Pure CSS | ✅ CSS vars | N/A (tokens only) | ~5k | ⚠️ Token reference |
| **Web Awesome** | 3.4.0 | N/A (web components) | ✅ Framework-agnostic | ✅ Themes | ✅ Built-in a11y | ~new | ⚠️ Early stage |

### Critical Decision: Why DaisyUI Wins

1. **Pure CSS** — zero JavaScript, works with any server-rendered HTML including Jinja2/HTMX
2. **Tailwind v4 native** — uses `@plugin "daisyui"` directive, no compatibility layer
3. **Semantic color system** — `bg-primary`, `bg-secondary`, `bg-accent`, `bg-success` etc. are CSS-variable-backed, maps directly to the project's token philosophy
4. **Custom themes via CSS** — can create 5 brand themes using CSS custom properties, injected server-side via `data-theme` attribute
5. **Active maintenance** — 40.6k stars, 37 open issues, 3 days since last commit, MIT license
6. **Additive, not replacement** — works alongside existing `@theme` tokens without conflict

---

## Detailed Sections

- [analysis.md](./analysis.md) — Multi-dimensional analysis of all options
- [sources.md](./sources.md) — Source credibility assessments
- [recommendations.md](./recommendations.md) — Project-specific implementation plan
- [raw-findings/](./raw-findings/) — Extracted data from each source

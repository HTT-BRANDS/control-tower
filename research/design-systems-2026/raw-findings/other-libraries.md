# Other Libraries — Raw Findings

## shadcn/ui
**Source:** https://ui.shadcn.com/ (Official, accessed 2026-03-27)
**Credibility:** Tier 1

- **What it is:** Code distribution platform + CLI, NOT a traditional installable library
- **Stars:** 111k (most popular in the space)
- **Architecture:** React + Radix UI primitives + Tailwind CSS
- **Non-React version:** ❌ Does not exist. Components are inherently React.
- **Theming approach:** CSS custom properties → Tailwind utility classes
  - Tokens: `background`, `foreground`, `primary`, `primary-foreground`, `secondary`, `muted`, `accent`, `destructive`, `border`, `input`, `ring`, `radius`
  - Uses `oklch()` color space
  - Configured via `tailwind.cssVariables: true` in components.json
- **Extractable value:** The theming pattern (semantic CSS variable naming + oklch) can be adopted without React
- **Principles:** Open Code, Composition, Distribution, Beautiful Defaults, AI-Ready

## Pico CSS v2.1.1
**Source:** https://picocss.com/ (Official, accessed 2026-03-27)
**Credibility:** Tier 1

- **Approach:** Classless CSS framework — styles semantic HTML elements directly
- **Features:** Version picker (NEW), Color schemes, Class-less version, Conditional styling (NEW), RTL support
- **Customization section** available in docs
- **Strengths:**
  - Zero-config: just add `<link rel="stylesheet" href="pico.min.css">`
  - Forms, tables, typography styled automatically
  - CSS custom properties for theming
  - Very lightweight
- **Weaknesses for this project:**
  - Conflicts with Tailwind CSS (both reset/style base elements)
  - No component classes (no .btn, .card, .modal)
  - Opinionated base styles would fight with Tailwind utilities

## Open Props v1.7.20
**Source:** https://open-props.style/ (Official, accessed 2026-03-27)
**Credibility:** Tier 1 (created by Adam Argyle, Google Chrome team)

- **What it is:** Pure CSS custom properties design token library
- **Tokens provided:**
  - Colors, Gradients, Shadows, Aspect Ratios, Typography, Easing, Animations, Sizes, Borders, Z-Index, Media Queries, Masks, Durations
- **Usage:** `@import "https://unpkg.com/open-props";`
- **License:** MIT
- **Strengths:**
  - Framework-agnostic (just CSS variables)
  - Expertly designed by browser engineer
  - Good reference for non-color tokens (shadows, easing, sizes)
- **Weaknesses for this project:**
  - Color tokens are generic, not semantic/brand-aware
  - Would be supplementary only, not a replacement
  - Adds another dependency for minimal benefit (project already has good token coverage)

## Web Awesome v3.4.0 (Shoelace successor)
**Source:** https://webawesome.com/ (Official, accessed 2026-03-27)
**Credibility:** Tier 2 (newer project)

- **Predecessor:** Shoelace (now sunset — "There is no active development here")
- **Architecture:** Web Components (Custom Elements + Shadow DOM)
- **Stats:** 50+ components, 100+ patterns, 11 themes
- **Framework support:** Framework-agnostic (React, Vue, Angular, Svelte, vanilla JS)
- **Pricing:** Free tier + Pro tier
- **Strengths:**
  - Built-in accessibility (ARIA roles, keyboard nav, focus management)
  - Web Components standard — works without any framework
  - Highly customizable via CSS custom properties
- **Weaknesses for this project:**
  - Shadow DOM may conflict with Tailwind utility classes
  - Web Components need registration/initialization after HTMX swaps
  - Newer project with smaller community than DaisyUI
  - Pro tier suggests potential feature gatekeeping
  - Web Components + HTMX interaction needs testing

## Shoelace v2.20.1 (SUNSET)
**Source:** https://shoelace.style/ (Official, accessed 2026-03-27)
- **Status:** SUNSET — "FYI: Shoelace Is Sunset. There is no active development here. Use Web Awesome for ongoing work, issues, and features."
- **Do not adopt.**

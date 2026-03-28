# Source Credibility Assessment

## Tier 1 — Official Documentation (Highest Reliability)

### Tailwind CSS v4.2 Documentation
- **URL:** https://tailwindcss.com/docs/theme
- **Authority:** Official docs from Tailwind Labs (framework authors)
- **Currency:** v4.2 (current), page updated for v4 release
- **Key findings:** `@theme` directive creates CSS variables AND utility classes; `:root` for non-utility variables; `@custom-variant` for dark mode; theme variable namespaces for organization
- **Credibility:** ★★★★★

### DaisyUI Official Documentation
- **URL:** https://daisyui.com/
- **Authority:** Official project site by Pouya Saadeghi (creator)
- **Currency:** v5.5.19 (March 2026), actively maintained
- **Key findings:** Pure CSS plugin for Tailwind v4 via `@plugin "daisyui"`; 35 built-in themes; semantic color system backed by CSS variables; custom theme creation; no JS dependency
- **Credibility:** ★★★★★

### Flowbite Official Documentation
- **URL:** https://flowbite.com/docs/getting-started/introduction/
- **Authority:** Official project site by Themesberg
- **Currency:** v4.0.1 (March 2026), actively maintained
- **Key findings:** Vanilla JS + TypeScript; data attributes API for framework-free usage; Tailwind v3→v4 migration guide; CDN-compatible
- **Credibility:** ★★★★★

### shadcn/ui Documentation
- **URL:** https://ui.shadcn.com/docs
- **Authority:** Official project site by shadcn (Vercel employee)
- **Currency:** Continuously updated, 111k GitHub stars
- **Key findings:** Code distribution platform, not installable library; CSS variable theming with semantic tokens; React + Radix UI dependency; theming pattern (CSS vars → Tailwind) is extractable
- **Credibility:** ★★★★★

### Pico CSS Documentation
- **URL:** https://picocss.com/docs
- **Authority:** Official project documentation
- **Currency:** v2.1.1 (current)
- **Key findings:** Classless CSS framework; semantic HTML styling; CSS custom properties for theming; minimal footprint
- **Credibility:** ★★★★★

### Open Props
- **URL:** https://open-props.style/
- **Authority:** Created by Adam Argyle (Google Chrome team)
- **Currency:** v1.7.20 (current)
- **Key findings:** Pure CSS custom properties design tokens; Colors, Gradients, Shadows, Typography, Sizes, etc.; framework-agnostic; MIT license
- **Credibility:** ★★★★★

### Web Awesome (successor to Shoelace)
- **URL:** https://webawesome.com/
- **Authority:** Official project site (Shoelace → Web Awesome rebrand)
- **Currency:** v3.4.0 (current), active development
- **Key findings:** 50+ web components; 11 themes; framework-agnostic via Web Components standard; free + pro tiers
- **Credibility:** ★★★★☆ (newer project, less community validation)

## Tier 2 — GitHub Repositories (High Reliability)

### DaisyUI GitHub
- **URL:** https://github.com/saadeghi/daisyui
- **Stats:** 40.6k ⭐ | 1.6k forks | 37 open issues | 2,921 commits | MIT
- **Last activity:** 3 days ago (March 2026)
- **Health indicators:** Low issue count, active commits, stable release cadence
- **Credibility:** ★★★★★

### Flowbite GitHub
- **URL:** https://github.com/themesberg/flowbite
- **Stats:** 9.2k ⭐ | 851 forks | 215 open issues | 2,782 commits | MIT
- **Last activity:** 4 days ago (March 2026)
- **Health indicators:** ⚠️ High issue count (215 vs DaisyUI's 37), actively maintained but potential backlog
- **Credibility:** ★★★★☆

### Awesome HTMX
- **URL:** https://github.com/rajasegar/awesome-htmx
- **Stats:** 2.3k ⭐ | Curated list of HTMX resources
- **Last activity:** 9 months ago
- **Credibility:** ★★★☆☆ (curated list, may be slightly outdated)

## Source Cross-Reference Matrix

| Claim | DaisyUI Docs | GitHub | Tailwind Docs | Independent |
|-------|-------------|--------|--------------|-------------|
| DaisyUI works with TW v4 | ✅ `@plugin` syntax | ✅ package.json | ✅ Plugin API | ✅ |
| DaisyUI is pure CSS | ✅ Stated | ✅ No JS in src | N/A | ✅ |
| Flowbite needs JS | ✅ Stated | ✅ JS in dist | N/A | ✅ |
| shadcn/ui requires React | ✅ Install docs | ✅ Dependencies | N/A | ✅ |
| Shoelace is sunset | ✅ Banner on site | N/A | N/A | ✅ |

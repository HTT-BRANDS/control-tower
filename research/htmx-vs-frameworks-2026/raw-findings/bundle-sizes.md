# Bundle Size Comparison (March 2026)

**Source**: bundlephobia.com, official docs, npm package data (Tier 1/2)

## Raw Library Sizes (Minified + Gzipped)

| Library | Min+Gzip | Minified | Dependencies | Notes |
|---------|----------|----------|-------------|-------|
| HTMX 2.0.8 | **17.6 kB** | 59.1 kB | 0 | Verified via Bundlephobia |
| Alpine.js 3.15.x | **~15 kB** | ~43 kB | 0 | Official docs claim; Bundlephobia errored on latest |
| React 19 + ReactDOM | **~42 kB** | ~140 kB | 1 (scheduler) | react-dom entry is 1.3kB but loads ~40kB runtime |
| Vue 3.5 | **~33 kB** | ~95 kB | 5+ | @vue/reactivity, @vue/runtime-core, etc. |
| Svelte 5 runtime | **~3 kB** | ~8 kB | 0 | Compiled — most logic is in build output |
| Solid.js 1.9 | **~7 kB** | ~23 kB | 0 | No Virtual DOM, compiled JSX |
| Qwik 1.x | **~1 kB** | ~2 kB | 0 | Initial — lazy-loads more as needed (resumability) |

## Realistic Full-Stack Bundle Sizes

These include the meta-framework, router, state management, etc. — what you'd actually ship:

| Stack | Estimated Total Bundle (gzip) | Notes |
|-------|-------------------------------|-------|
| **HTMX alone** | **17.6 kB** | Just the library, all logic is server-side |
| **HTMX + Alpine.js** | **~33 kB** | Both libraries, still no build step needed |
| **HTMX + Alpine.js + Chart.js** | **~100 kB** | Current project would be ~this |
| **React + React-DOM + Router** | **~65 kB** | Minimum viable React SPA |
| **Next.js app** | **~85-120 kB** | Framework overhead + React + hydration |
| **Vue + Vue Router + Pinia** | **~55 kB** | Standard Vue SPA stack |
| **Nuxt 4 app** | **~75-100 kB** | Framework + Vue + SSR hydration |
| **SvelteKit app** | **~25-40 kB** | Compiled, smallest full framework |
| **SolidStart app** | **~35-50 kB** | Small runtime + compiled JSX |
| **Qwik City app** | **~15-30 kB** | Initial load; lazy-loads more on interaction |

## What This Project Currently Ships

```
HTMX 1.9.12          ~16 kB gzip (loaded via CDN)
Chart.js 4.4.7        ~67 kB gzip (loaded via CDN)
navigation.bundle.js  ~26 kB raw (custom JS, not gzipped figure)
theme.css             ~68 kB raw (Tailwind compiled)
riverside.css         ~22 kB raw
```

**Total JS shipped**: ~83 kB gzipped (HTMX + Chart.js)
**Total CSS shipped**: ~90 kB raw (~18 kB gzipped estimate)

## Analysis for This Project

### Current State (HTMX 1.9.12 + vanilla JS)
- Total JS: ~83 kB gzipped
- No build step for JS (CDN loaded)
- Build step only for Tailwind CSS

### Proposed State (HTMX 2.0 + Alpine.js + Chart.js)
- Total JS: ~100 kB gzipped
- Still no build step for JS
- ~17 kB increase for Alpine.js — gains: declarative client-side state

### If Migrated to React/Next.js
- Total JS: ~150-200 kB gzipped (minimum)
- Would need: Node.js build pipeline, webpack/turbopack, SSR setup
- Chart.js would be replaced with react-chartjs-2 or recharts
- All Jinja2 templates rewritten as React components

### Key Insight
For an internal tool with 10-30 users on a corporate LAN, bundle size
differences are negligible for performance. The real cost is in **build
complexity**, **developer experience**, and **maintenance burden**.

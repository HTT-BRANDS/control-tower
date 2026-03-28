# Multi-Dimensional Analysis: Frontend Frameworks for Azure Governance Platform

**Research Date**: March 27, 2026

---

## 1. HTMX 2.0 (Upgrade from 1.9.12)

### Current State (March 2026)
- **Version**: 2.0.7 (GitHub) / 2.0.8 (npm) — stable since Jun 2024
- **Stars**: 47,720 | **Bundle**: 17.6 kB gzip | **Deps**: 0
- **Release cadence**: 7 patch releases in ~21 months (stable, not stagnant)

### What's New in 2.0
- Shadow DOM support
- Proper ESM/AMD/CJS module builds
- Extensions separated from core (modular architecture)
- Core extensions: SSE, WebSockets, idiomorph, preload, response-targets, head-support
- `selfRequestsOnly: true` by default (security improvement)
- IE support dropped (irrelevant for us)

### Security Analysis
- ✅ `selfRequestsOnly` default prevents cross-origin leakage
- ✅ CSP nonce support (already using in base.html)
- ✅ No eval() or dynamic code execution
- ⚠️ 602 open issues — normal for a popular library, but worth monitoring

### Cost Analysis
- ✅ Free, BSD-2-Clause license
- ✅ No build pipeline changes needed
- ✅ CDN-loaded, zero infrastructure cost
- ✅ Migration cost: 2-4 hours

### Implementation Complexity
- ✅ Drop-in upgrade from 1.9.12
- ✅ htmx-1-compat extension available as safety net
- ✅ No architectural changes required

### Stability
- ✅ 2.0.0 is 21 months old — proven stable
- ✅ Maintained by Big Sky Software (Carson Gross)
- ⚠️ Single primary maintainer — bus factor risk
- ✅ 47.7k stars, strong community

### Data-Heavy Table Performance
- ✅ Server-side pagination/filtering — no client-side DOM overhead
- ✅ Partial swaps mean only the table body updates
- ⚠️ No built-in virtual scrolling for 1000+ rows
- ⚠️ Sorting requires server round-trip (but acceptable for 10-30 users)

### Real-Time Updates
- ✅ Polling via `hx-trigger="every 5s"` (currently used)
- ✅ SSE core extension for push-based updates
- ✅ WebSocket core extension for bi-directional communication
- Server-side events work naturally with FastAPI's `StreamingResponse`

### Limitations
- ❌ No client-side state management
- ❌ Complex client-side interactions require vanilla JS
- ❌ No reactive data binding
- ❌ Chart interactions (tooltips, zoom) can't be driven by HTMX

---

## 2. HTMX + Alpine.js (Recommended Approach)

### Why This Combo Works
HTMX handles **server communication** (AJAX, partial updates, SSE), while Alpine.js
handles **client-side interactivity** (dropdowns, modals, tabs, form validation,
countdown timers). They complement each other perfectly:

```
┌─────────────────────────────────────────────────┐
│  Browser                                        │
│  ┌──────────────┐  ┌────────────────────────┐  │
│  │   HTMX       │  │    Alpine.js           │  │
│  │  • hx-get    │  │  • x-data (state)      │  │
│  │  • hx-post   │  │  • x-show (toggle)     │  │
│  │  • hx-swap   │  │  • x-on (events)       │  │
│  │  • hx-trigger│  │  • x-for (loops)       │  │
│  │  • SSE/WS    │  │  • x-transition        │  │
│  └──────┬───────┘  └────────────────────────┘  │
│         │                                       │
│         ▼                                       │
│  ┌──────────────┐                               │
│  │ FastAPI +    │                               │
│  │ Jinja2       │                               │
│  └──────────────┘                               │
└─────────────────────────────────────────────────┘
```

### What Alpine.js Adds Over Vanilla JS

| Capability | Vanilla JS (current) | Alpine.js |
|------------|---------------------|-----------|
| Toggle visibility | `element.classList.toggle()` | `x-show="isOpen"` |
| State management | Manual DOM manipulation | `x-data="{ count: 0 }"` |
| Event handling | `addEventListener()` | `@click="count++"` |
| Conditional rendering | `if/else + innerHTML` | `x-if="condition"` |
| List rendering | Manual loop + appendChild | `x-for="item in items"` |
| Transitions | CSS + JS classes | `x-transition` built-in |
| Two-way binding | Manual input/change listeners | `x-model="value"` |
| Watchers | MutationObserver | `x-effect` |

### Already In Use (Almost)
The project **already uses Alpine.js syntax** in `riverside.html`:
```html
<div class="space-y-6" x-data="riversideDashboard()">
```
But Alpine.js is **not loaded** in `base.html`. This `x-data` attribute is inert.
Adding Alpine.js would immediately activate this code.

### alpine-morph Extension
When HTMX swaps HTML that contains Alpine.js components, Alpine state is normally
lost. The `alpine-morph` extension uses Alpine's morph plugin to preserve state
during HTMX swaps. This is essential for combining the two libraries.

### Combined Bundle Size
- HTMX 2.0: 17.6 kB gzip
- Alpine.js 3.15: ~15 kB gzip
- **Total: ~33 kB gzip** — less than React-DOM alone

### Use Cases in This Project

| Feature | Current Approach | With Alpine.js |
|---------|-----------------|----------------|
| Riverside countdown | Vanilla JS + setInterval | `x-data` + `x-init` with Alpine |
| Dark mode toggle | darkMode.js (custom) | `x-data="{ dark: false }"` |
| Mobile menu | mobileMenu.js (custom) | `@click="open = !open"` inline |
| Table sorting (client) | Not available | `x-data` + computed sort |
| Filter dropdowns | Not available | `x-show` + `x-model` |
| Confirmation dialogs | confirmDialog.js (custom) | `x-data` + `x-show` |
| Tab switching | Not available | `x-data="{ tab: 'overview' }"` |
| Toast notifications | toast.js (custom) | `x-data` + `x-transition` |

### Security
- ✅ Alpine.js respects CSP — can use `Alpine.directive()` instead of inline expressions
- ⚠️ Default inline expressions work with `nonce` attribute (already using)
- ✅ No eval() in strict mode
- ✅ MIT license

### Estimated Integration Effort
- Add Alpine.js CDN to `base.html`: 30 minutes
- Add `alpine-morph` extension: 30 minutes
- Migrate riverside.html `x-data` to work: 2 hours
- Replace darkMode.js + mobileMenu.js: 4 hours
- **Total: ~1 day**

---

## 3. React 19 / Next.js 16

### Current State (March 2026)
- **React**: 19.2.4 (244k stars) — mature, dominant ecosystem
- **Next.js**: 16.2.1 (139k stars) — latest stable, extremely active

### Why It's Overkill for This Project

1. **Architecture Mismatch**: React requires a complete rewrite of all Jinja2 templates
   into JSX components. This is not incremental — it's a full rebuild.

2. **Build Pipeline**: Requires Node.js build tooling (webpack/turbopack), which doesn't
   exist in the current Python-centric workflow.

3. **API Rewrite**: FastAPI currently renders HTML directly. With React/Next.js, you'd
   need to either:
   - Run Next.js as a separate frontend (→ CORS, auth complexity, deployment complexity)
   - Use Next.js API routes (→ abandon FastAPI entirely)

4. **For 10-30 Users**: React's Virtual DOM diffing, client-side state management, and
   hydration overhead provide zero benefit for such a small user base.

### Migration Cost Assessment
- **Effort**: 3-6 months full rewrite
- **Skills required**: React, JSX, Next.js App Router, Server Components
- **Infrastructure changes**: Node.js server, build pipeline, separate deployment
- **Risk**: Complete feature freeze during migration

### When React/Next.js Would Make Sense
- If user count grew to 1000+ and needed offline/PWA capabilities
- If multiple teams needed to develop independent UI features
- If real-time collaborative editing was required
- If the team was primarily JavaScript/TypeScript developers

### Data Table Libraries
- `@tanstack/react-table`: Excellent for large datasets (virtual scrolling, pagination)
- `react-data-grid`: Spreadsheet-like with 100k+ row support
- `ag-grid-react`: Enterprise-grade (but expensive license: $1,490/dev)

### Real-Time Updates
- React Query / TanStack Query: Automatic polling and cache invalidation
- Socket.io / ws: WebSocket libraries
- Server-Sent Events: Via EventSource API or libraries
- React Server Components: Streaming updates from server

---

## 4. Vue 3.5 / Nuxt 4.4

### Current State (March 2026)
- **Vue**: 3.5.31 (53.3k stars) — very stable, released 3 days ago
- **Nuxt**: 4.4.2 (59.9k stars) — active development

### Comparison to React for This Project

Vue is often considered the "middle ground" — easier to learn than React, with better
built-in features (transitions, v-model, computed properties).

**Incremental adoption advantage**: Vue can be mounted on existing HTML pages via CDN,
similar to Alpine.js. This is its key differentiator from React for migration purposes.

```html
<!-- Vue can be added incrementally to a Jinja2 page -->
<div id="app">
  <button @click="count++">{{ count }}</button>
</div>
<script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
<script>
  Vue.createApp({ data: () => ({ count: 0 }) }).mount('#app')
</script>
```

However, this approach essentially makes Vue do what Alpine.js does — but at 33 kB
gzipped (2x the size of Alpine.js) with more complexity.

### Nuxt Server Components
Nuxt 4's server components can render on the server and stream HTML — conceptually
similar to what HTMX + Jinja2 already does. Using Nuxt to achieve what we already
have would be circular.

### Migration Cost
- **Effort**: 2-4 months (less than React due to CDN incremental adoption)
- **Skills required**: Vue 3 Composition API, Nuxt 4, TypeScript
- **Risk**: Moderate — could adopt incrementally

### Verdict
Vue is a good framework, but for this project, Alpine.js gives us 80% of Vue's
client-side benefits at 45% of the bundle size, with zero architectural changes.

---

## 5. Svelte 5 / SvelteKit 2

### Current State (March 2026)
- **Svelte**: 5.55.0 (86.1k stars) — very active, Svelte 5 "runes" system
- **SvelteKit**: 2.x — meta-framework with SSR

### Svelte 5 Runes System
```svelte
<script>
  let count = $state(0);        // reactive state
  let doubled = $derived(count * 2);  // computed
  $effect(() => {               // side effects
    console.log(count);
  });
</script>
```

### Advantages for Data-Heavy Tools
- **Compiled**: Svelte compiles to vanilla JS — smallest runtime (~3 kB gzip)
- **No Virtual DOM**: Direct DOM updates — excellent for large tables
- **Built-in transitions**: Animation system built into the language
- **Stores**: Simple reactive state management

### Why It's Still Not Right for This Project
1. **Full rewrite required**: Can't incrementally adopt Svelte in Jinja2 templates
2. **Different paradigm**: `.svelte` single-file components ≠ Jinja2 templates
3. **Build tooling**: Requires Vite + SvelteKit build pipeline
4. **Small ecosystem for enterprise**: Fewer enterprise dashboard component libraries
   compared to React or Vue

### If Starting Fresh
Svelte/SvelteKit would be a strong contender for a greenfield project. Its compiled
approach is ideal for data-heavy dashboards. But migrating an existing HTMX+Jinja2
app to SvelteKit provides insufficient ROI.

---

## 6. Solid.js / SolidStart

### Current State (March 2026)
- **Solid.js**: 1.9.12 (35.4k stars) — fine-grained reactivity without Virtual DOM
- **Last major release**: v1.9.0 on Sep 24, 2024 (18 months ago!)
- **SolidStart**: Meta-framework, still evolving

### Fine-Grained Reactivity for Data Tables
Solid.js excels at updating individual cells in a data table without re-rendering the
entire table. This is its theoretical advantage for data-heavy applications.

```jsx
// Solid.js — only the changed cell updates
const [data, setData] = createSignal(tableData);
<For each={data()}>
  {(row) => <tr><td>{row.name}</td><td>{row.value}</td></tr>}
</For>
```

### Concerns
- ⚠️ **Release cadence**: 18 months since last major release — moving toward 2.0 but
  slowly. This is a maturity/sustainability concern.
- ⚠️ **Ecosystem size**: 35k stars is healthy but ecosystem (component libraries,
  enterprise tools) is much smaller than React/Vue/Svelte
- ⚠️ **SolidStart maturity**: The meta-framework is less mature than Next.js/Nuxt/SvelteKit
- ❌ **Same migration problem**: Full rewrite from Jinja2 required

### Verdict
Solid.js has the best theoretical performance for data tables, but ecosystem maturity
and release cadence are concerns. Not recommended for migration from HTMX+Jinja2.

---

## 7. Qwik / Qwik City

### Current State (March 2026)
- **Qwik**: 1.19.2 (22k stars) — resumability-focused framework
- **Install size**: 28.2 MB (largest of all options)

### Resumability Concept
Qwik's key innovation is "resumability" — the ability to serialize application state
into HTML and resume it on the client without hydration. This means:
- Near-zero JavaScript on initial load (~1 kB)
- JavaScript loads lazily on user interaction
- No hydration waterfall

### Relevance to Internal Tool
**Low relevance**. Resumability optimizes for:
- Cold starts on slow networks (not applicable — corporate LAN)
- First-contentful-paint for SEO (not applicable — internal tool)
- Large public-facing sites with many visitors (not applicable — 10-30 users)

### Concerns
- ⚠️ Smallest ecosystem (22k stars)
- ⚠️ Largest install size (28.2 MB) — suggests complexity
- ⚠️ Qwik 2.0 in development — potential instability
- ⚠️ Novel mental model — steep learning curve
- ❌ Very few enterprise dashboard examples

### Verdict
Qwik solves a problem (initial load performance) that doesn't exist for an internal
tool. Not recommended.

---

## Cross-Cutting Comparisons

### Real-Time Update Strategies

| Framework | Polling | SSE | WebSocket | Best For This Project |
|-----------|---------|-----|-----------|----------------------|
| HTMX | `hx-trigger="every Xs"` | SSE extension (core) | WS extension (core) | SSE for sync status |
| Alpine.js | `x-init` + setInterval | EventSource API | WebSocket API | Complements HTMX |
| React | TanStack Query refetchInterval | EventSource | socket.io/ws | Over-engineered |
| Vue | Composable + setInterval | useEventSource | useWebSocket | Similar to React |
| Svelte | Stores + setInterval | EventSource | WebSocket | Clean but requires rewrite |
| Solid | createResource refetch | EventSource | WebSocket | Good but immature |
| Qwik | useTask$ | Not well documented | Limited | Too novel |

### Multi-Tenant Theming Compatibility

| Framework | CSS Variables | Dynamic Theme Injection | Existing Theme System Compat |
|-----------|-------------|------------------------|------------------------------|
| HTMX+Alpine | ✅ Native CSS | ✅ Jinja2 injects per request | ✅ Perfect — no changes needed |
| React/Next | ✅ CSS-in-JS or variables | ⚠️ Requires React context/provider | ❌ Rewrite theme system |
| Vue/Nuxt | ✅ CSS variables | ⚠️ Requires composable/provide | ❌ Rewrite theme system |
| Svelte/Kit | ✅ CSS variables | ✅ Good scoped CSS support | ❌ Rewrite theme system |
| Solid/Start | ✅ CSS variables | ⚠️ Requires context | ❌ Rewrite theme system |
| Qwik | ✅ CSS variables | ⚠️ Requires useContext | ❌ Rewrite theme system |

### Developer Experience

| Aspect | HTMX+Alpine | React/Next | Vue/Nuxt | Svelte/Kit |
|--------|------------|-----------|---------|-----------|
| Learning curve (Python dev) | ⭐⭐⭐⭐⭐ Easy | ⭐⭐ Steep | ⭐⭐⭐ Moderate | ⭐⭐⭐½ Moderate |
| TypeScript support | ⚠️ Limited | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Hot reload | N/A (server) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Debugging | Browser DevTools | React DevTools | Vue DevTools | Svelte DevTools |
| Testing | pytest + Playwright | Jest/Vitest + RTL | Vitest + Vue Test Utils | Vitest + @testing-library |
| Full-stack ownership | ⭐⭐⭐⭐⭐ | ⭐⭐ (split) | ⭐⭐½ (split) | ⭐⭐⭐ (split) |

---

## The Core Question: Does SPA Complexity Pay for Itself?

### For 10-30 Internal Users: **No.**

The mathematical case:

| Factor | SPA Benefit | HTMX+Alpine Alternative | Winner |
|--------|-----------|------------------------|--------|
| First load speed | SSR+hydration ~200ms | Server-rendered HTML ~150ms | HTMX |
| Subsequent navigation | Client-side routing ~50ms | hx-boost partial swap ~100ms | SPA (marginal) |
| Large table rendering | Virtual scrolling | Server-side pagination | Depends on scale |
| Form validation | Instant client-side | Server round-trip ~50ms on LAN | SPA (marginal) |
| Offline capability | Service workers + cache | Not available | SPA (if needed) |
| Build/deploy complexity | Node.js + CDN + API | Python only | HTMX |
| Maintenance burden | npm audit, version upgrades | Minimal dependencies | HTMX |
| Developer productivity | Component reuse | Template inheritance | HTMX (for Python team) |

**For 10-30 users on a corporate LAN, the 50ms navigation speed difference and client-side
validation are not worth 3-6 months of migration and ongoing framework maintenance.**

### When to Reconsider
- User count exceeds 500+ external users
- Offline/PWA requirements emerge
- Real-time collaborative editing is needed
- The team hires dedicated frontend developers
- The application needs to become a public-facing product

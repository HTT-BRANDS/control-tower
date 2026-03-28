# Project-Specific Recommendations

**Project**: Azure Governance Platform
**Research Date**: March 27, 2026

---

## Prioritized Action Plan

### 🔴 Priority 1: Upgrade HTMX 1.9.12 → 2.0.7 (This Sprint)

**Effort**: 2-4 hours | **Risk**: Low | **Impact**: Security + feature enablement

#### Steps

1. **Update CDN reference** in `app/templates/base.html`:
   ```html
   <!-- Replace this: -->
   <script src="https://unpkg.com/htmx.org@1.9.12"
     integrity="sha384-ujb1lZYygJmzgSwoxRggbCHcjc0rB2XoQrxeTUQyRjrOnlCoYta87iKBWq3EsdM2"
     crossorigin="anonymous"
     nonce="{{ request.state.csp_nonce }}"></script>

   <!-- With this: -->
   <script src="https://unpkg.com/htmx.org@2.0.7/dist/htmx.min.js"
     integrity="sha384-[NEW_HASH]"
     crossorigin="anonymous"
     nonce="{{ request.state.csp_nonce }}"></script>
   ```

2. **Scan for hx-on attributes**:
   ```bash
   grep -rn "hx-on=" app/templates/ --include="*.html"
   ```
   Convert any matches to `hx-on:event-name=""` syntax.

3. **Update htmx-config meta tag** if needed:
   ```html
   <meta name="htmx-config" content='{
     "inlineScriptNonce":"{{ request.state.csp_nonce }}",
     "scrollBehavior":"smooth"
   }'>
   ```

4. **Run full test suite**:
   ```bash
   pytest tests/e2e/ -v
   pytest tests/integration/test_frontend_e2e.py -v
   ```

5. **Manual smoke test** all HTMX interactions (see migration guide for checklist)

#### Rollback Plan
If issues arise, load `htmx-1-compat` extension alongside HTMX 2.0 to restore 1.x behavior:
```html
<script src="https://unpkg.com/htmx-ext-htmx-1-compat@2.0.0/htmx-1-compat.js"></script>
```

---

### 🟡 Priority 2: Add Alpine.js 3.15.x (Next Sprint)

**Effort**: 1-2 days | **Risk**: Low | **Impact**: Significantly improved client-side DX

#### Steps

1. **Add Alpine.js to base.html** (after HTMX, before closing body):
   ```html
   <!-- Alpine.js -->
   <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.15.9/dist/cdn.min.js"
     nonce="{{ request.state.csp_nonce }}"></script>
   ```

2. **Add alpine-morph extension** (preserves Alpine state during HTMX swaps):
   ```html
   <script src="https://cdn.jsdelivr.net/npm/@alpinejs/morph@3.x.x/dist/cdn.min.js"
     nonce="{{ request.state.csp_nonce }}"></script>
   ```

3. **Activate riverside.html** — the `x-data="riversideDashboard()"` already exists.
   Create the Alpine component:
   ```html
   <script nonce="{{ request.state.csp_nonce }}">
   document.addEventListener('alpine:init', () => {
     Alpine.data('riversideDashboard', () => ({
       activeTab: 'overview',
       countdownDays: '--',
       // ... existing countdown logic from vanilla JS
     }));
   });
   </script>
   ```

4. **Replace custom JS modules** with Alpine.js equivalents:

   | Current File | Size | Alpine.js Replacement |
   |-------------|------|----------------------|
   | `darkMode.js` | 1.4 KB | `x-data` on `<html>` element |
   | `mobileMenu.js` | 661 B | `@click` + `x-show` inline |
   | `confirmDialog.js` | 5.3 KB | `x-data` + `x-show` + `@click` |
   | `toast.js` | 7.0 KB | `x-data` + `x-transition` + Alpine store |
   | **Total replaced** | **14.4 KB** | **~0 KB** (inline in HTML) |

5. **Update CSP headers** if needed to allow Alpine.js evaluation.

#### Expected Benefits
- Eliminate 4 custom JS files (~14 KB)
- Declarative client-side state in templates (no separate JS files)
- Better developer experience for toggles, tabs, dropdowns
- Smooth transitions/animations via `x-transition`

---

### 🟢 Priority 3: Add HTMX SSE Extension (Future Sprint)

**Effort**: 1-2 days | **Risk**: Low | **Impact**: Replace polling with push-based updates

#### Current State
The project uses HTMX polling for real-time updates:
```html
hx-trigger="load, every 60s"  <!-- Riverside badge -->
```

#### Improvement
Replace polling with Server-Sent Events for sync status, compliance updates:

1. **Add SSE extension to base.html**:
   ```html
   <script src="https://unpkg.com/htmx-ext-sse@2.2.0/sse.js"
     nonce="{{ request.state.csp_nonce }}"></script>
   ```

2. **Add SSE endpoint to FastAPI**:
   ```python
   @router.get("/api/v1/events/sync-status")
   async def sync_status_stream(request: Request):
       async def event_generator():
           while True:
               status = await get_sync_status()
               yield f"event: sync-update\ndata: {render_partial(status)}\n\n"
               await asyncio.sleep(5)
       return StreamingResponse(event_generator(), media_type="text/event-stream")
   ```

3. **Update template to use SSE**:
   ```html
   <div hx-ext="sse" sse-connect="/api/v1/events/sync-status">
     <div sse-swap="sync-update">
       <!-- Sync status updates here automatically -->
     </div>
   </div>
   ```

#### Benefits
- No wasted requests when nothing changes
- Instant updates when sync completes
- Lower server load (1 connection vs. repeated polling)
- Better UX for the sync dashboard

---

### 🔵 Priority 4: Enhance Data Tables (Future)

**Effort**: 2-3 days | **Risk**: Low | **Impact**: Better UX for large datasets

#### Current Approach
Tables are server-rendered in Jinja2 with full page data. For hundreds of rows,
this works but lacks sorting/filtering interactivity.

#### Recommended Enhancement: HTMX + Alpine.js Hybrid Tables

```html
<div x-data="dataTable()" hx-get="/api/v1/resources?page=1" hx-trigger="load"
     hx-target="#table-body" hx-swap="innerHTML">

  <!-- Client-side filter (Alpine.js) -->
  <input x-model="searchTerm" @input.debounce.300ms="$dispatch('filter-change')"
         placeholder="Filter resources...">

  <!-- Sort headers (HTMX — server-side sort) -->
  <table>
    <thead>
      <tr>
        <th hx-get="/api/v1/resources?sort=name&page=1"
            hx-target="#table-body" hx-swap="innerHTML"
            class="cursor-pointer">Name ↕</th>
        <th hx-get="/api/v1/resources?sort=cost&page=1"
            hx-target="#table-body" hx-swap="innerHTML"
            class="cursor-pointer">Cost ↕</th>
      </tr>
    </thead>
    <tbody id="table-body">
      <!-- Server-rendered rows swapped in by HTMX -->
    </tbody>
  </table>

  <!-- Pagination (HTMX) -->
  <div id="pagination"
       hx-get="/api/v1/resources?page=2"
       hx-target="#table-body" hx-swap="innerHTML">
    Next →
  </div>
</div>
```

This gives:
- **Server-side sorting** (HTMX) — correct for hundreds of rows
- **Client-side filtering** (Alpine.js) — instant for visible page
- **Server-side pagination** (HTMX) — scales to thousands of rows
- **No virtual scrolling needed** — pagination keeps DOM small

---

## What NOT to Do

### ❌ Don't Migrate to a SPA Framework

For this project at this scale, migrating to React/Next.js, Vue/Nuxt, Svelte/SvelteKit,
Solid.js, or Qwik would:
- Cost 3-6 months of development time
- Require hiring or training frontend specialists
- Introduce Node.js build/deployment complexity
- Break the existing multi-tenant CSS variable theming system
- Provide minimal UX improvement for 10-30 internal users

### ❌ Don't Add a Build Step for JavaScript

The current approach (CDN-loaded HTMX + vanilla JS) is a feature, not a limitation.
Adding webpack/Vite/turbopack to the project would:
- Complicate the Docker build
- Add Node.js as a runtime dependency
- Create npm audit maintenance burden
- Slow down development iteration

### ❌ Don't Over-Engineer Real-Time Updates

For 10-30 users, polling every 30-60 seconds is perfectly acceptable. SSE is a nice
improvement but WebSockets are overkill unless collaborative editing is needed.

---

## Decision Review Triggers

Revisit this analysis if any of these conditions change:

| Trigger | Threshold | Next Step |
|---------|-----------|-----------|
| User count growth | >100 concurrent users | Re-evaluate client-side rendering |
| Offline requirements | PWA needed | Consider SPA with service workers |
| Team composition | >2 dedicated frontend devs | Consider React or Svelte |
| Real-time collaboration | Multiple users editing same data | Consider WebSockets + framework |
| External-facing | Tool becomes customer-facing | Re-evaluate full framework |
| Performance complaints | Page loads >3 seconds consistently | Profile and optimize |

---

## Cost Summary

| Approach | Estimated Effort | Estimated Cost | ROI |
|----------|-----------------|----------------|-----|
| HTMX 2.0 upgrade | 2-4 hours | ~$200 | ⭐⭐⭐⭐⭐ Immediate |
| Add Alpine.js | 1-2 days | ~$1,500 | ⭐⭐⭐⭐⭐ High |
| Add SSE extension | 1-2 days | ~$1,500 | ⭐⭐⭐⭐ Good |
| Enhanced data tables | 2-3 days | ~$2,500 | ⭐⭐⭐⭐ Good |
| **Total recommended** | **~1 week** | **~$5,700** | **⭐⭐⭐⭐⭐** |
| React/Next.js migration | 3-6 months | ~$75,000-150,000 | ⭐ Poor |
| Vue/Nuxt migration | 2-4 months | ~$50,000-100,000 | ⭐½ Poor |
| Svelte/SvelteKit migration | 2-4 months | ~$50,000-100,000 | ⭐½ Poor |

The recommended path delivers 90% of the UX improvement at 4% of the cost.

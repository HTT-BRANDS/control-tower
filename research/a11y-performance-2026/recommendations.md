# Project-Specific Recommendations

## Priority Framework
- 🔴 **P0 — Critical**: Legal/compliance risk, do within 1 sprint
- 🟡 **P1 — High**: Significant quality improvement, do within 2 sprints
- 🟢 **P2 — Medium**: Nice to have, schedule when convenient
- ⚪ **P3 — Low**: Track but deprioritize

---

## Recommendation 1: axe-playwright-python CI Pipeline

**Priority**: 🔴 P0
**Effort**: ~2 hours
**Impact**: Automated WCAG 2.2 regression testing on every PR

### What to Do

1. **Install dependency:**
   ```bash
   uv add --dev axe-playwright-python
   ```

2. **Create test file:**
   ```python
   # tests/accessibility/test_wcag_regression.py
   import pytest
   import json
   from pathlib import Path
   from playwright.sync_api import Page
   from axe_playwright_python.sync_playwright import Axe
   
   axe = Axe()
   
   PAGES_REQUIRING_AUTH = [
       ("/dashboard", "Dashboard"),
       ("/sync-dashboard", "Sync Dashboard"),
       ("/costs", "Costs"),
       ("/compliance", "Compliance"),
       ("/resources", "Resources"),
       ("/identity", "Identity"),
       ("/riverside", "Riverside"),
   ]
   
   PAGES_NO_AUTH = [
       ("/login", "Login"),
   ]
   
   @pytest.mark.e2e
   @pytest.mark.parametrize("path,name", PAGES_NO_AUTH)
   def test_public_pages_a11y(page: Page, path, name):
       page.goto(f"http://localhost:8000{path}")
       page.wait_for_load_state("networkidle")
       results = axe.run(page)
       _save_report(name, results)
       assert results.violations_count == 0, _format_violations(name, path, results)
   
   
   def _save_report(name, results):
       report_dir = Path("tests/accessibility/reports")
       report_dir.mkdir(exist_ok=True)
       slug = name.lower().replace(" ", "-")
       (report_dir / f"{slug}.json").write_text(
           json.dumps(results.response, indent=2)
       )
   
   
   def _format_violations(name, path, results):
       violations = results.response.get("violations", [])
       lines = [f"\n{name} ({path}): {len(violations)} violations:"]
       for v in violations:
           lines.append(
               f"  [{v['impact']}] {v['id']}: {v['description']} "
               f"({len(v['nodes'])} elements)"
           )
       return "\n".join(lines)
   ```

3. **Update pyproject.toml markers:**
   ```toml
   [tool.pytest.ini_options]
   markers = [
       "a11y: marks tests as accessibility tests",
   ]
   ```

4. **Run:**
   ```bash
   # Start app first
   uvicorn app.main:app --port 8000 &
   
   # Run a11y tests
   pytest tests/accessibility/test_wcag_regression.py -v
   ```

### What This Catches
- All axe-core 4.11.1 rules for WCAG 2.0/2.1/2.2 A+AA
- Color contrast (including oklch/oklab)
- Missing labels, alt text, button names
- ARIA violations, duplicate IDs
- Heading hierarchy, landmark regions
- Keyboard traps (basic detection)

### What This Misses (Needs Topic 3 Manual Testing)
- Focus management quality
- Cognitive accessibility
- Screen reader experience
- Dynamic content behavior beyond initial load

---

## Recommendation 2: WCAG 2.2 Manual Testing Checklist

**Priority**: 🔴 P0
**Effort**: ~1 hour to set up, 2-3 hours per quarterly audit
**Impact**: Covers the 60-70% of issues automation misses

### Manual Testing Checklist Template

Create this file and assign ownership:

```markdown
# WCAG 2.2 AA Manual Testing Checklist
Date: ____________________
Tester: __________________
Browser: _________________
Screen Reader: ___________

## 1. Focus Not Obscured (2.4.11 AA)
- [ ] Tab through /dashboard — focus never hidden behind nav bar
- [ ] Tab through /sync-dashboard — focus visible during polling updates
- [ ] Tab through /costs — focus visible with sticky table headers
- [ ] Tab through /compliance — focus visible in rule editor
- [ ] Tab through /resources — focus visible in data tables
- [ ] Tab through /identity — focus visible in RBAC panels
- [ ] Tab through /riverside — focus visible in all sections
- [ ] Mobile menu doesn't trap focus behind overlay
Notes: _______________

## 2. Target Size (2.5.8 AA — 24x24px minimum)
- [ ] Run AccessibilityTester.checkTouchTargets() on each page
- [ ] Review violations — exclude inline text links (exempt)
- [ ] Verify icon-only buttons meet 24x24px
- [ ] Check nav links on mobile
Notes: _______________

## 3. Dragging Movements (2.5.7 AA)
- [ ] No drag-only interactions exist
- [ ] Any sortable lists have button alternatives
- [ ] Chart interactions don't require drag
Notes: _______________

## 4. Consistent Help (3.2.6 A)
- [ ] Help/docs links appear in same position across all pages
- [ ] Footer content order is consistent
- [ ] Error recovery guidance is consistent
Notes: _______________

## 5. Redundant Entry (3.3.7 A)
- [ ] Multi-step forms auto-populate previously entered data
- [ ] Tenant selection persists across page navigations
- [ ] Filter settings don't require re-entry
Notes: _______________

## 6. Accessible Authentication (3.3.8 AA)
- [ ] Login uses standard username/password (exempt) ✅
- [ ] No CAPTCHA or cognitive test required
- [ ] If MFA added: supports paste, authenticator apps, passkeys
Notes: _______________

## 7. Focus Appearance (2.4.13 AAA — best practice)
- [ ] Focus indicators visible on all interactive elements
- [ ] Focus ring has sufficient contrast against backgrounds
- [ ] Focus ring visible in both light and dark mode
Notes: _______________

## Overall Assessment
- Total issues found: _____
- Critical (blocks users): _____
- Major (significant barrier): _____
- Minor (inconvenience): _____
- Passed all criteria: [ ] Yes [ ] No
```

### Schedule
- **Monthly**: Quick 30-min keyboard walkthrough by any developer
- **Quarterly**: Full checklist by designated a11y champion (rotate)
- **Per release**: Run `AccessibilityTester.runAllChecks()` on changed pages

---

## Recommendation 3: Replace Sync Dashboard Polling with SSE

**Priority**: 🟡 P1
**Effort**: ~4-6 hours
**Impact**: Eliminates 360 req/min (at 30 users), enables real-time updates

### Implementation Steps

1. **Install sse-starlette:**
   ```bash
   uv add sse-starlette
   ```

2. **Create SSE endpoint:**
   ```python
   # app/api/v1/sync_events.py
   from fastapi import APIRouter, Request, Depends
   from sse_starlette import EventSourceResponse
   from app.core.auth import get_current_user
   import asyncio
   
   router = APIRouter()
   
   @router.get("/api/v1/sync-events")
   async def sync_events(request: Request, user=Depends(get_current_user)):
       async def event_generator():
           last_status = None
           while True:
               if await request.is_disconnected():
                   break
               
               status = await get_current_sync_status()
               status_html = render_sync_partial(status)
               
               # Only send if changed
               if status_html != last_status:
                   yield {
                       "event": "sync-update",
                       "data": status_html,
                   }
                   last_status = status_html
               
               await asyncio.sleep(2)
       
       return EventSourceResponse(
           event_generator(),
           ping=15,  # Keep-alive every 15s
       )
   ```

3. **Add HTMX SSE extension to base.html:**
   ```html
   <!-- After htmx.org script -->
   <script src="https://unpkg.com/htmx-ext-sse@2.2.2/sse.js"
           nonce="{{ request.state.csp_nonce }}"></script>
   ```

4. **Update sync-dashboard template:**
   ```html
   <!-- Replace: hx-trigger="every 5s" -->
   <!-- With: SSE connection -->
   <div hx-ext="sse" 
        sse-connect="/api/v1/sync-events"
        aria-live="polite">
       <div sse-swap="sync-update" hx-swap="innerHTML settle:150ms">
           {% include 'partials/sync_status.html' %}
       </div>
   </div>
   ```

5. **Add aria-live for screen readers** (already shown above — `aria-live="polite"` on the SSE container so screen readers announce updates).

### Fallback
Keep polling as a fallback for older browsers or SSE connection failures:
```html
<div hx-ext="sse" sse-connect="/api/v1/sync-events"
     hx-get="/sync-dashboard/status" hx-trigger="every 30s">
    <!-- SSE updates normally; polling every 30s as backup -->
</div>
```

---

## Recommendation 4: Accessible Responsive Tables

**Priority**: 🟡 P1
**Effort**: ~1 hour (global change)
**Impact**: WCAG 1.4.10 Reflow + keyboard accessibility for all data tables

### Implementation

1. **Create a Jinja2 macro:**
   ```html
   {# app/templates/macros/accessible_table.html #}
   {% macro responsive_table(caption_id, caption_text) %}
   <div role="region" 
        aria-labelledby="{{ caption_id }}" 
        tabindex="0"
        class="overflow-auto rounded-lg focus:outline-2 focus:outline-offset-2"
        style="outline-color: var(--brand-primary-100);">
       <table class="min-w-full">
           <caption id="{{ caption_id }}" class="sr-only">
               {{ caption_text }}
           </caption>
           {{ caller() }}
       </table>
   </div>
   {% endmacro %}
   ```

2. **Use in templates:**
   ```html
   {% from 'macros/accessible_table.html' import responsive_table %}
   
   {% call responsive_table('resources-table', 'Azure Resources') %}
   <thead>
       <tr>
           <th>Name</th>
           <th>Type</th>
           <th>Resource Group</th>
       </tr>
   </thead>
   <tbody>
       {% for r in resources %}
       <tr>
           <td>{{ r.name }}</td>
           <td>{{ r.type }}</td>
           <td>{{ r.resource_group }}</td>
       </tr>
       {% endfor %}
   </tbody>
   {% endcall %}
   ```

3. **Add CSS to accessibility.css** (or theme.src.css):
   ```css
   /* Accessible responsive table wrapper */
   [role="region"][aria-labelledby][tabindex] {
       overflow: auto;
   }
   [role="region"][aria-labelledby][tabindex]:focus {
       outline: 0.15em solid var(--brand-primary-100, #1e3a5f);
   }
   ```

---

## Recommendation 5: HTMX Focus Management After Swaps

**Priority**: 🟡 P1
**Effort**: ~2 hours
**Impact**: Screen reader users can follow HTMX dynamic content updates

### Implementation

Add to `app/static/js/accessibility.js`:

```javascript
/**
 * HTMX Focus Management for Accessibility
 * Ensures screen reader users can follow dynamic content updates
 */
(function() {
    'use strict';
    
    // After HTMX swaps content, manage focus for screen readers
    document.addEventListener('htmx:afterSwap', function(event) {
        const target = event.detail.target;
        
        // Skip if this is a minor update (badges, indicators)
        if (target.classList.contains('htmx-indicator') ||
            target.id === 'riverside-badge' ||
            target.id === 'nav-loading-indicator') {
            return;
        }
        
        // For main content area swaps, focus the content
        if (target.id === 'main-content' || target.closest('#main-content')) {
            const heading = target.querySelector('h1, h2, h3');
            if (heading) {
                if (!heading.hasAttribute('tabindex')) {
                    heading.setAttribute('tabindex', '-1');
                }
                heading.focus({ preventScroll: false });
            }
        }
        
        // Announce the update via aria-live region
        const announcer = document.getElementById('page-announcer');
        if (announcer && target.id !== 'page-announcer') {
            const heading = target.querySelector('h1, h2, h3');
            const text = heading ? heading.textContent.trim() : 'Content updated';
            
            // Clear then set to retrigger announcement
            announcer.textContent = '';
            requestAnimationFrame(() => {
                announcer.textContent = text;
            });
        }
    });
    
    // Set aria-busy during HTMX requests
    document.addEventListener('htmx:beforeRequest', function(event) {
        const target = event.detail.target;
        if (target && target.id === 'main-content') {
            target.setAttribute('aria-busy', 'true');
        }
    });
    
    document.addEventListener('htmx:afterRequest', function(event) {
        const target = event.detail.target;
        if (target && target.id === 'main-content') {
            target.removeAttribute('aria-busy');
        }
    });
})();
```

---

## Recommendation 6: Skeleton Screens for Dashboard

**Priority**: 🟢 P2
**Effort**: ~3 hours
**Impact**: Improved perceived performance for dashboard loads

### Implementation Pattern for Dashboard

```html
{# app/templates/pages/dashboard_skeleton.html #}
<div id="dashboard-content"
     hx-get="/dashboard/content"
     hx-trigger="load"
     hx-swap="innerHTML settle:200ms"
     aria-busy="true"
     hx-on::after-swap="this.removeAttribute('aria-busy')">
    
    <!-- Accessible loading announcement -->
    <div class="sr-only" aria-live="polite">Loading dashboard data...</div>
    
    <!-- Visual skeleton -->
    <div class="animate-pulse space-y-6" aria-hidden="true">
        <!-- KPI cards skeleton -->
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {% for _ in range(4) %}
            <div class="h-28 bg-surface-secondary rounded-lg border"
                 style="border-color: var(--border-color);"></div>
            {% endfor %}
        </div>
        
        <!-- Chart skeleton -->
        <div class="h-72 bg-surface-secondary rounded-lg border"
             style="border-color: var(--border-color);"></div>
        
        <!-- Table skeleton -->
        <div class="space-y-2">
            {% for _ in range(5) %}
            <div class="h-12 bg-surface-secondary rounded"
                 style="border-color: var(--border-color);"></div>
            {% endfor %}
        </div>
    </div>
</div>
```

### When to Use Skeletons vs Spinners in This Project

| Location | Pattern | Reason |
|----------|---------|--------|
| Full page navigation (hx-boost) | Skeleton screens | Shows page structure |
| Sync dashboard updates | Inline spinner | Partial update, data stays |
| Chart loading | Skeleton rectangle | Known dimensions |
| Table sort/filter | HTMX indicator (existing) | Quick operation |
| Form submission | Button spinner | Single action |

---

## Recommendation 7: Optimistic UI (Selective)

**Priority**: 🟢 P2
**Effort**: ~2 hours
**Impact**: Snappier UI for safe operations

### Where to Apply (and Where NOT)

| Action | Optimistic? | Why |
|--------|-------------|-----|
| Toggle dark mode | ✅ Yes | Zero risk, instant feedback |
| Filter/sort tables | ✅ Yes | Display-only, no side effects |
| Toggle sidebar | ✅ Yes | UI-only state |
| Start sync | ❌ No | Side effects, needs confirmation |
| Delete resource | ❌ No | Destructive, irreversible |
| Change RBAC | ❌ No | Security-critical |
| Create compliance rule | ❌ No | Needs validation |

---

## Recommendation 8: SSE Accessibility Considerations

**Priority**: 🟡 P1 (if SSE is implemented)
**Effort**: ~1 hour
**Impact**: SSE updates don't break screen reader experience

### Pattern: Throttle aria-live Announcements

```javascript
// Don't announce every SSE update — throttle to avoid screen reader spam
let lastAnnouncement = 0;
const ANNOUNCE_INTERVAL = 30000; // 30 seconds minimum between announcements

document.addEventListener('htmx:sseMessage', function(event) {
    const now = Date.now();
    if (now - lastAnnouncement > ANNOUNCE_INTERVAL) {
        const announcer = document.getElementById('page-announcer');
        announcer.textContent = '';
        requestAnimationFrame(() => {
            announcer.textContent = 'Sync status updated';
        });
        lastAnnouncement = now;
    }
});
```

---

## Implementation Roadmap

### Sprint 1 (This Week)
1. ✅ Install `axe-playwright-python` and create CI test
2. ✅ Create manual testing checklist and schedule first audit
3. ✅ Add accessible table wrappers (macro + CSS)

### Sprint 2 (Next Week)
4. Add HTMX focus management to accessibility.js
5. Replace sync-dashboard polling with SSE
6. Add SSE a11y throttling

### Sprint 3 (Following Week)
7. Implement skeleton screens for dashboard
8. Add skeleton screen for other slow-loading pages
9. Add selective optimistic UI for safe operations

### Backlog (Track but Deprioritize)
10. PWA manifest + service worker (revisit if user base grows)
11. Card view for mobile tables (horizontal scroll is sufficient)

---

## Dependencies to Add

```toml
# pyproject.toml [project.optional-dependencies.dev]
"axe-playwright-python>=0.1.7",   # a11y testing in Playwright

# pyproject.toml [project.dependencies]  (when SSE is implemented)
"sse-starlette>=3.3.0",           # SSE for FastAPI
```

```json
// package.json (when SSE extension needed)
{
    "dependencies": {
        "htmx-ext-sse": "^2.2.2"
    }
}
```

---

*Recommendations finalized: March 27, 2026*
*Researcher: Web-Puppy (web-puppy-c1adca)*
*Project: Azure Governance Platform*

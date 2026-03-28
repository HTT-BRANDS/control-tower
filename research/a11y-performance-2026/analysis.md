# Multi-Dimensional Analysis

## AREA A: Accessibility at Scale

---

### Topic 1: axe-core in CI/CD

#### Current State
- **Latest version**: 4.11.1 (January 6, 2025) — project already references this ✅
- **WCAG 2.2 support**: Via tags `wcag2a`, `wcag2aa`, `wcag22aa` — project config already correct ✅
- **v4.11.0 additions**: RGAA standard support, improved ARIA role handling, better color contrast (oklch/oklab)

#### What axe-core Catches vs Misses

**Catches (~30-40% of WCAG issues):**
- Color contrast violations (including oklch/oklab in v4.11.1)
- Missing alt text, labels, button names
- ARIA attribute validity and allowed roles
- Document language, page titles
- Heading hierarchy issues
- Form label associations
- Keyboard trap detection (basic)
- Link purpose, duplicate IDs
- Table header associations

**Misses (~60-70% require manual testing):**
- Focus order and logical navigation flow
- Focus Not Obscured (2.4.11) — needs visual/scroll testing
- Focus Appearance (2.4.13) — CSS analysis beyond automated capability
- Meaningful content in alt text (detects missing, not quality)
- Cognitive load and readability
- Consistent Help placement (3.2.6)
- Redundant Entry (3.3.7)
- Accessible Authentication (3.3.8)
- Screen reader announcement quality
- Dynamic content behavior (partial — needs real interaction)
- Touch/pointer target spacing context

#### Best Practice: pytest + axe-core Integration

**Option A: axe-playwright-python (RECOMMENDED for this project)**
```python
# tests/accessibility/test_axe_ci.py
import pytest
from playwright.sync_api import Page
from axe_playwright_python.sync_playwright import Axe

axe = Axe()

@pytest.fixture
def pages_to_test():
    return [
        "/dashboard",
        "/sync-dashboard",
        "/costs",
        "/compliance",
        "/resources",
        "/identity",
        "/riverside",
        "/login",
    ]

def test_wcag_compliance(page: Page, pages_to_test):
    for url_path in pages_to_test:
        page.goto(f"http://localhost:8000{url_path}")
        page.wait_for_load_state("networkidle")
        results = axe.run(page)
        assert results.violations_count == 0, (
            f"Page {url_path} has {results.violations_count} a11y violations: "
            f"{[v['id'] for v in results.response['violations']]}"
        )
```

**Option B: @axe-core/playwright (Node.js — for Playwright Test)**
```javascript
const { AxeBuilder } = require('@axe-core/playwright');

// In Playwright test
const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag22aa'])
    .exclude('.chart-container')  // Chart.js canvases
    .analyze();

expect(results.violations).toEqual([]);
```

#### Multi-Dimensional Assessment

| Dimension | Rating | Notes |
|-----------|--------|-------|
| **Security** | ✅ Low risk | Static analysis, no external calls |
| **Cost** | ✅ Free | Open-source MPL-2.0 |
| **Complexity** | ✅ Low | Drop-in with pytest-playwright |
| **Stability** | ✅ Excellent | 7k stars, Deque backed, regular releases |
| **Optimization** | ⚠️ 2-5s/page | Needs headless browser, add to CI budget |
| **Compatibility** | ✅ Full | Works with project's Playwright 1.58+ |
| **Maintenance** | ✅ Low | Auto-updates via dependency bumps |

---

### Topic 2: Pa11y v9.1.1

#### Current State
- **Latest version**: 9.1.1 (February 2026) — confirmed NOT v6.x ✅
- **Node requirement**: >=20
- **License**: LGPL 3.0
- **Runners**: HTML_CodeSniffer (default) + axe (optional) — can run both simultaneously

#### Pa11y vs axe-core Comparison

| Feature | Pa11y 9.1.1 | axe-core 4.11.1 |
|---------|-------------|-----------------|
| **WCAG 2.2 support** | Via axe runner only | Native tags |
| **Standards** | WCAG2A, WCAG2AA, WCAG2AAA | WCAG 2.0/2.1/2.2 + RGAA |
| **Dual runner** | ✅ htmlcs + axe combined | Single engine |
| **CLI** | ✅ First-class | Via @axe-core/cli |
| **Browser required** | ✅ Yes (Puppeteer internally) | ✅ Yes (needs DOM) |
| **CI integration** | Good (JSON/CSV output) | Excellent (many integrations) |
| **Python integration** | CLI only (subprocess) | Native via axe-playwright-python |
| **Unique value** | htmlcs catches different things than axe | Industry standard, more rules |

#### Key Finding: Pa11y Cannot Run Without a Browser
Pa11y uses Puppeteer internally — it ALWAYS needs a browser. It cannot analyze static HTML without rendering. This means CI must provision a headless browser regardless.

#### Recommendation for This Project
**Use BOTH tools in CI** — they catch different issues:
```bash
# Pa11y catches htmlcs-specific issues axe misses
pa11y http://localhost:8000/dashboard --runner axe --runner htmlcs --standard WCAG2AA --reporter json

# axe-playwright-python catches WCAG 2.2 specific issues
pytest tests/accessibility/ -k "test_axe"
```

#### Multi-Dimensional Assessment

| Dimension | Rating | Notes |
|-----------|--------|-------|
| **Security** | ✅ Low risk | CLI tool, no persistence |
| **Cost** | ✅ Free | Open-source LGPL 3.0 |
| **Complexity** | ✅ Low | CLI with config file already exists |
| **Stability** | ✅ Good | 4.4k stars, active maintenance |
| **Optimization** | ⚠️ Slower than axe alone | Runs two engines, ~5-10s/page |
| **Compatibility** | ⚠️ Node.js required | Already have Node for Tailwind |
| **Maintenance** | ✅ Low | Stable API, config already in place |

---

### Topic 3: Manual Testing Gaps — 7 WCAG 2.2 Criteria

These criteria CANNOT be fully automated. Each needs systematic manual testing:

#### 3.1 Focus Not Obscured (2.4.11 AA)
**What it requires**: When an element receives focus, it is not entirely hidden by author-created content.
**Why automation fails**: Requires visual assessment of sticky headers, modals, and overlapping elements during keyboard navigation.
**Testing approach for this project**:
- Tab through all pages; verify focused elements aren't behind the sticky nav (`.bg-brand-primary-100`)
- Check that HTMX-swapped content doesn't obscure focused elements
- The project's `accessibility.js` has `checkFocusObscured()` — good start, but needs manual verification
- Pay attention to mobile menu overlay

#### 3.2 Focus Appearance (2.4.13 AAA — but good practice)
**What it requires**: Focus indicator must have sufficient contrast and size.
**Why automation fails**: Requires measuring focus indicator area and contrast against adjacent colors.
**Testing approach**: Verify that all focusable elements show visible focus rings (project uses Tailwind's `focus:` utilities).

#### 3.3 Dragging Movements (2.5.7 AA)
**What it requires**: Any functionality using dragging can also be achieved with a single pointer without dragging.
**Why automation fails**: Cannot detect all drag interactions programmatically.
**Testing approach for this project**: Review all interactive elements — does anything require drag? (Dashboard widgets, reorderable lists, sliders). Provide alternatives.

#### 3.4 Target Size (2.5.8 AA — Minimum)
**What it requires**: Interactive targets must be at least 24×24 CSS pixels, with exceptions.
**Why automation partially works**: Can measure size (project's `checkTouchTargets()` does this), but exceptions (inline links, user-agent defaults) need manual review.
**Testing approach**: Run `AccessibilityTester.checkTouchTargets()` and manually review each violation.

#### 3.5 Consistent Help (3.2.6 A)
**What it requires**: Help mechanisms appear in the same relative order across pages.
**Why automation fails**: Cannot determine what constitutes "help" or compare relative ordering.
**Testing approach for this project**: Verify that any help links, tooltips, or documentation links appear in consistent positions across all pages.

#### 3.6 Redundant Entry (3.3.7 A)
**What it requires**: Information previously entered by the user is auto-populated or available for selection.
**Why automation fails**: Cannot determine if form data was previously entered in another step.
**Testing approach**: Review multi-step workflows — does the user ever need to re-enter data? (Tenant configuration, compliance rule creation).

#### 3.7 Accessible Authentication (3.3.8 AA)
**What it requires**: Authentication doesn't require cognitive function tests (memorizing passwords is exempt).
**Why automation fails**: Cannot evaluate cognitive load of authentication methods.
**Testing approach**: The login page uses standard password authentication (exempt). Verify no CAPTCHA or cognitive tests are added. If MFA is added, ensure it supports passkeys/authenticator apps.

#### Recommended Manual Testing Schedule
- **Monthly**: Quick keyboard navigation walkthrough (30 min)
- **Quarterly**: Full 7-criteria audit with documented findings (2-3 hours)
- **Per release**: Smoke test focus management on changed pages

---

### Topic 4: HTMX-Specific Accessibility Patterns

#### 4.1 aria-live Regions with HTMX Swaps

**Current project state**: Has `<div id="page-announcer" class="sr-only" aria-live="polite" aria-atomic="true">` ✅

**Best practice pattern:**
```html
<!-- Global announcer (already in base.html) -->
<div id="page-announcer" class="sr-only" aria-live="polite" aria-atomic="true"></div>

<!-- For HTMX swaps — announce what changed -->
<div hx-get="/api/data" 
     hx-target="#data-table"
     hx-swap="innerHTML"
     hx-on::after-swap="announceUpdate('Data table updated')">
    Load Data
</div>

<script>
function announceUpdate(message) {
    const announcer = document.getElementById('page-announcer');
    announcer.textContent = '';  // Clear first to re-trigger announcement
    setTimeout(() => { announcer.textContent = message; }, 100);
}
</script>
```

#### 4.2 Focus Management After Partial Page Updates

**The problem**: When HTMX swaps content, focus can be lost, confusing screen reader users.

**Pattern: Focus the first new content element**
```javascript
document.addEventListener('htmx:afterSwap', function(event) {
    const target = event.detail.target;
    
    // Find the first focusable element in swapped content
    const focusable = target.querySelector(
        'h1, h2, h3, [tabindex="-1"], a, button, input, select, textarea'
    );
    
    if (focusable) {
        // Add tabindex if needed for headings
        if (!focusable.hasAttribute('tabindex')) {
            focusable.setAttribute('tabindex', '-1');
        }
        focusable.focus();
    }
});
```

#### 4.3 Screen Reader Announcements for Dynamic Content

**Pattern: Use hx-swap-oob for announcements**
```html
<!-- Server response includes OOB swap for announcer -->
<div id="data-table">
    <!-- main content -->
</div>
<div id="page-announcer" hx-swap-oob="innerHTML">
    Showing 42 resources across 4 tenants
</div>
```

#### 4.4 HTMX Loading States for Assistive Technology

```html
<button hx-post="/api/sync"
        hx-indicator="#sync-spinner"
        aria-busy="false"
        hx-on::before-request="this.setAttribute('aria-busy','true')"
        hx-on::after-request="this.setAttribute('aria-busy','false')">
    Sync Now
</button>
```

---

### Topic 5: Automated a11y in Playwright

#### Integration Pattern for This Project

```python
# tests/accessibility/conftest.py
import pytest
from playwright.sync_api import Page
from axe_playwright_python.sync_playwright import Axe

@pytest.fixture
def axe():
    return Axe()

@pytest.fixture
def authenticated_page(page: Page):
    """Login and return authenticated page."""
    page.goto("http://localhost:8000/login")
    page.fill('[name="username"]', 'test_user')
    page.fill('[name="password"]', 'test_password')
    page.click('button[type="submit"]')
    page.wait_for_url("**/dashboard")
    return page
```

```python
# tests/accessibility/test_wcag_regression.py
import pytest
import json
from pathlib import Path

PAGES = [
    ("/dashboard", "Dashboard"),
    ("/sync-dashboard", "Sync Dashboard"),
    ("/costs", "Cost Management"),
    ("/compliance", "Compliance"),
    ("/resources", "Resources"),
    ("/identity", "Identity Governance"),
    ("/riverside", "Riverside"),
]

@pytest.mark.parametrize("path,name", PAGES)
def test_wcag22_aa_compliance(authenticated_page, axe, path, name):
    """WCAG 2.2 AA regression test for each page."""
    authenticated_page.goto(f"http://localhost:8000{path}")
    authenticated_page.wait_for_load_state("networkidle")
    
    results = axe.run(authenticated_page)
    
    # Save results for reporting
    report_dir = Path("tests/accessibility/reports")
    report_dir.mkdir(exist_ok=True)
    report_path = report_dir / f"{name.lower().replace(' ', '-')}.json"
    report_path.write_text(json.dumps(results.response, indent=2))
    
    violations = results.response.get("violations", [])
    
    assert len(violations) == 0, (
        f"\n{name} ({path}) has {len(violations)} WCAG violations:\n"
        + "\n".join(
            f"  - [{v['impact']}] {v['id']}: {v['description']} "
            f"({len(v['nodes'])} elements)"
            for v in violations
        )
    )


def test_login_page_accessibility(page, axe):
    """Login page must be accessible without authentication."""
    page.goto("http://localhost:8000/login")
    page.wait_for_load_state("networkidle")
    results = axe.run(page)
    assert results.violations_count == 0
```

#### CI Integration (GitHub Actions)

```yaml
# .github/workflows/accessibility.yml
name: Accessibility Tests
on: [push, pull_request]

jobs:
  a11y:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      
      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
          pip install axe-playwright-python
          playwright install chromium
          npm install -g pa11y@9.1.1
      
      - name: Start application
        run: |
          uvicorn app.main:app --host 0.0.0.0 --port 8000 &
          sleep 5
      
      - name: Run axe-core via Playwright
        run: pytest tests/accessibility/ -v --tb=long
      
      - name: Run Pa11y
        run: |
          pa11y http://localhost:8000/login \
            --config tests/accessibility/pa11y-config.json \
            --reporter json > pa11y-report.json || true
      
      - name: Upload reports
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: a11y-reports
          path: |
            tests/accessibility/reports/
            pa11y-report.json
```

---

## AREA B: Performance & UX Patterns

---

### Topic 6: SSE vs Polling for HTMX

#### Current State
The sync dashboard polls every 5 seconds: `hx-trigger="every 5s"`

#### Why SSE is Better

| Metric | Polling (every 5s) | SSE |
|--------|-------------------|-----|
| **Requests/min/user** | 12 | 0 (single connection) |
| **Latency** | Up to 5s stale | Real-time (<100ms) |
| **Server load** | 12 × N users req/min | N persistent connections |
| **Bandwidth** | Full response each time | Only changed data |
| **Complexity** | Simple | Moderate (needs SSE endpoint) |

For 30 users: Polling = 360 req/min vs SSE = 30 persistent connections.

#### Implementation with FastAPI + HTMX

**Server (FastAPI):**
```python
# app/api/v1/sync_events.py
from fastapi import APIRouter, Request
from sse_starlette import EventSourceResponse
import asyncio

router = APIRouter()

@router.get("/api/v1/sync-events")
async def sync_events(request: Request):
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            
            # Get current sync status
            status = await get_sync_status()
            
            # Send as HTML fragment for HTMX to swap
            yield {
                "event": "sync-update",
                "data": render_sync_status_html(status),
            }
            
            await asyncio.sleep(2)  # Check every 2s server-side
    
    return EventSourceResponse(event_generator())
```

**Client (HTMX):**
```html
<div hx-ext="sse" sse-connect="/api/v1/sync-events">
    <div sse-swap="sync-update" hx-swap="innerHTML">
        <!-- Initial content / loading state -->
        <div class="animate-pulse">Loading sync status...</div>
    </div>
</div>
```

**Install:**
```bash
pip install sse-starlette  # v3.3.3 as of March 2026
npm install htmx-ext-sse   # HTMX SSE extension
```

#### Multi-Dimensional Assessment

| Dimension | Rating | Notes |
|-----------|--------|-------|
| **Security** | ✅ Same as HTTP | Uses existing auth, same-origin |
| **Cost** | ✅ Reduces server load | Fewer requests = less compute |
| **Complexity** | ⚠️ Moderate | New endpoint + extension setup |
| **Stability** | ✅ Excellent | sse-starlette: 39M downloads/week |
| **Optimization** | ✅ Major improvement | Eliminates 360 req/min for 30 users |
| **Compatibility** | ✅ Full | All modern browsers support SSE |
| **Maintenance** | ✅ Low | sse-starlette actively maintained |

---

### Topic 7: Virtual Scrolling for Server-Rendered Tables

#### HTMX Approach: Infinite Scroll (NOT Virtual Scrolling)

True virtual scrolling (rendering only visible rows) isn't practical with server-rendered HTML. HTMX offers two alternatives:

#### Pattern A: Infinite Scroll (Load More on Scroll)
```html
<table>
    <thead>...</thead>
    <tbody id="resource-table">
        {% for resource in resources %}
        <tr>
            <td>{{ resource.name }}</td>
            <td>{{ resource.type }}</td>
        </tr>
        {% endfor %}
        <!-- Sentinel row triggers next page load -->
        <tr hx-get="/resources?page=2"
            hx-trigger="revealed"
            hx-swap="afterend"
            hx-select="tbody > tr">
            <td colspan="2" class="text-center">
                <span class="htmx-indicator">Loading...</span>
            </td>
        </tr>
    </tbody>
</table>
```

#### Pattern B: Server-Side Pagination (RECOMMENDED for this project)
```html
<div class="flex justify-between items-center mt-4">
    <span>Showing {{ start }}-{{ end }} of {{ total }}</span>
    <div class="flex gap-2">
        <button hx-get="/resources?page={{ page - 1 }}"
                hx-target="#resource-table"
                hx-swap="innerHTML"
                {% if page == 1 %}disabled{% endif %}>
            Previous
        </button>
        <button hx-get="/resources?page={{ page + 1 }}"
                hx-target="#resource-table"
                hx-swap="innerHTML"
                {% if page == total_pages %}disabled{% endif %}>
            Next
        </button>
    </div>
</div>
```

#### Recommendation for This Project
**Server-side pagination** is the better pattern because:
1. 10-30 users with governance data rarely exceeds 1000 rows
2. Pagination provides predictable URLs (bookmarkable, shareable)
3. Screen readers handle paginated tables better than infinite scroll
4. No complex client-side state management
5. Fits naturally with HTMX's server-rendered philosophy

Use infinite scroll only if users need to scan large datasets without interruption (unlikely for governance data).

---

### Topic 8: Skeleton Screens vs Loading Spinners

#### NN/g Research Findings (Tier 1 Source)

| Scenario | Best Loading Indicator |
|----------|----------------------|
| 0-0.3s | Nothing (feels instant) |
| 0.3-2s | Subtle inline spinner | 
| 2-10s | Skeleton screen OR spinner |
| >10s | Progress bar with estimation |

#### Key Principles:
1. **Skeleton screens are for full-page loads only** — not for inline updates
2. **Must show actual content structure** — gray boxes mimicking real layout
3. **Do NOT use frame-display skeletons** — header+footer+empty = useless
4. **Animated skeletons reduce perceived wait time** — pulsing gradients work best
5. **Not a replacement for performance optimization** — fix the speed, then add polish

#### For This Project's Data Dashboards

**Recommendation**: Use a **hybrid approach**:
- **Page navigation**: Skeleton screens showing table/card structure
- **HTMX partial updates**: Inline spinners (existing htmx-indicator pattern)
- **Chart loading**: Skeleton rectangles matching chart dimensions

#### HTMX Skeleton Screen Pattern
```html
<!-- Initial skeleton (shown via hx-trigger="load") -->
<div id="dashboard-content"
     hx-get="/dashboard/content"
     hx-trigger="load"
     hx-swap="innerHTML">
    <!-- Skeleton placeholder -->
    <div class="animate-pulse space-y-4" aria-hidden="true">
        <div class="grid grid-cols-4 gap-4">
            <div class="h-24 bg-surface-secondary rounded-lg"></div>
            <div class="h-24 bg-surface-secondary rounded-lg"></div>
            <div class="h-24 bg-surface-secondary rounded-lg"></div>
            <div class="h-24 bg-surface-secondary rounded-lg"></div>
        </div>
        <div class="h-64 bg-surface-secondary rounded-lg"></div>
        <div class="h-48 bg-surface-secondary rounded-lg"></div>
    </div>
    <!-- Screen reader alternative -->
    <div class="sr-only" aria-live="polite">Loading dashboard data...</div>
</div>
```

#### CSS (leverages existing Tailwind)
```css
/* Smooth skeleton-to-content transition */
.htmx-settling > .animate-pulse {
    opacity: 0;
    transition: opacity 200ms ease-out;
}

.htmx-added {
    opacity: 0;
}

.htmx-settling .htmx-added {
    opacity: 1;
    transition: opacity 300ms ease-in;
}
```

---

### Topic 9: Optimistic UI with HTMX

#### Can HTMX Support Optimistic Updates? YES, with patterns.

#### Pattern: Immediate Visual Feedback + Rollback on Error

```html
<!-- Optimistic delete with rollback -->
<tr id="resource-{{ resource.id }}">
    <td>{{ resource.name }}</td>
    <td>
        <button hx-delete="/api/v1/resources/{{ resource.id }}"
                hx-target="#resource-{{ resource.id }}"
                hx-swap="outerHTML swap:300ms"
                hx-confirm="Delete {{ resource.name }}?"
                hx-on::before-request="
                    this.closest('tr').style.opacity = '0.3';
                    this.closest('tr').style.transition = 'opacity 200ms';
                "
                hx-on::after-request="
                    if(event.detail.failed) {
                        this.closest('tr').style.opacity = '1';
                        showToast('Delete failed. Please try again.', 'error');
                    }
                ">
            Delete
        </button>
    </td>
</tr>
```

#### Pattern: Optimistic Toggle (e.g., compliance rule enable/disable)

```html
<label class="flex items-center gap-2">
    <input type="checkbox" 
           checked="{{ rule.enabled }}"
           hx-patch="/api/v1/rules/{{ rule.id }}/toggle"
           hx-swap="none"
           hx-on::before-request="this.disabled = true"
           hx-on::after-request="
               this.disabled = false;
               if(event.detail.failed) {
                   this.checked = !this.checked;
                   showToast('Toggle failed', 'error');
               }
           ">
    {{ rule.name }}
</label>
```

#### Recommendation for This Project
Use optimistic UI **selectively** — governance actions often have real consequences:
- ✅ **Good candidates**: UI toggles, filter selections, sort operations
- ❌ **Bad candidates**: Delete resources, change compliance rules, modify RBAC permissions
- For destructive actions, use confirmation dialogs (project already has `confirmDialog.js`)

---

### Topic 10: PWA for Internal Tools

#### Minimum Viable PWA Requirements

1. **HTTPS** — already required ✅
2. **Web App Manifest** (~20 lines JSON)
3. **Service Worker** (~30 lines JS for basic caching)
4. **Icons** — 192px and 512px PNG

#### Manifest Example
```json
{
    "name": "Azure Governance Platform",
    "short_name": "GovPlatform",
    "start_url": "/dashboard",
    "display": "standalone",
    "background_color": "#ffffff",
    "theme_color": "#1e3a5f",
    "icons": [
        { "src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
        { "src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png" }
    ]
}
```

#### Cost-Benefit Analysis for 10-30 Users

| Benefit | Value for 10-30 Internal Users |
|---------|-------------------------------|
| Offline access | ❌ Low — governance data is always live |
| Install to desktop | ⚠️ Marginal — they already have bookmarks |
| Push notifications | ❌ Not needed — users are at their desks |
| Faster load times | ⚠️ Marginal — internal network is fast |
| Full-screen mode | ⚠️ Nice but not critical |

**Verdict: Skip PWA for now.** The implementation effort (~4 hours) isn't zero, but the ROI for 10-30 internal users who are always on a corporate network with fast connections is very low. Revisit if user base grows or if offline audit review becomes a use case.

---

### Topic 11: Mobile/Responsive Patterns for Data Tables

#### Three Patterns Compared

| Pattern | Accessibility | Data Density | Implementation |
|---------|--------------|--------------|----------------|
| Horizontal scroll | ✅ Best (preserves table semantics) | ✅ High | ✅ Easiest |
| Card view | ⚠️ Loses table relationships | ⚠️ Low | ⚠️ Moderate |
| Column priority | ⚠️ Hides data without user consent | ⚠️ Medium | ❌ Complex |

#### Recommended: Accessible Horizontal Scroll (Roselli Pattern)

```html
<!-- Wrap every data table with this accessible container -->
<div role="region" 
     aria-labelledby="resources-caption" 
     tabindex="0"
     class="overflow-auto focus:outline-2 focus:outline-brand-primary-100 rounded-lg">
    <table>
        <caption id="resources-caption">Azure Resources ({{ count }} items)</caption>
        <thead>
            <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Resource Group</th>
                <th>Subscription</th>
                <th>Region</th>
                <th>Status</th>
                <th>Cost (30d)</th>
            </tr>
        </thead>
        <tbody>...</tbody>
    </table>
</div>
```

```css
/* 6 lines of CSS — that's it */
[role="region"][aria-labelledby][tabindex] {
    overflow: auto;
}
[role="region"][aria-labelledby][tabindex]:focus {
    outline: 0.15em solid var(--brand-primary-100);
}
```

#### WCAG Compliance of This Pattern
- **1.4.10 Reflow (AA)**: ✅ `overflow: auto` prevents page-level horizontal scroll
- **2.1.1 Keyboard (A)**: ✅ `tabindex="0"` enables keyboard scroll
- **4.1.2 Name, Role, Value (A)**: ✅ `role="region"` + `aria-labelledby`
- **2.4.7 Focus Visible (AA)**: ✅ `outline` on `:focus`
- **1.4.11 Non-text Contrast (AA)**: ✅ outline with 3:1+ contrast

#### Alternative: Card View for Very Small Screens (< 480px)

Only use if tables have ≤ 5 columns and users need to compare rows on mobile:
```css
@media (max-width: 480px) {
    table, thead, tbody, tr, td, th {
        display: block;
    }
    thead { display: none; }
    td {
        display: flex;
        justify-content: space-between;
        padding: 0.5rem 1rem;
    }
    td::before {
        content: attr(data-label);
        font-weight: 600;
    }
    tr {
        border: 1px solid var(--border-color);
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        padding: 0.5rem 0;
    }
}
```

**⚠️ Warning**: This CSS-only card view **destroys table semantics** for screen readers. If you must use it, add `role="list"` and `role="listitem"` to `tbody` and `tr`, and use `aria-label` on each cell. The horizontal scroll pattern is simpler and more accessible.

---

*Analysis conducted: March 27, 2026*
*Researcher: Web-Puppy (web-puppy-c1adca)*

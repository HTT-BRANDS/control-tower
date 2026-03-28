# UX Patterns Raw Findings

## Skeleton Screens (NN/g Research)
- **Source**: https://www.nngroup.com/articles/skeleton-screens/
- **Author**: Samhita Tankala, NN/g
- **Published**: June 4, 2023
- **Tier**: 1 (Primary UX research)

### Key Findings

1. **Definition**: Placeholder while page loads, mimics final page structure with gray boxes
2. **Types**:
   - Static-content skeletons: Gray boxes representing text and images
   - Animated skeletons: Pulsing/gradient animations indicating activity
3. **Purpose**: Reduce perception of loading time, set expectations for page layout

### When to Use What
| Wait Time | Recommended Indicator |
|-----------|----------------------|
| 0–0.3s | Nothing |
| 0.3–2s | Subtle spinner |
| 2–10s | Skeleton screen OR spinner |
| >10s | Progress bar with time estimate |

### Critical Rules
- **For full-page loads only** — not for inline partial updates
- **Must show actual content structure** — generic gray screen is useless
- **Do NOT use frame-display skeletons** — header+footer+empty = same as spinner
- **Animated > static** — pulsing gradients decrease perceived wait
- **Not a replacement for optimization** — fix speed first, polish second

### Skeleton Screen vs Spinner Decision
- **Spinners**: Best when page structure is unpredictable or loading is brief (2–10s)
- **Skeleton screens**: Best when page structure is known and consistent
- For < 10s, both can work — choose based on content predictability
- **For data dashboards**: Skeletons are better because layout is consistent across loads

---

## Responsive Data Tables (Adrian Roselli)
- **Source**: https://adrianroselli.com/2020/11/under-engineered-responsive-tables.html
- **Author**: Adrian Roselli (W3C invited expert, a11y consultant)
- **Tier**: 2 (Expert opinion with WCAG analysis)

### The Pattern: 2 Lines HTML + 6 Lines CSS

**HTML:**
```html
<div role="region" aria-labelledby="Caption01" tabindex="0">
    <table>[...]</table>
</div>
```

**CSS:**
```css
[role="region"][aria-labelledby][tabindex] {
    overflow: auto;
}
[role="region"][aria-labelledby][tabindex]:focus {
    outline: .1em solid rgba(0,0,0,.1);
}
```

### WCAG Compliance Analysis
- `tabindex="0"` → WCAG 2.1.1 Keyboard (A): keyboard users can tab to container and scroll
- `role="region"` + `aria-labelledby` → WCAG 4.1.2 Name, Role, Value (A)
- `overflow: auto` → WCAG 1.4.10 Reflow (AA): prevents page-level two-axis scrolling
- `outline` on `:focus` → WCAG 2.4.7 Focus Visible (AA)
- Outline with 3:1 contrast → WCAG 1.4.11 Non-text Contrast (AA)

### Why CSS Selector Matters
Using `[role="region"][aria-labelledby][tabindex]` as the CSS selector means:
- Table won't be clipped UNLESS HTML accessibility attributes are present
- Enforces that developers add the required ARIA attributes
- Better than using classes — self-documenting and self-enforcing

### Card View Alternative (Roselli's Position)
- CSS-only card views **destroy table semantics** for screen readers
- Only appropriate for very simple tables (≤5 columns)
- Horizontal scroll is almost always the better choice for data tables
- If card view is needed, must add `role` attributes to compensate

---

## PWA Install Criteria (web.dev)
- **Source**: https://web.dev/articles/install-criteria
- **Author**: Pete LePage (Google Chrome team)
- **Tier**: 1 (Browser vendor documentation)

### Chrome Install Requirements
1. **User engagement heuristics**:
   - User clicked/tapped page at least once
   - User spent at least 30 seconds viewing page
2. **HTTPS** (required)
3. **Web App Manifest** with:
   - `short_name` or `name`
   - `icons` — 192px and 512px
   - `start_url`
   - `display` — fullscreen, standalone, minimal-ui, or window-controls-overlay
   - `prefer_related_applications` — must not be present or be `false`
4. **Service Worker** with fetch handler

### Minimal Manifest
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

### Minimal Service Worker
```javascript
// sw.js — Cache-first for static assets only
const CACHE_NAME = 'gov-v1';
const STATIC_ASSETS = [
    '/static/css/theme.css',
    '/static/js/navigation/navigation.bundle.js',
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
    );
});

self.addEventListener('fetch', (event) => {
    // Only cache static assets — never cache API/HTML (data must be fresh)
    if (event.request.url.includes('/static/')) {
        event.respondWith(
            caches.match(event.request).then((response) => response || fetch(event.request))
        );
    }
});
```

### Assessment for This Project
- **Effort**: ~4 hours (manifest + service worker + icons)
- **Value for 10-30 internal users**: LOW
  - Offline access: Not useful (governance data needs to be live)
  - Install to desktop: Marginal (bookmarks work fine)
  - Push notifications: Not needed (users at desks)
  - Faster loads: Marginal (internal network is fast)
- **Verdict**: Skip unless user base grows significantly

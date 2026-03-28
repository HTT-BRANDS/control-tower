# HTMX 1.9.12 → 2.0.x Migration Guide

**Source**: https://htmx.org/migration-guide-htmx-1/ (Tier 1 — Official Documentation)

## Overview

HTMX places high value on backwards compatibility. In most cases, migration requires
very little work.

## Breaking Changes Relevant to This Project

### 1. Default Configuration Changes

| Setting | HTMX 1.x Default | HTMX 2.x Default | Impact on Our Project |
|---------|-------------------|-------------------|----------------------|
| `scrollBehavior` | `'smooth'` | `'instant'` | Minor — may want to revert for UX |
| `methodsThatUseUrlParams` | `["get"]` | `["get", "delete"]` | None — we use form-encoded bodies |
| `selfRequestsOnly` | `false` | `true` | ⚠️ **Important** — blocks cross-domain. Our CDN requests should be unaffected since HTMX requests go to same origin |

### 2. hx-on Attribute Syntax Change

**Old** (HTMX 1.x):
```html
<button hx-on="htmx:beforeRequest: alert('...')">
```

**New** (HTMX 2.x):
```html
<button hx-on:htmx:before-request="alert('...')">
```

**Impact**: Need to search for `hx-on=` in templates (use kebab-case for event names).

### 3. Extensions Separated from Core

All extensions are now distributed separately. Critical for this project:
- **SSE extension** → Must load from separate URL
- **WebSocket extension** → Must load from separate URL
- We currently don't use htmx extensions, so **no impact**.

### 4. IE Support Dropped

Not relevant — internal tool for modern browsers only.

### 5. Module Support Added

HTMX 2.x provides proper module files:
- ESM: `/dist/htmx.esm.js`
- AMD: `/dist/htmx.amd.js`
- CJS: `/dist/htmx.cjs.js`

Could be useful if we want to bundle HTMX with our navigation.bundle.js.

## Migration Steps for This Project

### Step 1: Update CDN Link in base.html

```html
<!-- OLD -->
<script src="https://unpkg.com/htmx.org@1.9.12" ...></script>

<!-- NEW -->
<script src="https://unpkg.com/htmx.org@2.0.7" ...></script>
```

Update the SRI integrity hash accordingly.

### Step 2: Check for hx-on Attributes

```bash
grep -r "hx-on=" app/templates/ --include="*.html"
```

Convert any matches to the new `hx-on:` syntax.

### Step 3: Verify selfRequestsOnly Default

Our HTMX requests all go to the same FastAPI origin, so this shouldn't be an issue.
If it is, add to htmx-config meta tag:

```html
<meta name="htmx-config" content='{"selfRequestsOnly": false}'>
```

### Step 4: Test All HTMX Interactions

Priority test list:
- [ ] Dashboard sync button (`hx-post="/api/v1/sync/all"`)
- [ ] Riverside sync (`hx-post="/api/v1/riverside/sync"`)
- [ ] Navigation hx-boost
- [ ] Polling triggers (`hx-trigger="load, every 60s"`)
- [ ] Partial swaps (sync dashboard, riverside badge)
- [ ] hx-confirm dialogs

### Step 5 (Optional): Add htmx-1-compat Extension

If any issues arise, the `htmx-1-compat` core extension rolls back most
HTMX 2 behavioral changes to 1.x defaults. Use as a safety net during migration.

## New Features Available in HTMX 2.0

1. **Shadow DOM support** — Not needed now, but useful for component isolation
2. **Better morph support (idiomorph)** — Core extension for DOM morphing
3. **Preload extension** — Pre-fetch pages for instant navigation
4. **Response-targets extension** — Different swap targets per HTTP status code
5. **head-support extension** — Merge `<head>` tag changes across navigations

## Estimated Migration Effort

**2-4 hours** including testing. This is the lowest-risk change we can make.

# Frontend QA / Accessibility Audit Expectations (2026)

**Scope:** Read-only audit checklist for a Next.js/React app. Context note: this repo is currently FastAPI/HTMX/Tailwind, but the requested target is a Next.js/React frontend audit; adapt route discovery and build artifact checks to the audited app.

## Current package baselines (npm latest checked 2026-05-20)

| Tool | Current version | Audit use | Notes |
|---|---:|---|---|
| `axe-core` | 4.11.4 | In-browser accessibility rules engine | WCAG 2.0/2.1/2.2 A/AA/AAA rules; catches ~57% of WCAG issues automatically and flags `incomplete` for manual review. |
| `@axe-core/playwright` | 4.11.3 | Playwright integration | Prefer page-state scans after UI becomes visible, not only initial route load. |
| `pa11y` | 9.1.1 | CLI/Node a11y URL checks | Requires Node 20/22/24; default standard WCAG2AA; runners: htmlcs default, axe optional. |
| `lighthouse` | 13.3.0 | Performance/a11y/SEO smoke | Open-source automated page-quality audit; use CLI/CI for regression budgets, not as conformance proof. |
| `@playwright/test` | 1.60.0 | E2E, responsive, API contract | Projects support multiple browsers/devices/environments; APIRequestContext covers backend/API assertions. |
| `next` | 16.2.6 | Framework reference | Static assets in `/public` map to root paths and default `Cache-Control: public, max-age=0`. |

## Concise audit checklist

### A. WCAG 2.2 AA manual gaps
- [ ] Define scope by **full pages**, responsive variants, and **complete processes** (auth, checkout/forms, onboarding); do not claim conformance from partial component checks alone.
- [ ] Run automated axe/Pa11y/Lighthouse, but separately perform knowledgeable human review because tools alone cannot determine conformance.
- [ ] Explicitly test WCAG 2.2 additions at A/AA: Focus Not Obscured (2.4.11), Dragging Movements (2.5.7), Target Size Minimum 24px/spacing (2.5.8), Consistent Help (3.2.6), Redundant Entry (3.3.7), Accessible Authentication Minimum (3.3.8).
- [ ] Keyboard-only: tab order, skip link, visible focus, no traps, Escape/dismiss behavior, modals/popovers, menus, toasts/status messages.
- [ ] Screen reader spot checks: landmarks/headings, form labels/instructions/errors, accessible names, live regions, route-change announcements, dialogs.
- [ ] Visual/manual: text contrast 4.5:1, large text 3:1, non-text contrast 3:1, reflow at 320 CSS px / 400% zoom, 200% text resize, text spacing overrides, orientation.
- [ ] Pointer/touch: target size and spacing, pointer cancellation, alternatives for drag/swipe/path gestures.
- [ ] Auth/privacy-sensitive flows: password-manager/copy-paste allowed; no CAPTCHA/puzzle-only cognitive test without accessible alternative; session timeout warnings and data preservation expectations.

### B. Automated a11y/tooling expectations
- [ ] Pin current major versions and record browser/Node versions in evidence.
- [ ] `axe-core`/`@axe-core/playwright`: fail CI on violations; triage `incomplete` as manual-review queue; scan after each meaningful UI state (menus open, modal open, validation errors visible, authenticated pages).
- [ ] Pa11y: run URL list in CI with `--standard WCAG2AA`, JSON reports, `--runner axe` or dual runner where useful, authenticated setup/actions for gated pages, mobile viewport runs.
- [ ] Lighthouse: run against representative production-like pages with fixed throttling/settings; track accessibility/performance/SEO/PWA where applicable; keep JSON artifacts.

### C. Playwright coverage best practices for Next.js/React
- [ ] Route inventory: crawl/link-check all public app routes plus generated static metadata files (`robots.txt`, `sitemap.xml`, manifest, icons, OG images) and role-gated/auth routes where credentials are available.
- [ ] Static assets: verify `/public` assets resolve from root paths; test image alt text where rendered; verify cache/security headers at CDN/app edge.
- [ ] Responsive matrix via Playwright projects: desktop Chromium/Firefox/WebKit; mobile Chrome/Safari emulations; critical breakpoints around nav/layout changes; high zoom/reflow checks.
- [ ] State coverage: unauthenticated, authenticated, empty/loading/error/success states, form validation states, modal/popover/menu states, localization if present.
- [ ] Backend contract checks: use Playwright `request` fixture/APIRequestContext to validate API preconditions/postconditions, status codes, JSON schemas, auth/CSRF/session behavior, and UI-to-API consistency.
- [ ] Network and error resilience: assert no unexpected 4xx/5xx, console errors, hydration errors, missing chunks/assets, CSP violations, or failed image/font loads.

### D. GPC/privacy UI expectations
- [ ] Detect and honor `Sec-GPC: 1` on server/API requests where applicable; treat invalid values as absent; propagate opt-out to analytics/ad/third-party sharing decisions.
- [ ] Expose/document `.well-known/gpc.json` with `application/json`, `{ "gpc": true|false, "lastUpdate": "YYYY-MM-DD" }` if claiming support.
- [ ] In browser/client tests, check `navigator.globalPrivacyControl === true` where automation supports it or inject test context/header; ensure privacy UI reflects opt-out without dark patterns.
- [ ] Privacy UI must clearly disclose how GPC conflicts with site-specific choices/consents are handled; preserve accessible controls for cookie/privacy choices.

## Bottom line

For a 2026 read-only audit, expected coverage is **hybrid**: automated axe/Pa11y/Lighthouse evidence across a route/state/device matrix plus manual WCAG 2.2 AA review of interactions, responsive variants, authentication, and privacy/GPC behavior. Automated scores are useful regression gates, not conformance proof.

# Multi-dimensional analysis

## Security
- Test CSP, mixed content, secure cookies, auth redirects, CSRF/session behaviors, and privacy consent/GPC paths alongside frontend QA.
- WCAG/security overlap: accessible authentication must not block password managers or copy/paste; error suggestions must avoid leaking sensitive data.

## Cost
- Low incremental cost if Playwright already exists: add projects, route manifests, APIRequestContext checks, axe integration, Pa11y/Lighthouse CI artifacts.
- Higher cost is manual a11y review: keyboard, screen reader, responsive/zoom, interaction states, and legal/privacy review.

## Implementation complexity
- Route/state discovery is harder than installing tools. A Next.js audit should enumerate App Router/Pages Router routes, dynamic params, auth roles, and static metadata/assets.
- Automated scans must be stateful: page load, menus, dialogs, validation errors, authenticated views, and empty/error/loading states.

## Stability
- Use current versions but pin majors; Pa11y 9 requires Node 20/22/24.
- axe-core minor releases arrive every 3-5 months and can add rules; expect baseline shifts after upgrades.

## Optimization
- Lighthouse should be used for repeatable regression budgets, not one-off scores only. Keep JSON artifacts and fixed settings.
- Playwright projects can separate fast smoke from broader matrix; run expensive full matrix pre-release/nightly.

## Compatibility
- Test Chromium, Firefox, WebKit, mobile Chrome/Safari emulations. Include real assistive technology spot checks where conformance confidence is required.
- Next.js static assets in `/public` map from root paths and may require CDN/header checks outside the app runtime.

## Maintenance
- Maintain a route inventory and evidence matrix as app routes change.
- Treat axe `incomplete`, Pa11y warnings/notices (when enabled), and manual findings as tracked audit exceptions with owners and due dates.

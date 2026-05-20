# Project-specific recommendations

1. **For the requested Next.js/React read-only audit**, require an evidence matrix: route x viewport/device x auth role x state x tool/manual result.
2. **Do not accept a single Lighthouse or axe score as conformance evidence.** Require manual WCAG 2.2 AA review and note automated blind spots.
3. **Baseline versions as of 2026-05-20:** axe-core 4.11.4, @axe-core/playwright 4.11.3, Pa11y 9.1.1, Lighthouse 13.3.0, Playwright 1.60.0, Next 16.2.6.
4. **Prioritize WCAG 2.2 manual gaps**: focus not obscured, target size, dragging alternatives, redundant entry, consistent help, accessible authentication.
5. **Use Playwright as the audit harness**: projects for browsers/devices/environments, request fixture for API/backend contracts, and page-state snapshots for a11y scans.
6. **Add privacy/GPC checks**: server handling of `Sec-GPC: 1`, `.well-known/gpc.json` if supported, accessible privacy UI, and documented conflict handling with site consent settings.

## Suggested audit commands/patterns

```bash
# Current package versions
npm view axe-core version
npm view @axe-core/playwright version
npm view pa11y version
npm view lighthouse version
npm view @playwright/test version
npm view next version

# Pa11y examples
pa11y https://example.test --standard WCAG2AA --runner axe --reporter json
pa11y https://example.test --standard WCAG2AA --viewport 390x844

# Lighthouse JSON artifact
lighthouse https://example.test --output=json --output-path=reports/lighthouse-home.json

# Playwright matrix
npx playwright test --project=chromium
npx playwright test --project="Mobile Safari"
```

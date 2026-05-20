# Sources and credibility assessment

| Source | Tier | Currency | Key evidence used | Bias / limits |
|---|---:|---|---|---|
| W3C WCAG 2.2 Recommendation, https://www.w3.org/TR/WCAG22/ | 1 | W3C Recommendation republished 2024-12-12 | WCAG 2.2 conformance model; new criteria; full pages/processes; privacy/security considerations. | Normative standard; not implementation-specific. |
| W3C WAI Evaluating Web Accessibility Overview, https://www.w3.org/WAI/test-evaluate/ | 1 | WAI resource page current as accessed 2026-05-20 | No tool alone can determine standards conformance; knowledgeable human evaluation required. | Guidance, not a test runner. |
| Deque axe-core GitHub README, https://github.com/dequelabs/axe-core | 1/2 | Current project README accessed 2026-05-20 | WCAG 2.0/2.1/2.2 A/AA/AAA rule coverage; ~57% automatic issue detection; `incomplete` manual review; release cadence/support notes. | Vendor/project source, but primary for axe behavior. |
| npm registry latest metadata, https://registry.npmjs.org/ | 1 | Queried 2026-05-20 | Current versions: axe-core 4.11.4, @axe-core/playwright 4.11.3, pa11y 9.1.1, lighthouse 13.3.0, @playwright/test 1.60.0, next 16.2.6. | Package registry, not qualitative guidance. |
| Pa11y GitHub README, https://github.com/pa11y/pa11y | 1/2 | Current README accessed 2026-05-20 | Pa11y 9 Node support; CLI options; default WCAG2AA; runners; reports; support table. | Project source; default runner HTML_CodeSniffer is not full WCAG 2.2 coverage. |
| Chrome for Developers Lighthouse overview, https://developer.chrome.com/docs/lighthouse/overview | 1/2 | Last updated 2025-06-02 UTC | Lighthouse is open-source automated tool for page quality; CLI/Node/CI integration; performance/accessibility/SEO audits. | Google documentation; Lighthouse is automated audit only. |
| Playwright docs: Projects, https://playwright.dev/docs/test-projects | 1 | Current docs accessed 2026-05-20 | Projects for browsers/devices/environments; dependencies; smoke/default splits. | Official docs; examples not exhaustive. |
| Playwright docs: API testing, https://playwright.dev/docs/api-testing | 1 | Current docs accessed 2026-05-20 | APIRequestContext for server API tests, preconditions, postconditions, storage state. | Official docs; contract schema strategy is auditor extension. |
| Next.js public folder docs, https://nextjs.org/docs/app/api-reference/file-conventions/public-folder | 1 | Last updated 2026-05-19; Next 16.2.6 | `/public` assets served from root; default `Cache-Control: public, max-age=0`; metadata files should use app conventions. | Framework docs; audited apps may use Pages Router or custom CDN. |
| W3C Global Privacy Control Editor's Draft, https://privacycg.github.io/gpc-spec/ | 1 | Editor’s Draft 2026-04-23 | `Sec-GPC: 1`; `navigator.globalPrivacyControl`; `.well-known/gpc.json`; legal/UI notes. | Editor’s Draft/work in progress; legal obligations vary by jurisdiction. |

## Cross-reference notes

- Automated accessibility coverage is bounded: W3C says human evaluation is required; Deque quantifies axe automatic detection around 57% and flags uncertain results as `incomplete`.
- WCAG 2.2 AA target adds interaction-heavy manual checks (focus obscuring, dragging alternatives, target size, accessible authentication) that are often missed by route-only scans.
- Playwright is the appropriate umbrella for route/state/device/API coverage; axe/Pa11y/Lighthouse are specialized layers within that matrix.

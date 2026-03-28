# Sources & Credibility Assessment

## Source Evaluation Criteria
Each source evaluated on: **Authority** (who published it), **Currency** (when updated), **Validation** (cross-referenced), **Bias** (conflicts of interest), **Primary vs Secondary**.

---

## Tier 1 Sources (Highest Reliability)

### S1. axe-core GitHub Releases
- **URL**: https://github.com/dequelabs/axe-core/releases
- **Authority**: Deque Systems (industry-leading a11y company)
- **Currency**: v4.11.1 released January 6, 2025 (latest as of March 2026)
- **Validation**: Verified directly on GitHub, cross-referenced with npm
- **Bias**: Vendor source, but axe-core is open-source (MPL-2.0)
- **Classification**: Primary source — official release notes

### S2. @axe-core/playwright README
- **URL**: https://github.com/dequelabs/axe-core-npm/tree/develop/packages/playwright
- **Authority**: Deque Systems
- **Currency**: Active development (commits 2 weeks ago as of March 2026)
- **Validation**: Cross-referenced with npm package
- **Bias**: Vendor, but open-source
- **Classification**: Primary source — official API documentation

### S3. Pa11y GitHub Releases
- **URL**: https://github.com/pa11y/pa11y/releases
- **Authority**: Pa11y open-source project (4.4k stars)
- **Currency**: v9.1.1 released February 2026 (confirmed NOT v6.x)
- **Validation**: Verified directly, cross-referenced with npm (v9.1.1)
- **Bias**: None — community open-source project (LGPL 3.0)
- **Classification**: Primary source — official releases

### S4. Pa11y README / Configuration
- **URL**: https://github.com/pa11y/pa11y/blob/main/README.md
- **Authority**: Pa11y maintainers
- **Currency**: Updated February 2026
- **Validation**: Tested configuration options
- **Bias**: None
- **Classification**: Primary source — official documentation
- **Key Finding**: `standard` option supports WCAG2A/AA/AAA only — WCAG 2.2 coverage depends on runners

### S5. HTMX Official Documentation
- **URL**: https://htmx.org/docs/, https://htmx.org/extensions/sse/, https://htmx.org/examples/
- **Authority**: HTMX project (47,720 GitHub stars)
- **Currency**: Current (actively maintained)
- **Validation**: Tested examples
- **Bias**: None — open-source project
- **Classification**: Primary source — official documentation

### S6. NN/g (Nielsen Norman Group) — Skeleton Screens 101
- **URL**: https://www.nngroup.com/articles/skeleton-screens/
- **Authority**: Nielsen Norman Group — gold standard for UX research
- **Currency**: Published June 4, 2023 (principles remain current)
- **Validation**: Cited by Google, Microsoft, and academic publications
- **Bias**: None — independent research organization
- **Classification**: Primary research — empirical UX findings

### S7. web.dev — PWA Install Criteria
- **URL**: https://web.dev/articles/install-criteria
- **Authority**: Google Chrome team
- **Currency**: Current (web.dev actively maintained)
- **Validation**: Cross-referenced with MDN and browser docs
- **Bias**: Chrome-centric, but criteria are widely adopted
- **Classification**: Primary source — browser vendor documentation

### S8. sse-starlette PyPI
- **URL**: https://pypi.org/project/sse-starlette/
- **Authority**: Maintained package (39M downloads/week)
- **Currency**: v3.3.3 released March 17, 2026 (10 days ago)
- **Validation**: Cross-referenced with GitHub, production-tested
- **Bias**: None — open-source
- **Classification**: Primary source — package registry

---

## Tier 2 Sources (High Reliability)

### S9. Adrian Roselli — Under-Engineered Responsive Tables
- **URL**: https://adrianroselli.com/2020/11/under-engineered-responsive-tables.html
- **Authority**: Adrian Roselli — recognized WCAG expert, W3C invited expert
- **Currency**: Published November 2020, updated multiple times (techniques stable)
- **Validation**: Referenced by W3C WAI, tested in screen readers
- **Bias**: None — independent accessibility consultant
- **Classification**: Expert opinion with implementation guidance

### S10. axe-playwright-python PyPI
- **URL**: https://pypi.org/project/axe-playwright-python/
- **Authority**: Community package, based on official axe-core
- **Currency**: v0.1.7 released November 30, 2025
- **Validation**: Cross-referenced with GitHub, active maintenance
- **Bias**: None — open-source
- **Classification**: Secondary source — community wrapper around primary tool

---

## Sources NOT Used (Evaluated and Rejected)

| Source | Reason for Rejection |
|--------|---------------------|
| Medium blog posts on HTMX a11y | Tier 4 — unverified, often outdated |
| Stack Overflow HTMX answers | Tier 3 — mixed quality, version-specific |
| AI-generated a11y guides | Tier 4 — no authority, cannot verify currency |
| Pa11y v6.x documentation | Obsolete — project is at v9.1.1 |

---

## Cross-Reference Validation Matrix

| Claim | Verified By |
|-------|------------|
| axe-core latest is 4.11.1 | S1 (GitHub), npm registry |
| Pa11y is v9.1.1 (not 6.x) | S3 (GitHub), S4 (README badges) |
| Pa11y requires browser (Puppeteer) | S4 (README — uses Puppeteer internally) |
| HTMX SSE extension replaces `hx-sse` | S5 (HTMX docs migration guide) |
| sse-starlette follows W3C spec | S8 (PyPI description) |
| Skeleton screens for full-page loads only | S6 (NN/g primary research) |
| PWA needs manifest + SW + HTTPS | S7 (web.dev Chrome criteria) |
| Responsive table needs role="region" | S9 (Roselli, WCAG SC references) |

---

*All sources accessed March 27, 2026*

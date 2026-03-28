# axe-core Raw Findings

## Version Information
- **Latest**: v4.11.1 (January 6, 2025)
- **Previous**: v4.11.0
- **Repository**: https://github.com/dequelabs/axe-core (7k stars, 876 forks)
- **License**: MPL-2.0

## v4.11.1 Release Notes (Extracted from GitHub)
- Addresses false positives, resulting in slightly lower number of issues reported
- Resolves color contrast rule edge case (page previously skipped)
- Corrects RGAA tag mappings

### Bug Fixes
- Allow shadow roots in axe.run contexts (#4952)
- Color contrast fails for oklch and oklab with none (#4959)
- color-contrast: do not incomplete on textarea (#4968)

## v4.11.0 Features
- RGAA standard support added (French accessibility standard)
- Some best-practice rules now tagged as both `best-practice` and `RGAAv4`
- Affected rules: `focus-order-semantics` (experimental), `region`, `skip-link`, `table-duplicate-name`
- aria-prohibited-attr: add support for fallback roles
- DqElement: deprecate fromFrame function
- DqElement: truncate large HTML strings
- get-xpath: return proper relative selector for id
- td-headers-attr: report headers attribute referencing other elements as unsupported

## @axe-core/playwright Package
- **Path**: packages/playwright in axe-core-npm monorepo
- **Versioning**: Follows axe-core major.minor (not SemVer)
- **API**: Chainable AxeBuilder
  - `new AxeBuilder({ page })` — constructor
  - `.analyze()` — returns Promise<axe.Results | Error>
  - `.include(selector)` — add CSS selectors to include
  - `.exclude(selector)` — exclude elements
  - `.options(options)` — pass axe.RunOptions
  - `.withRules(rules)` — limit to specific rule IDs
  - `.withTags(tags)` — filter by WCAG tags

## axe-playwright-python (PyPI)
- **Version**: 0.1.7 (November 30, 2025)
- **Python support**: 3.8–3.14
- **API**:
  ```python
  from playwright.sync_api import sync_playwright
  from axe_playwright_python.sync_playwright import Axe
  
  axe = Axe()
  results = axe.run(page)
  print(f"Found {results.violations_count} violations.")
  ```
- Based on axe-core-python by @ruslan-rv-ua
- Takes inspiration from axe-selenium-python for output formats

## WCAG Tags Available
- `wcag2a` — WCAG 2.0 Level A
- `wcag2aa` — WCAG 2.0 Level AA
- `wcag2aaa` — WCAG 2.0 Level AAA
- `wcag21a` — WCAG 2.1 Level A
- `wcag21aa` — WCAG 2.1 Level AA
- `wcag22aa` — WCAG 2.2 Level AA ← USE THIS
- `best-practice` — Best practices beyond WCAG
- `RGAAv4` — French RGAA standard (new in 4.11.0)

## Project's Current Config (tests/accessibility/axe-config.json)
```json
{
  "tags": ["wcag2a", "wcag2aa", "wcag22aa"],
  "resultTypes": ["violations", "incomplete"],
  "reporter": "v2",
  "rules": {
    "color-contrast": { "enabled": true },
    "label": { "enabled": true },
    "image-alt": { "enabled": true },
    "link-name": { "enabled": true },
    "button-name": { "enabled": true },
    "html-has-lang": { "enabled": true },
    "document-title": { "enabled": true },
    "bypass": { "enabled": true },
    "region": { "enabled": true }
  }
}
```
**Note**: Config is correct but limiting — explicitly enabling rules limits to only those 9. Remove the `rules` object to get ALL rules matching the tags.

# Pa11y Raw Findings

## Version Information
- **Latest**: v9.1.1 (February 2026, confirmed)
- **Previous**: v9.1.0
- **Repository**: https://github.com/pa11y/pa11y (4.4k stars, 289 forks)
- **License**: LGPL 3.0
- **Node requirement**: >=20

## v9.1.1 Release Notes
- Fix several issues with loading custom runners, including errors when loading any custom runner on Windows (#798)
- Update debug messages related to opening the page and navigating to the target URL (#701)
- Update dependencies (no functional changes)

## Key Capabilities
- **Default runner**: HTML_CodeSniffer
- **Alternative runner**: axe (use `--runner axe`)
- **Dual runner**: Can run both simultaneously: `--runner axe --runner htmlcs`
- **Standards**: WCAG2A, WCAG2AA, WCAG2AAA
- **Output formats**: JSON, CSV, TSV, CLI, HTML (via reporters)

## WCAG 2.2 Support Assessment
- **Via htmlcs runner**: WCAG 2.1 only (HTML_CodeSniffer hasn't added explicit WCAG 2.2 rules)
- **Via axe runner**: WCAG 2.2 supported (inherits axe-core's tags)
- **Standard option**: Only accepts `WCAG2A`, `WCAG2AA`, `WCAG2AAA` — no `WCAG22AA` equivalent
- **Conclusion**: To get WCAG 2.2 coverage, MUST use the axe runner

## Browser Requirement
Pa11y uses Puppeteer internally. It CANNOT run without a browser.
For CI, use headless Chrome:
```json
{
  "chromeLaunchConfig": {
    "args": ["--no-sandbox", "--disable-setuid-sandbox"]
  }
}
```

## Project's Current Config (tests/accessibility/pa11y-config.json)
```json
{
  "standard": "WCAG2AA",
  "runners": ["axe", "htmlcs"],
  "timeout": 30000,
  "wait": 2000,
  "chromeLaunchConfig": {
    "args": ["--no-sandbox", "--disable-setuid-sandbox"]
  },
  "hideElements": ".monaco-editor, .swagger-ui",
  "ignore": []
}
```
**Assessment**: Config is well-done — uses dual runners ✅, WCAG2AA standard ✅, headless-compatible ✅.

## CLI Usage Examples
```bash
# Basic scan
pa11y http://localhost:8000

# With config
pa11y http://localhost:8000 --config tests/accessibility/pa11y-config.json

# JSON output for CI
pa11y http://localhost:8000 --reporter json > pa11y-report.json

# Specific standard
pa11y http://localhost:8000 --standard WCAG2AA

# Dual runners
pa11y http://localhost:8000 --runner axe --runner htmlcs

# Threshold (allow N issues before failing)
pa11y http://localhost:8000 --threshold 5

# Test local HTML file
pa11y ./path/to/file.html
```

## Pa11y vs axe-core: Complementary Coverage

### Issues Pa11y (htmlcs) catches that axe might miss:
- Stricter heading hierarchy validation
- Form label techniques (explicit vs implicit)
- Some table header association patterns
- Certain ARIA usage patterns

### Issues axe-core catches that Pa11y (htmlcs) misses:
- WCAG 2.2 specific rules (Focus Not Obscured partial, Target Size partial)
- oklch/oklab color contrast
- Shadow DOM accessibility
- RGAA compliance

### Recommendation: Use BOTH for maximum coverage
```bash
# In CI: run both, fail on either
pa11y http://localhost:8000/login --runner axe --runner htmlcs --reporter json
pytest tests/accessibility/test_wcag_regression.py -v
```

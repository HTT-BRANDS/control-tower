# Accessibility Testing

Automated accessibility testing using **axe-core 4.11.1** and **Pa11y 9.1.1** for WCAG 2.2 AA compliance.

## Prerequisites

- Node.js 20+
- npm
- Running FastAPI application

## Quick Start

```bash
# Install tools globally
npm install -g @axe-core/cli@4.11.1 pa11y@9.1.1

# Start the application
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# Run axe-core scan
axe http://localhost:8000 --tags wcag2a,wcag2aa,wcag22aa

# Run Pa11y scan
pa11y http://localhost:8000 --config tests/accessibility/pa11y-config.json
```

## Configuration

| File | Tool | Purpose |
|------|------|---------|
| `axe-config.json` | axe-core 4.11.1 | Rules, tags, and result types |
| `pa11y-config.json` | Pa11y 9.1.1 | Standards, runners, timeouts |

## CI Integration

The `.github/workflows/accessibility.yml` workflow runs both tools automatically on push/PR.

## Interpreting Results

### axe-core
- **violations**: Issues that MUST be fixed (WCAG failures)
- **incomplete**: Items needing manual review

### Pa11y
- **error**: WCAG violations (must fix)
- **warning**: Potential issues (should review)
- **notice**: Best practice suggestions

## Adding Pages

To scan additional pages, add URLs to:
1. The axe-core scan step in `.github/workflows/accessibility.yml`
2. The Pa11y scan step in the same workflow

## Standards

- WCAG 2.2 Level AA (primary)
- WCAG 2.0 Level A (baseline)
- Section 508 (US federal)

## References

- [axe-core Rules](https://github.com/dequelabs/axe-core/blob/develop/doc/rule-descriptions.md)
- [Pa11y Documentation](https://github.com/pa11y/pa11y)
- [WCAG 2.2 Quick Reference](https://www.w3.org/WAI/WCAG22/quickref/)

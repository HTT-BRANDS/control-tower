# Azure Governance Platform — Dependency Management Strategy

## Overview

This document outlines the comprehensive dependency management strategy for the Azure Governance Platform. Our approach prioritizes **security**, **stability**, and **automation** while maintaining a clear separation between production and development dependencies.

## Table of Contents

- [Overview](#overview)
- [Dependency Sources](#dependency-sources)
- [Locking Strategy](#locking-strategy)
- [Automated Updates](#automated-updates)
- [Security Scanning](#security-scanning)
- [Manual Checks](#manual-checks)
- [Update Workflows](#update-workflows)
- [Troubleshooting](#troubleshooting)

## Dependency Sources

### Primary Source of Truth

| File | Purpose | Managed By |
|------|---------|------------|
| `pyproject.toml` | Human-editable dependency declarations | Developers |
| `uv.lock` | Machine-generated lock file | `uv lock` |
| `requirements.txt` | Production-ready pinned versions | `uv export` |
| `requirements-dev.txt` | Development dependencies | `uv export --only-dev` |

### Dependency Categories

```toml
# In pyproject.toml
[project.dependencies]           # Production runtime dependencies
[project.optional-dependencies]    # Optional extras (seldom used)
[dependency-groups.dev]           # Development dependencies (uv-specific)
```

## Locking Strategy

We use **uv** (the ultra-fast Python package manager) for dependency resolution and locking.

### Why uv?

- **Speed**: 10-100x faster than pip/poetry
- **Deterministic**: Reproducible builds with `uv.lock`
- **Compatible**: Works with standard `pyproject.toml`
- **Modern**: Native support for PEP 621, 631, and 735

### Lock File Management

```bash
# After editing pyproject.toml, regenerate the lock file
uv lock

# Verify lock file is up to date
uv lock --check
```

### Pinning Strategy

| Dependency Type | Strategy | Rationale |
|-----------------|----------|-----------|
| Production | Pinned exact versions | Reproducible builds, security |
| Development | Pinned exact versions | Consistent dev environment |
| pyproject.toml | Minimum versions (`>=`) | Flexibility for updates |

## Automated Updates

### Dependabot Configuration

Located at `.github/dependabot.yml`, Dependabot monitors three ecosystems:

1. **Python (pip)**: Weekly updates on Mondays
2. **GitHub Actions**: Weekly updates on Mondays
3. **Docker images**: Weekly updates on Mondays

### Update Grouping

To reduce PR noise, updates are grouped by type:

- **minor-patch**: Minor and patch updates (auto-mergeable if tests pass)
- **security**: Security updates (immediate attention)
- **major**: Major version updates (manual review required)

### Ignored Updates

Major version updates (`semver-major`) are intentionally ignored by Dependabot to require manual review. This is critical for a security-sensitive application.

```yaml
# From .github/dependabot.yml
ignore:
  - dependency-name: "*"
    update-types: ["version-update:semver-major"]
```

## Security Scanning

### Automated Scanning

**Weekly Schedule** (`.github/workflows/dependency-update.yml`):

1. **pip-audit**: Scans for known CVEs in dependencies
2. **GitHub Security Advisories**: Monitors for new security issues
3. **Auto-issue creation**: Creates GitHub issues for vulnerabilities

### Local Scanning

Use the `check-dependencies.sh` script for local audits:

```bash
# Full check (security + outdated + deprecated)
./scripts/check-dependencies.sh

# Security only
./scripts/check-dependencies.sh --security

# With JSON output
./scripts/check-dependencies.sh --json

# Save report to file
./scripts/check-dependencies.sh --report dependency-report.md
```

### Security Response Workflow

```
┌─────────────────┐
│ pip-audit finds │
│   vulnerability │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Auto-create     │
│ GitHub issue    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Apply fix       │
│ (uv add pkg@x)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Close issue     │
└─────────────────┘
```

## Manual Checks

### Pre-Commit Hook

Add to `.pre-commit-config.yaml`:

```yaml
- repo: local
  hooks:
    - id: check-dependencies
      name: Check for outdated dependencies
      entry: ./scripts/check-dependencies.sh --security
      language: script
      pass_filenames: false
      always_run: true
```

### Before Releases

Always run before deploying:

```bash
# 1. Update dependencies
uv sync --upgrade

# 2. Run full dependency check
./scripts/check-dependencies.sh

# 3. Run tests
uv run pytest

# 4. Lock and export
uv lock
uv export --no-hashes --no-dev > requirements.txt
uv export --no-hashes --only-dev > requirements-dev.txt
```

## Update Workflows

### Minor/Patch Updates (Automated)

```
Dependabot detects update
        │
        ▼
┌───────────────────────┐
│ Creates grouped PR    │
│ (minor-patch group)   │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ CI runs (tests pass)  │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ Auto-approved &       │
│ auto-merged           │
└───────────────────────┘
```

### Major Updates (Manual)

```
Dependabot detects major update
        │
        ▼
┌───────────────────────┐
│ Creates issue (not PR)│
│ for manual review       │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ Developer reviews     │
│ breaking changes      │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ Tests in staging      │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│ Manual PR merge       │
└───────────────────────┘
```

### Weekly Automation Schedule

| Day | Time | Action |
|-----|------|--------|
| Sunday | 22:00 UTC | `dependency-update.yml` runs (security audit, outdated check) |
| Monday | 09:00 UTC | Dependabot checks for updates |
| Ongoing | — | Auto-merge minor updates if CI passes |

## Troubleshooting

### Common Issues

#### Issue: `uv.lock` out of sync

```bash
# Symptom: "Lock file is out of date"
uv lock --upgrade
```

#### Issue: pip-audit reports false positives

```bash
# Check if vulnerability is exploitable in your context
pip-audit -r requirements.txt --desc --format=json | jq '.dependencies[] | select(.vulns)'

# If false positive, add to .trivyignore or document in known-issues.md
```

#### Issue: Dependabot PRs conflict with uv.lock

```bash
# Don't use Dependabot's "bump" PRs directly
# Instead:
1. Checkout the branch
2. Run: uv lock --upgrade-package <package>
3. Commit the updated uv.lock
```

### Lock File Corruption

```bash
# If uv.lock becomes corrupted:
rm uv.lock
uv lock
```

### Emergency Security Fix

```bash
# 1. Identify vulnerable package
pip-audit -r requirements.txt

# 2. Update to patched version
uv add <package>@<patched_version>

# 3. Test
uv run pytest

# 4. Commit and deploy
git add uv.lock pyproject.toml
git commit -m "security: fix CVE-XXXX in <package>"
```

## File Reference

| File | Purpose | Updated By |
|------|---------|------------|
| `pyproject.toml` | Dependency specifications | Manual edit |
| `uv.lock` | Locked dependency tree | `uv lock` |
| `requirements.txt` | Production exports | `uv export --no-dev` |
| `requirements-dev.txt` | Dev exports | `uv export --only-dev` |
| `.github/dependabot.yml` | Dependabot config | Manual edit |
| `.github/workflows/dependency-update.yml` | Weekly automation | Manual edit |
| `scripts/check-dependencies.sh` | Local checks | Manual edit |

## See Also

- [uv Documentation](https://docs.astral.sh/uv/)
- [pip-audit Documentation](https://github.com/pypa/pip-audit)
- [Dependabot Documentation](https://docs.github.com/en/code-security/dependabot)
- [GitHub Security Advisories](https://github.com/advisories)

---

*This strategy is reviewed quarterly. Last updated: $(date +%Y-%m-%d)*

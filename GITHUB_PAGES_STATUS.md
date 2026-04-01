# GitHub Pages Status Report

**Date:** April 1, 2026  
**Repository:** HTT-BRANDS/azure-governance-platform

---

## ✅ GitHub Pages Configuration

### Status
| Setting | Value |
|---------|-------|
| **Status** | 🟢 ACTIVE - Currently Building |
| **URL** | https://htt-brands.github.io/azure-governance-platform/ |
| **Source** | `/docs` folder on `main` branch |
| **Build Type** | Jekyll (legacy) |
| **Theme** | Minima |

### Configuration Files

#### docs/_config.yml
- **Title:** Azure Governance Platform
- **Description:** Technical Architecture & Operations Guide
- **URL:** https://htt-brands.github.io
- **BaseURL:** /azure-governance-platform
- **Theme:** minima
- **Plugins:** jekyll-feed, jekyll-sitemap, jekyll-seo-tag

#### docs/Gemfile
- GitHub Pages gem installed
- Compatible plugins configured
- Local Jekyll testing support

#### docs/index.md
- Jekyll frontmatter configured
- Layout: default
- Serves as homepage

---

## 📁 Documentation Structure

The GitHub Pages site is built from the `docs/` folder:

```
docs/
├── _config.yml          # Jekyll configuration
├── Gemfile              # Ruby dependencies
├── index.md             # Homepage
├── architecture/        # Architecture docs (collection)
├── operations/          # Operations docs (collection)
├── api/                 # API reference (collection)
├── decisions/           # ADRs
├── runbooks/            # Operational runbooks
├── security/            # Security documentation
├── governance/          # Governance docs
├── patterns/            # Design patterns
├── testing/             # Testing guides
├── validation/          # Validation reports
└── archive/             # Archived docs (excluded)
```

---

## 🚀 Accessing the Site

### Live URL
```
https://htt-brands.github.io/azure-governance-platform/
```

### Repository Homepage
The repository homepage is now set to the GitHub Pages URL:
```
https://htt-brands.github.io/azure-governance-platform/
```

---

## 🔧 How It Works

### Automatic Deployment
1. Push changes to `main` branch
2. GitHub detects changes in `/docs` folder
3. Jekyll builds the site (uses `_config.yml`)
4. Site is deployed to GitHub Pages
5. Changes are live within 1-2 minutes

### Local Testing (Optional)
```bash
cd docs/
bundle install
bundle exec jekyll serve
# Visit http://localhost:4000/azure-governance-platform/
```

---

## 📋 Maintenance Tasks

### Adding New Documentation
1. Create markdown file in `docs/` or appropriate subdirectory
2. Add frontmatter if needed:
   ```yaml
   ---
   layout: default
   title: Your Page Title
   ---
   ```
3. Commit and push to `main`
4. Site will rebuild automatically

### Collections
Three Jekyll collections are configured:
- `/architecture/` - Architecture documentation
- `/operations/` - Operations guides
- `/api/` - API reference docs

Files in these folders get special permalinks.

---

## 🔍 Verification Commands

### Check GitHub Pages Status
```bash
gh api repos/HTT-BRANDS/azure-governance-platform/pages | jq .
```

### Check Build Status
Visit: https://github.com/HTT-BRANDS/azure-governance-platform/settings/pages

### Test Local Build
```bash
cd docs/
bundle exec jekyll build
```

---

## 📝 Notes

- **Excluded from build:** `scripts/`, `tests/`, `archive/`, `infrastructure/terraform/`
- **404 page:** Not configured (uses default)
- **Custom domain:** Not configured (using default github.io domain)
- **HTTPS:** Enabled by default
- **CNAME:** Not required (using default domain)

---

**Last Updated:** April 1, 2026  
**Status:** ✅ GitHub Pages Active and Configured

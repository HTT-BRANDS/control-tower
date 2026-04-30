# GitHub CLI Automation Guide

> **Complete guide to automating Azure Governance Platform with `gh` CLI**  
> **Version:** 1.0  
> **Last Updated:** February 2025

---

## 📋 Overview

This guide covers using the [GitHub CLI (`gh`)](https://cli.github.com) to automate setup, deployment, and management of the Azure Governance Platform. The scripts in `scripts/` provide turnkey automation for common workflows.

### Why Use GitHub CLI?

- ✅ **No web UI clicking** - Automate repetitive tasks
- ✅ **Idempotent scripts** - Run multiple times safely
- ✅ **Consistent environments** - Same setup every time
- ✅ **CI/CD friendly** - Integrate with automation
- ✅ **Fast iteration** - Deploy from command line

### Script Overview

| Script | Purpose | Typical Use |
|--------|---------|-------------|
| `gh-setup.sh` | Master GitHub setup | First-time repo configuration |
| `gh-deploy-dev.sh` | Deploy to dev | Daily development workflow |
| `gh-status.sh` | Status dashboard | Check repo/workflow health |
| `gh-secret-rotate.sh` | Rotate secrets | Security maintenance |
| `gh-oidc-setup.sh` | OIDC federation | Azure AD integration |
| `gh-tenants-setup.sh` | Configure tenants | Set up tenant variables/secrets |
| `gh-tenants-list.sh` | List tenants | View configured tenants |
| `gh-tenants-sync.sh` | Sync tenants | Trigger tenant data sync |

---

## 🏢 Tenant Management Scripts

Scripts for managing Riverside tenant configurations via GitHub CLI.

### 6. `gh-tenants-setup.sh` - Configure Tenants

Set up tenant-specific variables and secrets for all Riverside tenants.

```bash
# Configure all tenants
./scripts/gh-tenants-setup.sh
```

**What it does:**
1. ✅ Sets GitHub Variables for each tenant (IDs, admin emails)
2. ✅ Creates placeholder secrets for client credentials
3. ✅ Supports all Riverside tenants: HTT, BCC, FN, TLL

**Tenants configured:**
| Code | Name | Admin Email |
|------|------|-------------|
| HTT | HTT Brands | tyler.granlund-admin@httbrands.com |
| BCC | Bishop's | tyler.granlund-Admin@bishopsbs.onmicrosoft.com |
| FN | Frenchies | tyler.granlund-Admin@ftgfrenchiesoutlook.onmicrosoft.com |
| TLL | Lash Lounge | tyler.granlund-Admin@LashLoungeFranchise.onmicrosoft.com |

**Variables set:** (non-sensitive, visible in workflows)
- `RIVERSIDE_<CODE>_TENANT_ID` - Azure AD tenant ID
- `RIVERSIDE_<CODE>_ADMIN_EMAIL` - Admin account email

**Secrets set:** (encrypted)
- `RIVERSIDE_<CODE>_CLIENT_ID` - App registration client ID (placeholder)
- `RIVERSIDE_<CODE>_CLIENT_SECRET` - Client secret (to be added manually)

**Next steps:**
```bash
# 1. Run the setup
./scripts/gh-tenants-setup.sh

# 2. Create app registrations in Azure
./scripts/setup-tenant-apps.ps1

# 3. Update secrets with real values
gh secret set RIVERSIDE_HTT_CLIENT_ID -b "<real-client-id>"
gh secret set RIVERSIDE_HTT_CLIENT_SECRET -b "<real-secret>"
```

---

### 7. `gh-tenants-list.sh` - List Tenants

Display all configured Riverside tenants with their variables and secrets.

```bash
# Show all tenant configuration
./scripts/gh-tenants-list.sh
```

**What it shows:**
- All RIVERSIDE_* variables (tenant IDs, admin emails)
- All RIVERSIDE_* secrets (IDs only, not values)
- Commands to update secrets

---

### 8. `gh-tenants-sync.sh` - Trigger Tenant Sync

Trigger sync workflows for tenant data.

```bash
# Sync all tenants
./scripts/gh-tenants-sync.sh

# Sync specific tenant
./scripts/gh-tenants-sync.sh HTT
./scripts/gh-tenants-sync.sh BCC
./scripts/gh-tenants-sync.sh FN
./scripts/gh-tenants-sync.sh TLL
```

**Note:** Requires tenant-sync.yml workflow to be configured.

---

## 🚀 Quick Start

### Prerequisites

```bash
# Install GitHub CLI
# macOS
brew install gh

# Windows (via winget)
winget install --id GitHub.cli

# Linux
sudo apt install gh  # Debian/Ubuntu
sudo dnf install gh  # Fedora

# Verify installation
gh --version  # Should be 2.40+
```

### Authenticate

```bash
# Interactive login
gh auth login

# Or with token (for CI/CD)
gh auth login --with-token < ~/.github-token

# Verify
gh auth status
```

### First Time Setup

```bash
# Clone and setup repository
git clone <your-repo-url>
cd control-tower

# Run master setup
./scripts/gh-setup.sh
```

---

## 📚 Available Scripts

### 1. `gh-setup.sh` - Master Setup

Complete GitHub repository configuration.

```bash
# Full setup for development
./scripts/gh-setup.sh

# Setup for production
./scripts/gh-setup.sh -e prod

# Setup without branch protection
./scripts/gh-setup.sh --skip-protection
```

**What it does:**
1. ✅ Creates GitHub environments (development, staging, production)
2. ✅ Sets repository secrets (Azure credentials, encryption keys)
3. ✅ Sets environment-specific secrets
4. ✅ Configures branch protection rules
5. ✅ Verifies setup

**Interactive prompts:**
- Azure Tenant ID
- Azure Subscription ID
- Azure Client ID (App Registration)

---

### 2. `gh-deploy-dev.sh` - Deploy to Dev

Deploy current branch to development environment.

```bash
# Deploy with monitoring
./scripts/gh-deploy-dev.sh

# Quick deploy (no monitoring)
./scripts/gh-deploy-dev.sh --no-watch

# Sync with main first, then deploy
./scripts/gh-deploy-dev.sh --sync

# Force push (use with caution)
./scripts/gh-deploy-dev.sh --force
```

**What it does:**
1. ✅ Checks for uncommitted changes
2. ✅ Optionally syncs with main
3. ✅ Merges current branch into `dev`
4. ✅ Pushes to trigger GitHub Actions
5. ✅ Monitors deployment progress
6. ✅ Runs verification tests

**Workflow:**
```
your-branch → dev → GitHub Actions → Azure Dev Environment
```

---

### 3. `gh-status.sh` - Status Dashboard

Quick overview of repository status, workflows, and deployments.

```bash
# Show current status
./scripts/gh-status.sh

# Watch mode (auto-refresh every 10s)
./scripts/gh-status.sh -w

# Show more runs
./scripts/gh-status.sh -l 10
```

**What it shows:**
- Repository info (stars, forks, default branch)
- Recent workflow runs with status
- Active/in-progress runs
- Open pull requests
- Configured environments
- Secret count

---

### 4. `gh-secret-rotate.sh` - Secret Rotation

Securely rotate GitHub secrets with generation and validation.

```bash
# Generate and rotate database encryption key
./scripts/gh-secret-rotate.sh DATABASE_ENCRYPTION_KEY --generate

# Rotate with specific value
./scripts/gh-secret-rotate.sh API_KEY -v "new-secret-value"

# Rotate environment-specific secret
./scripts/gh-secret-rotate.sh PROD_KEY -e production -g

# Delete a secret
./scripts/gh-secret-rotate.sh OLD_SECRET --delete
```

**Security features:**
- Cryptographically secure random generation
- Hidden input for manual values
- Confirmation prompts
- Verification after rotation
- Values never logged or displayed

---

### 5. `gh-oidc-setup.sh` - OIDC Federation

Set up OIDC authentication between GitHub and Azure.

```bash
# Full OIDC setup for dev
./scripts/gh-oidc-setup.sh

# Setup for production
./scripts/gh-oidc-setup.sh -e prod

# Create resource group if missing
./scripts/gh-oidc-setup.sh --create-rg

# Only update GitHub secrets (skip Azure)
./scripts/gh-oidc-setup.sh --skip-azure

# Only Azure setup (skip GitHub)
./scripts/gh-oidc-setup.sh --skip-gh-secrets
```

**What it does:**
1. ✅ Creates Azure AD App Registration
2. ✅ Creates Service Principal
3. ✅ Configures federated credentials for GitHub OIDC
4. ✅ Assigns Azure RBAC roles
5. ✅ Sets GitHub secrets
6. ✅ Saves configuration to JSON

---

## 🔧 Common Workflows

### Initial Repository Setup

```bash
# 1. Setup GitHub repository
./scripts/gh-setup.sh

# 2. Setup OIDC federation
./scripts/gh-oidc-setup.sh -e dev --create-rg

# 3. Verify GitHub secrets
gh secret list

# 4. Test deployment
./scripts/gh-deploy-dev.sh
```

### Daily Development Workflow

```bash
# Start feature work
git checkout -b feature/my-feature

# Make changes...
vim app/api/routes/my_route.py

# Commit
git add -A
git commit -m "Add new feature"

# Deploy to dev for testing
./scripts/gh-deploy-dev.sh --sync

# Monitor logs
gh run watch

# Open PR when ready
git push origin feature/my-feature
gh pr create --title "Add new feature" --body "Description..."
```

### Production Deployment

```bash
# 1. Ensure production OIDC is set up
./scripts/gh-oidc-setup.sh -e prod

# 2. Create release tag
git checkout main
git pull origin main
git tag -a v1.2.0 -m "Release v1.2.0"
git push origin v1.2.0

# 3. Monitor production deployment
gh run list --workflow=deploy-production.yml
gh run watch

# 4. Verify deployment
./scripts/verify-dev-deployment.sh  # Adapt for prod
```

---

## 🛠️ Essential gh CLI Commands

### Repository Management

```bash
# View repository
gh repo view
gh repo view --web  # Open in browser

# List repositories
gh repo list owner-name --limit 20

# Fork repository
gh repo fork

# Clone with gh credentials
gh repo clone owner/repo
```

### Workflows

```bash
# List workflows
gh workflow list

# View workflow
gh workflow view deploy-dev.yml

# Trigger workflow manually
gh workflow run deploy-dev.yml --ref dev

# Enable/disable workflow
gh workflow enable deploy-dev.yml
gh workflow disable deploy-dev.yml
```

### Runs

```bash
# List recent runs
gh run list
gh run list --workflow=deploy-dev.yml
gh run list --branch=dev --limit 10

# View run details
gh run view <run-id>
gh run view --web  # Open in browser

# Watch live run
gh run watch
gh run watch <run-id>

# Rerun failed jobs
gh run rerun <run-id>
gh run rerun <run-id> --failed

# Download logs
gh run download <run-id>
```

### Secrets & Variables

```bash
# List secrets
gh secret list
gh secret list --env production

# Set secret
echo "secret-value" | gh secret set SECRET_NAME
gh secret set SECRET_NAME --body "value"

# Set environment secret
echo "value" | gh secret set SECRET_NAME --env production

# Remove secret
gh secret remove SECRET_NAME

# List variables (non-sensitive)
gh variable list
gh variable set VAR_NAME --body "value"
```

### Environments

```bash
# List environments
gt api repos/owner/repo/environments --jq '.environments[].name'

# Create environment (via API)
gt api repos/owner/repo/environments/development --method PUT

# View environment protection rules
gt api repos/owner/repo/environments/development
```

### Pull Requests

```bash
# Create PR
gt pr create --title "Title" --body "Description"
gt pr create --draft  # Create as draft

# List PRs
gt pr list
gt pr list --state open --label bug

# Checkout PR locally
gt pr checkout 123

# View PR
gt pr view
gt pr view --web

# Merge PR
gt pr merge 123 --squash
gt pr merge 123 --rebase

# Review PR
gt pr review --approve
gt pr review --request-changes --body "Fix the tests"
```

### Issues

```bash
# Create issue
gt issue create --title "Bug" --body "Description"
gt issue create --label bug --project "Backlog"

# List issues
gt issue list
gt issue list --state open --assignee @me

# View issue
gt issue view 123
gt issue view --web

# Close issue
gt issue close 123 --comment "Fixed in PR #456"
```

---

## 🧪 Advanced Usage

### Scripting with gh CLI

```bash
#!/bin/bash
# Example: Deploy and notify

REPO="owner/azure-governance-platform"

# Trigger deployment
gh workflow run deploy-dev.yml --repo "$REPO" --ref dev

# Wait for completion
sleep 5
RUN_ID=$(gh run list --repo "$REPO" --branch dev --limit 1 --json databaseId -q '.[0].databaseId')
gh run watch "$RUN_ID" --repo "$REPO"

# Check result
STATUS=$(gh run view "$RUN_ID" --repo "$REPO" --json conclusion -q '.conclusion')

if [[ "$STATUS" == "success" ]]; then
    echo "✅ Deployment successful!"
    # Notify Slack, etc.
else
    echo "❌ Deployment failed!"
    exit 1
fi
```

### Batch Operations

```bash
# Set multiple secrets from file
while IFS='=' read -r key value; do
    echo "$value" | gh secret set "$key"
done < .secrets

# Update all workflows to use new secret
for workflow in $(gh workflow list --json name -q '.[].name'); do
    echo "Checking: $workflow"
done
```

### JSON Output for Automation

```bash
# Get structured data
gh run list --json databaseId,status,conclusion,createdAt

# Parse with jq
gh run list --json databaseId,status | jq '.[] | select(.status == "in_progress")'

# Get specific fields
gh secret list --json name | jq -r '.[].name'
```

---

## 🔒 Security Best Practices

### Token Management

```bash
# Use fine-grained tokens when possible
gh auth login --scopes "repo,workflow,write:packages"

# View current scopes
gh auth status

# Revoke token if needed
gt auth logout

# For CI/CD, use GitHub Apps or fine-grained tokens
# Never commit tokens to repository!
```

### Secret Handling

```bash
# Good: Pipe secret value
echo "$AZURE_CLIENT_ID" | gh secret set AZURE_CLIENT_ID

# Good: From environment variable
gh secret set API_KEY --body "$API_KEY"

# Bad: Command line exposure (may be logged)
gh secret set API_KEY --body "actual-secret-value"  # DON'T DO THIS
```

### Branch Protection via CLI

```bash
# Set branch protection rules
gt api repos/owner/repo/branches/main/protection \
  --method PUT \
  --input - <<< '{
    "required_status_checks": null,
    "enforce_admins": false,
    "required_pull_request_reviews": {
      "required_approving_review_count": 1,
      "dismiss_stale_reviews": true
    },
    "restrictions": null,
    "allow_force_pushes": false,
    "allow_deletions": false
  }'
```

---

## 🐛 Troubleshooting

### Authentication Issues

```bash
# Re-authenticate
gh auth logout
gh auth login

# Check token expiration
gh auth status

# Refresh token
gh auth refresh
```

### Permission Errors

```bash
# Check scopes
gt auth status

# Re-authenticate with more scopes
gh auth login --scopes "repo,workflow,admin:repo_hook"
```

### API Rate Limits

```bash
# Check rate limit
gt api rate_limit

# Use pagination for large lists
gt run list --limit 1000
```

### Script Debugging

```bash
# Enable verbose mode
export GH_DEBUG=api
./scripts/gh-setup.sh

# Or for specific command
gh run list --verbose
```

---

## 📊 Cheat Sheet

| Task | Command |
|------|---------|
| Login | `gh auth login` |
| Setup repo | `./scripts/gh-setup.sh` |
| Deploy to dev | `./scripts/gh-deploy-dev.sh` |
| Check status | `./scripts/gh-status.sh` |
| Rotate secret | `./scripts/gh-secret-rotate.sh NAME -g` |
| Setup OIDC | `./scripts/gh-oidc-setup.sh` |
| Setup tenants | `./scripts/gh-tenants-setup.sh` |
| List tenants | `./scripts/gh-tenants-list.sh` |
| Sync tenants | `./scripts/gh-tenants-sync.sh [tenant]` |
| List workflows | `gh workflow list` |
| Trigger workflow | `gh workflow run deploy-dev.yml` |
| Watch deployment | `gh run watch` |
| List secrets | `gh secret list` |
| Set secret | `echo "val" \| gh secret set NAME` |
| Create PR | `gh pr create --title "X" --body "Y"` |
| Merge PR | `gh pr merge 123 --squash` |
| View logs | `gh run view --log` |

---

## 🔗 Related Documentation

| Document | Description |
|----------|-------------|
| [GITHUB_SECRETS_SETUP.md](./GITHUB_SECRETS_SETUP.md) | Detailed secret configuration |
| [OIDC_SETUP.md](./OIDC_SETUP.md) | OIDC federation deep dive |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | Full deployment guide |
| [DEVELOPMENT.md](./DEVELOPMENT.md) | Development setup |

---

## 📚 Resources

- [GitHub CLI Manual](https://cli.github.com/manual/)
- [gh GitHub Repository](https://github.com/cli/cli)
- [GitHub Actions OIDC](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-azure)

---

*Last updated: February 2025*

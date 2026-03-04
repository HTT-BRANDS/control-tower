# Scripts Index

Quick reference for all automation scripts in this repository.

## 🚀 Quick Start (GitHub CLI)

Get up and running with GitHub CLI automation in 4 steps:

```bash
# 1. Setup GitHub environments and secrets
./scripts/gh-setup.sh

# 2. Configure Riverside tenants
./scripts/gh-tenants-setup.sh

# 3. Deploy to dev environment
./scripts/gh-deploy-dev.sh

# 4. Verify the deployment
./scripts/verify-dev-deployment.sh
```

---

## 🔧 GitHub CLI Scripts

### Core Setup & Configuration
| Script | Purpose | Key Features |
|--------|---------|--------------|
| `gh-setup.sh` | Setup environments and secrets | Creates dev/prod envs, validates secrets, interactive prompts |
| `gh-oidc-setup.sh` | OIDC federation setup | Federated identity with Azure, app registrations, service principals |
| `gh-secret-rotate.sh` | Rotate secrets | Time-based rotation, backup before rotation, audit trail |

### Deployment & Status
| Script | Purpose | Key Features |
|--------|---------|--------------|
| `gh-deploy-dev.sh` | Deploy to dev branch | Triggers workflow, monitors run, dev-first pipeline |
| `gh-status.sh` | View repository status | Shows secrets, variables, environments, clean overview |

### Tenant Management (Riverside)
| Script | Purpose | Key Features |
|--------|---------|--------------|
| `gh-tenants-setup.sh` | Configure Riverside tenants | Interactive tenant setup, API config, test connectivity |
| `gh-tenants-list.sh` | List tenant configuration | Displays tenant IDs, API endpoints, sync status |
| `gh-tenants-sync.sh` | Trigger tenant sync | Kinds sync workflow dispatch |

---

## 📋 Azure App Registration Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `setup-riverside-apps.py` | Manage app registrations across tenants | `python setup-riverside-apps.py --check-only` |
| `verify-azure-apps.sh` | Quick verification of all apps | `./verify-azure-apps.sh` |

### Setup Script Features
- ✅ Check existing app registrations
- ✅ Verify Microsoft Graph permissions
- ✅ Verify Azure Management permissions
- ✅ Generate new client secrets
- ✅ Output credentials to `.env.azure`
- ✅ Support for all 5 Riverside tenants

### Verify Script Features
- ✅ Check app exists and is enabled
- ✅ Verify admin consent status
- ✅ JSON output support
- ✅ Per-tenant or all-tenants mode

## 📋 Other Scripts

| Script | Purpose |
|--------|---------|
| `deploy-dev.sh` | Legacy deployment script |
| `setup.sh` | Initial repository setup |
| `setup-azure.sh` | Azure resource setup |
| `verify-dev-deployment.sh` | Verify dev deployment health |
| `run_preflight.py` | Preflight security checks |
| `init_riverside_db.py` | Initialize Riverside database |
| `seed_data.py` | Seed test data |

---

## 📚 Documentation

- **[docs/GITHUB_CLI_GUIDE.md](../docs/GITHUB_CLI_GUIDE.md)** - Complete gh CLI documentation
- **[docs/TENANT_SETUP.md](../docs/TENANT_SETUP.md)** - Azure AD tenant setup
- **[docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md)** - Deployment architecture
- **[docs/OIDC_SETUP.md](../docs/OIDC_SETUP.md)** - OIDC configuration

---

## 🎯 One-Liner Commands by Phase

### Phase 1: Initial Setup
```bash
./scripts/gh-setup.sh && ./scripts/gh-oidc-setup.sh
```

### Phase 2: Tenant Configuration
```bash
./scripts/gh-tenants-setup.sh && ./scripts/gh-tenants-list.sh
```

### Phase 3: Deploy & Verify
```bash
./scripts/gh-deploy-dev.sh && ./scripts/verify-dev-deployment.sh
```

### Phase 4: Monitoring
```bash
./scripts/gh-status.sh && ./scripts/gh-tenants-sync.sh
```

---

## 🔐 Prerequisites

All GitHub CLI scripts require:
- [GitHub CLI](https://cli.github.com/) installed and authenticated
- Azure CLI (`az`) installed and logged in
- Proper repository permissions (repo admin or maintainer)

Run `gh auth status` to verify you're logged in.

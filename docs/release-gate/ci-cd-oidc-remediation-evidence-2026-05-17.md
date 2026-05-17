# CI/CD OIDC Remediation Evidence — 2026-05-17

> **Purpose:** Read-only baseline for bd `ct-90r.1` before any destructive Azure/GitHub remediation.
> **Collector:** `code-puppy-1c7422` on behalf of Tyler Granlund.
> **Scope:** GitHub Actions OIDC, Entra federated credentials, GitHub environments, branch protection, RBAC, and tenant secret-name inventory.
> **Secret handling:** GitHub secret *values* were not read. This bundle records secret names only.

---

## Executive summary

| Finding | Evidence status | Remediation bead |
|---|---|---|
| Shared OIDC app registration spans environments | Confirmed: `azure-governance-platform-oidc-dev` / `3184145f-dab3-4f22-8cd4-4b8a11eea6ed` | `ct-90r.8`, `ct-90r.9` |
| Stale old-repo federated credentials | Confirmed: 10 subjects reference `HTT-BRANDS/azure-governance-platform` | `ct-90r.2` |
| Current control-tower FICs exist | Confirmed: 5 subjects reference `HTT-BRANDS/control-tower` | `ct-90r.2` validation guard |
| Contributor on staging/prod RGs | Confirmed in RBAC inventory | `ct-90r.10` |
| Ghost GitHub environments | Confirmed: production-production, production-staging, staging-production, staging-staging | `ct-90r.5` |
| Production `skip_tests` input | Confirmed by workflow grep | `ct-90r.6` |
| Branch protection lacks PR review/admin enforcement | Confirmed: PR reviews = `None`, admin enforcement = `False` | `ct-90r.7` |
| BCC/FN/TLL repo secrets exist; no active consumer found in app/workflow grep | Confirmed as investigation starting state | `ct-90r.12`, `ct-90r.13` |

---

## Azure account context

```json
{
  "id": "32a28177-6fb2-4668-a528-6d6cafb9665e",
  "name": "HTT-CORE",
  "tenantId": "0c0e35dc-188a-4eb3-b8ba-61752154b407",
  "user": "tyler.granlund-admin@httbrands.com"
}
```

## App registration

```json
{
  "appId": "3184145f-dab3-4f22-8cd4-4b8a11eea6ed",
  "displayName": "azure-governance-platform-oidc-dev",
  "objectId": "dfb9e2e4-e68b-4a47-89e3-3e8b626ea208",
  "signInAudience": "AzureADMyOrg"
}
```

## Federated identity credentials

| Name | Subject | Issuer |
|---|---|---|
| github-actions-control-tower-production-backup | repo:HTT-BRANDS/control-tower:environment:production-backup | https://token.actions.githubusercontent.com |
| github-actions-control-tower-pr | repo:HTT-BRANDS/control-tower:pull_request | https://token.actions.githubusercontent.com |
| github-actions-control-tower-main | repo:HTT-BRANDS/control-tower:ref:refs/heads/main | https://token.actions.githubusercontent.com |
| github-actions-control-tower-production | repo:HTT-BRANDS/control-tower:environment:production | https://token.actions.githubusercontent.com |
| github-actions-control-tower-staging | repo:HTT-BRANDS/control-tower:environment:staging | https://token.actions.githubusercontent.com |
| environment-staging-production | repo:HTT-BRANDS/azure-governance-platform:environment:staging-production | https://token.actions.githubusercontent.com |
| environment-staging-staging | repo:HTT-BRANDS/azure-governance-platform:environment:staging-staging | https://token.actions.githubusercontent.com |
| environment-production-production | repo:HTT-BRANDS/azure-governance-platform:environment:production-production | https://token.actions.githubusercontent.com |
| environment-production-staging | repo:HTT-BRANDS/azure-governance-platform:environment:production-staging | https://token.actions.githubusercontent.com |
| staging-branch | repo:HTT-BRANDS/azure-governance-platform:ref:refs/heads/staging | https://token.actions.githubusercontent.com |
| environment-staging | repo:HTT-BRANDS/azure-governance-platform:environment:staging | https://token.actions.githubusercontent.com |
| environment-prod | repo:HTT-BRANDS/azure-governance-platform:environment:production | https://token.actions.githubusercontent.com |
| pr-branch | repo:HTT-BRANDS/azure-governance-platform:pull_request | https://token.actions.githubusercontent.com |
| dev-branch | repo:HTT-BRANDS/azure-governance-platform:ref:refs/heads/dev | https://token.actions.githubusercontent.com |
| main-branch | repo:HTT-BRANDS/azure-governance-platform:ref:refs/heads/main | https://token.actions.githubusercontent.com |

### Stale old-repo FIC count

- Stale old-repo FICs: **10**
- Current `control-tower` FICs: **5**

## Azure RBAC assignments for app registration

| Role | Scope |
|---|---|
| Website Contributor | /subscriptions/32a28177-6fb2-4668-a528-6d6cafb9665e/resourceGroups/rg-governance-dev |
| Web Plan Contributor | /subscriptions/32a28177-6fb2-4668-a528-6d6cafb9665e/resourceGroups/rg-governance-dev |
| Contributor | /subscriptions/32a28177-6fb2-4668-a528-6d6cafb9665e/resourceGroups/rg-governance-staging |
| Contributor | /subscriptions/32a28177-6fb2-4668-a528-6d6cafb9665e/resourceGroups/rg-governance-production |
| Storage Blob Data Contributor | /subscriptions/32a28177-6fb2-4668-a528-6d6cafb9665e/resourceGroups/rg-governance-staging/providers/Microsoft.Storage/storageAccounts/stgovstagingxnczpwyv |
| Storage Blob Data Contributor | /subscriptions/32a28177-6fb2-4668-a528-6d6cafb9665e/resourceGroups/rg-governance-production/providers/Microsoft.Storage/storageAccounts/stgovprodbkup001 |
| Bicep Drift Reader | /subscriptions/32a28177-6fb2-4668-a528-6d6cafb9665e |

## GitHub environments and secret names

| Environment | Ghost candidate | Secret names |
|---|---|---|
| development | no | none |
| github-pages | no | none |
| production | no | AZURE_APP_SERVICE_NAME, AZURE_CLIENT_ID, AZURE_RESOURCE_GROUP, AZURE_STORAGE_ACCOUNT, AZURE_SUBSCRIPTION_ID, AZURE_TENANT_ID, DATABASE_URL |
| production-backup | no | AZURE_CLIENT_ID, AZURE_STORAGE_ACCOUNT, AZURE_SUBSCRIPTION_ID, AZURE_TENANT_ID, DATABASE_URL |
| production-production | yes | none |
| production-staging | yes | none |
| staging | no | AZURE_CLIENT_ID, AZURE_STORAGE_ACCOUNT, AZURE_SUBSCRIPTION_ID, AZURE_TENANT_ID, DATABASE_URL, SQL_ADMIN_PASSWORD |
| staging-production | yes | none |
| staging-staging | yes | none |

## Repo-level secret and variable names

### Repo secrets

```text
AZURE_APP_SERVICE_NAME
AZURE_CLIENT_ID
AZURE_RESOURCE_GROUP
AZURE_SUBSCRIPTION_ID
AZURE_TENANT_ID
BCC_CLIENT_ID
BCC_TENANT_ID
FN_CLIENT_ID
FN_TENANT_ID
GHCR_PAT
STAGING_ADMIN_KEY
TLL_CLIENT_ID
TLL_TENANT_ID
```

### Repo variables

```text
AZURE_WEBAPP_NAME
RESOURCE_GROUP
```

## Main branch protection snapshot

| Property | Value |
|---|---|
| Required status checks strict | `True` |
| Required checks | `Browser Smoke, Security Scan` |
| Required pull request reviews | `None` |
| Admin enforcement | `False` |
| Force pushes allowed | `False` |
| Branch deletion allowed | `False` |

## Recent deployment workflow runs

### Production

```json
[
  {
    "conclusion": "success",
    "createdAt": "2026-04-30T22:44:38Z",
    "databaseId": 25193020385,
    "event": "workflow_dispatch",
    "headBranch": "main",
    "headSha": "9ccd870...",
    "status": "completed",
    "url": "https://github.com/HTT-BRANDS/control-tower/actions/runs/25193020385"
  },
  {
    "conclusion": "failure",
    "createdAt": "2026-04-30T22:20:18Z",
    "databaseId": 25192183149,
    "event": "workflow_dispatch",
    "headBranch": "main",
    "headSha": "ec9658f...",
    "status": "completed",
    "url": "https://github.com/HTT-BRANDS/control-tower/actions/runs/25192183149"
  },
  {
    "conclusion": "success",
    "createdAt": "2026-04-29T20:21:53Z",
    "databaseId": 25131829042,
    "event": "workflow_dispatch",
    "headBranch": "main",
    "headSha": "3c9c317...",
    "status": "completed",
    "url": "https://github.com/HTT-BRANDS/control-tower/actions/runs/25131829042"
  },
  {
    "conclusion": "failure",
    "createdAt": "2026-04-26T16:36:54Z",
    "databaseId": 24961635696,
    "event": "workflow_dispatch",
    "headBranch": "main",
    "headSha": "a929791...",
    "status": "completed",
    "url": "https://github.com/HTT-BRANDS/control-tower/actions/runs/24961635696"
  },
  {
    "conclusion": "failure",
    "createdAt": "2026-04-24T02:37:03Z",
    "databaseId": 24869349736,
    "event": "workflow_dispatch",
    "headBranch": "main",
    "headSha": "0fb6d17...",
    "status": "completed",
    "url": "https://github.com/HTT-BRANDS/control-tower/actions/runs/24869349736"
  }
]
```

### Staging

```json
[
  {
    "conclusion": "success",
    "createdAt": "2026-05-17T21:49:50Z",
    "databaseId": 26003695371,
    "event": "push",
    "headBranch": "main",
    "headSha": "1235586...",
    "status": "completed",
    "url": "https://github.com/HTT-BRANDS/control-tower/actions/runs/26003695371"
  },
  {
    "conclusion": "success",
    "createdAt": "2026-05-04T21:08:58Z",
    "databaseId": 25343662220,
    "event": "push",
    "headBranch": "main",
    "headSha": "48fbf1a...",
    "status": "completed",
    "url": "https://github.com/HTT-BRANDS/control-tower/actions/runs/25343662220"
  },
  {
    "conclusion": "cancelled",
    "createdAt": "2026-05-04T21:07:38Z",
    "databaseId": 25343604547,
    "event": "push",
    "headBranch": "main",
    "headSha": "4e20afc...",
    "status": "completed",
    "url": "https://github.com/HTT-BRANDS/control-tower/actions/runs/25343604547"
  },
  {
    "conclusion": "success",
    "createdAt": "2026-05-04T20:48:36Z",
    "databaseId": 25342746400,
    "event": "push",
    "headBranch": "main",
    "headSha": "349f00e...",
    "status": "completed",
    "url": "https://github.com/HTT-BRANDS/control-tower/actions/runs/25342746400"
  },
  {
    "conclusion": "success",
    "createdAt": "2026-05-04T20:35:42Z",
    "databaseId": 25342138404,
    "event": "push",
    "headBranch": "main",
    "headSha": "56420b2...",
    "status": "completed",
    "url": "https://github.com/HTT-BRANDS/control-tower/actions/runs/25342138404"
  }
]
```

## Static workflow/code search excerpt

Command:

```bash
rg -n "skip_tests|azure/login|environment:|AZURE_CLIENT_ID|BCC_CLIENT_ID|FN_CLIENT_ID|TLL_CLIENT_ID|BCC_TENANT_ID|FN_TENANT_ID|TLL_TENANT_ID|production-production|production-staging|staging-production|staging-staging|production-backup|HTT-BRANDS/azure-governance-platform" .github app infrastructure scripts config docs control-tower
```

First 120 matches:

```text
control-tower/Ops/CI-CD/GitHub-Environments.md:11:> 9 environments exist. Only 3 + `github-pages` + `production-backup` are referenced by current workflows. The other 4 are sprawl from earlier infra runs — see [[Findings-and-Drift#P1-GitHub-environment-sprawl]].
control-tower/Ops/CI-CD/GitHub-Environments.md:20:| `production-backup` | (matching federated cred exists) | none | 🟡 intentional? confirm |
control-tower/Ops/CI-CD/GitHub-Environments.md:22:| `production-production` | nothing | none | ❌ sprawl |
control-tower/Ops/CI-CD/GitHub-Environments.md:23:| `production-staging` | nothing | none | ❌ sprawl |
control-tower/Ops/CI-CD/GitHub-Environments.md:24:| `staging-production` | nothing | none | ❌ sprawl |
control-tower/Ops/CI-CD/GitHub-Environments.md:25:| `staging-staging` | nothing | none | ❌ sprawl |
control-tower/Ops/CI-CD/GitHub-Environments.md:31:| `AZURE_CLIENT_ID` | 2026-03-05 | almost certainly `3184145f-...` (dev app reg) |
control-tower/Ops/CI-CD/GitHub-Environments.md:36:| `BCC_CLIENT_ID` / `BCC_TENANT_ID` | 2026-03-26 | BCC sibling tenant — see [[Multi-Tenant-Followup]] |
control-tower/Ops/CI-CD/GitHub-Environments.md:37:| `FN_CLIENT_ID` / `FN_TENANT_ID` | 2026-03-26 | FN sibling tenant |
control-tower/Ops/CI-CD/GitHub-Environments.md:38:| `TLL_CLIENT_ID` / `TLL_TENANT_ID` | 2026-03-26 | TLL sibling tenant |
control-tower/Ops/CI-CD/GitHub-Environments.md:49:> ⚠️ These repo-level vars are **production values** sitting at repo scope. Any job that doesn't declare `environment:` will get these. Consider scoping them under the `production` environment.
control-tower/Ops/CI-CD/GitHub-Environments.md:61:| `AZURE_CLIENT_ID` |
control-tower/Ops/CI-CD/GitHub-Environments.md:72:| `AZURE_CLIENT_ID` |
control-tower/Ops/CI-CD/Runbook-Rotate-and-Recover.md:36:2. **Tighten subjects** to add `environment:` qualifier instead of branch refs where possible. Environment-scoped subjects are gated by GH environment protection rules (required reviewers, branch policy).
control-tower/Ops/CI-CD/Runbook-Rotate-and-Recover.md:46:  "subject": "repo:HTT-BRANDS/control-tower:environment:<env>",
control-tower/Ops/CI-CD/Runbook-Rotate-and-Recover.md:82:6. **Update GitHub env-scoped `AZURE_CLIENT_ID` secrets** to the new client IDs.
control-tower/Ops/CI-CD/Runbook-Rotate-and-Recover.md:123:    "subject": "repo:HTT-BRANDS/control-tower:environment:qa",
control-tower/Ops/CI-CD/Runbook-Rotate-and-Recover.md:129:gh secret set AZURE_CLIENT_ID       --env qa --repo HTT-BRANDS/control-tower --body "<client-id>"
control-tower/Ops/CI-CD/GitHub-OIDC-Federation.md:21:  │  (job declares: environment: staging | production)
control-tower/Ops/CI-CD/GitHub-OIDC-Federation.md:24:       e.g. "repo:HTT-BRANDS/control-tower:environment:staging"
control-tower/Ops/CI-CD/GitHub-OIDC-Federation.md:26:  ▼  azure/login@v2 sends token to
control-tower/Ops/CI-CD/GitHub-OIDC-Federation.md:47:| 3 | `github-actions-control-tower-staging` | `repo:HTT-BRANDS/control-tower:environment:staging` |
control-tower/Ops/CI-CD/GitHub-OIDC-Federation.md:48:| 4 | `github-actions-control-tower-production` | `repo:HTT-BRANDS/control-tower:environment:production` |
control-tower/Ops/CI-CD/GitHub-OIDC-Federation.md:49:| 5 | `github-actions-control-tower-production-backup` | `repo:HTT-BRANDS/control-tower:environment:production-backup` |
control-tower/Ops/CI-CD/GitHub-OIDC-Federation.md:51:### ❌ Stale — old repo name `HTT-BRANDS/azure-governance-platform` (10) — DELETE
control-tower/Ops/CI-CD/GitHub-OIDC-Federation.md:55:| 6 | `main-branch` | `repo:HTT-BRANDS/azure-governance-platform:ref:refs/heads/main` |
control-tower/Ops/CI-CD/GitHub-OIDC-Federation.md:56:| 7 | `dev-branch` | `repo:HTT-BRANDS/azure-governance-platform:ref:refs/heads/dev` |
control-tower/Ops/CI-CD/GitHub-OIDC-Federation.md:57:| 8 | `staging-branch` | `repo:HTT-BRANDS/azure-governance-platform:ref:refs/heads/staging` |
control-tower/Ops/CI-CD/GitHub-OIDC-Federation.md:58:| 9 | `pr-branch` | `repo:HTT-BRANDS/azure-governance-platform:pull_request` |
control-tower/Ops/CI-CD/GitHub-OIDC-Federation.md:59:| 10 | `environment-staging` | `repo:HTT-BRANDS/azure-governance-platform:environment:staging` |
control-tower/Ops/CI-CD/GitHub-OIDC-Federation.md:60:| 11 | `environment-prod` | `repo:HTT-BRANDS/azure-governance-platform:environment:production` |
control-tower/Ops/CI-CD/GitHub-OIDC-Federation.md:61:| 12 | `environment-staging-staging` | `repo:HTT-BRANDS/azure-governance-platform:environment:staging-staging` |
control-tower/Ops/CI-CD/GitHub-OIDC-Federation.md:62:| 13 | `environment-staging-production` | `repo:HTT-BRANDS/azure-governance-platform:environment:staging-production` |
control-tower/Ops/CI-CD/GitHub-OIDC-Federation.md:63:| 14 | `environment-production-staging` | `repo:HTT-BRANDS/azure-governance-platform:environment:production-staging` |
control-tower/Ops/CI-CD/GitHub-OIDC-Federation.md:64:| 15 | `environment-production-production` | `repo:HTT-BRANDS/azure-governance-platform:environment:production-production` |
control-tower/Ops/CI-CD/GitHub-OIDC-Federation.md:77:| Job with `environment: X` | `repo:OWNER/REPO:environment:X` |
control-tower/Ops/CI-CD/Findings-and-Drift.md:19:**Why it matters.** Each of these federated credentials trusts a *repo path that no longer belongs to you* (`HTT-BRANDS/azure-governance-platform`). If someone else creates a repo at that path under the org (or the org allows external forks), they could obtain Azure tokens for this app's service principal — which currently has `Contributor` on staging and production resource groups.
control-tower/Ops/CI-CD/Findings-and-Drift.md:33:  environment-staging-staging
control-tower/Ops/CI-CD/Findings-and-Drift.md:34:  environment-staging-production
control-tower/Ops/CI-CD/Findings-and-Drift.md:35:  environment-production-staging
control-tower/Ops/CI-CD/Findings-and-Drift.md:36:  environment-production-production
control-tower/Ops/CI-CD/Findings-and-Drift.md:80:# Then for each new app, update GH env-scoped AZURE_CLIENT_ID:
control-tower/Ops/CI-CD/Findings-and-Drift.md:81:gh secret set AZURE_CLIENT_ID --env staging --repo HTT-BRANDS/control-tower --body "<new-staging-client-id>"
control-tower/Ops/CI-CD/Findings-and-Drift.md:82:gh secret set AZURE_CLIENT_ID --env production --repo HTT-BRANDS/control-tower --body "<new-prod-client-id>"
control-tower/Ops/CI-CD/Findings-and-Drift.md:120:`production-production`, `production-staging`, `staging-production`, `staging-staging` aren't referenced by any current workflow.
control-tower/Ops/CI-CD/Findings-and-Drift.md:126:for env in production-production production-staging staging-production staging-staging; do
control-tower/Ops/CI-CD/Findings-and-Drift.md:137:`infrastructure/.oidc-config-dev.json` records `"githubRepo": "HTT-BRANDS/azure-governance-platform"`.
control-tower/Ops/CI-CD/Findings-and-Drift.md:144:sed -i '' 's|HTT-BRANDS/azure-governance-platform|HTT-BRANDS/control-tower|g' \
scripts/check-github-secrets.sh:80:        "AZURE_CLIENT_ID"
scripts/check-github-secrets.sh:159:        echo "   AZURE_CLIENT_ID:     Your App Registration ID"
scripts/check-github-secrets.sh:164:        echo "   gh secret set AZURE_CLIENT_ID --repo $REPO"
control-tower/Ops/CI-CD/Pipeline-Workflow.md:11:> Both `deploy-staging.yml` and `deploy-production.yml` use `azure/login@v2` with the same secret names. The right values are pulled from the right env-scoped secrets *because the deploy job declares `environment:`*.
control-tower/Ops/CI-CD/Pipeline-Workflow.md:18:| Job declaring `environment:` | `deploy` (line ~226) — `environment: staging` |
control-tower/Ops/CI-CD/Pipeline-Workflow.md:19:| OIDC login | line 288, `azure/login@v2` |
control-tower/Ops/CI-CD/Pipeline-Workflow.md:33:environment: staging
control-tower/Ops/CI-CD/Pipeline-Workflow.md:36:  uses: azure/login@v2
control-tower/Ops/CI-CD/Pipeline-Workflow.md:38:    client-id:       ${{ secrets.AZURE_CLIENT_ID }}       # ← staging env-scoped
control-tower/Ops/CI-CD/Pipeline-Workflow.md:43:The matching federated credential subject must be: `repo:HTT-BRANDS/control-tower:environment:staging` ✅ exists (cred #3).
control-tower/Ops/CI-CD/Pipeline-Workflow.md:50:| Job declaring `environment:` | `deploy` (line ~264) — `environment: production` |
control-tower/Ops/CI-CD/Pipeline-Workflow.md:51:| OIDC login | line 482, `azure/login@v2` |
control-tower/Ops/CI-CD/Pipeline-Workflow.md:58:Matching federated credential subject: `repo:HTT-BRANDS/control-tower:environment:production` ✅ exists (cred #4).
control-tower/Ops/CI-CD/Pipeline-Workflow.md:81:- [ ] TODO: audit each Azure-touching workflow's `environment:` declaration to ensure they always hit env-scoped secrets, not repo-level
infrastructure/modules/uami.bicep:50:@allowed(['refs/heads/main', 'refs/heads/staging', 'environment:production', 'environment:staging'])
infrastructure/modules/uami.bicep:242:  AZURE_CLIENT_ID: uami.properties.clientId
.github/workflows/bicep-drift-detection.yml:69:        uses: azure/login@v2
.github/workflows/bicep-drift-detection.yml:71:          client-id:       ${{ secrets.AZURE_CLIENT_ID }}
infrastructure/modules/uami.json:51:        "environment:production",
infrastructure/modules/uami.json:52:        "environment:staging"
infrastructure/modules/uami.json:282:        "AZURE_CLIENT_ID": "[reference(resourceId('Microsoft.ManagedIdentity/userAssignedIdentities', parameters('uamiName')), '2023-01-31').clientId]",
control-tower/Ops/CI-CD/_handoffs/SA-Review-Request.md:55:- **P0** — Stale federated creds for old repo name (`HTT-BRANDS/azure-governance-platform`) — 10 entries, remediation script ready
control-tower/Ops/CI-CD/_handoffs/SA-Review-Request.md:67:| BCC | `BCC_CLIENT_ID`, `BCC_TENANT_ID` | ❌ no |
control-tower/Ops/CI-CD/_handoffs/SA-Review-Request.md:68:| FN | `FN_CLIENT_ID`, `FN_TENANT_ID` | ❌ no |
control-tower/Ops/CI-CD/_handoffs/SA-Review-Request.md:69:| TLL | `TLL_CLIENT_ID`, `TLL_TENANT_ID` | ❌ no |
control-tower/Ops/CI-CD/_handoffs/SA-Review-Request.md:87:- **Q1a.** Given that we don't yet know if BCC/FN/TLL are ARM-bound or Graph-bound, what discovery should we run first? (Suggestion: `grep -rn "BCC_CLIENT_ID\|FN_CLIENT_ID\|TLL_CLIENT_ID" .github/ app/ infrastructure/`)
control-tower/Ops/CI-CD/_handoffs/SA-Review-Request.md:101:- [ ] Subject naming convention — should we standardize on `environment:` claims only (drop `ref:refs/heads/*` creds entirely)?
control-tower/Ops/CI-CD/Multi-Tenant-Followup.md:18:| BCC | `BCC_CLIENT_ID`, `BCC_TENANT_ID` | 2026-03-26 |
control-tower/Ops/CI-CD/Multi-Tenant-Followup.md:19:| FN | `FN_CLIENT_ID`, `FN_TENANT_ID` | 2026-03-26 |
control-tower/Ops/CI-CD/Multi-Tenant-Followup.md:20:| TLL | `TLL_CLIENT_ID`, `TLL_TENANT_ID` | 2026-03-26 |
control-tower/Ops/CI-CD/Multi-Tenant-Followup.md:22:No `_SUBSCRIPTION_ID` secrets exist for BCC/FN/TLL — meaning these are likely used for **token acquisition / Graph calls against those tenants**, not Azure resource deployments. Confirm by searching the codebase for `BCC_CLIENT_ID` etc.
control-tower/Ops/CI-CD/Multi-Tenant-Followup.md:26:- [ ] Identify the consumer(s) of `BCC_*` / `FN_*` / `TLL_*` secrets — `grep -rn "BCC_CLIENT_ID\|FN_CLIENT_ID\|TLL_CLIENT_ID" .github/ app/ infrastructure/`
.github/workflows/topology-diagram.yml:42:      AZURE_CLIENT_ID: ${{ secrets.AZURE_CLIENT_ID }}
.github/workflows/topology-diagram.yml:62:        if: env.AZURE_CLIENT_ID != ''
.github/workflows/topology-diagram.yml:63:        uses: azure/login@v2
.github/workflows/topology-diagram.yml:65:          client-id: ${{ secrets.AZURE_CLIENT_ID }}
.github/workflows/topology-diagram.yml:73:          if [ -z "${AZURE_CLIENT_ID}" ]; then
.github/workflows/topology-diagram.yml:74:            echo "No AZURE_CLIENT_ID secret — running in offline mode."
control-tower/Ops/CI-CD/Overview.md:31:- [[Pipeline-Workflow]] — how `azure/login@v2` is wired in deploy workflows
control-tower/Ops/CI-CD/Overview.md:45:2. **10 of 15 federated credentials point at a stale repo name** (`HTT-BRANDS/azure-governance-platform`). Should be deleted.
control-tower/Ops/CI-CD/Overview.md:47:4. **4 ghost GitHub environments** (`production-production`, `production-staging`, `staging-production`, `staging-staging`) — not used by any current workflow.
.github/workflows/bacpac-export.yml:12:      environment:
.github/workflows/bacpac-export.yml:33:    environment: ${{ github.event.inputs.environment || 'production' }}
.github/workflows/bacpac-export.yml:38:        uses: azure/login@v2
.github/workflows/bacpac-export.yml:40:          client-id: ${{ secrets.AZURE_CLIENT_ID }}
.github/workflows/bacpac-export.yml:71:              echo "Unsupported environment: $TARGET_ENV" >&2
app/preflight/tenant_checks.py:516:        print("  - AZURE_CLIENT_ID")
control-tower/Ops/Environments/development.md:5:github_environment: development
control-tower/Ops/Environments/development.md:36:The active creds for `HTT-BRANDS/control-tower` include `main`, `pull_request` — both reach dev when a workflow doesn't set `environment:`. There is **no explicit `environment:development`** federated credential.
control-tower/Ops/Environments/development.md:38:- [ ] Decide whether to add `environment:development` federated cred + env-scoped secrets, or formally retire the `development` GH environment
app/templates/login.html:133:                const resp = await fetch('/api/v1/auth/azure/login');
control-tower/Ops/Environments/staging.md:5:github_environment: staging
control-tower/Ops/Environments/staging.md:34:- `AZURE_CLIENT_ID`
control-tower/Ops/Environments/staging.md:52:`github-actions-control-tower-staging` → `repo:HTT-BRANDS/control-tower:environment:staging` ✅
app/preflight/checks.py:107:                    "Configure AZURE_CLIENT_ID environment variable",
app/preflight/checks.py:431:                    recommendations=["Check AZURE_CLIENT_ID and AZURE_CLIENT_SECRET"],
control-tower/Ops/Environments/production.md:5:github_environment: production
control-tower/Ops/Environments/production.md:34:- `AZURE_CLIENT_ID`
control-tower/Ops/Environments/production.md:56:`github-actions-control-tower-production` → `repo:HTT-BRANDS/control-tower:environment:production` ✅
control-tower/Ops/Environments/production.md:58:There is also a separate cred `github-actions-control-tower-production-backup` → `environment:production-backup`. Confirm the `backup.yml` workflow uses `environment: production-backup` to pick it up.
.github/workflows/backup.yml:21:      environment:
.github/workflows/backup.yml:32:  id-token: write # Required by azure/login@v2 OIDC federation.
.github/workflows/backup.yml:45:    # repo:HTT-BRANDS/control-tower:environment:production-backup
.github/workflows/backup.yml:46:    environment: ${{ (github.event.inputs.environment || 'production') == 'production' && 'production-backup' || 'staging' }}
.github/workflows/backup.yml:70:        uses: azure/login@v2
.github/workflows/backup.yml:72:          client-id: ${{ secrets.AZURE_CLIENT_ID }}
.github/workflows/backup.yml:85:            *) echo "Unsupported backup environment: $BACKUP_ENVIRONMENT" >&2; exit 1 ;;
.github/workflows/backup.yml:218:    environment: staging
.github/workflows/backup.yml:242:        uses: azure/login@v2
.github/workflows/backup.yml:244:          client-id: ${{ secrets.AZURE_CLIENT_ID }}
control-tower/Ops/_templates/env.md:5:github_environment: <…>
control-tower/Ops/_templates/env.md:33:- `AZURE_CLIENT_ID`
```

---

## Validation command receipts

Read-only commands used:

```bash
az account show --query '{name:name,id:id,tenantId:tenantId,user:user.name}' -o json
az ad app show --id 3184145f-dab3-4f22-8cd4-4b8a11eea6ed --query '{displayName:displayName, appId:appId, objectId:id, signInAudience:signInAudience}' -o json
az ad app federated-credential list --id 3184145f-dab3-4f22-8cd4-4b8a11eea6ed --query '[].{name:name, subject:subject, issuer:issuer, audiences:audiences}' -o json
az role assignment list --assignee 3184145f-dab3-4f22-8cd4-4b8a11eea6ed --all --query '[].{role:roleDefinitionName, scope:scope}' -o json
gh api repos/HTT-BRANDS/control-tower/environments
gh secret list --repo HTT-BRANDS/control-tower
gh variable list --repo HTT-BRANDS/control-tower
gh api repos/HTT-BRANDS/control-tower/branches/main/protection
gh run list --repo HTT-BRANDS/control-tower --workflow deploy-production.yml --limit 5 --json databaseId,status,conclusion,headBranch,headSha,event,createdAt,url
gh run list --repo HTT-BRANDS/control-tower --workflow deploy-staging.yml --limit 5 --json databaseId,status,conclusion,headBranch,headSha,event,createdAt,url
```

No destructive commands were executed for this evidence baseline.

---

## Post-remediation receipt — ct-90r.2 stale federated credentials

**Timestamp:** 2026-05-17T22:13:59Z  
**Actor:** code-puppy-1c7422  
**Change:** Deleted 10 stale federated credentials whose subjects referenced `HTT-BRANDS/azure-governance-platform`.

### Post-delete validation

- Remaining old-repo FIC count: **0**
- Current `HTT-BRANDS/control-tower` FIC count: **5**

Current retained FICs:

```json
[
  {
    "name": "github-actions-control-tower-production-backup",
    "subject": "repo:HTT-BRANDS/control-tower:environment:production-backup"
  },
  {
    "name": "github-actions-control-tower-pr",
    "subject": "repo:HTT-BRANDS/control-tower:pull_request"
  },
  {
    "name": "github-actions-control-tower-main",
    "subject": "repo:HTT-BRANDS/control-tower:ref:refs/heads/main"
  },
  {
    "name": "github-actions-control-tower-production",
    "subject": "repo:HTT-BRANDS/control-tower:environment:production"
  },
  {
    "name": "github-actions-control-tower-staging",
    "subject": "repo:HTT-BRANDS/control-tower:environment:staging"
  }
]
```

Validation command shape:

```bash
az ad app federated-credential list --id 3184145f-dab3-4f22-8cd4-4b8a11eea6ed --query "length([?contains(subject, 'HTT-BRANDS/azure-governance-platform')])" -o tsv
az ad app federated-credential list --id 3184145f-dab3-4f22-8cd4-4b8a11eea6ed --query "[?contains(subject, 'HTT-BRANDS/control-tower')].{name:name, subject:subject}" -o json
```

---

## Remediation receipt — ct-90r.9 per-environment OIDC identities

**Timestamp:** 2026-05-17T22:29:18Z  
**Actor:** code-puppy-1c7422

### Created / configured identities

| Environment | App registration | Client ID | Federated subject | GitHub env secret |
|---|---|---|---|---|
| staging | control-tower-oidc-staging | 71ed6019-5d5a-4ba7-acc2-e9f6c536579a | `repo:HTT-BRANDS/control-tower:environment:staging` | `staging/AZURE_CLIENT_ID` updated |
| production | control-tower-oidc-production | b4959810-4b43-4887-9458-37a78af2d01d | `repo:HTT-BRANDS/control-tower:environment:production` | `production/AZURE_CLIENT_ID` updated |

### RBAC assigned

- Staging app: Website Contributor, Web Plan Contributor, Monitoring Contributor on `rg-governance-staging`.
- Production app: Website Contributor, Web Plan Contributor, Monitoring Contributor, Key Vault Secrets User on `rg-governance-production`.
- No staging roles were assigned to the production app.
- No production roles were assigned to the staging app.

### Runtime validation

- Staging workflow dispatch: https://github.com/HTT-BRANDS/control-tower/actions/runs/26004314666
- Staging Azure Login OIDC: **passed** with subject `repo:HTT-BRANDS/control-tower:environment:staging`.
- Staging deploy job: **passed**.
- Staging validation tests: initial transient `/openapi.json` read timeout, rerun **passed**.
- Direct `/openapi.json` check after deploy: HTTP 200, valid JSON.
- Production runtime deploy/login validation: **pending explicit production deployment approval/window**.


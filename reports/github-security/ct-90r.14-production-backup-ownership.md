# ct-90r.14 production-backup OIDC/environment ownership evidence

Captured: 2026-05-18T15:15:00Z

## Decision

Retain `production-backup` as an intentional GitHub environment.

Rationale: `.github/workflows/backup.yml` maps production database backups to a
dedicated approval-free environment so scheduled backups are not blocked by the
human approval gate on the deployment-oriented `production` environment.

```yaml
# Required OIDC subject:
# repo:HTT-BRANDS/control-tower:environment:production-backup
environment: ${{ (github.event.inputs.environment || 'production') == 'production' && 'production-backup' || 'staging' }}
```

## GitHub environment state

```json
{
  "name": "production-backup",
  "created_at": "2026-05-01T17:12:23Z",
  "updated_at": "2026-05-01T17:12:23Z",
  "can_admins_bypass": true,
  "protection_rules": [],
  "deployment_branch_policy": null
}
```

The empty `protection_rules` list is intentional for scheduled backups: adding
reviewers would block the daily 02:00 UTC production backup.

## Environment secret names

Secret values were not read.

```text
AZURE_CLIENT_ID
AZURE_STORAGE_ACCOUNT
AZURE_SUBSCRIPTION_ID
AZURE_TENANT_ID
DATABASE_URL
```

## Matching Azure federated identity credential

```json
[
  {
    "issuer": "https://token.actions.githubusercontent.com",
    "name": "github-actions-control-tower-production-backup",
    "subject": "repo:HTT-BRANDS/control-tower:environment:production-backup"
  }
]
```

## Latest scheduled backup observation

Latest observed scheduled run:

```text
https://github.com/HTT-BRANDS/control-tower/actions/runs/26011528016
```

Job conclusions:

```text
Production Database Backup: success
Staging Database Backup:    failure
```

The staging failure is separate from `production-backup` ownership. It was filed
as follow-up `ct-oib` because the staging job failed to create a SQL firewall
rule with `AuthorizationFailed` for `Microsoft.Sql/servers/firewallRules/write`.

## Ownership / recovery notes

- Primary owner: Tyler Granlund.
- Purpose: scheduled production database backup OIDC login and backup secret
  scope.
- Keep environment name stable unless `backup.yml` is changed with a matching
  Entra FIC subject update.
- If deleted accidentally, recreate:
  1. GitHub environment `production-backup`.
  2. Environment secrets by name only from Tyler's secret-of-record store.
  3. Entra FIC subject
     `repo:HTT-BRANDS/control-tower:environment:production-backup`.
  4. Run `backup.yml` manually for `environment=production`, preferably
     `backup_type=schema-only` first.

## Validation commands

```bash
gh api repos/HTT-BRANDS/control-tower/environments/production-backup

gh secret list --env production-backup --repo HTT-BRANDS/control-tower

az ad app federated-credential list \
  --id 3184145f-dab3-4f22-8cd4-4b8a11eea6ed \
  --query '[?contains(subject, `production-backup`)].{name:name,subject:subject,issuer:issuer}' \
  -o json
```

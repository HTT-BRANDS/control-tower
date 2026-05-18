# ct-oib staging scheduled backup remediation

Captured: 2026-05-18T16:05:00Z

## Original failure

Scheduled `backup.yml` run `26011528016` failed overall because the staging job
failed in `Prepare SQL firewall`:

```text
Staging Database Backup: failure
Production Database Backup: success
```

Initial failure signature:

```text
AuthorizationFailed on Microsoft.Sql/servers/firewallRules/write
principal/object id: aab735ac-d6ff-4d71-ba78-631fbf482c3c
```

## RBAC remediation applied

The staging OIDC service principal is:

```text
app registration: control-tower-oidc-staging
appId:            71ed6019-5d5a-4ba7-acc2-e9f6c536579a
sp objectId:      aab735ac-d6ff-4d71-ba78-631fbf482c3c
```

Created and assigned narrow custom roles instead of broad Contributor:

```text
Control Tower SQL Firewall Rule Operator
  scope: /subscriptions/32a28177-6fb2-4668-a528-6d6cafb9665e/resourceGroups/rg-governance-staging/providers/Microsoft.Sql/servers/sql-governance-staging-77zfjyem
  actions:
    Microsoft.Resources/subscriptions/resourceGroups/read
    Microsoft.Sql/servers/read
    Microsoft.Sql/servers/firewallRules/read
    Microsoft.Sql/servers/firewallRules/write
    Microsoft.Sql/servers/firewallRules/delete

Control Tower Storage Account Key Reader
  scope: /subscriptions/32a28177-6fb2-4668-a528-6d6cafb9665e/resourceGroups/rg-governance-staging/providers/Microsoft.Storage/storageAccounts/stgovstagingxnczpwyv
  actions:
    Microsoft.Resources/subscriptions/resourceGroups/read
    Microsoft.Storage/storageAccounts/read
    Microsoft.Storage/storageAccounts/listkeys/action
```

## Follow-up validation result

Manual staging backup validation was triggered with:

```bash
gh workflow run backup.yml \
  --repo HTT-BRANDS/control-tower \
  --ref main \
  -f environment=staging \
  -f backup_type=schema-only
```

Run:

```text
https://github.com/HTT-BRANDS/control-tower/actions/runs/26043358566
```

Result: failed earlier than any useful backup because staging `DATABASE_URL` is
not an Azure SQL connection string.

Sanitized failure:

```text
SqlServerNameError: Resolved invalid Azure SQL server name ''; check DATABASE_URL formatting
```

Live staging health confirms staging is currently SQLite-backed:

```json
{
  "status": "degraded",
  "components": {
    "database": "healthy"
  },
  "database_pool": "n/a (SQLite)"
}
```

The staging App Service `DATABASE_URL` setting has length 34 and does not contain
`database.windows.net` by non-secret metadata check. The actual value was not
printed.

## Decision

Retire the scheduled staging SQL backup job while staging uses SQLite.

Rationale:

- The scheduled production backup already runs from the primary `backup` job and
  uses the `production-backup` GitHub environment.
- The old `backup-staging` job assumes Azure SQL and cannot produce a meaningful
  backup for a SQLite database path that exists inside App Service storage, not
  on the GitHub runner.
- Keeping that job enabled creates daily red CI noise and trains humans to ignore
  backup failures. That is how RPOs become decorative.

## Code remediation

`.github/workflows/backup.yml` now keeps the production scheduled backup and
removes the separate `backup-staging` scheduled job.

Manual `workflow_dispatch` still exposes `environment=staging`, but staging is
not considered DR-protected by this SQL backup workflow until staging is moved
back to Azure SQL or a proper App Service/SQLite backup mechanism is designed.

## Future remediation options

If staging must become DR-protected again, choose one explicit model:

1. Move staging back to Azure SQL and keep the narrow RBAC roles above.
2. Add an App Service file/database export flow for SQLite.
3. Treat staging as disposable and document rebuild-from-code/seed-data only.

Do not silently re-enable SQL backup for SQLite. That would be silly. Azure is
already silly enough without our help.

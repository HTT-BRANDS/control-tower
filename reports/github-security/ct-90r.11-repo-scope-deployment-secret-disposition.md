# ct-90r.11 repo-scope deployment secret/variable disposition

Captured: 2026-05-18T16:50:00Z

## Scope

Move deployment-specific GitHub secrets and variables out of repository scope
where safe. Secret values were not read.

## Removed repo-scope configuration

Deleted unused repository-level GitHub Actions secrets:

```text
AZURE_APP_SERVICE_NAME
AZURE_RESOURCE_GROUP
```

Deleted unused repository-level GitHub Actions variables:

```text
AZURE_WEBAPP_NAME
RESOURCE_GROUP
```

These names were not referenced by active workflow files in `.github/workflows`:

```bash
rg -n 'secrets.AZURE_APP_SERVICE_NAME|secrets.AZURE_RESOURCE_GROUP|vars.AZURE_WEBAPP_NAME|vars.RESOURCE_GROUP' .github/workflows
```

Output:

```text
<empty>
```

Post-delete name-only verification also returned empty for those names in repo
secret and variable listings.

## Retained repo-scope secrets

The following repo-level secrets remain intentionally retained for now:

```text
AZURE_CLIENT_ID
AZURE_TENANT_ID
AZURE_SUBSCRIPTION_ID
GHCR_PAT
```

Rationale:

- `deploy-dev.yml` intentionally does not declare `environment: development`
  yet, so it still resolves repo-level Azure OIDC secrets.
- `bicep-drift-detection.yml`, `topology-diagram.yml`, and
  `container-registry-migration.yml` also use repo-level Azure OIDC secrets
  because they do not currently declare staging/production environments.
- `GHCR_PAT` is still used by deploy workflows to configure App Service pull
  credentials for GHCR. Removing it would risk restart/re-pull failures.

These retained secrets should be removed only after the workflows above are
migrated to explicit environment-scoped identities or documented as permanently
repo-scoped with least-privilege RBAC.

## Current active consumers found

```text
.github/workflows/deploy-dev.yml
  secrets.AZURE_CLIENT_ID
  secrets.AZURE_TENANT_ID
  secrets.AZURE_SUBSCRIPTION_ID

.github/workflows/bicep-drift-detection.yml
  secrets.AZURE_CLIENT_ID
  secrets.AZURE_TENANT_ID
  secrets.AZURE_SUBSCRIPTION_ID

.github/workflows/topology-diagram.yml
  secrets.AZURE_CLIENT_ID
  secrets.AZURE_TENANT_ID
  secrets.AZURE_SUBSCRIPTION_ID

.github/workflows/container-registry-migration.yml
  secrets.AZURE_CLIENT_ID
  secrets.AZURE_TENANT_ID
  secrets.AZURE_SUBSCRIPTION_ID

.github/workflows/deploy-staging.yml
.github/workflows/deploy-production.yml
  secrets.GHCR_PAT
```

## Follow-up recommendation

Create a follow-up to remove the remaining repo-level Azure OIDC triplet after
one of these is true:

1. Development gets a dedicated `environment: development` FIC and env-scoped
   Azure secrets.
2. Non-deploy Azure workflows are split by environment or use a dedicated
   read-only repo-scope OIDC principal with documented RBAC.
3. Legacy workflows that need broad repo-scope Azure access are retired.

Until then, deleting the remaining repo-level Azure OIDC secrets would be
breakage cosplay. We are trying not to do that today.

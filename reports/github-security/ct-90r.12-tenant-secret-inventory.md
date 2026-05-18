# ct-90r.12 BCC/FN/TLL tenant secret inventory and disposition

Captured: 2026-05-18T15:30:00Z

## Scope

Inventory the repository-level GitHub secret names below and determine whether
they are active, future-use, or orphaned. Secret values were not read.

- `BCC_CLIENT_ID`
- `BCC_TENANT_ID`
- `FN_CLIENT_ID`
- `FN_TENANT_ID`
- `TLL_CLIENT_ID`
- `TLL_TENANT_ID`

## GitHub inventory

Repository-level secret names exist:

```text
BCC_CLIENT_ID    updated 2026-03-26T15:24:07Z
BCC_TENANT_ID    updated 2026-03-26T15:24:08Z
FN_CLIENT_ID     updated 2026-03-26T15:24:07Z
FN_TENANT_ID     updated 2026-03-26T15:24:08Z
TLL_CLIENT_ID    updated 2026-03-26T15:24:07Z
TLL_TENANT_ID    updated 2026-03-26T15:24:08Z
```

No matching BCC/FN/TLL secret names were found in the checked GitHub
environments: `development`, `staging`, `production`, `production-backup`, or
`github-pages`.

## Consumer search results

### GitHub Actions

No active workflow references `secrets.BCC_CLIENT_ID`, `secrets.BCC_TENANT_ID`,
`secrets.FN_CLIENT_ID`, `secrets.FN_TENANT_ID`, `secrets.TLL_CLIENT_ID`, or
`secrets.TLL_TENANT_ID`.

Validated with:

```bash
rg -n 'BCC_|FN_|TLL_|secrets\.' .github/workflows
```

Observed workflow secret consumers use the platform deployment/backup secrets
such as `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`,
`DATABASE_URL`, `AZURE_STORAGE_ACCOUNT`, `SQL_ADMIN_PASSWORD`, and
`PRODUCTION_TEAMS_WEBHOOK`; not the BCC/FN/TLL repo-level tenant secret names.

### Application/runtime

No app code reads `BCC_CLIENT_ID`, `BCC_TENANT_ID`, `FN_CLIENT_ID`,
`FN_TENANT_ID`, `TLL_CLIENT_ID`, or `TLL_TENANT_ID` directly from environment
variables or GitHub secrets.

Current runtime credential resolution is tenant-record / Key Vault oriented:

- `app/api/services/azure_client.py` resolves per-tenant credentials from the DB
  tenant record and `client_secret_ref`, with Key Vault/env fallback for
  `RIVERSIDE_{CODE}_CLIENT_SECRET`.
- `docs/runbooks/enable-secret-fallback.md` documents production use of Key
  Vault secrets like `bcc-client-secret`, `fn-client-secret`, and
  `tll-client-secret`.
- `scripts/migrate-secrets-to-keyvault.sh` can ingest similarly named local env
  vars into Key Vault, but that script is a manual migration utility, not an
  active GitHub secret consumer.

### Tests/docs

`tests/smoke/test_oidc_connectivity.py` contains tenant/app IDs as non-secret
constants for real Azure smoke checks. It does not consume GitHub secret values.
Historical/release-gate docs mention these names as inventory evidence and
questions, not active consumers.

## Disposition

| Secret name | Classification | Recommended disposition | Owner | Consumer |
|---|---|---|---|---|
| `BCC_CLIENT_ID` | Orphaned GitHub repo secret / non-secret identifier | Remove from GitHub repository secrets after Tyler confirms no out-of-repo Obsidian/manual workflow still reads it. Preserve the ID in `config/tenants.yaml` / DB tenant record instead. | Tyler | None found in repo workflows/app runtime |
| `BCC_TENANT_ID` | Orphaned GitHub repo secret / non-secret identifier | Remove from GitHub repository secrets after Tyler confirms no out-of-repo Obsidian/manual workflow still reads it. Preserve the tenant ID in tenant config/DB/docs as appropriate. | Tyler | None found in repo workflows/app runtime |
| `FN_CLIENT_ID` | Orphaned GitHub repo secret / non-secret identifier | Remove from GitHub repository secrets after Tyler confirms no out-of-repo Obsidian/manual workflow still reads it. Preserve the ID in `config/tenants.yaml` / DB tenant record instead. | Tyler | None found in repo workflows/app runtime |
| `FN_TENANT_ID` | Orphaned GitHub repo secret / non-secret identifier | Remove from GitHub repository secrets after Tyler confirms no out-of-repo Obsidian/manual workflow still reads it. Preserve the tenant ID in tenant config/DB/docs as appropriate. | Tyler | None found in repo workflows/app runtime |
| `TLL_CLIENT_ID` | Orphaned GitHub repo secret / non-secret identifier | Remove from GitHub repository secrets after Tyler confirms no out-of-repo Obsidian/manual workflow still reads it. Preserve the ID in `config/tenants.yaml` / DB tenant record instead. | Tyler | None found in repo workflows/app runtime |
| `TLL_TENANT_ID` | Orphaned GitHub repo secret / non-secret identifier | Remove from GitHub repository secrets after Tyler confirms no out-of-repo Obsidian/manual workflow still reads it. Preserve the tenant ID in tenant config/DB/docs as appropriate. | Tyler | None found in repo workflows/app runtime |

## Why not delete them immediately?

The repository does not consume these GitHub secrets, so repo-local evidence
supports removal. But the acceptance criteria asks for disposition, not deletion,
and older release-gate evidence references Obsidian CI/CD notes. Deleting a
credential-like GitHub secret without owner confirmation could break an
out-of-repo/manual workflow. So the safe remediation is:

1. Owner confirms no out-of-repo workflow depends on repository secrets with
   these exact names.
2. Delete the six repository secrets.
3. Keep tenant/client identifiers in the appropriate source of truth:
   tenant DB rows, `config/tenants.yaml` for local/operator context, and Key
   Vault secret names for actual sensitive client secrets.
4. Do not create environment-level copies unless a workflow explicitly needs
   them; YAGNI, but wearing an Azure hoodie.

## Validation commands

```bash
# Values are not shown by this command.
gh secret list --repo HTT-BRANDS/control-tower | awk '/^(BCC|FN|TLL)_/{print}'

for env in development staging production production-backup github-pages; do
  gh secret list --env "$env" --repo HTT-BRANDS/control-tower 2>/dev/null \
    | awk '/^(BCC|FN|TLL)_/{print}'
done

rg -n 'BCC_CLIENT_ID|BCC_TENANT_ID|FN_CLIENT_ID|FN_TENANT_ID|TLL_CLIENT_ID|TLL_TENANT_ID|BCC_|FN_|TLL_' \
  .github app infrastructure scripts config docs tests SECRETS_OF_RECORD.md README.md
```

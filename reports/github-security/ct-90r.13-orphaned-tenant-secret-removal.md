# ct-90r.13 orphaned BCC/FN/TLL GitHub secret removal evidence

Captured: 2026-05-18T16:25:00Z

## Scope

Remove or document the repo-level BCC/FN/TLL tenant GitHub secrets after
`ct-90r.12` classified them as orphaned.

Secret values were not read.

## Secrets removed

The following repository-level GitHub Actions secrets were deleted from
`HTT-BRANDS/control-tower`:

```text
BCC_CLIENT_ID
BCC_TENANT_ID
FN_CLIENT_ID
FN_TENANT_ID
TLL_CLIENT_ID
TLL_TENANT_ID
```

## Pre-delete inventory

Name-only inventory before deletion:

```text
BCC_CLIENT_ID   updated 2026-03-26T15:24:07Z
BCC_TENANT_ID   updated 2026-03-26T15:24:08Z
FN_CLIENT_ID    updated 2026-03-26T15:24:07Z
FN_TENANT_ID    updated 2026-03-26T15:24:08Z
TLL_CLIENT_ID   updated 2026-03-26T15:24:07Z
TLL_TENANT_ID   updated 2026-03-26T15:24:08Z
```

## Post-delete verification

Repository-level name-only check after deletion returned no matching secrets:

```bash
gh secret list --repo HTT-BRANDS/control-tower \
  | awk '/^(BCC|FN|TLL)_(CLIENT|TENANT)_ID/{print}'
```

Output:

```text
<empty>
```

Environment-level name-only checks also returned no matching secrets for:

```text
development
staging
production
production-backup
github-pages
```

## Rationale

`ct-90r.12` found no active repo workflow or app/runtime consumer for these six
repo-level secret names. The active runtime credential model is tenant
DB/config + Key Vault secret refs, not repo-level tenant ID secrets.

These values are identifiers rather than credential material, but keeping them
as GitHub repository secrets created misleading inventory noise and widened the
set of repo-scope configuration available to jobs that do not declare a GitHub
environment.

## Recovery

If a future workflow legitimately needs tenant identifiers, do not recreate
these at repository scope by default. Prefer, in order:

1. Explicit non-secret config checked into the correct operational source of
   truth when safe.
2. Tenant DB/config source of truth.
3. Environment-scoped GitHub secret/variable only if a GitHub Actions job truly
   needs it and declares the matching environment.

YAGNI still applies, even when Azure asks nicely for more knobs.

## Commands used

```bash
for secret in \
  BCC_CLIENT_ID BCC_TENANT_ID \
  FN_CLIENT_ID FN_TENANT_ID \
  TLL_CLIENT_ID TLL_TENANT_ID; do
  gh secret delete "$secret" \
    --repo HTT-BRANDS/control-tower \
    --app actions
done
```

# ct-90r.9 environment-scoped OIDC remediation evidence

Captured: 2026-05-18T15:50:00Z

## Scope

Validate and document the per-environment OIDC model for GitHub Actions Azure
login. Secret values were not read.

Acceptance target:

- staging GitHub environment uses the staging app client ID.
- production GitHub environment uses the production app client ID.
- FIC subjects are environment-scoped and reference `HTT-BRANDS/control-tower`.
- Production app has no staging resource-group roles and staging app has no
  production resource-group roles unless explicitly justified.
- OIDC validation can be run without deploying.

## App registrations and FICs

```text
control-tower-oidc-staging
  appId: 71ed6019-5d5a-4ba7-acc2-e9f6c536579a
  objectId: 04be480d-60b8-4ffa-83db-5a2c460edc9b
  FIC: github-actions-control-tower-staging
  subject: repo:HTT-BRANDS/control-tower:environment:staging
  issuer: https://token.actions.githubusercontent.com
  audience: api://AzureADTokenExchange

control-tower-oidc-production
  appId: b4959810-4b43-4887-9458-37a78af2d01d
  objectId: 55450488-ce0e-48c7-bdb4-d8ea7cf02cf8
  FIC: github-actions-control-tower-production
  subject: repo:HTT-BRANDS/control-tower:environment:production
  issuer: https://token.actions.githubusercontent.com
  audience: api://AzureADTokenExchange
```

## GitHub environment secret names

Values were not read. Names only:

```text
staging:
  AZURE_CLIENT_ID        updated 2026-05-17T22:17:13Z
  AZURE_SUBSCRIPTION_ID  updated 2026-03-27T22:56:50Z
  AZURE_TENANT_ID        updated 2026-03-27T22:56:49Z

production:
  AZURE_CLIENT_ID        updated 2026-05-17T22:17:14Z
  AZURE_SUBSCRIPTION_ID  updated 2026-03-26T21:01:43Z
  AZURE_TENANT_ID        updated 2026-03-26T21:02:37Z
```

## RBAC separation

Service principals:

```text
staging appId:    71ed6019-5d5a-4ba7-acc2-e9f6c536579a
staging spId:     aab735ac-d6ff-4d71-ba78-631fbf482c3c
production appId: b4959810-4b43-4887-9458-37a78af2d01d
production spId:  84d2111e-f2d3-4f0e-af37-7b7e56862daf
```

Observed role assignments:

```text
staging SP:
  Website Contributor     /subscriptions/32a28177-6fb2-4668-a528-6d6cafb9665e/resourceGroups/rg-governance-staging
  Web Plan Contributor    /subscriptions/32a28177-6fb2-4668-a528-6d6cafb9665e/resourceGroups/rg-governance-staging
  Monitoring Contributor  /subscriptions/32a28177-6fb2-4668-a528-6d6cafb9665e/resourceGroups/rg-governance-staging

production SP:
  Website Contributor     /subscriptions/32a28177-6fb2-4668-a528-6d6cafb9665e/resourceGroups/rg-governance-production
  Web Plan Contributor    /subscriptions/32a28177-6fb2-4668-a528-6d6cafb9665e/resourceGroups/rg-governance-production
  Monitoring Contributor  /subscriptions/32a28177-6fb2-4668-a528-6d6cafb9665e/resourceGroups/rg-governance-production
  Key Vault Secrets User  /subscriptions/32a28177-6fb2-4668-a528-6d6cafb9665e/resourceGroups/rg-governance-production
```

No cross-environment resource-group roles were observed.

## Workflow validation path added

Added `.github/workflows/validate-environment-oidc.yml`.

This workflow is intentionally read-only:

1. Requires `workflow_dispatch` with `environment` = `staging` or `production`.
2. Declares `environment: ${{ inputs.environment }}` so GitHub emits the
   correct OIDC subject and resolves environment-scoped secrets.
3. Runs `azure/login@v2`.
4. Confirms read access to the expected resource group.
5. Confirms the opposite environment resource group is not reachable.
6. Performs no deploy, export, restart, or runtime mutation.

## Validation commands

```bash
az ad app list --display-name control-tower-oidc-staging \
  --query '[].{displayName:displayName,appId:appId,id:id}' -o json
az ad app federated-credential list --id 71ed6019-5d5a-4ba7-acc2-e9f6c536579a \
  --query '[].{name:name,issuer:issuer,subject:subject,audiences:audiences}' -o json

az ad app list --display-name control-tower-oidc-production \
  --query '[].{displayName:displayName,appId:appId,id:id}' -o json
az ad app federated-credential list --id b4959810-4b43-4887-9458-37a78af2d01d \
  --query '[].{name:name,issuer:issuer,subject:subject,audiences:audiences}' -o json

for env in staging production; do
  gh secret list --env "$env" --repo HTT-BRANDS/control-tower
done

az role assignment list --assignee aab735ac-d6ff-4d71-ba78-631fbf482c3c --all \
  --query '[].{role:roleDefinitionName,scope:scope}' -o table
az role assignment list --assignee 84d2111e-f2d3-4f0e-af37-7b7e56862daf --all \
  --query '[].{role:roleDefinitionName,scope:scope}' -o table
```

## Remaining closure condition

After this workflow lands on `main`, run both validations:

```bash
gh workflow run validate-environment-oidc.yml \
  --repo HTT-BRANDS/control-tower \
  --ref main \
  -f environment=staging

gh workflow run validate-environment-oidc.yml \
  --repo HTT-BRANDS/control-tower \
  --ref main \
  -f environment=production
```

Production may require GitHub environment approval. That is expected and good.

Close `ct-90r.9` only after both validation runs succeed.

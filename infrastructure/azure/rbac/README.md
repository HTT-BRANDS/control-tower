# Azure RBAC: Bicep Drift Reader

bd `azure-governance-platform-rxki` tracks the live assignment. This directory
contains the least-privilege custom role definition to unblock
`.github/workflows/bicep-drift-detection.yml` without granting broad write
access.

## Why this role exists

`infrastructure/main.bicep` is `targetScope = 'subscription'`, so drift detection
uses `az deployment sub what-if`. The GitHub Actions OIDC service principal must
be authorized at subscription scope for:

- `Microsoft.Resources/deployments/whatIf/action`
- subscription/resource reads needed to evaluate the template
- deployment metadata reads

Resource-group-scoped assignments are not enough for subscription-scoped
what-if.

## Definition

Use `bicep-drift-reader.role.json` as the source of truth. Replace
`<subscription-id>` before applying.

```bash
SUBSCRIPTION_ID="<subscription-id>"
jq --arg scope "/subscriptions/${SUBSCRIPTION_ID}" \
  '.AssignableScopes = [$scope]' \
  infrastructure/azure/rbac/bicep-drift-reader.role.json \
  > /tmp/bicep-drift-reader.role.json

az role definition create --role-definition /tmp/bicep-drift-reader.role.json
```

If the role already exists and needs a definition update, use:

```bash
az role definition update --role-definition /tmp/bicep-drift-reader.role.json
```

## Assignment (Tyler/admin only)

Do **not** run this from automation without explicit approval. Assign the role at
subscription scope to the OIDC service principal used by the drift workflow:

```bash
SUBSCRIPTION_ID="<subscription-id>"
OIDC_OBJECT_ID="<service-principal-object-id>"

az role assignment create \
  --assignee-object-id "$OIDC_OBJECT_ID" \
  --assignee-principal-type ServicePrincipal \
  --role "Bicep Drift Reader" \
  --scope "/subscriptions/${SUBSCRIPTION_ID}"
```

Then manually dispatch `bicep-drift-detection.yml`. bd `rxki` should remain open
until all matrix environments complete without `AuthorizationFailed` or report
real drift.

# Project-specific recommendations

## Priority 1 — CI/CD identity isolation

Create or verify these identities:

- `control-tower-deploy-dev`
- `control-tower-deploy-staging`
- `control-tower-deploy-prod`

Each identity should have a federated identity credential with a GitHub environment subject:

```text
issuer:   https://token.actions.githubusercontent.com
audience: api://AzureADTokenExchange
subject:  repo:HTT-BRANDS/control-tower:environment:production
```

Use `development`, `staging`, and `production` subjects matching actual GitHub environment names.

## Priority 2 — GitHub environment protection

- Keep production Azure IDs in the `production` environment only.
- Require reviewer approval for production.
- Ensure workflows set `environment: production` before requesting Azure OIDC tokens.
- Set `permissions: id-token: write` only on jobs requiring Azure login.

## Priority 3 — RBAC least privilege

- Give staging identity access only to staging resource groups.
- Give production identity access only to production resource groups.
- Split read-only drift/inventory from deploy/write workflows.
- Avoid `Owner` and `User Access Administrator` in normal deploy workflows.

## Priority 4 — Cross-tenant model

- Use **Azure Lighthouse** for customer/brand Azure Resource Manager control-plane operations where the target is Azure resources, subscriptions, resource groups, policy, inventory, or deployment.
- Use **per-tenant app registrations** for Microsoft Graph/Entra directory operations that Lighthouse does not cover.
- Avoid one global multi-tenant app registration for all CI/CD deployment authority.

## Priority 5 — Stale credential remediation

Run the read-only command cookbook quarterly and before major releases. Flag and remediate:

- federated credentials whose `subject` references deleted environments, renamed repos, stale branches, or pull-request subjects not intended for deployment;
- GitHub repository secrets duplicating environment secrets;
- service principals with no corresponding active workflow/environment;
- role assignments at subscription scope where resource-group scope is sufficient;
- Lighthouse registration assignments for offboarded customer/brand tenants.

Suggested cleanup order:

1. Remove unused GitHub environment/repository secrets.
2. Remove unused federated identity credentials.
3. Remove Azure role assignments.
4. Remove unused service principals/app registrations where safe.
5. Remove stale Lighthouse registration assignments/definitions according to tenant ownership and change-control rules.

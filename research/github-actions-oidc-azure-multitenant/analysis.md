# Multi-dimensional analysis

## Security

- OIDC removes stored Azure client secrets from GitHub and uses short-lived tokens.
- The strongest boundary is one Azure identity per GitHub environment and tenant/subscription boundary.
- Federated identity credentials should use exact `issuer`, `audiences`, and `subject` values. For production, prefer `repo:HTT-BRANDS/control-tower:environment:production` plus GitHub environment protection rules.
- Azure Lighthouse is strong for delegated Azure Resource Manager access, because customer tenants can see/remove delegation and authorization is constrained by delegated scopes and roles.
- A single multi-tenant app registration is the riskiest CI/CD model because role assignments and federated credentials can accumulate across tenants and the client ID becomes a high-value control-plane identifier.

## Cost

- OIDC has no direct licensing cost.
- Azure Lighthouse has no direct platform cost; operational cost is onboarding/delegation management.
- Per-tenant app registrations have higher administrative cost but lower incident blast radius.

## Implementation complexity

- Per-environment app/UAMI in one tenant: low complexity.
- Lighthouse: medium complexity due to onboarding definitions/assignments and customer/brand delegation flow.
- Multi-tenant app registration: medium-to-high complexity when combined with consent, per-tenant service principals, Graph permissions, and cleanup.
- Per-tenant apps: high setup volume, but easy audit semantics.

## Stability and compatibility

- GitHub Actions OIDC with `azure/login@v2` is documented by both Microsoft and GitHub.
- Azure CLI provides stable command groups for app registrations, service principals, federated credentials, role assignments, and managed services registrations.
- Lighthouse is purpose-built for Azure delegated resource management; it does not replace Graph/Entra app consent for directory APIs.

## Maintenance

- Create a periodic access review job using the command cookbook in `README.md`.
- Compare actual federated credential subjects against current `.github/workflows/*` environment names.
- Compare GitHub environment secrets against current active Azure identities.
- Remove stale role assignments before deleting app registrations/service principals so orphaned privileged paths do not remain.

## Optimization

- Prefer environment variables for non-secret IDs if policy permits (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` are identifiers, not credentials), but environment secrets are acceptable and common.
- Use targeted RBAC scopes: resource group for deployments; subscription Reader only for inventory/drift; avoid subscription Contributor unless required.
- Use custom roles for deployment workflows when built-in Contributor is too broad.

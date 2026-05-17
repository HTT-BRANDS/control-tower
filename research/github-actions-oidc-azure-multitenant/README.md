# GitHub Actions OIDC to Azure across environments, tenants, and subscriptions

## Executive summary

For this Control Tower project (Azure/M365-first, Python/FastAPI app with dev/staging/prod Azure resource groups and a multi-tenant governance posture), prefer **separate GitHub environments and separate Azure identities per deployment environment and per trust boundary**. Use GitHub Actions OIDC instead of client secrets.

**Recommended default:**
1. **Internal HTT dev/staging/prod subscriptions:** use **per-environment Microsoft Entra app registrations or user-assigned managed identities** with narrowly scoped Azure RBAC at the resource group or subscription scope required by each workflow.
2. **Customer/brand tenant delegated operations:** use **Azure Lighthouse** for cross-tenant delegated resource management when the CI/CD identity only needs Azure Resource Manager control-plane access to delegated subscriptions/resource groups. This aligns with the repo architecture that already models Azure Lighthouse as the cross-tenant control-plane bridge.
3. **Avoid a single broad multi-tenant app registration for CI/CD deployment authority** unless there is a strong reason to centralize app identity. It concentrates blast radius and complicates stale service principal cleanup in every customer tenant.

## Architecture option comparison

| Option | Best fit | Strengths | Weaknesses / risk | Recommendation |
|---|---|---|---|---|
| **Azure Lighthouse delegated resource management** | MSP/control-plane access to many Azure tenants/subscriptions/RGs | Native cross-tenant Azure Resource Manager delegation; customer can see/remove delegations; no per-customer GitHub secret values beyond selected tenant/subscription metadata; works well for inventory, policy, deployments within delegated scopes | Only covers Azure Resource Manager delegated resources, not Microsoft Graph/Entra directory operations; authorization is defined by Lighthouse registration definitions and eligible roles; customers must onboard delegations | **Use for customer/brand Azure resource governance and deployments** where ARM access is sufficient. Keep separate deployment identities/groups per env. |
| **Single multi-tenant Entra app registration** | SaaS/API scenario needing consent across many tenants, sometimes Graph | One app/client ID can have service principals in many tenants; central app config | High blast radius if federated subject/role assignments are too broad; each tenant has a service principal to audit/remove; app-owner tenant controls credential policy; least-privilege per env is harder if reused | **Generally avoid for CI/CD control-plane deployment**. Consider only for app-level Graph/API access with explicit tenant consent and separate app roles/scopes. |
| **Per-tenant app registrations** | Strong tenant isolation, customer-owned CI/CD identity, or environments in different Entra tenants | Clean blast-radius isolation; local tenant owners can audit app registrations/federated credentials/role assignments; simple stale credential deletion | More setup and inventory overhead; GitHub env secrets must map to each tenant/subscription/client ID; automation must loop tenants | **Use for high-trust boundaries or prod isolation** when Lighthouse is insufficient or directory/Graph permissions are needed. |

## Read-only validation command cookbook

> Replace placeholders. These commands list metadata only; they do not reveal secret values.

### Azure context

```bash
az account show --query '{tenantId:tenantId,subscriptionId:id,name:name,user:user.name}' -o json
az account list --query '[].{name:name,id:id,tenantId:tenantId,isDefault:isDefault}' -o table
```

### App registrations, service principals, federated credentials

```bash
# App registrations in the current tenant
az ad app list --all \
  --query "[].{displayName:displayName, appId:appId, objectId:id, signInAudience:signInAudience}" -o table

# Find a specific app registration
az ad app list --filter "displayName eq 'APP_DISPLAY_NAME'" \
  --query "[].{displayName:displayName, appId:appId, objectId:id, signInAudience:signInAudience}" -o json

# Service principals for an appId in the current tenant
az ad sp list --all --filter "appId eq 'APPLICATION_CLIENT_ID'" \
  --query "[].{displayName:displayName, appId:appId, objectId:id, accountEnabled:accountEnabled}" -o table

# Federated identity credentials on an app registration
az ad app federated-credential list --id APPLICATION_OBJECT_ID_OR_APP_ID \
  --query "[].{name:name, issuer:issuer, subject:subject, audiences:audiences}" -o table

# Microsoft Graph REST fallback for federated identity credentials
az rest --method GET \
  --url "https://graph.microsoft.com/beta/applications/APPLICATION_OBJECT_ID/federatedIdentityCredentials" \
  --query "value[].{name:name,issuer:issuer,subject:subject,audiences:audiences}" -o table
```

### Azure RBAC assignments at subscription / resource group scope

```bash
SUB_ID="00000000-0000-0000-0000-000000000000"
RG="rg-governance-staging"
ASSIGNEE_OBJECT_ID="00000000-0000-0000-0000-000000000000"

# All role assignments at subscription scope, including inherited
az role assignment list --scope "/subscriptions/$SUB_ID" --include-inherited --all \
  --query "[].{principalName:principalName,principalId:principalId,principalType:principalType,role:roleDefinitionName,scope:scope}" -o table

# Role assignments for one CI/CD principal at subscription scope
az role assignment list --assignee-object-id "$ASSIGNEE_OBJECT_ID" --assignee-principal-type ServicePrincipal \
  --scope "/subscriptions/$SUB_ID" --include-inherited --all \
  --query "[].{role:roleDefinitionName,scope:scope,principalId:principalId}" -o table

# Role assignments for one CI/CD principal at a resource-group scope
az role assignment list --assignee-object-id "$ASSIGNEE_OBJECT_ID" --assignee-principal-type ServicePrincipal \
  --scope "/subscriptions/$SUB_ID/resourceGroups/$RG" --include-inherited --all \
  --query "[].{role:roleDefinitionName,scope:scope,principalId:principalId}" -o table
```

### GitHub environments and environment secrets

```bash
OWNER="HTT-BRANDS"
REPO="control-tower"
ENV="production"

# Environments
 gh api "repos/$OWNER/$REPO/environments" --jq '.environments[] | {name, protection_rules, deployment_branch_policy}'

# Environment secrets: names and timestamps only, not values
 gh secret list --repo "$OWNER/$REPO" --env "$ENV"
 gh api "repos/$OWNER/$REPO/environments/$ENV/secrets" --jq '.secrets[] | {name, created_at, updated_at}'

# Repository-level Actions secrets: identify values that should move to environments
 gh secret list --repo "$OWNER/$REPO"
 gh api "repos/$OWNER/$REPO/actions/secrets" --jq '.secrets[] | {name, created_at, updated_at}'
```

### Azure Lighthouse delegated resources / registrations

```bash
SUB_ID="00000000-0000-0000-0000-000000000000"
SCOPE="/subscriptions/$SUB_ID"

# Registration assignments and definitions visible at a scope
az managedservices assignment list --scope "$SCOPE" -o table
az managedservices definition list --scope "$SCOPE" -o table

# ARM REST fallback with full details
az rest --method GET \
  --url "https://management.azure.com${SCOPE}/providers/Microsoft.ManagedServices/registrationAssignments?api-version=2022-10-01" \
  --query "value[].{name:name,registrationDefinitionId:properties.registrationDefinitionId,provisioningState:properties.provisioningState}" -o table

az rest --method GET \
  --url "https://management.azure.com${SCOPE}/providers/Microsoft.ManagedServices/registrationDefinitions?api-version=2022-10-01" \
  --query "value[].{name:name,managedByTenantId:properties.managedByTenantId,description:properties.description,authorizations:properties.authorizations}" -o json
```

## Security best practices

- **Use OIDC, not long-lived client secrets.** GitHub and Microsoft both document OIDC as a way for workflows to request short-lived cloud tokens without storing cloud credentials.
- **Set `permissions: id-token: write` only on jobs that need Azure login.** Keep default workflow permissions minimal.
- **Use GitHub environments for dev/staging/prod.** Store `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, and `AZURE_SUBSCRIPTION_ID` as environment secrets or environment variables; require reviewers for production.
- **Use separate Entra identities per environment.** Do not let a staging federated subject assume production RBAC.
- **Constrain federated credential `subject` claims.** Prefer `repo:ORG/REPO:environment:production` for production, not broad branch or pull-request subjects. Use separate credentials for dev/staging/prod, with clear names.
- **Scope Azure RBAC narrowly.** Prefer RG-scoped roles for app deployment; avoid Owner/User Access Administrator in CI except for tightly controlled infra-bootstrap jobs. Use custom roles if built-ins are broader than necessary.
- **Do not use a single multi-tenant app as a universal deploy key.** If multi-tenant app registration is used, create separate app registrations or separate federated credentials per environment and audit all service principals in consuming tenants.
- **Remediate stale credentials and principals.** Regularly list GitHub env secrets, app federated credentials, service principals, Azure role assignments, and Lighthouse registration assignments. Remove identities with no matching active workflow/environment.

## Project-specific recommendation

For HTT Control Tower, model CI/CD access as:

- `control-tower-deploy-dev`, `control-tower-deploy-staging`, `control-tower-deploy-prod` identities with one federated credential each for `repo:HTT-BRANDS/control-tower:environment:<env>`.
- Environment-specific GitHub environments with production reviewer protection.
- Resource group scoped deployment roles for `rg-governance-staging` and `rg-governance-production`; separate subscription-scope read-only role for drift/inventory if required.
- Azure Lighthouse for delegated customer/brand resource management, but keep Microsoft Graph/Entra directory operations behind separate, explicitly consented per-tenant app registrations or app roles.

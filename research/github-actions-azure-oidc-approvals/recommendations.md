# Project-specific implementation guardrails

## P0 guardrails

1. **Environment-scoped Azure federated credential for production**
   - Subject: `repo:HTT-BRANDS/control-tower:environment:production`.
   - Issuer: `https://token.actions.githubusercontent.com`.
   - Audience: `api://AzureADTokenExchange`.
   - Ensure only the post-approval production deploy job can match this subject.

2. **Keep Azure login behind the production environment gate**
   - Production deploy job must keep `environment: production`.
   - Do not add a separate pre-approval job with `azure/login` and the same prod credential.
   - Prefer `permissions: { id-token: write, contents: read }` at the Azure-authenticating job level.

3. **Split deploy and what-if identities**
   - Production deploy principal: only required production deployment actions.
   - Drift/what-if principal: no deployment writes; no broad Contributor role.
   - Staging/dev identities: separate from prod.

4. **Custom what-if RBAC role**
   Use explicit actions only. Start with:
   - `Microsoft.Resources/deployments/whatIf/action`
   - `Microsoft.Resources/deployments/validate/action`
   - `Microsoft.Resources/deployments/read`
   - `Microsoft.Resources/deployments/operations/read`
   - `Microsoft.Resources/deployments/operationstatuses/read`
   - `Microsoft.Resources/subscriptions/read`
   - `Microsoft.Resources/subscriptions/locations/read`
   - `Microsoft.Resources/subscriptions/resourceGroups/read`
   - `Microsoft.Resources/subscriptions/resources/read`
   - `Microsoft.Resources/resources/read`
   - `Microsoft.Resources/providers/read`
   - Resource-provider-specific `*/read` actions for every resource type in `infrastructure/main.bicep`.

   Exclude unless proven necessary:
   - `Microsoft.Resources/deployments/write`
   - `Microsoft.Resources/subscriptions/resourceGroups/write`
   - any provider `*/write`, `*/delete`, or `*/action` unrelated to what-if.

5. **Issuer rotation with issuer-specific validation profiles**
   - Each accepted issuer must have explicit: algorithms, audience, JWKS/key source, token TTL expectations, and deprecation date.
   - Rotation overlap window = max token lifetime + refresh-token lifetime if applicable + clock skew.
   - After the window, remove old issuer and old signing keys; do not leave permanent dual issuer acceptance.

## P1 operational guardrails

- Add an environment inventory check to ensure `production`, `staging`, and `dev` environments exist and have expected protection rules before relying on OIDC subject scoping.
- Name federated credentials by environment and workflow intent, e.g. `gha-control-tower-prod-deploy`, `gha-control-tower-prod-whatif`.
- Keep federated credential count under 20 per app/UAMI; use environment subjects rather than per-branch subjects for protected environments.
- Alert on Azure sign-ins/token exchanges by GitHub Actions principals outside expected workflow windows.
- For JWT rotation, log accepted issuer, `kid`, token type, and validation failure class without logging raw tokens.

## Things to avoid

- Do not use Azure client secrets in GitHub for deployment if OIDC is available.
- Do not scope Azure federated credentials to broad branch refs for production if the deploy job uses GitHub environments.
- Do not rely on GitHub environment approval alone while giving the Azure principal broad Contributor/Owner access.
- Do not use wildcard federated credential subjects; Azure federated credentials do not support wildcard property values.
- Do not disable JWT signature validation except in tightly controlled diagnostics.
- Do not use token header `alg` to decide which algorithms are allowed.

## Concise acceptance checklist

- [ ] Prod Azure federated credential subject exactly matches `repo:HTT-BRANDS/control-tower:environment:production`.
- [ ] Prod environment has required reviewers, prevent self-review, branch/tag restrictions, and no routine admin bypass.
- [ ] Drift detection uses a distinct Azure principal with a custom what-if role.
- [ ] Custom what-if role includes `Microsoft.Resources/deployments/whatIf/action` and omits deployment/resource writes.
- [ ] PyJWT validation config supports dual issuers only during a documented rotation window.
- [ ] Old JWT issuer/key removed after TTL + skew, with metrics confirming no active old-issuer traffic.

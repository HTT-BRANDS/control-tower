# GitHub Actions Environment Approvals + Azure OIDC Guardrails

## Executive summary

For this FastAPI/PyJWT + Azure/GitHub Actions project, the safest pattern is:

1. **GitHub environment approval gates before Azure login**: any job that can request the Azure OIDC token for production should reference the protected `production` environment and should not run `azure/login` until after required reviewers approve the job.
2. **Azure federated credentials scoped to environment-specific `sub` claims**: use exact subject values such as `repo:HTT-BRANDS/control-tower:environment:production` with audience `api://AzureADTokenExchange`; avoid branch/tag-only credentials for prod unless explicitly needed.
3. **Separate identities by blast radius**: use a deploy identity for actual deployment and a lower-privilege drift/what-if identity for scheduled what-if. Do not reuse a broad deployment principal for read/drift checks.
4. **Custom RBAC for Bicep what-if**: include `Microsoft.Resources/deployments/whatIf/action` plus required read/list/validate operations at the narrowest scope. Do not grant `deployments/write` unless the same identity must create deployments.
5. **Issuer rotation for app JWTs**: support an overlap window where both old and new issuers are accepted, but bind each issuer to its own expected audience, algorithm allow-list, and key/JWKS source; retire the old issuer only after max token TTL + clock-skew leeway.

## Project relevance

Observed repo context:

- Python 3.12, FastAPI, PyJWT, Azure SDKs.
- `.github/workflows/deploy-production.yml` already uses `permissions: id-token: write`, protected `environment: production`, `azure/login@v2`, digest-pinned deployment, and attestation gates.
- `.github/workflows/bicep-drift-detection.yml` runs `az deployment sub what-if` across dev/staging/production using the same Azure secrets/identity as other workflows.
- The project values zero-secrets architecture, release gates, Bicep drift detection, and production approval discipline.

## Highest-priority guardrails

### GitHub Actions / Azure OIDC

- Keep `id-token: write` at **job scope** where possible, not global workflow scope.
- Every job that can call `azure/login` against production must declare `environment: production` so GitHub holds the job until environment protection rules pass.
- Configure production environment with:
  - required reviewers;
  - prevent self-review;
  - deployment branch/tag allow-list;
  - disallow administrator bypass for normal operations.
- Ensure the Azure federated identity credential `subject` exactly matches the GitHub job context. If the job uses `environment: production`, the subject is `repo:ORG/REPO:environment:production` rather than a branch ref.
- Use separate Entra app registrations or user-assigned managed identities for:
  - prod deploy;
  - staging deploy;
  - drift/what-if;
  - backup/export tasks.
- Remember Entra federated credentials are exact-match and do **not** support wildcards; max 20 federated credentials per app/UAMI.

### Azure RBAC for what-if

Minimum useful custom role shape for a drift-only identity:

- `Microsoft.Resources/deployments/whatIf/action` — required for ARM what-if.
- `Microsoft.Resources/deployments/validate/action` — useful preflight validation.
- `Microsoft.Resources/deployments/read` and deployment operation reads — to inspect existing deployment state.
- `Microsoft.Resources/subscriptions/resourceGroups/read`, `Microsoft.Resources/resources/read`, `Microsoft.Resources/subscriptions/resources/read`, provider/location reads — to resolve current state.
- Resource-provider-specific `*/read` actions for resources referenced by templates.
- Avoid `Microsoft.Resources/deployments/write` and resource `*/write` in the scheduled drift identity unless it also performs actual deployments.

### Safe JWT issuer rotation in FastAPI/PyJWT

- Maintain an explicit issuer registry: issuer -> allowed algorithms, audience(s), JWKS URI or key set, token type, deprecation deadline.
- Do not decode with unbounded issuer choices. First inspect the unverified payload/header only to route to a configured issuer/key, then perform full signature + `iss` + `aud` + `exp` + `nbf` validation.
- Never trust token `alg`; pass an explicit algorithm allow-list per issuer.
- During rotation:
  1. publish new issuer/JWKS;
  2. add new issuer to validators in monitor-only or dual-accept mode;
  3. switch token minting to new issuer;
  4. wait at least max access-token TTL + refresh-token TTL if refresh tokens embed issuer + skew;
  5. remove old issuer and old keys.
- Keep leeway small, usually seconds to a few minutes, and require `exp`, `iss`, and `sub` on internal tokens.

## Bottom line

The repo is already close to current best practice for production deploy approval. The main hardening opportunity is identity separation: production deployment and Bicep what-if/drift detection should not share the same Azure principal or broad RBAC assignment. For application JWTs, issuer rotation should be treated as a controlled compatibility window, not as a permissive multi-issuer bypass.

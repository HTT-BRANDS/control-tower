# Sources and credibility assessment

## Tier 1 — primary / official sources

1. **GitHub Docs — Managing environments for deployment**  
   URL: https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments  
   Credibility: Tier 1, official GitHub documentation.  
   Currency observed: current GitHub Docs page; no visible last-updated field in extracted text.  
   Key findings: jobs referencing environments must satisfy protection rules before running or accessing environment secrets; up to 6 required reviewers; only one required reviewer needs to approve; prevent self-review option; branch/tag deployment restrictions; running a workflow referencing a non-existent environment can create an unprotected environment.

2. **GitHub Docs — Configuring OpenID Connect in Azure**  
   URL: https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-azure  
   Credibility: Tier 1, official GitHub documentation.  
   Key findings: OIDC removes long-lived Azure secrets; `id-token: write` is required only to fetch an OIDC JWT and does not grant resource write access by itself; GitHub recommends environment protection rules when environments are used in workflows or OIDC policies; recommended Azure audience is `api://AzureADTokenExchange`.

3. **GitHub Docs — OpenID Connect reference**  
   URL: https://docs.github.com/en/actions/reference/security/oidc  
   Credibility: Tier 1, official GitHub documentation.  
   Key findings: issuer is `https://token.actions.githubusercontent.com`; environment subject format is `repo:ORG-NAME/REPO-NAME:environment:ENVIRONMENT-NAME`; branch subject is `repo:ORG/REPO:ref:refs/heads/BRANCH`; GitHub states at least one cloud trust condition is required to prevent untrusted repositories from obtaining cloud tokens; OIDC tokens can include custom subject templates and claims.

4. **Microsoft Learn — Configure an app to trust an external identity provider / federated identity credentials**  
   URL: https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation-create-trust  
   Credibility: Tier 1, official Microsoft documentation.  
   Currency observed: last updated 2024-12-13.  
   Key findings: Entra federated credentials validate issuer + subject + audience; issuer/subject pair must be unique; wildcard characters are not supported; max 20 federated identity credentials per app or UAMI; subject values must exactly match GitHub workflow configuration; recommended audience `api://AzureADTokenExchange`; GitHub environment subjects use `repo:<Organization/Repository>:environment:<Name>`.

5. **Microsoft Learn — Azure custom roles**  
   URL: https://learn.microsoft.com/en-us/azure/role-based-access-control/custom-roles  
   Credibility: Tier 1, official Microsoft documentation.  
   Currency observed: last updated 2025-10-23.  
   Key findings: custom roles define Actions/NotActions/DataActions/NotDataActions and AssignableScopes; Microsoft recommends explicit actions over wildcards to avoid future permissions expanding unexpectedly; custom role limits and assignable-scope behavior documented.

6. **Microsoft Learn — Azure permissions for Management and governance**  
   URL: https://learn.microsoft.com/en-us/azure/role-based-access-control/permissions/management-and-governance  
   Credibility: Tier 1, official Microsoft documentation.  
   Currency observed: last updated 2026-04-09.  
   Key findings: `Microsoft.Resources/deployments/whatIf/action` description is “Predicts template deployment changes”; adjacent actions include deployment read/write/delete/cancel/validate/exportTemplate and deployment operation reads.

7. **PyJWT documentation — Usage Examples / registered claims / JWKS**  
   URL: https://pyjwt.readthedocs.io/en/stable/usage.html  
   Credibility: Tier 1 for PyJWT behavior, official project documentation.  
   Version observed: PyJWT 2.12.1 documentation.  
   Key findings: `iss` is case-sensitive and `InvalidIssuerError` is raised on mismatch; `aud` can accept multiple values but must match; `exp` and `nbf` support small leeway; `require` option can require claims; `PyJWKClient` retrieves JWKS by `kid`, refreshes when a key is missing, and caches keys; reading claims without validation is generally ill-advised except for controlled routing.

## Validation / cross-reference notes

- GitHub and Microsoft agree on the core Azure OIDC contract: GitHub issuer, exact `sub`, and `api://AzureADTokenExchange` audience.
- Microsoft RBAC permission documentation confirms the exact ARM operation string for what-if.
- PyJWT guidance aligns with general JWT safety: fixed algorithms, signature validation, issuer/audience checks, expiry/nbf validation, and JWKS `kid`-based key selection.

## Bias and limitations

- GitHub and Microsoft docs are vendor documentation; authoritative for platform behavior but can emphasize platform-supported paths.
- Azure federated credential behavior can vary slightly between app registrations and UAMIs; verify live object type and CLI/API behavior during implementation.
- PyJWT docs describe library capabilities; application-level rotation sequencing and telemetry must be designed by the project.

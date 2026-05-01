# Multi-dimensional analysis

## Security

### GitHub environment approvals + OIDC

Strong pattern:

- `environment: production` on the job that invokes `azure/login`.
- Production environment configured with required reviewers and prevent-self-review.
- Azure federated credential subject scoped to the environment: `repo:HTT-BRANDS/control-tower:environment:production`.
- `permissions: id-token: write` only on jobs that need OIDC.

Why it matters: GitHub environment protection rules hold the job before it can access environment secrets/vars and before deployment steps run. When Azure’s federated credential is scoped to the environment subject, branch-only or PR-triggered jobs cannot exchange their GitHub OIDC token for Azure credentials.

Residual risks:

- If a workflow references a typo/non-existent environment, GitHub can create it without protections. Guard with workflow lint/review and environment inventory checks.
- Environment approval protects jobs, not all workflows globally; any other job with `id-token: write` and matching Azure federated subject can still authenticate.
- A broad Azure role assignment can turn a narrow OIDC subject into high-impact Azure access.

### Azure custom RBAC for what-if

`Microsoft.Resources/deployments/whatIf/action` is the critical permission for ARM/Bicep what-if. It should live in a drift-only custom role assigned at the subscription or resource-group scope needed by `az deployment sub what-if`.

Security guidance:

- Prefer explicit `read`, `validate`, and `whatIf/action` permissions.
- Avoid `Microsoft.Resources/deployments/write` for scheduled drift detection; `write` permits actual deployment creation/update.
- Avoid `*` wildcard actions; future provider actions can silently expand access.
- Split identities: production deploy identity can write, drift identity should not.

### JWT issuer rotation

Issuer rotation risk is usually self-inflicted by making validation too permissive. Safe rotation requires dual acceptance without losing claim binding.

Guardrails:

- Validate `iss`, `aud`, signature, `exp`, and `nbf` every time.
- Bind each issuer to its own expected audience and key/JWKS source.
- Do not accept both HS* and RS*/ES* algorithms for the same issuer/key path.
- Treat unverified header/payload reads as routing only; never authorize from them.
- Retire the old issuer after all possible old tokens have expired or been revoked.

## Cost

- GitHub environments and OIDC have no direct runtime cost in typical GitHub plans, but required reviewers/custom protection rules can require plan features for private repositories.
- Azure custom roles are free; cost is operational maintenance and review overhead.
- Separate Entra applications/UAMIs have negligible cost; the benefit is reduced blast radius.

## Implementation complexity

Low-to-medium:

- GitHub environment approvals are already present for production deployment in this repo.
- Azure federated credentials require exact subject setup and can fail silently at token exchange time if mismatched.
- Custom RBAC requires iterative testing because what-if may need resource-provider-specific reads depending on template contents.
- JWT issuer rotation requires config/schema support, logging, and runbook discipline but not a major architectural change.

## Stability

- GitHub OIDC and Azure workload identity federation are mature current best practices.
- Azure federated credentials have fixed limits, notably 20 credentials per app/UAMI, so avoid one-credential-per-branch sprawl.
- PyJWT 2.x supports issuer/audience validation and JWKS key selection; keep dependency pinned/updated via existing dependency management.

## Optimization

- Narrow job-level `permissions` reduces token availability.
- Separate what-if identity reduces risk while preserving automated weekly drift detection.
- JWT key lookup should use JWKS caching and `kid`-based refresh to avoid repeated network calls and to survive signing-key rollover.

## Compatibility

- The current `.github/workflows/deploy-production.yml` pattern is compatible with environment-scoped Azure OIDC.
- The current `.github/workflows/bicep-drift-detection.yml` runs subscription-scope what-if; RBAC assignment scope must match that (`/subscriptions/...`) unless templates can be constrained.
- FastAPI/PyJWT can support multi-issuer rotation using existing PyJWT primitives; ensure middleware dependencies keep issuer config environment-specific.

## Maintenance

- Review federated credentials quarterly and after repo/org/environment renames.
- Store expected OIDC subjects in docs or IaC outputs to avoid portal drift.
- Keep a rotation runbook for JWT issuers and signing keys, including rollback and telemetry queries.
- Audit Azure role assignments for stale GitHub Actions principals.

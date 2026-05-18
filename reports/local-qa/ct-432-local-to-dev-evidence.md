# ct-432 Local QA → Development Evidence

Owner: Richard (`code-puppy-1c7422`)
Target: development only (`app-governance-dev-001`)

## Decision

Local QA is approved for development-only promotion. This evidence does **not** authorize staging or production.

## Three-pass local gate

- Run 1: PASS — 2026-05-18T03:58:37Z → 2026-05-18T04:02:07Z; doctor 9 pass/0 fail; unit 3659 passed/9 warnings; integration 403 passed; local data smoke 27 pass/0 fail; browser/seeded E2E 26 passed; axe 17 expected skips.
- Run 2: PASS — 2026-05-18T04:02:17Z → 2026-05-18T04:05:55Z; doctor 9 pass/0 fail; unit 3659 passed/9 warnings; integration 403 passed; local data smoke 27 pass/0 fail; browser/seeded E2E 26 passed; axe 17 expected skips.
- Run 3: PASS — 2026-05-18T04:06:06Z → 2026-05-18T04:09:49Z; doctor 9 pass/0 fail; unit 3659 passed/9 warnings; integration 403 passed; local data smoke 27 pass/0 fail; browser/seeded E2E 26 passed; axe 17 expected skips.

## Real local development server smoke

`ENVIRONMENT=development DATABASE_URL=sqlite:///./data/local-dev.db` was started with uvicorn and validated with public and authenticated checks.

Covered:

- `/health`, `/health/detailed`, `/openapi.json`, `/docs`.
- root redirect behavior.
- `/login`.
- real `/api/v1/auth/login` cookie contract with HttpOnly cookies.
- authenticated pages: dashboard, costs, compliance, resources, identity, sync dashboard, Riverside, DMARC.
- authenticated APIs: costs, compliance, resources, identity, Riverside, DMARC representative endpoints.

See `reports/local-qa/local-deployment-smoke.md` for sanitized status/byte evidence.

## Security scanner evidence

- `detect-secrets --all-files`: PASS.
- Bandit via `uvx bandit -r app`: 0 high severity findings after marking cache-key MD5 as `usedforsecurity=False`.

## Specialist review

- QA Kitten: APPROVE for development-only promotion; re-run smoke after dev deploy.
- Release Gate Arbiter: CONDITIONAL_PASS for local → development; missing/ambiguous dev deployment mechanism must be documented/remediated before future gates.

## Rollback

Previous dev image before promotion:

`acrgovernancedev.azurecr.io/governance-platform:20260331124605`

Rollback command:

```bash
az webapp config container set \
  --resource-group rg-governance-dev \
  --name app-governance-dev-001 \
  --container-image-name acrgovernancedev.azurecr.io/governance-platform:20260331124605 \
  --container-registry-url https://acrgovernancedev.azurecr.io
az webapp restart --resource-group rg-governance-dev --name app-governance-dev-001
./scripts/verify-dev-deployment.sh
```

## Development deployment result

Manual dev-only container promotion completed.

- Commit/image source: `d666268`.
- New dev image: `acrgovernancedev.azurecr.io/governance-platform:qa-d666268-20260518`.
- Previous rollback image: `acrgovernancedev.azurecr.io/governance-platform:20260331124605`.
- Dev App Service container setting confirms the new image.
- Dev `/health` returned healthy, environment `development`, version `2.5.0`.
- Post-deploy dev smoke passed for public endpoints and protected-route no-500 checks.
- Rollback was not required.

See `reports/local-qa/dev-deployment.summary` and `reports/local-qa/dev-deployment-smoke.md`.

## Known process gap

The repo references `deploy-dev.yml`, but GitHub has no active dev deployment workflow. This promotion uses manual dev-only ACR/App Service container update after local QA. A follow-up bead tracks restoring/documenting deterministic dev deployment.

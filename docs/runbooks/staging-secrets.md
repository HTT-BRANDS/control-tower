# Staging secrets — one-time setup runbook

**Issue:** [ct-wph](../../README.md) — wire AZURE_AD_* env vars into staging
deploy automation.

**Owner:** Tyler · **Last updated:** 2026-05-19

---

## Why this runbook exists

Before [ct-wph](../../README.md) landed, the staging webapp
`app-governance-staging-xnczpwyv` had all `AZURE_AD_*` env vars declared
but **empty**. Browser-based login was broken with the error message:

> Azure AD sign-in unavailable. Azure AD not configured.

On 2026-05-19 Tyler patched it by hand with `az webapp config appsettings
set`, copying nine settings from `app-governance-prod`. That worked
operationally, but a future bicep redeploy or `az webapp config container
set` could wipe the settings again — the live state lived only in Tyler's
zsh history.

The fix in `.github/workflows/deploy-staging.yml` makes the wiring
idempotent: every staging deploy now calls `az webapp config appsettings
set` with the AZURE_AD values pulled from GitHub Secrets. The deploy
gracefully skips this step if the secrets aren't set yet (so existing
branch deploys stay green while you walk through the steps below).

---

## What you need to set (one-time, ~5 minutes)

Add the following secrets in the GitHub repo settings:

  **Settings → Secrets and variables → Actions → New repository secret**

| Secret name                          | Source                                    | Notes |
|--------------------------------------|-------------------------------------------|-------|
| `STAGING_AZURE_AD_TENANT_ID`         | HTT tenant ID (same as prod)              | Public-ish identifier; the same GUID prod uses. |
| `STAGING_AZURE_AD_CLIENT_ID`         | App registration **appId**                | `Riverside-Capital-PE-Governance-Platform` — appId `1e3e8417-49f1-4d08-b7be-47045d8a12e9` per ct-wph notes. Already has staging redirect URIs configured. |
| `STAGING_AZURE_AD_CLIENT_SECRET`     | App reg client secret                     | Currently shared with prod. **TODO** (`ct-wph` follow-up #2): rotate so staging has its own secret, and source from Key Vault instead of GitHub Secret. |
| `STAGING_ADMIN_EMAILS`               | Comma-separated emails                    | Optional. May differ from prod (`ct-wph` follow-up #3). Defaults to empty string if unset. |

You can pull the current values from the live webapp if you don't have
them at hand:

```bash
az webapp config appsettings list \
  --name app-governance-staging-xnczpwyv \
  --resource-group rg-governance-staging \
  --query "[?starts_with(name, 'AZURE_AD_') || name=='ADMIN_EMAILS'].{name:name, value:value}" \
  -o table
```

---

## Verifying after setup

1. **Re-run the staging deploy** (push to `main` or manually dispatch
   `Deploy to Staging` from the Actions tab).

2. **Check the workflow run** — you should see this in the log:

   > Setting 9 Azure AD app settings on staging webapp...
   > ✅ Azure AD settings applied to staging webapp

3. **Verify the live state:**

   ```bash
   curl -s https://app-governance-staging-xnczpwyv.azurewebsites.net/api/v1/health/detailed \
     | jq '.azure_configured'
   # Expected: "configured"
   ```

4. **Hit the login page in a browser** and click "Sign in with Microsoft"
   — it should redirect to `login.microsoftonline.com` instead of
   showing the "Azure AD not configured" error.

---

## Why we don't just put these in `parameters.staging.json`

The bicep template (`infrastructure/modules/app-service.bicep`) already
declares `AZURE_AD_*` app settings and pulls from bicep params. So in
principle you could fill the values in `parameters.staging.json` and
they'd flow through on a bicep redeploy.

We don't because:

1. **`azureAdClientSecret` is a secret.** It must not live in a
   git-committed parameter file. Even the non-secret tenant/client IDs
   are "less private" than full secret material, but treating the whole
   bundle uniformly (all in GitHub Secrets / Key Vault) avoids the
   one-day-someone-pastes-the-secret-into-the-wrong-file footgun.

2. **The staging deploy workflow uses `az webapp config container set`,
   not a full bicep redeploy.** So even if the params were filled in,
   they wouldn't take effect until the next infrastructure-shape change.
   Wiring it as an explicit appsettings step makes the dependency
   visible and the diff small.

3. **Per-environment overrides stay obvious** — anyone reading
   `deploy-staging.yml` can see exactly what staging gets. No
   chasing-the-config-graph-through-five-bicep-includes.

---

## Follow-ups (tracked on ct-wph)

1. ✅ Wire AZURE_AD_* into deploy automation (this commit).
2. ⏳ Source `AZURE_AD_CLIENT_SECRET` from Key Vault rather than as an
   inline app setting. The pattern is already used for `JWT_SECRET_KEY`
   (see `infrastructure/modules/app-service.bicep:271` for the
   `@Microsoft.KeyVault(SecretUri=...)` reference syntax).
3. ⏳ Ensure `ADMIN_EMAILS` is set per-environment (staging may want a
   different admin list than prod long-term — e.g. a QA-only group).

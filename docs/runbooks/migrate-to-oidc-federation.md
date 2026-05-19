# Migrate Home-Tenant App Reg to OIDC Federation (kill the runtime secret)

> 🎯 **Prefer a clickable, branded walkthrough?**
> Open [`../migration-cockpit/index.html`](../migration-cockpit/index.html)
> in your browser. Same content, with portal deep-links templated to
> your environment values + click-to-copy commands + progress tracking.
> This Markdown doc is the long-form companion.

## TL;DR

Eliminate `AZURE_AD_CLIENT_SECRET` from the runtime by trusting the App
Service Managed Identity as a federated credential on the management app
registration. After this migration:

- ✅ No more secret to rotate (no more ct-jxe-style 20-day silent outages)
- ✅ No more secret in App Service settings, GitHub Secrets, Key Vault
- ✅ `/health/detailed` reports `auth_mode: oidc` to prove it took
- ✅ `/api/v1/auth/azure/callback` mints a federated `client_assertion`
  JWT from the MI instead of sending a static secret

## Related runbooks (read these first if relevant)

| Doc | Scope | Read when |
|---|---|---|
| `oidc-federation-setup.md` | **Cross-tenant** federated credentials for sync jobs | Already done for the 5 tenant app regs |
| `phase-c-zero-secrets.md` | UAMI + federated credentials, architectural deep-dive | Background reading |
| `enable-secret-fallback.md` | How to revert to secrets if OIDC breaks | Rollback only |
| `rotate-azure-client-secret.md` | Rotation tooling for the OLD secret path | Pre-migration only |

This runbook covers the **home-tenant management app reg** — the one
whose secret is currently in `AZURE_AD_CLIENT_SECRET`. The cross-tenant
sync side is already on OIDC per `oidc-federation-setup.md`.

---

## Prerequisites

Before starting:

- [ ] **App Service has a system-assigned Managed Identity bound.** Verify:
  ```bash
  az webapp identity show \
    --name app-governance-staging-xnczpwyv \
    --resource-group rg-governance-staging \
    --query principalId -o tsv
  ```
  If empty, run `az webapp identity assign --name ... --resource-group ...`
  and note the returned `principalId` for the next step.

- [ ] **You know the home-tenant management app reg's client ID.** This
  is the value currently in `STAGING_AZURE_AD_CLIENT_ID` (GH Secret) and
  `AZURE_AD_CLIENT_ID` (App Service setting). They should match.

- [ ] **You have an Application Administrator role** on the home tenant
  (`0c0e35dc-188a-4eb3-b8ba-61752154b407` for HTT). The federated
  credential mutation needs this.

---

## Step 1 — Add the federated credential on the app reg

Portal path:
**Entra ID → App registrations → `<management-app-reg>` → Certificates &
secrets → Federated credentials → + Add credential**

Pick **"Other issuer"** (NOT the GitHub Actions preset — the issuer here
is the home tenant itself, since the MI lives in the home tenant).

Fields:

| Field | Value |
|---|---|
| Issuer | `https://login.microsoftonline.com/<HOME_TENANT_ID>/v2.0` |
| Subject identifier | The MI's **principal ID** (object ID) from prerequisites |
| Audience | `api://AzureADTokenExchange` |
| Name | `app-service-mi-staging` (or similar — purely for your reference) |

Click **Add**. There's no async propagation lag — the credential is live
when the portal toast fires.

**CLI alternative** (faster if you have the MI principal ID handy):
```bash
APP_OBJECT_ID=$(az ad app show --id "$STAGING_AZURE_AD_CLIENT_ID" \
  --query id -o tsv)
MI_PRINCIPAL=$(az webapp identity show \
  --name app-governance-staging-xnczpwyv \
  --resource-group rg-governance-staging \
  --query principalId -o tsv)

az ad app federated-credential create \
  --id "$APP_OBJECT_ID" \
  --parameters '{
    "name": "app-service-mi-staging",
    "issuer": "https://login.microsoftonline.com/0c0e35dc-188a-4eb3-b8ba-61752154b407/v2.0",
    "subject": "'"$MI_PRINCIPAL"'",
    "audiences": ["api://AzureADTokenExchange"]
  }'
```

---

## Step 2 — Flip the deploy workflow flag

In the GitHub UI:

**Repo Settings → Secrets and variables → Actions → Variables (NOT secrets) → New repository variable**

| Name | Value |
|---|---|
| `STAGING_USE_OIDC_FEDERATION` | `true` |

(It's a **variable**, not a secret — it's just a boolean flag. Variables
show up in PR logs, which is what we want for auditability of the
migration moment.)

---

## Step 3 — Trigger a staging deploy

Any push to `main` works, or manually:
```bash
gh workflow run deploy-staging.yml
```

What you should see in the workflow logs (look at the `Configure Azure AD
app settings` step):

```
Setting Azure AD app settings on staging webapp (oidc_mode=true)...
OIDC mode: removing AZURE_AD_CLIENT_SECRET from app settings (if present)
✅ Azure AD settings applied (OIDC mode — no client_secret in app settings)
```

If you see `oidc_mode=false`, the repo variable wasn't set correctly —
double-check it's a **variable**, not a secret, and the name is exactly
`STAGING_USE_OIDC_FEDERATION` with value exactly `true` (lowercase).

---

## Step 4 — Verify on `/health/detailed`

```bash
curl -s https://app-governance-staging-xnczpwyv.azurewebsites.net/api/v1/health/detailed \
  | jq '.checks.azure_configured'
```

Expected payload **after** the migration:

```json
{
  "status": "configured",
  "auth_mode": "oidc"
}
```

The critical line is **`"auth_mode": "oidc"`**. If you see
`"auth_mode": "secret"`, the runtime didn't pick up the flag (check that
`USE_OIDC_FEDERATION` is in app settings and the webapp restarted).

If `status` is `unauthenticated`:
- AADSTS700016 ("Application with identifier was not found") → the
  federated credential subject doesn't match the MI principal ID. Re-check
  Step 1.
- Any other AADSTS → consult `enable-secret-fallback.md` to revert while
  you debug. The runtime is currently broken.

---

## Step 5 — End-to-end test: actual user login

The probe being green means `client_credentials` works. The interactive
login flow is a separate path — exercise it explicitly:

```
1. Open https://app-governance-staging-xnczpwyv.azurewebsites.net/ in
   an incognito window.
2. Click "Sign in with Microsoft".
3. Complete the Microsoft login.
4. Verify you land on the dashboard with your user info populated.
```

If step 4 fails with "Failed to authenticate with Azure AD", check the
App Service logs for either of:

- `"OIDC federation failed during OAuth callback"` → the MI can't mint
  the assertion. Likely the federated credential's audience or subject is
  wrong. Re-check Step 1.
- `"Azure AD token exchange failed (HTTP 401)"` → Entra accepted our
  assertion but rejected the auth code. Usually means the user isn't in
  the right group; not an OIDC issue.

---

## Step 6 — Delete the dormant secret

Only do this **after** Steps 4 and 5 are green and have been green for
at least 24 hours (so a `/health/detailed` probe rolled over the
5-minute cache and re-verified).

- [ ] **GitHub secret:** Settings → Secrets → Actions → delete
  `STAGING_AZURE_AD_CLIENT_SECRET`
- [ ] **App registration secret:** Entra ID → App registrations →
  `<management-app-reg>` → Certificates & secrets → delete the active
  client secret entry
- [ ] **Key Vault** (if the secret was mirrored there):
  ```bash
  az keyvault secret delete --vault-name <kv> --name azure-ad-client-secret
  ```

After deletion, the staging environment runs with **zero static credentials**.

---

## Rollback

If anything breaks, the fastest path back is:

1. Flip the repo variable: set `STAGING_USE_OIDC_FEDERATION=false` (or
   delete it — the workflow defaults to false on absence).
2. Re-add the GitHub secret `STAGING_AZURE_AD_CLIENT_SECRET` if you
   already deleted it (Step 6 above — pull the old one from your
   password manager, or generate a new one via the app reg portal).
3. Re-run `deploy-staging.yml`.

The workflow re-applies `AZURE_AD_CLIENT_SECRET` to App Service settings
and sets `USE_OIDC_FEDERATION=false`. `/health/detailed` should flip back
to `auth_mode: secret` within a minute or two of the App Service restart.

The federated credential on the app reg can stay (it's harmless when
unused). That way the rollback-forward (re-flipping to OIDC) is just a
variable change.

---

## What about production?

Same playbook, with these substitutions:

- `STAGING_USE_OIDC_FEDERATION` → `PRODUCTION_USE_OIDC_FEDERATION`
- App reg → the prod management app reg
- App Service → `app-governance-prod`
- The deploy-production.yml workflow needs the same patch
  applied to deploy-staging.yml in this migration (filed as a tracking
  issue — see `bd show <prod-issue-id>`).

**Recommend running staging on OIDC for at least 1 week** before
production, so any obscure edge cases (token expiry, MI throttling under
load, etc.) surface in staging first.

---

## What `/health/detailed` now tells you

Pre-migration:
```json
{ "status": "configured", "auth_mode": "secret", "http_status": 200 }
```

Post-migration, healthy:
```json
{ "status": "configured", "auth_mode": "oidc" }
```

Post-migration, MI not bound:
```json
{
  "status": "unauthenticated",
  "auth_mode": "oidc",
  "azure_error_code": "AADSTS700016",
  "detail": "ClientAuthenticationError: ManagedIdentityCredential authentication unavailable"
}
```

Mid-migration (rare race; reload should clear it):
```json
{ "status": "configured", "auth_mode": "secret" }
```
…even when you thought you flipped to OIDC. This means the runtime
hasn't picked up the new `USE_OIDC_FEDERATION` setting yet. Trigger an
App Service restart.

---

## See also

- `app/core/oidc_credential.py` — `OIDCCredentialProvider` (existing)
- `app/core/oidc_client_assertion.py` — federated client assertion helper
  (added with this migration)
- `app/core/azure_credential_probe.py` — `probe_active_credential` —
  the auth-mode-aware health probe
- `tests/unit/test_oidc_client_assertion.py` — contract tests for the
  federated assertion path
- `tests/unit/test_azure_credential_probe.py::TestOIDCProbe` —
  contract tests for the OIDC liveness probe

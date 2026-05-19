# Rotate the Azure AD client secret

**Issue:** [ct-jxe](../../README.md) — prod data syncs frozen since 2026-04-29 (P1).

**Script:** [`scripts/rotate-azure-secret.sh`](../../scripts/rotate-azure-secret.sh)

---

## When to run this

Run this runbook when **all of these are true**:

1. Most sync timestamps in `/api/v1/health/data` are stuck on the same day.
2. Only `riverside_compliance` (config catalog, no Graph call) is updating.
3. `/health/detailed` says `azure_configured: true` (env var is present).

That's the fingerprint of an expired client secret — the env var is *shape*-correct (so the health check passes), but the actual value no longer authenticates against Microsoft Graph.

To confirm before rotating:

```bash
az ad app show --id 1e3e8417-49f1-4d08-b7be-47045d8a12e9 \
  --query "passwordCredentials[].{displayName:displayName, endDateTime:endDateTime}" \
  -o table
```

If the `endDateTime` for the secret currently in use is in the past, rotate.

---

## Step 1 — Generate a new secret in Azure portal

Cannot be scripted — Azure shows the secret "value" exactly once.

1. Azure portal → **App registrations** → **`Riverside-Capital-PE-Governance-Platform`** (appId `1e3e8417-49f1-4d08-b7be-47045d8a12e9`).
2. **Certificates & secrets** → **+ New client secret**.
3. Description: `rotation-YYYY-MM-DD` (today).
4. Expiry: pick the longest the org policy allows (24 months if possible — minimizes future rotation toil).
5. Copy the **Value** column immediately. (Not "Secret ID" — that's just a label.)
6. Paste it into a private password manager entry **first**, then proceed to step 2.

> ⚠️ Do NOT delete the old secret yet. Leave it until step 4 confirms the new one works.

---

## Step 2 — Run the rotation script

```bash
# Interactive (paste the value at the prompt — input is hidden):
./scripts/rotate-azure-secret.sh

# Or from a temp file if your terminal mangles long pastes:
echo -n "<paste-value>" > /tmp/new-secret
./scripts/rotate-azure-secret.sh -f /tmp/new-secret
rm /tmp/new-secret  # do not let it linger
```

What the script does:

1. `az webapp config appsettings set` on **prod** (rg-governance-prod).
2. `az webapp restart` on **prod**.
3. `az webapp config appsettings set` on **staging** (rg-governance-staging).
4. `az webapp restart` on **staging**.
5. `gh secret set STAGING_AZURE_AD_CLIENT_SECRET` on `HTT-BRANDS/control-tower` — so the next `deploy-staging.yml` run doesn't broadcast the OLD value (this is the ct-wph automation).
6. Loops on `/health` until both webapps return 200 (B1 cold-start takes ~30-90s).
7. Dumps a summary of `/api/v1/health/data` so you can spot-check.

Safety properties (locked by `tests/unit/test_rotate_azure_secret_script.py`):

- Secret never passed via argv — `ps`, shell history, and `/proc/<pid>/cmdline` stay clean.
- `read -rs` for interactive entry (no terminal echo).
- Min-length check rejects truncated pastes.
- `--dry-run` available for pre-flight.
- `--skip-prod` / `--skip-staging` / `--skip-github` for partial-rotation flows.
- Restarts each webapp (without this, the new env var doesn't take effect until the next platform-initiated recycle, which can be hours).
- Does NOT do a bicep redeploy (much bigger blast radius for no reason).

---

## Step 3 — Wait 5-10 minutes for schedulers

Sync jobs fire every 5 minutes by default. After the restart, the **first** tick on the new secret happens within ~5 min on prod and ~5 min on staging.

While you wait, you can confirm the webapp is healthy:

```bash
curl -s https://app-governance-prod.azurewebsites.net/health | jq .
# expect: {"status":"healthy", ...}
```

---

## Step 4 — Verify syncs are climbing

```bash
curl -s https://app-governance-prod.azurewebsites.net/api/v1/health/data \
  | jq '.tenants["Head-To-Toe (HTT)"]'
```

Expected: all timestamps less than ~10 minutes old. `stale` should be `false`.

If still stale after 15 minutes:

- Check Application Insights for sync-job errors filtered to today's date. Look for `MsalAuthenticationException` / `AADSTS7000215` (the standard "invalid client secret" error code).
- Verify the app registration's Graph API permissions still have **admin consent granted**. Sometimes a tenant admin revokes consent without realising.
- Specifically check **Delta Crown Extensions (DCE)** — historically a problem child. It may have its own per-tenant app registration that needs a separate rotation.

---

## Step 5 — Delete the old secret in Azure portal

Once step 4 confirms green:

1. Azure portal → App reg → Certificates & secrets.
2. Find the old secret (the one whose `endDateTime` is in the past).
3. Delete it. Leaving it around is a credential surface for no benefit.

---

## Step 6 — Mark ct-jxe closed

```bash
bd close ct-jxe -m "Rotated AZURE_AD_CLIENT_SECRET on YYYY-MM-DD. \
Verified: /api/v1/health/data shows fresh timestamps across all tenants. \
Old secret deleted from app registration."
```

If the rotation revealed any per-tenant secret issues (e.g. DCE needed its own rotation), file follow-ups before closing.

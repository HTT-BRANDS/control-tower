# Sync Tenant Auth Investigation Checklist — issue 918b

**Issue:** `azure-governance-platform-918b`  
**Purpose:** turn the five noisy production tenant IDs into a deterministic, reviewable auth-path verdict instead of another folklore-powered debugging session.

---

## Impacted tenant IDs from 2026-04-23 evidence

- `ce62e17d-2feb-4e67-a115-8ea4af68da30`
- `0c0e35dc-188a-4eb3-b8ba-61752154b407`
- `3c7d2bf3-b597-4766-b5cb-2b489c2904d6`
- `b5380912-79ec-452d-a6ca-6d897b19b294`
- `98723287-044b-4bbb-9294-19857d4128a0`

These are the tenants associated with repeated production log signatures:

- `Key Vault credentials not found for tenant ...`
- `falling back to settings credentials`

---

## Objective

For **each** impacted tenant, produce a reviewable answer to all of these:

1. Is the tenant row active?
2. Is it expected to use Lighthouse/shared credentials, explicit per-tenant secret refs, standard Key Vault secret pairs, OIDC/UAMI app IDs, or nothing at all?
3. Is the tenant currently scheduler-eligible according to the same logic the app uses?
4. Does Key Vault secret metadata actually support that expectation?
5. If the tenant is noisy in logs, is that noise expected, a config bug, or evidence that the tenant should not be scheduled at all?

No closure on `918b` without those answers.

---

## Evidence to export

### 1. Tenant rows from production DB

Use the query from `docs/runbooks/sync-recovery-verification.md` §2.6 and export JSON with at least:

- `name`
- `tenant_id`
- `is_active`
- `use_lighthouse`
- `use_oidc`
- `client_id`
- `client_secret_ref`

### 2. Production App Service settings

Export **metadata only** from the production app:

```bash
az webapp config appsettings list \
  -g rg-governance-production \
  -n app-governance-prod \
  -o json > /tmp/prod-app-settings.json
```

You care especially about:

- `USE_UAMI_AUTH`
- `USE_OIDC_FEDERATION`
- `KEY_VAULT_URL`
- `AZURE_CLIENT_ID`
- whether shared-secret mode is plausibly active

### 3. Key Vault secret names only

Export **names/metadata only**, not secret values:

```bash
az keyvault secret list \
  --vault-name kv-gov-prod \
  --query '[].{name:name}' \
  -o json > /tmp/prod-keyvault-secret-names.json
```

### 4. Log evidence for the same time window

Retain the App Service / App Insights evidence that shows the fallback spam so you can compare tenant classification against actual runtime noise.

---

## Run the classifier

```bash
uv run python scripts/investigate_sync_tenant_auth.py \
  --tenants-json /tmp/prod-tenants.json \
  --app-settings-json /tmp/prod-app-settings.json \
  --keyvault-secrets-json /tmp/prod-keyvault-secret-names.json \
  --tenant-id ce62e17d-2feb-4e67-a115-8ea4af68da30 \
  --tenant-id 0c0e35dc-188a-4eb3-b8ba-61752154b407 \
  --tenant-id 3c7d2bf3-b597-4766-b5cb-2b489c2904d6 \
  --tenant-id b5380912-79ec-452d-a6ca-6d897b19b294 \
  --tenant-id 98723287-044b-4bbb-9294-19857d4128a0 \
  --output-json /tmp/tenant-auth-investigation-918b.json \
  --output-md /tmp/tenant-auth-investigation-918b.md
```

The report now includes:

- `expected_auth_path`
- `scheduler_eligible`
- `scheduler_reason`
- `config_status`
- `recommended_action`

That should be enough to stop people arguing in circles.

---

## Expected interpretation patterns

### Case A — `scheduler_eligible=no`, `reason=missing_db_declared_secret_path`
Meaning: the tenant should not be participating in scheduled sync in secret/Key Vault mode.

**Action:** disable it for scheduled sync or add an explicit auth path.

### Case B — `expected_auth_path=explicit_per_tenant_secret_ref`, `config_status=missing_secret_metadata`
Meaning: DB row says explicit per-tenant secret, but Key Vault metadata does not support it.

**Action:** create/fix the referenced secret or correct the DB row.

### Case C — `expected_auth_path=lighthouse_shared_credentials`
Meaning: tenant is intentionally on shared/Lighthouse creds.

**Action:** prove that this is intended and that the shared creds are the ones being used.

### Case D — `expected_auth_path=standard_key_vault_secret_pair`
Meaning: tenant appears to depend on `{tenant-id}-client-id` and `{tenant-id}-client-secret` secrets.

**Action:** verify both names exist and match the intended credential pattern.

### Case E — `runtime_mode=uami` or `runtime_mode=oidc`
Meaning: stop looking for secret-pair explanations first; resolve the app-ID mapping story.

---

## Exit criteria for 918b

Before closing `918b`, attach evidence showing:

- the classification report for the five impacted tenants
- the production runtime mode
- whether each noisy tenant is expected or misconfigured
- what changed (tenant row, secret metadata, scheduler behavior, or disablement)
- a post-change log sample showing the fallback spam has stopped or been correctly explained

Only after that should `0gz3` be treated as meaningfully verifiable.

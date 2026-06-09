# Runbook: Revoke domain-intelligence external credentials at source

**Issue:** ct-18z (P3) - carved out of ct-mql decommission (2026-06-02)
**Owner / executor:** Tyler (requires Cloudflare + Cloudways portal access - cannot be automated by an agent)
**Reference:** `docs/SECRETS_OF_RECORD.md` section 5a
**Estimated time:** ~5 minutes

---

## Why this exists

When the `kv-domainiq-prod` Key Vault was deleted during the ct-mql decommission,
two credentials it held were for **external services**. Deleting the Azure vault
does NOT revoke those - they remain valid at the provider until revoked at source:

| Secret | Lives at | Action required |
|--------|----------|-----------------|
| `cloudflare-api-token` | Cloudflare | Revoke the API token |
| `CLOUDWAYS-SSH-PASSWORD` | Cloudways | Rotate/disable the SSH password |

Until both are revoked, a leaked copy of either value would still grant access.

## If you need the values (to identify which token/account)

The archived copies are available - read-only, for identification only:

- `kv-gov-prod` -> `domainiq-archived-cloudflare-api-token`
- `kv-gov-prod` -> `domainiq-archived-CLOUDWAYS-SSH-PASSWORD`
- Or recover from soft-deleted `kv-domainiq-prod` (purge-protected until **2026-08-31**).

```bash
# Identify (do NOT paste these values anywhere else):
az keyvault secret show --vault-name kv-gov-prod \
  --name domainiq-archived-cloudflare-api-token --query value -o tsv
az keyvault secret show --vault-name kv-gov-prod \
  --name domainiq-archived-CLOUDWAYS-SSH-PASSWORD --query value -o tsv
```

## Step 1 - Revoke the Cloudflare API token

1. Log in to the Cloudflare dashboard.
2. Go to **My Profile -> API Tokens** (`https://dash.cloudflare.com/profile/api-tokens`).
3. Find the token matching the archived value (compare the token id / name; the
   raw secret is only shown at creation, so match by name or last-used metadata).
4. Click the row's menu -> **Delete** (or **Roll** if a replacement is still needed -
   for decommission, **Delete** is correct).
5. Confirm. The token is now invalid everywhere immediately.

## Step 2 - Rotate/disable the Cloudways SSH password

1. Log in to the Cloudways platform (`https://platform.cloudways.com`).
2. Identify the server/account tied to the archived SSH password.
3. **Server Management -> Master Credentials** (or the relevant SSH/SFTP user):
   - Preferred: **regenerate/change** the SSH password so the archived value is dead, OR
   - If the server itself is being decommissioned, **delete the server/credential**.
4. Save. The old password no longer authenticates.

## Step 3 - Confirm and close

- [ ] Cloudflare token deleted (or rolled) - verified gone from the API Tokens list.
- [ ] Cloudways SSH password rotated/disabled (or server deleted).
- [ ] Optional: note the date in `docs/SECRETS_OF_RECORD.md` section 5a.
- [ ] `bd close ct-18z` with a one-line note ("revoked at source YYYY-MM-DD").

## Post-revocation: the archived copies

The `kv-gov-prod` archived copies and the soft-deleted `kv-domainiq-prod` become
harmless once the source creds are dead. You may leave them to expire naturally
(`kv-domainiq-prod` purge-protection lapses 2026-08-31) or purge the archived
secrets from `kv-gov-prod` now:

```bash
az keyvault secret delete --vault-name kv-gov-prod --name domainiq-archived-cloudflare-api-token
az keyvault secret delete --vault-name kv-gov-prod --name domainiq-archived-CLOUDWAYS-SSH-PASSWORD
```

# OIDC Workload Identity Federation — Tenant Authentication

> **tl;dr:** The platform authenticates to all 5 Riverside tenants using the App
> Service Managed Identity — no secrets, no Key Vault, no rotation headaches.

---

## Overview

Previously, each tenant required a `client_secret` stored in Azure Key Vault and
rotated every 90 days. With **OIDC Workload Identity Federation** that entire
secret lifecycle is eliminated. The App Service Managed Identity (MI) presents an
OIDC token, each tenant's app registration is pre-configured to trust it, and
Azure AD mints a short-lived access token on the fly.

**Zero secrets at runtime. Zero rotation. Zero Key Vault dependency.**

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────────┐
│  App Service (governance-platform)                                  │
│                                                                     │
│  1. OIDCCredentialProvider                                          │
│     └─ ManagedIdentityCredential.get_token(                         │
│            "api://AzureADTokenExchange"                             │
│        )  ──────────────────────────────────────────────────────┐   │
│                                                                  │   │
│  2. ClientAssertionCredential(                                   │   │
│       tenant_id  = <target tenant>,                              │   │
│       client_id  = <target app registration>,                    │   │
│       func       = lambda: <OIDC token from step 1>             │   │
│     )                                                            │   │
└─────────────────────────────────────────────────────────────────┼───┘
                                                                   │
              OIDC assertion (JWT)                                  │
                                                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Azure AD (managing tenant: HTT — 0c0e35dc-...)                      │
│                                                                      │
│  Issues OIDC token signed by:                                        │
│  issuer:  https://login.microsoftonline.com/0c0e35dc-.../v2.0        │
│  subject: <Managed Identity Object ID>                               │
│  audience: api://AzureADTokenExchange                                │
└───────────────────────────────┬──────────────────────────────────────┘
                                │  token exchange
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Azure AD (target tenant, e.g. BCC — b5380912-...)                   │
│                                                                      │
│  App registration: 4861906b-... has a Federated Identity Credential: │
│    issuer:  https://login.microsoftonline.com/0c0e35dc-.../v2.0      │
│    subject: <same MI Object ID>   ◄─── TRUST IS HERE                │
│    audience: api://AzureADTokenExchange                              │
│                                                                      │
│  ✓ Trust verified → issues access token for BCC tenant              │
└──────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                  Platform calls BCC ARM/Graph APIs ✅
```

### Key Points

- The MI identity is established **once** per App Service deployment.
- Each tenant's app registration must be configured with a **Federated Identity
  Credential** that names the managing tenant as the issuer and the MI object ID
  as the subject. This is a one-time operation.
- Azure handles token exchange and rotation automatically. Tokens live 5–10
  minutes; the SDK refreshes them transparently.

---

## Credential Resolution Order

The `OIDCCredentialProvider` (`app/core/oidc_credential.py`) checks the
environment and selects the appropriate credential strategy:

| Priority | Environment | Strategy | Env Var Trigger |
|----------|-------------|----------|-----------------|
| 1 | **Azure App Service** (prod/staging) | `ClientAssertionCredential` backed by `ManagedIdentityCredential` | `WEBSITE_SITE_NAME` is set |
| 2 | **CI / Kubernetes** (workload identity) | `WorkloadIdentityCredential` | `AZURE_FEDERATED_TOKEN_FILE` is set |
| 3 | **Local development** | `DefaultAzureCredential` (az login, VS Code, etc.) | neither of the above |

> ⚠️ On local dev you'll see a `WARNING` log: _"Using DefaultAzureCredential (local
> development fallback) …"_ — this is expected and harmless.

---

## Prerequisites

Before running the setup script you need:

1. **Azure CLI** installed and authenticated (`az login`)
2. **App Service Managed Identity** enabled on the governance platform App Service
   — either system-assigned or user-assigned
3. The **Managed Identity Object ID** (see below)
4. **Application Administrator** (or Global Admin) in each of the 5 tenants so
   you can create federated credentials on app registrations

### Finding the Managed Identity Object ID

```bash
# System-assigned MI
az webapp identity show \
  --name app-governance-prod \
  --resource-group rg-governance-production \
  --query principalId \
  --output tsv

# User-assigned MI
az identity show \
  --name <mi-name> \
  --resource-group <rg> \
  --query principalId \
  --output tsv
```

---

## Step 1: Configure Federated Credentials (One-Time)

Run the setup script to configure OIDC federation on all 5 app registrations:

```bash
./scripts/setup-federated-creds.sh \
  --managing-tenant-id 0c0e35dc-188a-4eb3-b8ba-61752154b407 \
  --mi-object-id <MI_OBJECT_ID>
```

### What the script does

For each of the 5 tenants it:

1. Logs in to that tenant via `az login --tenant <tenant_id> --allow-no-subscriptions`
2. Checks if a federated credential named `governance-platform-app-service` already
   exists on the app registration (idempotent — safe to re-run)
3. If not present, creates it with:
   - **issuer** `https://login.microsoftonline.com/0c0e35dc-.../v2.0`
   - **subject** `<MI_OBJECT_ID>`
   - **audiences** `["api://AzureADTokenExchange"]`
4. Prints a colour-coded status line (✓ green / ⚠ yellow already-exists / ✗ red error)
5. Exits 1 if any tenant fails

### Useful flags

| Flag | Description |
|------|-------------|
| `--managing-tenant-id <id>` | **Required.** HTT tenant ID (the MI's home tenant) |
| `--mi-object-id <id>` | **Required.** Object ID of the Managed Identity |
| `--verify-only` | Read-only mode — checks config without creating anything |
| `--tenant HTT\|BCC\|FN\|TLL\|DCE` | Run for a single tenant only |
| `--name <name>` | Override federated cred name (default: `governance-platform-app-service`) |

### Example: dry-run first

```bash
./scripts/setup-federated-creds.sh \
  --managing-tenant-id 0c0e35dc-188a-4eb3-b8ba-61752154b407 \
  --mi-object-id xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx \
  --verify-only
```

---

## Step 2: Set App Service Environment Variables

```bash
# Enable OIDC federation
az webapp config appsettings set \
  --name app-governance-prod \
  --resource-group rg-governance-production \
  --settings USE_OIDC_FEDERATION=true

# Only needed for user-assigned MI (omit for system-assigned)
az webapp config appsettings set \
  --name app-governance-prod \
  --resource-group rg-governance-production \
  --settings AZURE_MANAGED_IDENTITY_CLIENT_ID=<user-assigned-mi-client-id>
```

You can also set these in `.env` for local dev overrides (never commit secrets):

```bash
USE_OIDC_FEDERATION=true
AZURE_MANAGED_IDENTITY_CLIENT_ID=          # leave empty for system-assigned
AZURE_TENANT_ID=0c0e35dc-188a-4eb3-b8ba-61752154b407   # HTT managing tenant
AZURE_CLIENT_ID=1e3e8417-49f1-4d08-b7be-47045d8a12e9   # HTT app registration
```

---

## Step 3: Run Database Migration

If not already applied:

```bash
uv run alembic upgrade head
```

This applies migration `007_add_oidc_federation.py` which adds the `use_oidc`
boolean column to the `tenants` table (default `False`).

---

## Step 4: Seed Tenant Records

Upsert all 5 Riverside tenants into the database with `use_oidc=True`:

```bash
# Dry run (shows what would happen, no DB writes)
uv run python scripts/seed_riverside_tenants.py --dry-run

# Actually seed
uv run python scripts/seed_riverside_tenants.py
```

Each record gets:
- A deterministic UUID derived from the tenant ID (idempotent re-runs)
- `client_secret_ref = None` — no secrets stored
- `use_oidc = True`

To reset and re-seed from scratch:

```bash
uv run python scripts/seed_riverside_tenants.py --reset
```

---

## Step 5: Verify Configuration

### Check federated credentials are configured

```bash
./scripts/verify-federated-creds.sh \
  --managing-tenant-id 0c0e35dc-188a-4eb3-b8ba-61752154b407 \
  --mi-object-id <MI_OBJECT_ID>
```

This is read-only and shows, for each tenant:
- Whether the `governance-platform-app-service` credential exists
- The configured issuer, subject, and audiences
- A PASS/FAIL status

### Check the preflight API

```bash
curl -s https://app-governance-prod.azurewebsites.net/api/v1/preflight \
  | python3 -m json.tool
```

A successful OIDC response will show `"auth_mode": "oidc_federation"` (or
equivalent) without any `client_secret` references.

---

## Tenant App Registration Details

| Code | Tenant ID | App Registration (client_id) |
|------|-----------|------------------------------|
| **HTT** | `0c0e35dc-188a-4eb3-b8ba-61752154b407` | `1e3e8417-49f1-4d08-b7be-47045d8a12e9` |
| **BCC** | `b5380912-79ec-452d-a6ca-6d897b19b294` | `4861906b-2079-4335-923f-a55cc0e44d64` |
| **FN** | `98723287-044b-4bbb-9294-19857d4128a0` | `7648d04d-ccc4-43ac-bace-da1b68bf11b4` |
| **TLL** | `3c7d2bf3-b597-4766-b5cb-2b489c2904d6` | `52531a02-78fd-44ba-9ab9-b29675767955` |
| **DCE** | `ce62e17d-2feb-4e67-a115-8ea4af68da30` | `79c22a10-3f2d-4e6a-bddc-ee65c9a46cb0` |

These values are the source of truth in `app/core/tenants_config.py`.

---

## Local Development

OIDC federation requires an actual Azure Managed Identity, so it cannot be used
locally. The `OIDCCredentialProvider` falls back to `DefaultAzureCredential`
automatically when not running on App Service.

```bash
# Log in to Azure
az login

# (Optional) Set a specific tenant
az login --tenant 0c0e35dc-188a-4eb3-b8ba-61752154b407
```

`DefaultAzureCredential` will pick up your `az login` session and authenticate
to each tenant using your own account's cross-tenant permissions (subject to
Conditional Access policies in each tenant).

### Testing against real tenants from a local machine

If you need to test the real OIDC flow locally (e.g. debugging token exchange
errors), you can impersonate a service principal with a certificate:

```bash
az login \
  --service-principal \
  --username <app-id> \
  --password <path-to-cert.pem> \
  --tenant <tenant-id>
```

For CI/CD OIDC setup (GitHub Actions), see `docs/OIDC_SETUP.md`.

---

## Troubleshooting

### `AADSTS70021: No matching federated identity record found`

The federated credential hasn't been created on this tenant's app registration,
or the issuer/subject/audience don't match exactly.

**Fix:** Re-run `setup-federated-creds.sh --verify-only` to see what's
configured, then re-run without `--verify-only` for the failing tenant:

```bash
./scripts/setup-federated-creds.sh \
  --managing-tenant-id 0c0e35dc-... \
  --mi-object-id <id> \
  --tenant BCC
```

### `AADSTS50020: User account from identity provider does not exist in tenant`

The **subject** in the federated credential doesn't match the MI object ID
you're presenting. Common cause: you used the MI's **client ID** instead of its
**object ID** (principal ID).

**Fix:** Get the correct value:

```bash
az webapp identity show \
  --name app-governance-prod \
  --resource-group rg-governance-production \
  --query principalId -o tsv   # <-- this is the Object ID, use this
```

Then re-create the federated credential with the correct subject:

```bash
./scripts/setup-federated-creds.sh \
  --managing-tenant-id 0c0e35dc-... \
  --mi-object-id <CORRECT_OBJECT_ID> \
  --tenant BCC
```

### `ManagedIdentityCredentialError` / `CredentialUnavailableError`

The App Service doesn't have a Managed Identity enabled, or the
`AZURE_MANAGED_IDENTITY_CLIENT_ID` environment variable points to a MI that
doesn't exist / isn't assigned to this App Service.

**Fix:**

```bash
# Enable system-assigned MI
az webapp identity assign \
  --name app-governance-prod \
  --resource-group rg-governance-production

# Or verify user-assigned MI assignment
az webapp identity show \
  --name app-governance-prod \
  --resource-group rg-governance-production
```

### `WARNING: Using DefaultAzureCredential (local development fallback)`

You're running locally — this is **expected and correct** behaviour. The
credential will use your `az login` session. You only see this warning outside
App Service or Kubernetes/CI environments.

### Token exchange succeeds but API calls return 403

The app registration doesn't have the required API permissions in the target
tenant (e.g. `Directory.Read.All` for Graph, `reader` on the subscription for
ARM). These permissions are separate from the federated credential setup and
must be granted by an admin in each tenant.

---

## Security Notes

| Property | Value |
|----------|-------|
| **Secrets at runtime** | Zero — no client secrets anywhere in the system |
| **Token lifetime** | 5–10 minutes (automatic rotation by Azure AD) |
| **Revocation** | Delete or modify the federated credential in the app registration |
| **Blast radius** | Each tenant's trust is scoped to a single MI object ID |
| **Audit trail** | All token exchanges appear in Azure AD Sign-in logs (service principal sign-ins) |
| **MFA / CA policies** | Workload identity conditional access can be applied per-tenant |
| **Secret rotation** | N/A — there are no secrets to rotate |

### What you cannot do with a compromised MI

- Authenticate as a human user
- Bypass tenant-specific Conditional Access policies on the app registration
- Access tenants where no federated credential has been configured

### Revoking access to a specific tenant

Navigate to:
**Azure Portal → \<target tenant\> → App Registrations → \<app\> →
Certificates & Secrets → Federated Credentials → Delete `governance-platform-app-service`**

Or via CLI (while logged in to the target tenant):

```bash
az ad app federated-credential delete \
  --id <app-registration-client-id> \
  --federated-credential-id <credential-id>
```

---

## Related Docs

- `docs/OIDC_SETUP.md` — CI/CD GitHub Actions OIDC federation (separate topic)
- `docs/TENANT_SETUP.md` — General tenant onboarding
- `docs/PERMISSIONS_REFERENCE.md` — Required API permissions per tenant
- `scripts/setup-federated-creds.sh` — Setup script (annotated source)
- `scripts/verify-federated-creds.sh` — Verification script
- `app/core/oidc_credential.py` — Runtime credential provider implementation

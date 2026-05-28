# OIDC Workload Identity Federation — Cross-Tenant Setup

## Overview

The Azure Governance Platform uses OIDC Workload Identity Federation (no secrets)
to authenticate from the production App Service into each Riverside tenant's
Azure AD. This requires configuring **federated identity credentials** on each
tenant's app registration.

## Current Error

```
AADSTS700236: Entra ID tokens issued by issuer 
'https://login.microsoftonline.com/0c0e35dc-188a-4eb3-b8ba-61752154b407/v2.0' 
may not be used for federated identity credentials
```

## Prerequisites

- **App Service Managed Identity Principal ID:** `8ff7caa7-566b-428f-b76e-b122ebd43365`
- **Home Tenant (HTT):** `0c0e35dc-188a-4eb3-b8ba-61752154b407`
- **Managed Identity Issuer:** `https://login.microsoftonline.com/0c0e35dc-188a-4eb3-b8ba-61752154b407/v2.0`

## Per-Tenant Configuration

For **each** of the 5 tenants, perform these steps:

### Step 1: Verify App Registration Exists

Each tenant needs an app registration with the `app_id` (client_id) from `config/tenants.yaml`:

| Tenant | Code | Tenant ID | App Registration Client ID |
|--------|------|-----------|---------------------------|
| Head-To-Toe | HTT | `0c0e35dc-188a-4eb3-b8ba-61752154b407` | `1e3e8417-49f1-...` |
| Bishops | BCC | `b5380912-79ec-452d-a6ca-6d897b19b294` | `4861906b-2079-...` |
| Frenchies | FN | `98723287-044b-4bbb-9294-19857d4128a0` | `7648d04d-ccc4-...` |
| Lash Lounge | TLL | `3c7d2bf3-b597-4766-b5cb-2b489c2904d6` | `52531a02-78fd-...` |
| Delta Crown | DCE | `ce62e17d-2feb-4e67-a115-8ea4af68da30` | `1e3e8417-49f1-...` |

### Step 2: Add Federated Identity Credential

For each tenant's app registration, add a federated identity credential:

```bash
# Template — replace TENANT_ID, APP_OBJECT_ID for each tenant
az ad app federated-credential create \
  --id <APP_OBJECT_ID> \
  --parameters '{
    "name": "governance-platform-mi",
    "issuer": "https://login.microsoftonline.com/0c0e35dc-188a-4eb3-b8ba-61752154b407/v2.0",
    "subject": "8ff7caa7-566b-428f-b76e-b122ebd43365",
    "audiences": ["api://AzureADTokenExchange"],
    "description": "Azure Governance Platform App Service Managed Identity"
  }'
```

> **Note:** The `--id` parameter is the **Object ID** of the app registration
> (not the client/application ID). Find it with:
> `az ad app show --id <CLIENT_ID> --query id -o tsv`

### Step 3: Grant Graph API Permissions

Each app registration needs these **Application** permissions with admin consent:

| Permission | Type | Purpose |
|-----------|------|---------|
| `Directory.Read.All` | Application | Read users, groups, roles |
| `Reports.Read.All` | Application | MFA registration details |
| `SecurityEvents.Read.All` | Application | Security alerts |
| `Domain.Read.All` | Application | Domain verification status |
| `AuditLog.Read.All` | Application | Sign-in activity (optional) |

```bash
# Grant permissions (requires Global Admin consent)
# Get the MS Graph service principal ID first
GRAPH_SP=$(az ad sp list --filter "displayName eq 'Microsoft Graph'" --query "[0].id" -o tsv)

# Add each permission
az ad app permission add --id <APP_OBJECT_ID> \
  --api 00000003-0000-0000-c000-000000000000 \
  --api-permissions \
    7ab1d382-f21e-4acd-a863-ba3e13f7da61=Role \
    230c1aed-a721-4c5d-9cb4-a90514e508ef=Role \
    bf394140-e372-4bf9-a898-299cfc7564e5=Role \
    dbb9058a-0e50-45d7-ae91-66909b5d4664=Role

# Grant admin consent
az ad app permission admin-consent --id <APP_OBJECT_ID>
```

### Step 4: Verify

After configuring all 5 tenants, restart the App Service:

```bash
az webapp restart --name app-governance-prod --resource-group rg-governance-production

# Wait for sync (next hourly cron)
# Then check:
# 1. Logs should show successful Graph API calls
# 2. riverside_mfa table should have data
# 3. Dashboard should show real metrics
```

## HTT (Home Tenant) — Special Case

HTT is the home tenant where the Managed Identity lives. OIDC federation
should work automatically here because the MI can get tokens for its own
tenant without cross-tenant federation. If HTT still fails, check that:
1. The app registration exists with the correct client_id
2. Graph API permissions are granted with admin consent
3. The MI has the `User.Read.All` scope at minimum

## Troubleshooting

### Error: AADSTS700236
Federated identity credential not configured on the target tenant's app registration.
Run Step 2 above.

### Error: AADSTS700025
Subject claim mismatch. Verify the `subject` field matches the MI Principal ID exactly.

### Error: Insufficient privileges
Graph API permissions not granted or admin consent not given. Run Step 3 above.

### Circuit Breaker Tripping
After fixing, restart the App Service to reset the circuit breaker state.
The breaker opens after 5 failures and stays open for 60 seconds.

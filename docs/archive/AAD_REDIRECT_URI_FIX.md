# Azure AD Redirect URI Fix

**Date:** 2026-03-27  
**Agent:** code-puppy-ecf058  
**Issue:** Production app missing redirect URI causing authentication errors

---

## Problem

Users attempting to log into the production environment were receiving Azure AD authentication errors because the production redirect URI was not configured in the app registration.

**Error:** `AADSTS50011: The reply URL specified in the request does not match the reply URLs configured for the application`

---

## Solution

Added production redirect URIs to the HTT Azure AD app registration.

---

## HTT App Registration (1e3e8417-49f1-4d08-b7be-47045d8a12e9)

### Before Fix (4 URIs)

| URI | Environment |
|-----|-------------|
| http://localhost:8000/login | Local dev |
| http://localhost:8000/auth/callback | Local dev |
| https://app-governance-staging-xnczpwyv.azurewebsites.net/login | Staging |
| https://app-governance-staging-xnczpwyv.azurewebsites.net/auth/callback | Staging |

### After Fix (6 URIs)

| URI | Environment |
|-----|-------------|
| http://localhost:8000/login | Local dev |
| http://localhost:8000/auth/callback | Local dev |
| https://app-governance-staging-xnczpwyv.azurewebsites.net/login | Staging |
| https://app-governance-staging-xnczpwyv.azurewebsites.net/auth/callback | Staging |
| **https://app-governance-prod.azurewebsites.net/login** | **Production** ✅ |
| **https://app-governance-prod.azurewebsites.net/auth/callback** | **Production** ✅ |

---

## Action Taken

```bash
# Updated HTT app registration with all redirect URIs including production
az ad app update --id 1e3e8417-49f1-4d08-b7be-47045d8a12e9 \
  --web-redirect-uris \
  "http://localhost:8000/login" \
  "http://localhost:8000/auth/callback" \
  "https://app-governance-staging-xnczpwyv.azurewebsites.net/login" \
  "https://app-governance-staging-xnczpwyv.azurewebsites.net/auth/callback" \
  "https://app-governance-prod.azurewebsites.net/login" \
  "https://app-governance-prod.azurewebsites.net/auth/callback"
```

---

## Multi-Tenant App Registrations

The following app registrations are in **other tenants** and require separate configuration:

| Tenant | App ID | Status |
|--------|--------|--------|
| BCC | 4861906b-2079-4335-923f-a55cc0e44d64 | ❌ Not in HTT tenant |
| FN | 7648d04d-ccc4-43ac-bace-da1b68bf11b4 | ❌ Not in HTT tenant |
| TLL | (see tenant config) | ❌ Not in HTT tenant |

**Note:** These app registrations are in their respective tenant directories. To configure redirect URIs for multi-tenant authentication, you would need to:

1. Switch to the target tenant context, OR
2. Have a global admin configure them in each tenant's Azure AD

---

## Verification

✅ Production redirect URIs now configured  
✅ Authentication should work for https://app-governance-prod.azurewebsites.net  
✅ Existing staging and local dev URIs preserved

---

## Testing

1. Navigate to https://app-governance-prod.azurewebsites.net/login
2. Click "Sign in with Microsoft"
3. Azure AD should now redirect successfully back to the app

---

## Related Documentation

- [INFRASTRUCTURE_INVENTORY.md](./INFRASTRUCTURE_INVENTORY.md)
- [SESSION_HANDOFF.md](./SESSION_HANDOFF.md)

---

## Follow-Up: OAuth Callback 500 Error (2026-03-27)

**Agent:** planning-agent-9a4ce8

### Problem After Redirect URI Fix

After adding production redirect URIs, the Azure AD redirect worked correctly (no more `AADSTS50011` error). However, the OAuth callback at `/api/v1/auth/azure/callback` returned HTTP 500. The login page showed "An unexpected error occurred".

**Console errors observed:**
- `Failed to load resource: server responded with status 500` on `api/v1/auth/azure/callback`
- `OAuth callback error: Error: An unexpected error occurred`
- `Failed to load resource: server responded with status 500` on `api/v1/auth/login`

### Root Cause

1. The global exception handler in `app/main.py` masks real errors in production (`DEBUG=false`)
2. The Bicep infrastructure template was missing all Azure AD environment variables
3. The `DATABASE_URL` connection string lacked managed identity authentication parameters
4. The `azure_oauth_callback` handler had no try/except for httpx or database errors

### Fix Applied

| File | Change |
|------|--------|
| `app/api/routes/auth.py` | Added pre-flight config validation, httpx error handling, non-fatal DB sync |
| `infrastructure/modules/app-service.bicep` | Added 12 Azure AD/security app settings, fixed DATABASE_URL |
| `infrastructure/main.bicep` | Pass-through for new params |
| `scripts/diagnose-production.sh` | New diagnostic tool for production auth issues |

### Status

✅ Code fixes ready in v1.6.3-dev  
⏳ Requires deployment to production + Azure AD App Service config update

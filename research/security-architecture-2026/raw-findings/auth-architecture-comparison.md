# Authentication Architecture — Detailed Comparison

## Current Implementation Analysis

### Token Flow (from app/core/auth.py)

```
Browser Login:
  User → POST /api/v1/auth/login (credentials)
       → JWTTokenManager.create_access_token() [HS256, 30min]
       → JWTTokenManager.create_refresh_token() [HS256, 7d, with jti]
       → Set-Cookie: access_token (HttpOnly)
       → Return { access_token, refresh_token, token_type: "bearer" }

Azure AD Login:
  User → GET /api/v1/auth/azure/login
       → Redirect to Azure AD authorize endpoint
       → Azure AD callback with authorization code
       → POST /api/v1/auth/azure/callback
       → Exchange code for Azure AD tokens
       → AzureADTokenValidator.validate_token() [RS256, JWKS verification]
       → JWTTokenManager.create_access_token() [HS256, internal token]
       → Set-Cookie: access_token (HttpOnly)

API Request:
  Client → Authorization: Bearer <token>
         → get_current_user() dependency
         → Check token blacklist
         → Detect issuer (Azure AD vs internal)
         → If Azure AD: validate_token() with JWKS [RS256]
         → If internal: decode_token() with secret [HS256]
         → Return User object with roles + tenant_ids
```

### Security Controls Present
- ✅ Algorithm confusion prevention (checks issuer, not algorithm header)
- ✅ Token type validation (access vs refresh)
- ✅ Token blacklist with Redis backend (in-memory fallback)
- ✅ JWKS caching (24-hour TTL)
- ✅ Production-enforced JWT_SECRET_KEY (can't start without explicit key)
- ✅ HttpOnly cookies for browser auth
- ✅ Security headers middleware (HSTS, CSP, X-Frame-Options, etc.)
- ✅ Rate limiting on auth endpoints

### Security Controls Missing
- ❌ Refresh token rotation (tokens reusable for full 7-day window)
- ❌ Nonce in token claims (replay prevention)
- ❌ Token binding to client fingerprint
- ⚠️ Password validation is placeholder in development mode

## Easy Auth Architecture (from Microsoft docs)

### How It Works on Linux Containers
- Runs as **separate sidecar container** (Ambassador pattern)
- Intercepts ALL incoming HTTP before reaching app
- Performs OAuth2 flows, token validation, session management
- Injects identity into request headers:
  - `X-MS-CLIENT-PRINCIPAL`: Base64-encoded JSON with claims
  - `X-MS-CLIENT-PRINCIPAL-ID`: User object ID
  - `X-MS-CLIENT-PRINCIPAL-NAME`: User principal name
  - `X-MS-TOKEN-AAD-ACCESS-TOKEN`: Azure AD access token
  - `X-MS-TOKEN-AAD-ID-TOKEN`: Azure AD ID token
  - `X-MS-TOKEN-AAD-REFRESH-TOKEN`: Azure AD refresh token

### Easy Auth Capabilities
- Automatic HTTPS enforcement
- Built-in CSRF mitigation
- Token store (caches tokens per session)
- Session cookie management
- Supports: Microsoft Entra, Facebook, Google, GitHub, Apple, OpenID Connect
- PKCE support (if client provides parameters)
- Protected Resource Metadata (RFC 9728 preview)

### Easy Auth Limitations for This Project
1. **No custom token types**: Can't issue internal HS256 tokens
2. **No token blacklist**: Built-in token store doesn't support revocation
3. **No custom authorization**: Only authenticates, doesn't authorize
4. **No tenant isolation**: Doesn't understand app-level multi-tenancy
5. **Opaque middleware**: Can't debug or extend auth logic
6. **Header-only**: Identity passed via headers, not JWT claims
7. **No API-first design**: Optimized for browser flows, not API clients
8. **Front Door considerations**: Requires forwardProxy configuration if behind Front Door

## Azure AD App Roles Architecture

### How App Roles Work
1. Define roles in app manifest: `"appRoles": [{ "value": "Admin", ... }]`
2. Assign users/groups to roles in Azure AD portal
3. Roles appear as `roles` claim in JWT: `"roles": ["Admin", "Operator"]`
4. Application validates role claims

### Role Claim in Token
```json
{
  "aud": "api://client-id",
  "iss": "https://login.microsoftonline.com/tenant-id/v2.0",
  "roles": ["Platform.Admin", "Tenant.Bishops.Operator"],
  "oid": "user-object-id",
  "groups": ["group-id-1", "group-id-2"]
}
```

### Comparison: Groups (current) vs App Roles

| Feature | Groups (current) | App Roles |
|---------|-----------------|-----------|
| Claim name | `groups` | `roles` |
| Value type | Group GUIDs or names | Custom strings |
| Management | Azure AD Groups portal | App Registration portal |
| Max per app | Unlimited (but token has 200 group limit) | 1,500 per app manifest |
| Overage | If >200 groups, must call Graph API | No overage, always in token |
| Naming control | Group names can change | Role values are fixed |
| Cryptographic binding | Group membership in token | Role assignment in token |
| Self-service | Users can request group membership | Admin-only assignment |

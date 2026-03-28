# Managed Identity Audit — Current State

## System-Assigned Managed Identity

### App Service Configuration (from app-service.bicep)
```bicep
identity: {
  type: 'SystemAssigned'
}
```
- ✅ Enabled on App Service
- ✅ Used for Key Vault access (access policy grants get/list on secrets)
- ✅ Used for SQL access (connection string with `Authentication=ActiveDirectoryMsi`)

### OIDC Credential Provider (from oidc_credential.py)
```
Credential Resolution Order:
1. App Service (prod/staging): ClientAssertionCredential + ManagedIdentityCredential
2. Workload Identity (CI/K8s): WorkloadIdentityCredential via AZURE_FEDERATED_TOKEN_FILE
3. Local development fallback: DefaultAzureCredential (az login, VS Code, CLI)
```
- ✅ Per-tenant credential via OIDC federation (no client secrets needed)
- ✅ Uses MI to obtain OIDC assertion token for cross-tenant access
- ✅ Development fallback explicitly guarded by `OIDC_ALLOW_DEV_FALLBACK`

## Credential Inventory

### Credentials That Should Be Eliminated

| Credential | Location | Used By | Replacement |
|-----------|----------|---------|-------------|
| Storage Account Key | `app-service.bicep` line `storageAccount.listKeys().keys[0].value` | Azure Files mount (appdata, applogs) | RBAC role assignment: `Storage File Data SMB Share Contributor` |
| AZURE_AD_CLIENT_SECRET | `app-service.bicep` env var, `.env` | Azure AD OAuth2 callback (authorization code exchange) | OIDC federation (already partially implemented) |
| SQL Admin Password | `main.bicep` parameter `sqlAdminPassword` | SQL Server admin auth | Azure AD admin + MI-only access (remove SQL auth entirely) |
| Redis Connection String | `app-service.bicep` env var `REDIS_URL` | Token blacklist, rate limiting | Azure Cache for Redis AAD auth (when deployed) |

### Credentials Already Using MI (✅ Secured)

| Service | Credential Method | Details |
|---------|------------------|---------|
| Key Vault | System-Assigned MI | Access policy: get, list secrets |
| Azure SQL | MI + ActiveDirectoryMsi | Connection string uses MSI auth |
| Per-Tenant Graph API | OIDC Federation | ClientAssertionCredential backed by MI |
| Azure Resource Manager | OIDC Federation | Same as above for resource queries |

### Credentials That Can't Use MI

| Credential | Reason | Mitigation |
|-----------|--------|------------|
| JWT_SECRET_KEY | Symmetric key for HS256 signing | Stored in Key Vault, referenced via `@Microsoft.KeyVault()` ✅ |
| GHCR Docker credentials | External registry (not Azure) | Would need migration to ACR for MI |
| Teams Webhook URL | External service | No MI support; store in Key Vault |

## Managed Identity Cost

| Component | Cost |
|-----------|------|
| System-Assigned MI | Free |
| User-Assigned MI | Free |
| RBAC Role Assignments | Free |
| Key Vault access (with MI) | Free (just API call costs, negligible) |
| Total | $0/mo |

## Recommended Migration Priority

1. **HIGH**: Storage Account Key → RBAC (deploy history exposure)
2. **HIGH**: Azure AD Client Secret → Full OIDC federation (secret rotation burden)  
3. **MEDIUM**: SQL Admin Password → Azure AD-only admin (remove SQL auth)
4. **LOW**: Redis → AAD auth (only when Redis is deployed)
5. **LOW**: GHCR → ACR with MI pull (only if migrating registries)

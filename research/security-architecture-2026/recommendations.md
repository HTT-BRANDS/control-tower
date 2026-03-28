# Prioritized Recommendations — Security Architecture

## Budget Context
- **Current spend**: $73/mo (B1 App Service + S0 SQL + Log Analytics + App Insights + Storage + Key Vault)
- **Hard constraint**: No significant cost increases acceptable
- **Users**: 10-30 internal governance users
- **Risk profile**: Internal tool, not public-facing. Manages Azure tenant governance data.

---

## Phase 1: Zero-Cost Security Improvements (Week 1-2)

### 1.1 🔴 Eliminate Storage Account Key from Bicep Deployment

**What**: The `app-service.bicep` uses `storageAccount.listKeys().keys[0].value` to mount Azure Files. This embeds the storage key in ARM deployment history.

**Fix**: Replace with RBAC-based access using the App Service's system-assigned managed identity.

```bicep
// ADD: Role assignment for Storage File Data SMB Share Contributor
resource storageFileContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(appService.id, storageAccount.id, 'storage-file-contributor')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '0c867c2a-1d8c-454a-a3db-ab2ea1bdc8bb' // Storage File Data SMB Share Contributor
    )
    principalId: appService.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// MODIFY: azureStorageAccounts config to use identity-based access
resource azureStorageConfig 'Microsoft.Web/sites/config@2023-12-01' = {
  parent: appService
  name: 'azureStorageAccounts'
  properties: {
    dataVolume: {
      type: 'AzureFiles'
      shareName: 'appdata'
      mountPath: '/home/data'
      accountName: storageAccountName
      // REMOVE: accessKey
      // ADD: identity-based access (requires App Service 2023-12-01 API)
    }
  }
}
```

> **Note**: Azure Files identity-based mounting for App Service Linux containers requires confirming support for the storage auth method. If not yet supported, the interim fix is to store the key in Key Vault and use a Key Vault reference instead of `listKeys()`.

**Effort**: 2-4 hours  
**Cost**: $0  
**Risk reduction**: Eliminates credential in deployment history

---

### 1.2 🔴 Restrict Key Vault Network Access

**What**: Key Vault currently has `publicNetworkAccess: 'Enabled'` with `defaultAction: 'Allow'`. Any authenticated Azure identity worldwide can attempt access.

**Fix**: Change network ACLs to deny by default, allow only Azure services:

```bicep
// In modules/key-vault.bicep
networkAcls: {
  defaultAction: 'Deny'        // Changed from 'Allow'
  bypass: 'AzureServices'      // Keeps App Service MI access working
  ipRules: []
  virtualNetworkRules: []
}
```

**Effort**: 30 minutes  
**Cost**: $0  
**Risk reduction**: Blocks external network access to secrets

---

### 1.3 🔴 Add Refresh Token Rotation

**What**: Current refresh tokens have a 7-day lifetime but aren't rotated. If a refresh token is stolen, the attacker has 7 days of access.

**Fix**: Issue a new refresh token with each use, blacklist the old one:

```python
# In app/api/routes/auth.py — refresh endpoint
async def refresh_token(refresh_token_str: str):
    payload = jwt_manager.decode_token(refresh_token_str)
    
    # Verify it's a refresh token
    if payload.get("type") != "refresh":
        raise HTTPException(401, "Invalid token type")
    
    # Blacklist the used refresh token
    blacklist_token(refresh_token_str)
    
    # Issue new access + refresh tokens
    new_access = jwt_manager.create_access_token(user_id=payload["sub"], ...)
    new_refresh = jwt_manager.create_refresh_token(user_id=payload["sub"])
    
    return {"access_token": new_access, "refresh_token": new_refresh}
```

**Effort**: 2-4 hours  
**Cost**: $0  
**Risk reduction**: Limits stolen refresh token window to single use

---

### 1.4 🟡 Remove Unused Monitoring Dependencies

**What**: 5 monitoring packages are installed but not actively used:
- `prometheus-fastapi-instrumentator` — `/metrics` endpoint exists but no scraper
- `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-exporter-otlp` — tracing disabled by default

**Fix**: Remove from `pyproject.toml`:

```toml
# REMOVE these lines:
"prometheus-fastapi-instrumentator>=7.1.0",
"opentelemetry-api>=1.40.0",
"opentelemetry-sdk>=1.40.0",
"opentelemetry-instrumentation-fastapi>=0.61b0",
"opentelemetry-exporter-otlp>=1.40.0",
```

Also remove the Prometheus middleware registration in `app/main.py` and the OpenTelemetry tracing initialization.

**Effort**: 2-4 hours (including removing code references and updating tests)  
**Cost**: $0 (saves ~50MB Docker image size, faster cold starts)  
**Risk reduction**: Fewer dependencies = smaller attack surface. Each unused dependency is a potential CVE vector.

---

## Phase 2: Architecture Hardening (Week 3-4)

### 2.1 🟡 Add Azure AD App Roles for Platform-Level Roles

**What**: Supplement the custom `UserTenant` model with Azure AD App Roles for the 3 platform-level roles: `Platform.Admin`, `Platform.Operator`, `Platform.Viewer`.

**Why**: Platform roles (admin, operator, viewer) are currently determined by group name string matching (`admin_groups = ["admin", "administrator", ...]`). This is fragile. Azure AD App Roles provide cryptographically-signed role claims.

**How**:
1. Add roles to Azure AD app manifest:
```json
"appRoles": [
  {
    "allowedMemberTypes": ["User"],
    "displayName": "Platform Admin",
    "id": "uuid-here",
    "value": "Platform.Admin"
  },
  {
    "allowedMemberTypes": ["User"],
    "displayName": "Platform Operator", 
    "id": "uuid-here",
    "value": "Platform.Operator"
  }
]
```

2. Read roles from token claims instead of group name matching:
```python
# In auth.py
roles_claim = payload.get("roles", [])  # Azure AD App Roles
if "Platform.Admin" in roles_claim:
    roles.append("admin")
```

3. Keep `UserTenant` model for per-tenant permissions — this stays in the database.

**Effort**: 4-8 hours  
**Cost**: $0  
**Risk reduction**: Eliminates string-matching fragility for role assignment

---

### 2.2 🟡 Implement IP Allowlisting for App Service

**What**: Restrict App Service access to known corporate IP ranges. More effective than WAF for an internal tool with known users.

**How**: Add access restrictions in Bicep:
```bicep
// In app-service.bicep
siteConfig: {
  ipSecurityRestrictions: [
    {
      ipAddress: 'CORPORATE_IP_RANGE/CIDR'
      action: 'Allow'
      priority: 100
      name: 'AllowCorporate'
    }
    {
      ipAddress: 'Any'
      action: 'Deny'
      priority: 2147483647
      name: 'DenyAll'
    }
  ]
}
```

**Effort**: 1-2 hours (need to collect corporate IP ranges)  
**Cost**: $0  
**Risk reduction**: Blocks all external access without Front Door or WAF

---

### 2.3 🟢 Purge ARM Deployment History

**What**: Azure keeps deployment history including parameter values. Even `@secure()` parameters are stored internally.

**How**: Periodic cleanup:
```bash
# List and delete old deployments
az deployment sub list --query "[?properties.timestamp<'2026-01-01']" --output tsv | \
  while read name; do az deployment sub delete --name "$name"; done
```

Consider enabling automatic deployment history cleanup:
```bicep
// In main.bicep — enable auto-cleanup
resource deleteOldDeployments 'Microsoft.Resources/deployments@2023-07-01' = {
  // Azure auto-deletes when count exceeds 800
}
```

**Effort**: 1 hour (one-time script)  
**Cost**: $0  
**Risk reduction**: Removes historical credential exposure

---

## Phase 3: Future Considerations (Not Now)

### 3.1 ⏸️ Azure Front Door — DEFER

**When to reconsider**:
- Platform grows to 100+ users
- Public-facing endpoints are added
- Multi-region deployment is needed
- Compliance requires WAF (SOC2/NIST may)

**Minimum tier**: Front Door Standard at $35/mo
**Budget prerequisite**: Total infrastructure budget ≥ $150/mo

### 3.2 ⏸️ Private Endpoints — DEFER

**When to reconsider**:
- Regulated data is stored (PCI, HIPAA)
- VNet integration is enabled for App Service
- Budget allows ~$25/mo additional

**Implementation order when ready**:
1. Enable VNet integration on App Service (requires B1+, already met)
2. Create VNet with subnets (app-subnet, pe-subnet)
3. Private Endpoint for SQL first (highest data sensitivity)
4. Private Endpoint for Key Vault second
5. Private DNS zones for both

### 3.3 ⏸️ Redis Deployment — DEFER (revisit with budget)

**Current situation**: Token blacklist and rate limiter use in-memory fallback. State lost on restart.

**When to reconsider**:
- Multiple App Service instances (scaling out)
- Token revocation reliability is critical
- Budget allows +$16/mo (Basic C0)

**Zero-cost alternative**: SQL-backed token blacklist table (already recommended in prior architecture audit).

---

## Implementation Roadmap

```
Week 1 (4-8 hrs):
  ├── 1.1 Fix storage key exposure in Bicep
  ├── 1.2 Restrict Key Vault network ACLs  
  └── 1.3 Implement refresh token rotation

Week 2 (4-8 hrs):
  ├── 1.4 Remove unused monitoring dependencies
  └── 2.3 Purge ARM deployment history

Week 3 (4-8 hrs):
  ├── 2.1 Add Azure AD App Roles
  └── 2.2 Implement IP allowlisting

Week 4 (2-4 hrs):
  └── Validation, testing, documentation
```

**Total effort**: 14-28 hours over 4 weeks  
**Total cost impact**: $0/mo  
**Security improvement**: Eliminates credential exposure, adds network restrictions, hardens auth flow

---

## Decision Matrix Summary

| Topic | Decision | Rationale |
|-------|----------|-----------|
| Authentication | **Keep custom JWT + Azure AD** | Best multi-tenant flexibility, already well-implemented |
| Front Door + WAF | **Skip** | $35-330/mo is 48-452% of budget; IP allowlisting is free and more effective for internal tool |
| Managed Identity | **Expand** (critical) | $0 cost, eliminates storage key and other credential exposure |
| Private Endpoints | **Defer** | $23.50/mo (32% of budget); SQL already blocks public access |
| IaC (Bicep) | **Keep** | No state file risk, Azure-native, $0 cost, already deployed |
| Monitoring | **Consolidate** | Remove 5 unused packages, keep App Insights + Log Analytics + custom dashboard |

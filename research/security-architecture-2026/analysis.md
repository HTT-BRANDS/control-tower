# Security Architecture Analysis — Multi-Dimensional Comparison

## 1. Authentication Architecture Comparison

### Option A: Custom JWT Auth (PyJWT + HttpOnly Cookies) — CURRENT

**How it works in this project**: The platform uses `PyJWT` for internal JWT tokens (HS256 symmetric signing) and validates Azure AD tokens (RS256 asymmetric) against the JWKS endpoint. Tokens are stored in HttpOnly cookies for browser sessions and passed as Bearer tokens for API calls. A Redis-backed token blacklist enables revocation.

| Dimension | Assessment | Score |
|-----------|-----------|-------|
| **Security** | Strong. PyJWT is actively maintained, HS256 for internal + RS256 for Azure AD is correct architecture. HttpOnly cookies prevent XSS token theft. Token blacklist enables revocation. | 8/10 |
| **Maintenance** | Moderate. Team owns the auth stack — must keep PyJWT updated, manage JWKS caching, handle refresh token rotation. ~2-4 hrs/quarter maintenance. | 6/10 |
| **Multi-tenant** | Excellent. Custom group-to-tenant mapping in `_extract_tenant_ids_from_groups()` and `TenantAuthorization` provides granular per-tenant RBAC that's not easily achievable with platform auth. | 9/10 |
| **Refresh tokens** | Implemented. 7-day refresh tokens with JWT ID (`jti`) for revocation tracking. Token blacklist survives restarts if Redis is deployed. | 7/10 |
| **Flexibility** | Full control over token claims, expiry, and authorization logic. Can add custom claims without Azure AD app registration changes. | 9/10 |

**Verdict**: ✅ **Keep.** This is the right choice for a multi-tenant governance platform needing granular tenant isolation.

### Option B: Azure App Service Authentication (Easy Auth)

**How it works**: A platform-level middleware (running in a sidecar container on Linux) intercepts all HTTP requests before they reach the application. It handles OAuth2 flows, token validation, session management, and injects identity info into request headers.

| Dimension | Assessment | Score |
|-----------|-----------|-------|
| **Security** | Good baseline. Microsoft manages token validation, session cookies, CSRF mitigation. Automatically enforces HTTPS. But: opaque — you can't inspect or extend the auth logic. | 7/10 |
| **Maintenance** | Very low. Microsoft handles all updates, security patches, protocol changes. Zero code to maintain. | 9/10 |
| **Multi-tenant** | Poor for this use case. Easy Auth authenticates users but provides minimal authorization. The platform's concept of "tenant access" (governance-tenant-{id} groups → per-tenant RBAC) would need to be reimplemented in application code anyway. Easy Auth just validates the identity — it doesn't know about application tenants. | 3/10 |
| **Refresh tokens** | Built-in token store handles refresh. Tokens cached per session. But: no fine-grained control over refresh behavior or revocation. | 6/10 |
| **Flexibility** | Limited. Can't customize token claims processing. Can't add custom authorization logic at the middleware level. Header-based identity injection is one-way. No support for custom token types. | 3/10 |

**Key limitations for this project**:
- Easy Auth's `/.auth/login/aad` endpoint manages the OAuth flow, but the platform still needs all the tenant isolation logic in `app/core/authorization.py`
- Can't do dual-token architecture (internal HS256 + Azure AD RS256) — Easy Auth only supports the identity providers it's configured with
- Token blacklist for immediate revocation is not possible with Easy Auth's built-in token store
- The `X-MS-CLIENT-PRINCIPAL` header Easy Auth injects contains Azure AD claims but not the custom tenant mappings

**Verdict**: ❌ **Not recommended.** Easy Auth would remove the need for ~50 lines of JWKS validation code but would require rewriting the entire authorization layer to work with header-based identity injection. Net negative.

### Option C: Azure AD App Roles + Built-in Auth

**How it works**: Define application roles in the Azure AD app manifest. Users/groups are assigned roles in Azure AD. Roles appear as claims in the JWT token. The application validates role claims for authorization.

| Dimension | Assessment | Score |
|-----------|-----------|-------|
| **Security** | Strong. Roles are cryptographically bound to the token by Azure AD. No local role store needed. | 8/10 |
| **Maintenance** | Mixed. Auth code is simpler, but role management moves to Azure AD portal. Every tenant access change requires Azure AD admin action. At 10-30 users this is manageable; at scale it becomes a bottleneck. | 5/10 |
| **Multi-tenant** | Workable but rigid. Would need one App Role per tenant (e.g., `Tenant.Bishops.Read`, `Tenant.Bishops.Admin`). With 5+ tenants × 3 roles = 15+ App Roles. Azure AD supports max 1,500 App Roles, so scale is fine, but management is manual. | 5/10 |
| **Refresh tokens** | Handled by Azure AD/MSAL. Refresh token lifetime managed by Azure AD policies (configurable via CAE). | 7/10 |
| **Flexibility** | Moderate. Roles are defined in the app manifest — changes require a deployment or portal change, not a database update. Can't do dynamic tenant assignment at runtime. | 4/10 |

**Key consideration**: This approach works if tenant access is static and managed by an Azure AD admin. The current platform's `UserTenant` model with `can_manage_resources`, `can_view_costs`, `can_manage_compliance` granularity would be lost — these would need to become individual App Roles.

**Verdict**: ⚠️ **Partial fit.** Could replace group-to-role mapping but adds Azure AD admin dependency for every tenant access change. Not recommended as primary approach, but Azure AD App Roles could supplement the current system for organization-level roles (GlobalAdmin, AuditorRead).

### Recommendation: Hybrid Enhancement

Keep the current custom JWT architecture but enhance it:

1. **Already done well**: PyJWT with crypto, Azure AD JWKS validation, token blacklist, tenant isolation
2. **Add**: Use Azure AD App Roles for 2-3 platform-level roles (Admin, Operator, Viewer) while keeping the custom `UserTenant` model for granular per-tenant permissions
3. **Add**: Implement refresh token rotation (issue new refresh token with each use, blacklist the old one)
4. **Consider**: Add `nonce` claim to prevent replay attacks on token refresh

---

## 2. Azure Front Door + WAF vs Direct App Service Exposure

### Cost Analysis for 10-30 Users

**Azure Front Door Standard**: $35/mo base fee
- Data transfer (North America): $0.083/GB for first 10 TB
- Requests: $0.009 per 10,000 requests
- Estimated traffic for 30 users: ~1-5 GB/mo outbound, ~50k requests/mo
- **Total estimated**: ~$35.50/mo (dominated by base fee)

**Azure Front Door Premium** (includes WAF + Private Link): $330/mo base fee
- Same data transfer + request pricing
- WAF managed rules: Included in base fee
- **Total estimated**: ~$330.50/mo

**Direct App Service** (current): $0 additional cost
- App Service already includes: HTTPS/TLS 1.2, IP restrictions, managed certificates
- Custom security headers already implemented in middleware
- Rate limiting already implemented with Redis backend

### Cost Proportionality Analysis

```
Azure Front Door Standard:  $35/mo  = 48% of total budget ($73/mo)
Azure Front Door Premium:   $330/mo = 452% of total budget ($73/mo)

Cost per user (30 users):
  Front Door Standard:  $1.17/user/mo
  Front Door Premium:   $11.00/user/mo
  Current (direct):     $0/user/mo
```

### What You'd Get vs What You Already Have

| Feature | Front Door Provides | Already Have |
|---------|-------------------|-------------|
| DDoS protection | Layer 7 DDoS mitigation | Azure's basic DDoS protection (included with all Azure services) |
| WAF rules | OWASP Core Rule Set, bot protection, IP reputation | Custom rate limiting, security headers middleware, CSP |
| TLS termination | Edge TLS termination | App Service managed TLS |
| Geographic routing | Multi-region load balancing | Single-region B1 (appropriate for 10-30 users) |
| Caching | Edge caching for static content | In-app caching via Redis/memory |
| Custom domains | Custom domain + auto cert | App Service custom domain + managed cert |

### Security Gap Assessment Without Front Door

**What you're exposed to without Front Door**:
1. **Bot traffic**: Mitigated by rate limiting in `app/core/rate_limit.py`
2. **Layer 7 DDoS**: App Service basic tier has no DDoS protection beyond Azure's infrastructure-level protection. At 10-30 users, a targeted DDoS would be unusual but possible.
3. **OWASP Top 10**: Application-level controls (CSP, XSS protection, SQL parameterization) already cover these.
4. **IP reputation filtering**: Not available without WAF. Low risk at this user count.

### Verdict

❌ **Not recommended at current scale and budget.**

The $35/mo minimum for Front Door Standard represents 48% of the total budget. For 10-30 known users, the threat model doesn't justify this. The platform is an internal governance tool, not a public-facing web application.

**When to reconsider**: If the platform grows to 100+ users, handles public-facing data, or moves to multi-region deployment, Front Door Standard becomes worth evaluating. At current scale, the existing security middleware + App Service built-in protections are sufficient.

**Alternative for zero-cost protection**: Add IP allowlisting in App Service networking settings to restrict access to known corporate IP ranges. This provides more effective access control than WAF for an internal tool.

---

## 3. Managed Identity for Service-to-Service Communication

### Current State

The platform partially uses Managed Identity:

| Service | Current Auth Method | Managed Identity? |
|---------|-------------------|-------------------|
| Key Vault | `DefaultAzureCredential` via `keyvault.py` | ✅ Yes |
| Azure AD (per-tenant) | OIDC Federation via `oidc_credential.py` | ✅ Yes (ClientAssertionCredential) |
| Azure SQL | Connection string with `Authentication=ActiveDirectoryMsi` in Bicep | ✅ Yes (when SQL enabled) |
| Azure Graph API | Client credentials via `graph_client.py` | ⚠️ Partial — uses OIDC but falls back to client secret |
| Container Registry (GHCR) | Docker registry credentials | ❌ No (uses PAT/token) |
| Redis | Connection string with access key | ❌ No (uses shared key) |
| Storage Account | Access key in Bicep (for file mounts) | ❌ No (uses `listKeys()`) |

### Recommended: Full Managed Identity Migration

**Phase 1 — Eliminate storage account keys** (0 cost, high impact):
```bicep
// BEFORE (current in app-service.bicep):
accessKey: storageAccount.listKeys().keys[0].value

// AFTER: Use RBAC role assignment
resource storageRbac 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(appService.id, storageAccount.id, 'Storage File Data SMB Share Contributor')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '0c867c2a-1d8c-454a-a3db-ab2ea1bdc8bb')
    principalId: appService.identity.principalId
    principalType: 'ServicePrincipal'
  }
}
```

**Phase 2 — Azure Cache for Redis AAD auth** (if/when Redis is deployed):
```python
# Use azure-identity for Redis connection
from azure.identity import DefaultAzureCredential
import redis

cred = DefaultAzureCredential()
token = cred.get_token("https://redis.azure.com/.default")
r = redis.Redis(host='redis-name.redis.cache.windows.net', port=6380,
                username=managed_identity_object_id, password=token.token,
                ssl=True)
```

**Phase 3 — GHCR migration to Azure Container Registry with MI** (if registry costs are within budget):
Currently using GHCR (free for public images). If ACR is deployed, App Service can pull images using its system-assigned managed identity with `AcrPull` role — no credentials needed.

### Cost Impact

**$0 additional cost.** Managed Identity is free. RBAC role assignments are free. The only cost is developer time for migration (~4-8 hours total).

### Security Impact

**Critical improvement.** Eliminating stored credentials removes:
- Credential rotation burden
- Secret sprawl in Key Vault
- Risk of leaked access keys in deployment logs
- Blast radius of compromised credentials

### Verdict

🔴 **Critical priority. Implement in Phase 1 of next sprint.**

The `storageAccount.listKeys().keys[0].value` pattern in `app-service.bicep` is the highest-priority fix — it embeds the storage account key in the ARM deployment, which is stored in deployment history.

---

## 4. Azure Private Endpoints vs Public Endpoints

### Cost Calculation for This Platform

Private Endpoint pricing (per Microsoft's pricing page, verified July 2026):
- **Per endpoint**: $0.01/hour = ~$7.30/month
- **Data processing**: $0.01/GB (both inbound and outbound)

For the governance platform's 3 key services:

| Service | Private Endpoint Cost | Data Processing (est.) | Monthly Total |
|---------|---------------------|----------------------|---------------|
| Azure SQL (S0) | $7.30/mo | ~$0.05/mo (5 GB) | ~$7.35/mo |
| Key Vault | $7.30/mo | ~$0.01/mo (negligible) | ~$7.31/mo |
| Container Registry | $7.30/mo | ~$0.05/mo (image pulls) | ~$7.35/mo |
| **Total** | **$21.90/mo** | **~$0.11/mo** | **~$22.01/mo** |

Additional cost: Private DNS Zones (~$0.50/mo per zone × 3 = $1.50/mo)

**Total Private Endpoints cost: ~$23.50/mo = 32% of total budget**

### Current Security Posture Without Private Endpoints

| Service | Current Public Access | Mitigation |
|---------|---------------------|------------|
| Azure SQL | `publicNetworkAccess: 'Disabled'` in Bicep ✅ | Already hardened. No public access. Uses VNet rules when VNet enabled. |
| Key Vault | `publicNetworkAccess: 'Enabled'` with `bypass: 'AzureServices'` | Relies on Azure RBAC + access policies. No network restriction. |
| Container Registry | GHCR (external, public) | Images are public. No sensitive data in images. |

### Risk Assessment

**Azure SQL**: Already has `publicNetworkAccess: 'Disabled'` in the Bicep template. This means the SQL server is ONLY accessible via VNet integration or Azure service endpoints. Adding a Private Endpoint would provide an additional layer (traffic never leaves the Azure backbone) but the current config is already significantly hardened.

**Key Vault**: Currently publicly accessible with RBAC authorization. The risk is that if an attacker obtains a valid Azure AD token with Key Vault access, they could access secrets from any network. A Private Endpoint would restrict access to the VNet only. However, the Managed Identity approach means only the App Service's identity can access secrets — network restriction adds defense-in-depth but is not the primary control.

**Container Registry**: Using GHCR, which is external. Private Endpoints don't apply here. If migrating to ACR, Private Endpoints would only be relevant if ACR contains proprietary base images.

### Verdict

🟢 **Defer.** The $23.50/mo cost (32% of budget) is disproportionate to the security benefit at this scale. The SQL server already blocks public access. Key Vault uses RBAC + Managed Identity.

**When to implement**: 
- When the platform handles regulated data (PCI, HIPAA)
- When budget allows (~$100+/mo infrastructure spend)
- When VNet integration is enabled for App Service (prerequisite)

**Immediate action instead**: Restrict Key Vault network access to Azure services only:
```bicep
networkAcls: {
  defaultAction: 'Deny'    // Changed from 'Allow'
  bypass: 'AzureServices'
  ipRules: []
  virtualNetworkRules: []
}
```
This is **free** and provides most of the benefit of a Private Endpoint for Key Vault.

---

## 5. IaC Security: Bicep vs Terraform vs Pulumi

### Feature Comparison for This Project

| Feature | Bicep (Current) | Terraform | Pulumi |
|---------|----------------|-----------|--------|
| **State Management** | Stateless — ARM handles state | Remote state file (must secure) | Remote state file (must secure) |
| **State Security Risk** | None — no state file to leak | State can contain secrets in plaintext | State can contain secrets in plaintext |
| **Secret Handling** | `@secure()` decorator, Key Vault references, `newGuid()` | `sensitive` flag (still in state), Vault provider | Secret outputs, Vault provider |
| **Drift Detection** | Azure `what-if` deployment mode | `terraform plan` | `pulumi preview` |
| **Azure Integration** | First-party, day-0 support for all Azure APIs | Community provider, 1-7 day lag for new features | Community provider, variable lag |
| **Learning Curve** | Low (if team knows Azure) | Medium (HCL syntax, state management) | Low-Medium (uses familiar languages) |
| **Cost** | Free (Azure built-in) | Free (open source) or ~$20/mo+ (Terraform Cloud) | Free (open source) or $50/mo+ (Pulumi Cloud) |
| **Multi-cloud** | Azure only | Yes | Yes |

### Security-Specific Analysis

**Bicep (Current) — Security Strengths**:
1. **No state file**: The single biggest security advantage. Terraform state files are the #1 source of IaC secret leakage. Bicep has no state file — ARM API is the source of truth.
2. **`@secure()` parameters**: Prevents values from appearing in deployment logs. Already used in `main.bicep` for `sqlAdminPassword`, `azureAdClientSecret`, `jwtSecretKey`.
3. **Key Vault references**: `@Microsoft.KeyVault(SecretUri=...)` syntax already used in `app-service.bicep` for JWT secret.
4. **What-if**: Native drift detection via `az deployment sub what-if`.

**Bicep — Security Weaknesses**:
1. **Deployment history**: ARM stores deployment history including parameter values. Even `@secure()` parameters are stored (just masked in portal UI). Mitigated by periodically purging deployment history.
2. **No policy-as-code**: Bicep doesn't have built-in policy enforcement. Azure Policy can fill this gap.
3. **Output leakage**: The SQL connection string output issue (already identified in prior audit) — outputs are NOT masked even if inputs are `@secure()`.

**Terraform — Would Add Complexity**:
- State file requires secure storage (Azure Blob with encryption, access control)
- State lock mechanism needed (Azure Blob lease)
- `terraform.tfstate` contains ALL resource values including secrets in plaintext
- Additional tool to install, version, and maintain
- No Azure-specific advantages over Bicep for this project

**Pulumi — Interesting but Overkill**:
- Could write infrastructure in Python (matching app language) 
- But: state management still required, team would need to learn Pulumi concepts
- Cloud service costs $50/mo minimum for teams

### Verdict

✅ **Stay with Bicep.** It's already deployed, has no state file security risk, supports all Azure resources natively, and costs nothing. The project already makes good use of `@secure()` parameters and Key Vault references.

**Improvement**: Add Azure Policy definitions to enforce security baselines:
```bicep
resource sqlPolicy 'Microsoft.Authorization/policyAssignments@2022-06-01' = {
  name: 'enforce-sql-tls12'
  properties: {
    policyDefinitionId: '/providers/Microsoft.Authorization/policyDefinitions/32e6bbec-16b6-44c2-be37-c5b672d103cf'
    // Built-in: "Azure SQL Database should have the minimal TLS version of 1.2"
  }
}
```

---

## 6. Monitoring Stack: Current vs Azure-Native

### Current Monitoring Stack

| Component | Purpose | Status |
|-----------|---------|--------|
| **App Insights** | Request telemetry, error tracking | ✅ Configured (via `app_insights.py` middleware) |
| **OpenCensus** | Azure exporter for App Insights | ⚠️ Optional import, falls back to structured logging |
| **Prometheus** | Metrics endpoint (`prometheus-fastapi-instrumentator`) | ⚠️ Exposed but no scraper configured |
| **OpenTelemetry** | Distributed tracing | ⚠️ SDK installed but `ENABLE_TRACING=false` by default |
| **Custom monitoring** | `PerformanceMonitor` in `app/core/monitoring.py` | ✅ Active — tracks queries, sync jobs, cache |
| **Log Analytics** | Azure log aggregation | ✅ Configured in Bicep |

### Redundancy Analysis

**Problem**: The current setup has 4 overlapping telemetry systems:

```
Request → AppInsightsMiddleware (custom) → structured log
       → Prometheus instrumentator     → /metrics endpoint
       → OpenTelemetry SDK              → OTLP exporter (disabled)
       → OpenCensus                     → Azure exporter (optional)
```

For 10-30 users, this is significant over-engineering. Each system:
- Adds startup time and memory overhead
- Creates dependencies to update (4 SDKs × quarterly updates)
- Fragments observability data across systems

### Recommended: Consolidated Azure-Native Stack

**Keep**:
- **App Insights** (already paying for via Log Analytics workspace): Free ingestion up to 5 GB/month. Platform telemetry for a 10-30 user app will be well under 1 GB/month.
- **Log Analytics**: Already deployed. Free 31-day retention on analytics logs. 5 GB/month free ingestion.
- **Custom `PerformanceMonitor`**: In-app metrics dashboard — lightweight, no external dependency.

**Remove**:
- **`prometheus-fastapi-instrumentator`**: No Prometheus scraper is deployed. The `/metrics` endpoint serves no purpose without a Prometheus server (~$50-100/mo to run, or managed service at $0.16/10M samples). Remove the dependency.
- **OpenTelemetry SDK packages** (`opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-exporter-otlp`): 4 packages, disabled by default. If tracing is needed, App Insights provides distributed tracing natively.
- **OpenCensus**: Legacy SDK, Microsoft recommends migration to OpenTelemetry (which is also not needed here).

### Cost Analysis

| Component | Current Cost | After Consolidation |
|-----------|-------------|-------------------|
| Log Analytics (30-day retention) | ~$0/mo (under free tier) | ~$0/mo |
| App Insights ingestion | ~$0/mo (under 5 GB free) | ~$0/mo |
| Prometheus managed service | $0 (not deployed) | $0 (removed) |
| OpenTelemetry collector | $0 (disabled) | $0 (removed) |
| **Maintenance burden** | 4 SDKs to update | 1 SDK (App Insights) |

### Azure Workbooks vs Custom Dashboard

The platform already has a custom performance dashboard (`/api/v1/monitoring/dashboard`). Azure Workbooks provide:
- Pre-built templates for App Service monitoring
- KQL query-based visualizations
- No additional cost (uses Log Analytics data)
- Shareable dashboards

**Recommendation**: Use Azure Workbooks for infrastructure monitoring (CPU, memory, response times) and keep the custom dashboard for application-specific metrics (sync jobs, cache hit rates, tenant data).

### Dependency Cleanup Impact

Removing unused monitoring packages from `pyproject.toml`:
```toml
# REMOVE these 5 dependencies:
"prometheus-fastapi-instrumentator>=7.1.0",
"opentelemetry-api>=1.40.0",
"opentelemetry-sdk>=1.40.0",
"opentelemetry-instrumentation-fastapi>=0.61b0",
"opentelemetry-exporter-otlp>=1.40.0",
```

**Impact**: ~15-20 fewer transitive packages, ~50MB smaller Docker image, faster cold starts, reduced attack surface.

### Verdict

🟡 **High priority.** Consolidate to App Insights + Log Analytics + custom PerformanceMonitor. Remove Prometheus instrumentator and OpenTelemetry packages. Zero cost change, significant complexity reduction.

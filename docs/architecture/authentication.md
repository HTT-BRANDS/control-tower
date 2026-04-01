---
layout: default
title: Authentication & Authorization
---

# Authentication & Authorization

## 🔐 Overview

The Azure Governance Platform implements **enterprise-grade authentication** using Azure AD B2C with OpenID Connect (OIDC).

---

## Architecture Flow

### Authentication Sequence

1. **User Login** → Redirect to Azure AD B2C
2. **B2C Validation** → User credentials + MFA (if enabled)
3. **Token Return** → JWT ID Token + Access Token
4. **API Validation** → Bearer token validation (RS256)
5. **Tenant Context** → SQL session context for RLS
6. **Data Response** → Tenant-scoped data returned

---

## Current Implementation

### Identity Provider: Azure AD B2C

**Configuration:**
- Provider: Azure AD B2C (External)
- Tenant: httbrandsb2c.onmicrosoft.com
- Policy: B2C_1A_SIGNUP_SIGNIN
- Token Format: JWT (RS256)
- Session Lifetime: 8 hours
- MFA: Optional (per user policy)

### Token Structure (ID Token)

**Key Claims:**
- `oid` - User's unique Azure AD object ID
- `tid` - Tenant ID for multi-tenancy
- `extension_Role` - **Custom claim for RBAC**
- `extension_Department` - **Custom claim for personas**
- `emails` - User email address
- `name` - Display name

---

## HTTBrands Tenant Access Options

### Option 1: Azure AD B2C (Current) ✅

**How it works:**
- Users authenticate through Azure AD B2C
- B2C can federate to HTTBrands Azure AD
- Supports custom attributes (role, department)
- Built-in MFA support

**Pros:**
✅ Fully managed by Microsoft
✅ Supports social logins (optional)
✅ Built-in MFA and conditional access
✅ Easy custom attributes
✅ Scales automatically

**Configuration:**
```yaml
B2C Tenant: httbrandsb2c.onmicrosoft.com
Custom Attributes: extension_Role, extension_Department
User Flow: B2C_1A_SIGNUP_SIGNIN
Token Lifetime: 8 hours
```

### Option 2: Direct Azure AD Integration

**How it works:**
- Skip B2C, connect directly to HTTBrands Azure AD
- Use Microsoft Authentication Library (MSAL)
- App registration in HTTBrands tenant

**Pros:**
✅ No B2C dependency
✅ Direct SSO with HTTBrands
✅ Full Azure AD features (PIM, access reviews)
✅ Group-based access control

### Option 3: Hybrid (Recommended for Scale)

**How it works:**
- Keep B2C for external customers
- Add Azure AD for HTTBrands employees
- Users choose identity provider on login
- Same app supports both

**Pros:**
✅ Best of both worlds
✅ HTTBrands employees get SSO
✅ Can onboard external users
✅ Future-proof

---

## Role-Based Access Control (RBAC)

### Current Role Matrix

| Role | Tenant View | Cost Data | Compliance | Admin Panel | API Access |
|------|-------------|-----------|------------|-------------|------------|
| **Global Admin** | All ✅ | All ✅ | All ✅ | Full ✅ | Full ✅ |
| **Tenant Admin** | Own ✅ | Own ✅ | Own ✅ | Limited ✅ | Own ✅ |
| **Cost Manager** | Own ✅ | Own ✅ | Read Only ✅ | ❌ | Own ✅ |
| **Compliance Officer** | Own ✅ | Read Only ✅ | Own ✅ | ❌ | Own ✅ |
| **Read-Only User** | Own ✅ | Read Only ✅ | Read Only ✅ | ❌ | Own ✅ |
| **API Service** | N/A | N/A | N/A | N/A | System ✅ |

### Role Enforcement in Code

```python
from fastapi import Depends, HTTPException
from app.api.security import verify_token, require_role

@app.get("/api/v1/admin/users")
@require_role(["Global Admin", "Tenant Admin"])
async def list_users(current_user: dict = Depends(verify_token)):
    # Only accessible to admins
    return await user_service.list_all()

@app.get("/api/v1/costs/summary")
@require_role(["Global Admin", "Tenant Admin", "Cost Manager"])
async def get_cost_summary(current_user: dict = Depends(verify_token)):
    # Accessible to cost managers and above
    tenant_id = current_user["tid"]
    return await cost_service.get_summary(tenant_id)
```

---

## Department-Based Personas

### Dynamic UI Based on Department

```javascript
const department = token['extension_Department'];

switch(department) {
  case 'Finance':
    showFinanceDashboard();  // Cost focus
    break;
  case 'Security':
    showSecurityDashboard();  // Compliance focus
    break;
  case 'Engineering':
    showEngineeringDashboard();  // Resource focus
    break;
  case 'Executive':
    showExecutiveDashboard();  // High-level metrics
    break;
  default:
    showStandardDashboard();
}
```

### Pre-configured Personas

| Persona | Department | Role | Default View | Key Metrics |
|---------|------------|------|--------------|-------------|
| **CFO** | Finance | Global Admin | Cost dashboard | Total spend, trends, optimization |
| **CISO** | Security | Global Admin | Compliance view | Security score, gaps, violations |
| **Cloud Engineer** | Engineering | Tenant Admin | Resource inventory | VM count, storage, networking |
| **Finance Analyst** | Finance | Cost Manager | Cost allocation | By department, project, tag |
| **Compliance Auditor** | Security | Compliance Officer | Audit reports | Framework compliance, evidence |
| **Department Head** | Any | Tenant Admin | Dept summary | Resources, costs, users |

---

## Multi-Tenancy Security Model

### Row-Level Security (RLS) in Azure SQL

```sql
-- Security predicate function
CREATE FUNCTION dbo.tenant_access_predicate(@tenant_id uniqueidentifier)
RETURNS TABLE
WITH SCHEMABINDING
AS
RETURN SELECT 1 AS access_granted
WHERE 
    @tenant_id = CAST(SESSION_CONTEXT(N'tenant_id') AS uniqueidentifier)
    OR CAST(SESSION_CONTEXT(N'role') AS nvarchar(50)) = 'Global Admin';

-- Apply to resources table
CREATE SECURITY POLICY tenant_isolation
    ADD FILTER PREDICATE dbo.tenant_access_predicate(tenant_id)
    ON dbo.resources,
    ADD BLOCK PREDICATE dbo.tenant_access_predicate(tenant_id)
    ON dbo.resources AFTER INSERT,
    ADD BLOCK PREDICATE dbo.tenant_access_predicate(tenant_id)
    ON dbo.resources AFTER UPDATE
WITH (STATE = ON, SCHEMABINDING = ON);
```

### API Tenant Resolution

```python
async def get_current_tenant(request: Request) -> str:
    """Extract tenant_id from JWT and validate access."""
    token = extract_token_from_header(request)
    payload = jwt.decode(token, verify=False)
    
    tenant_id = payload.get("tid")
    user_role = payload.get("extension_Role")
    
    # Set session context for RLS
    await db.execute(
        "EXEC sp_set_session_context 'tenant_id', ?", tenant_id
    )
    await db.execute(
        "EXEC sp_set_session_context 'role', ?", user_role
    )
    
    return tenant_id
```

---

## Security Best Practices

### Current Implementation ✅

- ✅ **HTTPS-only** - All traffic encrypted
- ✅ **JWT validation** - RS256 signature verification
- ✅ **Token expiration** - 8-hour lifetime with refresh
- ✅ **Row-level security** - Database-level tenant isolation
- ✅ **Rate limiting** - 1000 req/hour per user
- ✅ **Audit logging** - All auth events logged
- ✅ **MFA support** - Optional, configurable per user
- ✅ **Secure headers** - 12 security headers configured

### Recommendations for HTTBrands

1. **Enable Conditional Access:**
   - Require MFA for admin roles
   - Restrict access by location/IP
   - Device compliance checks

2. **Implement PIM (Privileged Identity Management):**
   - Just-in-time admin access
   - Access reviews quarterly
   - Automated access certification

---

## Configuration Reference

### Environment Variables

```bash
# Authentication
AZURE_B2C_TENANT=httbrandsb2c.onmicrosoft.com
AZURE_B2C_POLICY=B2C_1A_SIGNUP_SIGNIN
AZURE_B2C_CLIENT_ID=<app-registration-client-id>

# Token validation
JWT_ALGORITHM=RS256
JWT_AUDIENCE=<app-client-id>
SESSION_TIMEOUT=28800  # 8 hours
```

---

<p align="center"><small>Authentication Guide v1.8.1 | Secured by Azure AD B2C</small></p>

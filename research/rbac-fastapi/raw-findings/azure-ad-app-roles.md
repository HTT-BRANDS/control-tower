# Azure AD / Entra ID App Roles — Raw Findings

**Source**: https://learn.microsoft.com/en-us/entra/identity-platform/howto-add-app-roles-in-apps
**Tier**: 1 (Official Vendor Documentation)
**Retrieved**: 2026-04-14
**Last Updated**: 2024-11-13

## What Are App Roles?

App roles are custom roles defined in an Azure AD App Registration that get emitted as a `roles` claim in JWT tokens. They are the Microsoft-recommended way to implement RBAC for custom applications.

## App Roles vs Groups

| Aspect | App Roles | Groups |
|--------|-----------|--------|
| Scope | App-specific (defined per registration) | Tenant-wide |
| Portability | Move with the app | ❌ Different IDs per tenant |
| JWT Claim | `roles` | `groups` |
| SaaS apps | ✅ Recommended | ❌ Group IDs differ per tenant |
| Removed when app deleted | Yes | No |

**Key Insight**: For SaaS/multi-tenant apps, **app roles are preferred** because group IDs are different in each tenant, but app role values are consistent.

## How App Roles Work

### 1. Define in App Registration

Azure Portal → App Registration → App roles → Create:

| Field | Description | Our Value |
|-------|-------------|-----------|
| Display name | Human label | "Admin" |
| Allowed member types | Users/Groups or Applications | Users/Groups |
| Value | String in the JWT `roles` claim | `admin` |
| Description | Detailed description | "Full platform administrator" |
| Enabled | Toggle | Yes |

### 2. Assign to Users/Groups

Azure Portal → Enterprise applications → [App] → Users and groups → Add assignment

Users/groups are assigned specific app roles. Multiple roles can be assigned.

### 3. Receive in Token

When user authenticates, the `roles` claim in the ID token (or access token) contains the assigned role values:

```json
{
  "aud": "your-client-id",
  "iss": "https://login.microsoftonline.com/{tenant}/v2.0",
  "sub": "user-object-id",
  "roles": ["admin", "tenant_admin"],
  "name": "Tyler Grundlund",
  ...
}
```

### 4. Validate in Application

```python
# In our token validation
roles = payload.get("roles", [])
# roles = ["admin"] or ["tenant_admin"] or ["viewer"]
```

## Manifest Definition (JSON)

App roles can also be defined in the app manifest JSON:

```json
"appRoles": [
  {
    "allowedMemberTypes": ["User"],
    "displayName": "Admin",
    "id": "unique-guid-here",
    "isEnabled": true,
    "description": "Full system administrator",
    "value": "admin"
  },
  {
    "allowedMemberTypes": ["User"],
    "displayName": "Tenant Admin", 
    "id": "another-guid",
    "isEnabled": true,
    "description": "Tenant-level administrator",
    "value": "tenant_admin"
  },
  {
    "allowedMemberTypes": ["User"],
    "displayName": "Analyst",
    "id": "another-guid-2",
    "isEnabled": true,
    "description": "Read and export access to all data",
    "value": "analyst"
  },
  {
    "allowedMemberTypes": ["User"],
    "displayName": "Viewer",
    "id": "another-guid-3",
    "isEnabled": true,
    "description": "Read-only access",
    "value": "viewer"
  }
]
```

## Impact on Our Current Implementation

### Current: Group-Based Role Mapping

```python
# app/core/auth.py — current implementation
def _map_groups_to_roles(self, groups: list[str]) -> list[str]:
    roles = ["user"]
    for group in groups:
        group_lower = group.lower()
        if any(admin in group_lower for admin in admin_groups):
            roles.append("admin")
        # ... keyword matching
    return list(set(roles))
```

**Problems with current approach**:
1. Brittle keyword matching
2. Group names/IDs differ per tenant
3. No formal role definition

### Target: App Role Claim Mapping

```python
# New approach — direct claim mapping
roles_claim = payload.get("roles", [])
# roles_claim is already ["admin"] or ["viewer"] — no mapping needed!

# Just validate against known roles
valid_roles = {r.value for r in Role}
user_roles = [r for r in roles_claim if r in valid_roles]
if not user_roles:
    user_roles = ["viewer"]  # Default
```

**Benefits**:
1. No keyword matching — roles are explicit in the token
2. Portable across tenants (same app role values)
3. Managed in Azure Portal (not in code)
4. Auditable via Entra ID logs

## Migration Steps

1. Define 4 app roles in our App Registration (Admin, TenantAdmin, Analyst, Viewer)
2. Assign app roles to existing users in Enterprise Applications
3. Update token validation to read `roles` claim
4. Keep `_map_groups_to_roles()` as fallback during transition
5. Remove group-based mapping after all users have app roles assigned

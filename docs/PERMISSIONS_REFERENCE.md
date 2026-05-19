# Azure Permissions Reference

This document provides detailed instructions for configuring all required permissions.

---

## Overview

The Governance Platform needs TWO types of permissions:

| Permission Type | What It Accesses | Where Configured |
|-----------------|-----------------|------------------|
| **Microsoft Graph API** | Azure AD data (users, groups, roles) | App Registration → API Permissions |
| **Azure RBAC** | Azure resources (VMs, storage, costs) | Subscription → Access Control (IAM) |

> ⚠️ **Both are required!** Graph API permissions alone won't give access to Azure resources, and RBAC alone won't give access to user/identity data.

---

## Part 1: Microsoft Graph API Permissions

### What These Permissions Allow

| Permission | What It Reads | Used For |
|------------|---------------|----------|
| `User.Read.All` | All user profiles | User counts, stale account detection |
| `Group.Read.All` | All groups and members | Group-based analysis |
| `Directory.Read.All` | Directory structure | Tenant overview |
| `RoleManagement.Read.All` | Role assignments | Privileged user identification |
| `Policy.Read.All` | Conditional access policies | Policy compliance |
| `AuditLog.Read.All` | Sign-in and audit logs | Activity tracking |
| `Reports.Read.All` | Usage reports | MFA statistics |

### Step-by-Step Instructions

#### Step 1: Navigate to API Permissions

```
Azure Portal
    └── Azure Active Directory
            └── App registrations
                    └── [Your App]
                            └── API permissions  ← Click this
```

#### Step 2: Add Microsoft Graph Permissions

1. Click **"+ Add a permission"**
2. Select **"Microsoft Graph"** (usually first option)
3. Select **"Application permissions"** (NOT Delegated!)

> ⚠️ **Critical:** Choose "Application permissions," not "Delegated permissions"
>
> - **Delegated** = Acts on behalf of a signed-in user
> - **Application** = Acts as itself, no user required ← **Choose this**

#### Step 3: Search and Add Each Permission

For each permission below:
1. Type the permission name in the search box
2. Check the box next to it
3. Click "Add permissions"
4. Repeat for all 7 permissions

| Search For | Select |
|------------|--------|
| User.Read | ☐ User.Read.All |
| Group.Read | ☐ Group.Read.All |
| Directory.Read | ☐ Directory.Read.All |
| RoleManagement.Read | ☐ RoleManagement.Read.All |
| Policy.Read | ☐ Policy.Read.All |
| AuditLog.Read | ☐ AuditLog.Read.All |
| Reports.Read | ☐ Reports.Read.All |

#### Step 4: Grant Admin Consent

After adding all permissions:

1. Click **"Grant admin consent for [Your Tenant Name]"**
2. Click **"Yes"** to confirm
3. Verify all permissions show **✅ Granted for [Tenant]**

> 🔒 **Requires Global Admin:** If the button is grayed out, you need a Global Administrator to perform this step.

#### Verification: What Success Looks Like

Your API permissions table should look like this:

| API / Permission Name | Type | Admin Consent Required | Status |
|-----------------------|------|----------------------|--------|
| Microsoft Graph | | | |
| └─ User.Read.All | Application | Yes | ✅ Granted for Contoso |
| └─ Group.Read.All | Application | Yes | ✅ Granted for Contoso |
| └─ Directory.Read.All | Application | Yes | ✅ Granted for Contoso |
| └─ RoleManagement.Read.All | Application | Yes | ✅ Granted for Contoso |
| └─ Policy.Read.All | Application | Yes | ✅ Granted for Contoso |
| └─ AuditLog.Read.All | Application | Yes | ✅ Granted for Contoso |
| └─ Reports.Read.All | Application | Yes | ✅ Granted for Contoso |

---

## Part 2: Azure RBAC Roles

### What These Roles Allow

| Role | What It Reads | Used For |
|------|---------------|----------|
| `Reader` | All Azure resources | Resource inventory, tags |
| `Cost Management Reader` | Cost and billing data | Cost aggregation, anomalies |
| `Security Reader` | Security recommendations | Secure Score, compliance |

### Important Concepts

#### Scope Hierarchy

```
Management Group (optional)
    └── Subscription          ← Assign roles HERE
            └── Resource Group
                    └── Resource
```

> 💡 **Best Practice:** Assign roles at the **Subscription** level. They automatically inherit down to all Resource Groups and Resources.

#### Role Assignment Components

| Component | Description | Example |
|-----------|-------------|----------|
| **Role** | What permissions to grant | Reader |
| **Assignee** | Who gets the permissions | governance-platform-reader (app) |
| **Scope** | Where it applies | /subscriptions/xxx-xxx-xxx |

### Step-by-Step Instructions

#### Step 1: Navigate to Subscription IAM

```
Azure Portal
    └── Subscriptions
            └── [Select a subscription]
                    └── Access control (IAM)  ← Click this
```

#### Step 2: Add Role Assignment

1. Click **"+ Add"**
2. Select **"Add role assignment"**

#### Step 3: Select the Role

1. In the Role tab, search for the role
2. Select it and click **"Next"**

| Role to Assign | Search Term |
|----------------|-------------|
| Reader | `Reader` |
| Cost Management Reader | `Cost Management Reader` |
| Security Reader | `Security Reader` |

> ⚠️ **Don't confuse:** "Reader" is different from "Cost Management Reader." You need both!

#### Step 4: Select the App as Member

1. On the Members tab, keep **"User, group, or service principal"** selected
2. Click **"+ Select members"**
3. Search for your app: `governance-platform-reader`
4. Select it from the list
5. Click **"Select"**
6. Click **"Review + assign"**

#### Step 5: Confirm the Assignment

1. Review the summary
2. Click **"Review + assign"** again

#### Step 6: Repeat for All Roles

Repeat Steps 2-5 for each of the three roles:
- [ ] Reader
- [ ] Cost Management Reader  
- [ ] Security Reader

#### Step 7: Repeat for All Subscriptions

If a tenant has multiple subscriptions, repeat the entire process for each one.

| Tenant | Subscription | Reader | Cost Mgmt Reader | Security Reader |
|--------|--------------|--------|------------------|------------------|
| Tenant 1 | Production Sub | ☐ | ☐ | ☐ |
| Tenant 1 | Dev Sub | ☐ | ☐ | ☐ |
| Tenant 2 | Main Sub | ☐ | ☐ | ☐ |
| ... | ... | ☐ | ☐ | ☐ |

### Verification: Check Role Assignments

1. Go to Subscription → Access control (IAM)
2. Click **"Role assignments"** tab
3. Search for your app name
4. Verify all three roles appear:

| Name | Type | Role | Scope |
|------|------|------|-------|
| governance-platform-reader | App | Reader | This subscription |
| governance-platform-reader | App | Cost Management Reader | This subscription |
| governance-platform-reader | App | Security Reader | This subscription |

---

## Part 3: Verification Testing

### Test Graph API Access

Use Azure CLI to verify Graph API permissions:

```bash
# Login as the service principal
az login --service-principal \
  --username <client-id> \
  --password <client-secret> \
  --tenant <tenant-id>

# Try to list users (requires User.Read.All)
az ad user list --query "[0:3].{Name:displayName,UPN:userPrincipalName}" --output table
```

**Expected Output:**
```
Name              UPN
----------------  -------------------------
John Smith        john@contoso.com
Jane Doe          jane@contoso.com
Bob Wilson        bob@contoso.com
```

**If Error:** `Insufficient privileges` → Graph permissions not granted correctly.

### Test Azure RBAC Access

```bash
# List subscriptions (requires Reader)
az account list --query "[].{Name:name,Id:id}" --output table

# List resources (requires Reader)
az resource list --subscription <sub-id> --query "[0:3].{Name:name,Type:type}" --output table
```

**Expected Output:**
```
Name                Type
------------------  ---------------------------------
my-storage-account  Microsoft.Storage/storageAccounts
my-vm               Microsoft.Compute/virtualMachines
my-vnet             Microsoft.Network/virtualNetworks
```

**If Error:** `AuthorizationFailed` → RBAC roles not assigned correctly.

---

## Part 4: Common Permission Errors

### Error: "The signed in user is not assigned to a role"

**Cause:** The app isn't recognized in the target tenant.

**Solution:** Make sure you're looking at the App Registration in the correct tenant.

### Error: "AADSTS65001: The user or administrator has not consented"

**Cause:** Admin consent was not granted.

**Solution:** Go to API permissions and click "Grant admin consent."

### Error: "AADSTS50020: User account does not exist in tenant"

**Cause:** You're trying to access a different tenant than where the app is registered.

**Solution:** Create an App Registration in each tenant.

<!-- ct-9x9: Earlier versions of this doc also suggested Azure Lighthouse
     cross-tenant delegation; that path was removed in ct-59n (April 2026)
     and the per-tenant SP model is now the only supported approach. -->

### Error: "AuthorizationFailed: does not have authorization to perform action"

**Cause:** RBAC role is missing or assigned at wrong scope.

**Solution:** Verify Reader role is assigned at subscription level (not resource group).

### Error: "Cost data not available"

**Cause:** Cost Management Reader role not assigned.

**Solution:** Add the Cost Management Reader role on the subscription.

---

## Part 5: Permission Scope Reference

### What Each Permission Enables in the Platform

| Platform Feature | Graph Permission | RBAC Role |
|-----------------|------------------|------------|
| User count / list | User.Read.All | - |
| Guest users | User.Read.All | - |
| Privileged accounts | RoleManagement.Read.All | - |
| MFA statistics | Reports.Read.All | - |
| Conditional Access | Policy.Read.All | - |
| Resource inventory | - | Reader |
| Resource tags | - | Reader |
| Cost aggregation | - | Cost Management Reader |
| Cost anomalies | - | Cost Management Reader |
| Secure Score | - | Security Reader |
| Policy compliance | - | Reader |

### Minimum Required Permissions (MVP)

If you need to minimize permissions for a pilot:

**Graph API (minimum):**
- User.Read.All
- Directory.Read.All
- RoleManagement.Read.All

**RBAC (minimum):**
- Reader
- Cost Management Reader

> ⚠️ **Note:** Reducing permissions will disable some features.

---

## Quick Reference Card

### Graph API Permissions (Application type, all need Admin Consent)

```
☐ User.Read.All
☐ Group.Read.All
☐ Directory.Read.All
☐ RoleManagement.Read.All
☐ Policy.Read.All
☐ AuditLog.Read.All
☐ Reports.Read.All
```

### Azure RBAC Roles (Subscription scope)

```
☐ Reader
☐ Cost Management Reader
☐ Security Reader
```

### Per-Tenant Checklist

```
Tenant: ________________________

App Registration:
  ☐ Created with name: governance-platform-reader
  ☐ Client ID recorded
  ☐ Client Secret created and recorded

Graph API Permissions:
  ☐ All 7 permissions added as Application type
  ☐ Admin consent granted (green checkmarks)

RBAC Roles (for EACH subscription):
  Subscription: ________________________
    ☐ Reader assigned
    ☐ Cost Management Reader assigned
    ☐ Security Reader assigned
  
  Subscription: ________________________
    ☐ Reader assigned
    ☐ Cost Management Reader assigned
    ☐ Security Reader assigned
```

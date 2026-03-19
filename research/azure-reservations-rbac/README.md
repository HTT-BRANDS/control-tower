# Azure Reservations RBAC & API Research

**Research ID:** web-puppy-78b68f  
**Date:** 2026-03-19  
**Status:** Complete  
**Scope:** Authoritative Microsoft Learn documentation — 6 targeted questions on Azure reservation permissions, API scopes, and Lighthouse cross-tenant behavior.

---

## 🎯 Executive Summary

This research resolves 6 critical questions about Azure reservation data access patterns directly relevant to this project's multi-tenant governance platform. The findings reveal **three separate permission systems** that are frequently conflated, and a **fundamental Lighthouse limitation** that may require architectural changes.

---

## 🔑 Key Findings at a Glance

| # | Question | Verdict |
|---|----------|---------|
| Q1 | Does Cost Management Reader include `Microsoft.Consumption/reservationSummaries/read`? | ✅ **YES** — via `Microsoft.Consumption/*/read` wildcard |
| Q2 | Does Contributor include `Microsoft.Capacity/reservations/read` and `Microsoft.Consumption/reservationSummaries/read`? | ✅ **YES** — via `*` wildcard, neither is in NotActions |
| Q3 | Reservation Summaries API endpoint, version, RBAC, and scope | ⚠️ **EA/billing-account scope only** for the List endpoint; requires billing account access |
| Q4 | Can Lighthouse delegate reservation summary access cross-tenant? | ❌ **BLOCKED** — dual architectural barriers prevent this |
| Q5 | Are `Microsoft.Capacity/reservations/read` and `Microsoft.Consumption/reservationSummaries/read` separate? | ✅ **YES** — completely separate namespaces, separate data |
| Q6 | Is there a built-in "Reservations Reader" role? | ✅ **YES** — `582fc458-8989-419f-a480-75249bc5db7e` (NOT `72fafb9e`) |

---

## Q1 — Cost Management Reader (`72fafb9e-0641-4937-9268-a91bfd8191a3`)

**Does it include `Microsoft.Consumption/reservationSummaries/read`?**

**YES.** The role's Actions contain `Microsoft.Consumption/*/read` — a wildcard covering **all** Microsoft.Consumption read operations including `reservationSummaries/read`.

### Complete Action List (from official JSON definition)

```json
"actions": [
  "Microsoft.Consumption/*/read",
  "Microsoft.CostManagement/*/read",
  "Microsoft.Billing/billingPeriods/read",
  "Microsoft.Resources/subscriptions/read",
  "Microsoft.Resources/subscriptions/resourceGroups/read",
  "Microsoft.Support/*",
  "Microsoft.Advisor/configurations/read",
  "Microsoft.Advisor/recommendations/read",
  "Microsoft.Management/managementGroups/read",
  "Microsoft.Billing/billingProperty/read"
],
"notActions": [],
"dataActions": [],
"notDataActions": []
```

### Microsoft.Consumption actions included (via wildcard):
- ✅ `Microsoft.Consumption/reservationSummaries/read`
- ✅ `Microsoft.Consumption/reservationDetails/read`
- ✅ `Microsoft.Consumption/usageDetails/read`
- ✅ `Microsoft.Consumption/budgets/read`
- ✅ `Microsoft.Consumption/charges/read`
- ✅ All other `Microsoft.Consumption/*/read` operations

### Microsoft.Capacity actions included:
- ❌ **NONE** — Cost Management Reader has zero Microsoft.Capacity permissions

> **Source:** https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/management-and-governance#cost-management-reader

---

## Q2 — Azure Contributor (`b24988ac-6180-42a0-ab88-20f7382dd24c`)

**Does it include `Microsoft.Capacity/reservations/read` or `Microsoft.Consumption/reservationSummaries/read`?**

**YES TO BOTH.** Contributor's action is `*` (all actions). The NotActions list contains **no** Microsoft.Capacity or Microsoft.Consumption exclusions.

### Full NotActions list (everything Contributor is denied):
```json
"notActions": [
  "Microsoft.Authorization/*/Delete",
  "Microsoft.Authorization/*/Write",
  "Microsoft.Authorization/elevateAccess/Action",
  "Microsoft.Blueprint/blueprintAssignments/write",
  "Microsoft.Blueprint/blueprintAssignments/delete",
  "Microsoft.Compute/galleries/share/action",
  "Microsoft.Purview/consents/write",
  "Microsoft.Purview/consents/delete",
  "Microsoft.Resources/deploymentStacks/manageDenySetting/action",
  "Microsoft.Subscription/cancel/action",
  "Microsoft.Subscription/enable/action"
]
```

**Microsoft.Capacity and Microsoft.Consumption are NOT excluded** → Contributor inherits both permissions.

> **Source:** https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/privileged#contributor

---

## Q3 — Azure Consumption API: Reservation Summaries Endpoint

### Exact Endpoint

```http
GET https://management.azure.com/{resourceScope}/providers/Microsoft.Consumption/reservationSummaries?api-version=2024-08-01&grain={grain}
```

### Parameters

| Parameter | In | Required | Description |
|-----------|-----|----------|-------------|
| `{resourceScope}` | path | ✅ | Fully qualified Azure Resource Manager identifier |
| `api-version` | query | ✅ | `2024-08-01` (current latest) |
| `grain` | query | ✅ | `daily` or `monthly` |
| `$filter` | query | ⚠️ Required for daily grain | `properties/UsageDate ge '{date}' and le '{date}'` |
| `reservationId` | query | Optional | Filter to specific reservation GUID |
| `reservationOrderId` | query | Optional | Reservation Order GUID |

### RBAC/Security Section (Official Docs)
The official security specification lists only:
- **Type:** oauth2
- **Flow:** implicit
- **Scope:** `user_impersonation`

> ⚠️ No specific RBAC action is listed in the OpenAPI spec security section. The permission is enforced at the ARM layer: **`Microsoft.Consumption/reservationSummaries/read`** is required (inherited from the namespace pattern).

### Supported Scopes — Critical Finding

**The List endpoint does NOT work at subscription scope.** The official documentation examples show:

| Example Name | Scope Pattern |
|-------------|---------------|
| `ReservationSummariesDailyWithBillingAccountId` | `/providers/Microsoft.Billing/billingAccounts/{id}` |
| `ReservationSummariesDailyWithBillingProfileId` | `/providers/Microsoft.Billing/billingAccounts/{id}/billingProfiles/{id}` |
| `ReservationSummariesMonthlyWithBillingAccountId` | `/providers/Microsoft.Billing/billingAccounts/{id}` |
| `ReservationSummariesMonthlyWithBillingProfileId` | `/providers/Microsoft.Billing/billingAccounts/{id}/billingProfiles/{id}` |
| `ReservationSummariesMonthlyWithBillingProfileIdReservationId` | `/providers/Microsoft.Billing/billingAccounts/{id}/billingProfiles/{id}` |

**No subscription-scope examples exist.**

Microsoft additionally states explicitly:
> *"If you're an EA customer, you can programmatically view how the reservations in your organization are being used. For other subscriptions, use the API **Reservations Summaries - List By Reservation Order And Reservation**."*

This means:
- **EA customers:** Use `List` at billing account scope
- **Non-EA (PAYG, MCA, etc.):** Use `List By Reservation Order And Reservation` at reservation order scope

> **Sources:**
> - https://learn.microsoft.com/en-us/rest/api/consumption/reservations-summaries/list?view=rest-consumption-2024-08-01
> - https://learn.microsoft.com/en-us/azure/cost-management-billing/reservations/reservation-apis#see-reservation-usage

---

## Q4 — Azure Lighthouse Cross-Tenant Reservation Access

### Can reservation summaries be read via Azure Lighthouse delegation?

**Answer: NO — blocked by two independent architectural barriers.**

### Barrier 1: Reservation Roles Cannot Be Delegated via Lighthouse

The four reservation-specific RBAC roles (`Reservations Reader`, `Reservations Administrator`, `Reservations Contributor`, `Reservation Purchaser`) all have:

```json
"assignableScopes": ["/providers/Microsoft.Capacity"]
```

Azure Lighthouse delegates at **subscription** or **resource group** scope. It **cannot** delegate roles scoped to `/providers/Microsoft.Capacity`. These are fundamentally different scope types.

### Barrier 2: Billing Account Scope Is Not Delegatable via Lighthouse

The reservation summaries API (the `List` endpoint) uses **billing account scope** (`/providers/Microsoft.Billing/billingAccounts/...`). Azure Lighthouse only delegates subscription and resource group management — **billing accounts are never in scope for Lighthouse delegation**.

### Official Lighthouse Limitations (from documentation, last updated 01/21/2026)

| Limitation | Details |
|-----------|---------|
| ARM-only | Lighthouse only supports `management.azure.com` operations — no instance-level URIs |
| No Owner/DataActions roles | Only built-in roles without DataActions |
| No custom roles | Not supported |
| IAM invisibility | Lighthouse assignments don't appear in `az role assignment list` |
| National cloud | Cross-national-cloud delegation not supported |

### Workarounds for Cross-Tenant Reservation Data

1. **Service Principal in customer tenant** — Create an SP with Reservations Reader in the customer's tenant, share credentials securely (not recommended for multi-tenant)
2. **Managed Identity with Customer Consent** — Customer grants EA billing reader access to the managing tenant's managed identity
3. **Export to Storage** — Customer configures reservation utilization export to a storage account that the managing tenant can read via Lighthouse
4. **Cost Management Partner APIs** — If operating as a CSP partner, use Partner Center APIs instead

> **Source:** https://learn.microsoft.com/en-us/azure/lighthouse/concepts/cross-tenant-management-experience#current-limitations

---

## Q5 — `Microsoft.Capacity/reservations/read` vs `Microsoft.Consumption/reservationSummaries/read`

### Are these separate permissions?

**YES — completely separate permissions in entirely different namespaces.**

| Dimension | `Microsoft.Capacity/reservations/read` | `Microsoft.Consumption/reservationSummaries/read` |
|-----------|----------------------------------------|--------------------------------------------------|
| **Namespace** | Microsoft.Capacity (Reservation management plane) | Microsoft.Consumption (Cost/billing plane) |
| **What it reads** | Reservation object metadata: SKU, term, quantity, scope, expiry, purchase info | Reservation utilization summaries: used hours, reserved hours, utilization %, avg/min/max |
| **Roles that grant it** | Reservations Reader, Reservations Administrator, Reservations Contributor, Contributor | Cost Management Reader, Contributor |
| **Scope** | `/providers/Microsoft.Capacity` | Billing account, billing profile |
| **API namespace** | `Microsoft.Capacity/reservations` REST API | `Microsoft.Consumption/reservationSummaries` REST API |
| **For Lighthouse** | ❌ Cannot delegate (wrong assignable scope) | ⚠️ Permission exists in delegatable roles, but API scope is billing account (not delegatable) |

### Which permission is needed for `GET /providers/Microsoft.Consumption/reservationSummaries`?

**`Microsoft.Consumption/reservationSummaries/read`** — not `Microsoft.Capacity/reservations/read`.

The endpoint lives in the `Microsoft.Consumption` namespace. Having only `Microsoft.Capacity/reservations/read` (Reservations Reader role) will **not** grant access to the consumption/summaries endpoint.

> **Source:** https://learn.microsoft.com/en-us/rest/api/consumption/reservations-summaries

---

## Q6 — Built-in "Reservations Reader" Role

### Does it exist?

**YES** — it is a distinct built-in role, completely separate from Cost Management Reader.

| Field | Value |
|-------|-------|
| **Role Name** | Reservations Reader |
| **roleDefinitionId** | `582fc458-8989-419f-a480-75249bc5db7e` |
| **Description** | "Lets one read all the reservations in a tenant" |
| **assignableScopes** | `["/providers/Microsoft.Capacity"]` |
| **roleType** | BuiltInRole |

### Full permissions:
```json
"actions": [
  "Microsoft.Capacity/*/read",
  "Microsoft.Authorization/roleAssignments/read"
],
"notActions": [],
"dataActions": [],
"notDataActions": []
```

### ⚠️ IMPORTANT: Role ID Clarification

The question referenced `72fafb9e-0641-4937-9268-a91bfd8191a3` as potentially being "Reservations Reader." This is **incorrect**:

- `72fafb9e-0641-4937-9268-a91bfd8191a3` = **Cost Management Reader**
- `582fc458-8989-419f-a480-75249bc5db7e` = **Reservations Reader**

These are completely different roles with different permissions, different scopes, and different purposes.

### Related reservation roles (all four built-in roles):

| Role | ID | Scope | Can Buy? | Can Manage? | Can Read? | Can Delegate? |
|------|----|-------|----------|-------------|-----------|---------------|
| Reservations Reader | `582fc458-8989-419f-a480-75249bc5db7e` | `/providers/Microsoft.Capacity` | ❌ | ❌ | ✅ | ❌ |
| Reservations Contributor | `(see docs)` | `/providers/Microsoft.Capacity` | ❌ | ✅ | ✅ | ❌ |
| Reservations Administrator | `a8889054-8d42-49c9-bc1c-52486c10e7cd` | `/providers/Microsoft.Capacity` | ❌ | ✅ | ✅ | ✅ |
| Reservation Purchaser | `(see docs)` | `/subscriptions` | ✅ | ❌ | ❌ | ❌ |

> **Sources:**
> - https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/management-and-governance#reservations-reader
> - https://learn.microsoft.com/en-us/azure/cost-management-billing/reservations/view-reservations#azure-reservation-rbac-roles

---

## Project Implications for azure-governance-platform

1. **Cost sync service**: The existing `cost_service.py` can read reservation summaries IF the managed service principal has Cost Management Reader and the customer is on EA with billing account access configured.

2. **Lighthouse-delegated tenants**: Cross-tenant reservation data **cannot** be fetched via the standard Lighthouse delegation path. The `azure_client.py` wrapper needs a separate code path for reservation data.

3. **Permission model**: The platform should document to onboarding customers that reservation data access requires **billing account RBAC**, which is separate from the subscription-level RBAC granted via Lighthouse.

4. **Recommended approach**: For EA customers, request billing account Cost Management Reader. For PAYG/MCA, use the reservation-order-scoped endpoint and require Reservations Reader in the customer's tenant.

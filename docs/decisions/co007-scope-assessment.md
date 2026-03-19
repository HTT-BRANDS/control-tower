# CO-007 Scope Assessment: Azure Lighthouse Delegation for Reserved Instance Utilization

**Status:** Complete  
**Date:** 2025-07-22  
**Author:** Solutions Architect 🏛️ (`solutions-architect-a1bb09`)  
**Task:** WIGGUM_ROADMAP §9.3.1  
**bd issue:** `azure-governance-platform-s6y`

---

## 1. Executive Summary

**Verdict: The current Azure Lighthouse delegation CANNOT provide reservation utilization data. This is an architectural scope limitation, not a missing permission.**

The Reservation Summaries API requires **billing account scope** (`/providers/Microsoft.Billing/billingAccounts/{id}`), which is outside the Lighthouse delegation model (subscription scope only). The `ReservationService` must be implemented with graceful degradation and an optional per-customer billing account onboarding path.

---

## 2. Current Delegation Scope

Source: `infrastructure/lighthouse/delegation.json`

| Role | Role Definition ID | Key Permissions |
|------|--------------------|-----------------|
| **Contributor** | `b24988ac-6180-42a0-ab88-20f7382dd24c` | `*` (all actions except listed NotActions) |
| **Cost Management Reader** | `72fafb9e-0641-4937-9268-a91bfd8191a3` | `Microsoft.Consumption/*/read`, `Microsoft.CostManagement/*/read` |
| **Security Reader** | `39bc4728-0917-49c7-9d2c-d95423bc2eb4` | Security policies, recommendations, alerts |

**Delegation scope:** Subscription level (per `Microsoft.ManagedServices/registrationDefinitions`)  
**API version:** `2022-10-01`  
**Supported tenants:** htt, frenchies, bishops, tll

---

## 3. Required Permissions Analysis

### 3.1 The Reservation Summaries Endpoint

```http
GET https://management.azure.com/{resourceScope}/providers/Microsoft.Consumption/reservationSummaries
    ?api-version=2024-08-01
    &grain={daily|monthly}
    [&$filter=properties/UsageDate ge '{date}' and le '{date}']
```

**Required RBAC permission:** `Microsoft.Consumption/reservationSummaries/read`

### 3.2 Permission Availability in Delegated Roles

| Permission | Cost Management Reader | Contributor | Notes |
|------------|----------------------|-------------|-------|
| `Microsoft.Consumption/reservationSummaries/read` | ✅ via `Microsoft.Consumption/*/read` | ✅ via `*` | Both roles include this |
| `Microsoft.Consumption/reservationDetails/read` | ✅ via `Microsoft.Consumption/*/read` | ✅ via `*` | Bonus: also available |
| `Microsoft.Capacity/reservations/read` | ❌ Not included | ✅ via `*` | Only in Contributor |

### 3.3 The Scope Problem (Critical Blocker)

The Reservation Summaries API does **NOT** support subscription scope. All documented examples use:

| Scope Type | Example Path |
|------------|-------------|
| Billing Account | `/providers/Microsoft.Billing/billingAccounts/{billingAccountId}` |
| Billing Profile | `/providers/Microsoft.Billing/billingAccounts/{id}/billingProfiles/{id}` |
| Reservation Order | `/providers/Microsoft.Capacity/reservationOrders/{id}/reservations/{id}` |

**Zero subscription-scope examples exist in Microsoft documentation.**

Microsoft's guidance:
> *"If you're an EA customer, you can programmatically view how the reservations in your organization are being used. For other subscriptions, use the API Reservations Summaries - List By Reservation Order And Reservation."*

### 3.4 Why Lighthouse Cannot Reach Billing Scope

Azure Lighthouse delegation operates at:
- ✅ Subscription scope
- ✅ Resource group scope
- ❌ Billing account scope (separate RBAC hierarchy)
- ❌ `/providers/Microsoft.Capacity` scope (incompatible assignableScopes)

Even though Cost Management Reader grants `Microsoft.Consumption/reservationSummaries/read`, the permission at **subscription scope** does NOT satisfy a **billing-account-scoped** API call. These are independent RBAC contexts.

---

## 4. Gap Analysis

| Requirement | Current State | Gap |
|-------------|---------------|-----|
| `Microsoft.Consumption/reservationSummaries/read` permission | ✅ Available (Cost Mgmt Reader wildcard) | None |
| Billing account scope access | ❌ Not delegated via Lighthouse | **BLOCKER** |
| Reservation order scope access | ❌ Not delegated via Lighthouse | **BLOCKER** |
| `Microsoft.Capacity/reservations/read` (reservation metadata) | ✅ Available via Contributor | None (but scope issue same) |

### Root Cause

The gap is **not** a missing permission — it's an **architectural scope mismatch**. Lighthouse delegates at subscription scope; the reservation API requires billing account scope. These are disjoint RBAC hierarchies.

---

## 5. Considered Approaches

### Option A: Direct Billing Account Consent (EA/MCA customers)
- Customer grants Cost Management Reader at billing account scope
- Requires separate onboarding step beyond Lighthouse
- Best for EA customers with centralized billing
- **Pros:** Full utilization data, official API path
- **Cons:** Extra onboarding burden, customer admin action required

### Option B: Per-Reservation-Order Access (non-EA)
- Customer grants Reservations Reader (`582fc458-8989-419f-a480-75249bc5db7e`) at `Microsoft.Capacity` scope
- Platform enumerates each reservation order separately
- **Pros:** Works for PAYG customers
- **Cons:** Requires knowing reservation order IDs, O(n) API calls

### Option C: Scheduled Exports to Shared Storage
- Customer configures Azure Cost Management export job
- Exports land in a storage account accessible via Lighthouse
- Platform reads exported CSV/Parquet files
- **Pros:** Decoupled from live API; works with any billing type
- **Cons:** Data latency (daily at best), extra infrastructure

### Option D: Graceful Degradation with Stub (Recommended for MVP) ✅
- Implement `ReservationService` with full API integration code
- When billing account scope is unavailable, return `{ "available": false, "reason": "billing_account_access_required" }`
- Add optional `billing_account_id` to tenant configuration for customers who provide it
- Platform functions fully for all other cost features; reservation utilization becomes an opt-in premium feature
- **Pros:** No blocking dependency, clean API contract, progressive enhancement
- **Cons:** Feature not available by default until customer opts in

---

## 6. Recommendation

### Implement Option D: Graceful Degradation with Optional Billing Account Access

**Rationale:** This approach:
1. **Unblocks implementation** — `ReservationService` can be built now with proper API integration
2. **No Lighthouse changes needed** — avoids risky delegation template modifications
3. **Progressive enhancement** — customers who provide billing account access get reservation data
4. **Clean API contract** — `GET /api/v1/costs/reservations` returns a clear availability status
5. **Future-proof** — when customers provide billing account IDs, the feature activates automatically

### Implementation Guidance for Python Programmer

#### API Call Pattern
```python
# Primary: billing account scope (when available)
GET /providers/Microsoft.Billing/billingAccounts/{billing_account_id}
    /providers/Microsoft.Consumption/reservationSummaries
    ?api-version=2024-08-01&grain=monthly

# Use httpx direct REST call (same pattern as cost_sync.py _query_costs_rest)
# API version: 2024-08-01
```

#### Tenant Configuration Extension
```python
# Add optional field to Tenant model or tenant config
billing_account_id: str | None = None  # Set when customer provides EA/MCA billing account
```

#### Response Contract
```python
# When billing_account_id is configured:
{
    "available": true,
    "reservations": [
        {
            "reservation_id": "...",
            "reservation_order_id": "...",
            "sku_name": "Standard_D2s_v3",
            "avg_utilization": 85.2,
            "min_utilization": 72.0,
            "max_utilization": 98.5,
            "used_hours": 720.0,
            "reserved_hours": 744.0,
            "grain": "monthly",
            "usage_date": "2025-07-01"
        }
    ],
    "summary": {
        "total_reservations": 12,
        "avg_utilization_percent": 85.2,
        "underutilized_count": 3,
        "underutilization_threshold": 80.0
    }
}

# When billing_account_id is NOT configured:
{
    "available": false,
    "reason": "billing_account_access_required",
    "setup_instructions": "Provide billing account ID in tenant configuration to enable reservation utilization tracking.",
    "reservations": [],
    "summary": null
}
```

#### File Location
- Service: `app/api/services/reservation_service.py`
- Route: `app/api/routes/costs.py` (add `GET /api/v1/costs/reservations`)
- Tests: `tests/unit/test_reservation_service.py`

---

## 7. STRIDE Security Analysis

| Threat | Risk | Mitigation |
|--------|------|------------|
| **Spoofing** | Low | Billing account ID validated against tenant config; no user-supplied scope |
| **Tampering** | Low | Read-only API calls; no write operations on billing data |
| **Repudiation** | Low | All reservation API calls logged via existing audit trail |
| **Information Disclosure** | Medium | Billing account IDs are sensitive; stored encrypted in tenant config. Reservation data reveals spending patterns — enforce tenant isolation |
| **Denial of Service** | Low | Circuit breaker + rate limiting already in place for Consumption API calls |
| **Elevation of Privilege** | Medium | Billing account scope is broader than subscription scope. Validate that only configured billing accounts are queried; never accept user-supplied billing account IDs in API requests |

---

## 8. References

| Source | URL |
|--------|-----|
| Consumption API — Reservation Summaries | https://learn.microsoft.com/en-us/rest/api/consumption/reservations-summaries/list |
| Cost Management Reader role definition | https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/management-and-governance#cost-management-reader |
| Contributor role definition | https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/privileged#contributor |
| Reservations Reader role definition | https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/management-and-governance#reservations-reader |
| Azure Lighthouse limitations | https://learn.microsoft.com/en-us/azure/lighthouse/concepts/cross-tenant-management-experience#current-limitations |
| Reservation usage APIs guide | https://learn.microsoft.com/en-us/azure/cost-management-billing/reservations/reservation-apis#see-reservation-usage |
| Current delegation template | `infrastructure/lighthouse/delegation.json` |
| Existing cost sync pattern | `app/core/sync/costs.py` |
| web-puppy research | `research/azure-reservations-rbac/` |

---

## 9. Decision

**Proceed with `ReservationService` implementation using graceful degradation (Option D).**

- ✅ Current Lighthouse scope is **sufficient for the codebase** — no delegation changes needed
- ⚠️ Reservation data requires **opt-in billing account configuration** per customer
- 🔨 Python Programmer can proceed with implementation immediately
- 📋 Future work: Add billing account onboarding UI/workflow (separate ticket)

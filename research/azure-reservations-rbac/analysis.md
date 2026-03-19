# Multi-Dimensional Analysis — Azure Reservations RBAC

**Research ID:** web-puppy-78b68f | **Date:** 2026-03-19

---

## The Three Separate Permission Systems (Conceptual Framework)

The root cause of confusion in Azure reservation permissions is that there are **three entirely separate systems** that all touch "reservation data":

```
┌─────────────────────────────────────────────────────────────────────┐
│  SYSTEM 1: Microsoft.Capacity                                       │
│  What: Reservation OBJECTS (metadata, scope, term, quantity)        │
│  Where: /providers/Microsoft.Capacity                               │
│  Roles: Reservations Reader (582fc458), Reservations Admin          │
│         (a8889054), Reservations Contributor                        │
│  Scoped to: /providers/Microsoft.Capacity (NOT subscriptions)       │
│  Lighthouse: ❌ Cannot delegate                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  SYSTEM 2: Microsoft.Consumption                                    │
│  What: Reservation UTILIZATION DATA (usage hours, utilization %)    │
│  Where: /providers/Microsoft.Billing/billingAccounts/...            │
│  Roles: Cost Management Reader (72fafb9e), Contributor              │
│  Scoped to: Billing account / billing profile (EA or MCA)           │
│  Lighthouse: ⚠️ Permission exists in delegatable roles BUT          │
│             billing account scope is NOT Lighthouse-accessible       │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  SYSTEM 3: Microsoft.CostManagement                                 │
│  What: Cost/budget AGGREGATION (spend, forecasts, exports)         │
│  Where: Subscription scope OR management group                      │
│  Roles: Cost Management Reader (72fafb9e), Contributor              │
│  Scoped to: Subscriptions / Management groups                       │
│  Lighthouse: ✅ Can delegate (subscription-scope works with         │
│             Lighthouse delegation)                                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Security Analysis

### Authentication & Authorization Model

| Layer | Mechanism | Notes |
|-------|-----------|-------|
| Authentication | Azure AD OAuth2 (implicit flow) | Standard for all ARM APIs |
| API Authorization | ARM RBAC (`Microsoft.Consumption/reservationSummaries/read`) | Enforced by ARM layer, not API spec |
| Scope Authorization | Billing account RBAC | Separate from subscription RBAC |
| Cross-tenant | Service principal per tenant OR billing account reader | No single delegation model |

### Security Risk: Role ID Confusion

The question referenced `72fafb9e-0641-4937-9268-a91bfd8191a3` as potentially being "Reservations Reader." 

**This is wrong and dangerous:**
- `72fafb9e` = **Cost Management Reader** (subscription-scoped, Cost data)
- `582fc458` = **Reservations Reader** (Capacity-scoped, reservation objects)

Assigning the wrong role in automation scripts or Terraform would silently grant the wrong access. Both are read-only but cover completely different data.

### Principle of Least Privilege Analysis

| Goal | Minimum Sufficient Role | Notes |
|------|------------------------|-------|
| Read reservation objects (what was purchased) | Reservations Reader (`582fc458`) | Scoped to Microsoft.Capacity |
| Read reservation utilization % (EA) | Cost Management Reader (`72fafb9e`) at billing account | Requires billing account assignment |
| Read reservation utilization % (non-EA) | Reservations Reader (`582fc458`) + call `List By Reservation Order` | Different endpoint |
| Read both objects + utilization (EA) | Cost Management Reader at billing account | Wildcard covers all Consumption |
| Full reservation management | Reservations Administrator (`a8889054`) | Scoped to Microsoft.Capacity |

---

## Cost Analysis (Implementation Cost)

### Option A: EA Billing Account Access
- **Setup effort:** Customer must grant billing account reader role in Azure Cost Management portal
- **Operational cost:** Zero additional API cost (included in Cost Management)
- **Maintenance:** Role assignment survives unless explicitly revoked
- **Risk:** High-privilege path — billing account access is broad

### Option B: Reservation-Order-Scoped Access (Non-EA)
- **Setup effort:** Per-reservation-order role assignment OR customer uses PowerShell to grant access
- **Operational cost:** Zero additional API cost
- **Maintenance:** Must be granted per reservation order — not scalable for many reservations
- **Risk:** Least-privilege but high management overhead

### Option C: Customer Exports to Storage (Recommended for Lighthouse)
- **Setup effort:** Customer configures Cost Management export to storage account
- **Operational cost:** Storage costs (~$0.01/GB/month for LRS)
- **Maintenance:** Export schedule management, storage access review
- **Risk:** Data is a snapshot (not real-time), but fully delegatable

---

## Implementation Complexity Analysis

### Complexity by Approach

| Approach | Dev Effort | Ops Effort | Scalability | Reliability |
|---------|-----------|-----------|-------------|-------------|
| Billing account RBAC (EA) | Low | Medium (customer setup per billing account) | Good | High |
| Reservation order RBAC | Medium | High (per-order grants) | Poor | Medium |
| Storage export | High (export parsing) | Medium | Excellent | High (async) |
| Partner Center API (CSP) | Very High | Low | Excellent | High |

### Code-Level Complexity for this Project

The project's `azure_client.py` currently wraps Azure SDK. For reservation summaries:

1. **Current cost_service.py** likely uses subscription-scoped endpoints — these will NOT return reservation data
2. **New endpoint pattern:** Must accept billing account ID as a parameter, not subscription ID
3. **Multi-tenant complication:** Each customer tenant has a separate billing account ID that is NOT discoverable via Lighthouse delegation
4. **SDK support:** The Azure SDK (`azure-mgmt-consumption`) supports the reservationSummaries endpoint but the billing account ID must be known in advance

---

## Stability Analysis

### API Versioning
- Current latest: `2024-08-01`
- Previous stable: `2023-03-01`
- Reservation summaries API has been stable since 2019, no breaking changes in recent versions
- Microsoft maintains N-2 API version support for consumption APIs

### Role Stability
- All four built-in reservation roles are stable and GA
- `assignableScopes: ["/providers/Microsoft.Capacity"]` has been constant
- Cost Management Reader has been stable since 2019

---

## Compatibility Analysis

### Azure Subscription Type Compatibility

| Subscription Type | `List` Endpoint | `List By Reservation Order` | Lighthouse Delegation |
|-------------------|-----------------|----------------------------|----------------------|
| EA (Enterprise Agreement) | ✅ Billing account scope | ✅ Reservation order scope | ❌ Billing account not Lighthouse scope |
| MCA (Microsoft Customer Agreement) | ✅ Billing profile scope | ✅ Reservation order scope | ❌ Billing profile not Lighthouse scope |
| PAYG (Pay-As-You-Go) | ❌ No billing account access | ✅ Reservation order scope | ❌ Same limitation |
| CSP (Cloud Solution Provider) | ⚠️ Via Partner Center | ✅ Reservation order scope | ❌ |
| Visual Studio / Dev/Test | ❌ Typically no reservations | ✅ If any reserved | ❌ |

### SDK Compatibility

| SDK | Supports reservationSummaries | Version |
|-----|-------------------------------|---------|
| `azure-mgmt-consumption` (Python) | ✅ | >= 3.0.0 |
| `@azure/arm-consumption` (JS/TS) | ✅ | >= 9.0.0 |
| `Az.Consumption` (PowerShell) | ✅ | >= 6.0.0 |
| Azure CLI (`az consumption`) | ✅ | >= 2.0.76 |

---

## Optimization Analysis

### Rate Limiting
- ARM APIs: 12,000 reads/hour per subscription
- Consumption APIs: Lower limits apply — recommend caching
- Reservation summaries are appropriate for **daily caching** (data only changes daily for monthly grain)

### Payload Size Warning
> ⚠️ Microsoft documentation explicitly warns: *"ARM has a payload size limit of 12MB, so currently callers get 400 when the response size exceeds the ARM limit. In such cases, API call should be made with smaller date ranges."*

For large EA customers with many reservations, this can be a real problem. Recommendation: Use monthly grain with date-range chunking.

### Caching Strategy for this Project
- Cache reservation summaries daily (grain = monthly, refreshed once per day)
- Store in SQLite `reservation_summary_cache` table with tenant_id + billing_account_id + date_key
- TTL: 24 hours for monthly grain, 12 hours for daily grain

---

## Maintenance Analysis

### What Requires Customer Action
The following cannot be set up unilaterally by the managing tenant:
1. Granting billing account Cost Management Reader role (customer must do this in Azure portal)
2. For MCA: Granting billing profile access
3. For non-EA: Granting access to individual reservation orders

### Monitoring Recommendations
- Monitor for `403 Forbidden` on reservation summaries — indicates billing account access lost
- Alert on `400 Bad Request` with "payload too large" — indicates date range needs chunking
- Track missing billing account IDs in the tenant onboarding database

---

## The Lighthouse Barrier — Detailed Analysis

This is the most architecturally significant finding. Here is why it breaks down precisely:

```
LIGHTHOUSE DELEGATION MODEL:
  Managing Tenant → delegates → Customer Subscription
                                         ↓
                    Can access: /subscriptions/{id}/resourceGroups/...
                    Can access: /subscriptions/{id}/providers/Microsoft.Compute/...
                    Can access: /subscriptions/{id}/providers/Microsoft.CostManagement/...
                    
                    CANNOT access: /providers/Microsoft.Billing/billingAccounts/...
                    CANNOT access: /providers/Microsoft.Capacity/...

RESERVATION SUMMARIES ENDPOINT:
  GET .../providers/Microsoft.Billing/billingAccounts/{id}/providers/
            Microsoft.Consumption/reservationSummaries
                              ↑
              This path starts at billingAccounts scope.
              Lighthouse delegation never reaches here.
              
RESERVATION READER ROLE:
  assignableScopes: ["/providers/Microsoft.Capacity"]
                              ↑
              This scope type doesn't exist in Lighthouse delegation.
              You can't assign this role to a managing tenant principal
              via Lighthouse because Lighthouse only creates
              assignments at subscription/resourceGroup scope.
```

**Bottom line:** Even if you assigned Cost Management Reader via Lighthouse at subscription scope, the `Microsoft.Consumption/reservationSummaries/read` permission it grants would be for subscription-level consumption data — the reservation summaries endpoint at billing account scope requires separate billing account RBAC that Lighthouse cannot provide.

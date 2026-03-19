# Recommendations — Azure Reservations RBAC

**Research ID:** web-puppy-78b68f | **Date:** 2026-03-19  
**Project Context:** azure-governance-platform (FastAPI + HTMX, multi-tenant, Azure Lighthouse)

---

## Priority 1 — Critical (Address Immediately)

### REC-001: Fix Role ID in Any Code/Config That References `72fafb9e`

If any code, Terraform, ARM templates, or documentation in this project refers to `72fafb9e-0641-4937-9268-a91bfd8191a3` as "Reservations Reader", **fix it immediately**.

- `72fafb9e-0641-4937-9268-a91bfd8191a3` = **Cost Management Reader** (cost data, billing periods)
- `582fc458-8989-419f-a480-75249bc5db7e` = **Reservations Reader** (reservation objects, utilization)

```bash
# Audit the codebase now
grep -r "72fafb9e" . --include="*.py" --include="*.json" --include="*.tf" --include="*.yaml"
grep -r "reservations.reader\|reservations_reader" . --include="*.py"
```

---

### REC-002: Do Not Attempt to Access Reservation Summaries via Lighthouse Subscription Delegation

The current architecture uses Azure Lighthouse to delegate subscription management. **Reservation summaries via the `Microsoft.Consumption/reservationSummaries` endpoint will not work through this path** for two separate reasons:

1. The List endpoint requires billing account scope, not subscription scope
2. Reservation roles (`Microsoft.Capacity`) cannot be delegated via Lighthouse

**Immediate action:** If `cost_service.py` or `azure_client.py` attempts to call the reservation summaries API using a Lighthouse-delegated service principal scoped to a subscription, it will receive `403 Forbidden`. Add explicit error handling and a clear user-facing message explaining that billing account access is required separately.

---

## Priority 2 — High (Address This Sprint/Iteration)

### REC-003: Add Billing Account ID to Tenant Onboarding Model

The tenant onboarding model (`app/models/tenant.py`) almost certainly has a `subscription_id` field. Add:

```python
class TenantConfig(BaseModel):
    # ... existing fields ...
    subscription_id: str
    billing_account_id: Optional[str] = None      # EA or MCA billing account
    billing_profile_id: Optional[str] = None      # MCA billing profile (within billing account)
    reservation_access_type: Optional[str] = None  # "billing_account", "reservation_order", "none"
```

Without `billing_account_id`, reservation summaries cannot be fetched programmatically.

---

### REC-004: Implement Two-Path Reservation Summary Fetching

Add logic that selects the correct API endpoint based on the customer's subscription type:

```python
async def get_reservation_summaries(
    tenant_id: str,
    grain: str = "monthly",
    start_date: str = None,
    end_date: str = None
) -> list[dict]:
    """
    Fetch reservation utilization summaries.
    
    EA customers: Uses /providers/Microsoft.Billing/billingAccounts/{id}
                  /providers/Microsoft.Consumption/reservationSummaries
                  Requires: Cost Management Reader at billing account scope
    
    Non-EA customers: Uses /providers/Microsoft.Capacity/reservationOrders/{id}
                      /providers/Microsoft.Consumption/reservationSummaries
                      Requires: Reservations Reader (582fc458) at reservation scope
    """
    tenant = await get_tenant_config(tenant_id)
    
    if tenant.billing_account_id:
        # EA / MCA path — billing account scope
        scope = f"providers/Microsoft.Billing/billingAccounts/{tenant.billing_account_id}"
        if tenant.billing_profile_id:
            scope += f"/billingProfiles/{tenant.billing_profile_id}"
        return await _fetch_reservation_summaries_at_scope(scope, grain, start_date, end_date)
    else:
        # Non-EA path — requires per-reservation-order access
        # List reservation orders first, then fetch summaries per order
        return await _fetch_reservation_summaries_by_order(tenant_id, grain, start_date, end_date)
```

---

### REC-005: Update the Lighthouse Onboarding Template

The self-service Lighthouse onboarding (`app/api/routes/onboarding.py`) must document to customers that:

1. **Subscription delegation** (current) → enables: cost management, compliance, resources, identity
2. **Billing account access** (additional, manual) → enables: reservation utilization summaries

Add to the onboarding instructions:
```
OPTIONAL - For reservation utilization reporting:
1. Go to Azure Portal → Cost Management + Billing
2. Select your billing account
3. Access Control (IAM) → Add → Cost Management Reader
4. Assign to: [your-managing-tenant-service-principal]
5. Enter your billing account ID in the platform settings
```

---

## Priority 3 — Medium (Next Iteration)

### REC-006: Implement Payload Size Protection

The Microsoft Consumption API has a 12MB ARM response limit and will return `400 Bad Request` for large responses. Add chunking:

```python
async def _fetch_reservation_summaries_at_scope(
    scope: str, grain: str, start_date: str, end_date: str
) -> list[dict]:
    """Fetch with automatic date-range chunking to stay under 12MB ARM limit."""
    all_results = []
    
    # For monthly grain: chunk by 3-month windows
    # For daily grain: chunk by 30-day windows  
    chunk_size = timedelta(days=90) if grain == "monthly" else timedelta(days=30)
    
    current_start = parse_date(start_date)
    final_end = parse_date(end_date)
    
    while current_start < final_end:
        chunk_end = min(current_start + chunk_size, final_end)
        try:
            chunk = await _call_reservation_summaries_api(
                scope, grain, current_start, chunk_end
            )
            all_results.extend(chunk)
        except ArmPayloadTooLargeError:
            # Further halve the chunk size and retry
            chunk_size = chunk_size // 2
            continue
        current_start = chunk_end
    
    return all_results
```

---

### REC-007: Cache Reservation Summaries in SQLite

Reservation utilization data changes at most daily (monthly grain) or daily (daily grain). Add caching:

```sql
CREATE TABLE reservation_summary_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    billing_account_id TEXT,
    scope_path TEXT NOT NULL,
    grain TEXT NOT NULL CHECK(grain IN ('daily', 'monthly')),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    data JSON NOT NULL,
    cached_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, scope_path, grain, period_start, period_end)
);

CREATE INDEX idx_reservation_cache_lookup 
    ON reservation_summary_cache(tenant_id, grain, period_start);
```

TTL: 24 hours for monthly grain, 6 hours for daily grain.

---

### REC-008: Add Reservation Preflight Check

Extend `app/api/routes/preflight.py` to check reservation access:

```python
async def check_reservation_access(tenant_config: TenantConfig) -> PreflightResult:
    """Check whether reservation data is accessible for a tenant."""
    
    # Check 1: Has billing account configured?
    if not tenant_config.billing_account_id:
        return PreflightResult(
            check="reservation_access",
            status="warning",
            message="No billing account ID configured. Reservation utilization data unavailable.",
            docs_url="https://learn.microsoft.com/en-us/azure/cost-management-billing/reservations/view-reservations"
        )
    
    # Check 2: Can we read reservation summaries?
    try:
        test_result = await get_reservation_summaries(
            tenant_config.tenant_id, 
            grain="monthly",
            start_date=(date.today() - timedelta(days=30)).isoformat(),
            end_date=date.today().isoformat()
        )
        return PreflightResult(check="reservation_access", status="ok", data_count=len(test_result))
    except PermissionError:
        return PreflightResult(
            check="reservation_access",
            status="error",
            message="Cost Management Reader not granted at billing account scope.",
            required_role="Cost Management Reader (72fafb9e-0641-4937-9268-a91bfd8191a3)",
            required_scope=f"/providers/Microsoft.Billing/billingAccounts/{tenant_config.billing_account_id}"
        )
```

---

## Quick Reference: Role IDs for Code

```python
# app/core/constants.py — verified role definition IDs

# Cost management roles (subscription-scoped, Lighthouse-delegatable)
ROLE_COST_MANAGEMENT_READER = "72fafb9e-0641-4937-9268-a91bfd8191a3"
ROLE_CONTRIBUTOR = "b24988ac-6180-42a0-ab88-20f7382dd24c"

# Reservation-specific roles (Microsoft.Capacity scoped, NOT Lighthouse-delegatable)
ROLE_RESERVATIONS_READER = "582fc458-8989-419f-a480-75249bc5db7e"
ROLE_RESERVATIONS_ADMINISTRATOR = "a8889054-8d42-49c9-bc1c-52486c10e7cd"
# Reservations Contributor and Reservation Purchaser IDs need separate lookup
```

---

## Decision Matrix: Which Role to Request from Customers?

```
Is the customer an EA or MCA customer?
│
├── YES → Request Cost Management Reader at billing account scope
│         role: 72fafb9e-0641-4937-9268-a91bfd8191a3
│         scope: /providers/Microsoft.Billing/billingAccounts/{id}
│         Gives: All reservation utilization summaries for the tenant
│
└── NO (PAYG, etc.) → Request Reservations Reader at tenant scope
                      role: 582fc458-8989-419f-a480-75249bc5db7e
                      scope: /providers/Microsoft.Capacity
                      Use endpoint: List By Reservation Order And Reservation
                      Note: Must enumerate reservation orders separately
```

---

## API Endpoint Quick Reference

```
# Get reservation summaries (EA — billing account scope)
GET https://management.azure.com/providers/Microsoft.Billing/billingAccounts/{billingAccountId}/providers/Microsoft.Consumption/reservationSummaries?api-version=2024-08-01&grain=monthly&$filter=properties/UsageDate ge '2024-01-01' and properties/UsageDate le '2024-12-31'

# Get reservation summaries (non-EA — reservation order scope)
GET https://management.azure.com/providers/Microsoft.Capacity/reservationOrders/{reservationOrderId}/reservations/{reservationId}/providers/Microsoft.Consumption/reservationSummaries?api-version=2024-08-01&grain=monthly

# Get reservation objects (any customer with Reservations Reader)
GET https://management.azure.com/providers/Microsoft.Capacity/reservations?api-version=2022-11-01
```

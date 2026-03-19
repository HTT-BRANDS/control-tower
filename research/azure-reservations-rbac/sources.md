# Sources — Azure Reservations RBAC Research

**Research ID:** web-puppy-78b68f | **Date:** 2026-03-19

---

## Source Credibility Framework

| Tier | Description |
|------|-------------|
| **Tier 1** | Official Microsoft Learn documentation, REST API specs, official JSON role definitions |
| **Tier 2** | Official Microsoft blog posts with engineering authorship |
| **Tier 3** | Community forums, Stack Overflow |
| **Tier 4** | Personal blogs, unverified content |

All sources used in this research are **Tier 1** — official Microsoft Learn documentation.

---

## Sources Used

### S1 — Cost Management Reader Built-in Role Definition
- **URL:** https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/management-and-governance#cost-management-reader
- **Tier:** 1 (Official Microsoft RBAC documentation)
- **Currency:** Active page, built-in roles are versioned with Azure
- **What it provided:** Complete JSON definition of the Cost Management Reader role confirming `roleDefinitionId = 72fafb9e-0641-4937-9268-a91bfd8191a3`, full `actions` list including `Microsoft.Consumption/*/read` wildcard, and confirmation of zero Microsoft.Capacity permissions
- **Authority:** Microsoft official documentation, primary source (the actual role definition)
- **Bias:** None — this is Azure's own machine-readable role definition published as documentation

---

### S2 — Azure Contributor Built-in Role Definition (Privileged)
- **URL:** https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/privileged#contributor
- **Tier:** 1 (Official Microsoft RBAC documentation)
- **Currency:** Active page
- **What it provided:** Complete JSON definition of Contributor (`b24988ac-6180-42a0-ab88-20f7382dd24c`) showing `actions: ["*"]` and full NotActions list, confirming no Microsoft.Capacity or Microsoft.Consumption exclusions
- **Authority:** Microsoft official documentation, primary source
- **Bias:** None

---

### S3 — Reservations Reader Built-in Role Definition
- **URL:** https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/management-and-governance#reservations-reader
- **Tier:** 1 (Official Microsoft RBAC documentation)
- **Currency:** Active page
- **What it provided:** Confirmed Reservations Reader `roleDefinitionId = 582fc458-8989-419f-a480-75249bc5db7e`, `assignableScopes: ["/providers/Microsoft.Capacity"]`, actions `Microsoft.Capacity/*/read` + `Microsoft.Authorization/roleAssignments/read`
- **Authority:** Microsoft official documentation, primary source (the actual role definition)
- **Bias:** None

---

### S4 — Reservations Administrator Built-in Role Definition (Privileged)
- **URL:** https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles/privileged#reservations-administrator
- **Tier:** 1 (Official Microsoft RBAC documentation)
- **Currency:** Active page
- **What it provided:** Confirmed Reservations Administrator `roleDefinitionId = a8889054-8d42-49c9-bc1c-52486c10e7cd`, `assignableScopes: ["/providers/Microsoft.Capacity"]`, confirming that ALL reservation management roles are Capacity-scoped, not subscription-scoped
- **Authority:** Microsoft official documentation, primary source
- **Bias:** None

---

### S5 — Azure Consumption REST API: Reservations Summaries — List
- **URL:** https://learn.microsoft.com/en-us/rest/api/consumption/reservations-summaries/list?view=rest-consumption-2024-08-01
- **Tier:** 1 (Official Microsoft REST API documentation, API version 2024-08-01)
- **Currency:** API version 2024-08-01 — current latest
- **What it provided:** Full endpoint: `GET https://management.azure.com/{resourceScope}/providers/Microsoft.Consumption/reservationSummaries?api-version=2024-08-01&grain={grain}`; all URI parameters; security section (oauth2/user_impersonation only); examples showing billing account scope exclusively; confirmed no subscription-scope examples exist
- **Authority:** Official REST API specification — highest authority for API behavior
- **Bias:** None

---

### S6 — Azure Consumption REST API: Reservations Summaries Overview
- **URL:** https://learn.microsoft.com/en-us/rest/api/consumption/reservations-summaries?view=rest-consumption-2024-08-01
- **Tier:** 1 (Official Microsoft REST API documentation)
- **Currency:** API version 2024-08-01
- **What it provided:** Overview of all three Reservations Summaries operations (List, List By Reservation Order, List By Reservation Order And Reservation); confirmed three distinct scoping patterns
- **Authority:** Official REST API specification
- **Bias:** None

---

### S7 — APIs for Azure Reservation Automation
- **URL:** https://learn.microsoft.com/en-us/azure/cost-management-billing/reservations/reservation-apis
- **Tier:** 1 (Official Microsoft Cost Management documentation)
- **Currency:** Active Microsoft Learn page
- **What it provided:** Explicit statement: *"If you're an EA customer, you can programmatically view how the reservations... For other subscriptions, use the API Reservations Summaries - List By Reservation Order And Reservation."* — confirms billing account (EA) vs. reservation order scope distinction
- **Authority:** Microsoft official guidance, Cost Management product team documentation
- **Bias:** None

---

### S8 — Permissions to View and Manage Azure Reservations
- **URL:** https://learn.microsoft.com/en-us/azure/cost-management-billing/reservations/view-reservations
- **Tier:** 1 (Official Microsoft Cost Management documentation)
- **Currency:** Active Microsoft Learn page
- **What it provided:** Confirmed four Azure reservation RBAC roles exist; Reservations Reader scope definition: "read-only access to one or more reservations in their Microsoft Entra tenant (directory)"; confirmed view requires "Reservations Reader role or higher" at tenant scope vs "built-in reader roles or higher" at reservation scope
- **Authority:** Microsoft official documentation, product team
- **Bias:** None

---

### S9 — View Reservation Utilization After Purchase
- **URL:** https://learn.microsoft.com/en-us/azure/cost-management-billing/reservations/reservation-utilization
- **Tier:** 1 (Official Microsoft Cost Management documentation)
- **Currency:** Active Microsoft Learn page
- **What it provided:** Portal-side confirmation that viewing all reservations in a tenant requires "Reservation administrator or reader role"; confirmed role-based access model for portal vs API
- **Authority:** Microsoft official documentation
- **Bias:** None

---

### S10 — Azure Lighthouse: Cross-Tenant Management Experiences (Current Limitations)
- **URL:** https://learn.microsoft.com/en-us/azure/lighthouse/concepts/cross-tenant-management-experience#current-limitations
- **Tier:** 1 (Official Microsoft Lighthouse documentation)
- **Currency:** **Last updated 01/21/2026** — very current
- **What it provided:** Complete list of Lighthouse limitations including: ARM-only operations, no Owner/DataActions roles, no custom roles, IAM invisibility, national cloud restrictions. Confirmed Lighthouse only supports management.azure.com URIs and subscription/resource group delegation scopes
- **Authority:** Official Azure Lighthouse product documentation, highly authoritative
- **Bias:** None

---

### S11 — Azure Lighthouse in Enterprise Scenarios
- **URL:** https://learn.microsoft.com/en-us/azure/lighthouse/concepts/enterprise
- **Tier:** 1 (Official Microsoft Lighthouse documentation)
- **Currency:** Active Microsoft Learn page
- **What it provided:** Context on Lighthouse delegation model; confirmed cross-tenant subscription management scope
- **Authority:** Official Azure Lighthouse product documentation
- **Bias:** None

---

## Source Coverage by Question

| Question | Primary Source(s) | Cross-Referenced With |
|----------|------------------|-----------------------|
| Q1 — Cost Management Reader permissions | S1 | S5 (Consumption namespace) |
| Q2 — Contributor permissions | S2 | S1 (namespace comparison) |
| Q3 — Consumption API endpoint/scope | S5, S6, S7 | S8 (RBAC requirements) |
| Q4 — Lighthouse limitations | S10, S11 | S3, S4 (assignableScopes) |
| Q5 — Separate permissions | S1, S3, S5 | S8 (role comparison) |
| Q6 — Reservations Reader role | S3, S8 | S4 (Reservations Admin comparison) |

---

## Verification Notes

- All role definition IDs were verified against the JSON `"name"` field in the official documentation (not just role display name)
- The `assignableScopes` field for all four reservation roles was directly observed in the rendered JSON on Microsoft Learn
- The API endpoint URL was extracted using `browser_get_text` on the `<code>` element directly
- The Lighthouse limitations page last-updated date (01/21/2026) was directly observed at the bottom of the page
- No third-party sources were used — all findings are from Tier 1 primary sources only

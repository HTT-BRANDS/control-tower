# QA Audit Round 1: API Contract & Data Display

Date: 2026-06-08
Auditor: Richard (code-puppy)
Method: Manual template-to-schema comparison for all data pages

## Critical Finding: Frontend expects fields the API doesn't provide

### 1. COMPLIANCE (compliance.html) - FIXED
- `summary.total_policies` - API has `total_compliant_resources`, no `total_policies`
- `summary.compliant_count` - API has `total_compliant_resources`
- `summary.non_compliant_count` - API has `total_non_compliant_resources`
- **FIXED**: Updated JS to use correct field names, grouped non-compliant table by policy

### 2. RESOURCES (resources.html) - 2 BUGS
- **BUG R2.1**: Idle resource name column always shows "--"
  - Template: `r.resource_name || r.name`
  - Schema (IdleResource): has `resource_id` (string), `description` (string) - NEITHER `resource_name` NOR `name`
  - **FIX**: Use `r.resource_id` with fallback to `r.description`
- **BUG R2.2**: Tagging compliance score always shows "0%"
  - Template: `tagging.compliance_percentage`
  - Schema (TaggingCompliance): field is `compliance_percent` (not `compliance_percentage`)
  - **FIX**: Use `tagging.compliance_percent`

### 3. IDENTITY (identity.html) - 1 BUG
- **BUG I3.1**: Privileged users "Roles" column always shows "--"
  - Template: `(u.roles || []).join(', ')`
  - Schema (PrivilegedAccount): has `role_name` (singular string), NOT `roles` (array)
  - **FIX**: Use `u.role_name || '--'`
- Note: `email` field fallback for guests/privileged - schema has `user_principal_name` but no `email`. Fallback works (shows UPN).

### 4. COSTS (costs.html) - NO BUGS
- All field names match schema correctly
- `total_cost`, `tenant_count`, `subscription_count`, `cost_change_percent`, `top_services`, etc. all present

### 5. DASHBOARD - NO BUGS
- Server-side rendered (Jinja2) with schema objects passed directly
- `cost_summary.total_cost`, `tenant_count`, `cost_change_percent` - all match CostSummary
- `compliance_summary.average_compliance_percent`, `total_compliant_resources`, `total_non_compliant_resources` - all match ComplianceSummary
- `identity_summary.total_users`, `mfa_enabled_percent`, `privileged_users` - all match IdentitySummary
- `resource_inventory.total_resources` - matches ResourceInventory
- Extra fields (`daily_labels`, `tenant_names`) use `|default([], true)` fallbacks

### 6. OTHER PAGES - NO CLIENT-SIDE FETCH
- topology.html, admin.html, franchise-coach.html, sync-dashboard.html, design-system.html, privacy.html, riverside.html
- All server-side rendered or static; no API contract mismatch risk

## Summary
| Page | Bugs | Severity | Status |
|------|------|----------|--------|
| Costs | 0 | - | OK |
| Compliance | 2 | High | FIXED |
| Resources | 2 | Medium | FIXED |
| Identity | 1 | Low | FIXED |
| Dashboard | 0 | - | OK |
| Other | 0 | - | OK |

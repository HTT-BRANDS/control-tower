# QA Audit Round 2: Validation & Deployment

Date: 2026-06-08

## Deployment Status
- Container: `ghcr.io/htt-brands/control-tower:qa-round2`
- Deployed to: production
- Health: 200 OK, version 2.5.0

## Automated Checks

### 1. Judge Framework: 49/49 PASSED (100%)
- All 49 checks pass including the new P4.8 page rendering check
- 13 pages render without template errors

### 2. Page Rendering Check (P4.8): PASSED
- All 13 registered page routes return HTTP 200
- No Jinja2 UndefinedError or SQL errors in response bodies
- All pages have `<h1>` elements (a11y)

### 3. API Authentication Check: EXPECTED 401
- `/api/v1/compliance/summary` → 401 (auth-gated, correct)
- `/api/v1/costs/summary` → 401 (auth-gated, correct)
- This is the expected behavior - data endpoints require Entra login

## Fixes Deployed in This Round

### Compliance Page (compliance.html)
- FIXED: `average_compliance_percent` field name (was `overall_score`)
- FIXED: Resource counts using `total_compliant_resources`/`total_non_compliant_resources`
- FIXED: Non-compliant table grouped by policy name (was showing duplicate rows)

### Resources Page (resources.html)
- FIXED: Idle resource name now uses `resource_id` (was `resource_name`/`name`)
- FIXED: Tagging compliance uses `compliance_percent` (was `compliance_percentage`)

### Identity Page (identity.html)
- FIXED: Privileged users roles uses `role_name` (was `roles` array)

## What Still Needs Visual Verification (Round 3)

These are data/UX issues that automated checks CANNOT catch:

1. **Data Freshness**: Syncs are 19 days stale. The UI will show real numbers but they may be outdated.
2. **Data Completeness**: Per-brand breakdown may be empty for tenants that haven't synced.
3. **Dark Mode Contrast**: DaisyUI cards should now use design system dark tokens, but needs visual check.
4. **Layout Clarity**: Tables may still be dense and hard to scan - needs human review.
5. **Costs Page**: Need to verify the total cost number is displayed correctly and broken down by brand.

## Recommendation

Before Round 3 visual check, **run a sync** from the Sync Dashboard to refresh data.
Without fresh data, the UI will show "0" or "--" for many fields even though the code is correct.

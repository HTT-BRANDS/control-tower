# Browser smoke deterministic render contract

This document encodes the first-wave browser smoke contract from
`docs/plans/ci-browser-gate-and-prod-sync-plan-2026-04-24.md` into a
concrete set of routes, allowed data states, and stable semantic markers.

## Rules

- First-wave smoke is a render/shell gate, not a historical-data gate.
- First-wave smoke is not the authoritative RBAC gate; see `docs/testing/browser_rbac_matrix.md`.
- Seeded data is optional unless explicitly called out below.
- Deterministic empty-state rendering is healthy and must not fail smoke.
- Gated assertions must avoid scheduler-driven timestamps, counters, or other
  volatile historical values.
- Broken placeholders, 500 pages, traceback text, or missing semantic markers
  are failures.

## First-wave pages

| Route | Contract type | Stable markers | Notes |
|---|---|---|---|
| `/login` | unauthenticated shell | `login-shell`, `login-azure-entry` | Dev form may be hidden; Azure entry must render. |
| `/dashboard` | deterministic empty-state or seeded shell | `dashboard-shell`, `dashboard-kpi-summary`, `dashboard-overview-grid`, optional `dashboard-empty-state` | Empty welcome card is healthy when no synced data exists. |
| `/sync-dashboard` | shell + HTMX region contract | `sync-dashboard-shell`, `sync-status-region`, `sync-alerts-region`, `sync-history-region`, `tenant-sync-region` | Do not assert live counts or scheduler freshness in first-wave smoke. |
| `/riverside` | shell + HTMX region contract | `riverside-shell`, `riverside-executive-summary-region`, `riverside-mfa-region`, `riverside-maturity-region`, `riverside-requirements-region`, `riverside-alerts-region` | Assert shell and region presence only; async payloads are tested separately. |
| `/dmarc` | shell + async container contract | `dmarc-shell`, `dmarc-alert-banner`, `dmarc-tenant-scores` | Rendered shell is the gate; fetched summary values are not first-wave hard requirements. |

## First-wave partials

| Partial | Contract type | Stable markers | Healthy empty-state markers |
|---|---|---|---|
| `/partials/sync-status-card` | seeded or healthy-empty fragment | `sync-status-card` | `sync-status-empty-healthy` |
| `/partials/sync-history-table` | seeded or healthy-empty fragment | `sync-history-table`, `sync-history-table-grid` | `sync-history-empty-state` |
| `/partials/active-alerts` | seeded or healthy-empty fragment | `active-alerts-panel` | `active-alerts-empty-state` |
| `/partials/tenant-sync-status` | seeded or healthy-empty fragment | `tenant-sync-grid` | `tenant-sync-empty-state` |

## Explicit non-goals for first-wave smoke

The following are intentionally **not** hard-gated in first-wave smoke:

- scheduler-dependent timestamps or freshness windows
- volatile alert counts
- historical trend values
- per-tenant seeded record counts
- exact async API payload contents for Riverside/DMARC dashboard widgets

Those belong in narrower API/unit tests or later seeded-browser coverage, not in
this minimum viable smoke gate.

## RBAC boundary

Render smoke intentionally does **not** prove role enforcement for admin-facing
operations. The lightweight first-wave authorization matrix lives in
`docs/testing/browser_rbac_matrix.md`, and the initial negative authorization
check is the dedicated Riverside sync deny-path coverage in
`tests/integration/test_riverside_api.py`.

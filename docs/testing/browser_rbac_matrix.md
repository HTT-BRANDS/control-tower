# First-wave browser route RBAC matrix

This document defines the lightweight authorization matrix for the
first-wave browser-gated routes and partials introduced by the browser smoke
rollout.

## Scope boundary

- **Browser smoke** remains a deterministic render/shell gate.
- **RBAC coverage** is tracked separately so authorization is explicit, not
  implied by successful admin rendering.
- Initial negative authorization coverage is implemented at the API/integration
  level for the Riverside manual sync action.

## Role legend

- `admin`: full access
- `operator`: operational actions allowed
- `reader`: authenticated read-only access where supported
- `unauthenticated`: redirected or denied

## Matrix

| Route / partial | Surface type | Intended access | Initial coverage |
|---|---|---|---|
| `/login` | page | unauthenticated | browser smoke render contract |
| `/dashboard` | page | authenticated (`reader`/`operator`/`admin`) | browser smoke render contract |
| `/sync-dashboard` | page | authenticated (`reader`/`operator`/`admin`) | browser smoke render contract |
| `/riverside` | page | authenticated (`reader`/`operator`/`admin`) | browser smoke render contract |
| `/dmarc` | page | authenticated (`reader`/`operator`/`admin`) | browser smoke render contract |
| `/partials/sync-status-card` | partial | authenticated (`reader`/`operator`/`admin`) | browser smoke fragment contract |
| `/partials/sync-history-table` | partial | authenticated (`reader`/`operator`/`admin`) | browser smoke fragment contract |
| `/partials/active-alerts` | partial | authenticated (`reader`/`operator`/`admin`) | browser smoke fragment contract |
| `/partials/tenant-sync-status` | partial | authenticated (`reader`/`operator`/`admin`) | browser smoke fragment contract |
| `/api/v1/riverside/sync` | admin-facing action | `operator` or `admin` only | integration RBAC negative check for `reader` |

## Explicit policy

- Passing browser smoke **does not** imply admin authorization is correct.
- First-wave smoke intentionally checks rendering, semantic markers, and basic
  shell health only.
- RBAC assertions belong in dedicated authz tests like
  `tests/integration/test_riverside_api.py::TestRiversideSyncEndpoint`.

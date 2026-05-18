# Local-First Stabilization Plan

> Owner: Tyler + Richard (`code-puppy-1c7422`)  
> Created: 2026-05-17  
> Purpose: stop treating staging/production as the first place we discover local app, data-fetching, and design-system failures.

## Executive level-set

The current repo has strong automated coverage in some layers, but local confidence is uneven:

| Area | Current evidence | Status |
|---|---|---|
| Unit tests | `uv run pytest tests/unit -q --tb=short` passed 3,656 tests on 2026-05-17 | ✅ Strong |
| Integration tests | `uv run pytest tests/integration -q --tb=short` passed 403 tests on 2026-05-17 | ✅ Strong |
| Focused browser smoke | `ENVIRONMENT=development DATABASE_URL=sqlite:///./data/local-dev.db uv run pytest tests/e2e/test_browser_smoke.py tests/e2e/test_accessibility_e2e.py tests/e2e/test_seeded_data_flows.py -q --tb=short` passed 26 tests on 2026-05-17 | ✅ Shell + seeded data coverage |
| App import/OpenAPI | `ENVIRONMENT=test E2E_HARNESS=true BROWSER_TEST_DISABLE_SCHEDULERS=true uv run python ...` imported app and generated OpenAPI; 207 routes | ✅ Healthy |
| Design-token unit checks | 119 targeted design/theme tests passed on 2026-05-17 | ✅ Token logic covered |
| Accessibility E2E | Initially failed 3 stale static asset checks; updated to current CSS stack and `uv run pytest tests/e2e/test_accessibility_e2e.py tests/e2e/test_axe_accessibility.py -q --tb=short` now passes 9, skips 17 axe/browser-optional checks | ✅ Basic accessibility asset contract healthy |
| Design-system visual quality | P0 audit items remediated/guarded on 2026-05-17: invisible text, dead text class, focus-visible token conflicts, ghost focus token, focus:outline-none, btn-brand outline, text-muted contrast, and JS hardcoded blue fallback. Broader browser-level visual assertions remain. | ⚠️ P0 healthy; UX depth pending |
| Local seeded data/fetching | `make local-reset-seed-smoke` uses dedicated SQLite `data/local-dev.db`; data smoke passed 27/27 checks across tenants, costs, compliance, resources, identity, sync, recommendations, DMARC, Riverside, and authz. Integrated into `make local-gate`. | ✅ Seed contract healthy |
| Local one-command gate | `make doctor`, `make local-fast-gate`, and `make local-gate` added on 2026-05-17. `make local-gate` passed in ~195s with doctor, ruff, format-check, unit, integration, browser smoke, accessibility E2E, and axe skip accounting. | ✅ Foundation healthy |

## What is healthy enough to trust today

These claims are backed by current local commands:

1. `make doctor` validates local prerequisites without Azure credentials.
2. The backend imports in the browser-test harness.
3. OpenAPI generation works.
4. Unit test suite is broad and passing.
5. Integration suite is broad and passing.
6. First-wave browser smoke for login, dashboard, sync dashboard, Riverside, DMARC, and key partials passes.
7. Basic accessibility/static-asset E2E passes against the current CSS stack.
8. `make local-gate` now provides a repeatable local pre-staging command surface.
9. Staging OIDC remediation was validated separately in release-gate evidence.

## What is *not* healthy enough to trust today

1. Browser-level design/UX assertions are still shallow even though P0 static design-system failures are now guarded.
2. Existing UAT reports are historical and conflict with current design audit reality.
3. Browser-level seeded data coverage exists for critical surfaces, but deeper product-specific click journeys still need expansion.

## Local gate target

Before any new staging/production deployment intended to validate application behavior, the following command should exist and pass:

```bash
make local-gate
```

Implemented command surface:

```bash
make doctor
make local-fast-gate
make local-gate
```

Current `make local-gate` sequence:

```bash
make doctor
uv run ruff check app tests scripts
uv run ruff format --check app tests scripts
# unit + integration run in parallel to keep the gate usable locally
uv run pytest tests/unit -q --tb=short
uv run pytest tests/integration -q --tb=short
make local-reset-seed-smoke
ENVIRONMENT=development DATABASE_URL=sqlite:///./data/local-dev.db uv run pytest tests/e2e/test_browser_smoke.py tests/e2e/test_accessibility_e2e.py tests/e2e/test_seeded_data_flows.py -q --tb=short
ENVIRONMENT=development DATABASE_URL=sqlite:///./data/local-dev.db uv run pytest tests/e2e/test_axe_accessibility.py -q --tb=short
```

`make local-gate` now includes `make local-reset-seed-smoke`, which resets/seeds/validates a dedicated local SQLite database before browser data-flow tests run. Staging should not proceed with open P0 failures or unwaived P1 failures.

## Validation layers

| Layer | Purpose | Current status | Needed action |
|---|---|---|---|
| Doctor | Prove the machine can run the app | Healthy | `scripts/doctor.py` + `make doctor` pass without Azure credentials |
| Static quality | Ruff/format/import sanity | Healthy | Included in `make local-gate` for `app`, `tests`, and `scripts` |
| Unit | Service/model/schema behavior | Strong | Keep green |
| Integration | FastAPI routes/templates/db fixtures | Strong | Keep green and map by domain |
| Contract | Page/API response shape stability | Improved | Seeded browser flows assert same-origin API fetches return non-empty rendered UI |
| Local data smoke | Seeded data exists for API/UI fetch surfaces | Healthy | `make local-reset-seed-smoke` passes 27/27 DB contract checks |
| Browser smoke | Critical human flows render | Seeded critical surfaces pass | Expand deeper click journeys around Tyler pain points |
| Accessibility | Keyboard/focus/a11y static assets | Basic healthy | Stale CSS asset checks fixed; axe file currently records 17 expected skips |
| Design system | Tokenized UI, contrast, focus, visual consistency | P0 static guardrails healthy | Add Playwright visual/UX fixture coverage for remaining depth |
| Staging smoke | Validate deployment environment | Exists | Only after local gate |

## Critical product surfaces to inventory

Each surface needs unit, integration, local data smoke, and browser coverage where user-facing:

- Auth/login/dev harness
- Dashboard
- Sync dashboard and partials
- Costs
- Compliance
- Resources
- Identity
- Riverside
- DMARC
- Preflight
- Health/OpenAPI/docs
- Design system shell/components

## Acceptance criteria: local healthy enough for staging

- [x] `make doctor` passes.
- [x] local DB reset/seed flow exists and creates meaningful HTT/BCC/FN/TLL/DCE demo data.
- [ ] app starts locally with one documented command.
- [ ] `/health`, `/health/detailed`, `/openapi.json`, and `/docs` work locally.
- [x] dashboard/cost/compliance/resource/identity/Riverside/DMARC/sync pages render with seeded or controlled empty states.
- [x] no critical page shows raw traceback, `None`, `undefined`, template error, or broken partial in seeded browser smoke.
- [ ] browser smoke covers Tyler's real click path.
- [ ] accessibility E2E passes or failures have explicit waiver beads.
- [x] design-system P0s from `DESIGN_SYSTEM_AUDIT.md` are fixed or tracked as staging blockers.
- [ ] every P0/P1 gap has a bd issue with repro command and close evidence.

## Supporting docs

- [Local data contract](./local-data-contract.md)
- [Surface health matrix](./surface-health-matrix.md)
- [Test coverage map](./test-coverage-map.md)

## Current known gaps filed from this level-set

See bd parent `ct-9bh`.

1. `ct-98s` — local doctor/local gate ✅ complete
2. `ct-dag` — seeded local data and fetch contracts ✅ complete
3. `ct-80e` — local surface inventory and health matrix ✅ complete
4. `ct-ba1` — design-system P0 remediation ✅ complete
5. `ct-1aq` — Playwright flows for Tyler's real data-fetching UX ✅ complete
6. `ct-cf2` — test coverage map by product surface ✅ complete

## Progress log

### 2026-05-17 — Local gate foundation

- Added `scripts/doctor.py`.
- Added `make doctor`, `make local-fast-gate`, and `make local-gate`.
- Fixed pre-existing Makefile parser issues in `db-stats`, `shell`, `docs`, and `env-check` recipes so Make targets are runnable.
- Validated `make doctor`: 9 pass, 0 warn, 0 fail.
- Validated `make local-fast-gate`: ruff/format/browser smoke/accessibility E2E passed.
- Validated `make local-gate`: doctor, ruff, format-check, unit, integration, browser smoke, accessibility E2E, and axe skip accounting passed in ~195s.

### 2026-05-17 — Local data contract

- Added dedicated local DB targets: `make local-db-reset`, `make local-seed`, `make local-data-smoke`, `make local-reset-seed-smoke`.
- Added `scripts/local_data_smoke.py` with SQLite safety guard and 27 minimum row-count checks.
- Added `docs/local-stabilization/local-data-contract.md`.
- Integrated local reset/seed/smoke into `make local-gate`.
- Validated `make local-reset-seed-smoke`: 27 pass, 0 fail.
- Validated `make local-gate`: full gate passed in ~201s, including seeded data smoke.
- Next true task: `ct-80e` — product surface inventory and health matrix.

### 2026-05-17 — Surface health matrix

- Added `docs/local-stabilization/surface-health-matrix.md` from live route/template inventory.
- Mapped critical surfaces to routes, templates/partials, API/data dependencies, seed status, test coverage, local status, and gap beads.
- Current risk shifted from P0 local boot/data to P1 design-system visual quality and seeded browser assertions.
- Next true tasks: `ct-ba1` design-system P0 remediation, then `ct-1aq` Playwright seeded data-fetching flows.

### 2026-05-17 — Design-system P0 remediation

- Updated current focus-visible CSS to use `var(--brand-primary, #500711)` directly instead of ghost `--border-focus` indirection.
- Removed hardcoded Walmart-blue behavior fallback from navigation progress bar source and bundle.
- Added JS guardrails for `focus:outline-none` and hardcoded `#0053e2` source regressions.
- Added CSS guardrail against ghost focus token usage.
- Updated `DESIGN_SYSTEM_AUDIT.md` with current P0 remediation status.
- Validated targeted design/accessibility suite: 133 passed.
- Next true task: `ct-1aq` — Playwright seeded data-fetching and UX flows.

### 2026-05-17 — Seeded browser data-flow validation

- Added `tests/e2e/test_seeded_data_flows.py` to prove seeded local data renders in browser for costs, compliance, resources, identity, sync, Riverside, and DMARC.
- Moved full `make local-gate` ordering so the local DB is reset/seeded before seeded browser assertions run.
- Fixed tenant isolation for FK-backed product tables by adding `TenantAuthorization.accessible_tenant_primary_keys` / `filter_tenant_primary_keys` and using them in costs, compliance, identity, and resources routes.
- Fixed `/api/v1/resources/orphaned` 500 caused by offset-naive vs offset-aware datetime subtraction.
- Fixed compliance page JS to read `overall_compliance_percent` instead of nonexistent `score`.
- Validation: local data smoke passed, seeded browser suite passed, design P0 guardrails passed.
- Next true task: `ct-cf2` — final surface coverage map.

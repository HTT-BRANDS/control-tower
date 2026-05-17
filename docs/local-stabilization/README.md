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
| Focused browser smoke | `uv run pytest tests/e2e/test_browser_smoke.py -q --tb=short` passed 10 tests on 2026-05-17 | ✅ Basic shell coverage |
| App import/OpenAPI | `ENVIRONMENT=test E2E_HARNESS=true BROWSER_TEST_DISABLE_SCHEDULERS=true uv run python ...` imported app and generated OpenAPI; 207 routes | ✅ Healthy |
| Design-token unit checks | 119 targeted design/theme tests passed on 2026-05-17 | ✅ Token logic covered |
| Accessibility E2E | Initially failed 3 stale static asset checks; updated to current CSS stack and `uv run pytest tests/e2e/test_accessibility_e2e.py tests/e2e/test_axe_accessibility.py -q --tb=short` now passes 9, skips 17 axe/browser-optional checks | ✅ Basic accessibility asset contract healthy |
| Design-system visual quality | `DESIGN_SYSTEM_AUDIT.md` reports invisible text, focus conflicts, raw Tailwind palette drift, and contrast failures | 🔴 Not trusted |
| Local seeded data/fetching | No single local reset/seed contract was validated in this pass | ⚪ Unknown |
| Local one-command gate | No `make local-gate` / `make doctor` exists today | 🔴 Missing |

## What is healthy enough to trust today

These claims are backed by current local commands:

1. The backend imports in the browser-test harness.
2. OpenAPI generation works.
3. Unit test suite is broad and passing.
4. Integration suite is broad and passing.
5. First-wave browser smoke for login, dashboard, sync dashboard, Riverside, DMARC, and key partials passes.
6. Staging OIDC remediation was validated separately in release-gate evidence.

## What is *not* healthy enough to trust today

1. The app does not have a documented one-command local health gate.
2. Local seeded/demo data is not defined as a contract.
3. The design system has documented violations that are not currently blocked by tests.
4. Existing UAT reports are historical and conflict with current design audit reality.
6. Data fetching is not mapped end-to-end from page → route → service → local fixture/seed → test.

## Local gate target

Before any new staging/production deployment intended to validate application behavior, the following command should exist and pass:

```bash
make local-gate
```

Target sequence:

```bash
make doctor
make lint
make format-check
uv run pytest tests/unit -q --tb=short
uv run pytest tests/integration -q --tb=short
uv run pytest tests/e2e/test_browser_smoke.py -q --tb=short
uv run pytest tests/e2e/test_accessibility_e2e.py tests/e2e/test_axe_accessibility.py -q --tb=short
make design-system-check
make local-data-smoke
```

The full gate can be split into `local-fast-gate` and `local-full-gate`, but staging should not proceed with open P0 failures or unwaived P1 failures.

## Validation layers

| Layer | Purpose | Current status | Needed action |
|---|---|---|---|
| Doctor | Prove the machine can run the app | Missing | Add `scripts/doctor.py` + `make doctor` |
| Static quality | Ruff/format/import sanity | Exists | Include in local gate |
| Unit | Service/model/schema behavior | Strong | Keep green |
| Integration | FastAPI routes/templates/db fixtures | Strong | Keep green and map by domain |
| Contract | Page/API response shape stability | Partial | Add explicit dashboard/data contracts |
| Local data smoke | Seeded data appears in UI/API | Missing | Add reset/seed/data smoke |
| Browser smoke | Critical human flows render | Basic exists | Expand around Tyler pain points |
| Accessibility | Keyboard/focus/a11y static assets | Broken/stale | Fix current failing asset checks |
| Design system | Tokenized UI, contrast, focus, visual consistency | Audit exists, gate missing | Add static checker + Playwright fixture/gallery |
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

- [ ] `make doctor` passes.
- [ ] local DB reset/seed flow exists and creates meaningful HTT/BCC/FN/TLL/DCE demo data.
- [ ] app starts locally with one documented command.
- [ ] `/health`, `/health/detailed`, `/openapi.json`, and `/docs` work locally.
- [ ] dashboard/cost/compliance/resource/identity/Riverside/DMARC/sync pages render with seeded or controlled empty states.
- [ ] no critical page shows raw traceback, `None`, `undefined`, template error, or broken partial.
- [ ] browser smoke covers Tyler's real click path.
- [ ] accessibility E2E passes or failures have explicit waiver beads.
- [ ] design-system P0s from `DESIGN_SYSTEM_AUDIT.md` are fixed or tracked as staging blockers.
- [ ] every P0/P1 gap has a bd issue with repro command and close evidence.

## Current known gaps filed from this level-set

See bd parent `ct-local` once created in this session. Child beads should cover:

1. local doctor/local gate
2. seeded local data and fetch contracts
3. local surface inventory and health matrix
4. design-system P0 remediation
5. Playwright flows for Tyler's real data-fetching UX
6. test coverage map by product surface

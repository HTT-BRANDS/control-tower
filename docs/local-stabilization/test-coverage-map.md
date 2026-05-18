# Test Coverage Map by Product Surface

> Owner: Richard (`code-puppy-1c7422`)  
> Bead: `ct-cf2`  
> Updated: 2026-05-17  
> Evidence baseline: `make local-gate` passed after seeded local DB reset/seed.

## Gate evidence

`make local-gate` currently proves:

- Doctor: 9 pass, 0 warn, 0 fail.
- Static quality: `ruff check app tests scripts` and `ruff format --check app tests scripts` pass.
- Unit: 3,659 passed.
- Integration: 403 passed.
- Local data smoke: 27/27 seeded data checks passed.
- Browser/accessibility/seeded E2E: 26 passed.
- Axe accessibility file: 17 expected skips.

## Coverage legend

| Mark | Meaning |
|---|---|
| ✅ | Covered in the current local gate or targeted suite. |
| ⚠️ | Partial coverage; acceptable for staging only if tracked. |
| ⏭️ | Deferred/non-P0 local surface. |
| N/A | Not applicable to the surface. |

## Required validation layers

P0/P1 user-facing surfaces require one of each relevant layer:

1. Unit/service behavior.
2. Integration route/API/template behavior.
3. Seed/data contract, unless intentionally cloud/config dependent.
4. Browser rendering/UX smoke for human-facing pages.
5. Accessibility/static-asset guardrail for pages in the shell.
6. Design-system guardrail for visual/token/focus regressions.

Unknown coverage is a gap. We do not do “probably fine” here; that’s how goblins get tenure.

## Surface map

| Surface | Unit | Integration | Contract/API | Local data smoke | Browser/Playwright | Accessibility | Design-system | Status | Gap / waiver |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| Auth/login/dev harness | ✅ | ✅ | ✅ | ✅ UserTenant mapping | ✅ login smoke | ✅ shell assets | ✅ focus/token guards | ✅ Healthy | Deeper Microsoft/Azure auth is staging/prod concern. |
| Dashboard | ✅ | ✅ | ✅ | ✅ cost/compliance/resource/identity/sync rows | ✅ shell smoke | ✅ shell assets | ✅ token/focus guards | ✅ Healthy basic | Full dashboard click/filter journey deferred to future UX depth. |
| Sync dashboard + partials | ✅ | ✅ | ✅ partial routes | ✅ SyncJob/Log/Metrics/Alert | ✅ shell + seeded partial render | ✅ shell assets | ✅ token/focus guards | ✅ Healthy basic | Loading/error-state interactions deferred. |
| Costs | ✅ | ✅ | ✅ `/api/v1/costs/*` | ✅ CostSnapshot/CostAnomaly | ✅ seeded browser fetch/render | ✅ shell assets | ✅ token/focus guards | ✅ Healthy basic | Budgets/recommendations journeys deferred. |
| Compliance | ✅ | ✅ | ✅ `/api/v1/compliance/*` | ✅ ComplianceSnapshot/PolicyState | ✅ seeded browser fetch/render | ✅ shell assets | ✅ token/focus guards | ✅ Healthy basic | Framework/rule drilldowns deferred. |
| Resources | ✅ | ✅ | ✅ `/api/v1/resources/*` | ✅ Resource/Tag/IdleResource | ✅ seeded browser fetch/render | ✅ shell assets | ✅ token/focus guards | ✅ Healthy basic | Provisioning/recommendation flows deferred. |
| Identity | ✅ | ✅ | ✅ `/api/v1/identity/*` | ✅ IdentitySnapshot/PrivilegedUser | ✅ seeded browser fetch/render | ✅ shell assets | ✅ token/focus guards | ✅ Healthy basic | License/admin-role UI depth deferred. |
| Riverside | ✅ | ✅ | ✅ `/api/v1/riverside/*` | ✅ Riverside compliance/MFA/devices/threats/requirements | ✅ shell + seeded API render | ✅ shell assets | ✅ token/focus guards | ✅ Healthy basic | Full per-widget interaction depth deferred. |
| DMARC | ✅ | ✅ | ✅ `/api/v1/dmarc/*` | ✅ DMARC/DKIM/report/alert rows | ✅ shell + seeded API render | ✅ shell assets | ✅ token/focus guards | ✅ Healthy basic | Alert acknowledge/sync interactions deferred. |
| Preflight | ✅ | ✅ | ✅ API route coverage | N/A cloud/config dependent | ⚠️ page exists but not first-wave browser path | ✅ shell assets when rendered | ✅ token/focus guards | ⚠️ Tracked | Local empty-state/browser depth deferred; non-blocking P2. |
| Health/OpenAPI/docs | ✅ | ✅ | ✅ doctor/OpenAPI | N/A | ✅ doctor import/OpenAPI | N/A | N/A | ✅ Healthy | None. |
| Search | ✅ | ✅ | ✅ API route coverage | ⚠️ indirectly seed-backed | ⚠️ browser UX not first-wave | ✅ shell assets if component rendered | ✅ token/focus guards | ⚠️ Tracked | Non-blocking P2 browser search UX. |
| Admin/audit/privacy | ✅ | ✅ | ✅ route coverage | ⚠️ admin data partially fixture-backed | ⚠️ not first-wave browser path | ✅ shell/privacy assets | ✅ token/focus guards | ⚠️ Tracked | Non-blocking P2 browser admin/audit UX. |
| Design system shell/components | ✅ | ✅ theme rendering | ✅ static asset contract | N/A | ⚠️ browser visual assertions partial | ✅ accessibility asset E2E | ✅ P0 static guardrails | ⚠️ Tracked | P0 fixed; visual regression depth deferred. |
| Topology/threats/exports | ✅ varies by service | ✅ route/service coverage varies | ⚠️ API coverage varies | ⏭️ not first-wave seed contract | ⏭️ deferred | ✅ shell assets when rendered | ✅ token/focus guards | ⏭️ Deferred | Non-P0 local stabilization scope. |

## Current remediation map

### Closed during this validation pass

| Bead | Result |
|---|---|
| `ct-ba1` | Design-system P0 audit failures remediated/guarded and pushed. |
| `ct-1aq` | Seeded browser data-flow validation added; tenant-scope/API/UI defects remediated and pushed. |

### Remaining tracked exceptions

No open P0/P1 local stabilization child remains under `ct-9bh` after this map. Remaining depth is P2/non-blocking and documented here:

| Area | Risk | Disposition |
|---|---|---|
| Axe accessibility test file | 17 expected skips | Existing behavior; local gate accounts for skips. Convert to active axe checks in a future accessibility hardening pass. |
| Preflight browser page | Cloud/config-dependent empty-state behavior not exhaustively asserted | Non-blocking P2; API/local route coverage exists. |
| Search/admin/audit browser UX | Not first-wave Tyler data-fetching path | Non-blocking P2; unit/integration coverage exists. |
| Visual regression depth | Design P0 static issues fixed, but screenshot/visual parity not full release quality | Non-blocking P2; `tests/e2e/baselines/README.md` and visual parity scaffolding exist. |

## Why the Obsidian-agent work needed remediation

The earlier validation stack proved DB seed counts and shell rendering, but it did not prove page → browser fetch → route → service → rendered data. The new seeded browser tests exposed real defects:

1. Cost/compliance/resource/identity pages returned successful API responses but rendered empty UI because FK-backed tables used internal `tenants.id` while route isolation compared against Azure tenant IDs.
2. `/api/v1/resources/orphaned` returned 500 due to offset-naive vs offset-aware datetime subtraction.
3. Compliance UI expected a nonexistent `score` field instead of `overall_compliance_percent`.

Those are now fixed and covered by local gate. This is the remediation pattern going forward: **DB row-count smoke is necessary, but browser-rendered seeded proof is the validation that matters for Tyler's UX.**

## Recommended staging decision

Local stabilization is healthy enough to proceed to staging validation if:

1. `git status` is clean and branch is pushed.
2. `make local-gate` passes on the machine doing release prep.
3. Any staging-only failures are filed as separate beads with logs and route/user impact.

Do not use staging to rediscover local data-fetching bugs. That goblin has been evicted.

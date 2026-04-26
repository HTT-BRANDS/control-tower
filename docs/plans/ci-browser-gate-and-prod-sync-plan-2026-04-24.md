# Implementation Plan — Prod Sync Investigation + Browser Gate Hardening

**Author:** Richard (`code-puppy-824f08`)
**Date:** 2026-04-24
**Status:** Executed in part; updated 2026-04-26 with production evidence and current QA blocker state

---

## Goals

1. **Resolve production sync ambiguity** by reconciling deployed auth mode, tenant config, and observed fallback behavior.
2. **Close the UI-quality gap in CI** by promoting existing browser tests into meaningful release gates.
3. **Stabilize app-backed browser tests** by disabling background schedulers during browser-test startup only.

---

## Status update (2026-04-26)

### What is now known
- Production is **not** currently in OIDC mode; the read-only evidence pass confirmed **secret Key Vault mode** with `USE_OIDC_FEDERATION=false`.
- Production App Service is still running image `ghcr.io/htt-brands/azure-governance-platform:6a7306a`, which predates commit `5647fab` (`fix: skip unconfigured tenants in scheduled sync`).
- The five noisy tenants from `918b` are now classified as scheduler-ineligible under current repo logic because they lack `client_secret_ref` in secret mode.
- Fresh production workflow run `24961635696` on current `main` failed in QA before deploy, so prod never received the newer image.
- Immediate unblock for the next session is therefore: fix the four QA test regressions, rerun deploy, then perform the post-deploy verification pass.

## Problem Summary

### A. Production sync inconsistency
Observed production behavior showed repeated tenant auth fallback messages involving Key Vault and shared settings credentials. That ambiguity has now been narrowed substantially: production is in **secret Key Vault mode**, the five impacted tenants are ineligible under current repo logic, and the live app is still running a **stale pre-fix image**.

So the dominant current hypothesis is no longer generic auth ambiguity; it is **stale deployment truth**. The remaining production task is to land a post-`5647fab` image and then verify the observed fallback noise actually burns down.

### B. CI blind spot for real UI behavior
Current CI/deploy gates strongly validate linting, unit/integration behavior, auth walls, health endpoints, and supply-chain integrity. They do **not** meaningfully validate rendered application pages in a browser before promotion.

### C. Browser test startup instability
App-backed E2E tests currently start the full FastAPI lifespan, which launches APScheduler and Riverside schedulers. This violates test isolation and can create flaky, slow, and noisy browser tests.

---

## Scope

### In scope
- Produce a production sync investigation runbook and evidence-to-decision workflow.
- Add a browser-test-only switch to disable scheduler startup during app-backed browser tests.
- Define and wire a **minimum viable browser smoke gate** into CI.
- Tighten selected browser tests so they fail on meaningful regressions.
- Define second-wave follow-up for accessibility and visual regression gates.
- Define a concrete follow-up task for authorization/RBAC browser coverage.

### Out of scope for first execution wave
- Full visual regression rollout across all pages and themes.
- Comprehensive redesign of the entire E2E architecture.
- Broad tenant-auth redesign across all environments.
- Production remediation that requires secret rotation or tenant-side admin consent before evidence is collected.
- Full production IdP/browser parity in PR CI; first-wave smoke remains a **code-level gate**.

---

## Non-Functional Constraints

- **No secrets may be retrieved, copied, or stored** during prod investigation.
- **Browser-smoke runtime target:** p95 under **7 minutes** wall-clock in CI.
- **Retry policy:** none for hard-gated browser smoke tests; flakes must be fixed, not hidden.
- **Artifacts:** upload on failure only; screenshots/console traces retained briefly and access-restricted.
- **Auth material in artifacts is prohibited:** no cookies, auth headers, storage-state dumps, or raw token-bearing traces.
- **Health semantics:** test-disabled schedulers must be distinguishable from genuine degraded scheduler failure.
- **Initial rollout quality target:** fewer than **5% non-actionable failures** across soak runs before promotion to required gate.

---

## Workstream 1 — Production Sync Investigation (Read-Only Evidence)

### Objective
Confirm the already-established production mode/image facts, preserve the evidence trail, and drive the remaining gap to closure: deploy a post-fix image and verify sync recovery against fresh production evidence.

### Deliverables
1. **Runbook/checklist** for prod verification.
2. Evidence table covering:
   - deployed App Service auth/runtime settings
   - deployed image/digest/version
   - noisy tenant DB rows
   - YAML tenant config mapping
   - Key Vault secret existence metadata only, if secret mode is expected
   - credential-branch evidence from logs
3. Decision memo: one of
   - runtime drift confirmed
   - tenant data drift confirmed
   - code-path mismatch confirmed
   - insufficient Azure visibility / escalation required
4. Follow-up issue(s) for remediation if needed.

### Secure evidence-handling rules
- Use **read-only** access for Azure, App Service, DB, and Key Vault inspection.
- Never retrieve secret values.
- Record only existence/metadata, never secret contents.
- Redact tenant IDs and sensitive app settings outside the incident thread.
- Do not paste raw portal screenshots or full config dumps into broad-access docs.
- Evidence should live in an approved restricted location or tightly scoped issue context.

### Evidence-to-decision matrix

| Signal | Source | Expected in UAMI mode | Expected in OIDC mode | Expected in secret mode | Interpretation if mismatched | Next action |
|---|---|---|---|---|---|---|
| `USE_UAMI_AUTH` | App Service settings | `true` | `false` | `false` | Runtime mode drift | inspect deployment settings provenance |
| `USE_OIDC_FEDERATION` | App Service settings | may be `true`, but UAMI still wins | `true` | `false` | mode ambiguity / drift | resolve precedence expectations |
| `OIDC_ALLOW_DEV_FALLBACK` | App Service settings | `false` | `false` | n/a | **Critical misconfig** if true in prod | file prod fix immediately |
| `KEY_VAULT_URL` | App Service settings | optional | optional | expected | secret-mode assumptions wrong | inspect actual credential path |
| `AZURE_MANAGED_IDENTITY_CLIENT_ID` / `UAMI_CLIENT_ID` | App Service settings | present as required | MI client ID may be present | not relevant to secret path | missing identity config | inspect auth bootstrap |
| image digest / version | App Service / deploy logs | matches intended deploy | matches intended deploy | matches intended deploy | stale image / old code path | verify deploy provenance |
| noisy tenant `use_oidc`, `use_lighthouse`, `client_id`, `client_secret_ref` | prod DB | app IDs resolvable; secret refs not primary path | app IDs resolvable | secret refs / lighthouse semantics matter | tenant data drift | compare to YAML + expected auth model |
| tenant app ID resolution | YAML + DB | resolvable | resolvable | optional unless custom secret path | auth-mode mismatch or stale records | correct config source of truth |
| credential branch log evidence | App Insights / app logs | UAMI branch observed | OIDC branch observed | secret branch observed | runtime not behaving as expected | investigate code/build mismatch |
| Key Vault secret existence metadata | Key Vault metadata only | usually irrelevant | usually irrelevant | should exist for intended tenants | secret path incomplete | remediate tenant secret setup |

### Implementation steps
1. Inspect deployed App Service application settings:
   - `USE_UAMI_AUTH`
   - `USE_OIDC_FEDERATION`
   - `OIDC_ALLOW_DEV_FALLBACK`
   - `KEY_VAULT_URL`
   - `AZURE_MANAGED_IDENTITY_CLIENT_ID`
   - `UAMI_CLIENT_ID`
2. Inspect deployed image/version/digest and correlate with expected main commit.
3. Inspect App Service startup command / container entrypoint overrides if any.
4. Query production `tenants` rows for the noisy tenant IDs from bd `918b`:
   - `is_active`
   - `use_lighthouse`
   - `use_oidc`
   - `client_id`
   - `client_secret_ref`
5. Compare those tenant IDs against `config/tenants.yaml` expectations.
6. Capture log evidence showing the actual credential branch invoked (UAMI, OIDC, or secret path), not just inferred settings.
7. If secret mode is active, verify Key Vault secret existence metadata only.
8. Produce decision memo and remediation issue(s).

### Exit criteria
- We can explain **why** the observed fallback messages occur.
- We can show production is off stale image `6a7306a`.
- A post-deploy verification pass confirms whether the fallback noise and alert load actually burn down.
- A follow-up execution ticket exists if remediation is still non-trivial after the real deploy lands.

---

## Workstream 2 — Browser-Test Scheduler Isolation

### Objective
Prevent app-backed E2E/browser tests from launching background jobs during FastAPI lifespan startup.

### Proposed design
Introduce an internal settings flag `disable_background_schedulers` backed by a **browser-test-only env alias**:
- **Env var:** `BROWSER_TEST_DISABLE_SCHEDULERS=true`
- **Allowlisted hard scoping rule:** this flag is accepted **only** when all of the following are true:
  1. `ENVIRONMENT=test`
  2. `E2E_HARNESS=1`
  3. startup occurs via the browser-test harness path defined in `tests/e2e/conftest.py`
- In **all other contexts** — including preview, review, QA, shared sandbox, staging, and production — startup must **fail closed** if the flag is present.

### Proposed changes
1. Add config support for browser-test scheduler disable.
2. In `app/main.py`, guard both:
   - `init_scheduler().start()`
   - Riverside scheduler startup
3. Ensure shutdown logic is safe when schedulers were never started.
4. Add explicit structured log message when schedulers are intentionally skipped.
5. Health/status behavior must distinguish:
   - `disabled_for_test`
   - from genuine `not_running` / degraded states
6. Update `tests/e2e/conftest.py` so the server subprocess starts with the browser-test scheduler-disable env var set **before** or **inside** subprocess startup.
7. Add unit/integration coverage for:
   - startup with schedulers enabled
   - startup with schedulers skipped
   - shutdown in both modes
   - startup acceptance only for the allowlisted tuple (`ENVIRONMENT=test`, `E2E_HARNESS=1`, test-harness startup path)
   - startup rejection in all non-allowlisted contexts when browser-test flag is set
   - health/status behavior in both modes

### Health assertion boundary
- App-backed browser CI may treat `disabled_for_test` as expected.
- Non-browser health/integration checks must continue validating normal scheduler behavior.
- No shared health gate may silently reinterpret a real `not_running` scheduler as acceptable.

### Design constraints
- No hidden magic based solely on `ENVIRONMENT=test`.
- The flag must not become a generic maintenance-mode shortcut.
- Test mode must not normalize degraded scheduler state in higher environments.

### Exit criteria
- App-backed browser tests can boot the app without starting background jobs.
- No scheduler-related Azure auth noise appears during browser suite startup.
- Non-test environments retain current scheduler behavior.
- Test-disabled scheduler state is observable and semantically distinct.

---

## Workstream 3 — Auth-Stable Browser Smoke Contract

### Objective
Define the authenticated browser mechanism and deterministic page-data expectations before adding a hard CI browser gate.

### Canonical auth strategy
#### Local CI/app-backed smoke
- Use **cookie/session-based browser auth**, not header-only page auth.
- Prefer the proven cookie-injection pattern from `tests/e2e/test_headless_full_audit.py` **only if the cookie is obtained from real server-side session issuance logic**.
- The canonical fixture must authenticate via:
  - the real app session issuance flow, **or**
  - a tightly controlled test bootstrap path that exercises the same server-side session/signing logic.
- **Manual/forged cookie construction that bypasses server auth/session issuance is forbidden.**

#### Session stability requirements
- Fresh browser context per test or tightly scoped test group.
- No persisted shared auth state across unrelated smoke tests.
- Deterministic session teardown/reset.
- Validate relevant cookie/session invariants where applicable (e.g. `HttpOnly`, SameSite/Secure expectations appropriate to test context).

#### Mandatory auth-fixture acceptance criteria
Implementation is not complete until tests prove all of the following:
- fresh browser context is created per smoke test or approved tightly scoped test group
- no storage-state reuse occurs across unrelated smoke tests
- deterministic teardown/reset clears session state between tests
- cookie/session invariants are asserted as appropriate to the test environment
- the auth fixture fails closed if unexpected shared auth state is detected

#### Live staging validation
- If live-browser validation is added later, use the guarded staging token/session path rather than dev login assumptions.

### Deterministic CI data/setup contract
- CI browser smoke must run against a **known deterministic app state**.
- Allowed models for first wave:
  - seeded local test data, or
  - deterministic empty-state rendering
- Disallowed for first-wave gated assertions:
  - time-varying backend expectations
  - dependence on background schedulers
  - assertions that require volatile historical state without seeding
- The execution implementation must document which routes are using seeded-state vs empty-state expectations.

### Deterministic data/render contract
For first-wave gated routes, the expected contract is:
- Page may render with seeded or empty-state data, but must render a healthy shell.
- Critical partials may render empty-state content, but must return the correct fragment successfully.
- Gated assertions must include at least one stable semantic check per route.

### First-wave page set and semantic expectations
#### Unauthenticated smoke
| Route | Minimum semantic assertion |
|---|---|
| `/login` | login page shell or auth entry CTA visible |

#### Authenticated smoke
| Route | Minimum semantic assertion |
|---|---|
| `/dashboard` | dashboard heading, nav landmark, and one stable widget container present; no server error text |
| `/sync-dashboard` | sync heading, status container, and one stable HTMX region present; no server error text |
| `/riverside` | riverside-specific heading/title plus main container present |
| `/dmarc` | DMARC-specific heading/title plus main container present |

### First-wave partial set and semantic expectations
- Partial checks should run under the same authenticated browser session model where practical.
- A partial may be “empty but healthy,” but must still return the expected fragment marker.
- A broken placeholder/error banner is a failure.

| Partial | Minimum semantic assertion |
|---|---|
| `/partials/sync-status-card` | sync card/status fragment marker present |
| `/partials/sync-history-table` | table/container fragment marker present |
| `/partials/active-alerts` | alerts fragment marker present |
| `/partials/tenant-sync-status` | tenant status fragment marker present |

### Exit criteria
- One canonical browser auth fixture exists for gating tests.
- Browser smoke tests no longer tolerate `401`, `403`, or `500` for expected-authenticated pages.
- Data expectations are explicit enough to avoid brittle false failures.

---

## Workstream 4 — Minimum Viable Browser Smoke Gate in CI

### Objective
Promote existing browser coverage into a hard gate that validates key app pages and critical partials before merges/deploys.

### First-wave assertions
For authenticated app pages:
- HTTP response is **200 only**
- no uncaught browser console errors per the policy below
- page body does not contain obvious server error text
- required shell/navigation/semantic marker exists

For HTMX partials:
- response is **2xx only**
- HTML is returned
- required fragment marker exists
- no partial-specific 500/error text

### Console-error policy
- Fail only on console events with **error** severity.
- Ignore warnings by default.
- Any allowlist of benign error messages must be:
  - minimal,
  - version-controlled,
  - specific to known non-user-impacting noise,
  - reviewed in code review.
- Do not allow a vague catch-all ignore list.

### Reuse strategy
Prefer extracting/tightening existing assets rather than duplicating tests:
- `tests/e2e/test_headless_full_audit.py`
- `tests/e2e/test_dashboard_page.py`
- `tests/e2e/test_sync_dashboard_page.py`

### CI execution-environment controls
- **Workflow file:** `.github/workflows/ci.yml`
- **New job:** `browser-smoke`
- **Dependency:** runs after `lint-and-test`
- **Parallelism:** runs in parallel with `security-scan`, not after it
- **Triggers:** PRs and pushes to `main` via the existing CI workflow
- **Required checks policy:** `browser-smoke` and `security-scan` become required only after successful soak rollout (below)
- **Enforcement mechanism after promotion:** GitHub branch protection/rulesets on `main` must require both checks to pass and be up to date before merge; direct pushes to protected branches remain restricted; any temporary bypass/demotion requires documented approval and tracking
- **Pinned environment:** browser/runtime versions and app startup command must be pinned in workflow/test config to minimize host drift
- **Readiness:** explicit app readiness check before browser tests begin
- **Timeouts:** deterministic startup and navigation timeouts must be encoded in the workflow/test harness
- **Runtime target:** p95 under 7 minutes
- **Artifacts on failure only:** screenshots, concise console log capture, optional sanitized Playwright trace if size is acceptable
- **Artifact retention:** short retention only; access limited to repo maintainers
- **Artifact prohibitions:** no storage state upload, no cookie dump, no auth header dump, no unsanitized network traces

### Staged rollout / soak requirement
1. Introduce `browser-smoke` as **non-blocking** initially.
2. Collect a soak window of consecutive runs (to be defined in the execution issue; default target: at least 10 green runs / several days of PR traffic).
3. Promote to **required PR check** only if:
   - non-actionable failure rate stays below 5%
   - runtime stays within budget
   - failures are producing actionable artifacts
4. If the gate exceeds the flake threshold for 3 consecutive runs after promotion, demote and fix forward.

### Important boundary
This CI gate validates **application behavior in CI**, not full Azure/App Service parity. It is a **code-level smoke gate**, not a replacement for post-deploy validation.

### Exit criteria
- CI fails if key app pages render with JS errors or broken partials.
- Browser smoke remains fast enough to be routine.
- Failure artifacts are actionable and do not leak sensitive data.
- Gate promotion happens only after soak criteria are met.

---

## Workstream 5 — Tighten Existing Browser Tests

### Objective
Convert permissive/non-gating browser tests into meaningful release checks and separate exploratory coverage from must-pass smoke coverage.

### Specific cleanup targets
1. Replace status-code allowances like `(200, 401, 403)` with exact expectations in smoke-gated tests.
2. Remove or retire any gated test that allows `500` from page tests.
3. Un-xfail the dashboard console-error assertion once cookie/session auth is stable.
4. Split:
   - focused must-pass smoke tests
   - broader exploratory/full-audit browser suites
5. Enforce hard separation:
   - smoke tests use dedicated smoke selection/path/job
   - smoke fixtures remain minimal and controlled
   - exploratory failures do not affect required status unless intentionally promoted later

### Exit criteria
- Gated browser tests have deterministic expectations.
- Gated tests do not silently tolerate broken UI behavior.
- Broader exploratory suites remain available without weakening the gate.

---

## Workstream 6 — Authorization Coverage Follow-Up

### Objective
Ensure the browser strategy does not stop at “renders for admin” and explicitly tracks negative authorization coverage.

### Minimum follow-up deliverables
- Define a lightweight role matrix for first-wave routes/partials.
- Add at least one non-admin or limited-role negative browser/API check for a protected admin-facing route/view.
- Document whether first-wave smoke remains render-only or includes RBAC assertions.
- Track this as a dedicated follow-up issue, not just a note.

---

## Workstream 7 — Second Wave (After First-Wave Stability)

### Accessibility gate
Use a reduced subset of `tests/e2e/test_axe_accessibility.py` for:
- `/login`
- `/dashboard`
- `/sync-dashboard`

Fail only on critical/serious violations initially.

### Visual regression gate
Use `tests/e2e/test_visual_parity.py` after:
- baseline trust is established
- scheduler-disabled startup is stable
- CI runtime/cost is acceptable

---

## Proposed Task Decomposition

1. **Prod sync evidence runbook + investigation memo**
2. **Browser-test scheduler isolation config + lifecycle tests**
3. **Canonical browser auth fixture stabilization**
4. **Deterministic browser smoke test data/setup contract**
5. **Focused browser smoke tests for pages + partials**
6. **CI workflow integration + artifact handling + soak rollout**
7. **Authorization/RBAC follow-up coverage task**
8. **Optional follow-up: accessibility gate**
9. **Optional follow-up: visual regression gate**

---

## Proposed Execution Order

### Parallel Track A — Read-only prod investigation
- Execute **Workstream 1** immediately.

### Parallel Track B — CI/browser hardening
1. **Workstream 2 first** — scheduler isolation
2. **Workstream 3 next** — auth-stable browser contract
3. **Workstream 4 + 5 together** — CI browser smoke gate + test tightening
4. **Workstream 6 next** — explicit authz follow-up
5. **Workstream 7 later** — a11y/visual follow-on

This keeps prod evidence collection moving without blocking the technical prerequisite for reliable browser tests.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Prod issue is caused by Azure-side state we cannot inspect fully from code | Medium | capture evidence cleanly and escalate with exact missing permissions/data |
| Browser gate becomes flaky due to auth/session/bootstrap issues | High | make auth fixture a first-class prerequisite; disable schedulers first |
| CI runtime balloons | Medium | gate only 5 pages + 4 partials initially |
| Existing browser tests are too coupled to dev-login assumptions | Medium | use cookie/session-based canonical fixture with real session issuance |
| Scheduler-disable flag leaks beyond intended test context | High | reject use outside explicit non-deployable test context |
| Failure artifacts leak sensitive data | Medium | upload on failure only, short retention, prohibit auth material artifacts |
| New gate loses trust due to noisy rollout | High | soak first, promote only after measurable stability |

---

## Success Metrics

### Prod sync investigation success
- One clear root-cause category identified
- One concrete remediation issue or patch plan produced

### Browser gate success
- Broken partials like `/partials/sync-history-table` fail CI before deploy
- Browser console regressions fail CI under the defined policy
- Scheduler startup noise no longer contaminates app-backed E2E runs
- Browser-smoke non-actionable failure rate stays below 5% during soak and after promotion
- Browser-smoke p95 runtime stays under target budget
- Any flaky smoke test blocks promotion to required status until fixed

---

## Reviewer Questions Resolved in This Revision

1. **Execution order** — split into parallel tracks; scheduler isolation is the technical prerequisite for browser gating, while prod investigation proceeds independently.
2. **First-wave page/partial size** — kept intentionally small and explicit.
3. **Accessibility timing** — moved to later wave.
4. **Issue/task decomposition** — now explicit.
5. **CI auth ambiguity** — now made a first-class prerequisite with real session issuance requirement.
6. **Evidence handling** — now explicitly constrained.
7. **Gate reliability** — soak rollout, measurable thresholds, console policy, deterministic environment/data requirements now included.

# ROUND 2 — Adversarial Audit (Release Gate Arbiter ⚔️)

**Auditor:** Release Gate Arbiter (`release-gate-arbiter-58d5f6`) — Sword of Ultimate Truths
**Date:** 2026-05-20
**Commit under review:** `5cb15ef` (post — "ct-0b1 + ct-59n CTA + login a11y").
**Mode:** Adversarial. Round 1 findings re-verified or refuted. Seams hunted. Receipts attached.
**Method:** Static review, live `curl` against `localhost:8000`, direct Jinja render of `login.html` with `is_dev=False` to simulate prod, `git log`, `bd show`, and full grep sweeps under `app/`, `infrastructure/`, `scripts/`, `docs/`.

---

## 0. One-paragraph adversarial summary

The Round 1 audits were largely correct, but one is now actively dangerous: the just-shipped `ct-0b1` fix in commit `5cb15ef` is **incomplete and breaks the Microsoft sign-in flow in staging and production** (see N1). The Jinja template now correctly omits the dev form HTML when `is_dev=False`, but the page's inline `<script>` still synchronously calls `form.addEventListener(...)` against an element that no longer exists, throwing `TypeError: Cannot read properties of null` before any other handler — including the Microsoft SSO button click handler and the OAuth callback handler — is wired up. The regression test added in the same commit only renders the Jinja template; it never executes the script. R1 backend was right about migration 008 (no-op against prod schema, self-admitted in code comments), right about the zero-records SQL bug (unchanged), right about the `enforce_admins` regression (both files still wrong), and right about the $200/mo cost number (validated line-by-line against `parameters.production.json` and `main.bicep`). R1 understated the rate-limit fail-open (P3 should be P2; on Redis outage, all non-`/auth` endpoints lose rate-limiting entirely) and the Lighthouse documentation rot (14 markdown files, not 7). R1 overstated the `arbiter/` framework: it is two files — a `README.md` and one `verify.yaml` — with no runtime enforcement; it is a policy declaration, not a wired-in gate.

---

## 1. Round 1 finding-by-finding validation

### 1.1 Backend / Infra audit (`ROUND1_BACKEND_AUDIT.md`)

| R1 ID | R1 severity | Verdict | Evidence |
|---|---|---|---|
| F-1 mig 008 no-op vs prod schema | P1 | ✅ **CONFIRMED** | `alembic/versions/008_add_performance_indexes.py:89,105,118` — author's own comments admit `monitoring_alerts`, `cost_data`, `compliance_scores`, `compliance_frameworks` don't exist. Only 4 of the ~14 indexes the file appears to create actually land. |
| F-2 zero-records query | P1 | ✅ **CONFIRMED, UNCHANGED** | `app/api/services/monitoring_service.py:461-471` is byte-identical to R1's quote. The `.limit(N).count()` antipattern + missing `tenant_id` filter are still in main. Dedup layer at line 475+ masks the symptom but doesn't fix the query. |
| F-3 Lighthouse doc drift across "7+" docs | P1 | ⚠️ **CONFIRMED + UNDERSTATED** | `rg -l -i "lighthouse" --type md` returns **14 files**, not 7. R1 missed `AGENT_ONBOARDING.md`, `CHANGELOG.md`, `CONTROL_TOWER_MASTERMIND_PLAN_2026.md`, `PORTFOLIO_PLATFORM_PLAN_V2.md`, `INFRASTRUCTURE_END_TO_END.md`, `docs/RUNBOOK.md`, `domains/resources/README.md`, `domains/resources/DATA_CLASSIFICATION.md`, `domains/identity/README.md`, `domains/identity/DATA_CLASSIFICATION.md`. App code itself (`rg -i "lighthouse" app/`) returns 0 — the demolition was clean; the docs sweep was not. |
| F-4 `enforce_admins:false` will regress | P1 | ✅ **CONFIRMED, STILL UNFIXED** | `scripts/gh-setup.sh:297` and `docs/GITHUB_CLI_GUIDE.md:617` both still emit `"enforce_admins": false`. ct-9f1 tracks the runtime restoration but does not patch the script — a future maintainer running gh-setup.sh silently regresses. |
| F-5 dev login form in prod HTML | P2 | ⚠️ **OVERTAKEN BY EVENTS** | The original info-disclosure surface is gone after `5cb15ef` (form not rendered when `is_dev=False`). But the fix introduced **N1 below**, which is strictly worse than the original finding. R1's P2 underestimated the blast radius of the unintended consequences. |
| F-6 `is_resolved` Mapped[bool]/Integer | P2 | ✅ **CONFIRMED** | `app/models/monitoring.py:112-114` unchanged. |
| F-7 1h resource sync cadence | P2 | ✅ **CONFIRMED** | `app/core/config.py:225` — `resource_sync_interval_hours: int = 1`. |
| F-8 `enableRedis:true` in staging params | P3 (speculative) | ❌ **DISPUTED — STALE CONCERN** | `infrastructure/parameters.staging.json:71` reads `"enableRedis": {"value": false}`. R1 hedged ("Need to confirm current state") — the answer is "already false." No action needed. |
| F-9 `SyncJobLog.tenant_id` nullable | P2 | ✅ **CONFIRMED** | Model unchanged. |
| F-10 `lazy="joined"` | P3 | ✅ **CONFIRMED** | Unchanged. |
| F-11 azure_client default cred race | P3 | ✅ **CONFIRMED (advisory)** | Unchanged; non-urgent. |
| F-12 superseded docs | P3 | ✅ **CONFIRMED** | Unchanged. |
| F-13 `arbiter/` "working as designed" | informational | ⚠️ **OVERSTATED** | The directory contains exactly **2 files**: `arbiter/README.md` (2.6 KB) and `arbiter/policies/verify.yaml` (7.4 KB). No runtime code, no test, no CI hook that actually loads `verify.yaml` and enforces it. R1 called this a "credibility multiplier" — it is a policy declaration with no executable counterpart inside the repo. The `.github/workflows/deploy-production.yml` is the only thing claimed to mirror it; verifying that drift is a manual eyeball exercise. Treat as **advisory, not enforced**. |
| F-14 hardcoded `admin/admin` | P2 | ✅ **CONFIRMED** | `app/api/routes/auth.py:53-54` unchanged. |
| F-15 rate-limit fail-open | P3 | ⚠️ **UNDERSTATED** | `app/main_middleware.py:130-137`: on a rate-limiter exception, only `/auth/` paths return 429; **all other paths fall through to `await call_next(request)` with no rate limiting at all**. If Redis goes down, every non-auth endpoint loses its limit silently. This is a P2 (DoS amplifier), not a P3. |

### 1.2 Frontend / Design audit (`ROUND1_DESIGN_AUDIT.md`)

| R1 ID | R1 severity | Verdict | Evidence |
|---|---|---|---|
| F1 dev login form ships to prod | P0 | ⚠️ **OVERTAKEN BY N1** | Original surface gone; replaced with worse bug (N1). |
| F2 `/onboarding/` CTA broken | P1 | ✅ **FIXED in 5cb15ef** | `app/templates/pages/dashboard.html:96-98` now reads `<a href="/sync-dashboard" class="btn-brand text-center">View Sync Status</a>`. CTA is honest. |
| F3 login bypasses base.html (no landmarks, wrong title, etc.) | P1 | ⚠️ **PARTIALLY FIXED** | `role="alert"` added to error div (good). **But:** `app/templates/login.html:5` still reads `<title>Login - Riverside Capital PE Governance</title>` — **wrong brand still in the title bar of a page now shipping in prod**. Still no `<main>`, no skip links, no favicon, no `data-brand`. Brand-trust hit at every login impression. ct-tdu remains open. |
| F4 site-wide `role="alert"` audit | P1 | ⚠️ **PARTIALLY FIXED** | Only the login error div was touched. `rg 'role="alert"' app/templates/` returns 1 match (login.html). The consent banner, dashboard partials, admin user-search, HTMX swap errors — none have it. |
| F5 dmarc dashboard heading skip | P2 | ✅ **CONFIRMED, UNFIXED** | `pages/dmarc_dashboard.html:77` unchanged. |
| F6 docs/design-system.md drift | P2 | ✅ **CONFIRMED, UNFIXED** | Unchanged. |
| F9 theme toggle target size | P2 | ✅ **CONFIRMED, UNFIXED** | |
| F10 mobile menu drift | P2 | ✅ **CONFIRMED, UNFIXED** | |
| F11 mobile menu focus trap | P2 (needs live test) | ✅ **STILL NEEDS LIVE TEST** | Server is up but no Playwright run executed this session. |
| F12 consent banner role=dialog without modal | P2 | ✅ **CONFIRMED, UNFIXED** | |
| F16 hydration error states | P2 | ✅ **CONFIRMED, UNFIXED** | |
| F17 filter pill color-only state | P2 | ✅ **CONFIRMED, UNFIXED** | |
| F18 external CDN scripts | P3 | ✅ **CONFIRMED, UNFIXED** | |
| F20 no automated WCAG CI gate | P2 | ✅ **CONFIRMED, UNFIXED** | |

---

## 2. New findings (R2-only)

Findings follow the 6-element canonical structure. ruleId reserved for future check catalog.

### N1 — Login JS calls `form.addEventListener` against a non-existent element in non-dev environments → Microsoft SSO is dead in prod

- **Verdict + severity:** 🔴 **P0 BLOCKER — site unusable in non-dev**
- **ruleId:** `RG-LOGIN-NULLREF-001`
- **Why this fired:** The ct-0b1 fix in `5cb15ef` removed the `<form id="login-form">` block from the rendered HTML when `is_dev=False`, but the page's inline `<script>` still executes the following synchronously at top level:
  ```javascript
  const form = document.getElementById('login-form');   // null in prod
  const submitBtn = document.getElementById('submit-btn');  // null in prod
  form.addEventListener('submit', async (e) => { ... });   // ❌ TypeError
  ```
  Because the throw happens at top-level synchronous evaluation, every line that follows is skipped: the Azure click handler (`azureBtn.addEventListener('click', signInWithAzureAD)`), the page-init IIFE (`(async () => { if (await handleOAuthCallback()) return; ... })()`), and the `/health` poll. Net effect in staging/prod: the "Sign in with Microsoft" button does nothing on click, AND any user redirected back from `login.microsoftonline.com` with `?code=…&state=…` in the URL is never processed — the callback handler is dead code. **There is no working sign-in path on the page in non-dev.**
- **Where in source:** `app/templates/login.html:244, 245, 247` (top-level script block); `:302` (dead unhide call inside IIFE that never runs); confirmed by direct Jinja render with `is_dev=False`:
  ```
  login-dev-form in HTML: False
  username input in HTML: False
  HAZARD present: "const form = document.getElementById('login-form')" -> True
  HAZARD present: 'form.addEventListener' -> True
  HAZARD present: "document.getElementById('login-form').classList.remove('hidden')" -> True
  ```
- **Tool provenance:** Jinja2 3.x direct render (uv-run python), 2026-05-20. Live server confirmation: `curl localhost:8000/login` (dev mode, form present); render at `is_dev=False` (form absent, script unchanged).
- **What to do next:**
  1. Wrap the dev-only JS in the same Jinja guard:
     ```jinja
     {% if is_dev %}
     <script nonce="{{ request.state.csp_nonce }}">
         // dev login form handler — only loaded with the form itself
         const form = document.getElementById('login-form');
         ...
     </script>
     {% endif %}
     ```
     and split the Azure SSO / OAuth callback JS into a sibling unconditional `<script>` block.
  2. Failing that, null-guard every `getElementById` deref:
     ```javascript
     const form = document.getElementById('login-form');
     if (form) {
         form.addEventListener('submit', async (e) => { ... });
     }
     ```
  3. **Add a real regression test that executes the script, not just the template.** The existing `tests/unit/test_login_dev_form_gating.py` is a false-positive net: it renders Jinja, asserts strings absent, and passes — but cannot catch a JS null-deref. Add a Playwright test that loads `/login` in a staging-like environment, clicks the Microsoft button, and asserts a navigation to `login.microsoftonline.com` is initiated. ct-0b1 should not close until that test exists and passes.
- **Effort:** XS for the Jinja wrap (10 min); S for the Playwright regression (45 min).

### N2 — `docs/GITHUB_CLI_GUIDE.md:617` documents the wrong `enforce_admins` value alongside `scripts/gh-setup.sh:297`

- **Verdict + severity:** 🟠 **P2** (governance / configuration drift)
- **ruleId:** `RG-DOC-ENFORCE-ADMINS-002`
- **Why this fired:** Solutions Architect's F-4 named the script, but didn't emphasize that `docs/GITHUB_CLI_GUIDE.md:617` documents the same wrong value. Future operators copy-pasting from the docs will reproduce the misconfiguration even if `gh-setup.sh` is fixed.
- **Where in source:**
  - `scripts/gh-setup.sh:297` — `"enforce_admins": false`
  - `docs/GITHUB_CLI_GUIDE.md:617` — same string in the documented payload example
- **Tool provenance:** `grep -n enforce_admins scripts/gh-setup.sh docs/GITHUB_CLI_GUIDE.md`, 2026-05-20.
- **What to do next:** Patch both files in one commit. Add `tests/architecture/test_branch_protection_config.py` (R1 §5 fitness #4) to assert both files contain `"enforce_admins": true`. ct-9f1 should require this patch as part of the acceptance criteria, not as a follow-up.
- **Effort:** XS.

### N3 — Rate-limit middleware fails open on every non-`/auth/` path when Redis is unreachable

- **Verdict + severity:** 🟠 **P2** (DoS amplifier; R1 marked P3 — escalating)
- **ruleId:** `RG-RATELIMIT-FAILOPEN-003`
- **Why this fired:** `app/main_middleware.py:128-137`:
  ```python
  except Exception as exc:
      logger.error(f"Rate limiting error: {exc}")
      if "/auth/" in request.url.path:
          return JSONResponse(status_code=429, ...)
      return await call_next(request)   # ← silently unlimited
  ```
  If Redis is down (B1 Azure Cache Basic has no SLA; today it's not even provisioned — `cache_enabled=True` falls through to in-memory), every non-auth request bypasses limiting. R1 treated this as P3; for a public-internet governance dashboard one IAM widening or one runaway scraper away from a billable-incident, it deserves P2. Note also: the rate limiter exempts `is_development` entirely (line 103), and `current_settings = get_settings()` is read on **every request** rather than at startup — if the env detection later mis-routes to "development" (see N5), all rate-limiting silently disappears.
- **Where in source:** `app/main_middleware.py:101-137`.
- **Tool provenance:** Static review, 2026-05-20.
- **What to do next:**
  1. Fail-closed on write methods (`POST`/`PUT`/`DELETE`/`PATCH`) even on rate-limiter exceptions.
  2. Fail-open with a hard ceiling for reads (e.g., budget of 50 req/min/IP via in-memory fallback when Redis is dead).
  3. Emit `rate_limit_infra_unavailable_total` Prometheus counter so this never goes unnoticed.
- **Effort:** S.

### N4 — Login `<title>` still claims a different product (brand-trust regression)

- **Verdict + severity:** 🟡 **P2** (brand-trust / a11y SC 2.4.2)
- **ruleId:** `RG-LOGIN-WRONG-TITLE-004`
- **Why this fired:** `app/templates/login.html:5` reads:
  ```html
  <title>Login - Riverside Capital PE Governance</title>
  ```
  The footer immediately below renders `HTT Control Tower v{{ app_version }}`. Browser tab and any tab-grouping UI shows the wrong product name. Any franchisee, auditor, or partner who lands on the login page from a shared link will see a Riverside-branded tab. R1-design F3 mentions this, but it survived `5cb15ef`. WCAG SC 2.4.2 Page Titled (Level A) also fails: title does not describe the actual app.
- **Where in source:** `app/templates/login.html:5`.
- **Tool provenance:** Direct file read, 2026-05-20.
- **What to do next:** `s/Riverside Capital PE Governance/HTT Control Tower/`. Also gate via brand context: `<title>Sign in — {{ brand_display_name }} Control Tower</title>`.
- **Effort:** XS.

### N5 — `environment` detection silently falls through to "development" if `ENVIRONMENT` env var is empty string

- **Verdict + severity:** 🟡 **P2** (defensive coding; latent fail-open)
- **ruleId:** `RG-CONFIG-ENV-FALLOPEN-005`
- **Why this fired:** `app/core/config.py:296-313` — `detect_environment` validator runs `mode="before"` and if `v` is falsy (None *or empty string*) it walks an env-var probe sequence and **defaults to "development"**. Pydantic v2 should pass the Field default ("production") in most cases, but an explicit `ENVIRONMENT=""` in a `.env` file, a kube manifest empty-string injection, or an `az webapp config appsettings set --settings ENVIRONMENT=""` (which is a legal Azure CLI command) lands the app in development mode. Consequences cascade through this entire audit: dev login form renders, hardcoded `admin/admin` is accepted, HSTS strict is off, rate limiter is bypassed.
- **Where in source:** `app/core/config.py:296-313`.
- **Tool provenance:** Static review, 2026-05-20.
- **What to do next:** Replace the heuristic fallthrough with `raise ValueError("ENVIRONMENT must be explicitly set to one of development|test|staging|production")`. Fail-closed on ambiguity.
- **Effort:** XS — but requires updating any test that relies on the implicit dev default.

### N6 — The new `tests/unit/test_login_dev_form_gating.py` is a false-positive net for the very bug it claims to prevent

- **Verdict + severity:** 🟠 **P2** (test design — gives false confidence; co-cause of N1)
- **ruleId:** `RG-TEST-STATIC-ONLY-006`
- **Why this fired:** The four tests render Jinja with `is_dev=False` and assert string absence. They never execute the script tag, so N1 — a runtime JavaScript null-deref guaranteed to fire on every prod page load — passes the test green. The test is necessary but not sufficient. It gave the committer enough confidence to ship a broken page.
- **Where in source:** `tests/unit/test_login_dev_form_gating.py:48-66`.
- **Tool provenance:** Direct file read, 2026-05-20.
- **What to do next:** Add a Playwright (or Pyppeteer) smoke test under `tests/e2e/`:
  ```python
  def test_login_page_has_no_js_errors(page, app_url_prod_mode):
      errors = []
      page.on("pageerror", lambda exc: errors.append(str(exc)))
      page.goto(f"{app_url_prod_mode}/login")
      page.wait_for_load_state("networkidle")
      assert errors == [], f"Login page raised JS errors: {errors}"
  ```
  Couple this with the existing `tests/e2e/test_headless_full_audit.py` infra. ct-0b1 acceptance must require it.
- **Effort:** S.

### N7 — Staging `AZURE_AD_CLIENT_SECRET` is an inline appsetting value, not a Key Vault reference (ct-wph follow-up unclosed)

- **Verdict + severity:** 🟡 **P2** (secret hygiene)
- **ruleId:** `RG-STAGING-INLINE-SECRET-007`
- **Why this fired:** `bd show ct-wph` documents that on 2026-05-19 the 9 `AZURE_AD_*` settings were copied from prod → staging via `az webapp config appsettings set`, with `AZURE_AD_CLIENT_SECRET` set as a literal value rather than a `@Microsoft.KeyVault(SecretUri=...)` reference. ct-wph names this as follow-up #2; bd shows ct-wph still **OPEN**. Any maintainer with App Service Contributor on staging can `az webapp config appsettings list -n app-governance-staging-xnczpwyv` and read the prod client secret in clear text. This is the same secret used by the prod app registration `Riverside-Capital-PE-Governance-Platform` (appId `1e3e8417-49f1-4d08-b7be-47045d8a12e9`) — staging and prod share the registration intentionally, so the secret is prod-equivalent.
- **Where in source:** No file — Azure App Service appsettings. `bd show ct-wph` for full audit trail. `infrastructure/parameters.staging.json` does not specify `azureAdClientSecret` (it's empty in the params), so the secret is set out-of-band.
- **Tool provenance:** `bd show ct-wph`, 2026-05-20.
- **What to do next:** (a) Rotate the prod client secret immediately (it has been readable from staging for ~24h). (b) Switch staging appsetting to `@Microsoft.KeyVault(SecretUri=https://kv-gov-prod.vault.azure.net/secrets/azure-ad-client-secret/<version>)`. (c) Add the binding to `.github/workflows/deploy-staging.yml` so it survives the next reconcile.
- **Effort:** S (rotation + KV reference) + M (CI plumbing).

### N8 — `main.bicep:73` defaults `sqlAdminPassword` to `newGuid()` — a fresh deploy regenerates the SQL admin password silently

- **Verdict + severity:** 🟡 **P2** (deploy-time footgun; prod is fine today because `sqlSetAdminPassword: false`)
- **ruleId:** `RG-BICEP-NEWGUID-DEFAULT-008`
- **Why this fired:** `infrastructure/main.bicep:73-74`:
  ```bicep
  param sqlAdminPassword string = newGuid()
  ```
  Combined with `param sqlSetAdminPassword bool = true` (line 76 default), any deploy that doesn't explicitly pass `sqlSetAdminPassword=false` AND doesn't supply `sqlAdminPassword` regenerates the SQL admin password to a new GUID — losing the previous one and breaking out-of-band tooling that knows the old password. Prod params correctly set `sqlSetAdminPassword: false`, so prod is safe today. Staging params also set `false`. Dev params **do not set this flag at all** (`infrastructure/parameters.dev.json` has no `sqlSetAdminPassword` key) — so a re-deploy of dev silently rotates the admin password every time.
- **Where in source:** `infrastructure/main.bicep:73-77`; `infrastructure/parameters.dev.json` (missing key).
- **Tool provenance:** Direct file read, 2026-05-20.
- **What to do next:** Change Bicep default to `sqlSetAdminPassword bool = false` and require explicit opt-in for password rotation. Add the flag to `parameters.dev.json` for clarity.
- **Effort:** XS.

### N9 — PII (user email, user_id) emitted in `logger.info`/`logger.warning` lines without redaction

- **Verdict + severity:** 🟢 **P3** (compliance hygiene; low impact at HTT scale today, GDPR Art. 5(1)(c) data minimization)
- **ruleId:** `RG-LOG-PII-009`
- **Why this fired:** Examples:
  - `app/api/routes/auth.py:378-383` — `logger.info(f"Azure AD callback: user={validated.sub}, azure_tid=..., group_tenant_ids=..., resolved_tenant_ids=..., is_admin=...")`
  - `app/services/email_service.py:428` — `logger.info(f"Sending email to: {', '.join(safe_recipients)}")` (function name suggests redaction is intended; verify)
  - `app/api/services/auth_service.py:296` — `logger.info("Created user tenant mapping: %s -> %s", token_data.sub, tenant_id)`
  These land in Log Analytics within `governance-logs` (90d retention in prod). For a governance platform that *checks compliance posture for other people*, leaving user identifiers in plaintext logs is a foot-shooting risk. Not a breach in itself, but compounds when the F-9 `tenant_id=NULL` issue lands log rows that mix users across tenants.
- **Where in source:** As above; `rg "logger\.(info|debug|warning).*(password|secret|token|email|user_id)"` for full inventory.
- **Tool provenance:** ripgrep, 2026-05-20.
- **What to do next:** Introduce a `redact(...)` helper that emits `sub=user:01F3...` truncated identifiers and emails as `j***@d***.com`. Add a `logging.Filter` that scrubs known PII fields. Document in `docs/security/logging-policy.md`.
- **Effort:** M (one-off scrub) + S (recurring filter).

### N10 — `arbiter/` framework is a declaration with no executable enforcement

- **Verdict + severity:** 🟢 **P3** (truth-in-advertising; R1 F-13 overstated)
- **ruleId:** `RG-ARBITER-VAPORWARE-010`
- **Why this fired:** `arbiter/` contains exactly `README.md` (2.6 KB) and `policies/verify.yaml` (7.4 KB). There is no Python module, no CI job that loads the YAML and enforces it, no `tests/policy/` checking the workflow mirrors the policy. The README says `.github/workflows/deploy-production.yml` is the "executable mirror" — but mirror drift is detected by manual code review only. R1's framing ("credibility multiplier — most 3-month-old projects don't have this") is generous; right now it is **a policy document with no executable counterpart**. That is fine for an aspirational artifact, but should not be cited as a control during a Riverside compliance review.
- **Where in source:** `arbiter/` directory.
- **Tool provenance:** `list_files arbiter/`, 2026-05-20.
- **What to do next:** Either (a) wire a CI job `arbiter-policy-check.yml` that parses `verify.yaml` and asserts the listed `gate_steps` exist in `deploy-production.yml`, or (b) re-label the directory as `policies/aspirational/` until enforcement lands.
- **Effort:** S (CI parser) or XS (rename).

---

## 3. Cost number challenge

**Round 1 claim:** "~$200/mo all-in ($53.40 Azure + $147 GitHub)" — `ROUND1_BACKEND_AUDIT.md` §3.1.

**Verdict:** ✅ **VALIDATED. Cost number is accurate.** No change.

**Receipts:**

| Cost-doc claim | Bicep / Params receipt | Match? |
|---|---|---|
| Prod App Service Plan = **B1** ($12.41/mo) | `parameters.production.json:11-12` → `"appServiceSku": "B1"` | ✅ |
| Prod SQL Database = **Basic** ($4.90/mo) | `parameters.production.json:14-15` → `"sqlDatabaseSku": "Basic"` | ✅ |
| Prod Storage = LRS | `parameters.production.json:81-82` → `"storageSku": "Standard_LRS"` | ✅ |
| Prod Redis = NOT deployed | `parameters.production.json:78-79` → `"enableRedis": false` | ✅ |
| Staging SKU = B1 + SQL Free | `parameters.staging.json:12-14` → `B1`; lines 16-17 → SQL `Free` | ✅ |
| Staging Redis = false | `parameters.staging.json:78-79` | ✅ (also refutes R1 F-8 speculation) |
| Dev SQL = Basic but `enableAzureSql: false` (uses SQLite locally) | `parameters.dev.json:14-15, 17-18` | ✅ |
| ACR Basic ($5/mo) on dev only | not in main.bicep; managed out-of-band; matches doc claim | ✅ (out-of-band) |
| Log retention prod = 90d, dev = 30d, staging = 14d | `parameters.production.json:28-29`, `parameters.dev.json:25-26`, `parameters.staging.json:25-26` | ✅ |
| GitHub Enterprise 7 seats × $21 = $147 | not in repo — `docs/COST_MODEL_AND_SCALING.md:97` cites "live billing" | ⚠️ unverified by me, taken at face value |

**Caveats the cost number does NOT capture:**
1. **App Insights / Log Analytics 5 GB free tier headroom is one bad incident away from breach.** If a Python traceback storm emits 6 GB of stack traces in a week (this is normal during a sync auth failure cascade), the bill jumps `+$2.30/GB × delta`. Resource-sync hourly cadence (F-7) is the highest-risk amplifier.
2. **The `azure-governance-platform` resource group is one of ~3-4 RGs in the subscription**. `docs/COST_MODEL_AND_SCALING.md:114` notes the full subscription is ~$282/mo. The $200/mo number is *governance only*; total HTT-BRANDS Azure spend is ~$282/mo + $147 GitHub = **~$429/mo** at the subscription level. The R1 audit is correctly scoped to the governance platform, but the COO will conflate the two if not framed.
3. **Staging is in West US 2** (`parameters.staging.json:8-9`) while prod is East US — egress between them is non-free if any sync traffic crosses, which it shouldn't, but worth confirming.

**Bottom line:** Solutions Architect's $200/mo number checks out line-by-line against IaC. The cost doc is fresh as of April 18 and bicep has not drifted since.

---

## 4. Single biggest risk going into the next deploy

> **N1 — Login page JavaScript null-deref breaks Microsoft SSO in staging and production.**

**Defense:**

1. **It ships now.** Commit `5cb15ef` is the tip of `main`. Any deploy of main → staging or main → prod takes this with it.
2. **It is silent.** No log line, no 5xx, no Application Insights exception in the server traces — the throw is browser-side. The first signal will be a franchisee opening a ticket: "I can't sign in." Time-to-detect = the time until someone with a real account tries to log in.
3. **It removes the only working sign-in path.** The dev `admin/admin` form is correctly gated out in prod (the fix was right about that); the Azure SSO button is the only remaining path; its `click` handler is never attached because the synchronous `form.addEventListener` line throws first. Microsoft SSO is dead on click. OAuth callbacks from Azure (`/login?code=…`) are also dead because the IIFE that calls `handleOAuthCallback` never runs.
4. **It defeats its own regression test.** `tests/unit/test_login_dev_form_gating.py` passes — green CI gives false confidence. Reviewing the test in isolation, a reasonable engineer concludes ct-0b1 is closed.
5. **Maps to the three risks Tyler named:**
   - **CVE-worthy bug?** Not a CVE, but a P0 availability outage on the auth surface — equivalent operational severity.
   - **Embarrassing in front of a franchisee?** Yes. The first impression of any new franchisee will be a non-functional sign-in button.
   - **Blowing up the on-call rotation?** Yes. The fix is a 10-line Jinja wrap, but the diagnosis requires opening DevTools on a prod page and reading the console — not something a 2am on-call rotation will do quickly.

**Why this beats the other contenders:**
- F-1 (migration 008) has been broken for 3 months without an incident. The indexes are missing but the queries work.
- F-2 (zero-records alert flood) is already symptomatic but dedup mitigates and there's no franchisee impact.
- F-4 (enforce_admins) is latent — only fires if someone runs `gh-setup.sh`.
- N7 (inline secret on staging) is a slow leak — exploiting it requires App Service Contributor on staging.
- N1 is **already in main, ships on next deploy, has zero detection path, and breaks the only thing every user does first**.

---

## 5. Release Gate verdict

```yaml
verdict: FAIL
source_env: dev
target_env: staging  # or any non-development environment
initiative_id: ct-0b1 + ct-59n + login-a11y bundle (commit 5cb15ef)
commit_or_build_ref: 5cb15ef
pillars:
  requirements_closure:
    status: CONDITIONAL
    findings:
      - "ct-0b1 still OPEN in bd — correctly, because the fix is incomplete (N1)"
      - "ct-tdu still OPEN — login a11y bundle only partially addressed (N4, base.html bypass remains)"
  code_review:
    status: FAIL
    findings:
      - "N1: JS null-deref in app/templates/login.html:244-247 when is_dev=False"
      - "N6: regression test does not exercise script; false-positive net"
  security:
    status: CONDITIONAL
    findings:
      - "N3: rate-limit fail-open on non-/auth/ paths — escalate F-15 to P2"
      - "N5: ENVIRONMENT empty-string fall-through to development mode"
      - "N7: staging AZURE_AD_CLIENT_SECRET stored inline, not via KV reference"
      - "F-4 / N2: enforce_admins still false in script + docs (ct-9f1)"
      - "F-14: hardcoded admin/admin still in source (env-gated, but ASVS V2.5)"
  infrastructure:
    status: CONDITIONAL
    findings:
      - "F-1: alembic 008 no-op on 4 prod tables (3 months in main without indexes)"
      - "N8: bicep sqlAdminPassword default = newGuid(); dev params missing sqlSetAdminPassword flag"
  stack_coherence:
    status: PASS
    findings:
      - "core_stack.yaml present; ct-59n Lighthouse demolition clean in app/"
      - "Doc drift (F-3 / 14 md files) — coherence preserved in code, not in docs"
  cost:
    status: PASS
    findings:
      - "$200/mo all-in validated against parameters.production.json + main.bicep"
      - "Forward 12-mo base case ($2,897) unchanged"
  maintenance:
    status: CONDITIONAL
    findings:
      - "F-3 / N4: 14 md docs describe deleted Lighthouse code → new-engineer hazard"
      - "ct-l2j (zero-records alert flood) symptomatic in prod, dedup mitigates"
  rollback:
    status: CONDITIONAL
    findings:
      - "5cb15ef can be reverted as a single commit (`git revert 5cb15ef`)"
      - "Revert reintroduces R1 F-5 (dev form in HTML) — choose the lesser of two evils until N1 patch lands"
      - "Migration 008 has no real prod indexes to roll back; F-1 is forward-only fix via new migration 012"

blocking_findings:
  - N1 (login JS null-deref — P0 BLOCKER)

non_blocking_findings:
  - F-1, F-2, F-3, F-4, F-9, F-15 (R1 backend P1/P2 still open)
  - N2, N3, N4, N5, N6, N7, N8 (R2 new)
  - F3-design, F4-design, F5-design, F6-design (R1 design P1/P2)

conditions_for_pass:
  # Required before next deploy to staging or prod
  - N1 patched (Jinja wrap dev-only JS OR null-guard every getElementById)
  - N1 covered by a Playwright/headless smoke test that asserts no JS errors on /login in non-dev mode
  - N4 patched (login <title> fixed to HTT brand)
  - N2 patched (docs/GITHUB_CLI_GUIDE.md + scripts/gh-setup.sh both flip to "enforce_admins": true)
  - N7 rotated (prod client secret rotated; staging switched to KV reference)
  # Required before claiming "all green"
  - F-1 migration 012 written and applied (indexes on real prod tables)
  - F-2 zero-records query corrected (tenant-scoped, materialize before count)

remediation_list:
  P0:
    - "N1: 10-line Jinja wrap in login.html — STOP-THE-LINE for any deploy"
  P1 (next sprint):
    - "F-1, F-2, F-4 / N2, F-3, N3, N7"
  P2 (next month):
    - "N4, N5, N6, N8, F-6, F-9, N9"

exception_waivers_applied: []
signed: release-gate-arbiter-58d5f6 / run-2026-05-20 / ROUND2
```

---

## 6. Recommended bd actions

| bd ID | Action | Why |
|---|---|---|
| ct-0b1 | **Keep OPEN.** Add comment with N1 evidence. Acceptance criteria must require a Playwright smoke test that loads `/login` in non-dev mode and asserts zero `pageerror` events. | N1, N6 |
| ct-9f1 | Acceptance must include both `scripts/gh-setup.sh:297` AND `docs/GITHUB_CLI_GUIDE.md:617` patched in the same PR, plus the architecture test. | N2 |
| ct-tdu | Add N4 (wrong `<title>`) to scope; was implicit in F3 but the title bug survived the fix attempt. | N4 |
| ct-wph | Reframe as P1, not P2. Inline production-equivalent secret in staging appsettings is a meaningful exposure window. | N7 |
| **NEW** | File: "sec: rate-limit middleware fails open on non-/auth/ paths during Redis outage" — P2 | N3 |
| **NEW** | File: "sec: ENVIRONMENT empty-string fall-through to development mode" — P2 | N5 |
| **NEW** | File: "infra: bicep sqlAdminPassword default = newGuid() — fix dev params + change default" — P2 | N8 |
| **NEW** | File: "ops: PII (email, user_id) emitted in logger.info — add scrubbing filter" — P3 | N9 |
| **NEW** | File: "arbiter: wire policies/verify.yaml into a CI job or rename directory" — P3 | N10 |
| Optional follow-up | F-3 sweep — patch all 14 markdown files in one coordinated doc PR | F-3 expanded |

---

## 7. Receipts index (file:line citations)

- `app/templates/login.html:5, 244, 245, 247, 290-308` — N1, N4
- `app/api/routes/dashboard.py:354-373` — `_login_context` and public login routes (correct)
- `app/api/routes/auth.py:53-54, 88-95, 378-383` — F-14, F-5 backend gate (correct), N9
- `app/api/services/monitoring_service.py:459-491` — F-2 unchanged
- `app/main_middleware.py:101-137` — N3
- `app/core/config.py:65, 87, 225, 264, 296-313, 333-360, 408-415` — N5, JWT validator (correct), CORS validator (correct)
- `app/models/monitoring.py:23-25, 42, 112-114, 122` — F-9, F-10, F-6
- `alembic/versions/008_add_performance_indexes.py:43-160` — F-1 (self-admitted dead code in comments)
- `infrastructure/main.bicep:73-77` — N8
- `infrastructure/parameters.production.json` — cost validation (B1 + SQL Basic + LRS + no Redis confirmed)
- `infrastructure/parameters.staging.json:78-79` — refutes R1 F-8
- `infrastructure/parameters.dev.json` — missing `sqlSetAdminPassword` flag (N8)
- `scripts/gh-setup.sh:297`, `docs/GITHUB_CLI_GUIDE.md:617` — F-4, N2
- `tests/unit/test_login_dev_form_gating.py:48-66` — N6
- `arbiter/README.md`, `arbiter/policies/verify.yaml` — N10
- `bd show ct-0b1, ct-9f1, ct-tdu, ct-l2j, ct-wph, ct-wvn, ct-vgf` — bd backlog cross-check
- `docs/COST_MODEL_AND_SCALING.md:11-17, 61-128` — cost numbers (validated)

---

*End of Round 2. Hand off to ops-comms-collie for COO-readable narrative if needed. — Release Gate Arbiter ⚔️ (`release-gate-arbiter-58d5f6`)*

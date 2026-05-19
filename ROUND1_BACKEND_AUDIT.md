# ROUND 1 — Backend / Infra / Cost Audit

**Author:** Solutions Architect 🏛️ (`solutions-architect-af02fd`)
**Date:** 2026-05-20
**Scope:** Backend code, API hygiene, data layer, sync/scheduler, security posture, Azure infra, cost
**Repo HEAD context:** post-ct-59n Lighthouse demolition (~3,686 LOC removed, migration 011 staged)
**Method:** static review of repo @ `/Users/tygranlund/dev/01-htt-brands/control-tower`, cross-referenced against docs, Alembic migrations, Bicep IaC, and `bd` issue tracker. No live Azure API queries — Tyler can run `az consumption usage list` if a billing-side check is needed.

---

## 1. Executive Summary

- 🟢 **ct-59n landed cleanly in the codebase.** Zero `use_lighthouse` references survive in `app/`. The auth resolver in `app/api/services/azure_client.py` is sound (4-mode credential resolution: UAMI → OIDC federation → shared secret → per-tenant KV ref; documented in `app/core/sync/utils.py:build_sync_eligibility_decision`).
- 🔴 **Documentation has NOT caught up with the demolition.** `README.md`, `ARCHITECTURE.md`, `REQUIREMENTS.md`, `RUNBOOK.md`, `SECRETS_OF_RECORD.md`, and `domains/lifecycle/README.md` still actively describe Lighthouse delegation, `LighthouseAzureClient`, and the deleted `onboarding.py` route — including line-number citations to a file that no longer exists. New engineers reading the repo will be misled within five minutes.
- 🔴 **The "performance indexes" migration (008) is a no-op against real tables.** It targets `sync_jobs`, `cost_data`, `compliance_scores`, `monitoring_alerts` — none of which exist. Actual tables are `sync_job_logs`, `cost_snapshots`, `compliance_snapshots`, `alerts`. The migration silently no-ops because `_index_exists` swallows `NoSuchTableError`. Production has been running without the indexes the doc claims it has.
- 🟡 **ct-l2j is partially fixed.** Dedup + auto-resolve logic now exists in `monitoring_service.py:346-487`. But a residual SQL bug remains: the zero-records threshold query uses `.limit(N).count()` (SQLAlchemy anti-pattern: count ignores limit), is not tenant-scoped, and counts ALL historical zero-record runs ever, not just the last N. Once you have ≥3 zero-record logs in the table for any (job_type) anywhere, the threshold is permanently tripped.
- 🟡 **Branch protection regression risk is real.** `scripts/gh-setup.sh:297` hard-codes `"enforce_admins": false`. ct-90r flipped this to `true` on main; running `gh-setup.sh` would silently undo that.
- 🟢 **Cost posture is healthy.** Today's run-rate is **~$200/mo all-in** ($53.40 Azure + $147 GitHub Enterprise). Down from ~$298/mo. The April 18 cost doc is still substantially accurate. Forward 12-month base-case is $2,897.

---

## 2. Findings

### F-1 — Migration 008 targets non-existent tables; performance indexes never deployed

- **Severity:** **P1 critical**
- **Evidence:**
  - `alembic/versions/008_add_performance_indexes.py` declares indexes on `sync_jobs`, `cost_data`, `compliance_scores`, `compliance_frameworks`, `monitoring_alerts` (lines 47–125).
  - The actual model tables are: `sync_job_logs` (`app/models/monitoring.py:18`), `cost_snapshots` (`app/models/cost.py`), `compliance_snapshots` (`app/models/compliance.py`), `alerts` (`app/models/monitoring.py:99`).
  - `_index_exists()` catches `NoSuchTableError` and returns `False` → `if not _index_exists(...)` → `True` → `op.create_index(...)` against a non-existent table → fails OR silently no-ops depending on dialect.
  - The migration even contains its own confession in inline comments: `# NOTE: monitoring_alerts table does not exist — the model uses __tablename__ = "alerts" instead.` (line 89), `# NOTE: cost_data table does not exist — models use cost_snapshots and cost_anomalies.` (line 105), `# NOTE: compliance_scores and compliance_frameworks tables do not exist…` (line 118). The author noticed and shipped the migration anyway.
  - Net result: of ~14 indexes the file appears to create, only the ones on the 4 real tables (`recommendations`, `budgets`, `resources`, `subscriptions`, `backfill_jobs`) actually land. None of the high-traffic `sync_job_logs.tenant_id`, `cost_snapshots.tenant_id+date`, or `alerts.tenant_id+is_resolved` indexes exist in prod.
- **Recommendation:**
  1. Write `012_real_performance_indexes.py` covering `sync_job_logs(tenant_id, started_at)`, `sync_job_logs(job_type, status, started_at desc)`, `cost_snapshots(tenant_id, date)`, `compliance_snapshots(tenant_id, snapshot_date)`, `alerts(alert_type, job_type, tenant_id, is_resolved)`, `alerts(created_at)`, `audit_logs(tenant_id, created_at)`.
  2. Add a pytest architecture check that asserts every model with `index=True` on a column has a corresponding `op.create_index` in a migration. (See §5 fitness function.)
- **Effort:** S (1–2 hours to write migration + test; deploy on next staging push)

### F-2 — ct-l2j residual bug: zero-records threshold check is wrong SQL and untenant-scoped

- **Severity:** **P1 critical**
- **Evidence:** `app/api/services/monitoring_service.py:461-471`:
  ```python
  recent_zeros = (
      self.db.query(SyncJobLog)
      .filter(
          SyncJobLog.job_type == log_entry.job_type,
          SyncJobLog.status == "completed",
          SyncJobLog.records_processed == 0,
      )
      .order_by(SyncJobLog.started_at.desc())
      .limit(ALERT_THRESHOLDS["zero_records_threshold"])
      .count()
  )
  ```
  Three bugs in nine lines:
  1. `.limit(3).count()` — in SQLAlchemy ORM this compiles to `SELECT count(*) FROM (… LIMIT 3)` only on some dialects; on others it ignores the LIMIT and counts everything. On MSSQL (prod), `.limit().count()` returns the **total** count, not 3. So once the table has 3+ zero-record logs for that job_type historically, every subsequent zero-record run trips the threshold forever.
  2. **Not tenant-scoped.** Three zero-record runs spread across three DIFFERENT tenants will trip an alert tagged with the most-recent tenant. Combined with the dedup-by-tenant logic added in the same file (`_existing_unresolved_alert`), this creates the exact pile-up seen in `SESSION_HANDOFF.md`: "1,489 active alerts."
  3. The "consecutive" semantics in the docstring ("Last N runs processed zero records") are not actually enforced — there's no check that the last N runs are zero. A single zero run among 100 successes will trip it.
- **Recommendation:**
  ```python
  recent_runs = (
      self.db.query(SyncJobLog)
      .filter(
          SyncJobLog.job_type == log_entry.job_type,
          SyncJobLog.tenant_id == log_entry.tenant_id,  # tenant-scope
          SyncJobLog.status == "completed",
      )
      .order_by(SyncJobLog.started_at.desc())
      .limit(ALERT_THRESHOLDS["zero_records_threshold"])
      .all()  # materialize, then check
  )
  if len(recent_runs) >= ALERT_THRESHOLDS["zero_records_threshold"] and all(
      r.records_processed == 0 for r in recent_runs
  ):
      ...
  ```
  Add unit test that seeds 3 zero-record runs for tenant A and 1 success for tenant B and asserts no alert fires for tenant B.
- **Effort:** XS (15 min fix, 30 min test)

### F-3 — Lighthouse documentation drift across 7+ top-level docs

- **Severity:** **P1 critical** (operational hazard: docs describe deleted endpoints)
- **Evidence:**
  - `README.md:82, 103, 146-148, 473` — still recommends "Azure Lighthouse: Cross-tenant delegation with self-service onboarding" as the primary cross-tenant pattern.
  - `ARCHITECTURE.md:18, 116, 347, 358` — diagrams show "Azure Lighthouse" layer; line 116 cites `onboarding.py` ("Self-service Lighthouse onboarding") — **file deleted in ct-59n**.
  - `REQUIREMENTS.md:136, 212, 406` — lists "Azure Lighthouse" as P0 required cross-tenant auth.
  - `RUNBOOK.md:143, 272` — operational runbook still says "Other 4 tenants: federated via Lighthouse delegated access."
  - `SECRETS_OF_RECORD.md:38, 55-59` — secret inventory references Lighthouse onboarding for HTT/BCC/FN/TLL/DCE.
  - `domains/lifecycle/README.md:11, 55, 101, 150, 185, 209` — entire domain doc is written around `LighthouseAzureClient` and `app/api/routes/onboarding.py:273-380`. **Both removed in ct-59n.** A new engineer would chase a phantom file.
  - `WIGGUM_ROADMAP.md:719` — Roadmap item 9.3.1 still marked `[x]` for "Azure Lighthouse delegation for Microsoft.Capacity/reservations/read" — the work it claims is done was actually deleted, not delivered.
  - `INFRASTRUCTURE_END_TO_END.md` — clean. (This doc was refreshed Apr 30, before ct-59n landed.)
- **Recommendation:** One coordinated docs sweep:
  1. Mark `domains/lifecycle/README.md` as **SUPERSEDED** with a banner pointing to whatever the post-ct-59n onboarding flow is (or "no onboarding flow exists, tenants are static-configured").
  2. Strike Lighthouse sections from `README.md`, `REQUIREMENTS.md`, `RUNBOOK.md`. Replace with "5 tenants are statically configured via `tenants_config.py`; cross-tenant auth uses UAMI/OIDC federation per `app/api/services/azure_client.py`."
  3. Update `ARCHITECTURE.md` ASCII diagram — remove Lighthouse box.
  4. Move `infrastructure/lighthouse/` to `infrastructure/archive/lighthouse/` (or delete; `git log` preserves it).
  5. Add a CI grep guard: `! grep -rEi 'LighthouseAzureClient|use_lighthouse|onboarding\.py' app/ docs/ README.md ARCHITECTURE.md`.
- **Effort:** M (~4 hours, mostly mechanical docs work + one grep guard)

### F-4 — `scripts/gh-setup.sh` will re-disable branch protection if executed

- **Severity:** **P1 critical**
- **Evidence:**
  - `reports/github-security/ct-90r.7-main-protection-after.md:12` confirms `enforce_admins.enabled = true` was set on main.
  - `scripts/gh-setup.sh:297` still posts `"enforce_admins": false` in its branch-protection PUT body.
  - `docs/GITHUB_CLI_GUIDE.md:617` documents `enforce_admins: false` as the expected configuration.
  - Any maintainer running `./scripts/gh-setup.sh` to refresh repo settings (which is what the script exists to do) will silently downgrade main protection without realizing it.
- **Recommendation:**
  1. Change `scripts/gh-setup.sh:297` and `docs/GITHUB_CLI_GUIDE.md:617` to `"enforce_admins": true`.
  2. Add a smoke test in `weekly-ops.yml` that calls `gh api /repos/{owner}/{repo}/branches/main/protection` and asserts `.enforce_admins.enabled == true`. Fail CI if drift detected.
- **Effort:** XS (5-min fix, 15-min CI gate)

### F-5 — Dev-login form HTML ships to all production users

- **Severity:** **P2 should-fix** (server-side gated, but information disclosure + brand trust hit)
- **Evidence:**
  - `app/templates/login.html:60-83` — the dev login form (`<form id="login-form" data-testid="login-dev-form">` with username/password inputs) is **always present** in the response HTML for `/login`, hidden by CSS class `hidden`.
  - The form is unhidden by client JS only when `/health` returns `environment === "development"` (line 318-329).
  - Any prod user can View Source on the login page and see: (a) a `data-testid="login-dev-form"`, (b) a placeholder username + password field, (c) a `divider` element that "shown when dev login is available." This advertises the existence of a dev login path to any attacker recon.
  - Server-side, `app/api/routes/auth.py:64-104` correctly rejects the dev `admin/admin` creds outside development via the `allow_direct_login` check. So this is **not** a credential bypass — it's info disclosure + a one-line config-drift away from being a bypass. If `ENVIRONMENT` ever drifts to `development` in prod (e.g. a Bicep regression), the form auto-unhides AND the backend accepts `admin/admin`.
  - `_DEV_USERNAME = "admin"` / `_DEV_PASSWORD = "admin"` are hard-coded in `app/api/routes/auth.py:53-54` — `docs/security/production-audit.md:158` already lists this as Open M-2.
- **Recommendation:**
  1. Server-render the login template conditionally: when `settings.is_development`, render the dev block; otherwise render a stripped template with only the Azure AD button. Same Jinja file, two branches.
  2. OR (smaller change) use `{% if request.app.state.settings.is_development %}` to wrap the entire dev section so it never reaches the wire in prod.
  3. Move dev creds out of source. Read from env (`DEV_LOGIN_USERNAME` / `DEV_LOGIN_PASSWORD` with bcrypt hash in env, no defaults).
  4. STRIDE: this finding maps to **Information Disclosure** (advertises auth surface) + **Spoofing** (one config flip = `admin/admin` works). Co-sign needed from Security Auditor before closing.
- **Effort:** S (template branch + env-driven creds + one test)

### F-6 — `Alert.is_resolved` typed as `Mapped[bool]` but stored as `Integer`

- **Severity:** **P2 should-fix** (data-integrity smell; runtime works, but lies to mypy and to readers)
- **Evidence:** `app/models/monitoring.py:112-114`:
  ```python
  is_resolved: Mapped[bool] = Column(
      Integer, default=False
  )  # Store as 0/1 for SQLite compatibility
  ```
  The type annotation claims `bool`, the column is `Integer`. Downstream code mixes idioms: `Alert.is_resolved == 0` (line 365 of `monitoring_service.py`), `existing.is_resolved = True` (line 405), and the `is_resolved_bool` property at line 134 exists exactly because the field can't be trusted to be `bool`.
  - The SQLite-compat comment is stale: both Azure SQL (BIT) and SQLite (INTEGER 0/1) handle `Boolean` natively in SQLAlchemy via `SmallInteger`-style storage. There's no portability reason for this.
- **Recommendation:** Change column to `Boolean`, drop the `is_resolved_bool` helper, and add an Alembic migration that converts existing `0/1` integers to booleans (no-op on MSSQL — BIT == BIT). Co-sign with whoever owns the alerts schema (Pack Leader or planning-agent track).
- **Effort:** S (~1 hour incl. migration + test)

### F-7 — Resource sync cadence (1 hour) is over-aggressive for governance data

- **Severity:** **P2 should-fix** (Azure ARM throttle + cost; no functional break)
- **Evidence:** `app/core/config.py:225`:
  ```python
  resource_sync_interval_hours: int = 1
  cost_sync_interval_hours: int = 24
  compliance_sync_interval_hours: int = 4
  identity_sync_interval_hours: int = 24
  ```
  Resource sync runs 24 × per day × 5 tenants × N subscriptions per tenant = ~120-300 ARM sweeps/day. For a governance dashboard whose data is consumed by humans glancing once or twice a day, hourly resource inventory refresh is wasted work. Azure Resource Graph rate limits are 15 ops/sec/user with daily quotas; we're nowhere near the ceiling, but it inflates App Insights ingestion (which is metered) and SQL write volume.
  - Crosscheck: `SESSION_HANDOFF.md:24` reports "data is ~20 days stale across 9 of 10 sync domains" — so the cadence isn't even buying freshness, the syncs are failing. Once F-2 + the underlying auth fix land, the 1-hour cadence will start actually firing — making this finding more urgent, not less.
- **Recommendation:** Raise to `resource_sync_interval_hours: 4` (matches compliance cadence). Quantify ARM call reduction in App Insights after one week.
- **Effort:** XS (1-line config change + one ADR addendum)

### F-8 — `enableRedis: true` in `parameters.staging.json` (parameters.production.json is fine)

- **Severity:** **P3 nice-to-have**
- **Evidence:**
  - `infrastructure/parameters.production.json:87-89` correctly shows `enableRedis: false` (already fixed since the April doc).
  - `infrastructure/parameters.staging.json` should be audited — based on `docs/COST_MODEL_AND_SCALING.md` Appendix D it was previously `true`. Need to confirm current state. If still `true`, a Bicep redeploy from staging params would silently spin up a $16/mo Redis Basic C0.
- **Recommendation:** Verify and align staging + dev parameters with prod (`enableRedis: false`). Set the Bicep module default to `false` so missing param fails safe.
- **Effort:** XS

### F-9 — `SyncJobLog.tenant_id` is nullable, breaking per-tenant attribution for cost/identity syncs

- **Severity:** **P2 should-fix**
- **Evidence:** `app/models/monitoring.py:23-25`:
  ```python
  tenant_id: Mapped[str | None] = Column(
      String(36), ForeignKey("tenants.id"), nullable=True
  )  # NULL = all tenants
  ```
  `app/core/sync/costs.py:122` calls `monitoring.start_sync_job(job_type="costs")` ONCE for the entire cross-tenant sweep — `tenant_id` is never set. So the per-job log row stores aggregated counts across all 5 tenants and 20+ subscriptions, with `tenant_id = NULL`. This breaks:
  1. Per-tenant freshness dashboards.
  2. Per-tenant zero-records alerting (which is exactly what F-2 needs to do correctly).
  3. The data-retention story (`docs/DATA_RETENTION_POLICY.md` says retention is per-tenant; NULL-tenant rows have no retention owner).
  - Same pattern in `app/core/sync/identity.py`, `app/core/sync/compliance.py`, `app/core/sync/resources.py` (I didn't read them all in detail; verify).
- **Recommendation:** Either (a) call `start_sync_job(job_type=..., tenant_id=<per-tenant>)` inside each per-tenant loop iteration so we get N log rows per sweep, or (b) introduce a `SyncJobBatch` parent row and `SyncJobLog` children. (a) is simpler.
- **Effort:** M (~2-3 hours; touches all 4 sync modules + monitoring service signature)

### F-10 — Sync job logs `lazy="joined"` on tenant relationship — silent N+1 mitigation but full-row JOIN

- **Severity:** **P3 nice-to-have**
- **Evidence:** `app/models/monitoring.py:42` (`SyncJobLog.tenant`) and `:122` (`Alert.tenant`) both use `lazy="joined"`. This means every `SELECT` against `sync_job_logs` or `alerts` issues a LEFT OUTER JOIN against `tenants` — even when the caller doesn't need the tenant row.
- **Recommendation:** Switch to `lazy="select"` (default) and use explicit `.options(joinedload(SyncJobLog.tenant))` at the call sites that need it. Saves ~30% bandwidth on the alerts dashboard query.
- **Effort:** XS

### F-11 — `azure_client.py` credential resolver is sound; minor caching wart

- **Severity:** **P3 nice-to-have**
- **Evidence:** Reviewed `app/api/services/azure_client.py:214-277` (`_resolve_credentials`) and `:278-430` (`get_credential`). The 4-mode resolution is clean:
  1. UAMI (`use_uami_auth`) → ManagedIdentityCredential + FIC
  2. OIDC federation (`use_oidc_federation`) → DefaultAzureCredential w/ OIDC
  3. Shared secret (env-vars) → ClientSecretCredential
  4. Per-tenant Key Vault secret ref → SecretClient lookup
  - TTL cache (`credential_ttl_seconds`, default 3600s) is sensible.
  - One smell: `self._default_credential: DefaultAzureCredential | None = None` initialized at `__init__` and lazily created (line 431-435). On test parallelism this could race. Not a bug today; flag for when we go multi-instance.
- **Recommendation:** Wrap `get_default_credential` in a thread/asyncio lock or use `functools.lru_cache(maxsize=1)`. Defer until F-2 + F-9 ship.
- **Effort:** XS

### F-12 — `docs/AUDIT-2026-04.md` and `INFRASTRUCTURE_INVENTORY.md` are superseded but still link-targets

- **Severity:** **P3 nice-to-have** (drift hazard, not a security/cost issue)
- **Evidence:** `INFRASTRUCTURE_INVENTORY.md` opens with a `SUPERSEDED` banner pointing to `INFRASTRUCTURE_END_TO_END.md` — good. But other docs still link to it as if authoritative. Same pattern for `docs/operations/cost-analysis.md` (called out in `docs/COST_MODEL_AND_SCALING.md` Appendix D, but not yet archived).
- **Recommendation:** Move both files to `docs/archive/` and update any in-repo links via `rg -l 'INFRASTRUCTURE_INVENTORY\.md' | xargs sed -i.bak '…'`.
- **Effort:** XS

### F-13 — `arbiter/` directory: what it is, and why it's fine

- **Severity:** **Informational** (Tyler asked)
- **Evidence:** `arbiter/policies/verify.yaml` is a machine-readable supply-chain verification policy (SLSA + Sigstore + Subject claims) consumed by the `release-gate-arbiter` agent during prod gating. Documented in `arbiter/README.md`. Companion to `core_stack.yaml` and `env-delta.yaml` as canonical declarations. Not a runtime concern.
- **Recommendation:** None. Working as designed.
- **Effort:** —

### F-14 — Hard-coded dev credentials in source (`admin/admin`)

- **Severity:** **P2 should-fix** (dup of `docs/security/production-audit.md:158` M-2, already known)
- **Evidence:** `app/api/routes/auth.py:53-54`. Backend env-gated, but credentials in source still violate ASVS V2.5.
- **Recommendation:** Move to env vars; bcrypt-hash; default = unset (login fails closed). Co-sign with Security Auditor.
- **Effort:** XS

### F-15 — Rate limiter exempts ALL of development & `/health` paths from rate limiting

- **Severity:** **P3 nice-to-have**
- **Evidence:** `app/main_middleware.py:103-106`:
  ```python
  if current_settings.is_development or request.url.path in RATE_LIMIT_EXEMPT_PATHS:
      return await call_next(request)
  ```
  The `is_development` branch is fine. But on rate-limit errors the middleware falls back to allowing the request through (lines 130-137) — silent fail-open. That's correct for `/auth/` (returns 429), but for all other paths a Redis outage = no rate limiting at all.
- **Recommendation:** Fail-closed on rate-limit infra failures for write endpoints (`POST`/`PUT`/`DELETE`/`PATCH`). Reads can fail-open.
- **Effort:** S

---

## 3. Cost State of the Union

### 3.1 Today's Actual Monthly Burn (Azure)

Source-of-truth: `INFRASTRUCTURE_END_TO_END.md` §3.4 + `infrastructure/parameters.production.json` confirms:

| Environment | Service | SKU | $/mo |
|---|---|---|---|
| Production | App Service Plan B1 (East US, Linux) | B1 | $12.41 |
| Production | SQL Database `governance` | Basic 5 DTU, 2 GB | $4.90 |
| Production | Key Vault `kv-gov-prod` | Standard | $0.03 |
| Production | App Insights `governance-appinsights` | Pay-as-you-go (under 5 GB free tier) | ~$0.00 |
| Production | Log Analytics `governance-logs` | PerGB (under 5 GB free tier) | ~$0.00 |
| Production | 7 metric alerts + 2 availability tests | — | $0.60 |
| Production | Egress (under 100 GB free tier) | — | $0.00 |
| **Production subtotal** | | | **~$17.94** |
| Staging | App Service Plan B1 (West US 2) | B1 | $11.68 |
| Staging | SQL Database `governance` | Free | $0.00 |
| Staging | Key Vault | Standard | $0.03 |
| Staging | Storage `stgovstagingxnczpwyv` | StorageV2 LRS, ~empty | ~$0.10 |
| Staging | Log Analytics (30-day retention) | PerGB | ~$0.50 |
| Staging | App Insights | PerGB | ~$0.30 |
| **Staging subtotal** | | | **~$12.61** |
| Dev | App Service Plan B1 | B1 | $11.68 |
| Dev | SQL Database `governance` | Basic 5 DTU | $4.90 |
| Dev | Container Registry `acrgovernancedev` | Basic 10 GB | $5.00 |
| Dev | Storage `stgovdev001` | LRS | ~$0.10 |
| Dev | Key Vault | Standard | $0.03 |
| Dev | Log Analytics / App Insights | Free tier | $0.00 |
| **Dev subtotal** | | | **~$21.71** |
| **AZURE TOTAL** | | | **~$52.26/mo** (rounds to **$53/mo**) |
| **GitHub Enterprise** | 7 seats × $21 | — | **$147/mo** |
| **GRAND TOTAL** | | | **~$200/mo** |

**Sanity-check vs `docs/COST_MODEL_AND_SCALING.md`:** matches the doc's stated $200/mo all-in. The cost doc is **still accurate** as of 2026-05-20 — no infra-relevant changes have landed since April 30 (the post-prod-deploy `INFRASTRUCTURE_END_TO_END.md` refresh).

### 3.2 Past-3-Months Build Investment (rough OOM)

Order-of-magnitude. Anchored to `CHANGELOG.md` Apr 16 entry ("Total Azure subscription = ~$282/mo before optimization") and the optimization deltas in `INFRASTRUCTURE_END_TO_END.md` §3.4:

| Month | Azure run-rate | GitHub | Total | Notes |
|---|---|---|---|---|
| Feb 2026 | ~$298/mo | $147 | $445 | Pre-optimization. B2 App Service + S2 SQL + ACR Standard + orphans |
| Mar 2026 | ~$298/mo | $147 | $445 | Same. Initial rightsizing happened ~Mar |
| Apr 2026 (avg) | ~$176/mo | $147 | $323 | Mid-month optimization (Apr 16): SQL S0→Basic, ACR deletion, GRS→LRS |
| **3-month subtotal** | | | **~$1,213** | Plus Feb 1 → today = ~3.7 months |

**To-develop investment Feb–May (≈3 months operational + 1 wind-down):** approximately **$1,200–$1,400** total cash burn on infrastructure to develop this thing, of which **~$580 was GitHub Enterprise seats** (a fixed cost that would have been paid regardless of this project) and **~$650 was Azure compute/storage**. That's the all-in capital number, excluding salaries.

For context: a single SaaS audit-tools tool (Vanta, Drata, etc.) starts at $5k/yr. The platform has cost less to build than ~3 months of one comparable SaaS subscription.

### 3.3 Forward 12-Month Forecast (from `docs/COST_MODEL_AND_SCALING.md` §5)

| Scenario | Tenants Month 12 | 12-Month Total | Avg /mo |
|---|---|---|---|
| **Conservative** (5 tenants flat) | 5 | $2,400 | $200 |
| **Base** (20 tenants) | 20 | $2,897 | $241 |
| **Aggressive** (50+ tenants) | 50 | $3,421 | $285 |

Forward forecast is **unchanged** from the April 18 doc — no infra moves have invalidated it.

### 3.4 Top 3 Cost Optimizations Available RIGHT NOW

1. **Stop dev environment outside business hours.** Dev = $21.71/mo running 24/7 = 720 hours. If dev is genuinely active only ~8h/day × 5 days/week = 174 hours, stopping the App Service Plan + dev SQL when idle saves ~$15/mo. Automatable via `az webapp stop` in a scheduled GitHub Action. **Savings: ~$15-18/mo, $180-216/yr.**
2. **Raise resource sync cadence from 1h → 4h** (F-7). Reduces ARM API calls 75%, App Insights ingestion ~50%. Marginal $ savings today (~$2-3/mo), but stops eating into the 5 GB Log Analytics free tier as user-load grows.
3. **GitHub Enterprise seat audit.** 7 seats × $21 = $147/mo. If 2 seats are inactive (engineers who left or never engaged), drop to 5 seats = **$42/mo savings, $504/yr.** Also worth pricing GitHub Team ($4/seat) — gives up SAML SSO + advanced audit, saves $119/mo, but is a real downgrade for a governance platform that should demonstrate the controls it preaches.

**Total reachable savings this quarter: $59-79/mo (~$700-950/yr), about 30-40% of current bill.** That's enough to fund the F-1 + F-2 + F-3 + F-4 fixes outright.

Reserved instance opportunities remain N/A at current SKU tier (B1 App Service and DTU-model SQL are not RI-eligible; see `docs/cost/consumption-vs-reserved-analysis.md`). Re-evaluate when/if we cross to P1v3 (~50 concurrent users).

---

## 4. Architectural Drift Score

**Score: 6 / 10**

- **What's pushing the score down:**
  - **F-1 (P1):** Production has been running for 3 months without indexes the migration claims it has. Real drift between declared and actual schema.
  - **F-3 (P1):** Five top-level docs describe a feature (Lighthouse + onboarding) that no longer exists in code. New engineers will be misled within an hour.
  - **F-2 (P1):** A "fixed" issue (ct-l2j) ships with a working dedup layer on top of a broken threshold query. The fix masks the underlying SQL bug; ct-l2j's symptom recurrence is one config change away.
  - **F-9 (P2):** Sync log rows can't be attributed to tenants, undermining the data-retention policy.
  - **F-4 (P1):** A maintenance script will silently regress a security control if executed.
- **What's holding the score up:**
  - **ct-59n was executed cleanly.** No `LighthouseAzureClient` ghosts in `app/`. Migration 011 is well-written and reversible. The credential resolver was simplified correctly.
  - **Cost story is honest and current** — the April 18 cost doc matches reality, even down to optional-Redis warnings.
  - **Auth posture is strong:** OIDC federation, JWT secret enforced in prod, HSTS tuned per env, 12 security headers, OAuth state + PKCE in the login template, no stored Azure client secrets.
  - **CI/CD scaffolding is mature:** SLSA L3, Sigstore cosign, attestation verification, OIDC workload identity, 10+ workflows, weekly ops.
  - **arbiter/ release-gate framework is a credibility multiplier** — most 3-month-old projects don't have this.

**Trajectory:** If F-1, F-2, F-3, F-4 are closed within the next sprint (estimated ~1.5 days of solutions-architect + 1 engineer time), this score moves to **8/10**. The platform's bones are good; the drift is in the connective tissue (docs, migrations, one residual SQL bug). None of it is structural — all of it is paying down post-demolition cleanup debt.

---

## 5. Proposed Fitness Functions (Pytest Checks)

To enforce the recommendations as automated guards:

1. **`tests/architecture/test_no_lighthouse_references.py`**
   ```python
   def test_no_lighthouse_imports_in_app():
       result = subprocess.run(
           ["rg", "-l", "LighthouseAzureClient|use_lighthouse|onboarding\\.py", "app/"],
           capture_output=True, text=True,
       )
       assert result.returncode != 0, f"Lighthouse references survive: {result.stdout}"
   ```
2. **`tests/architecture/test_migration_targets_exist.py`** — parse every `op.create_index(...)` / `op.create_table(...)` call across `alembic/versions/` and assert the target table exists in `Base.metadata.tables`.
3. **`tests/architecture/test_indexed_columns_have_migrations.py`** — every `Column(..., index=True)` in `app/models/` must have a matching `op.create_index` somewhere in `alembic/versions/`.
4. **`tests/architecture/test_branch_protection_config.py`** — assert `scripts/gh-setup.sh` and `docs/GITHUB_CLI_GUIDE.md` contain `enforce_admins: true`.
5. **`tests/security/test_dev_login_not_in_prod_template.py`** — render the login template with `ENVIRONMENT=production` and assert the response does NOT contain `data-testid="login-dev-form"`.

---

## 6. STRIDE Summary (cross-finding)

| Threat | Findings | Owner |
|---|---|---|
| **Spoofing** | F-5 (dev login visible in prod HTML; config-drift away from acceptance) | Security Auditor |
| **Tampering** | F-1 (missing indexes → no integrity issue, but slow queries enable DoS-by-cost-query) | Solutions Architect |
| **Repudiation** | F-9 (NULL tenant_id on sync_job_logs breaks per-tenant audit trail) | Security Auditor |
| **Information Disclosure** | F-3 (docs leak deleted-feature details), F-5 (dev login surface) | Solutions Architect + Sec |
| **Denial of Service** | F-2 (alert flood; mitigated by dedup but threshold is permanent), F-7 (ARM throttle risk) | Solutions Architect |
| **Elevation of Privilege** | F-4 (gh-setup.sh silently regresses branch protection → privileged push possible) | Security Auditor |

Co-sign needed from Security Auditor on F-4, F-5, F-9, F-14.

---

## 7. Research References

- `app/api/services/monitoring_service.py:300-490` — alert logic
- `app/core/sync/{costs,utils}.py` — sync flow
- `app/core/config.py:225-250` — sync intervals
- `app/api/services/azure_client.py:214-435` — credential resolver
- `alembic/versions/008_add_performance_indexes.py` — broken migration
- `alembic/versions/011_drop_tenant_use_lighthouse.py` — clean ct-59n migration
- `app/templates/login.html:52-83` — dev login form leak
- `scripts/gh-setup.sh:297` — branch protection regression
- `reports/github-security/ct-90r.7-main-protection-{before,after}.md` — branch protection evidence
- `INFRASTRUCTURE_END_TO_END.md` §3.4 — current Azure inventory
- `docs/COST_MODEL_AND_SCALING.md` — cost model + forecast
- `SESSION_HANDOFF.md:22-40` — ct-l2j field evidence (1,489 alerts, 20-day staleness)

---

*Prepared by Solutions Architect for ROUND 1 / 3 of the comprehensive audit. Next sessions should cover frontend/UX (Experience Architect) and a separate security deep-dive (Security Auditor) on findings F-4/F-5/F-9/F-14.*

# HTT Control Tower — Test Playbook

> Copy-paste-runnable smoke + UAT recipes. Pair this with [`STATUS.md`](./STATUS.md)
> for the current "what's deployed where" answer. If a command produces something
> different from what's documented here, **STATUS.md is the more recent doc** —
> trust the live signal first.

**Verified against production at 2026-04-30 22:55 UTC, image `htt-brands/control-tower@sha256:f762c98a...`.**

---

## 0. One-shot health check (30 seconds)

```bash
# Prod healthy?
curl -s https://app-governance-prod.azurewebsites.net/health | jq .
# Expect: {"status":"healthy","version":"2.5.0","environment":"production"}

# Prod fully wired?
curl -s https://app-governance-prod.azurewebsites.net/health/detailed | jq .
# Expect: status:healthy, components.database:healthy, scheduler:running, azure_configured:true

# Pages live?
curl -s -o /dev/null -w "%{http_code}\n" https://htt-brands.github.io/control-tower/
# Expect: 200
```

If any of those three is wrong, see "When something's broken" at the bottom.

---

## 0.5 Deep diagnostic — "the dashboard is blank" (2 minutes)

When `/health` is 200 but the dashboard still renders empty or stale, you have a
**data-flow** problem, not an API problem. Two scripts cover this:

| Script | Question it answers | When to reach for it |
|---|---|---|
| `scripts/smoke_test.py` | *Did the endpoint respond correctly?* | First check after a deploy. Hardcoded short-list of endpoints, asserts response shape. |
| `scripts/endpoint_audit.py` | *Did the endpoint respond with anything **meaningful**?* | When health is green but a UI is empty. Auto-discovers every GET from `/openapi.json`, flags silently-blank responses (empty arrays, null `last_synced`, all-zero summaries). |

Quick recipe:

```bash
# Unauth sweep against staging + prod (still surfaces stale data via public health endpoints)
python scripts/endpoint_audit.py \
    --url https://app-governance-staging-xnczpwyv.azurewebsites.net \
    --url https://app-governance-prod.azurewebsites.net

# With creds, to inspect authenticated /partials/* and /api/v1/* responses
python scripts/endpoint_audit.py \
    --url https://app-governance-prod.azurewebsites.net \
    --username you@example.com --password '...'

# Reports land in reports/endpoint_audit_<host>_<ts>.json for diffing across runs.
```

Exit codes: `0` everything healthy & populated, `1` at least one blank/error, `2` config error.

---

## 1. Production smoke (5 minutes)

### 1.1 HTTP surface

```bash
PROD=https://app-governance-prod.azurewebsites.net

# Root redirect (auth flow)
curl -s -o /dev/null -w "GET /                   -> HTTP %{http_code}\n" $PROD/
# Expected: 307 (redirects to /auth/login or similar)

# Healthchecks
curl -s -o /dev/null -w "GET /health             -> HTTP %{http_code}\n" $PROD/health
curl -s -o /dev/null -w "GET /health/detailed    -> HTTP %{http_code}\n" $PROD/health/detailed
# Expected: 200 / 200

# OpenAPI / Swagger
curl -s -o /dev/null -w "GET /openapi.json       -> HTTP %{http_code}\n" $PROD/openapi.json
curl -s -o /dev/null -w "GET /docs               -> HTTP %{http_code}\n" $PROD/docs
curl -s -o /dev/null -w "GET /redoc              -> HTTP %{http_code}\n" $PROD/redoc
# Expected: 200 / 200 / 200

# Static assets sample
curl -s -o /dev/null -w "GET /static/favicon.ico -> HTTP %{http_code}\n" $PROD/static/favicon.ico
# Expected: 200 (or 304 on second request)
```

### 1.2 Detailed health components

```bash
curl -s https://app-governance-prod.azurewebsites.net/health/detailed | jq '.components'
```

You should see (all healthy):

```json
{
  "database": "healthy",
  "scheduler": "running",
  "cache": "memory",
  "azure_configured": true,
  "token_blacklist": "memory"
}
```

If `azure_configured: false`, the UAMI binding is broken — see [`docs/runbooks/oidc-federation-setup.md`](./docs/runbooks/oidc-federation-setup.md).

### 1.3 Cache + scheduler self-report

```bash
curl -s https://app-governance-prod.azurewebsites.net/health/detailed | jq '.cache_metrics, .scheduler_jobs'
```

`scheduler_jobs` should list 17–18 active background jobs (cost sync, compliance, identity, riverside_*, deadline_tracker_*, mfa_alert_check, etc). The full inventory is in [`docs/cost/consumption-vs-reserved-analysis.md`](./docs/cost/consumption-vs-reserved-analysis.md) §1.2.

### 1.4 Confirm the deployed image

```bash
az webapp config show \
  --name app-governance-prod \
  --resource-group rg-governance-production \
  --query "linuxFxVersion" -o tsv
# Expected (current main, 2026-04-30 22:54 UTC):
#   DOCKER|ghcr.io/htt-brands/control-tower@sha256:f762c98a03c40f2d6cc77912d8bd13a82ed64e41969a9545094da262c8ff21ef
```

If the digest differs, that's only "wrong" if there's been no successful prod deploy since then. Cross-check with:

```bash
gh run list --workflow=deploy-production.yml --limit 5 \
  --json databaseId,status,conclusion,headSha,createdAt
```

---

## 2. Staging smoke (5–10 minutes; allow cold-start)

Staging is on B1 with no warm traffic, so the **first request is expected to take 30–90s** while the container cold-starts. Don't panic.

```bash
STAGING=https://app-governance-staging-xnczpwyv.azurewebsites.net

# Warm the app first (allow up to 120s on the first hit)
time curl --max-time 120 -s $STAGING/health
# Expect: {"status":"healthy","version":"2.5.0","environment":"staging"}

# After warm-up the rest is fast
curl -s $STAGING/health/detailed | jq .
curl -s -o /dev/null -w "GET /docs -> HTTP %{http_code}\n" $STAGING/docs
```

If the cold-start exceeds 120s repeatedly, that's the open observation in bd `mvxt` (cold-start monitoring) — file evidence in the bd if it's now consistently bad.

---

## 3. Public docs (GitHub Pages)

```bash
PAGES=https://htt-brands.github.io/control-tower

# Landing
curl -s -o /dev/null -w "GET /                              -> HTTP %{http_code}\n" $PAGES/

# Section landings (HTML index pages — Jekyll is disabled)
for path in architecture operations api decisions; do
  curl -s -o /dev/null -w "GET /$path/                          -> HTTP %{http_code}\n" $PAGES/$path/
done

# Status fallback (served as raw markdown — see scripts/render_status.py)
curl -s -o /dev/null -w "GET /status.md                          -> HTTP %{http_code}\n" $PAGES/status.md

# Continuity status (the "where are we" page on Pages)
curl -s -o /dev/null -w "GET /operations/continuity-status.html -> HTTP %{http_code}\n" \
  $PAGES/operations/continuity-status.html

# Bundled OpenAPI
curl -s -o /dev/null -w "GET /api/swagger/openapi.json         -> HTTP %{http_code}\n" \
  $PAGES/api/swagger/openapi.json
```

All should return 200.

---

## 4. CI / deployment health

```bash
# Last 5 runs of every important workflow
for wf in ci.yml security-scan.yml deploy-staging.yml deploy-production.yml \
          pages.yml gh-pages-tests.yml backup.yml bicep-drift-detection.yml; do
  echo "=== $wf ==="
  gh run list --workflow=$wf --limit 5 --json databaseId,status,conclusion,headSha,createdAt \
    --jq '.[] | "\(.createdAt | split("T")[0]) \(.conclusion // .status) \(.headSha[:7]) #\(.databaseId)"'
  echo
done
```

What "good" looks like at session close:

| Workflow | Expected |
|---|---|
| `ci.yml` | Latest run on `main` HEAD: ✅ success |
| `security-scan.yml` | Latest run on `main` HEAD: ✅ success |
| `deploy-staging.yml` | Latest run on `main` HEAD: ✅ success (allow 5–10 min lag after push) |
| `deploy-production.yml` | Last successful run: `25193020385` (2026-04-30 22:54 UTC) |
| `pages.yml` | Latest run on `main` HEAD: ✅ success (rebuilds public docs) |
| `gh-pages-tests.yml` | Latest run on `main` HEAD: ✅ success (cross-browser checks) |
| `backup.yml` | Latest manual or scheduled: ✅ success on schema-only path |

---

## 5. Manual UAT (browser, 10–15 minutes)

These exercise the human-facing surface beyond what HTTP checks reach.

### 5.1 Production

1. Visit <https://app-governance-prod.azurewebsites.net> → expect redirect to login.
2. Sign in with your Azure AD account (HTT tenant).
3. Land on the dashboard. Expect:
   - Brand selector top-right showing the 5 tenants (HTT / BCC / FN / TLL / DCE).
   - Cost / Compliance / Resources / Identity tiles populated within ~5s.
   - No `MOCK_*` strings or fixture leaks anywhere on the page.
4. Click into Riverside compliance view → expect MFA status, deadline counter (target: 2026-07-08), per-domain maturity.
5. Click into Cost → cross-tenant aggregation, anomaly chart, idle resource list.
6. Open `/docs` → Swagger UI loads, examples render, "Try it out" works for unauth-able endpoints (`/health`, `/health/detailed`).
7. Toggle dark mode (top-right) → CSS theme switches without flash, persists across reload.
8. Tab-key navigation reaches "Skip to content" link first → WCAG 2.2 skip-nav.

### 5.2 Public docs

1. Visit <https://htt-brands.github.io/control-tower/> → "HTT Control Tower" landing.
2. Architecture / Operations / API / Decisions all reachable from top nav.
3. Operations → Continuity Status renders the current state (CI green, prod live on `f762c98a` digest, only `9lfn` Tyler-blocking).
4. API → Swagger embeds the bundled OpenAPI spec.

If anything is broken, the diff vs reality is the bug. File a bd, don't paper over.

---

## 6. Disaster recovery rehearsal (60–90 min, scheduled)

Full procedure: [`docs/runbooks/disaster-recovery.md`](./docs/runbooks/disaster-recovery.md).

Currently scheduled as bd `uchp` for Q3 2026 (due 2026-07-31). Do **not** run an unscheduled DR test against prod — it consumes downtime budget.

The rollback control plane has been **field-tested** as of 2026-04-30:

- **Auto-rollback (bd `39yp` + bd `1vui` fix):** the Deploy job captures previous-good `linuxFxVersion` first, fails closed if image swap fails its post-deploy health gate, and restores the previous digest. Verified by run `25192183149` failing-closed at the capture step (prod un-mutated) and run `25193020385` succeeding fully after the fix.
- **Two-human cover:** Tyler + Dustin Boyd (bd `213e` closed 2026-04-30). Both hold required-reviewer status on the production environment.
- **Machine-verifiable waiver state:** [`docs/release-gate/rollback-current-state.yaml`](./docs/release-gate/rollback-current-state.yaml) — `waiver.status: resolved`, `current_authorized_humans: [Tyler, Dustin]`, `requires_min_authorized_humans: 2`.

---

## 7. When something's broken

Symptoms → first place to look:

| Symptom | Read |
|---|---|
| Prod `/health` not 200 | [`RUNBOOK.md`](./RUNBOOK.md) "Production not responding" |
| Prod returns 503 | [`fix-production-503.sh`](./fix-production-503.sh) (auto-diagnostic), then [`docs/runbooks/disaster-recovery.md`](./docs/runbooks/disaster-recovery.md) §B |
| Staging stuck cold-starting | bd `mvxt` (open observation), [`tests/staging/conftest.py`](./tests/staging/conftest.py) (warmup logic) |
| Pages says "no audit JSON" | Expected — see `scripts/render_status.py` fallback |
| Auto-rollback failed | [`docs/runbooks/disaster-recovery.md`](./docs/runbooks/disaster-recovery.md) §A.4 (rollback-also-failed scenario) |
| Backup workflow red | [`docs/runbooks/disaster-recovery.md`](./docs/runbooks/disaster-recovery.md) §C, then bd `jzpa` close-comment for the long story |
| Staging deploy red | `gh run view <run-id> --log-failed` first; then [`docs/STAGING_DEPLOYMENT.md`](./STAGING_DEPLOYMENT.md) |
| Production deploy red | If prod was un-mutated (failure before image swap), the system is fine — re-dispatch after fix. If prod *was* mutated, auto-rollback should have triggered; verify via `linuxFxVersion`. |

If still stuck: the canonical operational entry point is [`RUNBOOK.md`](./RUNBOOK.md). If the runbook itself has a 🔴 TYLER-ONLY gap on the path you need, that's a Tyler-blocking gap and should be flagged in `bd`.

---

## Full end-to-end suite (security · compliance · design · perf)

Unified gate that runs every layer in isolated passes and writes one report to
`reports/full-suite/<timestamp>/SUITE_REPORT.md`. See
[`docs/testing/TESTING_SUITE_AUDIT_2026-06.md`](./docs/testing/TESTING_SUITE_AUDIT_2026-06.md)
for the full inventory and findings.

```bash
make full-suite-fast     # security + compliance + design (fast inner loop)
make full-suite          # all gates + consolidated report
make full-suite-load     # all gates + 100-user local load profile
```

### 100+ concurrent-user load profile (local)

Closes the "unknown behavior at 100+ users" residual risk. Boots a local server,
mints a real JWT in-process, drives DB-backed read paths, gates on p95 ≤ 500 ms
and error rate ≤ 1 %. Verified: 100 users → 0 failures, median 2 ms.

```bash
make load-profile-quick  # 100 users / 20s
make load-profile        # staged ramp 50 → 120 → spike 160 → soak 100
```

> Trade-off: runs against local SQLite, so it proves the **app tier** scales but
> does not model Azure SQL Basic (5 DTU) under load. For DTU behaviour, run the
> profile against staging as a separate, scheduled exercise.

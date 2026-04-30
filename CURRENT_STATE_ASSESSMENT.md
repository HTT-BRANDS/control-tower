# Current State Assessment — HTT Control Tower

**Assessment Date:** 2026-04-30 22:55 UTC
**HEAD assessed:** [`6c75220`](https://github.com/HTT-BRANDS/control-tower/commit/6c75220) on `main` (`docs(session): record prod-deploy success + bd 1vui field-test cycle`)
**Source-of-truth siblings:** [`STATUS.md`](./STATUS.md) (single-glance), [`SESSION_HANDOFF.md`](./SESSION_HANDOFF.md) (in-flight detail), `bd ready` (live work backlog).

> Reality dashboard. If a row says "green" it has a run ID. If a row says
> "blocked" it has a named blocker. We are not doing decorative confetti.

---

## TL;DR

**Production live, healthy, on current `main`.** The 2026-04-30 prod deploy off `main` cleared Condition 1 of the v2.5.1 internal rehearsal verdict. Auto-rollback was field-tested (bd `1vui` discovered + fixed in flight; safety property held — prod was never mutated by the failed first attempt). Only one Tyler-only gate (bd `9lfn`) remains for full v2.5.1 PASS.

- Prod `/health` ✅ — `healthy / 2.5.0 / production`
- Prod image ✅ — `ghcr.io/htt-brands/control-tower@sha256:f762c98a…` (post-rebrand canonical GHCR path)
- Staging `/health` ✅ — `healthy / 2.5.0 / staging` (allow 30–90s cold-start on first hit)
- GitHub Pages ✅ — HTTP 200, refreshed in this same commit
- v2.5.1 release-gate ✅ — internal verdict `PASS-pending-9lfn`
- Bus-factor ✅ — Tyler + Dustin Boyd both authorized rollback humans (bd `213e`)
- Backup ✅ — schema-only validation green on staging + prod (bd `jzpa`)

---

## Live environment checks

| Surface | URL | Status (2026-04-30 22:55 UTC) |
|---|---|---|
| **Production** | <https://app-governance-prod.azurewebsites.net/health> | ✅ `{status:healthy, version:2.5.0, environment:production}` |
| **Production deep** | <https://app-governance-prod.azurewebsites.net/health/detailed> | ✅ database/scheduler/cache/azure_configured all healthy |
| **Production OpenAPI** | <https://app-governance-prod.azurewebsites.net/openapi.json> | ✅ live (auto-pulled into Pages on every Pages deploy) |
| **Staging** | <https://app-governance-staging-xnczpwyv.azurewebsites.net/health> | ✅ healthy after warm-up; first-hit cold-start can hit 30–90s on B1 |
| **GitHub Pages** | <https://htt-brands.github.io/control-tower/> | ✅ HTTP 200, title "HTT Control Tower" |
| **Continuity Pages section** | <https://htt-brands.github.io/control-tower/operations/continuity-status.html> | ✅ refreshed 2026-04-30 |

---

## Deployed image (current prod state)

```
linuxFxVersion: DOCKER|ghcr.io/htt-brands/control-tower@sha256:f762c98a03c40f2d6cc77912d8bd13a82ed64e41969a9545094da262c8ff21ef
Last modified : 2026-04-30T22:50:58 UTC
SKU           : Linux container, Basic B1, 1 instance
State         : Running
```

Primary proof run: [`25193020385`](https://github.com/HTT-BRANDS/control-tower/actions/runs/25193020385) (built + deployed from commit `9ccd870`, 9m 52s wall-clock). All 6 jobs ✅: QA Gate, Security Scan, Build & Push to GHCR, Deploy to Production, Production Smoke Tests, Notify Teams.

---

## Latest relevant GitHub Actions

| Workflow | Run | Conclusion | What it proves |
|---|---:|---|---|
| Deploy to Production | [`25193020385`](https://github.com/HTT-BRANDS/control-tower/actions/runs/25193020385) | ✅ success | v2.5.1 prod-gate proof run; auto-rollback active (with bd `1vui` fix). Built + deployed from `9ccd870` in 9m 52s. |
| Deploy to Production (prior) | [`25192183149`](https://github.com/HTT-BRANDS/control-tower/actions/runs/25192183149) | ❌ failure | First attempt of the day; failed at auto-rollback prev-image-capture step (bd `1vui`). Prod un-mutated — fail-closed property held. Replaced 35 min later by `25193020385`. |
| Database Backup (prod manual) | [`25171354807`](https://github.com/HTT-BRANDS/control-tower/actions/runs/25171354807) | ✅ success | Schema-only prod backup created, uploaded, verified, retention-cleaned, firewall cleanup ok. |
| Database Backup (staging manual) | [`25169438794`](https://github.com/HTT-BRANDS/control-tower/actions/runs/25169438794) | ✅ success | Schema-only staging backup end-to-end after `AZURE_STORAGE_KEY` ephemeral derivation fix. |
| Deploy to Staging | latest on `main` HEAD | ✅ expected | Re-runs on every push touching app code. |
| CI / Security Scan / Pages / gh-pages-tests | latest on `main` HEAD | ✅ expected | Mainline gates re-run on every push; cross-browser checks gate Pages. |
| Bicep Drift Detection | weekly schedule (Mon 13:00 UTC) | ⏳ no drift expected | Issue auto-rolling if drift; Teams ping when webhook configured. |

---

## v2.5.1 release-gate state

Internal rehearsal verdict ([`docs/release-gate/verdicts/rehearsal-2026-04-30-internal.md`](./docs/release-gate/verdicts/rehearsal-2026-04-30-internal.md)) post-prod-deploy success:

| Pillar | Verdict | Movement |
|---|---|---|
| 1. Requirements Closure | ✅ PASS | CONDITIONAL_PASS (retroactive RTM) → PASS (RTM-v2.5.1-DRAFT expanded to 56 tickets / 8 themes) |
| 2. Code Review | ✅ PASS | unchanged |
| 3. Security | ✅ PASS | DEGRADED → PASS (env-delta validator + supply-chain hardening) |
| 4. Infrastructure | ✅ PASS | CONDITIONAL_PASS → **PASS** (cleared 2026-04-30 22:54 UTC by run `25193020385`; prod now on post-rebrand GHCR path) |
| 5. Stack Coherence | ✅ PASS | unchanged |
| 6. Cost | ✅ PASS | with observation → PASS (cost analysis bd `j6tq` closed; B1 vs Container Apps decision-ready) |
| 7. Maintenance & Operability | ✅ PASS | CONDITIONAL_PASS → PASS (bus-factor 1→2 via bd `213e`) |
| 8. Rollback | ✅ PASS | PASS → **PASS (++ field-tested)** via bd `1vui` discover/fix/redeploy cycle |

**Overall:** `CONDITIONAL_PASS` → **`PASS-pending-9lfn`**.

---

## Current work queue

`bd ready` (2026-04-30 22:55 UTC):

| bd | Priority | Owner | Status |
|---|---|---|---|
| `9lfn` | **P1** | **Tyler-only** | Author `SECRETS_OF_RECORD.md` non-secret inventory. ~30 min. The last v2.5.1 gate condition. |
| `uchp` | P2 | Tyler / Dustin | Q3 2026 quarterly DR test cycle. Due 2026-07-31. |
| `l96f` | P3 | next-puppy | Rotate JWT `iss` claim from `azure-governance-platform` → `control-tower`. Cleanup, not blocking. |
| `rtwi` | P3 | next-puppy | Stop domain-intelligence App Service / pause PG if zero-traffic at 60-day mark (~2026-05-17). |
| `m4xw` | P4 | next-puppy | Automate quarterly audit-log archive to Azure Blob Archive tier. |

Operationally blocked:

| bd | Blocker |
|---|---|
| `cz89` | BACPAC export workflow exists, but staging Azure SQL Free edition does not support ImportExport. Decision required in [`docs/dr/bacpac-validation-decision.md`](./docs/dr/bacpac-validation-decision.md). |

Recently closed (last 48h): `0nup`, `213e`, `39yp`, `j6tq`, `jzpa`, `1vui`, `fifh`, `0dsr`, `re42`, `aiob` (and 5 sub-issues), `fbx8` Riverside scheduler split, `gvpt` cache split, `wnpf` admin risk split, `a3oq` Riverside sync split, `tg2z` DMARC investigation.

---

## Backup / RPO truth

Schema-only database backup is fully green on both environments. The earlier failures (which spanned ~5 days of debugging) remain documented because receipts matter and amnesia is not observability:

1. `fifh` fixed the broken `mda590/teams-notify` action pattern.
2. `3flq` fixed OIDC `id-token` permission for Azure login.
3. Run `25145371945` then exposed missing `DATABASE_URL` / `AZURE_STORAGE_ACCOUNT` GitHub environment secret names.
4. On 2026-04-30, both names were configured for production and staging without printing values.
5. Production storage account `stgovprodbkup001` was created in `rg-governance-production`.
6. Manual validation runs `25167657417` / `25167659155` exposed missing runner SQL tooling: optional `mssqlscripter` and ODBC Driver 18.
7. `backup_database.py` now falls back to SQLAlchemy; `backup.yml` installs `msodbcsql18` / `unixodbc-dev` before running `pyodbc`.
8. Validation runs `25168192604` / `25168194585` / `25168804362` moved past ODBC. Staging then failed Blob upload on `AuthorizationPermissionMismatch` even after Storage Blob Data Contributor was granted. Workflow now derives an ephemeral `AZURE_STORAGE_KEY` after OIDC login.
9. **Staging schema backup passed end-to-end in run `25169438794`.**
10. Production then created, uploaded, verified, and completed retention cleanup in run `25171161761`; only the firewall cleanup step failed because `az sql server firewall-rule delete` does not support `--yes`.
11. The leftover firewall rule was removed manually, the unsupported flag was removed from `backup.yml`, and **production validation passed end-to-end in run `25171354807`.** No temporary `GitHubActions-*` SQL firewall rules remained.
12. bd `jzpa` is closed.

Long-form BACPAC validation (bd `cz89`) is the only DR item still operationally blocked — see [`docs/dr/bacpac-validation-decision.md`](./docs/dr/bacpac-validation-decision.md) for options.

---

## Auto-rollback field-test (the bd `1vui` story, captured for posterity)

Auto-rollback was merged earlier (bd `39yp`, commit `d9d9d88`) and the rehearsal verdict's §N-2 explicitly flagged "merged but not yet field-tested" as a non-blocking risk. The first prod deploy of the day (run `25192183149`) exercised that path for real and surfaced a 76-char-wrap bug invisible to macOS-only local testing of the original auto-rollback PR.

**The safety property held.** Failure occurred at the very first step of the Deploy job ("Capture previous-good container image"), *before* any `az webapp config container set` call. Production `/health` returned 200 OK with `version 2.5.0` throughout the failure window. This is exactly the auto-rollback contract: fail-closed before touching Azure.

**Resolution timeline:**

| Time (UTC) | Event |
|---|---|
| 22:20 | Tyler dispatched run `25192183149` against `main` (`ec9658f`) |
| 22:40 | Deploy job ❌ at first step (bd `1vui` — GNU `base64` line-wrap) |
| 22:41 | Verified prod un-mutated; filed bd `1vui` (P1) |
| 22:43 | Fix landed in commit `9ccd870` (`base64 -w0`) |
| 22:44 | Re-dispatched → run `25193020385` against `9ccd870` |
| 22:54 | All 6 jobs ✅ in 9m 52s; bd `1vui` closed |
| 22:55 | Bundle + verdict updates committed (`8cf67e5`) |

Risk N-2 is now retired with field evidence.

---

## Public docs / Pages freshness

GitHub Pages was rebuilt by this commit. Refreshed surfaces:

- [`docs/index.md`](./docs/index.md) — landing
- [`docs/status.md`](./docs/status.md) (auto-generated by `scripts/render_status.py`) — fallback content updated for 2026-04-30 reality
- [`docs/operations/continuity-status.html`](./docs/operations/continuity-status.html) — full rewrite reflecting prod-live, bd `213e`/`1vui` outcomes, and current work queue
- [`STATUS.md`](./STATUS.md) (NEW) — single-glance "where are we" doc at repo root
- [`TEST_PLAYBOOK.md`](./TEST_PLAYBOOK.md) (NEW) — copy-paste smoke commands and UAT recipes

The OpenAPI spec at `docs/api/swagger/openapi.json` is refreshed automatically from `https://app-governance-prod.azurewebsites.net/openapi.json` on every Pages deploy.

---

## Tyler-only decisions still open

Do not decide these on Tyler's behalf:

- `9lfn`: complete `SECRETS_OF_RECORD.md` ownership/access/rotation metadata (the last v2.5.1 gate condition).
- D8 CIEM build-vs-buy (recommendation in V2 plan: Hybrid — Entra Permissions Mgmt as data source).
- D9 WIGGUM_ROADMAP relationship (recommendation: Supplement).
- D10 cross-tenant identity stance (recommendation: Hybrid — audit each grant).

`213e` (second rollback human) is **closed** — Dustin Boyd was onboarded on 2026-04-30. The waiver state in `docs/release-gate/rollback-current-state.yaml` reflects this.

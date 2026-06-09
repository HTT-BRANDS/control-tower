# End-to-End Testing Suite — Audit & Build-Out (2026-06)

**Author:** Tyler Granlund / IT Systems & Support
**Date:** 2026-06-09
**Scope:** Whole-repo testing posture — security, design/accessibility, performance, compliance, resilience — plus a unified runner.

---

## 1. What this delivers

Control Tower already had a large, healthy test base (~4,340 collected tests across unit, integration, e2e, smoke, chaos, architecture, load). The objective here was not to rebuild it but to (a) find the real holes against the documented residual risks, (b) fill the highest-value ones with tests that pass against the live app, and (c) wire a single gate that runs every layer and emits one report.

Bottom line: **71 new tests added (all green), one unified runner with a consolidated report, a verified 100+ concurrent-user local load profile, and five findings worth a decision.**

---

## 2. New test modules (71 tests, all passing)

| Module | Tests | Closes which gap | STRIDE / WCAG tie |
|---|---|---|---|
| `tests/integration/test_security_authwall_matrix.py` | 4 | No *systematic* proof that every data route refuses anonymous access. Introspects the live route table; fails if any new `/api/v1` route serves 200 to an anonymous caller. | I1, E1/E2 |
| `tests/unit/test_jwt_security.py` | 8 | JWT *decode* was untested adversarially. Covers alg=none, tampered payload, wrong secret, expiry, bad audience, untrusted issuer, garbage. | S1, T, E1 |
| `tests/unit/test_rate_limit_enforcement.py` | 8 (15 cases) | `app.core.rate_limit` had zero behavioural tests. Covers allow→block, header decrement, 429 raise, per-client isolation, login tightening, per-endpoint config routing, fail-open. | D1 |
| `tests/unit/test_compliance_rules_security.py` | 11 | Tenant-authored JSON-Schema rule engine was untested for abuse. Covers SSRF (`$ref` http/https blocked, local `#/` allowed), 64 KB DoS cap, category/severity validation, and full cross-tenant IDOR (read/update/delete/list). | I3, D, SSRF |
| `tests/unit/test_docs_exposure_by_env.py` | 5 | `/docs`, `/redoc`, `/openapi.json` gating was only asserted in prod manually. Pins env-gated behaviour: open in dev/staging, token-required in prod (header + cookie). | I1 |
| `tests/integration/test_multi_brand_design_a11y.py` | 6 (22 cases) | Only the default brand was exercised. Verifies all 5 brands' *emitted* `--text-on-primary` meets WCAG AA 4.5:1 and `--text-on-accent` meets AA-large 3:1, plus brand distinctness and CSS namespacing. | WCAG 2.2 AA |
| `tests/integration/test_audit_log_integrity.py` | 6 | Audit trail integrity was untested. Pins append-only-by-API-surface, tenant-scoped reads, chronological ordering, count accuracy — and documents the absence of a hash chain so it stays tracked. | R1–R3, T3 |

All 71 pass together: `71 passed in ~1s`.

---

## 3. Unified runner

`scripts/run_full_suite.sh` runs each layer as an **isolated pytest process** (the project already documents why cross-group runs leak event loops — ct-pm3) and writes one Markdown report to `reports/full-suite/<timestamp>/SUITE_REPORT.md` plus per-gate logs.

Gates: `security` → `compliance` → `design_a11y` → `chaos` → `architecture` → (`unit`, `integration` regression) → optional `load_100users`.

Make targets:

```
make full-suite          # all gates + consolidated report
make full-suite-fast     # security + compliance + design (fast inner loop)
make full-suite-load     # all gates + 100-user load profile
make load-profile        # staged 100→160→100 user profile vs local server
make load-profile-quick  # 100 users / 20s verification
```

Verified curated run (FAST): **security 184 ✓ · compliance 56 ✓ · design_a11y 31 ✓ · chaos 57 ✓ · architecture 38 ✓ (6 skipped).**

---

## 4. Performance: the 100+ user residual risk, closed locally

`SESSION_HANDOFF.md` flagged *"unknown behavior at 100+ concurrent users."* Added:

- `tests/load/locust_stress_profile.py` — a self-driving `LoadTestShape` (ramp 50 → sustain 120 → spike 160 → soak 100) reusing a realistic authenticated task mix. It mints a real in-process JWT (runner pins `JWT_SECRET_KEY` so the locust process and the app agree) so it exercises the **DB-backed read paths**, not just public endpoints. 429s are counted as expected load-shedding rather than errors.
- `scripts/run_load_profile.sh` — boots a local uvicorn on throwaway SQLite, waits for `/health`, runs locust headless, writes CSV/HTML to `reports/load/`, and gates on p95 ≤ 500 ms and error rate ≤ 1 %.

**Verified result (100 concurrent authenticated users, local):** 2,146 requests, **0 failures, median 2 ms, p95 ~42 ms.** The app handles 100 concurrent users locally without errors.

> Caveat (trade-off): local SQLite ≠ Azure SQL Basic (5 DTU). These numbers prove the *app tier* scales; they do **not** model production DTU exhaustion. A staging run against real Azure SQL is the only way to characterise that — at the cost of cold-start flake and DTU risk on the shared plan. Recommended as a separate, scheduled exercise.

---

## 5. Findings worth a decision

1. **`requirements.txt` is internally unsatisfiable.** It pins `pydantic==2.13.4` (which requires `pydantic-core==2.46.4`) *and* `pydantic-core==2.47.0`. `uv pip install -r requirements.txt` fails outright. CI likely survives because it installs from `uv.lock` (`uv sync`), masking the broken file for anyone who uses `requirements.txt` directly. **Fix:** repin `pydantic-core==2.46.4` (or regenerate the file from the lock). *Not auto-applied — this is a machine-generated pin file; regenerate it through your normal lock tooling rather than hand-editing.*

2. **Six routes serve 200 to anonymous callers — by design, now codified.** `/api/v1/status`, `/api/v1/accessibility/*` (2), `/api/v1/privacy/consent/*` (3). All are intentional (public status, pre-login a11y reference, GPC/CCPA consent banner). They are now in a reviewed allowlist in the auth-wall matrix; any *new* accidental public route will trip the test.

3. **No cryptographic tamper-evidence on the audit trail.** The audit log is append-only by API surface (no update/delete method) and tenant-scoped, which is good — but rows have no `content_hash`/`prev_hash` chain, so a DB-admin-level actor could alter history undetectably. Relevant to SOC 2 CC7.2 / Riverside evidence. `test_no_tamper_evidence_yet_is_documented` records this as a conscious risk and will flip to a chain-verification test the moment integrity columns are added.

4. **`tests/integration/test_frontend_e2e.py` is environment-fragile.** Its `auth_token` fixture posts to the live login endpoint; it fails in isolation on any env without a fully-wired login path (1 failed, 37 errors alone). Excluded from the runner's integration gate with a comment. **Recommend:** make the fixture mint a token via `jwt_manager` directly (as the load profile does) instead of round-tripping the login API.

5. **Route-level rate limiting sheds load correctly under stress.** During the load run, `/api/v1/resources` returned 429 under 100 users — its router-level `Depends(rate_limit("default"))` (100 req/min) firing as designed. Worth knowing for capacity planning: per-route limits, not app capacity, are the first ceiling some endpoints hit.

---

## 6. Coverage map (after this work)

| Dimension | Before | Added | Residual |
|---|---|---|---|
| **Security** | Headers, auth health, tenant isolation (2 tests), infra constraints | Systematic auth-wall matrix, JWT adversarial, rate-limit enforcement, SSRF/IDOR on rule engine, docs gating | DAST/CodeQL in CI; CSRF on state-changing forms |
| **Design / a11y** | Default brand, axe-core e2e, contrast architecture check | All-5-brand WCAG AA contract (light) | Per-brand **dark-mode** contrast; visual-regression baselines still unpopulated |
| **Performance** | k6 smoke, Locust ≤ 50 users | Staged 100→160 user profile + local runner, verified 0-error at 100 | Staging run vs Azure SQL Basic |
| **Compliance** | Sync fitness fns, retention, Riverside endpoints | Rule-engine security, audit-trail integrity contract | Audit hash chain; GPC with real headers end-to-end |
| **Resilience** | Chaos: DB/cache/timeout/degradation (57 tests) | — (already strong) | Mutation testing (`make mutation-test` references a missing script) |

---

## 7. How to run

```bash
# Fast inner loop (security + compliance + design)
make full-suite-fast

# Everything + one report
make full-suite

# Everything + 100-user load profile
make full-suite-load

# Just the load profile
make load-profile-quick      # 100 users / 20s
make load-profile            # staged 100 → 160 → soak

# The new modules on their own
pytest tests/unit/test_jwt_security.py tests/unit/test_rate_limit_enforcement.py \
       tests/unit/test_compliance_rules_security.py tests/unit/test_docs_exposure_by_env.py \
       tests/integration/test_security_authwall_matrix.py \
       tests/integration/test_multi_brand_design_a11y.py \
       tests/integration/test_audit_log_integrity.py
```

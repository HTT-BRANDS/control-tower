# HTT Control Tower — Production Readiness Goals

> **Single source of truth for "are we production-ready?"**
> Evaluated by `scripts/judge.py` — objective criteria, no hand-waving.
> Last updated: 2026-05-28
>
> **Judge coverage:** 18 of 50 criteria (36%) are evaluated automatically by
> `scripts/judge.py`. The rest are CI-only (test suite, deploy status, Azure
> spend) or manual (UX polish, runbook drills). See `scripts/judge.py` for
> the authoritative check registry. `GOALS_WIGGUM_WORKBOOK.md` tracks the
> sprint to push this to ≥ 27/50 (54%).

---

## Scoring

| Symbol | Meaning |
|---|---|
| 🟢 PASS | Criterion met, no action needed |
| 🟡 CONDITIONAL | Met with caveats; monitor or remediate in next sprint |
| 🔴 FAIL | Criterion not met; blocks release tag |

**Release tag rule:** All P0 criteria must be 🟢. No more than 2 P1 criteria may be 🟡. Zero 🔴 anywhere.

---

## Pillar 1: Health & Observability

| ID | Criterion | Target | How Verified |
|---|---|---|---|
| P1.1 | `/health` returns 200 | `< 500ms`, healthy body | `curl` every 60s |
| P1.2 | `/health/detailed` shows all components healthy | `database: healthy`, `scheduler: running`, `cache: healthy`, `azure_configured: true` | `curl` |
| P1.3 | `/healthz/data` tenant freshness | `any_stale: false` OR documented exception with ETA | `curl` + bd issue |
| P1.4 | `/metrics` returns valid Prometheus | `200`, non-empty, parseable | `curl` + `promtool check metrics` |
| P1.5 | App Insights telemetry flowing | Traces + logs visible in Azure portal | Manual check |
| P1.6 | Alert rules armed | 9× alerts configured + 2× availability tests | Azure portal |

## Pillar 2: Security Surface

| ID | Criterion | Target | How Verified |
|---|---|---|---|
| P2.1 | `/docs` auth-gated in production | `401` without valid Bearer/cookie | `curl` |
| P2.2 | `/redoc` auth-gated in production | `401` without valid Bearer/cookie | `curl` |
| P2.3 | `/openapi.json` auth-gated in production | `401` without valid Bearer/cookie | `curl` |
| P2.4 | Server header sanitized | Only `Azure-Governance-Platform`, no `uvicorn` | `curl -I` |
| P2.5 | CSP nonce present on `/docs` | `nonce="..."` in inline script | `curl` + grep |
| P2.6 | Security headers on all responses | `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, `HSTS` | `curl -I` |
| P2.7 | Rate limiting active | `X-RateLimit-*` headers on non-exempt endpoints | `curl` |
| P2.8 | JWT secret enforced | `JWT_SECRET_KEY` set, not default/dev value | `test_config.py` |
| P2.9 | No PYSEC advisories in direct deps | `pip-audit` clean OR documented risk-accept | CI Security Scan |
| P2.10 | STRIDE analysis current | Threat model reviewed within last 90 days | `docs/security/` |

## Pillar 3: Data Integrity & Sync

| ID | Criterion | Target | How Verified |
|---|---|---|---|
| P3.1 | All tenants have required-domain data | `resources`, `compliance`, `costs`, `identity` all non-null | `/healthz/data` |
| P3.2 | Sync scheduler running | `scheduler: running` in `/health/detailed` | `curl` |
| P3.3 | No orphaned sync job logs | All `started_at` have matching `completed_at` or are < 24h old | DB query |
| P3.4 | Alembic migrations current | `alembic current` == `alembic heads` | `alembic current` |

## Pillar 4: Design System & UX

| ID | Criterion | Target | How Verified |
|---|---|---|---|
| P4.1 | No `text-gray-100` invisible text | Zero occurrences in templates | `judge.py` (P4.1) |
| P4.2 | No `focus:outline-none` without ring color | Zero occurrences in templates/JS | `judge.py` (P4.2) |
| P4.3 | `:focus-visible` uses brand token | `var(--brand-primary)` not hardcoded blue | `judge.py` (P4.3) |
| P4.4 | `/design-system` endpoint renders | `200` with HTML, all macro variants visible | `curl` + browser |
| P4.5 | WCAG contrast tests pass | All brand colors pass AA on intended backgrounds | `test_wcag_brand_validation.py` |
| P4.6 | Dark mode toggle functional | Theme switches, no FOUC, persisted per-user | Manual test |
| P4.7 | No hand-rolled badge spans | All badge-shaped `<span>` elements use DaisyUI `.badge` (theme-aware) | `judge.py` (P4.7) |

## Pillar 5: Test Coverage

| ID | Criterion | Target | How Verified |
|---|---|---|---|
| P5.1 | Unit test suite passes | `pytest tests/unit/` — all green | CI QA Gate |
| P5.2 | Core smoke tests pass | `tests/unit/test_main_app.py` + `test_config.py` + `test_security_headers.py` | CI QA Gate |
| P5.3 | Integration test suite passes | `pytest tests/integration/` — all green | CI QA Gate |
| P5.4 | E2E smoke tests pass | `pytest tests/e2e/test_smoke.py` — all green | CI QA Gate |
| P5.5 | No xpass markers | `pytest` reports zero xpassed tests | `judge.py` (P5.5) |
| P5.6 | Code coverage ≥ 60% | `pytest --cov` overall ≥ 60% | CI QA Gate |
| P5.7 | Role enum lockstep with description map | `set(Role) == set(_ROLE_DESCRIPTIONS)` — module-import assertion (ct-2vx) | `judge.py` (P5.7) |

## Pillar 6: Infrastructure & Deploy

| ID | Criterion | Target | How Verified |
|---|---|---|---|
| P6.1 | Production deploy succeeds | All 6 jobs green (QA, Security, Build, Deploy, Smoke, Notify) | GitHub Actions |
| P6.2 | Auto-rollback tested | Previous-good image captured + rollback command known | `docs/release-gate/rollback-current-state.yaml` |
| P6.3 | Staging deploy succeeds | Deploy to Staging workflow green | GitHub Actions |
| P6.4 | GitHub Pages deploy succeeds | Pages workflow green | GitHub Actions |
| P6.5 | Container image labeled | `version` label present, not `-dev` suffix | Docker inspect |
| P6.6 | Runs as non-root | `USER appuser` in Dockerfile | `docker inspect` |
| P6.7 | SLSA attestation present | Cosign-signed attestation on GHCR image | `cosign verify` |
| P6.8 | Bicep drift ≤ 5 items | `infrastructure/bicep/drift/` count ≤ 5 | `ls` |

## Pillar 7: Documentation & Operability

| ID | Criterion | Target | How Verified |
|---|---|---|---|
| P7.1 | `STATUS.md` current | mtime within 14 days (workbook DoD threshold) | `judge.py` (P7.1) |
| P7.2 | `CHANGELOG.md` current | Dated entry within last 90 days | `judge.py` (P7.2) |
| P7.3 | `SECRETS_OF_RECORD.md` complete | Tyler-only fields filled, rotation dates present | Manual review |
| P7.4 | `RUNBOOK.md` current | Deploy/rollback/DR procedures match current infra | Manual review |
| P7.5 | `SESSION_HANDOFF.md` current | mtime within 7 days | `judge.py` (P7.5) |
| P7.6 | `bd` issues ≤ 10 open | Open issue count ≤ 10 | `bd list --status open` |

## Pillar 8: Cost & Sustainability

| ID | Criterion | Target | How Verified |
|---|---|---|---|
| P8.1 | Monthly Azure spend ≤ $60 | Production + staging combined | Azure Cost Management |
| P8.2 | No orphaned resources | Resource groups match `INFRASTRUCTURE_INVENTORY.md` | `az resource list` |
| P8.3 | PITR backups enabled | Azure SQL PITR retention ≥ 7 days | Azure portal |
| P8.4 | Schema backups automated | Weekly schema backup to `stgovprodbkup001` | Azure portal |

---

## Current Verdict

Run `python scripts/judge.py` for live evaluation.

**Last manual evaluation:** 2026-05-28 — see `SESSION_HANDOFF.md` for context.

**2026-05-29 update (Richard, code-puppy-5deed9):**
- Judge: **17/18 passed (94%)** — only P1.3 blocked (DCE stale)
- GOALS.md criteria: 50 defined; judge covers 18/50 (36%)
- See `GOALS_WIGGUM_WORKBOOK.md` for the sprint to push to ≥ 27/50 (54%)

---

## Issue ↔ Goal Mapping

> Ported from `STATE.md` for at-a-glance traceability between `bd` issues and
> GOALS.md criteria.

| bd Issue | Priority | Goal Criterion(s) | Status | Action |
|---|---|---|---|---|
| ct-1m0 | P0 | P1.3, P3.1 | in_progress | Tyler: Azure portal RBAC subscription-scope fix |
| azure-governance-platform-9lfn | P1 | P7.3 | open | Tyler: author SECRETS_OF_RECORD.md |
| ct-lw2 | P2 | P7.1, P7.4 | open | Richard: design-system arch diagram split |
| ct-2vx | P2 | P5.x | open | Richard: Role enum lockstep guard |
| ct-f9p | P2 | infra long-term | open | Deferred — own workbook |
| ct-a2t | P3 | cleanup | open | Richard: remove stale app_id refs |
| ct-l4v | P3 | P3.1 | open | Richard: sparse riverside diagnostic |
| ct-2eo | P3 | cleanup | open | Tyler: remove legacy JWT issuer |
| ct-8tg | P3 | P8.1 | open | Tyler: re-check PG pause |
| azure-governance-platform-m4xw | P4 | P8.x | open | Tyler: automate audit-log archive |
| azure-governance-platform-uchp | P2 | P8.x | open | Tyler: Q3 DR test cycle |

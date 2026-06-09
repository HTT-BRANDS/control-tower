# HTT Control Tower — Production Readiness Goals

> **Single source of truth for "are we production-ready?"**
> Evaluated by `scripts/judge.py` -- objective criteria, no hand-waving.
> Last updated: 2026-06-05
>
> **Judge coverage:** 44 of 52 criteria (85%) are evaluated automatically by
> `scripts/judge.py`. 8 criteria remain manual (Azure portal, human judgment,
> quarterly cadence). See `GOALS_WIGGUM_WORKBOOK.md` for the sprint status.
>
> **Judge score:** 43/44 passed (98%). Only P7.3 (SECRETS_OF_RECORD.md TODOs)
> remains Tyler-only.

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
| P1.5 | App Insights telemetry flowing | Traces + logs visible in Azure portal | `judge.py` (P1.5) |
| P1.6 | Alert rules armed | 9x alerts configured + 2x availability tests | `judge.py` (P1.6) |

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
| P2.8 | JWT secret enforced | `JWT_SECRET_KEY` set, not default/dev value | `judge.py` (P2.8) |
| P2.9 | No PYSEC advisories in direct deps | `pip-audit` clean OR documented risk-accept | `judge.py` (P2.9) |
| P2.10 | STRIDE analysis current | Threat model reviewed within last 90 days | `docs/security/` |

## Pillar 3: Data Integrity & Sync

| ID | Criterion | Target | How Verified |
|---|---|---|---|
| P3.1 | All tenants have required-domain data | `resources`, `compliance`, `costs`, `identity` all non-null | `judge.py` (P3.1) |
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
| P4.5 | WCAG contrast tests pass | All brand colors pass AA on intended backgrounds | `judge.py` (P4.5) |
| P4.6 | Dark mode toggle functional | Theme switches, no FOUC, persisted per-user | `judge.py` (P4.6) |
| P4.7 | No hand-rolled badge spans | All badge-shaped `<span>` elements use DaisyUI `.badge` (theme-aware) | `judge.py` (P4.7) |

## Pillar 5: Test Coverage

| ID | Criterion | Target | How Verified |
|---|---|---|---|
| P5.1 | Unit test suite passes | `pytest tests/unit/` -- all green | `judge.py` (P5.1) |
| P5.2 | Core smoke tests pass | `tests/unit/test_main_app.py` + `test_config.py` + `test_security_headers.py` | `judge.py` (P5.2) |
| P5.3 | Integration test suite passes | `pytest tests/integration/` -- all green | `judge.py` (P5.3) |
| P5.4 | E2E smoke tests pass | `pytest tests/e2e/test_smoke.py` -- all green | `judge.py` (P5.4) |
| P5.5 | No xpass markers | `pytest` reports zero xpassed tests | `judge.py` (P5.5) |
| P5.6 | Code coverage ≥ 60% | `pytest --cov` overall ≥ 60% | CI QA Gate |
| P5.7 | Role enum lockstep with description map | `set(Role) == set(_ROLE_DESCRIPTIONS)` — module-import assertion (ct-2vx) | `judge.py` (P5.7) |

## Pillar 6: Infrastructure & Deploy

| ID | Criterion | Target | How Verified |
|---|---|---|---|
| P6.1 | Production deploy succeeds | All 6 jobs green (QA, Security, Build, Deploy, Smoke, Notify) | `judge.py` (P6.1) |
| P6.2 | Auto-rollback tested | Previous-good image captured + rollback command known | `judge.py` (P6.2) |
| P6.3 | Staging deploy succeeds | Deploy to Staging workflow green | `judge.py` (P6.3) |
| P6.4 | GitHub Pages deploy succeeds | Pages workflow green | GitHub Actions |
| P6.5 | Container image labeled | `version` label present, not `-dev` suffix | `judge.py` (P6.5) |
| P6.6 | Runs as non-root | `USER appuser` in Dockerfile | `docker inspect` |
| P6.7 | SLSA attestation present | Cosign-signed attestation on GHCR image | `cosign verify` |
| P6.8 | Bicep drift ≤ 5 items | `infrastructure/bicep/drift/` count ≤ 5 | `ls` |

## Pillar 7: Documentation & Operability

| ID | Criterion | Target | How Verified |
|---|---|---|---|
| P7.1 | `STATUS.md` current | mtime within 14 days (workbook DoD threshold) | `judge.py` (P7.1) |
| P7.2 | `CHANGELOG.md` current | Dated entry within last 90 days | `judge.py` (P7.2) |
| P7.3 | `SECRETS_OF_RECORD.md` complete | Tyler-only fields filled, rotation dates present | `judge.py` (P7.3) |
| P7.4 | `RUNBOOK.md` current | Deploy/rollback/DR procedures match current infra | `judge.py` (P7.4) |
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

**Last manual evaluation:** 2026-06-05 -- judge.py 27/27 (100%)

**2026-06-08 update (Richard, code-puppy-1725d8):**
- Judge: **42/44 passed (95%)** -- P3.1 (DCE gap, ct-4if) + P7.3 (SECRETS_OF_RECORD TODOs, 9lfn)
- GOALS.md criteria: 52 defined; judge covers 44/52 (85%)
- All P0 criteria pass; READY FOR RELEASE TAG
- Added P1.5 App Insights, P6.2 rollback docs, P4.6 dark mode checks

---

## Issue ↔ Goal Mapping

> Ported from `STATE.md` for at-a-glance traceability between `bd` issues and
> GOALS.md criteria.

| bd Issue | Priority | Goal Criterion(s) | Status | Action |
|---|---|---|---|---|
| azure-governance-platform-9lfn | P1 | P7.3 | in_progress | Tyler: author SECRETS_OF_RECORD.md |
| ct-4if | P2 | P1.3, P3.1 | open | Tyler: Azure portal RBAC for DCE domains |
| ct-8by | P2 | P1.6 | open | Tyler: grant ops monitoring RBAC |
| ct-dxb | P2 | P7.4 | open | Tyler: deliver ops training session |
| azure-governance-platform-uchp | P2 | P8.x | open | Tyler: Q3 DR test cycle |
| ct-18z | P3 | P2.10 | open | Tyler: revoke domain-intelligence creds |
| ct-8zr | P3 | P4.6 | closed | Accepted vendored limitation |
| azure-governance-platform-m4xw | P4 | P8.x | closed | Deferred to 2026-07-01 trigger |
| ct-f9p | P2 | infra long-term | closed | Deferred to own UAMI workbook |

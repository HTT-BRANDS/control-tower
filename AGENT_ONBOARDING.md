# AGENT_ONBOARDING — From Zero to Productive in One Day

**Audience:** A different human (or fresh AI agent) starting work on this
platform with no prior context.
**Goal:** You can claim a `bd` issue and ship a meaningful change before
end-of-day-1.

**Filed under:** Phase 0.5 of `PORTFOLIO_PLATFORM_PLAN_V2.md`. Pairs with
[`RUNBOOK.md`](./RUNBOOK.md) (emergency operations) and
[`SECRETS_OF_RECORD.md`](./SECRETS_OF_RECORD.md) (Tyler-authored credentials map).

**Status:** v1 draft 2026-04-28 by code-puppy-ab8d6a. Will evolve as the
platform does.

---

## TL;DR — Day 1 First Hour

```bash
# Clone
# Current repo URL until bd 0dsr completes the GitHub repo rename cutover
git clone https://github.com/HTT-BRANDS/azure-governance-platform.git
cd azure-governance-platform

# Bootstrap
uv venv --clear && uv sync --dev --frozen
.venv/bin/pre-commit install

# Verify it works
.venv/bin/pytest tests/unit/test_routes_health_data.py -q   # 12/12 pass

# See what's claimable
bd ready

# Pick something tiny, claim it, ship it
bd update <id> --claim
```

If those four blocks succeed: you have a working environment. Continue
with §1–§9 below at your pace.

---

## 1. What This Platform Is (in 100 words)

HTT Control Tower is an internal multi-tenant governance hub run by HTT
Brands. One FastAPI instance, App Service B1, ~$53/mo total. Reads from 5
Azure tenants (HTT, BCC, FN, TLL, DCE) via OIDC federation — zero stored
client secrets. Surfaces cost, identity, compliance, resources, lifecycle,
BI/evidence workflows, and per-tenant sync freshness. Currently 4,192 tests,
WCAG 2.2 AA-targeted, supply-chain-hardened with SLSA L3 + cosign + SBOM.
Strategic direction is in [`PORTFOLIO_PLATFORM_PLAN_V2.md`](./PORTFOLIO_PLATFORM_PLAN_V2.md).
Tyler Granlund is lead engineer; HTT Brands owns the platform.

Naming note: Control Tower is HTT's internal name for this platform. It is
unrelated to AWS Control Tower and needs separate legal/naming review before
any external commercialization.

---

## 2. The Two-Doc Pyramid

| When you need... | Read... |
|---|---|
| **Strategic intent** (what the platform is becoming, why, in what order) | [`PORTFOLIO_PLATFORM_PLAN_V2.md`](./PORTFOLIO_PLATFORM_PLAN_V2.md) |
| **Tactical execution** (how the autonomous `/wiggum ralph` protocol drives work) | [`WIGGUM_ROADMAP.md`](./WIGGUM_ROADMAP.md) |
| **Live blocker dashboard** (what's currently broken or in-flight) | [`CURRENT_STATE_ASSESSMENT.md`](./CURRENT_STATE_ASSESSMENT.md) |
| **Live work backlog** | `bd ready` |
| **System topology** (what's deployed where) | [`INFRASTRUCTURE_END_TO_END.md`](./INFRASTRUCTURE_END_TO_END.md) |
| **Emergency operations** (Tyler is unavailable, prod is on fire) | [`RUNBOOK.md`](./RUNBOOK.md) |
| **Recent decisions** (why we did the thing) | `docs/adr/` |

Read the V2 plan first. Everything else makes more sense after.

---

## 3. Repo Tour (~10 min)

```
azure-governance-platform/
├── app/                        # The FastAPI application
│   ├── main.py                 # FastAPI wiring (1050 LOC; will split per bd bu72)
│   ├── api/
│   │   ├── routes/             # HTTP boundary — request/response only
│   │   └── services/           # Cross-domain orchestration
│   ├── core/                   # Auth, cache, config, logging, telemetry
│   ├── services/               # Domain services (will move into app/domains/)
│   ├── preflight/              # Pre-deployment safety checks
│   ├── models/                 # SQLAlchemy + Pydantic models
│   ├── templates/              # Jinja2 + HTMX UI
│   ├── static/                 # CSS, JS, images
│   └── tenants/                # Per-tenant config (5 tenants today)
├── infrastructure/             # Bicep IaC for dev/staging/production
├── tests/
│   ├── unit/                   # Fast, isolated (most tests live here)
│   ├── integration/            # Real DB, real cache
│   ├── e2e/                    # End-to-end Playwright + locust
│   ├── staging/                # Run against deployed staging
│   ├── accessibility/          # WCAG 2.2 AA checks
│   └── visual/                 # Screenshot-diff (browser-required)
├── docs/
│   ├── adr/                    # Architecture decision records
│   ├── runbooks/               # Detailed operational procedures
│   ├── plans/                  # Strategic plans (current + archived)
│   ├── contracts/              # API contracts
│   └── decisions/              # Cross-cutting decisions
├── scripts/                    # Operational scripts (one-shot tools)
├── .beads/                     # bd issue tracker DB + JSONL
├── .github/workflows/          # CI/CD pipelines
├── PORTFOLIO_PLATFORM_PLAN_V2.md      # ← strategic source of truth
├── WIGGUM_ROADMAP.md                  # ← tactical execution log
├── INFRASTRUCTURE_END_TO_END.md       # ← system topology
├── RUNBOOK.md                         # ← emergency ops
├── AGENT_ONBOARDING.md                # ← YOU ARE HERE
└── README.md                          # ← entry point
```

---

## 4. Local Development Loop

### Bootstrap (once)
```bash
# Python 3.12 required (3.12.12 currently)
uv venv --clear
uv sync --dev --frozen
uv pip install pre-commit          # not in dev deps yet — see follow-up
.venv/bin/pre-commit install
```

### Run tests (the main feedback loop)
```bash
# Unit tests (fast, ~2 min)
.venv/bin/pytest tests/unit/ -q

# Just one file
.venv/bin/pytest tests/unit/test_routes_health_data.py -q

# Full collection (sanity check)
.venv/bin/pytest --collect-only -q | tail -3       # should show 4,192 tests

# Skip browser-required visual tests (default for non-Playwright environments)
.venv/bin/pytest -m "not visual" -q
```

### Run the app locally
```bash
uvicorn app.main:app --reload --port 8000
# Then open http://localhost:8000
```

🔴 **TYLER-ONLY:** Local-dev environment variables (Azure tenant IDs,
Key Vault references, etc.) live in `.env.local` (not committed). Tyler
provides this. See `SECRETS_OF_RECORD.md` (bd `9lfn`) when it lands.

### Lint + format
Pre-commit hooks run automatically on commit:
- ruff import-sort, lint, format
- detect-secrets
- env-delta schema + literal-rejection (security gate)

To run manually:
```bash
.venv/bin/pre-commit run --all-files
```

---

## 5. The bd (beads) Issue Workflow

`bd` is the issue tracker. Backed by SQLite + JSONL + git.

```bash
bd ready                              # claimable issues
bd list --status in_progress          # what's currently being worked
bd show <id>                          # full issue detail
bd update <id> --claim                # claim it (sets you as assignee + in_progress)
bd update <id> --status closed \
   --session "your-session-id"        # close it
bd comments add <id> "<message>"      # add a comment

# Standard agent loop:
bd ready
bd update <id> --claim
# ... do the work ...
bd comments add <id> "Done. Evidence: <commands and outputs>"
bd update <id> --status closed --session "your-id"
git add .beads/issues.jsonl
git commit -m "bd: close <id>"
```

Issue IDs are 4-character random suffixes (e.g., `fkul`, `9lfn`, `bu72`).
Full IDs still include the historical project prefix (`azure-governance-platform-fkul`). Do not rename bd issue IDs during the Control Tower rebrand; issue history beats cosmetic purity.

---

## 6. The `/wiggum ralph` Autonomous Protocol

`WIGGUM_ROADMAP.md` is the source of truth for autonomous execution. The
`/wiggum ralph` protocol (per `.code-puppy/AGENTS.md`) is:

1. Run `python scripts/sync_roadmap.py --verify --json` first.
2. Trust the roadmap — if a task is `[x]`, it's done; move on.
3. Execute the next unchecked task.
4. Run validation. Update roadmap. Commit. Push.
5. Repeat.

**As of V2 plan adoption:** `WIGGUM_ROADMAP.md` is for tactical task
execution, V2 plan is for strategic direction. They coexist (per V2 §D9
recommendation).

---

## 7. Deploying

### To staging
Automatic on push to `main`. Watch:
```bash
gh run list --workflow=deploy-staging.yml --limit 5
gh run watch <run-id>
```

### To production
**Manual dispatch only.** Tyler typically does this:
```bash
gh workflow run deploy-production.yml --ref main
```

Don't dispatch production without coordination unless responding to an
incident — see [`RUNBOOK.md`](./RUNBOOK.md) §3.

---

## 8. The Domains (where logic actually lives)

V2 §4 defines six bounded contexts. As of 2026-04-28, the code is *not
yet* organized this way — Phase 1 (paper exercise) and Phase 2 (DDD
relocation) are upcoming.

| Domain | Today's location | Future location |
|---|---|---|
| Cost | `app/services/`, `app/api/services/budget_service.py`, `app/services/backfill_service.py` | `app/domains/cost/` |
| Identity | `app/api/routes/auth.py`, `app/services/lighthouse_client.py`, `app/preflight/admin_risk_checks.py`, `app/core/cache.py` | `app/domains/identity/` |
| Compliance | `app/services/riverside_sync.py`, `app/core/riverside_scheduler.py` | `app/domains/compliance/` |
| Resources | scattered | `app/domains/resources/` |
| Lifecycle | (mostly DeltaSetup repo) | `app/domains/lifecycle/` |
| BI Bridge | not yet built | `app/domains/bi_bridge/` |

Per V2 Phase 1 (bd issues `32d8`, `fos1`, `htnh`, `c10e`, `ewdp`, `sl01`),
each domain will get a `README.md` + `DATA_CLASSIFICATION.md` defining
its boundary, before code moves.

---

## 9. Common Patterns to Know

### Cache decorator
Heavy reads (Azure Resource Graph, Cost Mgmt, Graph API) are cached via
`app/core/cache.py`. Default TTL varies by endpoint. Bypass with
`?fresh=1` query param (admin only).

### ResilientAzureClient
Circuit-breaker + retry pattern around Azure SDK calls. Lives in the
predecessor `control-tower` repo today; will migrate forward in V2 Phase 3.
For now: when you call Azure APIs, wrap in `try/except` and respect
HTTP 429 retry-after headers.

### Tenant scoping
Every route that returns tenant data MUST scope by `tenant_key`. The
multi-tenant pool model means a missing scope = data leak. Tests in
`tests/integration/test_tenant_isolation.py` enforce this.

### HTMX over SPA
The UI is server-rendered Jinja2 + HTMX, not a SPA. Adding a new view
means a new route + a new template. Don't reach for React/Vue/Svelte.

### Design system
`app/templates/macros/ds/` — reusable components (`ds_table`,
`ds_static_table`, `ds_modal`, `ds_form_field`, etc.). Use these,
don't roll bespoke HTML.

---

## 10. First-Day Checklist

Once you complete this, you're ready to claim a real issue.

- [ ] Repo cloned
- [ ] `uv venv && uv sync --dev --frozen` succeeded
- [ ] `pre-commit install` succeeded
- [ ] `pytest tests/unit/test_routes_health_data.py` passes (12/12)
- [ ] `pytest --collect-only` reports ≥4,000 tests
- [ ] `bd ready` returns the live backlog
- [ ] You read [`PORTFOLIO_PLATFORM_PLAN_V2.md`](./PORTFOLIO_PLATFORM_PLAN_V2.md) (~30 min)
- [ ] You skimmed [`INFRASTRUCTURE_END_TO_END.md`](./INFRASTRUCTURE_END_TO_END.md) (~15 min)
- [ ] You read [`RUNBOOK.md`](./RUNBOOK.md) §1, §5, §11 (~5 min)
- [ ] You can `gh run list` against the repo (auth'd)
- [ ] You know your bd session ID for the `--session` flag on close

---

## 11. First Issue Recommendations

If everything above passes, here are sensible first issues by experience level:

| Experience | Suggested first issue | Why |
|---|---|---|
| **Brand new agent** | `0dhj` (RTO/RPO definition) | Pure docs; learn the artifacts |
| **Familiar with FastAPI** | Any `[refactor]` issue from Phase 1.5 (e.g., `bu72` main.py split) | Mechanical, gated by tests, low risk |
| **Familiar with the codebase** | A Phase 1 domain boundary doc (e.g., `sl01` bi_bridge) | Strategic value, no code touched |
| **Operations-minded** | `mvxt` follow-up monitoring (3-5 push validation) | Operational discipline, no code |

DO NOT pick: anything in the active P1 chain (`g1cc`, `918b`, `0gz3`,
`0nup`) — those are Tyler-coordinated.

---

## 12. Asking for Help

**Stuck for >30 min?** Document what you tried in a `bd comments add`
on the relevant issue. Even if Tyler's not around, the next agent can
pick up your trail.

**Found a bug not in `bd`?** File it: `bd create --title "<short>"
--description "<details>" --priority 2 --type bug`.

**Made a meaningful change?** Update the relevant doc (RUNBOOK,
INFRASTRUCTURE_END_TO_END, etc.) so the next agent inherits your
knowledge.

---

## 13. Things That Will Change Soon

Per V2 plan, expect these to land in the next ~5 months:

- **Domain reorganization** — `app/domains/{cost,identity,compliance,resources,lifecycle,bi_bridge}/`
- **Interface adapter layer** — `app/interfaces/{azure,aws,pax8,snowflake,m365}/`
- **Repo rename** — TBD (V2 §11 has 5 candidates: Switchyard, Aerie, Hangar, Meridian, Dispatch)
- **Cross-repo bridges** — Pax8 billing ingest, httbi XMLA, DART Athena, DCE Configuration-as-Code, B2B governance UI
- **AI layer** — `/ask` (RAG over platform data) + `/act` (agentic-ops with guardrails)
- **Quarterly evidence bundle generator**

This doc will lag those changes. When in doubt: check the V2 plan and
`CURRENT_STATE_ASSESSMENT.md`.

---

*Authored by Richard (code-puppy-ab8d6a) for Tyler Granlund, 2026-04-28.*
*v1 — draft. Update when the platform's geography shifts.*

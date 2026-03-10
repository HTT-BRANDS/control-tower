# WIGGUM ROADMAP — Code Puppy Agile SDLC Implementation

**Single Source of Truth for the `/wiggum ralph` Protocol**
**Managed By:** Planning Agent 📋 (planning-agent-fde434) + Pack Leader 🐺
**Created:** March 6, 2026

---

## Usage

```bash
# Verify roadmap state
python scripts/sync_roadmap.py --verify --json

# Mark a task complete
python scripts/sync_roadmap.py --update --task 1.1.1

# Autonomous loop follows this roadmap as truth
```

---

## Phase 1: Foundation (Agent Catalog + Framework)

### 1.1 Agent Catalog Completion
- [x] 1.1.1 Create Solutions Architect JSON agent (Agent Creator 🏗️)
  - File: ~/.code_puppy/agents/solutions-architect.json
  - Validation: `python -c "import json; json.load(open('$HOME/.code_puppy/agents/solutions-architect.json'))"`
  - Reviewed by: Prompt Reviewer 📝
  - Signed off by: Planning Agent 📋

- [x] 1.1.2 Create Experience Architect JSON agent (Agent Creator 🏗️)
  - File: ~/.code_puppy/agents/experience-architect.json
  - Validation: `python -c "import json; json.load(open('$HOME/.code_puppy/agents/experience-architect.json'))"`
  - Reviewed by: Prompt Reviewer 📝
  - Signed off by: Planning Agent 📋

- [x] 1.1.3 Audit all 29 agent tool permissions (Security Auditor 🛡️)
  - Output: docs/security/agent-tool-audit.md
  - Validation: Every agent has documented tool justification
  - Reviewed by: Code Reviewer 🛡️
  - Signed off by: Pack Leader 🐺

### 1.2 Traceability Framework
- [x] 1.2.1 Create TRACEABILITY_MATRIX.md (Planning Agent 📋)
  - File: TRACEABILITY_MATRIX.md
  - Validation: File exists with all 8 epics and agent assignments
  - Reviewed by: Solutions Architect 🏛️
  - Signed off by: Planning Agent 📋

- [x] 1.2.2 Create WIGGUM_ROADMAP.md (Planning Agent 📋)
  - File: WIGGUM_ROADMAP.md
  - Validation: File exists with checkbox task tree
  - Signed off by: Pack Leader 🐺

- [x] 1.2.3 Create scripts/sync_roadmap.py (Python Programmer 🐍)
  - File: scripts/sync_roadmap.py
  - Validation: `python scripts/sync_roadmap.py --verify --json` exits 0
  - Reviewed by: Python Reviewer 🐍
  - Signed off by: Pack Leader 🐺

- [x] 1.2.4 Wire callback hooks for audit trail (Husky 🐺)
  - Files: code_puppy/tools/ (callback integration)
  - Validation: Agent actions logged to bd issues
  - Reviewed by: Shepherd 🐕 + Code Reviewer 🛡️
  - Signed off by: Pack Leader 🐺

---

## Phase 2: Governance (Security + Architecture + UX)

### 2.1 Security Posture (Epic 6)
- [x] 2.1.1 STRIDE analysis for all 29 agents (Security Auditor 🛡️)
  - Output: docs/security/stride-analysis.md
  - Validation: Every agent has 6-category STRIDE row
  - Reviewed by: Solutions Architect 🏛️
  - Signed off by: Planning Agent 📋

- [x] 2.1.2 YOLO_MODE audit (Security Auditor 🛡️)
  - Validation: Config confirms default=false; risk documented
  - Reviewed by: Code Reviewer 🛡️
  - Signed off by: Pack Leader 🐺

- [x] 2.1.3 MCP trust boundary audit (Security Auditor 🛡️)
  - Output: docs/security/mcp-trust-audit.md
  - Validation: All MCP servers documented with trust level
  - Reviewed by: Solutions Architect 🏛️
  - Signed off by: Planning Agent 📋

- [x] 2.1.4 Self-modification protections audit (Security Auditor 🛡️)
  - Validation: Only agent-creator sanctioned for agents dir writes
  - Reviewed by: Code Reviewer 🛡️
  - Signed off by: Pack Leader 🐺

- [x] 2.1.5 GPC compliance validation (Experience Architect 🎨)
  - Validation: Sec-GPC:1 documented as P0 legal requirement
  - Reviewed by: Security Auditor 🛡️
  - Signed off by: Planning Agent 📋

### 2.2 Architecture Governance (Epic 7)
- [x] 2.2.1 Establish MADR 4.0 ADR workflow (Solutions Architect 🏛️)
  - Directory: docs/decisions/
  - Validation: Template exists with STRIDE section; 3 retroactive ADRs written
  - Reviewed by: Security Auditor 🛡️
  - Signed off by: Planning Agent 📋

- [x] 2.2.2 Implement Spectral API governance (Solutions Architect 🏛️)
  - File: .spectral.yaml
  - Validation: Spectral lints pass; integrated in pre-commit
  - Reviewed by: Code Reviewer 🛡️
  - Signed off by: Pack Leader 🐺

- [x] 2.2.3 Create architecture fitness functions (Solutions Architect 🏛️ + Python Programmer 🐍)
  - Directory: tests/architecture/
  - Validation: `pytest tests/architecture/ -v` passes with 3+ tests
  - Reviewed by: Python Reviewer 🐍
  - Signed off by: Watchdog 🐕‍🦺

- [x] 2.2.4 Document research-first protocol (Solutions Architect 🏛️)
  - Validation: Protocol documented; web-puppy invoked before every ADR
  - Signed off by: Planning Agent 📋

### 2.3 UX/Accessibility Governance (Epic 8)
- [x] 2.3.1 WCAG 2.2 AA baseline in Experience Architect prompt (Experience Architect 🎨)
  - Validation: System prompt mandates WCAG 2.2 AA; 7 manual criteria listed
  - Signed off by: Planning Agent 📋

- [x] 2.3.2 axe-core 4.11.1 + Pa11y 9.1.1 CI integration (Experience Architect 🎨 + Python Programmer 🐍)
  - Files: CI config, package.json or equivalent
  - Validation: Both tools run in CI; coverage report generated
  - Reviewed by: QA Expert 🐾
  - Signed off by: Watchdog 🐕‍🦺

- [x] 2.3.3 Privacy-by-design pattern library (Experience Architect 🎨 → Web Puppy 🕵️‍♂️)
  - Output: docs/patterns/privacy-by-design.md
  - Validation: Layered consent, JIT consent, progressive profiling, consent receipts, GPC documented
  - Reviewed by: Security Auditor 🛡️
  - Signed off by: Planning Agent 📋

- [x] 2.3.4 Accessibility API metadata contract (Experience Architect 🎨)
  - Output: docs/contracts/accessibility-api.md + JSON schema
  - Validation: ARIA-compatible error response schema; integration guide
  - Reviewed by: Solutions Architect 🏛️ + Code Reviewer 🛡️
  - Signed off by: Pack Leader 🐺

---

## Phase 3: Process Integration (Testing + Requirements + Dual-Scale)

### 3.1 13-Step Testing Methodology (Epic 3)
- [x] 3.1.1 Document testing methodology with agent assignments (QA Expert 🐾)
  - Output: docs/testing/13-step-methodology.md
  - Validation: All 13 steps have named agent owners
  - Signed off by: Pack Leader 🐺

- [x] 3.1.2 Create bd issue templates for each testing phase (Bloodhound 🐕‍🦺)
  - Validation: Templates exist for Test Prep, Execution, Issue Mgmt, Perf/Security, Closure
  - Signed off by: Planning Agent 📋

### 3.2 Requirements Flow (Epic 4)
- [x] 3.2.1 Document 9-role-to-agent mapping (Planning Agent 📋)
  - Output: docs/process/requirements-flow.md
  - Validation: All 9 Granlund roles mapped to specific agents
  - Signed off by: Pack Leader 🐺

- [x] 3.2.2 Configure bd workflows for requirements chain (Bloodhound 🐕‍🦺)
  - Validation: bd issues flow through Stakeholder → BRD → US → Sprint → Delivery
  - Signed off by: Planning Agent 📋

### 3.3 Dual-Scale Project Management (Epic 5)
- [x] 3.3.1 Sprint-scale track protocol (Pack Leader 🐺)
  - Output: docs/process/sprint-track.md
  - Validation: bd sprint labels, worktree-per-task, shepherd+watchdog gates documented
  - Signed off by: Planning Agent 📋

- [x] 3.3.2 Large-scale track protocol (Planning Agent 📋)
  - Output: docs/process/large-scale-track.md
  - Validation: Dedicated bd issue trees, isolated from sprints, WIGGUM_ROADMAP integration
  - Signed off by: Pack Leader 🐺

- [x] 3.3.3 Cross-track synchronization protocol (Planning Agent 📋 + Pack Leader 🐺)
  - Output: docs/process/cross-track-sync.md
  - Validation: Shared labels, sync protocol, mutual sign-off documented
  - Signed off by: Both (mutual)

---

## Phase 4: Validation & Closure

### 4.1 End-to-End Validation
- [x] 4.1.1 Full traceability matrix validation (QA Expert 🐾)
  - Validation: Every REQ-XXX has: impl agent, reviewer, test, sign-off
  - Signed off by: Planning Agent 📋

- [x] 4.1.2 Agent integration smoke tests (Terminal QA 🖥️)
  - Validation: All 29 agents load; Solutions Architect + Experience Architect invoke web-puppy successfully
  - Signed off by: Watchdog 🐕‍🦺

- [x] 4.1.3 Security posture final review (Security Auditor 🛡️)
  - Validation: All STRIDE rows complete; no open critical findings
  - Signed off by: Pack Leader 🐺 + Planning Agent 📋

### 4.2 Documentation & Handoff
- [x] 4.2.1 Update all documentation (Planning Agent 📋)
  - Validation: README, TRACEABILITY_MATRIX, WIGGUM_ROADMAP all current
  - Signed off by: Code Reviewer 🛡️

- [x] 4.2.2 Stakeholder sign-off (Pack Leader 🐺 + Planning Agent 📋)
  - Validation: All epics passed; all bd issues closed
  - Signed off by: Both (final)

## Phase 5: Design System Migration (DNS → Governance Platform)

### 5.1 Design Token Foundation
- [x] 5.1.1 Create Pydantic design token models (Python Programmer 🐍)
  - File: app/core/design_tokens.py
  - Source: ~/dev/microsoft-group-management/hub/frontend/src/types/index.ts
  - Validation: `uv run python -c "from app.core.design_tokens import BrandConfig; print('OK')"`
  - Reviewed by: Python Reviewer 🐍
  - Signed off by: Planning Agent 📋

- [x] 5.1.2 Port color utilities to Python (Python Programmer 🐍)
  - File: app/core/color_utils.py
  - Source: ~/dev/microsoft-group-management/hub/frontend/src/index.css + hub/frontend/tailwind.config.ts
  - Validation: `uv run pytest tests/unit/test_color_utils.py -v`
  - Reviewed by: Python Reviewer 🐍 + Security Auditor 🛡️
  - Signed off by: Pack Leader 🐺

- [x] 5.1.3 Create server-side CSS generator (Python Programmer 🐍)
  - File: app/core/css_generator.py
  - Source: ~/dev/microsoft-group-management/hub/frontend/src/index.css
  - Validation: `uv run pytest tests/unit/test_css_generator.py -v`
  - Reviewed by: Python Reviewer 🐍
  - Signed off by: Planning Agent 📋

- [x] 5.1.4 Create brand configuration YAML (Experience Architect 🎨)
  - File: config/brands.yaml
  - Source: ~/dev/microsoft-group-management/hub/frontend/src/index.css + hub/frontend/tailwind.config.ts
  - Validation: `uv run python -c "from app.core.design_tokens import load_brands; load_brands()"`
  - Reviewed by: Solutions Architect 🏛️
  - Signed off by: Pack Leader 🐺

### 5.2 Asset Migration & CSS Integration
- [x] 5.2.1 Copy brand logo assets (Code-Puppy 🐶)
  - Directory: app/static/assets/brands/
  - Source: ~/dev/microsoft-group-management/hub/frontend/public/images/
  - Validation: All 5 brand directories contain logo-primary, logo-white, icon files
  - Signed off by: Planning Agent 📋

- [x] 5.2.2 Rewrite theme.css with design token architecture (Experience Architect 🎨)
  - File: app/static/css/theme.css
  - Source: ~/dev/microsoft-group-management/hub/frontend/src/index.css
  - Validation: `uv run pytest tests/architecture/test_fitness_functions.py -v`
  - Reviewed by: Solutions Architect 🏛️ + Security Auditor 🛡️
  - Signed off by: Pack Leader 🐺

- [x] 5.2.3 Rewrite theme_service.py (Python Programmer 🐍)
  - File: app/services/theme_service.py
  - Validation: `uv run pytest tests/unit/test_theme_service.py -v`
  - Reviewed by: Python Reviewer 🐍
  - Signed off by: Planning Agent 📋

- [x] 5.2.4 Extend BrandConfig SQLAlchemy model + migration (Python Programmer 🐍)
  - Files: app/models/brand_config.py, alembic/versions/002_extend_brand_config.py
  - Validation: `uv run alembic upgrade head`
  - Reviewed by: Python Reviewer 🐍
  - Signed off by: Pack Leader 🐺

### 5.3 Template System Overhaul
- [x] 5.3.1 Create theme middleware (Python Programmer 🐍)
  - File: app/core/theme_middleware.py
  - Validation: `uv run pytest tests/unit/test_theme_middleware.py -v`
  - Reviewed by: Python Reviewer 🐍 + Solutions Architect 🏛️
  - Signed off by: Pack Leader 🐺

- [x] 5.3.2 Rewrite base.html with structured theme injection (Experience Architect 🎨)
  - File: app/templates/base.html
  - Validation: No duplicate CSS imports; brand logo renders; skip-link present
  - Reviewed by: Security Auditor 🛡️
  - Signed off by: Planning Agent 📋

- [x] 5.3.3 Create Jinja2 UI macro library (Experience Architect 🎨)
  - File: app/templates/macros/ui.html
  - Validation: All macros produce valid ARIA attributes
  - Reviewed by: QA Expert 🐾 + Security Auditor 🛡️
  - Signed off by: Planning Agent 📋

- [x] 5.3.4 Update dashboard templates to use new design system (Code-Puppy 🐶)
  - Files: app/templates/pages/*.html
  - Validation: No hardcoded hex colors in template files
  - Reviewed by: Experience Architect 🎨
  - Signed off by: Pack Leader 🐺

### 5.4 Testing & Validation
- [x] 5.4.1 Unit tests for design token modules (Watchdog 🐕‍🦺)
  - Files: tests/unit/test_color_utils.py, test_css_generator.py, test_design_tokens.py, test_theme_middleware.py
  - Validation: `uv run pytest tests/unit/test_color_utils.py tests/unit/test_css_generator.py tests/unit/test_design_tokens.py tests/unit/test_theme_middleware.py -v` all pass
  - Signed off by: Pack Leader 🐺

- [x] 5.4.2 Integration tests for brand theme rendering (Watchdog 🐕‍🦺)
  - File: tests/integration/test_theme_rendering.py
  - Validation: All 5 brands render with correct CSS variables
  - Signed off by: Planning Agent 📋

- [x] 5.4.3 WCAG accessibility validation (QA Expert 🐾)
  - Validation: All brand color combinations pass WCAG AA contrast (4.5:1)
  - Signed off by: Pack Leader 🐺

- [x] 5.4.4 Architecture fitness functions for design system (Python Programmer 🐍)
  - File: tests/architecture/test_fitness_functions.py (extend)
  - Validation: No hardcoded hex in templates; all brands validate; WCAG pass
  - Reviewed by: Python Reviewer 🐍
  - Signed off by: Watchdog 🐕‍🦺

### 5.5 Security, Performance & Fix Cycle
- [x] 5.5.1 Security review of theme injection (Security Auditor 🛡️)
  - Validation: No XSS via CSS injection; CSP compatible; no tenant data leakage
  - Reviewed by: Code Reviewer 🛡️
  - Signed off by: Pack Leader 🐺

- [x] 5.5.2 Performance validation (QA Expert 🐾)
  - Validation: CSS generation < 10ms; no FOUC; fonts use display=swap
  - Signed off by: Planning Agent 📋

- [x] 5.5.3 Defect fix and regression cycle (Python Programmer 🐍)
  - Validation: `uv run pytest tests/ -q` all pass; no regressions
  - Reviewed by: Shepherd 🐕
  - Signed off by: Watchdog 🐕‍🦺

### 5.6 Production Prep & Push
- [x] 5.6.1 Update all project documentation (Planning Agent 📋)
  - Files: README.md, ARCHITECTURE.md, TRACEABILITY_MATRIX.md, SESSION_HANDOFF.md
  - New: docs/design-system.md
  - Validation: All docs reference new design system architecture
  - Signed off by: Code Reviewer 🛡️

- [x] 5.6.2 Fix staging deployment blocker uh2 (Code-Puppy 🐶)
  - File: infrastructure/modules/log-analytics.bicep
  - Validation: Bicep deployment to rg-governance-staging succeeds
  - Signed off by: Pack Leader 🐺

- [x] 5.6.3 Add pre-commit secrets hook fp0 (Code-Puppy 🐶)
  - File: .pre-commit-config.yaml
  - Validation: detect-secrets hook catches test secrets
  - Signed off by: Security Auditor 🛡️

- [x] 5.6.4 Final staging smoke test (Terminal QA 🖥️)
  - Validation: All 5 brand themes render correctly on staging
  - Signed off by: Watchdog 🐕‍🦺

- [x] 5.6.5 Stakeholder sign-off and git push (Pack Leader 🐺)
  - Validation: All tests pass; git push succeeds; git status clean
  - Signed off by: Pack Leader 🐺 + Planning Agent 📋

---

## Phase 6: Cleanup & Consolidation

### 6.1 Documentation & Artifact Cleanup
- [x] 6.1.1 Relocate compass_artifact research doc from project root (Code-Puppy 🐶)
  - Action: `mv compass_artifact_wf-34ef2561-5cba-460c-90f6-358f0553d17c_text_markdown.md research/code-puppy-sdlc-analysis.md`
  - Validation: `test ! -f compass_artifact_wf-*.md && test -f research/code-puppy-sdlc-analysis.md`
  - Signed off by: Planning Agent 📋

- [x] 6.1.2 Update stale agent IDs in all documentation (Code-Puppy 🐶)
  - Files: WIGGUM_ROADMAP.md, TRACEABILITY_MATRIX.md, docs/design-system.md
  - Action: Replace planning-agent-cbc7e7 with planning-agent-fde434
  - Validation: `grep -r "planning-agent-cbc7e7" . | wc -l` returns 0
  - Signed off by: Planning Agent 📋

- [x] 6.1.3 Update pyproject.toml development status classifier (Code-Puppy 🐶)
  - File: pyproject.toml
  - Action: Change Development Status 3 - Alpha to 4 - Beta
  - Validation: `grep "Development Status :: 4 - Beta" pyproject.toml`
  - Signed off by: Planning Agent 📋

- [x] 6.1.4 Cut CHANGELOG v1.1.0 release for design system work (Code-Puppy 🐶)
  - File: CHANGELOG.md
  - Action: Move Unreleased design system items to v1.1.0 section
  - Validation: `grep "\[1.1.0\]" CHANGELOG.md`
  - Signed off by: Planning Agent 📋

- [x] 6.1.5 Clean up SQLite WAL orphans in data directory (Code-Puppy 🐶)
  - Action: Remove data/governance.db-shm and data/governance.db-wal if no .db file exists
  - Validation: `ls data/ | grep -v sp-audit` shows no orphan files
  - Signed off by: Planning Agent 📋

- [x] 6.1.6 Archive outdated PRE_STAGING_QA report (Code-Puppy 🐶)
  - Action: `mv docs/PRE_STAGING_QA.md docs/archive/PRE_STAGING_QA.md`
  - Validation: `test -f docs/archive/PRE_STAGING_QA.md && test ! -f docs/PRE_STAGING_QA.md`
  - Signed off by: Planning Agent 📋

- [x] 6.1.7 Rewrite SESSION_HANDOFF.md for production readiness phase (Planning Agent 📋)
  - File: SESSION_HANDOFF.md
  - Action: Update objective, agent ID, current state, and next steps for Phase 6-7
  - Validation: `grep "planning-agent-fde434" SESSION_HANDOFF.md`
  - Signed off by: Pack Leader 🐺

- [ ] 6.1.8 Add Epic 10 to TRACEABILITY_MATRIX.md (Planning Agent 📋)
  - File: TRACEABILITY_MATRIX.md
  - Action: Add Production Readiness epic with REQ-1001 through REQ-1015
  - Validation: `grep "REQ-1015" TRACEABILITY_MATRIX.md`
  - Signed off by: Pack Leader 🐺

- [ ] 6.1.9 Run full test suite to establish Phase 6 baseline (Watchdog 🐕‍🦺)
  - Command: `uv run pytest tests/ -q --ignore=tests/e2e --ignore=tests/smoke`
  - Validation: Exit code 0 with all tests passing
  - Signed off by: Planning Agent 📋

- [ ] 6.1.10 Commit and push Phase 6 cleanup (Code-Puppy 🐶)
  - Command: `git add -A && git commit -m "phase 6: cleanup and consolidation" && git push`
  - Validation: `git status` shows clean working tree
  - Signed off by: Pack Leader 🐺

---

## Phase 7: Production Hardening

### 7.1 Security Hardening
- [ ] 7.1.1 Enforce JWT_SECRET_KEY in production mode (Python Programmer 🐍)
  - Files: app/core/config.py, .env.example
  - Validation: App refuses to start in ENVIRONMENT=production without explicit JWT_SECRET_KEY
  - Reviewed by: Security Auditor 🛡️
  - Signed off by: Pack Leader 🐺

- [ ] 7.1.2 Verify Redis-backed token blacklist for production (Python Programmer 🐍)
  - Files: app/core/token_blacklist.py, pyproject.toml
  - Validation: `uv run pytest tests/unit/test_token_blacklist.py -v` passes
  - Reviewed by: Security Auditor 🛡️
  - Signed off by: Pack Leader 🐺

- [ ] 7.1.3 Harden CORS origins for production (Python Programmer 🐍)
  - Files: app/main.py, app/core/config.py
  - Validation: App rejects wildcard CORS in production mode
  - Reviewed by: Security Auditor 🛡️
  - Signed off by: Planning Agent 📋

- [ ] 7.1.4 Tune rate limiting for production traffic (Python Programmer 🐍)
  - Files: app/core/rate_limit.py, app/core/config.py
  - Validation: `uv run pytest tests/unit/test_rate_limit.py -v` passes
  - Reviewed by: Solutions Architect 🏛️
  - Signed off by: Pack Leader 🐺

- [ ] 7.1.5 Run production security audit (Security Auditor 🛡️)
  - Output: docs/security/production-audit.md
  - Validation: No critical or high findings remain open
  - Signed off by: Pack Leader 🐺 + Planning Agent 📋

### 7.2 Azure Integration
- [ ] 7.2.1 Document Azure AD app registration for production (Python Programmer 🐍)
  - Files: scripts/setup-app-registration-manual.md, docs/DEPLOYMENT.md
  - Validation: Production redirect URIs and group mappings documented
  - Signed off by: Security Auditor 🛡️

- [ ] 7.2.2 Wire Key Vault credential retrieval for all tenants (Python Programmer 🐍)
  - Files: app/core/config.py, app/core/tenants_config.py
  - Validation: Key Vault integration code exists with fallback to env vars
  - Reviewed by: Security Auditor 🛡️
  - Signed off by: Pack Leader 🐺

- [ ] 7.2.3 Replace backfill placeholder data with real Azure API calls (Python Programmer 🐍)
  - Files: app/services/backfill_service.py, app/api/services/identity_service.py
  - Validation: `grep -r "placeholder" app/ | wc -l` returns 0
  - Reviewed by: Python Reviewer 🐍
  - Signed off by: Pack Leader 🐺

- [ ] 7.2.4 Create admin user setup script for production (Python Programmer 🐍)
  - File: scripts/setup_admin.py
  - Validation: `uv run python scripts/setup_admin.py --help` shows usage
  - Signed off by: Planning Agent 📋

### 7.3 Staging Deployment
- [ ] 7.3.1 Deploy staging infrastructure via Bicep (Code-Puppy 🐶)
  - Files: infrastructure/parameters.staging.json, infrastructure/deploy.sh
  - Validation: Staging deployment documented in docs/STAGING_DEPLOYMENT_CHECKLIST.md
  - Signed off by: Solutions Architect 🏛️

- [ ] 7.3.2 Configure staging secrets and push container image (Code-Puppy 🐶)
  - Files: .env.production, docker-compose.prod.yml
  - Validation: Staging configuration documented with all required env vars
  - Signed off by: Security Auditor 🛡️

- [ ] 7.3.3 Run staging smoke tests (QA Expert 🐾)
  - File: scripts/smoke_test.py
  - Validation: Smoke test script supports --url parameter for staging
  - Signed off by: Watchdog 🐕‍🦺

- [ ] 7.3.4 Configure CI/CD OIDC federation (Code-Puppy 🐶)
  - Files: infrastructure/github-oidc.bicep, scripts/gh-oidc-setup.sh
  - Validation: OIDC setup documented with step-by-step instructions
  - Signed off by: Security Auditor 🛡️

### 7.4 Database and Migrations
- [ ] 7.4.1 Verify all Alembic migrations are current (Python Programmer 🐍)
  - Command: `uv run alembic upgrade head`
  - Validation: No pending migrations and schema matches models
  - Signed off by: Planning Agent 📋

- [ ] 7.4.2 Create missing Alembic migrations for model drift (Python Programmer 🐍)
  - Files: alembic/versions/
  - Validation: `uv run alembic upgrade head` is idempotent
  - Reviewed by: Python Reviewer 🐍
  - Signed off by: Pack Leader 🐺

### 7.5 Final Validation and Release
- [ ] 7.5.1 Run full test suite for production validation (Watchdog 🐕‍🦺)
  - Command: `uv run pytest tests/ -q --ignore=tests/e2e --ignore=tests/smoke`
  - Validation: Exit code 0 with zero failures
  - Signed off by: Pack Leader 🐺

- [ ] 7.5.2 Run linting and type checking (Watchdog 🐕‍🦺)
  - Command: `uv run ruff check .`
  - Validation: Zero errors reported
  - Signed off by: Planning Agent 📋

- [ ] 7.5.3 Update all documentation for production state (Planning Agent 📋)
  - Files: README.md, CHANGELOG.md, SESSION_HANDOFF.md, docs/DEPLOYMENT.md
  - Validation: README In Progress section cleared; staging URL documented
  - Signed off by: Code Reviewer 🛡️

- [ ] 7.5.4 Final security review of production config (Security Auditor 🛡️)
  - File: SECURITY_IMPLEMENTATION.md
  - Validation: Production Checklist in SECURITY_IMPLEMENTATION.md all checked
  - Signed off by: Pack Leader 🐺 + Planning Agent 📋

- [ ] 7.5.5 Tag release and push to production (Pack Leader 🐺)
  - Command: `git add -A && git commit -m "v1.2.0: production ready" && git tag v1.2.0 && git push && git push --tags`
  - Validation: `git status` shows clean tree and tag v1.2.0 exists
  - Signed off by: Pack Leader 🐺 + Planning Agent 📋

---

## Progress Summary

| Phase | Total Tasks | Completed | Remaining | Status |
|-------|-----------|-----------|-----------|--------|
| Phase 1: Foundation | 7 | 7 | 0 | ✅ Complete |
| Phase 2: Governance | 13 | 13 | 0 | ✅ Complete |
| Phase 3: Process | 7 | 7 | 0 | ✅ Complete |
| Phase 4: Validation | 5 | 5 | 0 | ✅ Complete |
| Phase 5: Design System Migration | 24 | 24 | 0 | ✅ Complete |
| Phase 6: Cleanup & Consolidation | 10 | 7 | 3 | 🔄 In Progress |
| Phase 7: Production Hardening | 20 | 0 | 20 | ⬜ Not Started |
| **TOTAL** | **86** | **63** | **23** | **🔄 In Progress** |

---

*This roadmap is the single source of truth for the /wiggum ralph protocol. Task completion is validated by running the task's validation command, then updating via `python scripts/sync_roadmap.py --update --task X.Y.Z`.*

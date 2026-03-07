# WIGGUM ROADMAP — Code Puppy Agile SDLC Implementation

**Single Source of Truth for the `/wiggum ralph` Protocol**
**Managed By:** Planning Agent 📋 (planning-agent-781acb) + Pack Leader 🐺
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
  - Source: ~/dev/DNS-Domain-Management/lib/types/brand.ts
  - Validation: `uv run python -c "from app.core.design_tokens import BrandConfig; print('OK')"`
  - Reviewed by: Python Reviewer 🐍
  - Signed off by: Planning Agent 📋

- [x] 5.1.2 Port color utilities to Python (Python Programmer 🐍)
  - File: app/core/color_utils.py
  - Source: ~/dev/DNS-Domain-Management/lib/theme/brand-utils.ts
  - Validation: `uv run pytest tests/unit/test_color_utils.py -v`
  - Reviewed by: Python Reviewer 🐍 + Security Auditor 🛡️
  - Signed off by: Pack Leader 🐺

- [x] 5.1.3 Create server-side CSS generator (Python Programmer 🐍)
  - File: app/core/css_generator.py
  - Source: ~/dev/DNS-Domain-Management/lib/theme/css-generator.ts
  - Validation: `uv run pytest tests/unit/test_css_generator.py -v`
  - Reviewed by: Python Reviewer 🐍
  - Signed off by: Planning Agent 📋

- [x] 5.1.4 Create brand configuration YAML (Experience Architect 🎨)
  - File: config/brands.yaml
  - Source: ~/dev/DNS-Domain-Management/config/brands.yaml
  - Validation: `uv run python -c "from app.core.design_tokens import load_brands; load_brands()"`
  - Reviewed by: Solutions Architect 🏛️
  - Signed off by: Pack Leader 🐺

### 5.2 Asset Migration & CSS Integration
- [x] 5.2.1 Copy brand logo assets (Code-Puppy 🐶)
  - Directory: app/static/assets/brands/
  - Source: ~/dev/DNS-Domain-Management/public/assets/brands/ + HTT-Brands-Logo/
  - Validation: All 5 brand directories contain logo-primary, logo-white, icon files
  - Signed off by: Planning Agent 📋

- [x] 5.2.2 Rewrite theme.css with design token architecture (Experience Architect 🎨)
  - File: app/static/css/theme.css
  - Source: ~/dev/DNS-Domain-Management/app/globals.css + tailwind.config.ts
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
- [ ] 5.6.1 Update all project documentation (Planning Agent 📋)
  - Files: README.md, ARCHITECTURE.md, TRACEABILITY_MATRIX.md, SESSION_HANDOFF.md
  - New: docs/design-system.md
  - Validation: All docs reference new design system architecture
  - Signed off by: Code Reviewer 🛡️

- [ ] 5.6.2 Fix staging deployment blocker uh2 (Code-Puppy 🐶)
  - File: infrastructure/modules/log-analytics.bicep
  - Validation: Bicep deployment to rg-governance-staging succeeds
  - Signed off by: Pack Leader 🐺

- [ ] 5.6.3 Add pre-commit secrets hook fp0 (Code-Puppy 🐶)
  - File: .pre-commit-config.yaml
  - Validation: detect-secrets hook catches test secrets
  - Signed off by: Security Auditor 🛡️

- [ ] 5.6.4 Final staging smoke test (Terminal QA 🖥️)
  - Validation: All 5 brand themes render correctly on staging
  - Signed off by: Watchdog 🐕‍🦺

- [ ] 5.6.5 Stakeholder sign-off and git push (Pack Leader 🐺)
  - Validation: All tests pass; git push succeeds; git status clean
  - Signed off by: Pack Leader 🐺 + Planning Agent 📋

---

## Progress Summary

| Phase | Total Tasks | Completed | Remaining | Status |
|-------|-----------|-----------|-----------|--------|
| Phase 1: Foundation | 7 | 7 | 0 | ✅ Complete |
| Phase 2: Governance | 13 | 13 | 0 | ✅ Complete |
| Phase 3: Process | 7 | 7 | 0 | ✅ Complete |
| Phase 4: Validation | 5 | 5 | 0 | ✅ Complete |
| Phase 5: Design System Migration | 24 | 19 | 5 | 🔄 In Progress |
| **TOTAL** | **56** | **51** | **5** | **🔄 In Progress** |

---

*This roadmap is the single source of truth for the /wiggum ralph protocol. Task completion is validated by running the task's validation command, then updating via `python scripts/sync_roadmap.py --update --task X.Y.Z`.*

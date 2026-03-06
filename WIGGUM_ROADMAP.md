# WIGGUM ROADMAP — Code Puppy Agile SDLC Implementation

**Single Source of Truth for the `/wiggum ralph` Protocol**
**Managed By:** Planning Agent 📋 (planning-agent-f52ac5) + Pack Leader 🐺
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
- [ ] 2.1.1 STRIDE analysis for all 29 agents (Security Auditor 🛡️)
  - Output: docs/security/stride-analysis.md
  - Validation: Every agent has 6-category STRIDE row
  - Reviewed by: Solutions Architect 🏛️
  - Signed off by: Planning Agent 📋

- [ ] 2.1.2 YOLO_MODE audit (Security Auditor 🛡️)
  - Validation: Config confirms default=false; risk documented
  - Reviewed by: Code Reviewer 🛡️
  - Signed off by: Pack Leader 🐺

- [ ] 2.1.3 MCP trust boundary audit (Security Auditor 🛡️)
  - Output: docs/security/mcp-trust-audit.md
  - Validation: All MCP servers documented with trust level
  - Reviewed by: Solutions Architect 🏛️
  - Signed off by: Planning Agent 📋

- [ ] 2.1.4 Self-modification protections audit (Security Auditor 🛡️)
  - Validation: Only agent-creator sanctioned for agents dir writes
  - Reviewed by: Code Reviewer 🛡️
  - Signed off by: Pack Leader 🐺

- [ ] 2.1.5 GPC compliance validation (Experience Architect 🎨)
  - Validation: Sec-GPC:1 documented as P0 legal requirement
  - Reviewed by: Security Auditor 🛡️
  - Signed off by: Planning Agent 📋

### 2.2 Architecture Governance (Epic 7)
- [ ] 2.2.1 Establish MADR 4.0 ADR workflow (Solutions Architect 🏛️)
  - Directory: docs/decisions/
  - Validation: Template exists with STRIDE section; 3 retroactive ADRs written
  - Reviewed by: Security Auditor 🛡️
  - Signed off by: Planning Agent 📋

- [ ] 2.2.2 Implement Spectral API governance (Solutions Architect 🏛️)
  - File: .spectral.yaml
  - Validation: Spectral lints pass; integrated in pre-commit
  - Reviewed by: Code Reviewer 🛡️
  - Signed off by: Pack Leader 🐺

- [ ] 2.2.3 Create architecture fitness functions (Solutions Architect 🏛️ + Python Programmer 🐍)
  - Directory: tests/architecture/
  - Validation: `pytest tests/architecture/ -v` passes with 3+ tests
  - Reviewed by: Python Reviewer 🐍
  - Signed off by: Watchdog 🐕‍🦺

- [ ] 2.2.4 Document research-first protocol (Solutions Architect 🏛️)
  - Validation: Protocol documented; web-puppy invoked before every ADR
  - Signed off by: Planning Agent 📋

### 2.3 UX/Accessibility Governance (Epic 8)
- [x] 2.3.1 WCAG 2.2 AA baseline in Experience Architect prompt (Experience Architect 🎨)
  - Validation: System prompt mandates WCAG 2.2 AA; 7 manual criteria listed
  - Signed off by: Planning Agent 📋

- [ ] 2.3.2 axe-core 4.11.1 + Pa11y 9.1.1 CI integration (Experience Architect 🎨 + Python Programmer 🐍)
  - Files: CI config, package.json or equivalent
  - Validation: Both tools run in CI; coverage report generated
  - Reviewed by: QA Expert 🐾
  - Signed off by: Watchdog 🐕‍🦺

- [ ] 2.3.3 Privacy-by-design pattern library (Experience Architect 🎨 → Web Puppy 🕵️‍♂️)
  - Output: docs/patterns/privacy-by-design.md
  - Validation: Layered consent, JIT consent, progressive profiling, consent receipts, GPC documented
  - Reviewed by: Security Auditor 🛡️
  - Signed off by: Planning Agent 📋

- [ ] 2.3.4 Accessibility API metadata contract (Experience Architect 🎨)
  - Output: docs/contracts/accessibility-api.md + JSON schema
  - Validation: ARIA-compatible error response schema; integration guide
  - Reviewed by: Solutions Architect 🏛️ + Code Reviewer 🛡️
  - Signed off by: Pack Leader 🐺

---

## Phase 3: Process Integration (Testing + Requirements + Dual-Scale)

### 3.1 13-Step Testing Methodology (Epic 3)
- [ ] 3.1.1 Document testing methodology with agent assignments (QA Expert 🐾)
  - Output: docs/testing/13-step-methodology.md
  - Validation: All 13 steps have named agent owners
  - Signed off by: Pack Leader 🐺

- [ ] 3.1.2 Create bd issue templates for each testing phase (Bloodhound 🐕‍🦺)
  - Validation: Templates exist for Test Prep, Execution, Issue Mgmt, Perf/Security, Closure
  - Signed off by: Planning Agent 📋

### 3.2 Requirements Flow (Epic 4)
- [ ] 3.2.1 Document 9-role-to-agent mapping (Planning Agent 📋)
  - Output: docs/process/requirements-flow.md
  - Validation: All 9 Granlund roles mapped to specific agents
  - Signed off by: Pack Leader 🐺

- [ ] 3.2.2 Configure bd workflows for requirements chain (Bloodhound 🐕‍🦺)
  - Validation: bd issues flow through Stakeholder → BRD → US → Sprint → Delivery
  - Signed off by: Planning Agent 📋

### 3.3 Dual-Scale Project Management (Epic 5)
- [ ] 3.3.1 Sprint-scale track protocol (Pack Leader 🐺)
  - Output: docs/process/sprint-track.md
  - Validation: bd sprint labels, worktree-per-task, shepherd+watchdog gates documented
  - Signed off by: Planning Agent 📋

- [ ] 3.3.2 Large-scale track protocol (Planning Agent 📋)
  - Output: docs/process/large-scale-track.md
  - Validation: Dedicated bd issue trees, isolated from sprints, WIGGUM_ROADMAP integration
  - Signed off by: Pack Leader 🐺

- [ ] 3.3.3 Cross-track synchronization protocol (Planning Agent 📋 + Pack Leader 🐺)
  - Output: docs/process/cross-track-sync.md
  - Validation: Shared labels, sync protocol, mutual sign-off documented
  - Signed off by: Both (mutual)

---

## Phase 4: Validation & Closure

### 4.1 End-to-End Validation
- [ ] 4.1.1 Full traceability matrix validation (QA Expert 🐾)
  - Validation: Every REQ-XXX has: impl agent, reviewer, test, sign-off
  - Signed off by: Planning Agent 📋

- [ ] 4.1.2 Agent integration smoke tests (Terminal QA 🖥️)
  - Validation: All 29 agents load; Solutions Architect + Experience Architect invoke web-puppy successfully
  - Signed off by: Watchdog 🐕‍🦺

- [ ] 4.1.3 Security posture final review (Security Auditor 🛡️)
  - Validation: All STRIDE rows complete; no open critical findings
  - Signed off by: Pack Leader 🐺 + Planning Agent 📋

### 4.2 Documentation & Handoff
- [ ] 4.2.1 Update all documentation (Planning Agent 📋)
  - Validation: README, TRACEABILITY_MATRIX, WIGGUM_ROADMAP all current
  - Signed off by: Code Reviewer 🛡️

- [ ] 4.2.2 Stakeholder sign-off (Pack Leader 🐺 + Planning Agent 📋)
  - Validation: All epics passed; all bd issues closed
  - Signed off by: Both (final)

---

## Progress Summary

| Phase | Total Tasks | Completed | Remaining | Status |
|-------|-----------|-----------|-----------|--------|
| Phase 1: Foundation | 7 | 7 | 0 | ✅ Complete |
| Phase 2: Governance | 13 | 1 | 12 | 🔄 In Progress |
| Phase 3: Process | 7 | 0 | 7 | ⬜ Not Started |
| Phase 4: Validation | 5 | 0 | 5 | ⬜ Not Started |
| **TOTAL** | **32** | **8** | **24** | **🔄 In Progress** |

---

*This roadmap is the single source of truth for the /wiggum ralph protocol. Task completion is validated by running the task's validation command, then updating via `python scripts/sync_roadmap.py --update --task X.Y.Z`.*

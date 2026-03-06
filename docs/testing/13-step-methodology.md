# 13-Step Testing Methodology — Code Puppy Agent Assignments

**Date:** 2026-03-06
**Owner:** QA Expert 🐾
**Sign-off:** Pack Leader 🐺
**Task:** 3.1.1 / REQ-301–313
**Methodology:** Tyler Granlund's Agile SDLC Testing Framework

---

## Overview

This document maps Tyler Granlund's 13-step testing methodology to Code Puppy's multi-agent system. Every step has a named owner agent, reviewer, defined inputs/outputs, and exit criteria.

### Five Testing Phases

| Phase | Steps | Focus |
|-------|-------|-------|
| **Test Preparation** | 1–4 | Planning, design, environment, automation |
| **Test Execution** | 5–7 | Manual, automated, and coordinated execution |
| **Issue Management** | 8–9 | Defect logging and fix verification |
| **Performance & Security** | 10–11 | Non-functional quality gates |
| **Documentation & Closure** | 12–13 | Final docs and stakeholder sign-off |

---

## Agent Assignment Summary

| Step | Name | Owner Agent(s) | Reviewer |
|------|------|---------------|----------|
| 1 | Review US/AC | QA Expert 🐾 + Experience Architect 🎨 | Planning Agent 📋 |
| 2 | Draft test cases | QA Expert 🐾 | Shepherd 🐕 |
| 3 | Set up test env | Terrier 🐕 + Husky 🐺 | Watchdog 🐕‍🦺 |
| 4 | Automate test setup | Python Programmer 🐍 | Python Reviewer 🐍 |
| 5 | Manual testing | QA Kitten 🐱 (web) / Terminal QA 🖥️ (CLI) | QA Expert 🐾 |
| 6 | Automated testing | Watchdog 🐕‍🦺 | QA Expert 🐾 |
| 7 | Execute all planned | Pack Leader 🐺 | Planning Agent 📋 |
| 8 | Log defects | Bloodhound 🐕‍🦺 | Pack Leader 🐺 |
| 9 | Verify fixes | Watchdog 🐕‍🦺 + Shepherd 🐕 | QA Expert 🐾 |
| 10 | Performance testing | QA Expert 🐾 | Solutions Architect 🏛️ |
| 11 | Security testing | Security Auditor 🛡️ + Solutions Architect 🏛️ | Pack Leader 🐺 |
| 12 | Update documentation | Planning Agent 📋 | Code Reviewer 🛡️ |
| 13 | Stakeholder feedback | Pack Leader 🐺 + Planning Agent 📋 | N/A (final) |

---

## Workflow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    TEST PREPARATION                          │
│                                                              │
│  Step 1: Review US/AC ──→ Step 2: Draft Cases ──→           │
│  Step 3: Setup Env    ──→ Step 4: Automate Setup            │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    TEST EXECUTION                            │
│                                                              │
│  Step 5: Manual Testing  ──┐                                │
│                            ├──→ Step 7: Execute All         │
│  Step 6: Automated Testing ┘                                │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                   ISSUE MANAGEMENT                           │
│                                                              │
│  Step 8: Log Defects ──→ Step 9: Verify Fixes               │
│        ↑                         │                           │
│        └─────────────────────────┘ (cycle until clean)      │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                PERFORMANCE & SECURITY                        │
│                                                              │
│  Step 10: Performance ──→ Step 11: Security                 │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│              DOCUMENTATION & CLOSURE                         │
│                                                              │
│  Step 12: Update Docs ──→ Step 13: Stakeholder Sign-off    │
└─────────────────────────────────────────────────────────────┘
```

---

## Detailed Step Descriptions

### Phase 1: Test Preparation

#### Step 1 — Review User Stories and Acceptance Criteria

| Field | Value |
|-------|-------|
| **Owner** | QA Expert 🐾 + Experience Architect 🎨 |
| **Reviewer** | Planning Agent 📋 |
| **REQ** | REQ-301 |
| **Input** | User stories, acceptance criteria from TRACEABILITY_MATRIX.md |
| **Output** | AC coverage report — confirms every AC has at least one test |
| **Tools** | `bd show`, TRACEABILITY_MATRIX.md |
| **Exit Criteria** | Every REQ-XXX has mapped test coverage |

**Description:** QA Expert reviews all user stories and their acceptance criteria. Experience Architect validates UX-related criteria for accessibility and usability coverage. The output is an AC coverage report confirming no gaps.

#### Step 2 — Draft Test Cases

| Field | Value |
|-------|-------|
| **Owner** | QA Expert 🐾 |
| **Reviewer** | Shepherd 🐕 |
| **REQ** | REQ-302 |
| **Input** | AC coverage report from Step 1 |
| **Output** | Test case specifications (positive, negative, edge cases) |
| **Tools** | `bd create` for test issues |
| **Exit Criteria** | Test cases exist for every AC; Shepherd approves quality |

**Description:** QA Expert drafts test cases covering positive paths, negative paths, boundary conditions, and edge cases. Shepherd reviews for completeness and quality. Test cases are tracked as bd issues.

#### Step 3 — Set Up Test Environment

| Field | Value |
|-------|-------|
| **Owner** | Terrier 🐕 + Husky 🐺 |
| **Reviewer** | Watchdog 🐕‍🦺 |
| **REQ** | REQ-303 |
| **Input** | Test case specs from Step 2 |
| **Output** | Clean, reproducible test environment |
| **Tools** | git worktree, docker-compose, venv |
| **Exit Criteria** | Environment boots clean; Watchdog verifies |

**Description:** Terrier creates isolated worktrees for test execution. Husky configures the environment (database, services, fixtures). Watchdog validates the environment is clean and reproducible.

#### Step 4 — Automate Test Setup

| Field | Value |
|-------|-------|
| **Owner** | Python Programmer 🐍 |
| **Reviewer** | Python Reviewer 🐍 |
| **REQ** | REQ-304 |
| **Input** | Test environment from Step 3 |
| **Output** | CI configuration, automated test runners |
| **Tools** | pytest, GitHub Actions, conftest.py |
| **Exit Criteria** | CI config valid; tests runnable via single command |

**Description:** Python Programmer creates or updates CI configurations so tests run automatically. Includes conftest.py fixtures, GitHub Actions workflows, and pytest configuration.

### Phase 2: Test Execution

#### Step 5 — Manual Testing

| Field | Value |
|-------|-------|
| **Owner** | QA Kitten 🐱 (web) / Terminal QA 🖥️ (CLI) |
| **Reviewer** | QA Expert 🐾 |
| **REQ** | REQ-305 |
| **Input** | Test cases from Step 2, environment from Step 3 |
| **Output** | Manual test execution log with pass/fail status |
| **Tools** | Playwright (QA Kitten), terminal commands (Terminal QA) |
| **Exit Criteria** | All manual test cases executed; results logged |

**Description:** QA Kitten handles web UI testing using Playwright with visual analysis. Terminal QA handles CLI and TUI testing. Both produce execution logs with screenshots/evidence.

#### Step 6 — Automated Testing

| Field | Value |
|-------|-------|
| **Owner** | Watchdog 🐕‍🦺 |
| **Reviewer** | QA Expert 🐾 |
| **REQ** | REQ-306 |
| **Input** | CI config from Step 4, test environment |
| **Output** | Test results: pass/fail counts, coverage report |
| **Tools** | pytest, coverage.py, GitHub Actions |
| **Exit Criteria** | All automated tests pass; coverage meets threshold |

**Description:** Watchdog runs the full automated test suite including unit, integration, and e2e tests. Generates coverage reports and identifies regressions.

#### Step 7 — Execute All Planned Tests

| Field | Value |
|-------|-------|
| **Owner** | Pack Leader 🐺 |
| **Reviewer** | Planning Agent 📋 |
| **REQ** | REQ-307 |
| **Input** | Results from Steps 5 and 6 |
| **Output** | Full test report combining manual + automated results |
| **Tools** | bd list, test reports |
| **Exit Criteria** | All planned tests executed; comprehensive report produced |

**Description:** Pack Leader coordinates the complete test execution, ensuring all planned manual and automated tests are run. Produces a consolidated report.

### Phase 3: Issue Management

#### Step 8 — Log Defects

| Field | Value |
|-------|-------|
| **Owner** | Bloodhound 🐕‍🦺 |
| **Reviewer** | Pack Leader 🐺 |
| **REQ** | REQ-308 |
| **Input** | Failed tests from Steps 5–7 |
| **Output** | bd issues for every defect with severity, steps to reproduce |
| **Tools** | `bd create`, `bd comment` |
| **Exit Criteria** | Every failure has a tracked bd issue |

**Description:** Bloodhound creates bd issues for every test failure. Each issue includes severity, steps to reproduce, expected vs actual behavior, and screenshots/logs.

#### Step 9 — Verify Fixes

| Field | Value |
|-------|-------|
| **Owner** | Watchdog 🐕‍🦺 + Shepherd 🐕 |
| **Reviewer** | QA Expert 🐾 |
| **REQ** | REQ-309 |
| **Input** | Fix commits from developers |
| **Output** | Regression test results confirming fixes |
| **Tools** | pytest, `bd close` |
| **Exit Criteria** | All defect fixes verified; regression tests pass |

**Description:** After Husky fixes defects, Shepherd reviews the code changes and Watchdog re-runs affected tests. Only when both approve is the fix considered verified. Bloodhound closes the bd issue.

### Phase 4: Performance & Security

#### Step 10 — Performance Testing

| Field | Value |
|-------|-------|
| **Owner** | QA Expert 🐾 |
| **Reviewer** | Solutions Architect 🏛️ |
| **REQ** | REQ-310 |
| **Input** | Deployed application, performance baselines |
| **Output** | Performance metrics: response times, throughput, resource usage |
| **Tools** | locust, pytest-benchmark, Application Insights |
| **Exit Criteria** | Performance metrics meet defined thresholds |

**Description:** QA Expert runs performance tests to verify response times, throughput, and resource usage. Solutions Architect reviews results against architecture requirements.

#### Step 11 — Security Testing

| Field | Value |
|-------|-------|
| **Owner** | Security Auditor 🛡️ + Solutions Architect 🏛️ |
| **Reviewer** | Pack Leader 🐺 |
| **REQ** | REQ-311 |
| **Input** | STRIDE analysis (docs/security/stride-analysis.md), OWASP checklist |
| **Output** | Security test results, vulnerability report |
| **Tools** | STRIDE tables, bandit, safety, OWASP ZAP |
| **Exit Criteria** | No critical/high vulnerabilities; STRIDE rows complete |

**Description:** Security Auditor conducts security testing guided by STRIDE analysis. Solutions Architect validates architecture-level security. Results mapped to OWASP ASVS.

### Phase 5: Documentation & Closure

#### Step 12 — Update Documentation

| Field | Value |
|-------|-------|
| **Owner** | Planning Agent 📋 |
| **Reviewer** | Code Reviewer 🛡️ |
| **REQ** | REQ-312 |
| **Input** | All test results, code changes |
| **Output** | Updated README, TRACEABILITY_MATRIX, WIGGUM_ROADMAP |
| **Tools** | sync_roadmap.py, git |
| **Exit Criteria** | All documentation reflects current state |

**Description:** Planning Agent updates all project documentation to reflect completed testing, resolved issues, and current project state.

#### Step 13 — Stakeholder Feedback and Sign-off

| Field | Value |
|-------|-------|
| **Owner** | Pack Leader 🐺 + Planning Agent 📋 |
| **Reviewer** | N/A (final step) |
| **REQ** | REQ-313 |
| **Input** | Complete test report, updated documentation |
| **Output** | Stakeholder sign-off recorded in bd |
| **Tools** | `bd comment`, `bd close` |
| **Exit Criteria** | Stakeholder approval recorded; all bd issues closed |

**Description:** Pack Leader and Planning Agent present results to stakeholders. Sign-off is recorded as bd comments. This is the final gate before release.

---

## Integration with bd Issue Tracking

Testing issues flow through bd as follows:

```
bd create "Test: [feature]" --label test-prep     → Steps 1-4
bd create "Execute: [test]" --label test-exec      → Steps 5-7
bd create "Defect: [bug]"  --label defect          → Steps 8-9
bd create "Perf: [metric]" --label perf-security   → Steps 10-11
bd create "Docs: [update]" --label documentation   → Step 12
bd close [all]                                      → Step 13
```

## Integration with Pack Workflow

The 13-step methodology integrates with the Pack Leader's worktree-based parallel execution:

1. **Worktree isolation** — Each test task gets its own worktree (Terrier)
2. **Parallel execution** — Independent test steps run in parallel (Pack Leader coordinates)
3. **Critic gates** — Shepherd + Watchdog must approve before marking steps complete
4. **Local merge** — Verified changes merge to base branch (Retriever)

---

## References

- TRACEABILITY_MATRIX.md — REQ-301 through REQ-313
- Tyler Granlund, "Agile SDLC for E-Commerce" (Adobe Experience Makers, Feb 2024)
- docs/security/stride-analysis.md — Security testing baseline
- tests/ — Existing test suite structure

---

*This methodology is the single source of truth for testing process agent assignments. Updated by QA Expert 🐾, signed off by Pack Leader 🐺.*

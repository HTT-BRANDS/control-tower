# Requirements Flow — 9 Granlund Roles Mapped to Code Puppy Agents

**Date:** 2026-03-06
**Owner:** Planning Agent 📋
**Sign-off:** Pack Leader 🐺
**Task:** 3.2.1 / REQ-401
**Methodology:** Tyler Granlund's Agile SDLC Requirements Framework

---

## Overview

Tyler Granlund's Agile SDLC methodology defines 9 roles in the requirements flow, from initial stakeholder request through delivery. This document maps each role to specific Code Puppy agents, defining how requirements flow through the multi-agent system.

## Requirements Flow Diagram

```
Stakeholder Request
       │
       ▼
┌──────────────┐     ┌──────────────┐
│  1. Backlog  │────→│ 2. Business  │
│  Management  │     │   Analyst    │
│ Bloodhound   │     │ Planning Agt │
└──────────────┘     └──────┬───────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
       ┌────────────┐ ┌──────────┐ ┌──────────────┐
       │ 3. Subject │ │4. External│ │ 8. Impl     │
       │   Matter   │ │Contributors│ │  Requirements│
       │  Experts   │ │ Web Puppy │ │  Architects  │
       │ Sol+Exp Arc│ │    🕵️‍♂️     │ │  Sol+Exp Arc │
       └────────────┘ └──────────┘ └──────────────┘
              │             │             │
              └─────────────┼─────────────┘
                            ▼
                     ┌──────────────┐
                     │ 5. Product   │
                     │    Owner     │
                     │ Pack Leader  │
                     └──────┬───────┘
                            │
                     ┌──────────────┐
                     │ 6. Sprint/   │
                     │  Dev Goals   │
                     │ Pack Leader  │
                     └──────┬───────┘
                            │
                     ┌──────────────┐
                     │ 7. Team      │
                     │Collaboration │
                     │ All Agents   │
                     └──────┬───────┘
                            │
                     ┌──────────────┐
                     │ 9. Product   │
                     │   Manager    │
                     │Planning Agent│
                     └──────────────┘
```

---

## 9-Role Mapping

### Role 1: Backlog Management

| Field | Value |
|-------|-------|
| **Granlund Role** | Backlog — intake and organization of work items |
| **Mapped Agent** | Bloodhound 🐕‍🦺 |
| **Responsibility** | Create bd issues for incoming requests, apply priority labels |
| **Tools** | `bd create`, `bd update`, labels, priorities |
| **Artifacts** | bd issues with descriptions, priorities, dependencies |
| **Handoff** | → Planning Agent for decomposition |

**How it works:** When a new request arrives, Bloodhound creates a bd issue with title, description, priority, and initial labels. Dependencies are mapped using `--deps "blocks:bd-N"` syntax. The backlog is always queryable via `bd list` and `bd ready`.

### Role 2: Business Analyst

| Field | Value |
|-------|-------|
| **Granlund Role** | Analysis — decompose requests into actionable work |
| **Mapped Agent** | Planning Agent 📋 |
| **Responsibility** | Break down requests → epics → user stories → tasks |
| **Tools** | WIGGUM_ROADMAP.md, TRACEABILITY_MATRIX.md, bd |
| **Artifacts** | Epics, user stories, task breakdowns, dependency chains |
| **Handoff** | → Subject Matter Experts for domain review |

**How it works:** Planning Agent analyzes incoming requests and decomposes them into structured hierarchies: Epic → User Story → Task. Each task gets a TRACEABILITY_MATRIX entry linking REQ-ID → implementation agent → reviewer → test → sign-off.

### Role 3: Subject Matter Experts

| Field | Value |
|-------|-------|
| **Granlund Role** | Domain expertise for technical decisions |
| **Mapped Agent** | Solutions Architect 🏛️ + Experience Architect 🎨 |
| **Responsibility** | Provide domain expertise (backend + frontend) |
| **Tools** | ADRs (docs/decisions/), web-puppy research |
| **Artifacts** | Architecture Decision Records, UX specifications |
| **Handoff** | → Product Owner for prioritization |

**How it works:** Solutions Architect handles backend/infrastructure decisions (APIs, databases, security). Experience Architect handles frontend/UX decisions (accessibility, design systems, privacy). Both invoke Web Puppy for research before making recommendations.

### Role 4: External Contributors

| Field | Value |
|-------|-------|
| **Granlund Role** | External research and evidence gathering |
| **Mapped Agent** | Web Puppy 🕵️‍♂️ |
| **Responsibility** | Evidence-based research, saved to ./research/ |
| **Tools** | Web search, source evaluation, analysis |
| **Artifacts** | research/{topic}/README.md, analysis.md, sources.md, recommendations.md |
| **Handoff** | → Architects for decision-making |

**How it works:** Web Puppy conducts research when invoked by architects or planners. Research follows the research-first protocol (ADR-0004): identify topic → research → save to `research/` → produce recommendations. All research is version-controlled.

### Role 5: Product Owner

| Field | Value |
|-------|-------|
| **Granlund Role** | Review, refine, prioritize the backlog |
| **Mapped Agent** | Pack Leader 🐺 |
| **Responsibility** | Review work items, prioritize via bd, make go/no-go decisions |
| **Tools** | `bd ready`, `bd list`, `bd update --priority` |
| **Artifacts** | Prioritized backlog, sprint selections |
| **Handoff** | → Sprint/Dev Goals for execution planning |

**How it works:** Pack Leader reviews `bd ready` to see available work, adjusts priorities, and selects tasks for the current sprint. Pack Leader declares the base branch and makes strategic decisions about what to execute and in what order.

### Role 6: Sprint/Dev Goals

| Field | Value |
|-------|-------|
| **Granlund Role** | Define sprint scope and development objectives |
| **Mapped Agent** | Pack Leader 🐺 |
| **Responsibility** | Declare base branch, plan parallel execution, set sprint goals |
| **Tools** | git branch, bd labels, worktree coordination |
| **Artifacts** | Base branch declaration, sprint plan, parallel execution map |
| **Handoff** | → Team Collaboration for execution |

**How it works:** Pack Leader declares: "Working from base branch: feature/X". Then selects ready issues from bd, groups them for parallel execution, and dispatches the pack. Sprint goals are tracked via bd labels (`sprint-N`).

### Role 7: Team Collaboration

| Field | Value |
|-------|-------|
| **Granlund Role** | Cross-functional team execution |
| **Mapped Agent** | All agents via invoke_agent |
| **Responsibility** | Session-based delegation, worktree isolation |
| **Tools** | invoke_agent, session IDs, worktrees |
| **Artifacts** | Completed code, tests, documentation in worktrees |
| **Handoff** | → Critic review (Shepherd + Watchdog) |

**How it works:** Pack Leader dispatches specialized agents: Terrier creates worktrees, Husky executes tasks, Shepherd reviews code, Watchdog runs tests. Each agent works in isolation with session-based context. The invoke_agent chain creates a traceable execution graph.

### Role 8: Implementation Requirements

| Field | Value |
|-------|-------|
| **Granlund Role** | Translate business needs to technical specifications |
| **Mapped Agent** | Solutions Architect 🏛️ + Experience Architect 🎨 |
| **Responsibility** | BRDs → user stories → technical scope and specifications |
| **Tools** | ADRs, API specs, design patterns, accessibility contracts |
| **Artifacts** | Technical specs, API contracts, architecture decisions |
| **Handoff** | → Team Collaboration for implementation |

**How it works:** Architects produce technical specifications that implementation agents (Husky, Python Programmer) can execute. This includes API contracts (docs/contracts/), governance rules (.spectral.yaml), and pattern libraries (docs/patterns/).

### Role 9: Product Manager

| Field | Value |
|-------|-------|
| **Granlund Role** | Strategic oversight, roadmap alignment |
| **Mapped Agent** | Planning Agent 📋 |
| **Responsibility** | Maintain WIGGUM_ROADMAP, track cross-phase progress |
| **Tools** | WIGGUM_ROADMAP.md, sync_roadmap.py, TRACEABILITY_MATRIX.md |
| **Artifacts** | Updated roadmap, progress reports, phase completion gates |
| **Handoff** | → Stakeholder sign-off |

**How it works:** Planning Agent maintains the strategic roadmap (WIGGUM_ROADMAP.md) and ensures all work aligns with the overall SDLC plan. Uses sync_roadmap.py for automated state verification. Coordinates with Pack Leader for execution timing.

---

## How bd Tracks Requirements

Requirements flow through bd with these labels:

| Stage | bd Label | Example |
|-------|----------|---------|
| Incoming request | `backlog` | `bd create "Add OAuth" --label backlog` |
| Analysis complete | `analyzed` | `bd update ID --label analyzed` |
| Sprint-ready | `sprint-N` | `bd update ID --label sprint-1` |
| In progress | status: `in_progress` | `bd update ID --status in_progress` |
| Review | `review` | `bd update ID --label review` |
| Done | status: `closed` | `bd close ID` |

---

## Case Study: Phase 1-2 Execution

This SDLC implementation demonstrates the flow:

1. **Backlog:** Bloodhound created 32 bd issues with dependency chains
2. **Analysis:** Planning Agent decomposed into 4 phases with task trees
3. **SMEs:** Solutions Architect + Experience Architect researched tools/patterns
4. **Research:** Web Puppy produced research in `research/` directories
5. **PO:** Pack Leader selected Phase 2 tasks via `bd ready`
6. **Sprint:** Pack Leader dispatched parallel huskies for Wave 1/2
7. **Collaboration:** 29 agents collaborated across sessions
8. **Implementation:** Architects produced specs, huskies implemented
9. **Strategy:** Planning Agent tracked progress via WIGGUM_ROADMAP

---

## References

- TRACEABILITY_MATRIX.md — Epic 4 (Requirements Flow)
- Tyler Granlund, "Agile SDLC for E-Commerce" (Adobe Experience Makers, Feb 2024)
- docs/decisions/adr-0004-research-first-protocol.md

---

*This document maps Granlund's 9 requirements roles to Code Puppy agents. Updated by Planning Agent 📋, signed off by Pack Leader 🐺.*

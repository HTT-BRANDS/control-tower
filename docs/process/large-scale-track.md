# Large-Scale Track Protocol

**Date:** 2026-03-06
**Owner:** Planning Agent 📋
**Sign-off:** Pack Leader 🐺
**Task:** 3.3.2 / REQ-502
**Scope:** Dual-Scale Project Management — Large-Scale Track

---

## Overview

The large-scale track handles multi-sprint strategic initiatives: SDLC implementations, platform migrations, security overhauls, and new product lines. Work spans weeks or months, is organized into phases with dependency chains, and is tracked via WIGGUM_ROADMAP.md.

## When to Use Large-Scale

| Use Large-Scale | Use Sprint-Scale Instead |
|----------------|--------------------------|
| Multi-phase initiatives (4+ weeks) | Single features |
| Cross-cutting concerns | Bug fixes |
| Platform migrations | Routine maintenance |
| SDLC/process implementation | Small enhancements |
| Security overhauls | Documentation updates |
| New product lines | Configuration changes |

---

## WIGGUM_ROADMAP Integration

### Single Source of Truth

`WIGGUM_ROADMAP.md` is the **single source of truth** for large-scale tracking. It contains:

1. **Phase structure** — Ordered phases with clear boundaries
2. **Task trees** — Checkbox-based task tracking with validation commands
3. **Agent assignments** — Every task has a named owner and reviewer
4. **Progress summary** — Auto-updated table showing phase completion
5. **Validation commands** — Every task has a command to verify completion

### /wiggum ralph Protocol

The autonomous execution protocol for large-scale work:

```bash
# 1. Verify roadmap state
python scripts/sync_roadmap.py --verify --json

# 2. Trust the roadmap — if task marked [x], it's done
# 3. Execute next unchecked task
# 4. After completion:
python scripts/sync_roadmap.py --update --task X.Y.Z
git add WIGGUM_ROADMAP.md && git commit -m "ralph: complete task X.Y.Z"

# 5. Repeat from step 1
```

### sync_roadmap.py

The state management tool:

```bash
# Verify state (returns JSON with task counts)
python scripts/sync_roadmap.py --verify --json
# Output: {"valid": true, "total_tasks": 32, "completed_tasks": 20, ...}

# Mark task complete (updates checkbox and progress table)
python scripts/sync_roadmap.py --update --task 2.1.1
# Output: ✅ Marked task 2.1.1 as complete.
```

---

## Dedicated bd Issue Trees

### Phase-Level Organization

Large-scale work uses bd labels for phase organization:

```bash
# Phase labels
bd create "Task title" --label phase-1
bd create "Task title" --label phase-2

# Sub-domain labels within phases
bd create "STRIDE analysis" --label phase-2 --label security
bd create "MADR workflow" --label phase-2 --label architecture

# View phase scope
bd list --label phase-2
bd list --label phase-2 --label security
```

### Dependency Chains

Phases and tasks have explicit dependencies:

```bash
# Task dependencies within a phase
bd create "Auth routes" --deps "blocks:bd-1"    # blocked by User model

# Cross-phase dependencies
bd create "Phase 3 task" --deps "blocks:bd-10"  # blocked by Phase 2 task

# View dependency tree
bd dep tree bd-5
bd blocked --json  # What's waiting?
bd ready --json    # What can execute now?
```

### Isolation from Sprint Work

Large-scale issues use different labels than sprint work:

| Work Type | Labels | Example |
|-----------|--------|---------|
| Sprint | `sprint-N` | `sprint-1`, `sprint-2` |
| Large-scale | `phase-N` | `phase-1`, `phase-2` |
| Both | domain labels | `security`, `architecture` |

This allows filtering: `bd list --label sprint-1` shows only sprint work; `bd list --label phase-2` shows only large-scale work.

---

## Planning Agent Role

### Responsibilities

1. **Create WIGGUM_ROADMAP.md** — Define phases, tasks, dependencies
2. **Maintain TRACEABILITY_MATRIX.md** — Track REQ → agent → test → sign-off
3. **Review phase completions** — Verify all tasks in a phase are done
4. **Coordinate with Pack Leader** — Timing, priorities, resource allocation
5. **Update documentation** — Keep all artifacts current

### Workflow

```
Planning Agent creates WIGGUM_ROADMAP.md
         │
         ▼
Planning Agent creates bd issues (via Bloodhound)
         │
         ▼
Pack Leader executes tasks (via pack)
         │
         ▼
Planning Agent verifies completion
         │
         ▼
Planning Agent updates TRACEABILITY_MATRIX.md
         │
         ▼
Next phase begins
```

---

## Progress Tracking

### Automated Verification

```bash
# Quick status check
python scripts/sync_roadmap.py --verify --json

# Expected output:
{
  "valid": true,
  "total_tasks": 32,
  "completed_tasks": 20,
  "remaining_tasks": 12,
  "phases": {
    "1": {"total": 7, "completed": 7, "status": "✅ Complete"},
    "2": {"total": 13, "completed": 13, "status": "✅ Complete"},
    "3": {"total": 7, "completed": 0, "status": "⬜ Not Started"},
    "4": {"total": 5, "completed": 0, "status": "⬜ Not Started"}
  }
}
```

### Phase Completion Gates

A phase is complete when:
1. All tasks marked `[x]` in WIGGUM_ROADMAP.md
2. All corresponding bd issues closed
3. `sync_roadmap.py --verify` shows 0 remaining for the phase
4. Planning Agent reviews and signs off

### Progress Summary Table

Maintained in WIGGUM_ROADMAP.md:

| Phase | Total | Done | Remaining | Status |
|-------|-------|------|-----------|--------|
| Phase 1: Foundation | 7 | 7 | 0 | ✅ Complete |
| Phase 2: Governance | 13 | 13 | 0 | ✅ Complete |
| Phase 3: Process | 7 | 0 | 7 | 🔄 In Progress |
| Phase 4: Validation | 5 | 0 | 5 | ⬜ Not Started |

---

## Case Study: This SDLC Implementation

This Agile SDLC implementation IS a large-scale initiative:

### Phase 1: Foundation (Complete)
- 7 tasks: Agent catalog, traceability framework
- Duration: Initial sprint
- Key deliverables: 29 agents cataloged, WIGGUM_ROADMAP created

### Phase 2: Governance (Complete)
- 13 tasks: Security posture, architecture governance, UX/a11y
- Duration: 1 session
- Key deliverables: STRIDE analysis, ADR workflow, fitness functions, CI config

### Phase 3: Process Integration (In Progress)
- 7 tasks: Testing methodology, requirements flow, dual-scale management
- Dependencies: Blocked by Phase 2 completion
- Key deliverables: Process documentation, bd templates

### Phase 4: Validation & Closure (Not Started)
- 5 tasks: End-to-end validation, smoke tests, final review
- Dependencies: Blocked by all Phase 3 tasks
- Key deliverables: Validated system, stakeholder sign-off

---

## Session Handoff

For multi-session large-scale work, use SESSION_HANDOFF.md:

```markdown
## Session Handoff
- **Last commit:** [hash]
- **Phase:** 3 (Process Integration)
- **Tasks completed this session:** 3.1.1, 3.2.1, 3.3.1, 3.3.2
- **Next tasks:** 3.1.2, 3.2.2, 3.3.3
- **Blockers:** None
- **Notes:** [context for next session]
```

Always verify state at session start:
```bash
python scripts/sync_roadmap.py --verify --json
bd ready --json
git log --oneline -5
```

---

## References

- docs/process/sprint-track.md — Companion sprint-scale protocol
- docs/process/requirements-flow.md — Requirements flow integration
- WIGGUM_ROADMAP.md — Active roadmap
- TRACEABILITY_MATRIX.md — Requirements traceability
- scripts/sync_roadmap.py — State management tool

---

*Large-scale track protocol. Owner: Planning Agent 📋, Sign-off: Pack Leader 🐺.*

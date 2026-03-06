# Sprint-Scale Track Protocol

**Date:** 2026-03-06
**Owner:** Pack Leader 🐺
**Sign-off:** Planning Agent 📋
**Task:** 3.3.1 / REQ-501
**Scope:** Dual-Scale Project Management — Sprint Track

---

## Overview

The sprint-scale track handles short-duration focused work: features, bug fixes, enhancements, and routine maintenance. Sprints are 1–2 weeks, with clear goals, parallel execution, and critic gates before merge.

## When to Use Sprint-Scale

| Use Sprint-Scale | Use Large-Scale Instead |
|-----------------|------------------------|
| Bug fixes | Platform migrations |
| New features (1-5 tasks) | SDLC implementation |
| Enhancements | Security overhauls |
| Routine maintenance | Cross-cutting refactors |
| Documentation updates | Multi-phase initiatives |

---

## Sprint Lifecycle

### 1. Sprint Planning

```bash
# Pack Leader reviews available work
bd ready --json

# Select tasks for the sprint
bd update <id> --label sprint-1

# Declare base branch
"Working from base branch: feature/sprint-1-auth-improvements"

# Create base branch if needed
git checkout main && git checkout -b feature/sprint-1-auth-improvements
```

**Pack Leader responsibilities:**
- Review `bd ready` for unblocked tasks
- Group related tasks into a sprint
- Apply `sprint-N` labels to selected issues
- Declare the base branch
- Identify parallelization opportunities

### 2. Sprint Execution

```
┌─────────────────────────────────────────────────┐
│              PARALLEL EXECUTION                   │
│                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │ TERRIER  │  │ TERRIER  │  │ TERRIER  │       │
│  │ Worktree │  │ Worktree │  │ Worktree │       │
│  │ bd-1     │  │ bd-2     │  │ bd-3     │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
│       │              │              │             │
│  ┌────▼─────┐  ┌────▼─────┐  ┌────▼─────┐       │
│  │  HUSKY   │  │  HUSKY   │  │  HUSKY   │       │
│  │ Execute  │  │ Execute  │  │ Execute  │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
│       │              │              │             │
│  ┌────▼─────┐  ┌────▼─────┐  ┌────▼─────┐       │
│  │ SHEPHERD │  │ SHEPHERD │  │ SHEPHERD │       │
│  │ Review   │  │ Review   │  │ Review   │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
│       │              │              │             │
│  ┌────▼─────┐  ┌────▼─────┐  ┌────▼─────┐       │
│  │ WATCHDOG │  │ WATCHDOG │  │ WATCHDOG │       │
│  │ QA       │  │ QA       │  │ QA       │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
│       │              │              │             │
│  ┌────▼─────┐  ┌────▼─────┐  ┌────▼─────┐       │
│  │RETRIEVER │  │RETRIEVER │  │RETRIEVER │       │
│  │ Merge    │  │ Merge    │  │ Merge    │       │
│  └──────────┘  └──────────┘  └──────────┘       │
└─────────────────────────────────────────────────┘
```

**For each task:**

```bash
# Terrier creates worktree FROM base branch
git worktree add ../bd-1 -b feature/bd-1-auth-fix base-branch

# Husky executes the task in the worktree
cd ../bd-1 && [implement changes]

# Shepherd reviews code quality
# → Returns: APPROVE or REQUEST_CHANGES

# Watchdog runs QA checks
# → Returns: APPROVE or REQUEST_CHANGES

# If both approve: Retriever merges
git checkout base-branch
git merge feature/bd-1-auth-fix --no-ff -m "Merge bd-1: auth fix"

# Bloodhound closes the issue
bd close bd-1

# Cleanup
git worktree remove ../bd-1
git branch -d feature/bd-1-auth-fix
```

### 3. Sprint Review

At sprint end, Pack Leader:
- Verifies all sprint-labeled issues are closed: `bd list --label sprint-1`
- Checks for remaining open issues
- Produces sprint summary
- Updates documentation if needed

### 4. Sprint Retrospective

Pack Leader + Planning Agent review:
- What went well? (parallel execution, critic quality)
- What didn't? (agent failures, merge conflicts)
- Process improvements for next sprint

---

## bd Sprint Integration

### Sprint Labels

```bash
# Label tasks for a sprint
bd update azure-governance-platform-xxx --label sprint-1

# View sprint scope
bd list --label sprint-1

# Track sprint progress
bd list --label sprint-1 --status closed    # Done
bd list --label sprint-1 --status open      # Remaining
```

### Sprint Board View

```
SPRINT-1 BOARD
═══════════════

READY          IN PROGRESS       REVIEW          DONE
──────         ───────────       ──────          ────
bd-5: API      bd-2: Auth fix   bd-1: Models    bd-3: Config
bd-6: Tests    bd-4: Routes                     bd-7: Docs
```

### Velocity Tracking

Track issues closed per sprint over time:

| Sprint | Planned | Completed | Velocity |
|--------|---------|-----------|----------|
| Sprint 1 | 8 | 7 | 87.5% |
| Sprint 2 | 7 | 7 | 100% |
| Sprint 3 | 9 | 8 | 88.9% |

---

## Worktree-Per-Task Pattern

### Why Worktrees?

1. **Isolation** — Each task works in its own directory, no interference
2. **Parallel** — Multiple huskies can work simultaneously
3. **Clean rollback** — Failed tasks don't affect other work
4. **Review-friendly** — Shepherd can review one worktree while Husky works on another

### Branch Naming Convention

```
feature/bd-{issue-id}-{short-slug}

Examples:
  feature/bd-1-user-model
  feature/bd-2-auth-routes
  feature/bd-3-jwt-middleware
```

### Worktree Directory Structure

```
project-root/          ← Main worktree (base branch)
../bd-1/               ← Worktree for issue bd-1
../bd-2/               ← Worktree for issue bd-2
../bd-3/               ← Worktree for issue bd-3
```

---

## Critic Gates

### Shepherd (Code Review)

Shepherd evaluates:
- Code style and best practices
- Architecture alignment
- Potential bugs or edge cases
- Documentation completeness

Returns: `APPROVE` or `REQUEST_CHANGES` with specific feedback.

### Watchdog (QA)

Watchdog evaluates:
- All tests pass (`pytest`)
- No regressions introduced
- Coverage meets threshold
- Functionality matches acceptance criteria

Returns: `APPROVE` or `REQUEST_CHANGES` with test results.

### Gate Rules

1. **Both must approve** — No exceptions
2. **REQUEST_CHANGES loops back** — Husky fixes in same worktree, then re-review
3. **Max 3 review cycles** — Escalate to Pack Leader if issues persist
4. **Comments tracked in bd** — `bd comment <id> "Shepherd: APPROVE"`

---

## Merge Protocol

```bash
# 1. Retriever checks out base branch
git checkout feature/sprint-1-base

# 2. Merge with --no-ff for clear history
git merge feature/bd-1-user-model --no-ff -m "Merge bd-1: User model implementation"

# 3. Verify merge is clean
git log --oneline -3
pytest tests/ -x --timeout=60

# 4. Bloodhound closes the issue
bd close bd-1

# 5. Cleanup worktree
git worktree remove ../bd-1
git branch -d feature/bd-1-user-model
```

---

## Example Sprint: Phase 2 Security Tasks

Phase 2 Wave 1 demonstrates the sprint pattern:

1. **Planning:** Pack Leader identified 5 P1 tasks from `bd ready`
2. **Execution:** 5 huskies dispatched in parallel for STRIDE, YOLO, MCP, self-mod, MADR
3. **Review:** Files validated against acceptance criteria
4. **Merge:** All committed to `feature/agile-sdlc` base branch
5. **Closure:** bd issues closed, roadmap updated

---

## References

- docs/process/large-scale-track.md — Companion large-scale protocol
- docs/process/requirements-flow.md — Requirements flow integration
- TRACEABILITY_MATRIX.md — REQ-501

---

*Sprint-scale track protocol. Owner: Pack Leader 🐺, Sign-off: Planning Agent 📋.*

# Development & Deployment Status

> Last updated: Session ending with commit `9e70992` on `main`

## Phase Completion Status

| Phase | Description | Status | Branch |
|-------|-------------|--------|--------|
| **Phase 1** | Core Platform & Riverside Compliance | ✅ Complete | Merged to `main` |
| **Phase 2** | Backfill Infrastructure & UI Foundations | ✅ Complete | Merged to `main` |
| **Phase 3** | Azure Lighthouse Integration | ✅ Complete | Merged to `main` |
| **Phase 4** | Data Backfill (Cost, Identity, Compliance) | 🔲 Not Started | — |
| **Phase 5** | WCAG 2.2 Accessibility & Dark Mode | 🔲 Not Started | — |
| **Phase 6** | App Insights, Retention, Final QA | 🔲 Not Started | — |

## Test Suite Health

**Overall: 599 passed, 49 failed, 3 skipped** (92.3% pass rate)

### ✅ Fully Passing Test Files
- `tests/unit/test_lighthouse_client.py` — 22 passed, 3 skipped
- `tests/unit/test_onboarding.py` — 25 passed
- `tests/unit/test_riverside_mfa_sync.py` — 11 passed (2 failed)
- All other test files (564+ tests)

### ❌ Known Failures (49 tests across 7 files)

| File | Failed | Root Cause | Bead |
|------|--------|-----------|------|
| `test_riverside_api.py` | 9 | Route calls non-existent service methods | `9gx` (P1) |
| `test_riverside_preflight.py` | 8 | Pre-existing preflight validation mismatches | `im3` (P2) |
| `test_riverside_sync.py` | 8 | Azure mock interference + assertion mismatches | `1yr` (P2) |
| `test_mfa_preflight.py` | 10 | Pre-existing preflight test mismatches | `im3` (P2) |
| `test_graph_mfa.py` | 6 | Graph client pagination/filtering issues | `im3` (P2) |
| `test_riverside_service.py` | 5 | Service layer test mismatches | `im3` (P2) |
| `test_riverside_mfa_sync.py` | 2 | Exception handling + partial failure mock | `1yr` (P2) |

## Phase 3: Lighthouse Integration (Completed)

### Components Delivered
- **Infrastructure**: ARM delegation template (`infrastructure/lighthouse/delegation.json`), setup script (`scripts/setup-lighthouse.sh`)
- **Client**: `LighthouseAzureClient` with circuit breaker, rate limiting, retry (`app/services/lighthouse_client.py`)
- **Onboarding**: Self-service HTMX UI + JSON API (`app/api/routes/onboarding.py`)
- **Tests**: Full coverage for lighthouse client (25 tests) and onboarding (25 tests)

### Key Architecture Decisions
- Uses Azure Managed Identity + DefaultAzureCredential (no per-tenant secrets)
- HTMX-first UI with JSON API fallback for programmatic access
- Form-based inputs for onboarding (not JSON body)
- Status endpoint returns JSON with nested tenant structure

## Open Beads (Issue Tracker)

### P1 — High Priority
| Bead ID | Title | Phase |
|---------|-------|-------|
| `9gx` | Fix Riverside API route-service method mismatch | Bug fix |
| `mx3` | Cost Data Backfill | Phase 4 |
| `yg0` | Identity Data Backfill | Phase 4 |
| `t4h` | Compliance & Resources Backfill | Phase 4 |

### P2 — Medium Priority
| Bead ID | Title | Phase |
|---------|-------|-------|
| `1yr` | Fix Riverside sync test assertion mismatches | Bug fix |
| `im3` | Fix Riverside preflight and service test failures | Bug fix |
| `n4e` | WCAG 2.2 Accessibility Implementation | Phase 5 |
| `cje` | Dark Mode Support | Phase 5 |
| `4vv` | Application Insights Integration | Phase 6 |
| `6ty` | Data Retention Service | Phase 6 |
| `59g` | Final QA Testing Suite | Phase 6 |

## Git State
- **Main branch**: `main` (up to date with `origin/main`)
- **Active worktrees**: 1 (main only — all stale worktrees cleaned)
- **Stale branches cleaned**: 37 merged feature branches deleted
- **Stale worktrees cleaned**: 35 worktrees removed

## Recommended Next Steps (Priority Order)
1. **Fix `9gx`** — Riverside API route-service method mismatch (P1 bug, 9 tests)
2. **Start Phase 4** — Data backfill (mx3, yg0, t4h)
3. **Fix `1yr` + `im3`** — Remaining test failures (P2)
4. **Phase 5** — Accessibility & dark mode
5. **Phase 6** — Observability, retention, final QA

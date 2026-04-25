# Browser smoke CI rollout and artifact policy

This document operationalizes the browser-smoke CI rollout from
`docs/plans/ci-browser-gate-and-prod-sync-plan-2026-04-24.md`.

## Job shape

- Workflow: `.github/workflows/ci.yml`
- Job name: `browser-smoke`
- Dependency: runs after `lint-and-test`
- Parallelism: runs in parallel with `security-scan`
- Current rollout mode: blocking CI gate (non-blocking soak has ended)
- Test selection: `tests/e2e/test_browser_smoke.py`

## Pinned execution environment

- Python: `3.12`
- uv action version: `0.5.x`
- Playwright Python package: pinned in lockfile / requirements-dev (`1.58.0`)
- Browser install command: `uv run playwright install chromium --with-deps`
- App startup command:
  `uv run python -m uvicorn app.main:app --host 127.0.0.1 --port 8099 --log-level warning`

## Readiness and timeouts

- Explicit readiness probe: `python scripts/wait_for_url.py http://127.0.0.1:8099/api/v1/health --timeout 45 --interval 1`
- CI job timeout: 15 minutes
- App startup timeout: 45 seconds
- Smoke scope stays limited to the first-wave gated routes and partials only

## Artifact policy

Artifacts are uploaded **only on failure** and retained briefly.

Allowed artifacts:
- Playwright screenshots under `tests/e2e/screenshots/`
- concise pytest output / smoke log capture

Prohibited artifacts:
- cookie dumps
- auth headers
- storage state files
- Playwright traces containing unsanitized network/auth material
- HAR/network captures

Current implementation uploads only screenshots and concise text logs, which is
intentionally boring and much safer than clever trace hoarding.

## Soak and promotion policy

The initial non-blocking soak is complete. `browser-smoke` is now expected to
run as a blocking CI gate.

Promotion criteria that justified the move:

1. the stabilization children under `azure-governance-platform-aiob` were completed
2. scheduler interference was removed for browser/e2e startup
3. deterministic seeded/empty-state contracts were defined for gated routes and partials
4. failure artifacts remain intentionally sanitized and actionable

If the promoted gate exceeds the flake threshold for 3 consecutive runs,
demote it from required status only with an explicit tracked issue/incident and
fix forward immediately.

## Branch protection / ruleset follow-up

GitHub branch protection or rulesets for `main` must require both of these
checks to pass and be up to date before merge:

- `browser-smoke`
- `security-scan`

Repository administrators should treat missing branch protection/rulesets as a
release-readiness gap, not as an excuse to pretend the workflow alone is enough.
Any temporary bypass or demotion must be explicitly approved and tracked in an
issue or incident note. No invisible "just this once" nonsense.

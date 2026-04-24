# Browser smoke CI rollout and artifact policy

This document operationalizes the browser-smoke CI rollout from
`docs/plans/ci-browser-gate-and-prod-sync-plan-2026-04-24.md`.

## Job shape

- Workflow: `.github/workflows/ci.yml`
- Job name: `browser-smoke`
- Dependency: runs after `lint-and-test`
- Parallelism: runs in parallel with `security-scan`
- Initial rollout mode: non-blocking (`continue-on-error: true`)
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

Initial rollout is non-blocking. Promote to required only after:

1. at least 10 consecutive green `browser-smoke` runs across several days of PR traffic
2. non-actionable failure rate stays below 5%
3. runtime remains within the p95 target budget (<7 minutes)
4. failure artifacts remain actionable and sanitized

If the promoted gate exceeds the flake threshold for 3 consecutive runs,
demote it from required status and fix forward.

## Branch protection / ruleset follow-up

After soak promotion, GitHub branch protection or rulesets for `main` must
require both of these checks to pass and be up to date before merge:

- `browser-smoke`
- `security-scan`

Any temporary bypass or demotion must be explicitly approved and tracked in an
issue or incident note. No invisible "just this once" nonsense.

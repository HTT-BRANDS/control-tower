# Visual Parity Baselines

This directory holds pinned PNG screenshots used by
`tests/e2e/test_visual_parity.py`.

**Status (2026-06):** Infrastructure is wired and the capture script works.
Baselines have not been committed to the repo because PNG snapshots are
machine-rendering-dependent (font anti-aliasing, GPU compositing) and would
create flaky CI failures across different OS images. Capture them locally on
the machine you want to use as the reference, or run the scheduled capture
job against a stable staging URL.

## Expected files

One PNG per migrated page, matching the `PAGES` list in `test_visual_parity.py`:

- `dashboard.png`
- `costs.png`
- `compliance.png`
- `resources.png`
- `identity.png`
- `franchise-coach.png`

## How to populate

### Quick path (self-baseline from local seeded app)

```bash
# 1. Seed the local database
make local-db-reset local-seed

# 2. Capture (app starts automatically on port 8099)
make capture-baselines

# 3. Run the visual tests to confirm baselines pass
uv run pytest -m visual -v
```

The capture script waits for each page's readiness selector, then takes a
full-page screenshot at 1280x720. If the HTMX partial endpoints are slow,
try increasing the wait in `scripts/capture_visual_baselines.py`.

### Against staging (recommended for the CI baseline)

```bash
make capture-baselines CAPTURE_URL=https://app-governance-staging-xnczpwyv.azurewebsites.net
```

This requires the staging server to be up and responding (allow 120s cold-start).

### Subset only

```bash
uv run python scripts/capture_visual_baselines.py --only dashboard costs
```

## Running the tests

Opt-in via the `visual` pytest marker. Tests **skip cleanly** when baselines
are missing — they do not fail CI when PNGs are absent.

```bash
uv run pytest -m visual -v          # all visual tests
uv run pytest -m visual -k costs    # one page
```

When a test fails, before/after/diff PNGs land in `tests/e2e/visual_diffs/`
(git-ignored). Inspect `{page}.diff.png` to see exactly what changed.

## Tolerance

Default: 0.5% of pixels may differ (font anti-aliasing, sub-pixel layout).
Override per-run:

```bash
VISUAL_TOLERANCE_PCT=1.0 uv run pytest -m visual
```

## When a design change is intentional

Re-run `make capture-baselines` to update baselines, then commit the updated
PNG(s) alongside the code change. The PNG diff makes the design decision
visible in code review.

## CI integration

The `full-suite` runner includes a `WITH_VISUAL=1` optional gate that runs the
visual suite. It skips cleanly when baselines are absent so CI never fails due
to missing PNGs. To run locally with the visual gate:

```bash
WITH_VISUAL=1 bash scripts/run_full_suite.sh
```

# Visual Parity Baselines

This directory holds pinned PNG screenshots used by
`tests/e2e/test_visual_parity.py`.

**Status (2026-06):** Baselines are committed and the visual gate is green.

**CRITICAL — how baselines must be captured:** baselines MUST be blessed
through the *same* browser context that compares them (`VISUAL_UPDATE=1`).
A baseline captured by a *different* context — e.g. the standalone
`capture_visual_baselines.py` script — drifts at the sub-pixel level (font
hinting / deviceScaleFactor differences), producing a uniform text-ghosting
diff of ~3-4% on every run even though nothing actually changed. This is the
same reason Playwright ships `--update-snapshots`. Always use `make
capture-baselines` (which runs `VISUAL_UPDATE=1 pytest -m visual`).

## Expected files

One PNG per migrated page, matching the `PAGES` list in `test_visual_parity.py`:

- `dashboard.png`
- `costs.png`
- `compliance.png`
- `resources.png`
- `identity.png`
- `franchise-coach.png`

## How to populate (the right way)

```bash
# Seeds the local demo DB, blesses baselines through the test's own context,
# then verifies they pass. This is the ONLY supported local path.
make capture-baselines
```

Under the hood that runs:
```bash
make local-db-reset local-seed
VISUAL_UPDATE=1 pytest -m visual   # writes baselines via the test context
make visual-test                   # verifies they pass
```

### Determinism safeguards already built in

The test + capture path neutralises the three things that otherwise make
full-page dashboard screenshots flaky:

1. **HTMX background polling** — we wait for `load` + a fixed settle, never
   `networkidle` (which never fires on a polling page).
2. **GDPR consent banner** — a `consent_preferences` cookie is pre-seeded so
   the banner never renders (it would shove all content down 5-20px).
3. **Sub-pixel font drift** — baselines are blessed through the comparison
   context (`VISUAL_UPDATE=1`), so rendering is identical run-to-run.

### Standalone script (remote URLs only)

`scripts/capture_visual_baselines.py` is retained for capturing against a
remote URL (e.g. staging) where the in-process test server isn't used. Do NOT
use it to bless local gate baselines — its context differs from the test's
and will reintroduce the sub-pixel drift.

```bash
uv run python scripts/capture_visual_baselines.py \
  --base-url https://app-governance-staging-xnczpwyv.azurewebsites.net
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

# Running the test suite (supported invocations)

> TL;DR: use `make test-ci` (or `make test-all`). **Do NOT run a bare
> `pytest tests/`** — it mixes test groups in one process and produces
> misleading order-dependent failures. See "Why" below.

## Supported commands

| Command | What it runs | When |
|---------|--------------|------|
| `make test` | `tests/unit` | fast inner loop |
| `make test-ci` | `tests/unit tests/integration` + coverage | mirrors CI exactly |
| `make test-all` | every group, **in isolated passes** | full local verification |

CI runs:

```bash
uv run pytest tests/unit/ tests/integration/ -m "not visual" --cov=app --cov-fail-under=35
```

This is fully green (4295 passed at time of writing).

## Why not `pytest tests/`?

The repo has test groups with very different runtime needs:

- `tests/unit`, `tests/integration` — the 4000+ core tests (CI gate).
- `tests/architecture` — fitness functions (file size, layering, security constraints).
- `tests/chaos` — resilience / circuit-breaker / failure-injection tests.
- `tests/performance` — timing-sensitive checks.
- `tests/e2e`, `tests/load`, `tests/smoke`, `tests/staging` — ignored by default
  (`addopts` in `pyproject.toml`); they need a running server or live URLs.

The architecture/chaos/performance suites exercise **sync↔async bridges**
(`asyncio.run()`, `loop.run_until_complete()`, `ThreadPoolExecutor` wrappers)
and run under `pytest-asyncio` `asyncio_mode = "auto"`. When they execute in the
**same process** as the unit tests, the collection ordering can leave a running
event loop active, after which later tests that bridge sync→async fail with:

```
RuntimeError: Runner.run() cannot be called from a running event loop
```

This cascades into hundreds of order-dependent failures — none of which are real
product defects (every group passes cleanly in its own process). To prove it:

```bash
pytest tests/unit tests/integration -m "not visual"   # green (4295)
pytest tests/architecture                              # green (43)
pytest tests/chaos                                     # green (57)
pytest tests/performance                               # green (3)
```

## Enforcement

`make test-all` deliberately invokes each group as a **separate `pytest`
process** (fresh interpreter + event loop), so "run all the tests" is green and
trustworthy. The bare `pytest tests/` anti-pattern is documented here and in the
`Makefile` `test-all` target so nobody is misled by it again.

A future hardening (tracked in ct-pm3) could make the sync↔async bridge helpers
loop-safe so a single-process full run also passes, but that touches widely-used
runtime code and is not worth destabilizing the green suite for. The isolated-
pass boundary is the supported contract today.

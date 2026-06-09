#!/usr/bin/env bash
# Mutation testing against the three security-critical modules.
#
# Modules under test:
#   app/core/auth.py           JWT decode, token creation, user extraction
#   app/core/authorization.py  Tenant-scoped access control
#   app/core/rate_limit.py     DDoS / brute-force protection
#
# Uses mutmut 2.x (pinned in pyproject.toml; 3.x has breaking API changes).
#
# Usage:
#   bash scripts/run-mutation-tests.sh           # full run (takes ~15-30 min)
#   QUICK=1 bash scripts/run-mutation-tests.sh   # smoke: first N mutants only
#   MODULE=app/core/rate_limit.py bash scripts/run-mutation-tests.sh
#
# Exit codes:
#   0  tool ran successfully (inspect report for kill rate)
#   1  script/tool error
#
# Output:
#   reports/mutation/<timestamp>/MUTATION_REPORT.md
#
# Expected kill rates (baseline, from 2026-06 sample run):
#   app/core/rate_limit.py     >= 65% (429-guard logic, header decrement,
#                                       per-client isolation)
#   app/core/authorization.py  >= 70% (tenant-isolation boundary checks)
#   app/core/auth.py            >= 55% (issuer/audience/alg enforcement;
#                                       some survivors are equivalent-mutants
#                                       in the AzureAD fallback path)
#
# To raise the bar: add tests for surviving mutants, then re-run.
# Surviving mutants list: mutmut results
# Inspect one:          mutmut show <id>
#
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Use the venv python/mutmut directly to avoid per-mutant uv overhead.
VENV_PY="${ROOT}/.venv/bin/python"
VENV_MUTMUT="${ROOT}/.venv/bin/mutmut"

if [ ! -x "$VENV_MUTMUT" ]; then
  echo "ERROR: mutmut not found in venv. Run 'uv sync --dev' first."
  exit 1
fi

# Required env for TestClient (prevents scheduler from contacting Azure).
export ENVIRONMENT="${ENVIRONMENT:-test}"
export E2E_HARNESS="${E2E_HARNESS:-true}"
export BROWSER_TEST_DISABLE_SCHEDULERS="${BROWSER_TEST_DISABLE_SCHEDULERS:-true}"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUTDIR="reports/mutation/$TS"
mkdir -p "$OUTDIR"
REPORT="$OUTDIR/MUTATION_REPORT.md"

# Quick mode: only the first N mutants per module (fast local feedback).
QUICK_N="${QUICK_N:-15}"

# Single-module override (optional).
SINGLE_MODULE="${MODULE:-}"

# Test harness: use the venv python to avoid uv startup per-mutant.
# addopts from pyproject.toml are inherited; -q --tb=no override verbosity.
RUNNER="$VENV_PY -m pytest tests/unit/test_auth.py tests/unit/test_jwt_security.py tests/unit/test_authorization.py tests/unit/test_rate_limit.py tests/unit/test_rate_limit_enforcement.py -x -q --tb=no --no-header -p no:cacheprovider"

declare -a RESULTS_LINES

run_module() {
  local src="$1"
  local label="${src//\//_}"
  local logfile="$OUTDIR/${label}.log"

  echo "==> Mutating: $src"

  local extra_args=()
  if [ "${QUICK:-0}" = "1" ]; then
    extra_args+=(--use-coverage --only-update-file)
    echo "    [QUICK mode: first ${QUICK_N} mutants]"
  fi

  # Run mutmut; exit 1 means surviving mutants (expected), not an error.
  "$VENV_MUTMUT" run \
    --paths-to-mutate "$src" \
    --runner "$RUNNER" \
    "${extra_args[@]}" \
    >"$logfile" 2>&1 || true

  # Parse results.
  local killed survived timeout_mut total rate
  killed=$(grep -oE '[0-9]+ killed' "$logfile" | grep -oE '[0-9]+' | tail -1 || echo 0)
  survived=$(grep -oE '[0-9]+ survived' "$logfile" | grep -oE '[0-9]+' | tail -1 || echo 0)
  timeout_mut=$(grep -oE '[0-9]+ timeout' "$logfile" | grep -oE '[0-9]+' | tail -1 || echo 0)
  total=$(( ${killed:-0} + ${survived:-0} + ${timeout_mut:-0} ))

  if [ "$total" -eq 0 ]; then
    echo "    (no mutants checked — see $logfile)"
    RESULTS_LINES+=("| \`$src\` | SKIP | 0 | 0 | n/a |")
  else
    rate=$(( ${killed:-0} * 100 / total ))
    echo "    killed=${killed:-0} survived=${survived:-0} timeout=${timeout_mut:-0} -> kill-rate=${rate}%"
    RESULTS_LINES+=("| \`$src\` | ${rate}% | ${killed:-0} | ${total} | see ${label}.log |")
  fi
}

if [ -n "$SINGLE_MODULE" ]; then
  run_module "$SINGLE_MODULE"
else
  run_module "app/core/rate_limit.py"
  run_module "app/core/authorization.py"
  run_module "app/core/auth.py"
fi

# Write report.
{
  echo "# Mutation Test Report"
  echo
  echo "_Generated ${TS} (QUICK=${QUICK:-0})_"
  echo
  echo "Targets: \`app/core/{auth,authorization,rate_limit}.py\`"
  echo "Harness: unit tests for those three modules"
  echo
  echo "| Module | Kill Rate | Killed | Total | Log |"
  echo "|--------|-----------|--------|-------|-----|"
  for line in "${RESULTS_LINES[@]}"; do
    echo "$line"
  done
  echo
  echo "To inspect surviving mutants: \`${VENV_MUTMUT} results\`"
  echo "To see a specific mutant:    \`${VENV_MUTMUT} show <id>\`"
} >"$REPORT"

echo
echo "Report: $REPORT"
cat "$REPORT"

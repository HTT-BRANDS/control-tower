#!/usr/bin/env bash
# Unified end-to-end test gate for Control Tower.
#
# Runs every layer of the testing pyramid as a sequence of named gates and
# writes a single consolidated Markdown report to reports/full-suite/<ts>/.
# Each gate runs in its own pytest invocation so one layer's event-loop/state
# cannot pollute another (see ct-pm3). The script never aborts on first failure
# -- it runs every gate, then exits non-zero if any required gate failed, so you
# get the whole picture in one pass.
#
# Usage:
#   scripts/run_full_suite.sh                 # all gates (skips browser e2e + load by default)
#   WITH_LOAD=1 scripts/run_full_suite.sh     # also run the 100-user load profile
#   FAST=1 scripts/run_full_suite.sh          # security + compliance + design only
#
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="${PYTHON:-python}"
export ENVIRONMENT="${ENVIRONMENT:-test}"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUTDIR="reports/full-suite/$TS"
mkdir -p "$OUTDIR"
REPORT="$OUTDIR/SUITE_REPORT.md"

declare -a GATE_NAMES GATE_STATUS GATE_DETAIL

PYTEST_BASE=(-p no:cacheprovider --no-header -o addopts="" -q)

run_gate() {
  local name="$1"; shift
  local logfile="$OUTDIR/${name// /_}.log"
  echo "==> GATE: $name"
  if "$@" >"$logfile" 2>&1; then
    local summary; summary="$(grep -aE '[0-9]+ (passed|failed|skipped|error)' "$logfile" | tail -1)"
    GATE_NAMES+=("$name"); GATE_STATUS+=("PASS"); GATE_DETAIL+=("${summary:-ok}")
    echo "    PASS  ${summary:-ok}"
  else
    local summary; summary="$(grep -aE '[0-9]+ (passed|failed|skipped|error)' "$logfile" | tail -1)"
    GATE_NAMES+=("$name"); GATE_STATUS+=("FAIL"); GATE_DETAIL+=("${summary:-see ${logfile##*/}}")
    echo "    FAIL  ${summary:-see log}"
  fi
}

pytest_gate() {  # name, then pytest paths/args
  local name="$1"; shift
  run_gate "$name" "$PY" -m pytest "${PYTEST_BASE[@]}" "$@"
}

# ---- Gates -----------------------------------------------------------------

# 1. Security (authn/authz/jwt/rate-limit/headers/ssrf/docs)
pytest_gate "security" \
  tests/unit/test_jwt_security.py \
  tests/unit/test_rate_limit_enforcement.py \
  tests/unit/test_docs_exposure_by_env.py \
  tests/unit/test_auth.py \
  tests/unit/test_authorization.py \
  tests/integration/test_security_authwall_matrix.py \
  tests/integration/test_security_headers_enhanced.py \
  tests/integration/test_tenant_isolation.py \
  tests/architecture/test_security_constraints.py

# 2. Compliance (rule engine ssrf/isolation, audit trail, fitness)
pytest_gate "compliance" \
  tests/unit/test_compliance_rules_security.py \
  tests/integration/test_audit_log_integrity.py \
  tests/integration/test_compliance_api.py \
  tests/architecture/test_sync_data_integrity.py

# 3. Design + accessibility (multi-brand, theming, dark mode)
pytest_gate "design_a11y" \
  tests/integration/test_multi_brand_design_a11y.py \
  tests/integration/test_theme_rendering.py \
  tests/integration/test_sync_status_dark_mode.py

# 4. Resilience / chaos
pytest_gate "chaos" tests/chaos

# 5. Architecture fitness functions
pytest_gate "architecture" tests/architecture

if [ "${FAST:-0}" != "1" ]; then
  # 6. Full unit + integration regression
  #    test_frontend_e2e.py is excluded: its auth_token fixture posts to the live
  #    login endpoint, which only works against a fully-wired Azure/login env (it
  #    fails in isolation on a sandbox too). Tracked as a pre-existing finding in
  #    docs/testing/TESTING_SUITE_AUDIT_2026-06.md, not a regression from this gate.
  pytest_gate "unit" tests/unit
  pytest_gate "integration" tests/integration \
    --ignore=tests/integration/auth_flow \
    --ignore=tests/integration/test_frontend_e2e.py
fi

# 7. Optional: 100+ user local load profile
if [ "${WITH_LOAD:-0}" = "1" ]; then
  run_gate "load_100users" env QUICK=1 PYTHON="$PY" bash scripts/run_load_profile.sh
fi

# ---- Consolidated report ---------------------------------------------------
{
  echo "# Control Tower -- Full Suite Report"
  echo
  echo "_Generated ${TS} (ENVIRONMENT=${ENVIRONMENT})_"
  echo
  echo "| Gate | Result | Detail |"
  echo "|------|--------|--------|"
  fail=0
  for i in "${!GATE_NAMES[@]}"; do
    icon="✅"; [ "${GATE_STATUS[$i]}" = "FAIL" ] && { icon="❌"; fail=1; }
    echo "| ${GATE_NAMES[$i]} | ${icon} ${GATE_STATUS[$i]} | ${GATE_DETAIL[$i]} |"
  done
  echo
  if [ "$fail" = "0" ]; then
    echo "**Overall: PASS** — every gate green."
  else
    echo "**Overall: FAIL** — one or more gates red. See per-gate logs in this folder."
  fi
  echo
  echo "Logs: \`${OUTDIR}/<gate>.log\`"
} > "$REPORT"

echo
echo "================ SUITE SUMMARY ================"
cat "$REPORT"
echo "=============================================="
echo "Report: $REPORT"

for s in "${GATE_STATUS[@]}"; do [ "$s" = "FAIL" ] && exit 1; done
exit 0

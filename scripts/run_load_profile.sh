#!/usr/bin/env bash
# Run the staged 100+ user load profile against a *local* app instance.
#
# Boots uvicorn on a throwaway SQLite DB, waits for /health, runs locust headless
# through StagedStressShape, writes CSV + HTML to reports/load/, and tears the
# server down. Exits non-zero if the p95 SLA is breached or error rate > 1%.
#
# Usage:
#   scripts/run_load_profile.sh            # full ~150s staged profile
#   QUICK=1 scripts/run_load_profile.sh    # short 100-user/20s verification
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="${PYTHON:-python}"
HOST="http://127.0.0.1:8000"
OUTDIR="reports/load"
mkdir -p "$OUTDIR"

export ENVIRONMENT="${ENVIRONMENT:-test}"
export E2E_HARNESS="true"   # disable the rate-limit middleware so we measure the app, not the throttle
# Pin a stable JWT secret so the locust process can mint tokens the server accepts.
export JWT_SECRET_KEY="${JWT_SECRET_KEY:-load-test-fixed-secret-key-32bytes-minimum-xx}"

echo "==> Starting local app server"
$PY -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --log-level warning &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT

echo "==> Waiting for /health"
for i in $(seq 1 60); do
  if curl -fsS "$HOST/health" >/dev/null 2>&1; then
    echo "    server up after ${i}s"
    break
  fi
  sleep 1
  if [ "$i" = "60" ]; then echo "ERROR: server did not become healthy"; exit 1; fi
done

if [ "${QUICK:-0}" = "1" ]; then
  echo "==> QUICK verification: 100 users / 20s (flat, authenticated)"
  $PY -m locust -f tests/load/locust_stress_profile.py \
    --host "$HOST" --headless \
    --users 100 --spawn-rate 25 --run-time 20s \
    --csv "$OUTDIR/quick" --html "$OUTDIR/quick.html" \
    --only-summary
  SUMMARY="$OUTDIR/quick_stats.csv"
else
  echo "==> Full staged stress profile (ramp -> 120 -> spike 160 -> soak 100)"
  $PY -m locust -f tests/load/locust_stress_profile.py \
    --host "$HOST" --headless \
    --csv "$OUTDIR/stress" --html "$OUTDIR/stress.html" \
    --only-summary
  SUMMARY="$OUTDIR/stress_stats.csv"
fi

echo "==> Load run complete. Summary: $SUMMARY"
$PY - "$SUMMARY" <<'PYEOF'
import csv, sys
path = sys.argv[1]
with open(path) as f:
    rows = list(csv.DictReader(f))
agg = next((r for r in rows if r.get("Name") == "Aggregated"), None)
if not agg:
    print("No aggregated row found"); sys.exit(0)
p95 = float(agg.get("95%", agg.get("95%ile", 0)) or 0)
reqs = float(agg.get("Request Count", 0) or 0)
fails = float(agg.get("Failure Count", 0) or 0)
err = (fails / reqs * 100) if reqs else 0
print(f"   requests={int(reqs)}  failures={int(fails)}  err={err:.2f}%  p95={p95:.0f}ms")
problems = []
if p95 > 500: problems.append(f"p95 {p95:.0f}ms > 500ms SLA")
if err > 1.0: problems.append(f"error rate {err:.2f}% > 1%")
if problems:
    print("   SLA BREACH: " + "; ".join(problems)); sys.exit(2)
print("   SLA OK")
PYEOF

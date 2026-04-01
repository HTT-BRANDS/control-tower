#!/bin/bash
# Weekly Operations Review - Run every Monday

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║  WEEKLY OPERATIONS REVIEW - Week $(date +%U)             ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# 1. Smoke Tests
echo "🧪 Running smoke tests..."
make smoke-test 2>&1 | tail -10

# 2. Quick Load Test
echo ""
echo "⚡ Running quick load test..."
make load-test-smoke 2>&1 | tail -10

# 3. Check Weekly Metrics
echo ""
echo "📊 Weekly Metrics (manual check):"
echo "  - Open Azure Portal → App Insights → Usage"
echo "  - Review: Request count, response times, exceptions"
echo "  - Target: <1% error rate, <500ms p95 response"

# 4. Cost Review
echo ""
echo "💰 Cost Review:"
echo "  - Check: Portal → Cost Management"
echo "  - Compare to budget: ~$12/month"
echo "  - Look for: Unexpected spikes, unused resources"

# 5. Documentation Check
echo ""
echo "📚 Documentation:"
echo "  - Review any alerts from the week"
echo "  - Update operational runbook if needed"
echo "  - Check: Any new issues or observations"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  WEEKLY REVIEW COMPLETE"
echo "═══════════════════════════════════════════════════════════"

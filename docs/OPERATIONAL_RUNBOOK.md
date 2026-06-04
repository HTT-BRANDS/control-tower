# HTT Control Tower - Operational Runbook

**For:** Operations, DevOps, and SRE Teams  
**Version:** 2.5.0  
**Last Updated:** 2026-06-04

> New to Control Tower? Read `docs/OPS_ONBOARDING.md` first (what each
> dashboard means, what "stale" means, who to call). This runbook is the
> SRE/operational reference; the onboarding guide is the day-one walkthrough.

---

## Quick Reference

### Production URLs
- **Application:** https://app-governance-prod.azurewebsites.net
- **Health Check:** https://app-governance-prod.azurewebsites.net/health
- **Data freshness:** https://app-governance-prod.azurewebsites.net/healthz/data
- **Azure Portal:** https://portal.azure.com

### Tenants monitored (5)
Head-To-Toe (HTT), Bishops (BCC), Frenchies (FN), Lash Lounge (TLL),
Delta Crown Extensions (DCE).

### Emergency Contacts
<!-- TODO(ct-o1w): Tyler to replace the placeholders below with REAL people +
     an on-call rotation + a severity matrix. The animal-agent names from the
     old draft were removed because they are not real escalation contacts. -->
| Role | Contact | Escalation |
|------|---------|------------|
| Operations owner | _TODO(ct-o1w): name / channel_ | Immediate |
| Platform / on-call eng | _TODO(ct-o1w): name + rotation_ | 15 min |
| Security | _TODO(ct-o1w): name_ | Immediate |
| Business owner (Tyler) | _TODO(ct-o1w): contact_ | As needed |

---

## Daily Operations

### 1. Health Check (Morning)

```bash
# Quick health verification
curl -s https://app-governance-prod.azurewebsites.net/health | jq .
# Expected: {"status": "healthy", "version": "2.5.0", "environment": "production"}

# Data freshness (THE most important daily check — stale data = bad decisions)
curl -s https://app-governance-prod.azurewebsites.net/healthz/data | jq '.any_stale'
# Expected: false. If true -> go to "Data Freshness & Sync Recovery" below.
```

### 2. Check Alerts (Morning)

**Azure Portal:** Monitor → Alerts
- Review any active alerts from last 24 hours
- Verify alert rules are enabled
- Check action group notifications

### 3. Review Dashboards (Morning)

**App Insights:** governance-appinsights → Overview
- Request volume trends
- Response time percentiles
- Exception rates

**Log Analytics:** governance-logs → Logs
- Run tenant-health-query
- Check for anomalies

---

## Weekly Operations

### 1. Review Metrics (Monday)

| Metric | Target | Action if Below |
|--------|--------|-----------------|
| Availability | 99.9% | Review logs, check alerts |
| Response Time (p95) | <500ms | Investigate slow queries |
| Error Rate | <1% | Check exception logs |
| Cost | Budget | Review resource usage |

### 2. Test Execution (Wednesday)

```bash
# Run smoke tests
make smoke-test

# Run quick load test
make load-test-smoke

# Expected: All tests pass
```

### 3. Security Review (Friday)

- Check Key Vault access logs
- Review failed authentication attempts
- Verify no security alerts

---

## Monthly Operations

### 1. Comprehensive Testing

```bash
# Full test suite
make test

# Mutation testing
make mutation-test

# Review results
```

### 2. Documentation Review

- Update runbook if procedures changed
- Review ADRs for accuracy
- Update contact information

### 3. Cost Optimization Review

```bash
# Check Azure costs
az consumption usage list \
  --billing-period-name $(date +%Y%m) \
  --query "[].{resourceName:instanceName, cost:pretaxCost}"

# Identify optimization opportunities
```

---

## Troubleshooting Guide

### Issue: Data is STALE (`/healthz/data` -> `any_stale: true`)  [MOST COMMON]

This is the failure that blocked release in June 2026 (bd `ct-cne`). The data
is usually *complete* but *old* because the in-process scheduler
(`app/core/scheduler.py`, an `AsyncIOScheduler` started in the app lifespan)
**silently stops** when the App Service worker is unloaded/recycled or idles
without "Always On", and it *skips* the runs it missed. Symptom: dashboards
show data older than 24h; `judge.py` fails P1.3.

**1. Confirm + scope it (which tenants/domains):**
```bash
curl -s https://app-governance-prod.azurewebsites.net/healthz/data | jq '{any_stale, tenants}'
python -m scripts.diagnose_sync --env production   # per-tenant complete-vs-missing

# Is the SCHEDULER itself alive, or has a job stalled? (ct-ar3 heartbeat)
curl -s https://app-governance-prod.azurewebsites.net/healthz/scheduler | jq '{running, any_overdue, jobs: [.jobs[] | {id, next_run_time, overdue, last_success}]}'
# running:false or any_overdue:true => scheduler stalled (the ct-cne mechanism).
```

**2. Recover NOW (kick a manual sync):** requires an operator bearer token in
`MANUAL_SYNC_TOKEN` (see the script header for how it's minted).
```bash
export MANUAL_SYNC_TOKEN=...        # operator token (ask Tyler / Key Vault)
python -m scripts.manual_sync --wait 90
```

**3. Verify recovery:**
```bash
curl -s https://app-governance-prod.azurewebsites.net/healthz/data | jq '.any_stale'   # -> false
python -m scripts.diagnose_sync --env production
```

**4. Don't stop at the manual kick — prove the *scheduler* recovered.** A manual
sync turns dashboards green but hides the real bug. Confirm a **scheduled**
(unattended) cycle completes within its interval. Permanent fix is tracked in
bd `ct-ar3` (App Service "Always On" + a freshness watchdog) and the alert that
makes a future stall page a human is `ct-vuv`. Detailed verification steps:
`docs/runbooks/sync-recovery-verification.md`.

**5. If a single tenant is *missing* a domain (not just stale)** — e.g. DCE
missing `resources`/`compliance` — that's an RBAC/consent gap, not a scheduler
stall. See `scripts/grant-dce-sync-permissions.sh` and bd `ct-4if`.

### Issue: Application Down (503/500 Errors)

**Immediate Actions:**
1. Check health endpoint: `curl /health`
2. Check App Service status in Azure Portal
3. Review App Insights exceptions
4. Check SQL Database connectivity

**Resolution:**
```bash
# Restart App Service (if needed)
az webapp restart \
  --name app-governance-prod \
  --resource-group rg-governance-production

# Verify after 2 minutes
curl -s https://app-governance-prod.azurewebsites.net/health
```

### Issue: High Response Times (>1s)

**Investigation:**
1. Check App Insights → Performance
2. Review slowest requests
3. Check SQL Query Store for slow queries
4. Verify no N+1 queries (should be cached)

**Resolution:**
- Scale up App Service Plan if CPU/Memory high
- Check database connection pool
- Review cache hit rates

### Issue: Alert Fatigue (Too Many Alerts)

**Investigation:**
1. Review alert thresholds
2. Check if alerts are actionable
3. Verify no false positives
4. For sync-related alert storms, use `docs/runbooks/sync-recovery-verification.md`

**Resolution:**
```bash
# Adjust alert thresholds (example)
az monitor metrics alert update \
  --name "High Response Time - Warning" \
  --resource-group rg-governance-production \
  --threshold 2000  # Change from 1000 to 2000ms
```

### Issue: Database Connection Failures

**Investigation:**
1. Check SQL Server firewall rules
2. Verify connection string in Key Vault
3. Check connection pool exhaustion

**Resolution:**
```bash
# Test database connectivity
az sql db show \
  --name governance \
  --server sql-governance-prod \
  --resource-group rg-governance-production

# Check firewall rules
az sql server firewall-rule list \
  --server sql-governance-prod \
  --resource-group rg-governance-production
```

---

## Deployment Procedures

### Blue-Green Deployment

```bash
# Deploy to staging first
make deploy-staging

# Validate staging
./scripts/verify-and-test-deployment.sh --environment staging

# Swap to production
az webapp deployment slot swap \
  --name app-governance-prod \
  --resource-group rg-governance-production \
  --slot staging \
  --target-slot production

# Verify production
./scripts/verify-and-test-deployment.sh --environment production
```

### Rollback Procedure

```bash
# If deployment fails, rollback immediately
az webapp deployment slot swap \
  --name app-governance-prod \
  --resource-group rg-governance-production \
  --slot production \
  --target-slot staging

# Or restore a previous version (registry is GHCR per ADR-0008)
az webapp config container set \
  --name app-governance-prod \
  --resource-group rg-governance-production \
  --container-image-name ghcr.io/htt-brands/control-tower:PREVIOUS_TAG
```

---

## Monitoring Checklist

### Daily (5 minutes)
- [ ] Health endpoint returns 200
- [ ] No critical alerts active
- [ ] App Insights receiving telemetry

### Weekly (15 minutes)
- [ ] Smoke tests pass
- [ ] Response time p95 < 500ms
- [ ] Error rate < 1%
- [ ] Cost within budget

### Monthly (1 hour)
- [ ] Full test suite passes
- [ ] Security review complete
- [ ] Documentation updated
- [ ] Cost optimization review

---

## Escalation Procedures

### Severity 1: Production Down
1. Page on-call engineer immediately
2. Attempt automatic recovery (restart)
3. If not resolved in 15 minutes, escalate to DevOps lead
4. Post-mortem within 24 hours

### Severity 2: Performance Degraded
1. Create incident ticket
2. Investigate root cause
3. Implement fix or workaround
4. Communication to stakeholders

### Severity 3: Warning/Monitoring
1. Log in monitoring system
2. Review during next business day
3. Tune thresholds if needed

---

## Useful Commands

### Azure CLI Commands
```bash
# Get App Service logs
az webapp log tail \
  --name app-governance-prod \
  --resource-group rg-governance-production

# Check SQL status
az sql db show \
  --name governance \
  --server sql-governance-prod \
  --query "{status:status, edition:edition}"

# View App Insights metrics
az monitor app-insights metrics show \
  --app governance-appinsights \
  --metric requests/count \
  --interval PT1H
```

### Application Commands
```bash
# Health check
curl -s https://app-governance-prod.azurewebsites.net/health | jq .

# API status
curl -s https://app-governance-prod.azurewebsites.net/api/v1/status | jq .

# Metrics
curl -s https://app-governance-prod.azurewebsites.net/metrics
```

### Testing Commands
```bash
# Quick smoke test
make smoke-test

# Load test
make load-test-smoke

# Full validation
./scripts/verify-and-test-deployment.sh --environment production
```

---

## Contact Information

<!-- TODO(ct-o1w): real team contacts — the addresses below were placeholder
     animal-agent handles and must be replaced before go-live. -->
### Team Contacts
| Team | Primary | Backup |
|------|---------|--------|
| Operations | _TODO(ct-o1w)_ | _TODO_ |
| Platform / Engineering | _TODO(ct-o1w)_ | _TODO_ |
| Security | _TODO(ct-o1w)_ | _TODO_ |

### Azure Support
- Azure Portal: https://portal.azure.com
- Azure Support Tickets: https://portal.azure.com/#blade/Microsoft_Azure_Support/HelpAndSupportBlade
- Azure Status: https://status.azure.com

---

**Document Owner:** Operations Team (contacts TBD — bd ct-o1w)  
**Review Cycle:** Monthly  
**Last refreshed:** 2026-06-04 (Richard — rebrand to HTT Control Tower, v2.5.0,
added the Data Freshness & Sync Recovery playbook, GHCR rollback, real-contact
placeholders).  
**Next Review:** 2026-07-04

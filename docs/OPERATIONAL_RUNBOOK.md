# Azure Governance Platform - Operational Runbook

**For:** DevOps, SRE, and Operations Teams  
**Version:** 1.8.1  
**Last Updated:** 2026-03-31

---

## Quick Reference

### Production URLs
- **Application:** https://app-governance-prod.azurewebsites.net
- **Health Check:** https://app-governance-prod.azurewebsites.net/health
- **Azure Portal:** https://portal.azure.com

### Emergency Contacts
| Role | Contact | Escalation |
|------|---------|------------|
| DevOps Lead | Husky | Immediate |
| Backend Lead | Code-puppy | 15 min |
| QA Lead | QA-kitten | 30 min |
| Security | Bloodhound | Immediate |

---

## Daily Operations

### 1. Health Check (Morning)

```bash
# Quick health verification
curl -s https://app-governance-prod.azurewebsites.net/health | jq .

# Expected: {"status": "healthy", "version": "1.8.1"}
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

# Or restore previous version
az webapp config container set \
  --name app-governance-prod \
  --resource-group rg-governance-production \
  --container-image-name acrgovprod.azurecr.io/azure-governance-platform:PREVIOUS_TAG
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

### Team Contacts
| Team | Primary | Backup |
|------|---------|--------|
| DevOps | husky@httbrands.com | oncall@httbrands.com |
| Engineering | codepuppy@httbrands.com | backend@httbrands.com |
| QA | qakitten@httbrands.com | testing@httbrands.com |
| Security | bloodhound@httbrands.com | security@httbrands.com |

### Azure Support
- Azure Portal: https://portal.azure.com
- Azure Support Tickets: https://portal.azure.com/#blade/Microsoft_Azure_Support/HelpAndSupportBlade
- Azure Status: https://status.azure.com

---

**Document Owner:** DevOps Team  
**Review Cycle:** Monthly  
**Next Review:** 2026-04-30

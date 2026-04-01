# Operations Runbook

## Quick Reference

| Resource | URL |
|----------|-----|
| **Production** | https://app-governance-prod.azurewebsites.net |
| **Health Check** | https://app-governance-prod.azurewebsites.net/health |
| **API Docs** | https://app-governance-prod.azurewebsites.net/docs |
| **Azure Portal** | https://portal.azure.com |

---

## Daily Operations (5 minutes)

### Morning Health Check

Run automated check:
```bash
./scripts/daily-ops-check.sh
```

Manual verification:
```bash
# Health endpoint
curl -s https://app-governance-prod.azurewebsites.net/health | jq .

# Response time (should be <1s)
for i in {1..3}; do
  curl -s -o /dev/null -w "%{time_total}\n" \
    https://app-governance-prod.azurewebsites.net/health
done
```

### Alert Review

Check Azure Portal: **Monitor → Alerts**

Verify 4 alert rules enabled:
- ✅ Server Errors - Critical
- ✅ High Response Time - Warning
- ✅ Availability Drop - Critical
- ✅ Business Logic Errors - Critical

---

## Weekly Operations (15 minutes)

### Monday Morning Routine

```bash
./scripts/weekly-ops-review.sh
```

### Metrics Review

| Metric | Target | Check Location |
|--------|--------|----------------|
| **Availability** | 99.9% | App Insights → Availability |
| **Response Time** | <500ms | App Insights → Performance |
| **Error Rate** | <1% | App Insights → Failures |
| **Cost** | <$15/mo | Portal → Cost Management |

---

## Deployment Procedures

### Blue-Green Deployment

```bash
# 1. Deploy to staging
make deploy-staging

# 2. Validate staging
./scripts/verify-and-test-deployment.sh --environment staging

# 3. Swap to production
az webapp deployment slot swap \
  --name app-governance-prod \
  --resource-group rg-governance-production \
  --slot staging \
  --target-slot production

# 4. Verify production
./scripts/verify-and-test-deployment.sh --environment production
```

### Rollback

```bash
# Swap back (if within 5 minutes)
az webapp deployment slot swap \
  --name app-governance-prod \
  --resource-group rg-governance-production \
  --slot production \
  --target-slot staging
```

---

## Troubleshooting

### Application Down (503/500)

1. Check App Service status in Portal
2. Review App Insights exceptions
3. If unresolved in 5 min, execute rollback

```bash
# Emergency restart
az webapp restart \
  --name app-governance-prod \
  --resource-group rg-governance-production
```

### High Response Time (>1s)

1. Check App Insights → Performance
2. Review SQL Query Store
3. Check App Service Plan CPU/Memory

### Database Connection Failures

```bash
# Check SQL status
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

## Monitoring & Alerting

### Alert Response Matrix

| Alert | Severity | Response | Action |
|-------|----------|----------|--------|
| **Server Errors** | Critical | Immediate | Investigate |
| **Availability Drop** | Critical | Immediate | Rollback |
| **High Response Time** | Warning | 30 min | Tune thresholds |
| **Business Logic Errors** | Critical | Immediate | Check deploy |

### Escalation

**Severity 1: Production Down**
1. Page on-call engineer
2. Attempt automatic recovery
3. Escalate if not resolved in 15 min
4. Post-mortem within 24 hours

---

## SLAs

| Metric | Target | Current |
|--------|--------|---------|
| **Availability** | 99.9% | 99.9%+ ✅ |
| **Response Time (p95)** | <500ms | ~130ms ✅ |
| **Error Rate** | <1% | <0.1% ✅ |
| **Recovery Time** | <15 min | N/A ✅ |

---

<p align="center">
  <small>Operations Runbook v1.8.1 | Last Updated: March 31, 2026</small>
</p>

---
layout: default
title: Operations Playbook
permalink: /operations/playbook/
---

# Azure Governance Platform - Operations Playbook

> **Document Version:** 1.0  
> **Last Updated:** May 2025  
> **Audience:** DevOps Engineers, SREs, Platform Operators, On-Call Staff  
> **System:** Azure Governance Platform v1.6+

---

## Table of Contents

1. [Overview](#1-overview)
2. [Daily Operations](#2-daily-operations)
3. [System Health Checks](#3-system-health-checks)
4. [Common Troubleshooting](#4-common-troubleshooting)
5. [Alert Response](#5-alert-response)
6. [Incident Response](#6-incident-response)
7. [Escalation Procedures](#7-escalation-procedures)
8. [Contact Information](#8-contact-information)
9. [Runbook Templates](#9-runbook-templates)

---

## 1. Overview

### 1.1 Purpose

This playbook provides day-to-day operational guidance for the Azure Governance Platform. It covers:
- Routine health checks and monitoring
- Common troubleshooting scenarios
- Alert response procedures
- Escalation paths
- Emergency contacts

### 1.2 System Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Azure App Service                         │
│              (Azure Governance Platform)                     │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │   API    │  │  Static  │  │  Auth    │  │  Sync    │   │
│  │  Layer   │  │   Files  │  │  Service │  │ Scheduler│   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
└───────┼─────────────┼─────────────┼─────────────┼─────────┘
        │             │             │             │
   ┌────┴─────┐ ┌────┴─────┐ ┌────┴─────┐ ┌──────┴──────┐
   │  Azure   │ │   Key    │ │  Azure   │ │ Azure AD /  │
   │   SQL    │ │  Vault   │ │  Monitor │ │   Entra ID  │
   │ Database │ │          │ │          │ │             │
   └──────────┘ └──────────┘ └──────────┘ └─────────────┘
```

### 1.3 Critical Dependencies

| Component | Impact if Down | Recovery Time |
|-----------|----------------|---------------|
| Azure App Service | Complete outage | 5-15 minutes |
| Azure SQL Database | Data unavailable | 5-30 minutes |
| Azure AD | Auth failures | 0-60 minutes (Microsoft managed) |
| Key Vault | Secret retrieval fails | 5-10 minutes |
| Application Insights | Monitoring blind | 5 minutes (non-critical) |

### 1.4 Operational Hours

- **Standard Support:** Monday-Friday, 8:00 AM - 6:00 PM ET
- **On-Call Support:** 24/7 for P1 incidents
- **Maintenance Windows:** Sundays 2:00 AM - 6:00 AM ET

---

## 2. Daily Operations

### 2.1 Morning Health Check (Start of Shift)

**Time Required:** 5 minutes

```bash
#!/bin/bash
# Save as: ~/scripts/daily-health-check.sh

BASE_URL="https://app-governance-prod.azurewebsites.net"
WEBHOOK_URL="${TEAMS_WEBHOOK_URL:-}"

echo "=== Daily Health Check - $(date) ==="

# Check 1: Basic health
HEALTH=$(curl -s "$BASE_URL/health" 2>/dev/null)
if [[ "$HEALTH" != *"healthy"* ]]; then
    echo "❌ CRITICAL: Health check failed"
    # Send alert if configured
    [[ -n "$WEBHOOK_URL" ]] && curl -s -X POST "$WEBHOOK_URL" \
        -H "Content-Type: application/json" \
        -d '{"text":"🚨 Azure Governance Platform - Health check failed"}'
    exit 1
fi
echo "✅ Health check passed"

# Check 2: Database connectivity
DB_STATUS=$(curl -s "$BASE_URL/health/detailed" | jq -r '.components.database')
if [[ "$DB_STATUS" != "healthy" && "$DB_STATUS" != *"sqlite"* ]]; then
    echo "❌ WARNING: Database status: $DB_STATUS"
else
    echo "✅ Database: $DB_STATUS"
fi

# Check 3: Scheduler status
SCHEDULER=$(curl -s "$BASE_URL/health/detailed" | jq -r '.components.scheduler')
echo "📊 Scheduler: $SCHEDULER"

# Check 4: Active alerts
ALERTS=$(curl -s "$BASE_URL/api/v1/sync/alerts" 2>/dev/null | jq '.alerts | length')
echo "🔔 Active alerts: $ALERTS"

# Check 5: Recent sync jobs
JOBS=$(curl -s "$BASE_URL/api/v1/sync/status" 2>/dev/null | jq '.jobs | length')
echo "🔄 Active sync jobs: $JOBS"

echo "=== Check Complete ==="
```

### 2.2 Dashboard Review Checklist

Access: `https://app-governance-prod.azurewebsites.net/dashboard`

| Check | Expected | Action if Failed |
|-------|----------|------------------|
| Dashboard loads | < 3 seconds | Check app health |
| Cost data age | < 25 hours | Trigger manual sync |
| Compliance age | < 5 hours | Trigger compliance sync |
| Resources age | < 2 hours | Trigger resource sync |
| Alert count | 0 critical | Investigate immediately |
| All tenants green | 5/5 healthy | Check tenant connectivity |
| Cache hit rate | > 70% | Review cache metrics |

### 2.3 Key Metrics to Monitor

```bash
# Get quick metrics summary
curl -s "$BASE_URL/api/v1/status" | jq '{
    status: .status,
    database: .components.database,
    scheduler: .components.scheduler,
    alerts: .alerts.active_count,
    cache_hit_rate: .cache.hit_rate_percent
}'
```

### 2.4 Weekly Tasks

| Day | Task | Duration | Command/Location |
|-----|------|----------|------------------|
| Monday | Review weekend alerts | 15 min | Dashboard → Alerts |
| Tuesday | Check sync job performance | 10 min | `/api/v1/sync/metrics` |
| Wednesday | Review cost anomalies | 15 min | Dashboard → Costs |
| Thursday | Verify backup status | 5 min | Azure Portal → Backups |
| Friday | Weekly summary report | 20 min | Generate from dashboard |

---

## 3. System Health Checks

### 3.1 Quick Health Check Commands

```bash
# Basic health
 curl -s https://app-governance-prod.azurewebsites.net/health | jq .

# Detailed health with all components
curl -s https://app-governance-prod.azurewebsites.net/health/detailed | jq .

# System status with metrics
curl -s https://app-governance-prod.azurewebsites.net/api/v1/status | jq .

# Prometheus metrics
curl -s https://app-governance-prod.azurewebsites.net/metrics | head -50
```

### 3.2 Component-Specific Checks

#### Database Health

```bash
# Check database connectivity
curl -s https://app-governance-prod.azurewebsites.net/health/detailed | \
    jq '.components.database'

# Expected response: "healthy"

# Check connection pool stats (Azure SQL only)
curl -s https://app-governance-prod.azurewebsites.net/health/detailed | \
    jq '.database_pool'
```

#### Cache Health

```bash
# Check cache status
curl -s https://app-governance-prod.azurewebsites.net/health/detailed | \
    jq '.components.cache'

# View cache metrics
curl -s https://app-governance-prod.azurewebsites.net/health/detailed | \
    jq '.cache_metrics'

# Expected: backend = "memory" or "redis", hit_rate_percent > 50
```

#### Scheduler Health

```bash
# Check scheduler status
curl -s https://app-governance-prod.azurewebsites.net/health/detailed | \
    jq '.components.scheduler'

# Expected response: "running"
```

#### Azure Configuration

```bash
# Check Azure connectivity
curl -s https://app-governance-prod.azurewebsites.net/health/detailed | \
    jq '.components.azure_configured'

# Expected response: true
```

### 3.3 Sync Job Health

```bash
# Check sync status
curl -s https://app-governance-prod.azurewebsites.net/api/v1/sync/status | jq .

# Check sync history
curl -s "https://app-governance-prod.azurewebsites.net/api/v1/sync/history?limit=10" | jq .

# Check for failed jobs
curl -s "https://app-governance-prod.azurewebsites.net/api/v1/sync/history?limit=20" | \
    jq '.logs[] | select(.status == "failed")'
```

### 3.4 Tenant Health Verification

```bash
# List all tenants
curl -s https://app-governance-prod.azurewebsites.net/api/v1/tenants | jq .

# Check tenant-specific sync status
for tenant in HTT BCC FN TLL DCE; do
    echo "Checking $tenant..."
    # Add tenant-specific checks here
done
```

---

## 4. Common Troubleshooting

### 4.1 Authentication Issues

#### Symptom: Users Cannot Log In

**Diagnostic Steps:**

```bash
# 1. Check auth health
curl -s https://app-governance-prod.azurewebsites.net/api/v1/auth/health | jq .

# 2. Verify Azure AD configuration
curl -s https://app-governance-prod.azurewebsites.net/health/detailed | \
    jq '.components.azure_configured'

# 3. Check JWT configuration
curl -s https://app-governance-prod.azurewebsites.net/api/v1/auth/health | \
    jq '.jwt_configured'
```

**Common Causes & Solutions:**

| Cause | Solution |
|-------|----------|
| Client secret expired | Rotate credentials (Section 4.6) |
| Redirect URI mismatch | Update ALLOWED_REDIRECT_URIS in App Settings |
| Azure AD app disabled | Enable app in Azure Portal → App Registrations |
| Clock skew | Verify server time sync with Azure AD |

#### Symptom: Token Validation Failures

```bash
# Check token blacklist status
curl -s https://app-governance-prod.azurewebsites.net/health/detailed | \
    jq '.token_blacklist'

# If needed, clear token blacklist (requires admin)
# Contact engineering team for token blacklist reset
```

### 4.2 Database Connectivity Issues

#### Symptom: Database Shows "unhealthy"

**Diagnostic Steps:**

```bash
# Check detailed error message
curl -s https://app-governance-prod.azurewebsites.net/health/detailed | \
    jq '.components.database'

# Check connection pool status
curl -s https://app-governance-prod.azurewebsites.net/health/detailed | \
    jq '.database_pool'
```

**Resolution Steps:**

1. **Azure SQL Connection Issues:**
   ```bash
   # Verify Azure SQL firewall rules
   az sql server firewall-rule list \
       --server my-server \
       --resource-group my-rg
   
   # Add App Service outbound IP if missing
   az sql server firewall-rule create \
       --server my-server \
       --resource-group my-rg \
       --name AllowAppService \
       --start-ip-address <app-outbound-ip> \
       --end-ip-address <app-outbound-ip>
   ```

2. **Connection Pool Exhaustion:**
   - Restart App Service to clear connections
   - Check for connection leaks in application logs

### 4.3 Sync Job Failures

#### Symptom: Sync Jobs Not Running

**Diagnostic Steps:**

```bash
# Check scheduler status
curl -s https://app-governance-prod.azurewebsites.net/health/detailed | \
    jq '.components.scheduler'

# Check recent sync history
curl -s "https://app-governance-prod.azurewebsites.net/api/v1/sync/history?limit=20" | \
    jq '.logs[] | {job_type, status, started_at, error_message}'

# Check for active alerts
curl -s https://app-governance-prod.azurewebsites.net/api/v1/sync/alerts | jq .
```

**Resolution by Error Type:**

| Error Pattern | Solution |
|-------------|----------|
| `AADSTS7000215: Invalid client secret` | Rotate tenant credentials |
| `429 Too Many Requests` | Reduce sync frequency, implement backoff |
| Connection timeout | Check Azure service health, retry with backoff |
| Data schema error | Update sync module, contact engineering |

**Trigger Manual Sync:**

```bash
# Trigger specific sync types
curl -X POST https://app-governance-prod.azurewebsites.net/api/v1/sync/costs
curl -X POST https://app-governance-prod.azurewebsites.net/api/v1/sync/compliance
curl -X POST https://app-governance-prod.azurewebsites.net/api/v1/sync/resources
curl -X POST https://app-governance-prod.azurewebsites.net/api/v1/sync/identity

# Trigger Riverside sync
curl -X POST https://app-governance-prod.azurewebsites.net/api/v1/riverside/sync
```

### 4.4 Performance Issues

#### Symptom: Slow API Response Times

**Diagnostic Steps:**

```bash
# Check cache hit rate
curl -s https://app-governance-prod.azurewebsites.net/health/detailed | \
    jq '.cache_metrics.hit_rate_percent'

# Check system status for performance metrics
curl -s https://app-governance-prod.azurewebsites.net/api/v1/status | \
    jq '.performance'
```

**Resolution Steps:**

1. **Low Cache Hit Rate (< 50%):**
   - Review cache TTL settings
   - Enable Redis cache for production
   - Check for cache invalidation patterns

2. **Database Performance:**
   ```bash
   # Check for slow queries (if enabled)
   # Review Application Insights → Performance
   ```

3. **Scale Up Resources:**
   ```bash
   # Scale up App Service plan
   az appservice plan update \
       --name app-governance-prod-plan \
       --resource-group rg-governance-prod \
       --sku P1V2
   ```

### 4.5 Cache Issues

#### Symptom: Stale Data or Cache Errors

```bash
# Check cache metrics
curl -s https://app-governance-prod.azurewebsites.net/health/detailed | \
    jq '.cache_metrics'

# Clear preflight cache (if needed)
curl -X POST https://app-governance-prod.azurewebsites.net/api/v1/preflight/clear-cache

# Restart app to clear all caches
az webapp restart --name app-governance-prod --resource-group rg-governance-prod
```

### 4.6 Certificate/Secret Rotation

#### Rotate Client Secret

```bash
# 1. Create new secret in Azure AD
# Azure Portal → App Registrations → [App] → Certificates & Secrets → New client secret

# 2. Update App Service settings
az webapp config appsettings set \
    --name app-governance-prod \
    --resource-group rg-governance-prod \
    --settings "AZURE_CLIENT_SECRET=@Microsoft.KeyVault(SecretUri=...)"

# 3. Verify rotation
curl -s https://app-governance-prod.azurewebsites.net/health/detailed | \
    jq '.components.azure_configured'

# 4. Delete old secret (after 24 hours)
```

---

## 5. Alert Response

### 5.1 Alert Severity Levels

| Level | Description | Response Time | Example |
|-------|-------------|---------------|---------|
| **P1 - Critical** | Complete outage or data loss | 15 minutes | Platform down, all auth failing |
| **P2 - High** | Major feature impaired | 1 hour | Sync failing for > 1 tenant |
| **P3 - Medium** | Minor feature issue | 4 hours | Single tenant sync delayed |
| **P4 - Low** | Cosmetic or informational | 24 hours | UI glitch, non-urgent |

### 5.2 Alert Response Procedures

#### P1 - Critical Alert Response

```bash
# Immediate checks (within 5 minutes)

# 1. Verify platform accessibility
curl -s https://app-governance-prod.azurewebsites.net/health | jq .

# 2. Check Azure resource status
az webapp show --name app-governance-prod --resource-group rg-governance-prod --query "state"

# 3. View recent logs
az webapp log tail --name app-governance-prod --resource-group rg-governance-prod

# 4. If needed, restart App Service
az webapp restart --name app-governance-prod --resource-group rg-governance-prod

# 5. Verify recovery
curl -s https://app-governance-prod.azurewebsites.net/health | jq .
```

**Escalation:** Page on-call engineer immediately if:
- Restart doesn't resolve issue
- Database connectivity failing
- Multiple Azure services affected

#### P2 - High Alert Response

```bash
# Investigation steps (within 15 minutes)

# 1. Identify affected component
curl -s https://app-governance-prod.azurewebsites.net/health/detailed | jq .

# 2. Check sync job status
curl -s https://app-governance-prod.azurewebsites.net/api/v1/sync/status | jq .

# 3. Review recent errors
curl -s "https://app-governance-prod.azurewebsites.net/api/v1/sync/history?limit=10" | \
    jq '.logs[] | select(.status == "failed")'
```

### 5.3 Viewing and Managing Alerts

```bash
# List active alerts
curl -s https://app-governance-prod.azurewebsites.net/api/v1/sync/alerts | jq .

# Resolve specific alert
curl -X POST "https://app-governance-prod.azurewebsites.net/api/v1/sync/alerts/{alert_id}/resolve" \
    -H "Content-Type: application/json" \
    -d '{"resolved_by": "operator@company.com", "resolution_notes": "Issue resolved after credential rotation"}'
```

---

## 6. Incident Response

### 6.1 Incident Classification

| Type | Criteria | Response Team |
|------|----------|---------------|
| Security | Unauthorized access, data exposure | Security + Engineering |
| Outage | Complete or partial platform unavailability | Engineering + DevOps |
| Data | Data loss, corruption, sync failures | Engineering + DBA |
| Performance | Degraded response times | DevOps + Engineering |

### 6.2 Incident Response Workflow

```
Incident Detected
        |
        v
Assess Severity (P1-P4)
        |
        +-- P1 --> Page On-Call (15 min SLA)
        |
        +-- P2 --> Create Ticket, Notify Team (1 hour SLA)
        |
        +-- P3 --> Create Ticket (4 hour SLA)
        |
        +-- P4 --> Backlog for Next Sprint
        |
        v
Execute Runbook
        |
        v
Document Actions in Incident Channel
        |
        v
Post-Incident Review (within 48 hours for P1/P2)
```

### 6.3 Communication Templates

#### Incident Announcement (Slack/Teams)

```markdown
🚨 **INCIDENT ALERT** 🚨

**Severity:** P1 - Critical
**Time:** 2025-05-15 14:30 UTC
**Status:** Investigating

**Impact:** Azure Governance Platform is inaccessible
**Symptoms:** 503 errors on all endpoints

**Actions Taken:**
- On-call engineer paged
- Restart initiated

**Next Update:** 15 minutes

**Incident Channel:** #incident-2025-05-15-platform-down
```

#### Status Update Template

```markdown
📊 **Status Update** - 14:45 UTC

**Incident:** Platform downtime (P1)
**Status:** Identified

**Root Cause:** Azure SQL connection pool exhausted
**Resolution:** Database connections cleared, service recovering

**ETA to Resolution:** 30 minutes
```

#### Resolution Summary Template

```markdown
✅ **RESOLVED** - 15:15 UTC

**Incident:** Platform downtime (P1)
**Duration:** 45 minutes

**Root Cause:** Connection pool leak in sync job scheduler
**Resolution:** Restarted App Service, implemented connection cleanup

**Preventive Actions:**
- Added connection pool monitoring alert
- Scheduled code review for sync module
- Increased pool size from 3 to 5

**Post-Mortem:** Scheduled for 2025-05-17
```

---

## 7. Escalation Procedures

### 7.1 Escalation Matrix

| Level | Role | Contact | When to Escalate |
|-------|------|---------|------------------|
| L1 | Platform Support | platform-support@company.com | Initial triage, routine issues |
| L2 | DevOps Engineer | devops-oncall@company.com | Technical issues, deployments |
| L3 | Engineering Manager | eng-manager@company.com | Major incidents, architecture decisions |
| L4 | Director of Engineering | director-eng@company.com | Business-impacting outages |

### 7.2 Escalation Paths by Scenario

#### Scenario 1: Platform Down (P1)

```
0-5 min:   L1 attempts restart
5-15 min:  Escalate to L2 if unresolved
15-30 min: Escalate to L3, notify stakeholders
30+ min:   Escalate to L4, executive notification
```

#### Scenario 2: Security Incident

```
Immediate: Page L2 + Security team
5 min:     Isolate affected systems
15 min:    Escalate to L3 + Legal if data exposure
30 min:    External notification if required (breach laws)
```

#### Scenario 3: Data Loss

```
Immediate: Stop all write operations
5 min:     Page L2 + DBA
15 min:    Assess scope, begin recovery from backup
30 min:    Escalate to L3, customer notification decision
```

### 7.3 External Escalation

| Vendor | Support Channel | Escalation Path |
|--------|-----------------|-----------------|
| Microsoft Azure | https://portal.azure.com/#blade/Microsoft_Azure_Support/HelpAndSupportBlade | Open severity A ticket |
| Azure AD Issues | Microsoft 365 Admin Center | Escalate through tenant admin |
| Third-Party Integrations | Vendor-specific | Contact per SLA |

---

## 8. Contact Information

### 8.1 Internal Contacts

| Role | Name | Email | Phone | Slack |
|------|------|-------|-------|-------|
| Platform Support | [TBD] | platform-support@company.com | [TBD] | #platform-support |
| DevOps On-Call | [TBD] | devops-oncall@company.com | [TBD] | #devops-oncall |
| Engineering Manager | [TBD] | eng-manager@company.com | [TBD] | @eng-manager |
| Security Team | [TBD] | security@company.com | [TBD] | #security |
| Product Owner | [TBD] | product@company.com | [TBD] | @product-owner |

### 8.2 Vendor Contacts

| Vendor | Support URL | Account ID | Notes |
|--------|-------------|------------|-------|
| Microsoft Azure | https://azure.microsoft.com/support | [TBD] | EA Agreement #[TBD] |
| Azure AD Premium | Via Azure Portal | [TBD] | P2 Licenses |
| GitHub Enterprise | https://support.github.com | [TBD] | Enterprise account |
| Datadog/New Relic | [TBD] | [TBD] | APM and monitoring |

### 8.3 Emergency Contacts

| Emergency Type | Contact | When to Use |
|----------------|---------|-------------|
| Azure Service Outage | Microsoft Support | Azure-wide issues |
| Security Breach | security@company.com + Legal | Confirmed or suspected breach |
| Data Center Issues | Azure Status Page | Physical infrastructure |

---

## 9. Runbook Templates

### 9.1 Incident Response Checklist

```markdown
## Incident Response Checklist

### Initial Response (0-5 minutes)
- [ ] Acknowledge incident
- [ ] Create incident channel
- [ ] Page on-call if P1/P2
- [ ] Post initial announcement
- [ ] Begin triage

### Assessment (5-15 minutes)
- [ ] Classify severity (P1-P4)
- [ ] Identify affected components
- [ ] Check health endpoints
- [ ] Review recent deployments
- [ ] Check Azure status page

### Resolution (15-60 minutes)
- [ ] Execute runbook for issue type
- [ ] Document all actions taken
- [ ] Post regular updates (every 15 min for P1)
- [ ] Escalate if needed

### Post-Resolution
- [ ] Verify all systems healthy
- [ ] Send resolution notification
- [ ] Schedule post-mortem (P1/P2)
- [ ] Update documentation if needed
```

### 9.2 Deployment Verification Checklist

```bash
#!/bin/bash
# Post-Deployment Verification Checklist

URL="https://app-governance-prod.azurewebsites.net"

echo "=== Post-Deployment Verification ==="

# Health checks
curl -s "$URL/health" | jq -e '.status == "healthy"' || { echo "❌ Health check failed"; exit 1; }
curl -s "$URL/health/detailed" | jq -e '.components.database == "healthy"' || echo "⚠️ Database check failed"
curl -s "$URL/health/detailed" | jq -e '.components.scheduler == "running"' || echo "⚠️ Scheduler not running"

# API checks
curl -s "$URL/api/v1/status" | jq -e '.status == "healthy"' || { echo "❌ Status API failed"; exit 1; }

# Auth checks
curl -s "$URL/api/v1/auth/health" | jq -e '.jwt_configured == true' || echo "⚠️ JWT not configured"

# Metrics
curl -s "$URL/metrics" | head -1 | grep -q "# HELP" && echo "✅ Metrics available"

echo "=== Verification Complete ==="
```

### 9.3 Maintenance Window Procedure

```markdown
## Maintenance Window Procedure

### Pre-Maintenance (24 hours before)
- [ ] Announce maintenance window to stakeholders
- [ ] Verify backup is current
- [ ] Prepare rollback plan
- [ ] Confirm maintenance team availability

### During Maintenance
- [ ] Put system in maintenance mode (if available)
- [ ] Execute planned changes
- [ ] Run verification tests after each change
- [ ] Monitor logs for errors

### Post-Maintenance
- [ ] Remove maintenance mode
- [ ] Run full verification script
- [ ] Monitor for 30 minutes
- [ ] Notify stakeholders of completion
- [ ] Document any issues encountered
```

---

## Appendix A: Quick Reference Commands

```bash
# Health & Status
curl -s https://app-governance-prod.azurewebsites.net/health | jq .
curl -s https://app-governance-prod.azurewebsites.net/health/detailed | jq .
curl -s https://app-governance-prod.azurewebsites.net/api/v1/status | jq .

# Sync Operations
curl -X POST https://app-governance-prod.azurewebsites.net/api/v1/sync/costs
curl -X POST https://app-governance-prod.azurewebsites.net/api/v1/sync/compliance
curl -X POST https://app-governance-prod.azurewebsites.net/api/v1/riverside/sync

# Azure Operations
az webapp restart --name app-governance-prod --resource-group rg-governance-prod
az webapp log tail --name app-governance-prod --resource-group rg-governance-prod
az appservice plan update --name app-governance-prod-plan --resource-group rg-governance-prod --sku P1V2

# Logs and Monitoring
az webapp log tail --name app-governance-prod --resource-group rg-governance-prod
az monitor app-insights query --apps app-governance-prod --analytics-query "traces | where severityLevel >= 3"
```

---

## Appendix B: Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-05-15 | DevOps Team | Initial operations playbook |

---

**Related Documents:**
- [Deployment Guide](../DEPLOYMENT.md)
- [API Documentation](../API.md)
- [Architecture Overview](../ARCHITECTURE.md)
- [Security Procedures](../security/production-audit.md)

# Azure Governance Platform - Operations Runbook

> **Version:** 1.0  
> **Last Updated:** February 2025  
> **Audience:** DevOps Engineers, SREs, Platform Operators

---

## Table of Contents

1. [Daily Operations Checklist](#1-daily-operations-checklist)
2. [Monitoring Sync Job Health](#2-monitoring-sync-job-health)
3. [Handling Sync Failures](#3-handling-sync-failures)
4. [Manual Sync Procedures](#4-manual-sync-procedures)
5. [Adding New Tenants](#5-adding-new-tenants)
6. [Rotating Credentials](#6-rotating-credentials)
7. [Backup and Restore Procedures](#7-backup-and-restore-procedures)
8. [Escalation Procedures](#8-escalation-procedures)
9. [Emergency Procedures](#9-emergency-procedures)
10. [Common Operational Tasks](#10-common-operational-tasks)
11. [Performance Tuning](#11-performance-tuning)
12. [Maintenance Windows](#12-maintenance-windows)

---

## 1. Daily Operations Checklist

### 1.1 Automated Health Check Script

Create and schedule this daily health check:

```bash
#!/bin/bash
# Save as daily-health-check.sh

BASE_URL="https://your-app.azurewebsites.net"

echo "=== Daily Health Check ==="
echo "$(date)"
echo ""

# 1. Basic health
echo "1. Checking basic health..."
HEALTH=$(curl -s "$BASE_URL/health")
echo "   Response: $HEALTH"

# 2. Detailed health
echo ""
echo "2. Checking detailed health..."
curl -s "$BASE_URL/health/detailed" | jq '.components'

# 3. Sync status
echo ""
echo "3. Checking sync status..."
curl -s "$BASE_URL/api/v1/sync/status" | jq '.jobs | length' | xargs echo "   Active jobs:"

# 4. Active alerts
echo ""
echo "4. Checking for active alerts..."
ALERT_COUNT=$(curl -s "$BASE_URL/api/v1/sync/alerts" | jq '.alerts | length')
echo "   Active alerts: $ALERT_COUNT"

echo ""
echo "=== Health Check Complete ==="
```

### 1.2 Daily Dashboard Review (10 minutes)

Access the dashboard and verify:

| Check | Expected Result | Action if Failed |
|-------|-----------------|------------------|
| Dashboard loads | Page displays within 5 seconds | Check app health |
| Cost data current | Last updated < 25 hours ago | Trigger cost sync |
| Compliance data current | Last updated < 5 hours ago | Trigger compliance sync |
| Resource inventory current | Last updated < 2 hours ago | Trigger resource sync |
| No critical alerts | Alert count = 0 | Investigate alerts |
| All tenants responding | All tenants show "healthy" | Check tenant connectivity |

### 1.3 Key Metrics to Monitor

```bash
# Get key metrics summary
curl -s "$BASE_URL/api/v1/status" | jq '{
  status: .status,
  db_status: .components.database,
  scheduler_status: .components.scheduler,
  active_alerts: .alerts.active_count,
  cache_hit_rate: .performance.cache_stats.hit_rate_percent
}'
```

---

## 2. Monitoring Sync Job Health

### 2.1 Sync Job Schedule

| Job Type | Frequency | Expected Duration | Max Acceptable Duration |
|----------|-----------|-------------------|------------------------|
| Costs | Every 24 hours | 5-15 minutes | 60 minutes |
| Compliance | Every 4 hours | 10-20 minutes | 45 minutes |
| Resources | Every 1 hour | 5-10 minutes | 30 minutes |
| Identity | Every 24 hours | 10-15 minutes | 60 minutes |

### 2.2 Health Check Commands

```bash
# Check overall sync health
curl -s "$BASE_URL/api/v1/sync/health"

# Expected response:
# {
#   "status": "healthy",
#   "last_sync": "2025-02-25T08:00:00Z",
#   "next_sync": "2025-02-26T00:00:00Z",
#   "recent_failures": 0,
#   "consecutive_failures": 0
# }
```

### 2.3 Sync Metrics Dashboard

```bash
# Get detailed metrics
curl -s "$BASE_URL/api/v1/sync/metrics" | jq '.metrics[] | {
  job_type,
  success_rate,
  avg_duration_minutes: (.avg_duration_ms / 60000),
  last_run: .last_run_at,
  last_success: .last_success_at,
  last_failure: .last_failure_at
}'
```

### 2.4 Setting Up Alerts

Configure these alert thresholds:

```yaml
alerts:
  - name: sync_failure
    condition: job.status == "failed"
    severity: critical
    notification: immediate

  - name: sync_stalled
    condition: last_success > expected_interval * 2
    severity: warning
    notification: within_1_hour

  - name: high_error_rate
    condition: error_rate > 10% over 1 hour
    severity: warning
    notification: within_1_hour
```

---

## 3. Handling Sync Failures

### 3.1 Failure Response Flowchart

```
Sync Job Fails
     |
     v
Check Error Type
     |
     +-- Authentication Error --> Rotate Credentials (Section 6)
     |
     +-- Rate Limit Error -----> Wait 15 min, Retry
     |
     +-- Timeout Error --------> Check Azure Service Health
     |                            |
     |                            +-- Azure degraded --> Wait for restoration
     |                            |
     |                            +-- Azure healthy --> Retry with backoff
     |
     +-- Data Error -----------> Check data source
     |                            |
     |                            +-- Schema changed --> Update sync module
     |                            |
     |                            +-- Temporary issue --> Retry
     |
     +-- Unknown Error --------> Enable debug logging
                                  |
                                  +-- Reproducible --> File bug report
                                  |
                                  +-- One-time --> Monitor for recurrence
```

### 3.2 Common Failure Patterns

#### Pattern 1: Authentication Failures

**Symptoms:**
- Error: `AADSTS7000215: Invalid client secret`
- All sync jobs fail simultaneously

**Resolution:**
```bash
# 1. Verify credentials
curl -s "$BASE_URL/health/detailed" | jq '.components.azure_configured'

# 2. If false, rotate credentials (see Section 6)

# 3. Verify after rotation
curl -X POST "$BASE_URL/api/v1/sync/resources"
```

#### Pattern 2: Rate Limiting

**Symptoms:**
- Error: `429 Too Many Requests`
- Intermittent failures
- Gradual increase in failures

**Resolution:**
```bash
# 1. Check current sync frequency
# Reduce if too aggressive

# 2. Implement exponential backoff
# Already built-in, but verify settings

# 3. Check for multiple instances
# Ensure only one scheduler is running
```

#### Pattern 3: Timeout Errors

**Symptoms:**
- Error: `Connection timeout`
- Sync jobs take longer than normal
- Partial data updates

**Resolution:**
```bash
# 1. Check Azure service health
# Visit: https://status.azure.com

# 2. If Azure healthy, check network
ping login.microsoftonline.com

# 3. Restart application if needed
az webapp restart --name $APP_NAME --resource-group $RESOURCE_GROUP
```

### 3.3 Recovery Procedures

#### Immediate Recovery

```bash
# 1. Check current status
curl -s "$BASE_URL/api/v1/sync/status"

# 2. Identify failed jobs
curl -s "$BASE_URL/api/v1/sync/history?limit=10" | jq '.logs[] | select(.status == "failed")'

# 3. Resolve underlying issue (see patterns above)

# 4. Trigger manual sync
curl -X POST "$BASE_URL/api/v1/sync/costs"
curl -X POST "$BASE_URL/api/v1/sync/compliance"

# 5. Verify recovery
curl -s "$BASE_URL/api/v1/sync/health"
```

#### Post-Recovery Verification

```bash
# Verify data integrity
curl -s "$BASE_URL/api/v1/costs/summary"
curl -s "$BASE_URL/api/v1/compliance/summary"
curl -s "$BASE_URL/api/v1/resources" | jq '.total_resources'

# Check for gaps in sync history
curl -s "$BASE_URL/api/v1/sync/history?limit=50" | jq '.logs[] | {job_type, started_at, status}'
```

---

## 4. Manual Sync Procedures

### 4.1 Triggering Manual Sync

```bash
# Trigger specific sync type
curl -X POST "$BASE_URL/api/v1/sync/costs"
curl -X POST "$BASE_URL/api/v1/sync/compliance"
curl -X POST "$BASE_URL/api/v1/sync/resources"
curl -X POST "$BASE_URL/api/v1/sync/identity"

# Trigger Riverside sync (if enabled)
curl -X POST "$BASE_URL/api/v1/riverside/sync"

# Expected response:
# {"status": "triggered", "sync_type": "costs"}
```

### 4.2 Monitoring Manual Sync

```bash
# Check sync is running
curl -s "$BASE_URL/api/v1/sync/status"

# Watch logs (run in separate terminal)
az webapp log tail --name $APP_NAME --resource-group $RESOURCE_GROUP

# Check completion
curl -s "$BASE_URL/api/v1/sync/history?limit=5" | jq '.logs[0] | {job_type, status, started_at, ended_at}'
```

### 4.3 Historical Data Backfill

If you need to sync historical data:

```bash
# Note: This requires implementation of backfill endpoint
# Contact development team if needed

curl -X POST "$BASE_URL/api/v1/sync/costs/backfill" \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2024-01-01",
    "end_date": "2024-12-31"
  }'
```

---

## 5. Adding New Tenants

### 5.1 Pre-Add Checklist

Before adding a new tenant:

- [ ] Obtain tenant administrator approval
- [ ] Verify Azure AD permissions (Global Admin or App Admin)
- [ ] Create App Registration in target tenant
- [ ] Grant API permissions and admin consent
- [ ] Assign RBAC roles (Reader, Cost Management Reader, Security Reader)
- [ ] Collect credentials (tenant ID, client ID, client secret)
- [ ] Document tenant purpose and owner

### 5.2 Adding Tenant via API

```bash
# Add new tenant
curl -X POST "$BASE_URL/api/v1/tenants" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "New Production Tenant",
    "tenant_id": "new-tenant-guid-here",
    "description": "Production environment for new division",
    "client_id": "app-registration-client-id",
    "client_secret_ref": "key-vault-secret-reference"
  }'
# ct-9x9: the `use_lighthouse` field was dropped from the tenants table
# in migration 011 (May 2026) — including it is harmless (it'll be
# ignored) but no longer required.

# Verify tenant was added
curl -s "$BASE_URL/api/v1/tenants"

# Trigger initial sync for new tenant
curl -X POST "$BASE_URL/api/v1/sync/resources"
```

### 5.3 Post-Add Verification

```bash
# Check tenant appears in list
curl -s "$BASE_URL/api/v1/tenants" | jq '.[] | select(.tenant_id == "new-tenant-guid-here")'

# Verify sync completed for new tenant
curl -s "$BASE_URL/api/v1/sync/history?limit=20" | jq '.logs[] | select(.tenant_id == "new-tenant-guid-here")'

# Check data is flowing
curl -s "$BASE_URL/api/v1/resources?tenant_ids=new-tenant-guid-here" | jq '.total_resources'
```

---

## 6. Rotating Credentials

### 6.1 Rotation Schedule

| Credential Type | Rotation Frequency | Notification Lead Time |
|-----------------|-------------------|----------------------|
| Client Secrets | 12 months | 30 days |
| API Keys | 6 months | 14 days |
| Database | On-demand | N/A |

### 6.2 Client Secret Rotation Procedure

#### Step 1: Create New Secret

```bash
# In Azure Portal or via CLI
# 1. Go to App Registration → Certificates & secrets
# 2. Click "New client secret"
# 3. Set expiration (24 months max)
# 4. Copy the secret VALUE (not ID!)
```

#### Step 2: Update Application

```bash
# For App Service deployment
az webapp config appsettings set \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings AZURE_CLIENT_SECRET="new-secret-value"

# For local/Docker
# Edit .env file and restart
```

#### Step 3: Verify New Credentials

```bash
# Wait 30 seconds for app restart
curl -s "$BASE_URL/health/detailed" | jq '.components.azure_configured'
# Should return: true

# Test sync
curl -X POST "$BASE_URL/api/v1/sync/resources"
```

#### Step 4: Remove Old Secret

```bash
# Only after confirming new secret works!
# In Azure Portal → App Registration → Certificates & secrets
# Delete the old expired secret
```

### 6.3 Emergency Credential Rotation

If credentials are compromised:

```bash
# 1. Immediately revoke old secret in Azure Portal

# 2. Create new secret

# 3. Update application
az webapp config appsettings set \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings AZURE_CLIENT_SECRET="new-secret-value"

# 4. Force restart
az webapp restart --name $APP_NAME --resource-group $RESOURCE_GROUP

# 5. Verify
sleep 10
curl -s "$BASE_URL/health"

# 6. Run preflight checks
curl -X POST "$BASE_URL/api/v1/preflight/run"
```

---

## 7. Backup and Restore Procedures

### 7.1 Automated Daily Backup

```bash
#!/bin/bash
# Save as backup-script.sh

BACKUP_DIR="/backups/governance-platform"
DB_PATH="data/governance.db"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup database
cp $DB_PATH "$BACKUP_DIR/governance-$DATE.db"

# Compress
 gzip "$BACKUP_DIR/governance-$DATE.db"

# Cleanup old backups (keep 30 days)
find $BACKUP_DIR -name "governance-*.db.gz" -mtime +30 -delete

echo "Backup completed: governance-$DATE.db.gz"
```

Schedule with cron:
```bash
# Daily at 2 AM
0 2 * * * /path/to/backup-script.sh
```

### 7.2 Azure Storage Backup (App Service)

```bash
# Mount Azure Files for persistent storage
az webapp config storage-account add \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --custom-id BackupVolume \
  --storage-type AzureFiles \
  --account-name $STORAGE_ACCOUNT \
  --share-name backups \
  --mount-path /home/backups

# Backup script will now save to /home/backups
```

### 7.3 Database Restore

```bash
# 1. Stop application
az webapp stop --name $APP_NAME --resource-group $RESOURCE_GROUP

# 2. Backup current database (just in case)
cp data/governance.db data/governance-corrupted-$(date +%Y%m%d).db

# 3. Restore from backup
cp backups/governance-20250224_020000.db data/governance.db

# 4. Verify database integrity
python -c "from app.core.database import SessionLocal; db = SessionLocal(); print('Database OK')"

# 5. Start application
az webapp start --name $APP_NAME --resource-group $RESOURCE_GROUP

# 6. Verify
curl -s "$BASE_URL/health"
```

### 7.4 Point-in-Time Recovery

If you need to restore to a specific point:

```bash
# List available backups
ls -la backups/governance-*.db.gz

# Extract specific backup
gunzip -c backups/governance-20250224_020000.db.gz > data/governance.db

# Restart application
az webapp restart --name $APP_NAME --resource-group $RESOURCE_GROUP
```

---

## 8. Escalation Procedures

### 8.1 Severity Levels

| Level | Description | Response Time | Escalation Path |
|-------|-------------|---------------|-----------------|
| **P1 - Critical** | Platform down, no data access | 15 minutes | Page on-call → Manager → VP |
| **P2 - High** | Major feature broken, workarounds exist | 1 hour | Ticket → On-call → Manager |
| **P3 - Medium** | Minor feature issue | 4 hours | Ticket → Team queue |
| **P4 - Low** | Cosmetic issue, question | 24 hours | Ticket → Team queue |

### 8.2 Escalation Contacts

```yaml
escalation_path:
  level_1:
    name: "Platform Support"
    contact: "platform-support@company.com"
    pager: "+1-XXX-XXX-XXXX"
    response_time: "15 minutes"

  level_2:
    name: "DevOps Manager"
    contact: "devops-manager@company.com"
    pager: "+1-XXX-XXX-XXXX"
    response_time: "1 hour"

  level_3:
    name: "VP Engineering"
    contact: "vp-eng@company.com"
    response_time: "4 hours"

  external:
    microsoft_support:
      portal: "https://portal.azure.com/#blade/Microsoft_Azure_Support/HelpAndSupportBlade"
      severity_a_response: "1 hour"
```

### 8.3 Incident Response Template

```markdown
## Incident Report: [Brief Description]

**Severity:** P1/P2/P3/P4
**Start Time:** YYYY-MM-DD HH:MM UTC
**Status:** Investigating/Resolved

### Impact
- [ ] Complete outage
- [ ] Partial outage (describe)
- [ ] Data issue
- [ ] Performance degradation

### Symptoms
- Dashboard inaccessible
- Sync jobs failing
- Specific error messages

### Actions Taken
1. [Action 1]
2. [Action 2]

### Root Cause (if known)
[Description]

### Resolution
[Steps taken to resolve]

### Prevention
[How to prevent recurrence]
```

---

## 9. Emergency Procedures

### 9.1 Complete Platform Outage

```bash
# 1. Check Azure status
# https://status.azure.com

# 2. Check if App Service is running
az webapp show --name $APP_NAME --resource-group $RESOURCE_GROUP --query "state"

# 3. If stopped, start it
az webapp start --name $APP_NAME --resource-group $RESOURCE_GROUP

# 4. If running but unresponsive, restart
az webapp restart --name $APP_NAME --resource-group $RESOURCE_GROUP

# 5. Check logs
az webapp log tail --name $APP_NAME --resource-group $RESOURCE_GROUP

# 6. If still down, check resource constraints
az webapp show --name $APP_NAME --resource-group $RESOURCE_GROUP --query "{cpu: siteConfig.numberOfWorkers, memory: siteConfig.memorySize}"

# 7. Scale up if needed
az appservice plan update --name ${APP_NAME}-plan --resource-group $RESOURCE_GROUP --sku S1
```

### 9.2 Database Corruption

```bash
# 1. Stop application
az webapp stop --name $APP_NAME --resource-group $RESOURCE_GROUP

# 2. Backup corrupted database
cp data/governance.db data/governance-corrupted-$(date +%Y%m%d).db

# 3. Restore from last known good backup
cp backups/governance-LAST-GOOD.db data/governance.db

# 4. Start application
az webapp start --name $APP_NAME --resource-group $RESOURCE_GROUP

# 5. Trigger full sync to recover data
curl -X POST "$BASE_URL/api/v1/sync/costs"
curl -X POST "$BASE_URL/api/v1/sync/compliance"
curl -X POST "$BASE_URL/api/v1/sync/resources"
curl -X POST "$BASE_URL/api/v1/sync/identity"

# 6. Monitor recovery
curl -s "$BASE_URL/api/v1/sync/status"
```

### 9.3 Security Incident

```bash
# 1. Immediately rotate all credentials
# See Section 6.3

# 2. Enable enhanced logging
az webapp config appsettings set \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings LOG_LEVEL=DEBUG

# 3. Review access logs
az webapp log tail --name $APP_NAME --resource-group $RESOURCE_GROUP --filter "auth"

# 4. Check for unauthorized access
curl -s "$BASE_URL/api/v1/tenants" | jq '.[].tenant_id'

# 5. Notify security team
# Create incident ticket with severity P1

# 6. Preserve evidence
# Do not delete logs until investigation complete
```

---

## 10. Common Operational Tasks

### 10.1 Clearing Cache

```bash
# Clear preflight cache
curl -X POST "$BASE_URL/api/v1/preflight/clear-cache"

# Restart to clear application cache
az webapp restart --name $APP_NAME --resource-group $RESOURCE_GROUP
```

### 10.2 Resetting Metrics

```bash
# Reset performance metrics
curl -X POST "$BASE_URL/monitoring/reset"

# Note: This affects dashboards until new data is collected
```

### 10.3 Resolving Alerts

```bash
# List active alerts
curl -s "$BASE_URL/api/v1/sync/alerts" | jq '.alerts[] | {id, title, severity}'

# Resolve specific alert
curl -X POST "$BASE_URL/api/v1/sync/alerts/123/resolve" \
  -H "Content-Type: application/json" \
  -d '{"resolved_by": "operator@company.com"}'

# Resolve all alerts of a type
curl -s "$BASE_URL/api/v1/sync/alerts" | jq '.alerts[].id' | \
  xargs -I {} curl -X POST "$BASE_URL/api/v1/sync/alerts/{}/resolve"
```

### 10.4 Generating Reports

```bash
# Export cost data
curl -s "$BASE_URL/api/v1/exports/costs?start_date=2025-01-01&end_date=2025-02-25" \
  -o costs-export.csv

# Export compliance data
curl -s "$BASE_URL/api/v1/exports/compliance" \
  -o compliance-export.csv

# Export resource inventory
curl -s "$BASE_URL/api/v1/exports/resources" \
  -o resources-export.csv
```

---

## 11. Performance Tuning

### 11.1 Identifying Bottlenecks

```bash
# Check slow queries
curl -s "$BASE_URL/monitoring/queries?slow_only=true" | jq '.[] | {query, duration_ms}'

# Check sync job performance
curl -s "$BASE_URL/monitoring/sync-jobs" | jq '.[] | {job_type, duration_ms}'

# Check cache hit rate
curl -s "$BASE_URL/monitoring/cache" | jq '.hit_rate_percent'
```

### 11.2 Optimization Recommendations

| Metric | Target | If Below Target |
|--------|--------|-----------------|
| Cache hit rate | >80% | Enable caching, increase TTL |
| API response time | <500ms | Add indexes, optimize queries |
| Sync duration | <30 min | Scale up App Service plan |
| Database size | <1GB | Archive old data |

### 11.3 Scaling Procedures

```bash
# Scale up App Service plan
az appservice plan update \
  --name ${APP_NAME}-plan \
  --resource-group $RESOURCE_GROUP \
  --sku S1  # or P1V2 for production

# Scale down (cost optimization)
az appservice plan update \
  --name ${APP_NAME}-plan \
  --resource-group $RESOURCE_GROUP \
  --sku B1
```

---

## 12. Maintenance Windows

### 12.1 Scheduled Maintenance

| Task | Frequency | Duration | Impact |
|------|-----------|----------|--------|
| Certificate renewal | Annually | 30 min | Brief interruption |
| Secret rotation | Quarterly | 15 min | Brief interruption |
| Platform updates | Monthly | 1 hour | Read-only mode |
| Database cleanup | Weekly | 30 min | Performance impact |
| Full backup | Daily | 10 min | Minimal |

### 12.2 Maintenance Window Procedure

```bash
# 1. Schedule maintenance (1 week advance notice)
# Send notification to stakeholders

# 2. Pre-maintenance checks
curl -s "$BASE_URL/health"
curl -s "$BASE_URL/api/v1/status"

# 3. Put system in maintenance mode (if implemented)
curl -X POST "$BASE_URL/api/v1/maintenance/enable" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Scheduled maintenance", "duration_minutes": 60}'

# 4. Perform maintenance tasks
# [Your maintenance tasks here]

# 5. Exit maintenance mode
curl -X POST "$BASE_URL/api/v1/maintenance/disable"

# 6. Post-maintenance verification
curl -s "$BASE_URL/health"
curl -X POST "$BASE_URL/api/v1/sync/resources"
curl -s "$BASE_URL/api/v1/sync/status"

# 7. Notify stakeholders of completion
```

### 12.3 Emergency Maintenance

For unplanned maintenance:

1. Assess urgency (can it wait for scheduled window?)
2. Notify stakeholders immediately
3. Document reason and estimated duration
4. Proceed with Section 12.2 steps 2-7
5. Post-incident review within 48 hours

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | February 2025 | Initial runbook |

---

**Related Documents:**
- [Deployment Guide](./DEPLOYMENT.md)
- [API Documentation](./API.md)
- [Implementation Guide](./IMPLEMENTATION_GUIDE.md)
- [Common Pitfalls](./COMMON_PITFALLS.md)

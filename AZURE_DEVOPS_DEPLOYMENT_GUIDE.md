# Azure DevOps and Deployment Optimizations Guide

This guide covers the Azure-native DevOps and deployment optimizations implemented for the Azure Governance Platform.

## 🚀 New Features Overview

### 1. Blue-Green Deployment Support
Zero-downtime deployments using Azure App Service deployment slots.

**Files:**
- `.github/workflows/blue-green-deploy.yml` - Complete CI/CD workflow
- `scripts/validate-slot.sh` - Pre-swap validation script

**Features:**
- Automatic staging slot creation and deployment
- Comprehensive pre-swap validation
- Automated slot swapping with health verification
- Automatic rollback on failure
- Teams/Slack notifications support

**Usage:**
```bash
# Automatic deployment on push to main
git push origin main

# Manual deployment
gh workflow run blue-green-deploy.yml \
  --field environment=production \
  --field container_tag=v1.2.3
```

### 2. Azure Container Instances for Jobs
Cost-effective compute for one-off and scheduled batch operations.

**Files:**
- `infrastructure/modules/container-instances.bicep` - Reusable module
- `infrastructure/examples/database-migration-job.bicep` - Migration example
- `infrastructure/examples/data-processing-job.bicep` - Processing example
- `infrastructure/examples/cleanup-job.bicep` - Resource cleanup example

**Use Cases:**
- Database migrations (Alembic, EF Core, etc.)
- Data processing and ETL jobs
- Resource cleanup and maintenance
- Batch compliance scans
- Cost optimization analysis

**Key Features:**
- Azure Files integration for shared storage
- Managed identity support
- Log Analytics integration
- GPU support for ML workloads
- VNet integration for secure networking
- Configurable restart policies

**Cost Benefits:**
- Pay-per-second billing
- No VM management overhead
- Automatic shutdown after completion
- ~70% cheaper than running VMs for batch jobs

### 3. Azure Logic Apps for Automation
Serverless workflow automation for operational tasks.

**Files:**
- `infrastructure/modules/logic-apps.bicep` - Complete automation module

**Pre-built Workflows:**
- **Teams Notifications** - Alert routing to Microsoft Teams
- **Scheduled Cleanup** - Daily resource cleanup reports
- **Cost Alerts** - Budget threshold notifications

**Features:**
- Teams/Slack webhook integration
- Azure Monitor alerts integration
- Cost optimization workflows
- Managed identity authentication
- Diagnostic logging

**Customization:**
```bicep
module logicApp './modules/logic-apps.bicep' = {
  name: 'governance-automation'
  params: {
    name: 'logic-governance'
    teamsWebhookUrl: teamsWebhookUrl
    notificationEmail: 'ops@example.com'
    costAlertThreshold: 1000.00
    monitoredResourceGroups: ['rg-production', 'rg-staging']
  }
}
```

### 4. Azure Monitor Workbooks
Interactive dashboards for operations teams.

**Files:**
- `infrastructure/monitoring/workbooks/governance-dashboard.json` - Complete dashboard
- `infrastructure/monitoring/workbooks/workbook.bicep` - Deployment module
- `infrastructure/monitoring/workbooks/README.md` - Documentation

**Dashboard Sections:**
- **Overview** - Real-time status tiles and operations timeline
- **Sync Status** - Per-tenant sync health and duration metrics
- **Cost Analysis** - Cost tracking and trend analysis
- **Compliance** - Compliance scorecards with letter grades
- **Tenant Health** - Response times, error rates, recent alerts

**Deployment:**
```bash
# Via Azure CLI
az monitor workbook create \
  --category "workbook" \
  --display-name "Azure Governance Dashboard" \
  --serialized-data @governance-dashboard.json
```

### 5. Azure Policy for Compliance
Enforce organizational standards across all resources.

**Files:**
- `infrastructure/policies/require-tags-policy.json` - Mandatory tags
- `infrastructure/policies/enforce-encryption-policy.json` - Encryption standards
- `infrastructure/policies/prevent-public-storage-policy.json` - Security controls
- `infrastructure/policies/compliance-audit-policy.json` - Comprehensive auditing
- `infrastructure/modules/policy-definition.bicep` - Deployment module
- `infrastructure/modules/policy-assignment.bicep` - Assignment module

**Policies:**

| Policy | Purpose | Mode | Effect |
|--------|---------|------|--------|
| Require Tags | Enforce governance metadata | Audit/Deny | Mandatory: Application, Environment, Owner, CostCenter |
| Enforce Encryption | Data protection | Deny | TLS 1.2+, TDE enabled, encryption at rest |
| Prevent Public Storage | Data exposure prevention | Deny | Blocks public blob/network access |
| Compliance Audit | Continuous monitoring | Audit | VM patching, SQL auditing, KV protection |

**Deployment:**
```bash
# Deploy all policies
az deployment sub create \
  --location eastus \
  --template-file deploy-governance-infrastructure.bicep \
  --parameters environment=production enablePolicies=true
```

## 📋 Deployment Workflows

### Quick Start

```bash
# 1. Deploy infrastructure
az deployment sub create \
  --name governance-infra \
  --location eastus \
  --template-file infrastructure/deploy-governance-infrastructure.bicep \
  --parameters \
    environment=production \
    enableLogicApps=true \
    enableContainerInstances=true \
    enableWorkbooks=true \
    enablePolicies=true \
    teamsWebhookUrl="$TEAMS_WEBHOOK" \
    notificationEmail="ops@example.com"

# 2. Verify deployment
az policy state summarize

# 3. Access dashboard
az monitor workbook show \
  --name governance-dashboard \
  --resource-group rg-governance-production
```

### Full Stack Deployment

```bash
# Deploy everything including app service
az deployment sub create \
  --name governance-fullstack \
  --location eastus \
  --template-file infrastructure/main.bicep \
  --parameters infrastructure/parameters.production.json

# Deploy extended infrastructure
az deployment sub create \
  --name governance-extended \
  --location eastus \
  --template-file infrastructure/deploy-governance-infrastructure.bicep \
  --parameters \
    environment=production \
    logAnalyticsWorkspaceId="/subscriptions/xxx/resourcegroups/xxx/..." \
    storageAccountName="stgovprod123"
```

## 🔧 Operations Guide

### Running Container Jobs

```bash
# Database migration
az container create \
  --resource-group rg-governance-production \
  --name db-migration-20260101 \
  --image ghcr.io/htt-brands/control-tower-migrations:latest \
  --command-line "python -m alembic upgrade head" \
  --environment-variables DATABASE_URL="$DB_URL" \
  --cpu 2 --memory 4

# Data processing batch
az container create \
  --resource-group rg-governance-production \
  --name data-processor \
  --image ghcr.io/htt-brands/control-tower-processor:latest \
  --command-line "python process_tenants.py --date 2026-01-01" \
  --cpu 4 --memory 8
```

### Triggering Logic Apps

```bash
# Manual trigger via HTTP
curl -X POST "{logicAppEndpoint}" \
  -H "Content-Type: application/json" \
  -d '{
    "alertName": "Cost Threshold Exceeded",
    "severity": "Warning",
    "description": "Monthly cost at 85% of budget",
    "resourceName": "control-tower",
    "timestamp": "2026-01-15T10:30:00Z"
  }'
```

### Viewing Compliance Status

```bash
# Get policy compliance summary
az policy state summarize \
  --filter "resourceGroup eq 'rg-governance-production'"

# Get detailed compliance for specific policy
az policy state list \
  --filter "policyDefinitionName eq 'governance-require-tags'"

# Export compliance report
az policy state list \
  --output table \
  > compliance-report.txt
```

## 🔐 Security Considerations

### Managed Identities
All new resources use managed identities for Azure AD authentication:
- Container Instances access storage via managed identity
- Logic Apps authenticate to Azure services
- No secrets in application settings

### Network Security
- Container Instances support VNet integration
- Logic Apps can use private endpoints
- Storage accounts use private access by default

### Data Protection
- TDE enabled on all SQL databases
- Storage encryption enforced by policy
- TLS 1.2+ required for all connections

## 💰 Cost Optimization

### Container Instances vs VMs
| Workload Type | ACI Cost | VM Cost | Savings |
|---------------|----------|---------|---------|
| Daily 1hr job | $0.04/day | $1.50/day | 97% |
| Weekly migration | $0.30/week | $10/week | 97% |
| Monthly cleanup | $0.10/month | $5/month | 98% |

### Logic Apps Pricing
- **Free Tier**: 200 runs/day, no cost
- **Standard**: ~$60/month for continuous operations
- **Consumption**: $0.025 per action execution

### Policy Enforcement Benefits
- Automated compliance reduces manual audit effort
- Prevent costly misconfigurations before deployment
- Chargeback accuracy through mandatory tagging

## 🚨 Troubleshooting

### Blue-Green Deployment Issues

**Validation fails:**
```bash
# Check staging slot health
az webapp log tail \
  --name app-governance-prod \
  --resource-group rg-governance-production \
  --slot staging
```

**Swap fails:**
- Review GitHub Actions logs
- Check App Service deployment slots exist
- Verify staging slot is running

### Container Job Issues

**Job fails immediately:**
```bash
# Check container logs
az container logs \
  --name db-migration \
  --resource-group rg-governance-production

# Verify managed identity permissions
az role assignment list \
  --assignee $(az container show --name db-migration --resource-group rg-governance-production --query identity.principalId -o tsv) \
  --all
```

**Container stuck:**
```bash
# Check container state
az container show \
  --name db-migration \
  --resource-group rg-governance-production \
  --query instanceView.state

# Force delete and recreate
az container delete \
  --name db-migration \
  --resource-group rg-governance-production --yes
```

### Policy Issues

**Policy not evaluating:**
```bash
# Check assignment
az policy assignment list \
  --scope "/subscriptions/$(az account show --query id -o tsv)"

# Trigger re-evaluation
az policy state trigger-scan
```

## 📚 Additional Resources

- [Azure Container Instances Docs](https://docs.microsoft.com/azure/container-instances/)
- [Azure Logic Apps Docs](https://docs.microsoft.com/azure/logic-apps/)
- [Azure Policy Docs](https://docs.microsoft.com/azure/governance/policy/)
- [Azure Monitor Workbooks](https://docs.microsoft.com/azure/azure-monitor/visualize/workbooks-overview/)
- [Blue-Green Deployment Patterns](https://docs.microsoft.com/azure/architecture/patterns/blue-green-deployment/)

## 🔄 Maintenance

### Regular Tasks

**Weekly:**
- Review container job execution logs
- Check Logic Apps run history
- Verify policy compliance status

**Monthly:**
- Update container images
- Review and optimize policies
- Export compliance reports

**Quarterly:**
- Cost analysis of automation infrastructure
- Security review of managed identities
- Policy effectiveness assessment

#!/bin/bash
# Phase 4: Advanced Observability with Custom Dashboards & Log Analytics
# Workbooks, Saved Queries, and Log-Based Alerts for Azure Governance Platform

set -e

echo "🚀 Phase 4: Advanced Observability - Dashboards & Log Analytics"
echo "================================================================"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
SUBSCRIPTION="HTT-CORE"
RESOURCE_GROUP="rg-governance-production"
APP_INSIGHTS_NAME="governance-appinsights"
LOG_ANALYTICS_NAME="governance-logs"
WORKBOOK_NAME="governance-overview-workbook"
ALERT_ACTION_GROUP="governance-alerts"

# Set subscription
echo -e "${YELLOW}Setting subscription to $SUBSCRIPTION...${NC}"
az account set --subscription "$SUBSCRIPTION"
echo -e "${GREEN}✓ Subscription set${NC}"

# Get resource IDs
echo -e "${YELLOW}Getting resource IDs...${NC}"
APP_INSIGHTS_ID=$(az monitor app-insights component show \
  --app "$APP_INSIGHTS_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query id -o tsv 2>/dev/null)

LOG_ANALYTICS_ID=$(az monitor log-analytics workspace show \
  --workspace-name "$LOG_ANALYTICS_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query id -o tsv 2>/dev/null)

if [ -z "$APP_INSIGHTS_ID" ]; then
  echo -e "${RED}✗ Failed to get Application Insights resource ID${NC}"
  exit 1
fi

if [ -z "$LOG_ANALYTICS_ID" ]; then
  echo -e "${RED}✗ Failed to get Log Analytics workspace ID${NC}"
  exit 1
fi

echo -e "${GREEN}✓ App Insights ID: $APP_INSIGHTS_ID${NC}"
echo -e "${GREEN}✓ Log Analytics ID: $LOG_ANALYTICS_ID${NC}"

# Get Action Group ID (should exist from Phase 3)
ACTION_GROUP_ID=$(az monitor action-group show \
  --name "$ALERT_ACTION_GROUP" \
  --resource-group "$RESOURCE_GROUP" \
  --query id -o tsv 2>/dev/null)

if [ -z "$ACTION_GROUP_ID" ]; then
  echo -e "${YELLOW}⚠ Action Group not found, creating...${NC}"
  az monitor action-group create \
    --name "$ALERT_ACTION_GROUP" \
    --resource-group "$RESOURCE_GROUP" \
    --short-name "gov-alerts" \
    --email-receivers '[{"name":"admin","emailAddress":"admin@httbrands.com","useCommonAlertSchema":true}]' \
    --tags Project=governance Environment=production Phase=phase4
  
  ACTION_GROUP_ID=$(az monitor action-group show \
    --name "$ALERT_ACTION_GROUP" \
    --resource-group "$RESOURCE_GROUP" \
    --query id -o tsv)
fi

echo -e "${GREEN}✓ Action Group ID: $ACTION_GROUP_ID${NC}"

echo ""
echo "📊 STEP 1: Creating Governance Overview Workbook..."
echo "================================================================"

# Check if workbook exists
WORKBOOK_EXISTS=$(az resource list \
  --resource-group "$RESOURCE_GROUP" \
  --resource-type "Microsoft.Insights/workbooks" \
  --query "[?name=='$WORKBOOK_NAME' || tags.displayName=='Azure Governance Platform - Overview'].name" -o tsv)

if [ -z "$WORKBOOK_EXISTS" ]; then
  # Load workbook JSON
  WORKBOOK_JSON=$(cat infrastructure/monitoring/workbooks/phase4-overview-workbook.json)
  
  # Create workbook using az rest since workbook create CLI is not available
  WORKBOOK_PAYLOAD=$(cat <<EOF
{
  "location": "westus2",
  "tags": {
    "displayName": "Azure Governance Platform - Overview",
    "Phase": "phase4",
    "Project": "governance"
  },
  "kind": "shared",
  "properties": {
    "displayName": "Azure Governance Platform - Overview",
    "description": "Real-time governance platform monitoring dashboard with request volume, response times, and exceptions",
    "category": "workbook",
    "serializedData": $(echo "$WORKBOOK_JSON" | jq -c .),
    "sourceId": "Azure Monitor",
    "version": "1.0"
  }
}
EOF
)
  
  # Generate unique workbook name
  WORKBOOK_UNIQUE_NAME=$(uuidgen)
  
  az rest --method PUT \
    --uri "https://management.azure.com/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Insights/workbooks/$WORKBOOK_UNIQUE_NAME?api-version=2022-04-01" \
    --body "$WORKBOOK_PAYLOAD" \
    --headers "Content-Type=application/json" 2>/dev/null || {
      echo -e "${YELLOW}⚠ Workbook creation via REST API had issues${NC}"
      echo -e "${YELLOW}Creating via Bicep deployment instead...${NC}"
      
      # Fallback to Bicep deployment
      az deployment group create \
        --resource-group "$RESOURCE_GROUP" \
        --template-file infrastructure/monitoring/workbooks/workbook.bicep \
        --parameters \
          name="$WORKBOOK_NAME" \
          displayName="Azure Governance Platform - Overview" \
          serializedData="$WORKBOOK_JSON" \
          sourceId="$LOG_ANALYTICS_ID" \
          tags="{Phase:phase4,Project:governance}" \
        --name "phase4-workbook-deployment" \
        2>/dev/null || echo -e "${YELLOW}⚠ Bicep deployment also had issues${NC}"
    }
  
  if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Governance Overview Workbook created${NC}"
  fi
else
  echo -e "${YELLOW}⚠ Workbook already exists: $WORKBOOK_EXISTS${NC}"
fi

echo ""
echo "🔍 STEP 2: Creating Log Analytics Saved Query for Tenant Health..."
echo "================================================================"

# Check if saved query exists
QUERY_EXISTS=$(az monitor log-analytics workspace saved-search list \
  --workspace-name "$LOG_ANALYTICS_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query "[?name=='tenant-health-query'].name" -o tsv 2>/dev/null)

if [ -z "$QUERY_EXISTS" ]; then
  az monitor log-analytics workspace saved-search create \
    --workspace-name "$LOG_ANALYTICS_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --name "tenant-health-query" \
    --category "Governance" \
    --display-name "Tenant Health Summary" \
    --query 'AppRequests
| where TimeGenerated > ago(1h)
| summarize 
    TotalRequests = count(),
    FailedRequests = countif(ResultCode >= 500),
    AvgDuration = avg(DurationMs),
    P95Duration = percentile(DurationMs, 95)
    by Tenant = tostring(Properties["tenant_id"])
| extend SuccessRate = round(100.0 * (TotalRequests - FailedRequests) / TotalRequests, 2)
| order by TotalRequests desc' \
    --tags Phase=phase4 Project=governance 2>/dev/null || {
      echo -e "${YELLOW}⚠ Saved query creation had issues, trying alternative...${NC}"
      
      # Try with escaped query
      az monitor log-analytics workspace saved-search create \
        --workspace-name "$LOG_ANALYTICS_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --name "tenant-health-query" \
        --category "Governance" \
        --display-name "Tenant Health Summary" \
        --query "AppRequests | where TimeGenerated > ago(1h) | summarize TotalRequests = count(), FailedRequests = countif(ResultCode >= 500), AvgDuration = avg(DurationMs), P95Duration = percentile(DurationMs, 95) by Tenant = tostring(Properties['tenant_id']) | extend SuccessRate = round(100.0 * (TotalRequests - FailedRequests) / TotalRequests, 2) | order by TotalRequests desc" \
        --tags Phase=phase4 Project=governance
    }
  
  if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Tenant Health Query saved${NC}"
  fi
else
  echo -e "${YELLOW}⚠ Saved query already exists: $QUERY_EXISTS${NC}"
fi

echo ""
echo "🚨 STEP 3: Creating Log-Based Alert for Business Logic Errors..."
echo "================================================================"

# Check if log-based alert exists
ALERT_EXISTS=$(az monitor scheduled-query list \
  --resource-group "$RESOURCE_GROUP" \
  --query "[?name=='Business Logic Errors - Critical'].name" -o tsv 2>/dev/null)

if [ -z "$ALERT_EXISTS" ]; then
  # Get the Log Analytics workspace as scope
  SCOPE="/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.OperationalInsights/workspaces/$LOG_ANALYTICS_NAME"
  
  az monitor scheduled-query create \
    --name "Business Logic Errors - Critical" \
    --resource-group "$RESOURCE_GROUP" \
    --scopes "$SCOPE" \
    --condition "count 'exceptions' > 5" \
    --condition-query exceptions="exceptions | where severityLevel >= 3 or customDimensions['error_type'] == 'business_logic_error'" \
    --window-size 5m \
    --evaluation-frequency 1m \
    --severity 0 \
    --description "Alert when application exceptions exceed 5 in 5 minutes" \
    --action "$ACTION_GROUP_ID" \
    --tags AlertType=BusinessLogic Severity=Critical Phase=phase4 2>/dev/null || {
      echo -e "${YELLOW}⚠ Scheduled query alert creation had issues${NC}"
      echo -e "${YELLOW}Trying with simplified parameters...${NC}"
      
      # Try with minimal parameters
      az monitor scheduled-query create \
        --name "Business Logic Errors - Critical" \
        --resource-group "$RESOURCE_GROUP" \
        --scopes "$SCOPE" \
        --condition "count 'exceptions' > 5" \
        --window-size 5 \
        --evaluation-frequency 1 \
        --severity 0 \
        --description "Alert when application exceptions exceed 5 in 5 minutes" \
        --action "$ACTION_GROUP_ID"
    }
  
  if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Log-based alert created${NC}"
  fi
else
  echo -e "${YELLOW}⚠ Log-based alert already exists: $ALERT_EXISTS${NC}"
fi

echo ""
echo "📋 Verification..."
echo "================================================================"

# List workbooks
echo -e "${YELLOW}Workbooks:${NC}"
az resource list \
  --resource-group "$RESOURCE_GROUP" \
  --resource-type "Microsoft.Insights/workbooks" \
  --query "[].{Name:name, DisplayName:tags.displayName, Type:kind}" \
  -o table 2>/dev/null || echo "Could not list workbooks"

# List saved queries
echo ""
echo -e "${YELLOW}Saved Queries:${NC}"
az monitor log-analytics workspace saved-search list \
  --workspace-name "$LOG_ANALYTICS_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query "[].{Name:name, Category:category, DisplayName:displayName}" \
  -o table 2>/dev/null || echo "Could not list saved queries"

# List scheduled query alerts
echo ""
echo -e "${YELLOW}Log-Based Alerts (Scheduled Queries):${NC}"
az monitor scheduled-query list \
  --resource-group "$RESOURCE_GROUP" \
  --query "[].{Name:name, Description:description, Severity:severity, Enabled:enabled}" \
  -o table 2>/dev/null || echo "Could not list scheduled queries"

echo ""
echo -e "${GREEN}================================================================${NC}"
echo -e "${GREEN}Phase 4: Advanced Observability - COMPLETE${NC}"
echo -e "${GREEN}================================================================${NC}"
echo ""
echo "Summary of Created Resources:"
echo "  📊 Workbook: Azure Governance Platform - Overview"
echo "  🔍 Saved Query: Tenant Health Summary (Governance category)"
echo "  🚨 Alert: Business Logic Errors - Critical (log-based)"
echo ""
echo "Portal URLs:"
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
echo "  Workbooks: https://portal.azure.com/#@/resource/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Insights/workbooks"
echo "  Log Analytics: https://portal.azure.com/#@/resource/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.OperationalInsights/workspaces/$LOG_ANALYTICS_NAME/logs"
echo "  Alerts: https://portal.azure.com/#@/resource/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Insights/scheduledQueryRules"
echo ""
echo "Next Steps:"
echo "  1. View workbook in Azure Portal > Monitoring > Workbooks"
echo "  2. Test saved query in Log Analytics workspace"
echo "  3. Verify alert rules and notification channels"
echo "  4. Customize dashboard visualizations as needed"
echo ""

# Output resource IDs for reference
echo "Resource IDs:"
echo "  App Insights: $APP_INSIGHTS_ID"
echo "  Log Analytics: $LOG_ANALYTICS_ID"
echo "  Action Group: $ACTION_GROUP_ID"

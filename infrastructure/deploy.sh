#!/bin/bash
# =============================================================================
# Azure Governance Platform - Infrastructure Deployment Script
# =============================================================================
# This script deploys the complete Azure infrastructure for the
# Azure Governance Platform using Bicep templates.
#
# Usage:
#   ./deploy.sh [environment] [location]
#
# Examples:
#   ./deploy.sh                    # Deploy to production in eastus
#   ./deploy.sh development        # Deploy to dev environment
#   ./deploy.sh production westus2 # Deploy to prod in westus2
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default values
ENVIRONMENT="${1:-production}"
LOCATION="${2:-eastus}"
SECONDARY_LOCATION="${3:-westus2}"
DEPLOYMENT_NAME="control-tower-${ENVIRONMENT}"

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(development|staging|production)$ ]]; then
    echo -e "${RED}Error: Environment must be one of: development, staging, production${NC}"
    exit 1
fi

# Select parameters file
case "$ENVIRONMENT" in
    development)
        PARAMS_FILE="parameters.dev.json"
        ;;
    staging)
        PARAMS_FILE="parameters.staging.json"
        ;;
    production)
        PARAMS_FILE="parameters.json"
        ;;
esac

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Azure Governance Platform Deployment${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "Environment: ${GREEN}${ENVIRONMENT}${NC}"
echo -e "Location: ${GREEN}${LOCATION}${NC}"
echo -e "Parameters: ${GREEN}${PARAMS_FILE}${NC}"
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check Azure CLI
if ! command -v az &> /dev/null; then
    echo -e "${RED}Error: Azure CLI is not installed${NC}"
    echo "Install from: https://docs.microsoft.com/cli/azure/install-azure-cli"
    exit 1
fi

# Check Bicep
if ! az bicep version &> /dev/null; then
    echo -e "${YELLOW}Installing Bicep...${NC}"
    az bicep install
fi

# Check login status
echo -e "${YELLOW}Checking Azure login status...${NC}"
if ! az account show &> /dev/null; then
    echo -e "${YELLOW}Please login to Azure:${NC}"
    az login
fi

# Get subscription info
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
SUBSCRIPTION_NAME=$(az account show --query name -o tsv)
echo -e "Using subscription: ${GREEN}${SUBSCRIPTION_NAME} (${SUBSCRIPTION_ID})${NC}"
echo ""

# Confirm deployment
if [[ "$ENVIRONMENT" == "production" ]]; then
    echo -e "${RED}WARNING: You are about to deploy to PRODUCTION${NC}"
    read -p "Are you sure? (yes/no): " confirm
    if [[ "$confirm" != "yes" ]]; then
        echo -e "${YELLOW}Deployment cancelled${NC}"
        exit 0
    fi
fi

# Generate SQL password if needed
SQL_ADMIN_PASSWORD=""
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
    SQL_ADMIN_PASSWORD=$(grep -E '^SQL_ADMIN_PASSWORD=' "${PROJECT_ROOT}/.env" | cut -d'=' -f2 | tr -d '"' || echo "")
fi

if [[ -z "$SQL_ADMIN_PASSWORD" ]]; then
    SQL_ADMIN_PASSWORD=$(openssl rand -base64 24 2>/dev/null || tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 24)
    echo -e "${YELLOW}Generated SQL admin password${NC}"
fi

echo -e "${YELLOW}Starting deployment...${NC}"
echo ""

# Change to infrastructure directory
cd "$SCRIPT_DIR"

# Deploy using Bicep
echo -e "${BLUE}Deploying infrastructure...${NC}"
az deployment sub create \
    --name "$DEPLOYMENT_NAME" \
    --location "$LOCATION" \
    --template-file main.bicep \
    --parameters "${PARAMS_FILE}" \
    --parameters location="$LOCATION" \
    --parameters secondaryLocation="$SECONDARY_LOCATION" \
    --parameters sqlAdminPassword="$SQL_ADMIN_PASSWORD" \
    --output none \
    || {
        echo -e "${RED}Deployment failed!${NC}"
        exit 1
    }

echo -e "${GREEN}✓ Infrastructure deployed successfully${NC}"
echo ""

# Get deployment outputs
echo -e "${YELLOW}Getting deployment outputs...${NC}"
OUTPUTS=$(az deployment sub show --name "$DEPLOYMENT_NAME" --query properties.outputs -o json 2>/dev/null || echo '{}')

APP_SERVICE_NAME=$(echo "$OUTPUTS" | grep -o '"appServiceName": "[^"]*"' | cut -d'"' -f4 || echo "")
APP_URL=$(echo "$OUTPUTS" | grep -o '"appUrl": "[^"]*"' | cut -d'"' -f4 || echo "")
RESOURCE_GROUP_NAME=$(echo "$OUTPUTS" | grep -o '"resourceGroupName": "[^"]*"' | cut -d'"' -f4 || echo "")
KEY_VAULT_NAME=$(echo "$OUTPUTS" | grep -o '"keyVaultName": "[^"]*"' | cut -d'"' -f4 || echo "")
STORAGE_ACCOUNT_NAME=$(echo "$OUTPUTS" | grep -o '"storageAccountName": "[^"]*"' | cut -d'"' -f4 || echo "")

# If outputs are empty, try to get them another way
if [[ -z "$APP_SERVICE_NAME" ]]; then
    RESOURCE_GROUP_NAME="rg-governance-${ENVIRONMENT}"
    APP_SERVICE_NAME=$(az webapp list --resource-group "$RESOURCE_GROUP_NAME" --query '[0].name' -o tsv 2>/dev/null || echo "")
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Resource Group: ${BLUE}${RESOURCE_GROUP_NAME}${NC}"
echo -e "App Service: ${BLUE}${APP_SERVICE_NAME}${NC}"
echo -e "Storage Account: ${BLUE}${STORAGE_ACCOUNT_NAME}${NC}"
echo -e "Key Vault: ${BLUE}${KEY_VAULT_NAME}${NC}"
echo ""

# Get App Service URL
if [[ -n "$APP_SERVICE_NAME" && -n "$RESOURCE_GROUP_NAME" ]]; then
    APP_URL=$(az webapp show --name "$APP_SERVICE_NAME" --resource-group "$RESOURCE_GROUP_NAME" --query defaultHostName -o tsv 2>/dev/null || echo "")
    if [[ -n "$APP_URL" ]]; then
        echo -e "Application URL: ${GREEN}https://${APP_URL}${NC}"
        echo -e "Health Check: ${GREEN}https://${APP_URL}/health${NC}"
    fi
fi

echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Configure Azure AD credentials in the App Service settings"
echo "2. Store secrets in Key Vault: ${KEY_VAULT_NAME}"
echo "3. Configure deployment from your GitHub repository"
echo "4. Run database initialization"
echo ""
echo -e "${BLUE}Azure Portal:${NC} https://portal.azure.com/#@${SUBSCRIPTION_ID}/resource/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP_NAME}"
echo ""

# Save deployment info
cat > "${SCRIPT_DIR}/.deployment-info-${ENVIRONMENT}.json" << EOF
{
  "environment": "${ENVIRONMENT}",
  "location": "${LOCATION}",
  "subscriptionId": "${SUBSCRIPTION_ID}",
  "subscriptionName": "${SUBSCRIPTION_NAME}",
  "resourceGroup": "${RESOURCE_GROUP_NAME}",
  "appServiceName": "${APP_SERVICE_NAME}",
  "storageAccountName": "${STORAGE_ACCOUNT_NAME}",
  "keyVaultName": "${KEY_VAULT_NAME}",
  "appUrl": "https://${APP_URL}",
  "deploymentTime": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo -e "${GREEN}Deployment info saved to: ${SCRIPT_DIR}/.deployment-info-${ENVIRONMENT}.json${NC}"
echo ""
echo -e "${GREEN}Done!${NC}"

#!/bin/bash
# =============================================================================
# Azure Lighthouse Setup Script for Azure Governance Platform
# =============================================================================
# This script configures Azure Lighthouse delegation for multi-tenant
# management. It retrieves the Managed Identity from the App Service
# and generates a deployment template for customer onboarding.
#
# Usage:
#   ./scripts/setup-lighthouse.sh [app-service-name] [resource-group]
#
# Arguments:
#   app-service-name: Name of the Azure App Service (default: app-governance-dev-001)
#   resource-group:   Name of the resource group (default: rg-governance-dev-001)
#
# Examples:
#   ./scripts/setup-lighthouse.sh
#   ./scripts/setup-lighthouse.sh app-governance-prod-001 rg-governance-prod-001
#
# Supported Tenant Types:
#   - htt (Head-To-Toe)
#   - frenchies (Frenchies)
#   - bishops (Bishops)
#   - tll (Lash Lounge)
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
OUTPUT_TEMPLATE="$PROJECT_ROOT/infrastructure/lighthouse/delegation.json"

# Default values
DEFAULT_APP_SERVICE_NAME="app-governance-dev-001"
DEFAULT_RESOURCE_GROUP="rg-governance-dev-001"

# Parse arguments
APP_SERVICE_NAME="${1:-$DEFAULT_APP_SERVICE_NAME}"
RESOURCE_GROUP="${2:-$DEFAULT_RESOURCE_GROUP}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Azure Lighthouse Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# =============================================================================
# Prerequisites Check
# =============================================================================

echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check Azure CLI
if ! command -v az &> /dev/null; then
    echo -e "${RED}Error: Azure CLI not found. Please install it:${NC}"
    echo "  https://docs.microsoft.com/cli/azure/install-azure-cli"
    exit 1
fi

# Check jq for JSON processing
if ! command -v jq &> /dev/null; then
    echo -e "${YELLOW}Warning: jq not found. JSON output will not be formatted.${NC}"
    echo "  Install jq for better output formatting:"
    echo "    - macOS: brew install jq"
    echo "    - Ubuntu/Debian: sudo apt-get install jq"
    echo "    - RHEL/CentOS: sudo yum install jq"
    HAS_JQ=false
else
    HAS_JQ=true
fi

# Check Azure CLI version
AZ_VERSION=$(az version --query "azure-cli" -o tsv)
echo -e "  Azure CLI version: ${GREEN}${AZ_VERSION}${NC}"

# Check login status
echo -e "  Checking Azure login status...${NC}"
if ! az account show &> /dev/null; then
    echo -e "${YELLOW}Logging in to Azure...${NC}"
    az login
fi

# Get current subscription info
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
SUBSCRIPTION_NAME=$(az account show --query name -o tsv)
TENANT_ID=$(az account show --query tenantId -o tsv)

echo -e "  Current subscription: ${GREEN}${SUBSCRIPTION_NAME}${NC}"
echo -e "  Subscription ID: ${GREEN}${SUBSCRIPTION_ID}${NC}"
echo -e "  Tenant ID: ${GREEN}${TENANT_ID}${NC}"
echo ""

# =============================================================================
# Get Managed Identity Information
# =============================================================================

echo -e "${YELLOW}Retrieving Managed Identity from App Service...${NC}"
echo -e "  App Service: ${CYAN}${APP_SERVICE_NAME}${NC}"
echo -e "  Resource Group: ${CYAN}${RESOURCE_GROUP}${NC}"
echo ""

# Verify App Service exists
echo -e "  Verifying App Service exists...${NC}"
if ! az webapp show --name "$APP_SERVICE_NAME" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
    echo -e "${RED}Error: App Service '${APP_SERVICE_NAME}' not found in resource group '${RESOURCE_GROUP}'${NC}"
    echo ""
    echo "Available App Services in subscription:"
    az webapp list --query "[].{name:name, resourceGroup:resourceGroup}" -o table
    exit 1
fi
echo -e "  ${GREEN}✓ App Service found${NC}"

# Get Managed Identity Principal ID
echo -e "  Retrieving Managed Identity...${NC}"
PRINCIPAL_ID=$(az webapp identity show \
    --name "$APP_SERVICE_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query principalId \
    --output tsv 2>/dev/null)

if [ -z "$PRINCIPAL_ID" ]; then
    echo -e "${YELLOW}Managed Identity not found. Creating...${NC}"
    PRINCIPAL_ID=$(az webapp identity assign \
        --name "$APP_SERVICE_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query principalId \
        --output tsv)
    echo -e "  ${GREEN}✓ Managed Identity created${NC}"
else
    echo -e "  ${GREEN}✓ Managed Identity found${NC}"
fi

# Get Managed Identity details
echo -e "  Retrieving identity details...${NC}"
IDENTITY_INFO=$(az ad sp show --id "$PRINCIPAL_ID" 2>/dev/null || echo "")

if [ -n "$IDENTITY_INFO" ] && [ "$HAS_JQ" = true ]; then
    IDENTITY_NAME=$(echo "$IDENTITY_INFO" | jq -r '.displayName')
    IDENTITY_APP_ID=$(echo "$IDENTITY_INFO" | jq -r '.appId')
    echo -e "  Identity Name: ${CYAN}${IDENTITY_NAME}${NC}"
    echo -e "  App ID: ${CYAN}${IDENTITY_APP_ID}${NC}"
fi

echo -e "  Principal ID: ${CYAN}${PRINCIPAL_ID}${NC}"
echo ""

# =============================================================================
# Generate Delegation Template
# =============================================================================

echo -e "${YELLOW}Generating Lighthouse delegation template...${NC}"

# Create the delegation template with actual values
TEMPLATE_CONTENT=$(cat <<EOF
{
  "\$schema": "https://schema.management.azure.com/schemas/2019-08-01/subscriptionDeploymentTemplate.json#",
  "contentVersion": "1.0.0.0",
  "metadata": {
    "description": "Azure Lighthouse delegation template for Azure Governance Platform",
    "version": "1.0.0",
    "author": "Azure Governance Platform",
    "generatedAt": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
    "serviceProvider": {
      "tenantId": "${TENANT_ID}",
      "managedIdentityPrincipalId": "${PRINCIPAL_ID}",
      "appServiceName": "${APP_SERVICE_NAME}",
      "resourceGroup": "${RESOURCE_GROUP}"
    },
    "supportedTenantTypes": ["htt", "frenchies", "bishops", "tll"]
  },
  "parameters": {
    "managedByTenantId": {
      "type": "string",
      "defaultValue": "${TENANT_ID}",
      "metadata": {
        "description": "The Azure AD tenant ID of the service provider (Azure Governance Platform)"
      }
    },
    "managedByPrincipalId": {
      "type": "string",
      "defaultValue": "${PRINCIPAL_ID}",
      "metadata": {
        "description": "The Object ID of the Managed Identity from the Azure Governance Platform App Service"
      }
    },
    "mspOfferName": {
      "type": "string",
      "defaultValue": "Azure Governance Platform",
      "metadata": {
        "description": "Name of the Lighthouse offer"
      }
    },
    "mspOfferDescription": {
      "type": "string",
      "defaultValue": "Multi-tenant governance, compliance, and cost management through Azure Lighthouse delegation",
      "metadata": {
        "description": "Description of the Lighthouse offer"
      }
    },
    "principalDisplayName": {
      "type": "string",
      "defaultValue": "Azure Governance Platform Managed Identity",
      "metadata": {
        "description": "Display name for the managed identity principal"
      }
    }
  },
  "variables": {
    "registrationDefinitionName": "[parameters('mspOfferName')]",
    "registrationDefinitionId": "[guid(parameters('mspOfferName'), parameters('managedByTenantId'), subscription().subscriptionId)]"
  },
  "resources": [
    {
      "type": "Microsoft.ManagedServices/registrationDefinitions",
      "apiVersion": "2022-10-01",
      "name": "[variables('registrationDefinitionId')]",
      "properties": {
        "registrationDefinitionName": "[parameters('mspOfferName')]",
        "description": "[parameters('mspOfferDescription')]",
        "managedByTenantId": "[parameters('managedByTenantId')]",
        "authorizations": [
          {
            "principalId": "[parameters('managedByPrincipalId')]",
            "principalIdDisplayName": "[concat(parameters('principalDisplayName'), ' - Contributor')]",
            "roleDefinitionId": "b24988ac-6180-42a0-ab88-20f7382dd24c"
          },
          {
            "principalId": "[parameters('managedByPrincipalId')]",
            "principalIdDisplayName": "[concat(parameters('principalDisplayName'), ' - Cost Management Reader')]",
            "roleDefinitionId": "72fafb9e-0641-4937-9268-a91bfd8191a3"
          },
          {
            "principalId": "[parameters('managedByPrincipalId')]",
            "principalIdDisplayName": "[concat(parameters('principalDisplayName'), ' - Security Reader')]",
            "roleDefinitionId": "39bc4728-0917-49c7-9d2c-d95423bc2eb4"
          }
        ]
      }
    },
    {
      "type": "Microsoft.ManagedServices/registrationAssignments",
      "apiVersion": "2022-10-01",
      "name": "[variables('registrationDefinitionId')]",
      "dependsOn": [
        "[resourceId('Microsoft.ManagedServices/registrationDefinitions', variables('registrationDefinitionId'))]"
      ],
      "properties": {
        "registrationDefinitionId": "[resourceId('Microsoft.ManagedServices/registrationDefinitions', variables('registrationDefinitionId'))]"
      }
    }
  ],
  "outputs": {
    "registrationDefinitionId": {
      "type": "string",
      "value": "[variables('registrationDefinitionId')]",
      "metadata": {
        "description": "The unique ID of the Lighthouse registration definition"
      }
    },
    "registrationDefinitionName": {
      "type": "string",
      "value": "[variables('registrationDefinitionName')]",
      "metadata": {
        "description": "The name of the Lighthouse registration definition"
      }
    },
    "managedByTenantId": {
      "type": "string",
      "value": "[parameters('managedByTenantId')]",
      "metadata": {
        "description": "The service provider tenant ID"
      }
    },
    "subscriptionId": {
      "type": "string",
      "value": "[subscription().subscriptionId]",
      "metadata": {
        "description": "The customer subscription ID where delegation is applied"
      }
    },
    "authorizations": {
      "type": "array",
      "value": [
        {
          "roleName": "Contributor",
          "roleDefinitionId": "b24988ac-6180-42a0-ab88-20f7382dd24c",
          "description": "Grants full access to manage all resources, but does not allow assigning roles"
        },
        {
          "roleName": "Cost Management Reader",
          "roleDefinitionId": "72fafb9e-0641-4937-9268-a91bfd8191a3",
          "description": "Can view cost data and configuration"
        },
        {
          "roleName": "Security Reader",
          "roleDefinitionId": "39bc4728-0917-49c7-9d2c-d95423bc2eb4",
          "description": "Can view security-related information such as policies, recommendations, and security alerts"
        }
      ],
      "metadata": {
        "description": "List of RBAC roles delegated to the service provider"
      }
    }
  }
}
EOF
)

# Write the template
echo "$TEMPLATE_CONTENT" > "$OUTPUT_TEMPLATE"

if [ -f "$OUTPUT_TEMPLATE" ]; then
    echo -e "  ${GREEN}✓ Template generated${NC}"
    echo -e "  Location: ${CYAN}${OUTPUT_TEMPLATE}${NC}"
    
    if [ "$HAS_JQ" = true ]; then
        echo ""
        echo -e "  Template preview:${NC}"
        jq '.' "$OUTPUT_TEMPLATE" | head -20
        echo "  ..."
    fi
else
    echo -e "  ${RED}✗ Failed to generate template${NC}"
    exit 1
fi

echo ""

# =============================================================================
# Summary
# =============================================================================

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Lighthouse Configuration Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}Service Provider Configuration:${NC}"
echo -e "  Tenant ID:              ${CYAN}${TENANT_ID}${NC}"
echo -e "  Managed Identity ID:    ${CYAN}${PRINCIPAL_ID}${NC}"
echo -e "  App Service:            ${CYAN}${APP_SERVICE_NAME}${NC}"
echo -e "  Resource Group:         ${CYAN}${RESOURCE_GROUP}${NC}"
echo ""
echo -e "${BLUE}Generated Files:${NC}"
echo -e "  Template: ${CYAN}${OUTPUT_TEMPLATE}${NC}"
echo ""

# =============================================================================
# Customer Deployment Instructions
# =============================================================================

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}Customer Deployment Instructions${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""
echo -e "To delegate subscription access to Azure Governance Platform, customers should:${NC}"
echo ""
echo -e "${CYAN}1. Save the delegation template to their local machine${NC}"
echo "   The template is located at:"
echo "   ${OUTPUT_TEMPLATE}"
echo ""
echo -e "${CYAN}2. Deploy using Azure CLI:${NC}"
echo "   az deployment sub create \\"
echo "     --name \"governance-platform-delegation\" \\"
echo "     --location \"eastus\" \\"
echo "     --template-file \"${OUTPUT_TEMPLATE}\""
echo ""
echo -e "${CYAN}3. Or deploy using Azure Portal:${NC}"
echo "   - Navigate to 'Deploy a custom template' in the Azure Portal"
echo "   - Select 'Build your own template in the editor'"
echo "   - Copy and paste the contents of delegation.json"
echo "   - Select the target subscription"
echo "   - Deploy"
echo ""
echo -e "${CYAN}4. Verify deployment:${NC}"
echo "   az managedservices definition list --output table"
echo "   az managedservices assignment list --output table"
echo ""

# =============================================================================
# Supported Tenant Types
# =============================================================================

echo -e "${YELLOW}========================================${NC}"
echo -e "${YELLOW}Supported Tenant Types${NC}"
echo -e "${YELLOW}========================================${NC}"
echo ""
echo "The following tenant types are supported for Lighthouse delegation:"
echo ""
echo -e "  ${GREEN}htt${NC}       - Head-To-Toe (HTT Brands)"
echo -e "  ${GREEN}frenchies${NC} - Frenchies (FN)"
echo -e "  ${GREEN}bishops${NC}   - Bishops (BCC)"
echo -e "  ${GREEN}tll${NC}       - Lash Lounge (TLL)"
echo ""
echo "For each tenant, ensure the 'use_lighthouse' field is set to true"
echo "in the Tenant model to enable Lighthouse-based access."
echo ""

# =============================================================================
# Next Steps
# =============================================================================

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Next Steps${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "1. Share the delegation template with customers"
echo "2. Customers deploy the template in their subscription"
echo "3. Verify delegation is active using Azure CLI or Portal"
echo "4. Update tenant configuration: use_lighthouse = true"
echo "5. Test cross-tenant access from the App Service"
echo ""
echo -e "${BLUE}Useful Commands:${NC}"
echo "  # List all delegated subscriptions"
echo "  az account list --output table"
echo ""
echo "  # View registration definitions"
echo "  az managedservices definition list --output table"
echo ""
echo "  # View registration assignments"
echo "  az managedservices assignment list --output table"
echo ""
echo "  # Delete a registration (if needed)"
echo "  az managedservices assignment delete --assignment <assignment-id>"
echo "  az managedservices definition delete --definition <definition-id>"
echo ""

echo -e "${GREEN}Done!${NC}"

targetScope = 'resourceGroup'

// Deployed at resource-group scope because every resource in this file is
// RG-scoped (deployment scripts, managed identity, role assignments). Use:
//   az deployment group create -g <rg> -f infrastructure/github-oidc.bicep
// Flipped from 'subscription' scope to resolve BCP135 errors; the previous
// `existing` RG reference is no longer needed now that the file runs IN the RG.

// =============================================================================
// Azure Governance Platform - GitHub OIDC Federation Bicep Template
// =============================================================================
// This template configures OIDC federation between Azure AD and GitHub Actions.
// 
// WHAT IT DOES:
//   - Creates Azure AD App Registration for GitHub Actions
//   - Creates Service Principal
//   - Configures federated credentials for branch/environment-based auth
//   - Assigns Azure RBAC roles for deployment
//
// NO LONG-LIVED SECRETS ARE CREATED - Uses OIDC tokens only!
//
// Usage:
//   az deployment sub create \
//     --name github-oidc-setup \
//     --location eastus \
//     --template-file github-oidc.bicep \
//     --parameters environment=dev githubRepo=htt-brands/control-tower
// =============================================================================

// -----------------------------------------------------------------------------
// Parameters
// -----------------------------------------------------------------------------
@description('Environment name (dev, staging, production)')
@allowed([
  'dev'
  'development'
  'staging'
  'prod'
  'production'
])
param environment string = 'dev'

@description('GitHub repository in format: owner/repo')
param githubRepo string

@description('Azure AD Tenant ID (auto-detected if not provided)')
param azureTenantId string = tenant().tenantId

@description('Resource group name for role assignments')
param resourceGroupName string

@description('Resource group location')
param location string = resourceGroup().location

@description('Tags to apply to resources')
param tags object = {
  Application: 'Azure Governance Platform'
  ManagedBy: 'Bicep'
  Purpose: 'GitHub Actions OIDC'
}

// -----------------------------------------------------------------------------
// Variables
// -----------------------------------------------------------------------------
var normalizedEnvironment = environment == 'development' ? 'dev' : environment == 'production' ? 'prod' : environment

// NOTE: appRegistrationName is intentionally preserved as 'azure-governance-platform-oidc-*'
// after the 2026-04-30 Control Tower repo rename. Renaming would orphan the
// already-deployed Entra app registration 'azure-governance-platform-oidc-dev' along
// with its 14 federated identity credentials (10 legacy 'azure-governance-platform'
// subjects + 4 new 'control-tower' subjects added during the cutover). Leave as-is
// until a separate, planned migration with explicit FIC re-creation.
var appRegistrationName = 'azure-governance-platform-oidc-${normalizedEnvironment}'
// GitHub OIDC issuer
var githubOidcIssuer = 'https://token.actions.githubusercontent.com'

// Federated credential configurations
// -----------------------------------------------------------------------------
// Azure AD App Registration
// -----------------------------------------------------------------------------
// Note: Microsoft.Graph resources require Microsoft Graph Bicep extension
// For now, we document the manual steps or use deployment scripts

// -----------------------------------------------------------------------------
// Deployment Script for OIDC Setup
// Uses Azure CLI to create App Registration and Federated Credentials
// -----------------------------------------------------------------------------
resource oidcSetupScript 'Microsoft.Resources/deploymentScripts@2023-08-01' = {
  name: 'oidc-setup-${normalizedEnvironment}'
  location: location
  kind: 'AzureCLI'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${deploymentIdentity.id}': {}
    }
  }
  properties: {
    azCliVersion: '2.60.0'
    timeout: 'PT30M'
    retentionInterval: 'PT1H'
    cleanupPreference: 'OnSuccess'
    arguments: '\'${appRegistrationName}\' \'${githubRepo}\' \'${azureTenantId}\' \'${resourceGroup().id}\' \'${normalizedEnvironment}\''
    scriptContent: '''
#!/bin/bash
set -e

APP_NAME="$1"
GITHUB_REPO="$2"
TENANT_ID="$3"
RESOURCE_GROUP_ID="$4"
ENVIRONMENT="$5"

echo "Setting up OIDC for: $APP_NAME"
echo "GitHub Repo: $GITHUB_REPO"

# Login with managed identity
az login --identity

# Create or get App Registration
echo "Creating App Registration..."
APP_ID=$(az ad app list --display-name "$APP_NAME" --query "[0].appId" -o tsv 2>/dev/null || echo "")

if [ -z "$APP_ID" ]; then
    echo "Creating new app registration..."
    APP_CREATE_OUTPUT=$(az ad app create --display-name "$APP_NAME" --sign-in-audience AzureADMyOrg --query "{appId: appId, id: id}" -o json)
    APP_ID=$(echo "$APP_CREATE_OUTPUT" | jq -r '.appId')
    APP_OBJECT_ID=$(echo "$APP_CREATE_OUTPUT" | jq -r '.id')
    echo "Created App ID: $APP_ID"
else
    echo "App already exists: $APP_ID"
    APP_OBJECT_ID=$(az ad app show --id "$APP_ID" --query "id" -o tsv)
fi

# Create or get Service Principal
echo "Creating Service Principal..."
SP_ID=$(az ad sp list --filter "appId eq '$APP_ID'" --query "[0].id" -o tsv 2>/dev/null || echo "")

if [ -z "$SP_ID" ]; then
    SP_ID=$(az ad sp create --id "$APP_ID" --query "id" -o tsv)
    echo "Created Service Principal: $SP_ID"
else
    echo "Service Principal already exists: $SP_ID"
fi

# Create Federated Credentials
echo "Creating Federated Credentials..."

CREDENTIALS=(
    "main-branch:repo:${GITHUB_REPO}:ref:refs/heads/main"
    "dev-branch:repo:${GITHUB_REPO}:ref:refs/heads/dev"
    "tag-deploy:repo:${GITHUB_REPO}:ref:refs/tags/v*"
    "environment-production:repo:${GITHUB_REPO}:environment:production"
    "environment-staging:repo:${GITHUB_REPO}:environment:staging"
    "environment-development:repo:${GITHUB_REPO}:environment:development"
    "pull-request:repo:${GITHUB_REPO}:pull_request"
)

for cred in "${CREDENTIALS[@]}"; do
    IFS=':' read -r CRED_NAME CRED_TYPE CRED_REPO CRED_CLAIM CRED_VALUE <<< "$cred"
    
    # Check if exists
    EXISTING=$(az ad app federated-credential list --id "$APP_ID" --query "[?name=='$CRED_NAME'].name" -o tsv 2>/dev/null || echo "")
    
    if [ -n "$EXISTING" ]; then
        echo "  Credential exists: $CRED_NAME"
        continue
    fi
    
    if [ "$CRED_CLAIM" == "pull_request" ]; then
        SUBJECT="${CRED_TYPE}:${CRED_REPO}:${CRED_CLAIM}"
    else
        SUBJECT="${CRED_TYPE}:${CRED_REPO}:${CRED_CLAIM}:${CRED_VALUE}"
    fi
    
    PARAMS=$(cat <<EOF
{
    "name": "${CRED_NAME}",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "${SUBJECT}",
    "description": "GitHub Actions ${CRED_NAME} authentication",
    "audiences": ["api://AzureADTokenExchange"]
}
EOF
)
    
    az ad app federated-credential create --id "$APP_ID" --parameters "$PARAMS" --output none 2>/dev/null || true
    echo "  Created: $CRED_NAME"
done

# Assign RBAC Roles
echo "Assigning RBAC Roles..."
ROLES=("Website Contributor" "Web Plan Contributor")

if [ "$ENVIRONMENT" == "prod" ] || [ "$ENVIRONMENT" == "production" ]; then
    ROLES+=("Monitoring Contributor" "Key Vault Secrets User")
fi

for ROLE in "${ROLES[@]}"; do
    # Check if already assigned
    EXISTING=$(az role assignment list --assignee "$APP_ID" --role "$ROLE" --scope "$RESOURCE_GROUP_ID" --query "[0].id" -o tsv 2>/dev/null || echo "")
    
    if [ -n "$EXISTING" ]; then
        echo "  Role assigned: $ROLE"
        continue
    fi
    
    az role assignment create --role "$ROLE" --assignee "$APP_ID" --scope "$RESOURCE_GROUP_ID" --output none || {
        az role assignment create --role "$ROLE" --assignee-object-id "$SP_ID" --assignee-principal-type ServicePrincipal --scope "$RESOURCE_GROUP_ID" --output none
    }
    echo "  Assigned: $ROLE"
done

# Output results
OUTPUT=$(cat <<EOF
{
    "appRegistration": {
        "name": "$APP_NAME",
        "clientId": "$APP_ID",
        "objectId": "$APP_OBJECT_ID"
    },
    "servicePrincipal": {
        "id": "$SP_ID"
    },
    "githubSecrets": {
        "AZURE_CLIENT_ID": "$APP_ID",
        "AZURE_TENANT_ID": "$TENANT_ID",
        "AZURE_SUBSCRIPTION_ID": "$(az account show --query id -o tsv)",
        "AZURE_RESOURCE_GROUP": "$(echo $RESOURCE_GROUP_ID | cut -d'/' -f5)"
    }
}
EOF
)

echo "$OUTPUT" > "$AZ_SCRIPTS_OUTPUT_PATH"
echo "Setup complete!"
    '''
  }
}

// -----------------------------------------------------------------------------
// Managed Identity for Deployment Script
// Requires: Microsoft.Authorization/roleAssignments/write permission
// -----------------------------------------------------------------------------
resource deploymentIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-07-31-preview' = {
  name: 'id-oidc-setup-${normalizedEnvironment}'
  location: location
  tags: tags
}

// -----------------------------------------------------------------------------
// Role Assignment for Deployment Identity
// Grants permission to create App Registrations and assign roles
// -----------------------------------------------------------------------------
resource deploymentIdentityRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(subscription().id, resourceGroup().id, deploymentIdentity.name, 'Contributor')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b24988ac-6180-42a0-ab88-20f7382dd24c') // Contributor
    principalId: deploymentIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// -----------------------------------------------------------------------------
// Alternative: Manual Setup Documentation
// -----------------------------------------------------------------------------
resource oidcDocumentation 'Microsoft.Resources/deploymentScripts@2023-08-01' = {
  name: 'oidc-documentation'
  location: location
  kind: 'AzureCLI'
  properties: {
    azCliVersion: '2.60.0'
    timeout: 'PT5M'
    retentionInterval: 'PT1H'
    cleanupPreference: 'OnExpiration'
    scriptContent: '''
echo "OIDC Setup Documentation"
echo "========================="
echo ""
echo "If the automated script fails, follow these manual steps:"
echo ""
echo "1. Create App Registration:"
echo "   az ad app create --display-name '$APP_NAME' --sign-in-audience AzureADMyOrg"
echo ""
echo "2. Create Service Principal:"
echo "   az ad sp create --id <APP_ID>"
echo ""
echo "3. Add Federated Credentials:"
echo "   az ad app federated-credential create --id <APP_ID> --parameters '{...}'"
echo ""
echo "4. Assign Roles:"
echo "   az role assignment create --role 'Website Contributor' --assignee <APP_ID> --scope <RESOURCE_GROUP_ID>"
echo ""
    '''
  }
}

// -----------------------------------------------------------------------------
// Outputs
// -----------------------------------------------------------------------------
output oidcSetupScriptOutput object = oidcSetupScript.properties.outputs

output manualSetupInstructions object = {
  step1: 'Create Azure AD App Registration: az ad app create --display-name "${appRegistrationName}"'
  step2: 'Create Service Principal: az ad sp create --id <APP_ID>'
  step3: 'Add federated credentials for GitHub OIDC'
  step4: 'Assign RBAC roles: Website Contributor, Web Plan Contributor'
  step5: 'Configure GitHub secrets: AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID'
  appRegistrationName: appRegistrationName
  githubRepo: githubRepo
  githubOidcIssuer: githubOidcIssuer
}

output githubSecrets object = {
  AZURE_CLIENT_ID: 'From deployment output'
  AZURE_TENANT_ID: azureTenantId
  AZURE_SUBSCRIPTION_ID: subscription().subscriptionId
  AZURE_RESOURCE_GROUP: resourceGroupName
  note: 'Run the setup-oidc.sh script or check the deployment script output for actual values'
}

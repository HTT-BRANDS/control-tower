/*
  User-Assigned Managed Identity (UAMI) Module
  Phase C: Zero-secrets authentication for HTT Control Tower

  Creates:
  - User-Assigned Managed Identity for zero-secrets auth
  - Federated Identity Credential on the multi-tenant app
  - Role assignments for Key Vault and App Service

  Architecture:
    UAMI (User-Assigned Managed Identity)
      ↓ (federated token)
    Federated Identity Credential on Multi-Tenant App
      ↓ (token exchange)
    ClientAssertionCredential
      ↓ (access token)
    Microsoft Graph API

  Usage:
    module uami './modules/uami.bicep' = {
      name: 'uamiDeployment'
      params: {
        uamiName: 'mi-control-tower'
        location: resourceGroup().location
        multiTenantAppObjectId: '<app-object-id>'
        federatedIdentityCredentialName: 'github-actions-federation'
        githubOrganization: 'htt-brands'
        githubRepository: 'control-tower'
        keyVaultName: 'kv-gov-prod-001'
      }
    }
*/

@description('Name of the User-Assigned Managed Identity')
param uamiName string = 'mi-control-tower'

@description('Azure region for resources')
param location string = resourceGroup().location

@description('Name for the Federated Identity Credential')
param federatedIdentityCredentialName string = 'github-actions-federation'

@description('GitHub organization name')
param githubOrganization string

@description('GitHub repository name')
param githubRepository string

@description('GitHub branch or environment for OIDC federation')
@allowed(['refs/heads/main', 'refs/heads/staging', 'environment:production', 'environment:staging'])
param githubRef string = 'refs/heads/main'

@description('Name of the Key Vault for role assignment')
param keyVaultName string

@description('Array of additional role assignments for the UAMI')
param additionalRoleAssignments array = []

@description('Tags to apply to resources')
param tags object = {
  Environment: 'production'
  Project: 'control-tower'
  Phase: 'C'
  ManagedBy: 'bicep'
}

@description('Enable diagnostic settings')
param enableDiagnostics bool = true

@description('Log Analytics workspace ID for diagnostics')
param logAnalyticsWorkspaceId string = ''

// ============================================================================
// Notes on Federated Identity Credential
// ============================================================================
// The Federated Identity Credential (FIC) is configured on the multi-tenant
// App Registration via Azure CLI, not in this Bicep template. This is because
// FICs are child resources of the App Registration (Microsoft.Graph/applications)
// which is outside the ARM/Bicep resource provider namespace.
//
// To create the FIC after deploying this UAMI, run:
//   APP_OBJECT_ID=$(az ad app show --id <multi-tenant-app-id> --query "id" -o tsv)
//   az ad app federated-credential create \
//       --id "$APP_OBJECT_ID" \
//       --parameters '{
//           "name": "github-actions-federation",
//           "issuer": "https://token.actions.githubusercontent.com",
//           "subject": "repo:<org>/<repo>:ref:refs/heads/main",
//           "audiences": ["api://AzureADTokenExchange"]
//       }'
// ============================================================================

// ============================================================================
// User-Assigned Managed Identity
// ============================================================================

resource uami 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: uamiName
  location: location
  tags: tags
}

// ============================================================================
// Federated Identity Credential (on the multi-tenant app)
// ============================================================================

// Note: Federated Identity Credentials are created on the App Registration,
// not on the UAMI. The UAMI provides the identity, the FIC on the app
// allows that identity to authenticate to the app.

resource federatedIdentityCredential 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  name: federatedIdentityCredentialName
  parent: uami
  properties: {
    issuer: 'https://token.actions.githubusercontent.com'
    subject: 'repo:${githubOrganization}/${githubRepository}:${githubRef}'
    audiences: [
      'api://AzureADTokenExchange'
    ]
  }
}

// ============================================================================
// Role Assignments
// ============================================================================

// Key Vault Secrets User - allows UAMI to read secrets from Key Vault
resource keyVaultSecretsUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, uami.id, '4633458b-17de-408a-b874-0445caeb07de')
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445caeb07de') // Key Vault Secrets User
    principalId: uami.properties.principalId
    principalType: 'ServicePrincipal'
    description: 'Allow UAMI to read secrets from Key Vault for Phase C zero-secrets auth'
  }
}

// Key Vault Reader - allows UAMI to list and read Key Vault metadata
resource keyVaultReaderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, uami.id, '21090545-7ca7-4776-b22c-e363652d74d2')
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '21090545-7ca7-4776-b22c-e363652d74d2') // Key Vault Reader
    principalId: uami.properties.principalId
    principalType: 'ServicePrincipal'
    description: 'Allow UAMI to read Key Vault metadata'
  }
}

// Additional custom role assignments
resource additionalRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for role in additionalRoleAssignments: {
    name: guid(role.scopeResourceId, uami.id, role.roleDefinitionId)
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', role.roleDefinitionId)
      principalId: uami.properties.principalId
      principalType: 'ServicePrincipal'
      description: role.description
    }
  }
]

// ============================================================================
// Referenced Resources
// ============================================================================

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

// ============================================================================
// Diagnostics (optional)
// ============================================================================

resource uamiDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (enableDiagnostics && !empty(logAnalyticsWorkspaceId)) {
  name: '${uamiName}-diagnostics'
  scope: uami
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        category: 'AuditEvent'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

// ============================================================================
// Outputs
// ============================================================================

@description('Client ID of the User-Assigned Managed Identity')
output uamiClientId string = uami.properties.clientId

@description('Principal ID (Object ID) of the UAMI')
output uamiPrincipalId string = uami.properties.principalId

@description('Resource ID of the UAMI')
output uamiResourceId string = uami.id

@description('Name of the UAMI')
output uamiName string = uami.name

@description('Tenant ID of the UAMI')
output uamiTenantId string = uami.properties.tenantId

@description('Federated Identity Credential name')
output federatedIdentityCredentialName string = federatedIdentityCredential.name

@description('Federated Identity Credential issuer')
output federatedIdentityCredentialIssuer string = federatedIdentityCredential.properties.issuer

@description('Federated Identity Credential subject')
output federatedIdentityCredentialSubject string = federatedIdentityCredential.properties.subject

@description('Full configuration for App Service integration')
output appServiceIdentityConfig object = {
  type: 'UserAssigned'
  userAssignedIdentities: {
    '${uami.id}': {}
  }
}

@description('Environment variables for application configuration')
output appEnvironmentVariables object = {
  UAMI_CLIENT_ID: uami.properties.clientId
  UAMI_PRINCIPAL_ID: uami.properties.principalId
  FEDERATED_IDENTITY_CREDENTIAL_ID: federatedIdentityCredential.name
  USE_UAMI_AUTH: 'true'
}

@description('GitHub Actions OIDC configuration')
output githubActionsConfig object = {
  AZURE_CLIENT_ID: uami.properties.clientId
  AZURE_TENANT_ID: uami.properties.tenantId
  #disable-next-line no-hardcoded-env-urls
  AZURE_SUBSCRIPTION_ID: subscription().subscriptionId
}

@description('Summary of Phase C configuration')
output phaseCSummary object = {
  uami: {
    name: uami.name
    clientId: uami.properties.clientId
    principalId: uami.properties.principalId
  }
  federation: {
    credentialName: federatedIdentityCredential.name
    issuer: federatedIdentityCredential.properties.issuer
    subject: federatedIdentityCredential.properties.subject
  }
  roleAssignments: [
    {
      role: 'Key Vault Secrets User'
      scope: keyVault.name
    }
    {
      role: 'Key Vault Reader'
      scope: keyVault.name
    }
  ]
}

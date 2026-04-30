// =============================================================================
// Azure Governance Platform - Extended Infrastructure
// Deploys Container Instances, Logic Apps, Workbooks, and Policies
// =============================================================================

targetScope = 'subscription'

// -----------------------------------------------------------------------------
// Parameters
// -----------------------------------------------------------------------------
@description('Environment name')
param environment string = 'production'

@description('Primary location')
param location string = deployment().location

@description('Resource group name for governance resources')
param resourceGroupName string = 'rg-governance-${environment}'

@description('Unique suffix for naming')
param resourceSuffix string = uniqueString(subscription().id, deployment().name)

@description('Enable Container Instances for batch jobs')
param enableContainerInstances bool = true

@description('Enable Logic Apps for automation')
param enableLogicApps bool = true

@description('Enable Monitor Workbooks')
param enableWorkbooks bool = true

@description('Enable Azure Policy definitions')
param enablePolicies bool = true

@description('Log Analytics workspace ID')
param logAnalyticsWorkspaceId string = ''

@description('Storage account name')
param storageAccountName string = ''

@description('Microsoft Teams webhook URL for notifications')
@secure()
param teamsWebhookUrl string = ''

@description('Notification email address')
param notificationEmail string = ''

@description('Tags to apply')
param tags object = {
  Application: 'Azure Governance Platform'
  Environment: environment
  ManagedBy: 'Bicep'
}

// -----------------------------------------------------------------------------
// Resource Group
// -----------------------------------------------------------------------------
resource resourceGroup 'Microsoft.Resources/resourceGroups@2023-07-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

// -----------------------------------------------------------------------------
// Logic Apps for Automation
// -----------------------------------------------------------------------------
module logicApp './modules/logic-apps.bicep' = if (enableLogicApps) {
  name: 'logicAppDeploy'
  scope: resourceGroup
  params: {
    name: 'logic-governance-${environment}-${take(resourceSuffix, 8)}'
    location: location
    sku: environment == 'production' ? 'Standard' : 'Free'
    tags: tags
    enableManagedIdentity: true
    logAnalyticsWorkspaceId: logAnalyticsWorkspaceId
    storageAccountName: storageAccountName
    enableTeamsIntegration: !empty(teamsWebhookUrl)
    teamsWebhookUrl: teamsWebhookUrl
    enableCostOptimization: true
    notificationEmail: notificationEmail
    monitoredResourceGroups: [resourceGroupName]
    costAlertThreshold: environment == 'production' ? 1000 : 100
  }
}

// -----------------------------------------------------------------------------
// Container Instances - Sample Jobs
// -----------------------------------------------------------------------------

// Migration job container (created but not started automatically)
module migrationContainer './modules/container-instances.bicep' = if (enableContainerInstances) {
  name: 'migrationContainerDeploy'
  scope: resourceGroup
  params: {
    name: 'aci-migration-${environment}-${take(resourceSuffix, 8)}'
    location: location
    containerImage: 'ghcr.io/htt-brands/control-tower-migrations:latest'
    jobType: 'migration'
    cpuCores: 2
    memoryGB: 4
    restartPolicy: 'Never'
    enableManagedIdentity: true
    storageAccountName: storageAccountName
    fileShareName: 'migration-data'
    logAnalyticsWorkspaceId: logAnalyticsWorkspaceId
    tags: union(tags, { JobType: 'migration' })
  }
}

// Data processing container
module processingContainer './modules/container-instances.bicep' = if (enableContainerInstances) {
  name: 'processingContainerDeploy'
  scope: resourceGroup
  params: {
    name: 'aci-processing-${environment}-${take(resourceSuffix, 8)}'
    location: location
    containerImage: 'ghcr.io/htt-brands/control-tower-processor:latest'
    jobType: 'processing'
    cpuCores: 4
    memoryGB: 8
    restartPolicy: 'Never'
    enableManagedIdentity: true
    storageAccountName: storageAccountName
    fileShareName: 'processing-data'
    logAnalyticsWorkspaceId: logAnalyticsWorkspaceId
    tags: union(tags, { JobType: 'processing' })
  }
}

// Cleanup job container
module cleanupContainer './modules/container-instances.bicep' = if (enableContainerInstances) {
  name: 'cleanupContainerDeploy'
  scope: resourceGroup
  params: {
    name: 'aci-cleanup-${environment}-${take(resourceSuffix, 8)}'
    location: location
    containerImage: 'mcr.microsoft.com/azure-cli:latest'
    jobType: 'cleanup'
    cpuCores: 1
    memoryGB: 2
    restartPolicy: 'Never'
    enableManagedIdentity: true
    logAnalyticsWorkspaceId: logAnalyticsWorkspaceId
    tags: union(tags, { JobType: 'cleanup' })
  }
}

// -----------------------------------------------------------------------------
// Azure Monitor Workbooks
// -----------------------------------------------------------------------------
module governanceWorkbook './monitoring/workbooks/workbook.bicep' = if (enableWorkbooks) {
  name: 'governanceWorkbookDeploy'
  scope: resourceGroup
  params: {
    name: 'workbook-governance-${environment}'
    displayName: 'Azure Governance Platform Dashboard'
    location: location
    serializedData: loadJsonContent('monitoring/workbooks/governance-dashboard.json')
    sourceId: logAnalyticsWorkspaceId
    tags: tags
  }
}

// -----------------------------------------------------------------------------
// Azure Policy Definitions
// -----------------------------------------------------------------------------

// Required tags policy
module requireTagsPolicy './modules/policy-definition.bicep' = if (enablePolicies) {
  name: 'requireTagsPolicyDeploy'
  params: {
    name: 'governance-require-tags-${environment}'
    displayName: 'Governance: Require Mandatory Tags'
    description: 'Ensures all resources have required governance tags'
    category: 'Governance'
    policyRule: loadJsonContent('policies/require-tags-policy.json').properties.policyRule
    parameters: loadJsonContent('policies/require-tags-policy.json').properties.parameters
  }
}

// Encryption enforcement policy
module encryptionPolicy './modules/policy-definition.bicep' = if (enablePolicies) {
  name: 'encryptionPolicyDeploy'
  params: {
    name: 'governance-enforce-encryption-${environment}'
    displayName: 'Governance: Enforce Encryption'
    description: 'Ensures encryption at rest and in transit for all resources'
    category: 'Security'
    policyRule: loadJsonContent('policies/enforce-encryption-policy.json').properties.policyRule
    parameters: loadJsonContent('policies/enforce-encryption-policy.json').properties.parameters
  }
}

// Public storage prevention policy
module publicStoragePolicy './modules/policy-definition.bicep' = if (enablePolicies) {
  name: 'publicStoragePolicyDeploy'
  params: {
    name: 'governance-prevent-public-storage-${environment}'
    displayName: 'Governance: Prevent Public Storage Access'
    description: 'Prevents storage accounts with public access configuration'
    category: 'Security'
    policyRule: loadJsonContent('policies/prevent-public-storage-policy.json').properties.policyRule
    parameters: loadJsonContent('policies/prevent-public-storage-policy.json').properties.parameters
  }
}

// Compliance audit policy
module complianceAuditPolicy './modules/policy-definition.bicep' = if (enablePolicies) {
  name: 'complianceAuditPolicyDeploy'
  params: {
    name: 'governance-compliance-audit-${environment}'
    displayName: 'Governance: Compliance Audit'
    description: 'Audits resources for compliance with organizational standards'
    category: 'Governance'
    policyRule: loadJsonContent('policies/compliance-audit-policy.json').properties.policyRule
    parameters: loadJsonContent('policies/compliance-audit-policy.json').properties.parameters
  }
}

// Policy Assignments (at subscription level)
module requireTagsAssignment './modules/policy-assignment.bicep' = if (enablePolicies) {
  name: 'requireTagsAssignment'
  params: {
    name: 'require-tags-assignment'
    displayName: 'Require Mandatory Tags Assignment'
    policyDefinitionId: requireTagsPolicy!.outputs.policyId
    parameters: {
      effect: {
        value: environment == 'production' ? 'Deny' : 'Audit'
      }
    }
    enforcementMode: 'Default'
  }
}

module encryptionAssignment './modules/policy-assignment.bicep' = if (enablePolicies) {
  name: 'encryptionAssignment'
  params: {
    name: 'enforce-encryption-assignment'
    displayName: 'Enforce Encryption Assignment'
    policyDefinitionId: encryptionPolicy!.outputs.policyId
    parameters: {
      effect: {
        value: 'Deny'
      }
    }
    enforcementMode: 'Default'
  }
}

module publicStorageAssignment './modules/policy-assignment.bicep' = if (enablePolicies) {
  name: 'publicStorageAssignment'
  params: {
    name: 'prevent-public-storage-assignment'
    displayName: 'Prevent Public Storage Access Assignment'
    policyDefinitionId: publicStoragePolicy!.outputs.policyId
    parameters: {
      effect: {
        value: 'Deny'
      }
    }
    enforcementMode: 'Default'
  }
}

module complianceAuditAssignment './modules/policy-assignment.bicep' = if (enablePolicies) {
  name: 'complianceAuditAssignment'
  params: {
    name: 'compliance-audit-assignment'
    displayName: 'Compliance Audit Assignment'
    policyDefinitionId: complianceAuditPolicy!.outputs.policyId
    parameters: {
      effect: {
        value: 'AuditIfNotExists'
      }
    }
    enforcementMode: 'Default'
  }
}

// -----------------------------------------------------------------------------
// Outputs
// -----------------------------------------------------------------------------
output resourceGroupName string = resourceGroup.name
output resourceGroupId string = resourceGroup.id

// Logic Apps outputs
output logicAppId string = enableLogicApps ? logicApp!.outputs.logicAppId : ''
output logicAppName string = enableLogicApps ? logicApp!.outputs.logicAppName : ''
output logicAppPrincipalId string = enableLogicApps ? logicApp!.outputs.principalId : ''

// Container instances outputs
output migrationContainerId string = enableContainerInstances ? migrationContainer!.outputs.containerGroupId : ''
output processingContainerId string = enableContainerInstances ? processingContainer!.outputs.containerGroupId : ''
output cleanupContainerId string = enableContainerInstances ? cleanupContainer!.outputs.containerGroupId : ''

// Workbook outputs
output workbookId string = enableWorkbooks ? governanceWorkbook!.outputs.workbookId : ''
output workbookName string = enableWorkbooks ? governanceWorkbook!.outputs.workbookName : ''

// Policy outputs
output requireTagsPolicyId string = enablePolicies ? requireTagsPolicy!.outputs.policyId : ''
output encryptionPolicyId string = enablePolicies ? encryptionPolicy!.outputs.policyId : ''
output publicStoragePolicyId string = enablePolicies ? publicStoragePolicy!.outputs.policyId : ''
output complianceAuditPolicyId string = enablePolicies ? complianceAuditPolicy!.outputs.policyId : ''

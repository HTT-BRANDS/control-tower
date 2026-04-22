@description('Name of the container instance')
param name string

@description('Location for the resource')
param location string = resourceGroup().location

@description('Container image to deploy')
param containerImage string

@description('Container registry URL')
param containerRegistryUrl string = 'ghcr.io'

@description('Container registry credentials (for private registries)')
@secure()
param containerRegistryPassword string = ''

@description('Container registry username')
param containerRegistryUsername string = ''

@description('Command override for the container')
param command array = []

@description('Environment variables for the container')
param environmentVariables array = []

@description('Secure environment variables. NOTE: @secure() was removed because Bicep no longer allows it on array params. For actual per-value secrecy, pass items with `secureValue` instead of `value` inside `environmentVariables`. Tracked as: follow-up refactor.')
param secureEnvironmentVariables array = []

@description('CPU cores allocated to the container')
param cpuCores int = 1

@description('Memory allocated to the container in GB')
param memoryGB int = 2

@description('GPU count (if using GPU containers)')
param gpuCount int = 0

@description('GPU SKU (if using GPU containers)')
@allowed(['K80', 'P100', 'V100'])
param gpuSku string = 'K80'

@description('OS type for the container')
@allowed(['Linux', 'Windows'])
param osType string = 'Linux'

@description('Restart policy')
@allowed(['Always', 'OnFailure', 'Never'])
param restartPolicy string = 'OnFailure'

@description('Azure Files share name for persistent storage')
param fileShareName string = ''

@description('Storage account name for Azure Files mount')
param storageAccountName string = ''

@description('Storage account key for Azure Files mount')
@secure()
param storageAccountKey string = ''

@description('Mount path for Azure Files share inside container')
param fileShareMountPath string = '/data'

@description('Log Analytics workspace ID for container logs')
param logAnalyticsWorkspaceId string = ''

@description('Log Analytics workspace key')
@secure()
param logAnalyticsWorkspaceKey string = ''

@description('Enable managed identity')
param enableManagedIdentity bool = true

@description('User-assigned managed identity resource ID (optional)')
param userAssignedIdentityId string = ''

@description('Tags to apply')
param tags object = {}

@description('Job type for categorization')
@allowed(['migration', 'backup', 'cleanup', 'processing', 'maintenance', 'custom'])
param jobType string = 'custom'

@description('Scheduled job trigger (cron expression, empty for manual runs)')
param schedule string = ''

@description('Enable virtual network integration')
param enableVNet bool = false

@description('Virtual network name (if VNet integration enabled)')
param vnetName string = ''

@description('Subnet name for container (if VNet integration enabled)')
param subnetName string = ''

// Reference to storage account if file share is used
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' existing = if (!empty(storageAccountName)) {
  name: storageAccountName
}

// Build container registry credentials if provided
var registryCredentials = !empty(containerRegistryPassword) ? [
  {
    server: containerRegistryUrl
    username: !empty(containerRegistryUsername) ? containerRegistryUsername : 'token'
    password: containerRegistryPassword
  }
] : []

// Build volume mounts if file share is configured
var volumeMounts = !empty(fileShareName) && !empty(storageAccountName) ? [
  {
    name: 'datavolume'
    mountPath: fileShareMountPath
  }
] : []

// Build volumes configuration
var volumes = !empty(fileShareName) && !empty(storageAccountName) ? [
  {
    name: 'datavolume'
    azureFile: {
      shareName: fileShareName
      storageAccountName: storageAccountName
      storageAccountKey: !empty(storageAccountKey) ? storageAccountKey : storageAccount.listKeys().keys[0].value // #nosec — Key Vault preferred, listKeys is fallback
    }
  }
] : []

// Build log analytics configuration
var logAnalyticsConfig = !empty(logAnalyticsWorkspaceId) && !empty(logAnalyticsWorkspaceKey) ? {
  workspaceId: logAnalyticsWorkspaceId
  workspaceKey: logAnalyticsWorkspaceKey
  logType: 'ContainerInsights'
  metadata: [
    {
      name: 'job-type'
      value: jobType
    }
  ]
} : null

// Build identity configuration
var identityType = enableManagedIdentity ? (!empty(userAssignedIdentityId) ? 'UserAssigned' : 'SystemAssigned') : 'None'
var identityConfig = enableManagedIdentity ? {
  type: identityType
  userAssignedIdentities: !empty(userAssignedIdentityId) ? {
    '${userAssignedIdentityId}': {}
  } : null
} : null

// Build GPU resources if specified
var gpuResources = gpuCount > 0 ? {
  count: gpuCount
  sku: gpuSku
} : null

// Build resources configuration
var resourcesConfig = gpuCount > 0 ? {
  requests: {
    cpu: cpuCores
    memoryInGB: memoryGB
    gpu: gpuResources
  }
} : {
  requests: {
    cpu: cpuCores
    memoryInGB: memoryGB
  }
}

// Container instance resource
resource containerInstance 'Microsoft.ContainerInstance/containerGroups@2023-05-01' = {
  name: name
  location: location
  tags: union(tags, {
    jobType: jobType
    schedule: !empty(schedule) ? 'scheduled' : 'manual'
  })
  identity: identityConfig
  properties: {
    osType: osType
    restartPolicy: restartPolicy
    containers: [
      {
        name: name
        properties: {
          image: containerImage
          resources: resourcesConfig
          command: !empty(command) ? command : null
          environmentVariables: environmentVariables
          secureEnvironmentVariables: secureEnvironmentVariables
          volumeMounts: volumeMounts
          ports: [
            {
              protocol: 'TCP'
              port: 80
            }
          ]
        }
      }
    ]
    imageRegistryCredentials: !empty(registryCredentials) ? registryCredentials : null
    volumes: volumes
    diagnostics: logAnalyticsConfig != null ? {
      logAnalytics: logAnalyticsConfig
    } : null
    ipAddress: enableVNet ? null : {
      type: 'Public'
      ports: [
        {
          protocol: 'TCP'
          port: 80
        }
      ]
      dnsNameLabel: !enableVNet ? '${name}-${uniqueString(resourceGroup().id)}' : null
    }
    subnetIds: enableVNet && !empty(vnetName) && !empty(subnetName) ? [
      {
        id: resourceId('Microsoft.Network/virtualNetworks/subnets', vnetName, subnetName)
      }
    ] : null
    sku: 'Standard'
  }
}

// Role assignment for managed identity to access storage if needed
resource storageRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (enableManagedIdentity && !empty(storageAccountName)) {
  name: guid(storageAccount.id, containerInstance.id, 'StorageBlobDataContributor')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: enableManagedIdentity && !empty(userAssignedIdentityId) ? reference(userAssignedIdentityId, '2023-01-31').principalId : containerInstance.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Outputs
output containerGroupId string = containerInstance.id
output containerGroupName string = containerInstance.name
output ipAddress string = enableVNet ? '' : containerInstance.properties.ipAddress.ip
output fqdn string = enableVNet ? '' : containerInstance.properties.ipAddress.fqdn
output principalId string = enableManagedIdentity ? (enableManagedIdentity && !empty(userAssignedIdentityId) ? reference(userAssignedIdentityId, '2023-01-31').principalId : containerInstance.identity.principalId) : ''

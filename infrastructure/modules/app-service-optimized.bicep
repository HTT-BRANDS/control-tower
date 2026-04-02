@description('Name of the App Service')
param name string

@description('Location for the resource')
param location string

@description('App Service Plan ID')
param appServicePlanId string

@description('Application Insights connection string')
param appInsightsConnectionString string = ''

@description('Storage account name for file mounts')
param storageAccountName string

@description('Key Vault name (optional)')
param keyVaultName string = ''

@description('SQL Server name (optional)')
param sqlServerName string = ''

@description('SQL Database name (optional)')
param sqlDatabaseName string = ''

@description('Enable Azure SQL')
param enableAzureSql bool = false

@description('Container image tag')
param containerImage string = 'latest'

@description('Azure Container Registry name (optional, for reference)')
param acrName string = ''

@description('Container registry URL for private registries like GHCR')
param containerRegistryUrl string = 'https://ghcr.io'

@description('Environment name')
param environment string

@description('Tags to apply')
param tags object = {}

@description('Python version (used when not deploying as container)')
param pythonVersion string = '3.11'

@description('Use container deployment instead of code deployment')
param useContainerDeployment bool = true

@description('Log Analytics workspace ID for diagnostics')
param logAnalyticsWorkspaceId string = ''

@description('Azure AD tenant ID for user authentication')
param azureAdTenantId string = ''

@description('Azure AD app registration client ID')
param azureAdClientId string = ''

@description('Azure AD app registration client secret')
@secure()
param azureAdClientSecret string = ''

@description('JWT signing secret key (min 32 chars)')
@secure()
param jwtSecretKey string = ''

@description('Comma-separated CORS origins')
param corsOrigins string = ''

@description('Comma-separated admin email addresses')
param adminEmails string = ''

@description('Redis URL for caching and token blacklist')
param redisUrl string = ''

@description('Storage account access key (passed securely via Key Vault). When empty, falls back to listKeys().') // #nosec — documentation only
@secure()
param storageAccessKey string = ''

// ============================================================================
// CLOUD-NATIVE OPTIMIZATION PARAMETERS
// ============================================================================

@description('Enable auto-scaling rules based on CPU and memory')
param enableAutoScaling bool = true

@description('Minimum instance count for auto-scaling')
param autoScaleMinInstances int = 1

@description('Maximum instance count for auto-scaling')
param autoScaleMaxInstances int = 5

@description('Default instance count')
param autoScaleDefaultInstances int = 2

@description('CPU threshold percentage for scaling up')
param scaleUpCpuThreshold int = 70

@description('Memory threshold percentage for scaling up')
param scaleUpMemoryThreshold int = 75

@description('CPU threshold percentage for scaling down')
param scaleDownCpuThreshold int = 30

@description('Enable deployment slots for blue-green deployments')
param enableDeploymentSlots bool = true

@description('Names of deployment slots to create (staging, preview, etc.)')
param deploymentSlotNames array = ['staging']

@description('Enable health check integration with detailed monitoring')
param enableHealthCheck bool = true

@description('Health check path')
param healthCheckPath string = '/health'

@description('Maximum ping failures before unhealthy')
param healthCheckMaxFailures int = 3

@description('Enable Application Insights Profiler for performance analysis')
param enableAppInsightsProfiler bool = true

@description('Enable Application Insights Snapshot Debugger')
param enableSnapshotDebugger bool = true

@description('Enable Azure Files for persistent storage with high durability')
param enableAzureFiles bool = true

@description('Azure Files share quota in GB')
param azureFilesQuotaGB int = 100

@description('Enable virtual network integration')
param enableVnetIntegration bool = false

@description('Virtual network subnet ID for integration')
param vnetSubnetId string = ''

@description('Enable private endpoints')
param enablePrivateEndpoint bool = false

@description('Enable zone redundancy for high availability')
param enableZoneRedundancy bool = false

@description('User-Assigned Managed Identity IDs')
param userAssignedIdentityIds array = []

@description('Enable easy auth (Authentication/Authorization)')
param enableEasyAuth bool = false

@description('Easy Auth token store enabled')
param easyAuthTokenStore bool = true

// Reference to storage account
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: storageAccountName
}

// Reference to Key Vault
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = if (!empty(keyVaultName)) {
  name: keyVaultName
}

// Use Key Vault-sourced key when available, fall back to listKeys() for backwards compatibility
var effectiveStorageKey = !empty(storageAccessKey) ? storageAccessKey : storageAccount.listKeys().keys[0].value // #nosec — Key Vault preferred, listKeys is fallback

// Determine kind based on deployment type
var appKind = useContainerDeployment ? 'app,linux,container' : 'app,linux'

// Determine linuxFxVersion based on deployment type
var linuxFxVersion = useContainerDeployment ? 'DOCKER|${containerImage}' : 'PYTHON|${pythonVersion}'

// ============================================================================
// AUTO-SCALING CONFIGURATION
// ============================================================================

resource autoScaleSettings 'Microsoft.Insights/autoscalesettings@2022-10-01' = if (enableAutoScaling) {
  name: '${name}-autoscale'
  location: location
  tags: tags
  properties: {
    name: '${name}-autoscale'
    targetResourceUri: appServicePlanId
    enabled: true
    profiles: [
      {
        name: 'Default Auto-Scale Profile'
        capacity: {
          minimum: string(autoScaleMinInstances)
          maximum: string(autoScaleMaxInstances)
          default: string(autoScaleDefaultInstances)
        }
        rules: [
          // Scale up on high CPU
          {
            metricTrigger: {
              metricName: 'CpuPercentage'
              metricResourceUri: appServicePlanId
              timeGrain: 'PT1M'
              statistic: 'Average'
              timeWindow: 'PT5M'
              timeAggregation: 'Average'
              operator: 'GreaterThan'
              threshold: scaleUpCpuThreshold
            }
            scaleAction: {
              direction: 'Increase'
              type: 'ChangeCount'
              value: '1'
              cooldown: 'PT5M'
            }
          }
          // Scale up on high memory
          {
            metricTrigger: {
              metricName: 'MemoryPercentage'
              metricResourceUri: appServicePlanId
              timeGrain: 'PT1M'
              statistic: 'Average'
              timeWindow: 'PT5M'
              timeAggregation: 'Average'
              operator: 'GreaterThan'
              threshold: scaleUpMemoryThreshold
            }
            scaleAction: {
              direction: 'Increase'
              type: 'ChangeCount'
              value: '1'
              cooldown: 'PT5M'
            }
          }
          // Scale down on low CPU
          {
            metricTrigger: {
              metricName: 'CpuPercentage'
              metricResourceUri: appServicePlanId
              timeGrain: 'PT1M'
              statistic: 'Average'
              timeWindow: 'PT10M'
              timeAggregation: 'Average'
              operator: 'LessThan'
              threshold: scaleDownCpuThreshold
            }
            scaleAction: {
              direction: 'Decrease'
              type: 'ChangeCount'
              value: '1'
              cooldown: 'PT10M'
            }
          }
        ]
      }
      // Night mode profile - reduced capacity during off-peak hours
      {
        name: 'Night Mode'
        capacity: {
          minimum: '1'
          maximum: string(autoScaleMaxInstances)
          default: '1'
        }
        recurrence: {
          frequency: 'Week'
          schedule: {
            timeZone: 'Pacific Standard Time'
            days: [
              'Monday'
              'Tuesday'
              'Wednesday'
              'Thursday'
              'Friday'
              'Saturday'
              'Sunday'
            ]
            hours: [0]
            minutes: [0]
          }
        }
      }
    ]
    notifications: []
  }
}

// ============================================================================
// MAIN APP SERVICE
// ============================================================================

// Determine identity type based on user-assigned identities
var identityType = !empty(userAssignedIdentityIds) ? 'SystemAssigned, UserAssigned' : 'SystemAssigned'
var identityConfig = !empty(userAssignedIdentityIds) ? {
  type: identityType
  userAssignedIdentities: reduce(userAssignedIdentityIds, {}, (cur, id) => union(cur, { '${id}': {} }))
} : {
  type: identityType
}

resource appService 'Microsoft.Web/sites@2023-12-01' = {
  name: name
  location: location
  tags: union(tags, {
    'azd-service-name': name
    'hidden-link: /app-insights-resource-id': appInsightsConnectionString
    'optimal-auto-scale': string(enableAutoScaling)
    'zone-redundant': string(enableZoneRedundancy)
  })
  kind: appKind
  identity: identityConfig
  properties: {
    serverFarmId: appServicePlanId
    enabled: true
    reserved: true
    httpsOnly: true
    clientAffinityEnabled: false
    clientCertEnabled: false
    hostNameSslStates: []
    siteConfig: {
      numberOfWorkers: 1
      linuxFxVersion: linuxFxVersion
      alwaysOn: true
      httpLoggingEnabled: true
      minTlsVersion: '1.2'
      scmMinTlsVersion: '1.2'
      ftpsState: 'Disabled'
      appCommandLine: useContainerDeployment ? '' : 'python -m uvicorn app.main:app --host 0.0.0.0 --port 8000'
      healthCheckPath: enableHealthCheck ? healthCheckPath : ''
      use32BitWorkerProcess: false
      webSocketsEnabled: false
      managedPipelineMode: 'Integrated'
      loadBalancing: 'LeastRequests'
      experiments: {
        rampUpRules: []
      }
      // Enhanced auto-heal rules
      autoHealEnabled: true
      autoHealRules: {
        actions: {
          actionType: 'Recycle'
          minProcessExecutionTime: '00:01:00'
        }
        triggers: {
          requests: {
            count: 100
            timeInterval: '00:05:00'
          }
          statusCodes: [
            {
              status: 500
              subStatus: 0
              win32Status: 0
              count: 10
              timeInterval: '00:05:00'
            }
            {
              status: 502
              subStatus: 0
              win32Status: 0
              count: 10
              timeInterval: '00:05:00'
            }
            {
              status: 503
              subStatus: 0
              win32Status: 0
              count: 5
              timeInterval: '00:05:00'
            }
          ]
          slowRequests: {
            timeTaken: '00:01:00'
            count: 10
            timeInterval: '00:05:00'
          }
          memoryRules: {
            isEnabled: true
            trigger: 'Above'
            value: 85
          }
        }
      }
      // App Insights Profiler settings
      appSettings: union([
        {
          name: 'ENVIRONMENT'
          value: environment
        }
        {
          name: 'DEBUG'
          value: 'false'
        }
        {
          name: 'LOG_LEVEL'
          value: 'INFO'
        }
        {
          name: 'HOST'
          value: '0.0.0.0'
        }
        {
          name: 'PORT'
          value: '8000'
        }
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: useContainerDeployment ? 'false' : 'true'
        }
        {
          name: 'DOCKER_REGISTRY_SERVER_URL'
          value: useContainerDeployment ? containerRegistryUrl : ''
        }
        {
          name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE'
          value: enableAzureFiles ? 'true' : 'false'
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsightsConnectionString
        }
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: empty(appInsightsConnectionString) ? '' : split(appInsightsConnectionString, ';')[0]
        }
        // Application Insights Profiler
        {
          name: 'APPINSIGHTS_PROFILERFEATURE_VERSION'
          value: enableAppInsightsProfiler ? '1.0.0' : ''
        }
        {
          name: 'DiagnosticServices_EXTENSION_VERSION'
          value: enableAppInsightsProfiler ? '~3' : ''
        }
        // Snapshot Debugger
        {
          name: 'SnapshotDebugger_EXTENSION_VERSION'
          value: enableSnapshotDebugger ? 'latest' : ''
        }
        // Health check configuration
        {
          name: 'WEBSITE_HEALTHCHECK_MAXPINGFAILURES'
          value: string(healthCheckMaxFailures)
        }
        {
          name: 'CACHE_ENABLED'
          value: 'true'
        }
        {
          name: 'DATABASE_URL'
          value: enableAzureSql
            ? 'mssql+pyodbc://@${sqlServerName}.database.windows.net:1433/${sqlDatabaseName}?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&Authentication=ActiveDirectoryMsi'
            : 'sqlite:////home/data/governance.db'
        }
        {
          name: 'KEY_VAULT_URL'
          value: empty(keyVaultName) ? '' : 'https://${keyVaultName}.vault.azure.net'
        }
        {
          name: 'PYTHON_VERSION'
          value: pythonVersion
        }
        {
          name: 'AZURE_AD_TENANT_ID'
          value: azureAdTenantId
        }
        {
          name: 'AZURE_AD_CLIENT_ID'
          value: azureAdClientId
        }
        {
          name: 'AZURE_AD_CLIENT_SECRET'
          value: azureAdClientSecret
        }
        {
          name: 'AZURE_AD_ISSUER'
          value: empty(azureAdTenantId) ? '' : 'https://login.microsoftonline.com/${azureAdTenantId}/v2.0'
        }
        {
          name: 'AZURE_AD_TOKEN_ENDPOINT'
          value: empty(azureAdTenantId) ? '' : 'https://login.microsoftonline.com/${azureAdTenantId}/oauth2/v2.0/token'
        }
        {
          name: 'AZURE_AD_AUTHORIZATION_ENDPOINT'
          value: empty(azureAdTenantId) ? '' : 'https://login.microsoftonline.com/${azureAdTenantId}/oauth2/v2.0/authorize'
        }
        {
          name: 'AZURE_AD_JWKS_URI'
          value: empty(azureAdTenantId) ? '' : 'https://login.microsoftonline.com/${azureAdTenantId}/discovery/v2.0/keys'
        }
        {
          name: 'JWT_SECRET_KEY'
          value: !empty(keyVaultName) ? '@Microsoft.KeyVault(SecretUri=https://${keyVaultName}.vault.azure.net/secrets/jwt-secret-key)' : jwtSecretKey
        }
        {
          name: 'CORS_ORIGINS'
          value: empty(corsOrigins) ? 'https://${name}.azurewebsites.net' : corsOrigins
        }
        {
          name: 'ADMIN_EMAILS'
          value: adminEmails
        }
        {
          name: 'REDIS_URL'
          value: redisUrl
        }
        {
          name: 'USE_OIDC_FEDERATION'
          value: 'true'
        }
        {
          name: 'OIDC_ALLOW_DEV_FALLBACK'
          value: environment == 'development' ? 'true' : 'false'
        }
        // Performance tuning settings
        {
          name: 'WEBSITE_NODE_DEFAULT_VERSION'
          value: '18.x'
        }
        {
          name: 'PYTHON_ENABLE_GUNICORN_MULTIWORKERS'
          value: 'true'
        }
        {
          name: 'WEBSITE_HTTPLOGGING_RETENTION_DAYS'
          value: '7'
        }
        // X-Ray tracing for enhanced observability
        {
          name: 'XDT_MicrosoftApplicationInsights_Mode'
          value: 'default'
        }
      ], [])
      connectionStrings: []
      // Virtual network integration
      vnetName: enableVnetIntegration ? split(vnetSubnetId, '/')[8] : ''
      vnetRouteAllEnabled: enableVnetIntegration
    }
    // Virtual network integration
    virtualNetworkSubnetId: enableVnetIntegration ? vnetSubnetId : ''
  }
}

// ============================================================================
// DEPLOYMENT SLOTS (BLUE-GREEN DEPLOYMENT)
// ============================================================================

resource deploymentSlots 'Microsoft.Web/sites/slots@2023-12-01' = [for slotName in (enableDeploymentSlots ? deploymentSlotNames : []): {
  name: slotName
  parent: appService
  location: location
  tags: union(tags, {
    slot: slotName
    deploymentSlot: 'true'
  })
  kind: appKind
  identity: identityConfig
  properties: {
    serverFarmId: appServicePlanId
    enabled: true
    reserved: true
    httpsOnly: true
    clientAffinityEnabled: false
    siteConfig: {
      numberOfWorkers: 1
      linuxFxVersion: linuxFxVersion
      alwaysOn: true
      httpLoggingEnabled: true
      minTlsVersion: '1.2'
      scmMinTlsVersion: '1.2'
      ftpsState: 'Disabled'
      appCommandLine: useContainerDeployment ? '' : 'python -m uvicorn app.main:app --host 0.0.0.0 --port 8000'
      healthCheckPath: enableHealthCheck ? healthCheckPath : ''
      use32BitWorkerProcess: false
      autoHealEnabled: true
      appSettings: appService.properties.siteConfig.appSettings
    }
  }
}]

// ============================================================================
// AZURE FILES MOUNT CONFIGURATION
// ============================================================================

// Ensure file shares exist with proper quota
resource appDataShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-01-01' = if (enableAzureFiles) {
  name: '${storageAccountName}/default/appdata'
  properties: {
    shareQuota: azureFilesQuotaGB
    enabledProtocols: 'SMB'
  }
}

resource logsShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-01-01' = if (enableAzureFiles) {
  name: '${storageAccountName}/default/applogs'
  properties: {
    shareQuota: 10
    enabledProtocols: 'SMB'
  }
}

// Azure Files mount configuration
resource azureStorageConfig 'Microsoft.Web/sites/config@2023-12-01' = if (enableAzureFiles) {
  parent: appService
  name: 'azureStorageAccounts'
  properties: {
    dataVolume: {
      type: 'AzureFiles'
      shareName: 'appdata'
      mountPath: '/home/data'
      accountName: storageAccountName
      accessKey: effectiveStorageKey
    }
    logsVolume: {
      type: 'AzureFiles'
      shareName: 'applogs'
      mountPath: '/home/logs'
      accountName: storageAccountName
      accessKey: effectiveStorageKey
    }
  }
}

// ============================================================================
// RBAC CONFIGURATION
// ============================================================================

// Storage File Data SMB Share Contributor - prepares for Managed Identity migration
resource storageFileRbac 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, appService.id, '0c867c2a-1d8c-454a-a3db-ab2ea1bdc8bb')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '0c867c2a-1d8c-454a-a3db-ab2ea1bdc8bb')
    principalId: appService.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Storage Blob Data Contributor - for backup container access
resource storageBlobRbac 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, appService.id, 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: appService.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// ============================================================================
// DIAGNOSTIC SETTINGS (Enhanced)
// ============================================================================

resource diagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (!empty(logAnalyticsWorkspaceId)) {
  name: 'AppServiceDiagnostics'
  scope: appService
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        category: 'AppServiceHTTPLogs'
        enabled: true
        retentionPolicy: {
          days: 7
          enabled: true
        }
      }
      {
        category: 'AppServiceConsoleLogs'
        enabled: true
        retentionPolicy: {
          days: 7
          enabled: true
        }
      }
      {
        category: 'AppServiceAppLogs'
        enabled: true
        retentionPolicy: {
          days: 30
          enabled: true
        }
      }
      {
        category: 'AppServiceAuditLogs'
        enabled: true
        retentionPolicy: {
          days: 90
          enabled: true
        }
      }
      {
        category: 'AppServiceIPSecAuditLogs'
        enabled: true
        retentionPolicy: {
          days: 90
          enabled: true
        }
      }
      {
        category: 'AppServicePlatformLogs'
        enabled: true
        retentionPolicy: {
          days: 7
          enabled: true
        }
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
        retentionPolicy: {
          days: 30
          enabled: true
        }
      }
    ]
  }
}

// ============================================================================
// KEY VAULT ACCESS POLICY
// ============================================================================

resource keyVaultAccessPolicy 'Microsoft.KeyVault/vaults/accessPolicies@2023-07-01' = if (!empty(keyVaultName)) {
  parent: keyVault
  name: 'add'
  properties: {
    accessPolicies: [
      {
        tenantId: subscription().tenantId
        objectId: appService.identity.principalId
        permissions: {
          secrets: [
            'get'
            'list'
          ]
        }
      }
    ]
  }
}

// ============================================================================
// EASY AUTH CONFIGURATION (Optional)
// ============================================================================

resource authSettings 'Microsoft.Web/sites/config@2023-12-01' = if (enableEasyAuth) {
  parent: appService
  name: 'authsettingsV2'
  properties: {
    globalValidation: {
      requireAuthentication: true
      unauthenticatedClientAction: 'RedirectToLoginPage'
      redirectToProvider: 'azureactivedirectory'
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          clientId: azureAdClientId
          clientSecretSettingName: 'MICROSOFT_PROVIDER_AUTHENTICATION_SECRET' // pragma: allowlist secret
          openIdIssuer: 'https://login.microsoftonline.com/${azureAdTenantId}/v2.0'
        }
        login: {
          disableWWWAuthenticate: false
        }
        validation: {
          allowedAudiences: [
            azureAdClientId
          ]
        }
      }
    }
    login: {
      tokenStore: {
        enabled: easyAuthTokenStore
        tokenRefreshExtensionHours: 72
        fileSystem: {}
      }
      preserveUrlFragmentsForLogins: true
      cookieExpiration: {
        convention: 'FixedTime'
        timeToExpiration: '08:00:00'
      }
      nonce: {
        validateNonce: true
        nonceExpirationInterval: '00:05:00'
      }
    }
    httpSettings: {
      requireHttps: true
      routes: {
        apiPrefix: '/.auth'
      }
      forwardProxy: {
        convention: 'NoProxy'
      }
    }
  }
}

// ============================================================================
// OUTPUTS
// ============================================================================

output appServiceId string = appService.id
output appServiceName string = appService.name
output appUrl string = 'https://${appService.properties.defaultHostName}'
output principalId string = appService.identity.principalId
output slotUrls array = [for (slotName, i) in deploymentSlotNames: 'https://${appService.name}-${slotName}.azurewebsites.net']
output autoScaleEnabled bool = enableAutoScaling
output healthCheckEnabled bool = enableHealthCheck

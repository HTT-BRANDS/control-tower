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

@description('Storage account access key (passed securely via Key Vault). When empty, falls back to listKeys().') // #nosec — description only
@secure()
param storageAccessKey string = ''

// Reference to storage account
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: storageAccountName
}

// Reference to Key Vault
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = if (!empty(keyVaultName)) {
  name: keyVaultName
}

// Use Key Vault-sourced key when available, fall back to listKeys() for backwards compatibility
var effectiveStorageKey = !empty(storageAccessKey) ? storageAccessKey : storageAccount.listKeys().keys[0].value // #nosec — backwards-compat fallback; Key Vault path preferred

// Determine kind based on deployment type
var appKind = useContainerDeployment ? 'app,linux,container' : 'app,linux'

// Determine linuxFxVersion based on deployment type
var linuxFxVersion = useContainerDeployment ? 'DOCKER|${containerImage}' : 'PYTHON|${pythonVersion}'

// App Service
resource appService 'Microsoft.Web/sites@2023-12-01' = {
  name: name
  location: location
  tags: tags
  kind: appKind
  identity: {
    type: 'SystemAssigned'
  }
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
      healthCheckPath: '/health'
      use32BitWorkerProcess: false
      webSocketsEnabled: false
      managedPipelineMode: 'Integrated'
      loadBalancing: 'LeastRequests'
      experiments: {
        rampUpRules: []
      }
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
          ]
          slowRequests: {
            timeTaken: '00:01:00'
            count: 10
            timeInterval: '00:05:00'
          }
        }
      }
      appSettings: [
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
          value: useContainerDeployment ? 'false' : 'true'
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsightsConnectionString
        }
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: empty(appInsightsConnectionString) ? '' : split(appInsightsConnectionString, ';')[0]
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
          value: empty(keyVaultName) ? '' : 'https://${keyVaultName}${az.environment().suffixes.keyvaultDns}'
        }
        {
          name: 'PYTHON_VERSION'
          value: pythonVersion
        }
        {
          name: 'WEBSITE_HEALTHCHECK_MAXPINGFAILURES'
          value: '3'
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
          value: empty(azureAdTenantId) ? '' : '${az.environment().authentication.loginEndpoint}${azureAdTenantId}/v2.0'
        }
        {
          name: 'AZURE_AD_TOKEN_ENDPOINT'
          value: empty(azureAdTenantId) ? '' : '${az.environment().authentication.loginEndpoint}${azureAdTenantId}/oauth2/v2.0/token'
        }
        {
          name: 'AZURE_AD_AUTHORIZATION_ENDPOINT'
          value: empty(azureAdTenantId) ? '' : '${az.environment().authentication.loginEndpoint}${azureAdTenantId}/oauth2/v2.0/authorize'
        }
        {
          name: 'AZURE_AD_JWKS_URI'
          value: empty(azureAdTenantId) ? '' : '${az.environment().authentication.loginEndpoint}${azureAdTenantId}/discovery/v2.0/keys'
        }
        {
          name: 'JWT_SECRET_KEY'
          value: !empty(keyVaultName) ? '@Microsoft.KeyVault(SecretUri=https://${keyVaultName}${az.environment().suffixes.keyvaultDns}/secrets/jwt-secret-key)' : jwtSecretKey
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
      ]
      connectionStrings: []
    }
  }
}

// Configure AzureFiles mount for persistent storage
resource azureStorageConfig 'Microsoft.Web/sites/config@2023-12-01' = {
  parent: appService
  name: 'azureStorageAccounts'
  properties: {
    dataVolume: {
      type: 'AzureFiles'
      shareName: 'appdata'
      mountPath: '/home/data'
      accountName: storageAccountName
      // SECURITY: Key is passed via @secure() param from Key Vault (redacted in deployment history).
      // Fallback to listKeys() only when Key Vault is not configured.
      // Future: Migrate to Managed Identity when Azure Files supports identity-based App Service mounts.
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

// RBAC: Storage File Data SMB Share Contributor — prepares for future Managed Identity migration
// When Azure Files supports identity-based mounts for App Service, this role enables the transition
// without redeployment. Role ID: 0c867c2a-1d8c-454a-a3db-ab2ea1bdc8bb
resource storageFileRbac 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, appService.id, '0c867c2a-1d8c-454a-a3db-ab2ea1bdc8bb')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '0c867c2a-1d8c-454a-a3db-ab2ea1bdc8bb')
    principalId: appService.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// RBAC: Storage Blob Data Contributor — for backup container access via MI
// Role ID: ba92f5b4-2d11-453d-a403-e96b0029c9fe
resource storageBlobRbac 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, appService.id, 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: appService.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Diagnostic settings
resource diagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (!empty(logAnalyticsWorkspaceId)) {
  name: 'AppServiceDiagnostics'
  scope: appService
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        category: 'AppServiceHTTPLogs'
        enabled: true
      }
      {
        category: 'AppServiceConsoleLogs'
        enabled: true
      }
      {
        category: 'AppServiceAppLogs'
        enabled: true
      }
      {
        category: 'AppServiceAuditLogs'
        enabled: true
      }
      {
        category: 'AppServiceIPSecAuditLogs'
        enabled: true
      }
      {
        category: 'AppServicePlatformLogs'
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

// Key Vault access policy (grant app service access to Key Vault)
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

output appServiceId string = appService.id
output appServiceName string = appService.name
output appUrl string = 'https://${appService.properties.defaultHostName}'
output principalId string = appService.identity.principalId

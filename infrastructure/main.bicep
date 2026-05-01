targetScope = 'subscription'

// =============================================================================
// Azure Governance Platform - Main Bicep Template
// Deploys complete infrastructure for the Azure Governance Platform
// =============================================================================

// -----------------------------------------------------------------------------
// Parameters
// -----------------------------------------------------------------------------
@description('Environment name (dev, staging, production)')
param environment string = 'production'

@description('Primary location for resources')
param location string = deployment().location

@description('Unique suffix for resource naming')
param resourceSuffix string = uniqueString(subscription().id, deployment().name)

@description('App Service Plan SKU')
@allowed([
  'F1'
  'D1'
  'B1'
  'B2'
  'B3'
  'S1'
  'S2'
  'S3'
  'P1v2'
  'P2v2'
  'P3v2'
])
param appServiceSku string = 'B1'

@description('Azure SQL Database SKU')
@allowed([
  'Free'
  'Basic'
  'Standard_S0'
  'Standard_S1'
  'Standard_S2'
  'Premium_P1'
])
param sqlDatabaseSku string = 'Standard_S0'

@description('Enable Azure SQL (otherwise uses SQLite)')
param enableAzureSql bool = false

@description('Enable Application Insights')
param enableAppInsights bool = true

@description('Enable Key Vault')
param enableKeyVault bool = true

@description('Enable VNet integration')
param enableVNetIntegration bool = false

@description('Enable Azure Cache for Redis. Leave FALSE until: (a) App Service scaled to 2+ instances, (b) cache miss rate >20% sustained, or (c) memory pressure on App Service. See docs/COST_MODEL_AND_SCALING.md section 6.2 trigger #7. Redis C0 adds ~$16/mo.')
param enableRedis bool = false

@description('Admin username for SQL Server. Not marked @secure() because the username is an identifier, not a credential — the password (sqlAdminPassword) is the actual secret. Having it unsecured also silences the secure-parameter-default linter warning, which correctly flags @secure() params with hardcoded non-empty defaults.')
param sqlAdminUsername string = 'sqladmin'

@description('Admin password for SQL Server')
@secure()
param sqlAdminPassword string = newGuid()

@description('Docker image tag to deploy')
param containerImage string = 'latest'

@description('Use container deployment instead of code deployment')
param useContainerDeployment bool = true

@description('Log retention in days')
param logRetentionDays int = 30

@description('Tags to apply to all resources')
param tags object = {
  Application: 'Azure Governance Platform'
  Environment: environment
  ManagedBy: 'Bicep'
}

@description('Azure AD tenant ID for user authentication')
param azureAdTenantId string = ''

@description('Azure AD app registration client ID for OAuth2')
param azureAdClientId string = ''

@description('Azure AD app registration client secret')
@secure()
param azureAdClientSecret string = ''

@description('JWT signing secret key (min 32 chars). Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"')
@secure()
param jwtSecretKey string = ''

@description('Comma-separated CORS allowed origins (e.g. https://app-governance-prod.azurewebsites.net)')
param corsOrigins string = ''

@description('Comma-separated admin email addresses for elevated access')
param adminEmails string = ''

@description('Optional explicit resource group name. Leave empty to use the generated default.')
param resourceGroupNameOverride string = ''

@description('Optional explicit App Service Plan name. Leave empty to use the generated default.')
param appServicePlanNameOverride string = ''

@description('Optional explicit App Service name. Leave empty to use the generated default.')
param appServiceNameOverride string = ''

@description('Optional explicit Application Insights name. Leave empty to use the generated default.')
param appInsightsNameOverride string = ''

@description('Optional explicit Log Analytics workspace name. Leave empty to use the generated default.')
param logAnalyticsNameOverride string = ''

@description('Optional explicit Key Vault name. Leave empty to use the generated normalized default. Explicit overrides are not truncated.')
param keyVaultNameOverride string = ''

@description('Optional explicit Storage Account name. Leave empty to use the generated normalized default. Explicit overrides are not truncated or otherwise normalized.')
param storageAccountNameOverride string = ''

@description('Optional explicit SQL Server name. Leave empty to use the generated default.')
param sqlServerNameOverride string = ''

@description('Optional explicit SQL Database name. Leave empty to use the generated default.')
param sqlDatabaseNameOverride string = ''

// -----------------------------------------------------------------------------
// Variables
// -----------------------------------------------------------------------------
var generatedResourceGroupName = 'rg-governance-${environment}'
var generatedAppServicePlanName = 'asp-governance-${environment}-${resourceSuffix}'
var generatedAppServiceName = 'app-governance-${environment}-${take(resourceSuffix, 8)}'
var generatedAppInsightsName = 'ai-governance-${environment}-${resourceSuffix}'
var generatedLogAnalyticsName = 'log-governance-${environment}-${resourceSuffix}'
var generatedKeyVaultName = 'kv-gov-${environment}-${take(resourceSuffix, 8)}'
var generatedStorageAccountName = 'stgov${environment}${take(resourceSuffix, 8)}'
var generatedSqlServerName = 'sql-governance-${environment}-${take(resourceSuffix, 8)}'
var generatedSqlDatabaseName = 'governance-db'

// Only generated names are normalized/truncated. Explicit overrides are preserved exactly.
var normalizedGeneratedKeyVaultName = length(generatedKeyVaultName) > 24 ? take(generatedKeyVaultName, 24) : generatedKeyVaultName
var normalizedGeneratedStorageAccountName = length(replace(generatedStorageAccountName, '-', '')) > 24 ? take(replace(generatedStorageAccountName, '-', ''), 24) : replace(generatedStorageAccountName, '-', '')

var resourceGroupName = empty(resourceGroupNameOverride) ? generatedResourceGroupName : resourceGroupNameOverride
var appServicePlanName = empty(appServicePlanNameOverride) ? generatedAppServicePlanName : appServicePlanNameOverride
var appServiceName = empty(appServiceNameOverride) ? generatedAppServiceName : appServiceNameOverride
var appInsightsName = empty(appInsightsNameOverride) ? generatedAppInsightsName : appInsightsNameOverride
var logAnalyticsName = empty(logAnalyticsNameOverride) ? generatedLogAnalyticsName : logAnalyticsNameOverride
var keyVaultName = empty(keyVaultNameOverride) ? normalizedGeneratedKeyVaultName : keyVaultNameOverride
var storageAccountName = empty(storageAccountNameOverride) ? normalizedGeneratedStorageAccountName : storageAccountNameOverride
var sqlServerName = empty(sqlServerNameOverride) ? generatedSqlServerName : sqlServerNameOverride
var sqlDatabaseName = empty(sqlDatabaseNameOverride) ? generatedSqlDatabaseName : sqlDatabaseNameOverride
var vnetName = 'vnet-governance-${environment}'
var redisName = 'redis-gov-${environment}-${take(resourceSuffix, 8)}'

// -----------------------------------------------------------------------------
// Resource Group
// -----------------------------------------------------------------------------
resource resourceGroup 'Microsoft.Resources/resourceGroups@2023-07-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

// -----------------------------------------------------------------------------
// Log Analytics Workspace (for Application Insights and diagnostics)
// -----------------------------------------------------------------------------
module logAnalytics 'modules/log-analytics.bicep' = {
  name: 'logAnalyticsDeploy'
  scope: resourceGroup
  params: {
    name: logAnalyticsName
    location: location
    retentionInDays: logRetentionDays
    tags: tags
  }
}

// -----------------------------------------------------------------------------
// Application Insights
// -----------------------------------------------------------------------------
module appInsights 'modules/app-insights.bicep' = if (enableAppInsights) {
  name: 'appInsightsDeploy'
  scope: resourceGroup
  params: {
    name: appInsightsName
    location: location
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
    tags: tags
  }
}

// -----------------------------------------------------------------------------
// Storage Account (for logs, backups, and file shares)
// -----------------------------------------------------------------------------
module storage 'modules/storage.bicep' = {
  name: 'storageDeploy'
  scope: resourceGroup
  params: {
    name: storageAccountName
    location: location
    tags: tags
  }
}

// -----------------------------------------------------------------------------
// Azure SQL Server and Database
// -----------------------------------------------------------------------------
module sqlServer 'modules/sql-server.bicep' = if (enableAzureSql) {
  name: 'sqlServerDeploy'
  scope: resourceGroup
  params: {
    serverName: sqlServerName
    databaseName: sqlDatabaseName
    location: location
    adminUsername: sqlAdminUsername
    adminPassword: sqlAdminPassword
    skuName: sqlDatabaseSku
    tags: tags
  }
}

// -----------------------------------------------------------------------------
// Key Vault
// -----------------------------------------------------------------------------
module keyVault 'modules/key-vault.bicep' = if (enableKeyVault) {
  name: 'keyVaultDeploy'
  scope: resourceGroup
  params: {
    name: keyVaultName
    location: location
    tags: tags
  }
}

// -----------------------------------------------------------------------------
// Storage Key → Key Vault Secret (eliminates listKeys() from deployment history)
// -----------------------------------------------------------------------------
module storageKeySecret 'modules/storage-key-secret.bicep' = if (enableKeyVault) {
  name: 'storageKeySecretDeploy'
  scope: resourceGroup
  params: {
    keyVaultName: keyVaultName
    storageAccountName: storageAccountName
  }
  dependsOn: [
    storage
    keyVault
  ]
}

// Reference Key Vault for secure parameter passing (getSecret)
resource existingKeyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  scope: resourceGroup
  name: keyVaultName
}

// -----------------------------------------------------------------------------
// Virtual Network (optional, for private endpoints)
// -----------------------------------------------------------------------------
module vnet 'modules/vnet.bicep' = if (enableVNetIntegration) {
  name: 'vnetDeploy'
  scope: resourceGroup
  params: {
    name: vnetName
    location: location
    tags: tags
  }
}

// -----------------------------------------------------------------------------
// Azure Cache for Redis (token blacklist, rate limiting, caching)
// -----------------------------------------------------------------------------
module redis 'modules/redis.bicep' = if (enableRedis) {
  name: 'redisDeploy'
  scope: resourceGroup
  params: {
    name: redisName
    location: location
    tags: tags
  }
}

// -----------------------------------------------------------------------------
// App Service Plan
// -----------------------------------------------------------------------------
module appServicePlan 'modules/app-service-plan.bicep' = {
  name: 'appServicePlanDeploy'
  scope: resourceGroup
  params: {
    name: appServicePlanName
    location: location
    sku: appServiceSku
    tags: tags
  }
}

// -----------------------------------------------------------------------------
// App Service
// -----------------------------------------------------------------------------
module appService 'modules/app-service.bicep' = {
  name: 'appServiceDeploy'
  scope: resourceGroup
  params: {
    name: appServiceName
    location: location
    appServicePlanId: appServicePlan.outputs.planId
    appInsightsConnectionString: enableAppInsights ? appInsights!.outputs.connectionString : ''
    storageAccountName: storageAccountName
    keyVaultName: enableKeyVault ? keyVaultName : ''
    sqlServerName: enableAzureSql ? sqlServerName : ''
    sqlDatabaseName: sqlDatabaseName
    enableAzureSql: enableAzureSql
    containerImage: containerImage
    environment: environment
    tags: tags
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
    useContainerDeployment: useContainerDeployment
    azureAdTenantId: azureAdTenantId
    azureAdClientId: azureAdClientId
    azureAdClientSecret: azureAdClientSecret
    jwtSecretKey: jwtSecretKey
    corsOrigins: corsOrigins
    adminEmails: adminEmails
    redisUrl: enableRedis ? redis!.outputs.connectionString : ''
    storageAccessKey: enableKeyVault ? existingKeyVault.getSecret('storage-access-key') : ''
  }
  dependsOn: [
    // redis intentionally omitted: `redisUrl: enableRedis ? redis!.outputs.connectionString : ''`
    // above already creates an implicit module dependency on redis. Listing
    // it here again fires no-unnecessary-dependson.
    storage
    keyVault
    storageKeySecret
    sqlServer
  ]
}

// -----------------------------------------------------------------------------
// Outputs
// -----------------------------------------------------------------------------
output resourceGroupName string = resourceGroup.name
output appServiceName string = appServiceName
output appServiceUrl string = appService.outputs.appUrl
output appInsightsName string = enableAppInsights ? appInsightsName : ''
output keyVaultName string = enableKeyVault ? keyVaultName : ''
output storageAccountName string = storageAccountName
output sqlServerName string = enableAzureSql ? sqlServerName : ''
output sqlDatabaseName string = enableAzureSql ? sqlDatabaseName : ''

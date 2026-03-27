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

@description('Secondary location for disaster recovery')
param secondaryLocation string = 'westus2'

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

@description('Enable Azure Cache for Redis')
param enableRedis bool = false

@description('Admin username for SQL Server')
@secure()
param sqlAdminUsername string = 'sqladmin'

@description('Admin password for SQL Server')
@secure()
param sqlAdminPassword string = newGuid()

@description('Docker image tag to deploy')
param containerImage string = 'latest'

@description('Use container deployment instead of code deployment')
param useContainerDeployment bool = true

@description('Azure Container Registry name (optional)')
param acrName string = ''

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

// -----------------------------------------------------------------------------
// Variables
// -----------------------------------------------------------------------------
var resourceGroupName = 'rg-governance-${environment}'
var appServicePlanName = 'asp-governance-${environment}-${resourceSuffix}'
var appServiceName = 'app-governance-${environment}-${take(resourceSuffix, 8)}'
var appInsightsName = 'ai-governance-${environment}-${resourceSuffix}'
var logAnalyticsName = 'log-governance-${environment}-${resourceSuffix}'
var keyVaultName = 'kv-gov-${environment}-${take(resourceSuffix, 8)}'
var storageAccountName = 'stgov${environment}${take(resourceSuffix, 8)}'
var sqlServerName = 'sql-governance-${environment}-${take(resourceSuffix, 8)}'
var sqlDatabaseName = 'governance-db'
var vnetName = 'vnet-governance-${environment}'
var redisName = 'redis-gov-${environment}-${take(resourceSuffix, 8)}'

// Validate resource names
var validatedKeyVaultName = length(keyVaultName) > 24 ? take(keyVaultName, 24) : keyVaultName
var validatedStorageName = length(replace(storageAccountName, '-', '')) > 24 ? take(replace(storageAccountName, '-', ''), 24) : replace(storageAccountName, '-', '')

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
    name: validatedStorageName
    location: location
    secondaryLocation: secondaryLocation
    environment: environment
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
    name: validatedKeyVaultName
    location: location
    environment: environment
    tags: tags
  }
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
    environment: environment
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
    appInsightsConnectionString: enableAppInsights ? appInsights.outputs.connectionString : ''
    storageAccountName: validatedStorageName
    keyVaultName: enableKeyVault ? validatedKeyVaultName : ''
    sqlServerName: enableAzureSql ? sqlServerName : ''
    sqlDatabaseName: sqlDatabaseName
    enableAzureSql: enableAzureSql
    containerImage: containerImage
    acrName: acrName
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
    redisUrl: enableRedis ? redis.outputs.redisUrl : ''
  }
  dependsOn: [
    storage
    keyVault
    sqlServer
    redis
  ]
}

// -----------------------------------------------------------------------------
// Outputs
// -----------------------------------------------------------------------------
output resourceGroupName string = resourceGroup.name
output appServiceName string = appServiceName
output appServiceUrl string = appService.outputs.appUrl
output appInsightsName string = enableAppInsights ? appInsightsName : ''
output keyVaultName string = enableKeyVault ? validatedKeyVaultName : ''
output storageAccountName string = validatedStorageName
output sqlServerName string = enableAzureSql ? sqlServerName : ''
output sqlDatabaseName string = enableAzureSql ? sqlDatabaseName : ''

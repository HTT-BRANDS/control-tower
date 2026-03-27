@description('Name of the SQL Server')
param serverName string

@description('Name of the database')
param databaseName string

@description('Location for the resources')
param location string

@description('Administrator username')
@secure()
param adminUsername string

@description('Administrator password')
@secure()
param adminPassword string

@description('Enable VNet integration for private connectivity')
param enableVNetIntegration bool = false

@description('VNet subnet ID for SQL server')
param sqlSubnetId string = '' 

@description('Database SKU name')
param skuName string = 'Standard_S0'

@description('Tags to apply')
param tags object = {}

@description('Enable TDE')
param enableTde bool = true

@description('Enable auditing')
param enableAuditing bool = true

// SQL Server
resource sqlServer 'Microsoft.Sql/servers@2023-05-01-preview' = {
  name: serverName
  location: location
  tags: tags
  properties: {
    administratorLogin: adminUsername
    administratorLoginPassword: adminPassword
    version: '12.0'
    minimalTlsVersion: '1.2'
    publicNetworkAccess: 'Disabled'
    restrictOutboundNetworkAccess: 'Disabled'
  }
}

// SQL Database
resource sqlDatabase 'Microsoft.Sql/servers/databases@2023-05-01-preview' = {
  parent: sqlServer
  name: databaseName
  location: location
  tags: tags
  sku: {
    name: skuName
  }
  properties: {
    collation: 'SQL_Latin1_General_CP1_CI_AS'
    maxSizeBytes: 268435456000 // 250 GB for S0
    sampleName: ''
    zoneRedundant: false
    readScale: 'Disabled'
    requestedBackupStorageRedundancy: 'Geo'
    isLedgerOn: false
  }
}

// Transparent Data Encryption
resource tde 'Microsoft.Sql/servers/databases/transparentDataEncryption@2023-05-01-preview' = if (enableTde) {
  parent: sqlDatabase
  name: 'current'
  properties: {
    state: 'Enabled'
  }
}

// VNet rule for private connectivity
resource vnetRule 'Microsoft.Sql/servers/virtualNetworkRules@2023-05-01-preview' = if (enableVNetIntegration && !empty(sqlSubnetId)) {
  parent: sqlServer
  name: 'VNetRule'
  properties: {
    virtualNetworkSubnetId: sqlSubnetId
    ignoreMissingVnetServiceEndpoint: false
  }
}


output serverId string = sqlServer.id
output serverName string = sqlServer.name
output serverFqdn string = sqlServer.properties.fullyQualifiedDomainName
output databaseId string = sqlDatabase.id
output databaseName string = sqlDatabase.name

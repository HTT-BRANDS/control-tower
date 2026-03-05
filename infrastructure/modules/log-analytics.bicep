@description('Name of the Log Analytics workspace')
param name string

@description('Location for the resource')
param location string

@description('Log retention in days - only used for Standalone/PerNode tiers')
param retentionInDays int = 30

@description('SKU for the workspace')
@allowed([
  'PerGB2018'
  'Free'
  'Standalone'
  'PerNode'
])
param sku string = 'PerGB2018'

@description('Tags to apply')
param tags object = {}

// Only apply retentionInDays for supported SKUs (Standalone, PerNode)
// PerGB2018 and Free tiers don't support direct retention setting
var supportedSkuForRetention = sku == 'Standalone' || sku == 'PerNode'

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    sku: {
      name: sku
    }
    retentionInDays: supportedSkuForRetention ? retentionInDays : null
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
  }
}

output workspaceId string = logAnalyticsWorkspace.id
output workspaceName string = logAnalyticsWorkspace.name
output customerId string = logAnalyticsWorkspace.properties.customerId

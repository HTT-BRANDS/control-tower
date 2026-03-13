@description('Name of the App Service Plan')
param name string

@description('Location for the resource')
param location string

@description('SKU for the App Service Plan')
@allowed(['F1', 'D1', 'B1', 'B2', 'B3', 'S1', 'S2', 'S3', 'P1v2', 'P2v2', 'P3v2'])
param sku string = 'B1'

@description('Tags to apply')
param tags object = {}

@description('OS type')
@allowed(['Linux', 'Windows'])
param osType string = 'Linux'

var skuMap = {
  F1: { tier: 'Free', size: 'F1', family: 'F', capacity: 0 }
  D1: { tier: 'Shared', size: 'D1', family: 'D', capacity: 0 }
  B1: { tier: 'Basic', size: 'B1', family: 'B', capacity: 1 }
  B2: { tier: 'Basic', size: 'B2', family: 'B', capacity: 1 }
  B3: { tier: 'Basic', size: 'B3', family: 'B', capacity: 1 }
  S1: { tier: 'Standard', size: 'S1', family: 'S', capacity: 1 }
  S2: { tier: 'Standard', size: 'S2', family: 'S', capacity: 1 }
  S3: { tier: 'Standard', size: 'S3', family: 'S', capacity: 1 }
  P1v2: { tier: 'PremiumV2', size: 'P1v2', family: 'Pv2', capacity: 1 }
  P2v2: { tier: 'PremiumV2', size: 'P2v2', family: 'Pv2', capacity: 1 }
  P3v2: { tier: 'PremiumV2', size: 'P3v2', family: 'Pv2', capacity: 1 }
}

resource appServicePlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: name
  location: location
  tags: tags
  kind: osType == 'Linux' ? 'linux' : 'app'
  sku: {
    name: sku
    tier: skuMap[sku].tier
    size: skuMap[sku].size
    family: skuMap[sku].family
    capacity: skuMap[sku].capacity
  }
  properties: {
    reserved: osType == 'Linux'
    zoneRedundant: false
    perSiteScaling: false
    elasticScaleEnabled: false
    targetWorkerCount: 0
    targetWorkerSizeId: 0
  }
}

output planId string = appServicePlan.id
output planName string = appServicePlan.name
output sku string = appServicePlan.sku.name

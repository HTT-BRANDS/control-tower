@description('Name of the virtual network')
param name string

@description('Location for the resource')
param location string

@description('Tags to apply')
param tags object = {}

@description('VNet address prefix')
param vnetAddressPrefix string = '10.0.0.0/16'

@description('Subnet address prefixes')
param subnetPrefixes object = {
  appService: '10.0.1.0/24'
  database: '10.0.2.0/24'
  privateEndpoints: '10.0.3.0/24'
}

resource vnet 'Microsoft.Network/virtualNetworks@2023-09-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [
        vnetAddressPrefix
      ]
    }
    subnets: [
      {
        name: 'AppServiceSubnet'
        properties: {
          addressPrefix: subnetPrefixes.appService
          delegations: [
            {
              name: 'delegation'
              properties: {
                serviceName: 'Microsoft.Web/serverFarms'
              }
            }
          ]
          serviceEndpoints: [
            {
              service: 'Microsoft.Sql'
            }
            {
              service: 'Microsoft.Storage'
            }
          ]
        }
      }
      {
        name: 'DatabaseSubnet'
        properties: {
          addressPrefix: subnetPrefixes.database
          serviceEndpoints: [
            {
              service: 'Microsoft.Sql'
            }
            {
              service: 'Microsoft.Storage'
            }
          ]
        }
      }
      {
        name: 'PrivateEndpointSubnet'
        properties: {
          addressPrefix: subnetPrefixes.privateEndpoints
          privateEndpointNetworkPolicies: 'Disabled'
          privateLinkServiceNetworkPolicies: 'Enabled'
        }
      }
    ]
  }
}

output vnetId string = vnet.id
output vnetName string = vnet.name
output appServiceSubnetId string = resourceId('Microsoft.Network/virtualNetworks/subnets', name, 'AppServiceSubnet')
output databaseSubnetId string = resourceId('Microsoft.Network/virtualNetworks/subnets', name, 'DatabaseSubnet')
output privateEndpointSubnetId string = resourceId('Microsoft.Network/virtualNetworks/subnets', name, 'PrivateEndpointSubnet')

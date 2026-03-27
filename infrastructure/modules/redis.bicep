// =============================================================================
// Azure Cache for Redis - Basic C0
// Cost: ~$16/month | 250MB | Non-SSL port disabled
// =============================================================================

@description('Redis cache name')
param name string

@description('Location')
param location string = resourceGroup().location

@description('Tags')
param tags object = {}

@description('SKU: Basic C0 for token blacklist + rate limiting')
@allowed([
  'Basic_C0'
  'Basic_C1'
  'Standard_C0'
  'Standard_C1'
])
param skuName string = 'Basic_C0'

var skuParts = split(skuName, '_')
var family = skuParts[0] == 'Basic' || skuParts[0] == 'Standard' ? 'C' : 'P'

resource redis 'Microsoft.Cache/redis@2023-08-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    sku: {
      name: skuParts[0]
      family: family
      capacity: int(replace(skuParts[1], 'C', ''))
    }
    enableNonSslPort: false
    minimumTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled' // Basic tier doesn't support Private Endpoints
    redisConfiguration: {
      'maxmemory-policy': 'volatile-lru' // Evict keys with TTL first (perfect for token blacklist)
    }
  }
}

@description('Redis hostname')
output hostName string = redis.properties.hostName

@description('Redis SSL port')
output sslPort int = redis.properties.sslPort

@description('Redis primary connection string')
output connectionString string = '${redis.properties.hostName}:${redis.properties.sslPort}'

@description('Redis primary access key')
output primaryKey string = redis.listKeys().primaryKey

@description('Full Redis URL for app configuration')
output redisUrl string = 'rediss://:${redis.listKeys().primaryKey}@${redis.properties.hostName}:${redis.properties.sslPort}/0'

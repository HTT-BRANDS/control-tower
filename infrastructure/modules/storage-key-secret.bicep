@description('Name of the Key Vault')
param keyVaultName string

@description('Name of the storage account')
param storageAccountName string

@description('Name for the secret')
param secretName string = 'storage-access-key'

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: storageAccountName
}

// Store primary storage key in Key Vault.
// listKeys() is used here in a secure context — the secret value
// is redacted in ARM deployment history.
resource storageKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: secretName
  properties: {
    value: storageAccount.listKeys().keys[0].value // #nosec — secure context; stored as Key Vault secret
    contentType: 'Storage Account Access Key'
    attributes: {
      enabled: true
    }
  }
}

output secretName string = storageKeySecret.name
output secretUri string = storageKeySecret.properties.secretUri

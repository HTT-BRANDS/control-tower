// =============================================================================
// infra/domain-intelligence/main.bicep — re-creation stash for ct-mql Option A
// =============================================================================
//
// PURPOSE
//   ct-mql chose Option A: DELETE the idle domain-intelligence resources
//   (zero traffic 60+ days). This Bicep is the "stash" that lets the stack be
//   re-created later if the project is revived, so deleting now is reversible
//   in intent even though it's destructive in Azure.
//
// PROVENANCE / CONFIDENCE
//   This template is reconstructed from operational evidence, NOT exported from
//   the live resources (no `az ... export` was run — the resources are stopped
//   and slated for deletion). Values marked `// [VERIFY]` are best-effort and
//   should be confirmed against `az ... show` output BEFORE relying on this for
//   an exact rebuild. Known-good facts (from
//   reports/ops/domain-intelligence-stop-2026-05-18.md):
//     - PostgreSQL flexible server: SKU Standard_B1ms, version 16
//     - App Service: domain-intelligence-prod (Linux App Service assumed)
//     - Resource group: rg-htt-domain-intelligence (subscription HTT-CORE)
//   Suspected-but-unconfirmed (from docs/COST_MODEL_AND_SCALING.md):
//     - A Cosmos DB (~$35/mo) also lives in this RG. Its config is unknown.
//       See cosmos section below — it is PARAMETERISED OFF by default so this
//       template doesn't fabricate a schema we can't verify.
//
// USAGE (revival)
//   az group create -n rg-htt-domain-intelligence -l <region>
//   az deployment group create \
//     -g rg-htt-domain-intelligence \
//     -f infra/domain-intelligence/main.bicep \
//     -p infra/domain-intelligence/main.parameters.json
//
//   Then redeploy app code + restore data from whatever backup was taken at
//   delete time (see infra/domain-intelligence/README.md "Before you delete").
// =============================================================================

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('App Service (web app) name. Must be globally unique.')
param appServiceName string = 'domain-intelligence-prod'

@description('App Service Plan name.')
param appServicePlanName string = 'plan-domain-intelligence-prod'

// [VERIFY] Plan SKU was not captured in the stop evidence. B1 is a reasonable
// low-cost guess (~$13/mo Linux) consistent with the recorded cost. Confirm
// against the real plan before trusting this for an identical rebuild.
@description('App Service Plan SKU (e.g. B1, B2, S1).')
param appServicePlanSku string = 'B1'

@description('PostgreSQL flexible server name.')
param postgresServerName string = 'domainiq-db-prod'

@description('PostgreSQL administrator login.')
param postgresAdminLogin string = 'dbadmin' // [VERIFY] actual admin login unknown

@description('PostgreSQL administrator password. Supply at deploy time; never commit.')
@secure()
param postgresAdminPassword string

// [VERIFY] storage size + backup retention not captured. 32 GB / 7 days are the
// Azure defaults for B1ms and a safe starting point.
@description('PostgreSQL storage size in GB.')
param postgresStorageGb int = 32

@description('PostgreSQL backup retention in days.')
param postgresBackupRetentionDays int = 7

@description('Set true ONLY if you have confirmed the Cosmos DB config. Off by default to avoid fabricating an unverified schema.')
param deployCosmos bool = false

@description('Cosmos DB account name (used only when deployCosmos = true).')
param cosmosAccountName string = 'domainiq-cosmos-prod' // [VERIFY] real name unknown

// ---------------------------------------------------------------------------
// App Service Plan + Web App (Linux)
// ---------------------------------------------------------------------------
resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: appServicePlanName
  location: location
  sku: {
    name: appServicePlanSku
  }
  kind: 'linux'
  properties: {
    reserved: true // required for Linux plans
  }
}

resource webApp 'Microsoft.Web/sites@2023-12-01' = {
  name: appServiceName
  location: location
  kind: 'app,linux'
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      // [VERIFY] original runtime stack unknown. Adjust linuxFxVersion to match
      // the revived app (e.g. 'PYTHON|3.12', 'NODE|20-lts', 'DOCKER|<image>').
      linuxFxVersion: 'PYTHON|3.12'
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
    }
  }
}

// ---------------------------------------------------------------------------
// PostgreSQL Flexible Server (Standard_B1ms, v16 — confirmed from stop evidence)
// ---------------------------------------------------------------------------
resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: postgresServerName
  location: location
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    version: '16'
    administratorLogin: postgresAdminLogin
    administratorLoginPassword: postgresAdminPassword
    storage: {
      storageSizeGB: postgresStorageGb
    }
    backup: {
      backupRetentionDays: postgresBackupRetentionDays
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
  }
}

// ---------------------------------------------------------------------------
// Cosmos DB (OFF by default — config unverified, see header note)
// ---------------------------------------------------------------------------
resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' = if (deployCosmos) {
  name: cosmosAccountName
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
      }
    ]
  }
}

output appServiceHostName string = webApp.properties.defaultHostName
output postgresFqdn string = postgres.properties.fullyQualifiedDomainName

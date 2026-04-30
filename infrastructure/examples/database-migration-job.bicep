// =============================================================================
// Example: Database Migration Job using Azure Container Instances
// This example demonstrates running a one-off database migration job
// =============================================================================

@description('Name for the migration job')
param jobName string = 'db-migration-${utcNow('yyyyMMdd')}'

@description('Location for the resources')
param location string = resourceGroup().location

@description('Container image with migration tools')
param containerImage string = 'ghcr.io/htt-brands/control-tower-migrations:latest'

@description('Storage account for migration artifacts')
param storageAccountName string

@description('Log Analytics workspace for logging')
param logAnalyticsWorkspaceId string

@description('Log Analytics workspace key')
@secure()
param logAnalyticsWorkspaceKey string

@description('Database connection string for target database')
@secure()
param databaseUrl string

@description('Migration direction')
@allowed(['up', 'down', 'status'])
param migrationDirection string = 'up'

@description('Specific migration version (empty for all)')
param migrationVersion string = ''

@description('Tags to apply')
param tags object = {
  Application: 'Database Migration'
  Environment: 'Production'
  JobType: 'migration'
}

// Container instance for migration job
module migrationJob '../modules/container-instances.bicep' = {
  name: 'db-migration-job'
  params: {
    name: jobName
    location: location
    containerImage: containerImage
    jobType: 'migration'
    cpuCores: 2
    memoryGB: 4
    osType: 'Linux'
    restartPolicy: 'Never'
    enableManagedIdentity: true
    storageAccountName: storageAccountName
    fileShareName: 'migration-artifacts'
    fileShareMountPath: '/migrations'
    logAnalyticsWorkspaceId: logAnalyticsWorkspaceId
    logAnalyticsWorkspaceKey: logAnalyticsWorkspaceKey
    tags: tags
    command: [
      'python'
      '-m'
      'alembic'
      'upgrade'
      migrationVersion
    ]
    environmentVariables: [
      {
        name: 'DATABASE_URL'
        value: databaseUrl
      }
      {
        name: 'MIGRATION_DIRECTION'
        value: migrationDirection
      }
      {
        name: 'LOG_LEVEL'
        value: 'INFO'
      }
      {
        name: 'MIGRATIONS_PATH'
        value: '/migrations'
      }
    ]
  }
}

// Outputs
output jobName string = jobName
output containerGroupId string = migrationJob.outputs.containerGroupId
output principalId string = migrationJob.outputs.principalId

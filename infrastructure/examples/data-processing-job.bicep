// =============================================================================
// Example: Data Processing Job using Azure Container Instances
// This example demonstrates running batch data processing
// =============================================================================

@description('Name for the processing job')
param jobName string = 'data-processor-${utcNow('yyyyMMdd-HHmm')}'

@description('Location for the resources')
param location string = resourceGroup().location

@description('Container image with data processing tools')
param containerImage string = 'ghcr.io/htt-brands/control-tower-data-processor:latest'

@description('Storage account for input/output data')
param storageAccountName string

@description('Log Analytics workspace for logging')
param logAnalyticsWorkspaceId string

@description('Log Analytics workspace key')
@secure()
param logAnalyticsWorkspaceKey string

@description('Input blob container path')
param inputPath string = 'raw-data/'

@description('Output blob container path')
param outputPath string = 'processed-data/'

@description('Processing script to run')
param processingScript string = 'process_tenant_data.py'

@description('Tenant IDs to process (comma-separated)')
param tenantIds string = ''

@description('Processing date range start')
param dateRangeStart string = utcNow('yyyy-MM-dd')

@description('Processing date range end')
param dateRangeEnd string = utcNow('yyyy-MM-dd')

@description('CPU cores for the job')
param cpuCores int = 2

@description('Memory in GB for the job')
param memoryGB int = 4

@description('Tags to apply')
param tags object = {
  Application: 'Data Processing'
  Environment: 'Production'
  JobType: 'processing'
}

// Container instance for data processing job
module processingJob '../modules/container-instances.bicep' = {
  name: 'data-processing-job'
  params: {
    name: jobName
    location: location
    containerImage: containerImage
    jobType: 'processing'
    cpuCores: cpuCores
    memoryGB: memoryGB
    osType: 'Linux'
    restartPolicy: 'Never'
    enableManagedIdentity: true
    storageAccountName: storageAccountName
    fileShareName: 'processing-data'
    fileShareMountPath: '/data'
    logAnalyticsWorkspaceId: logAnalyticsWorkspaceId
    logAnalyticsWorkspaceKey: logAnalyticsWorkspaceKey
    tags: tags
    command: [
      'python'
      processingScript
    ]
    environmentVariables: [
      {
        name: 'INPUT_PATH'
        value: inputPath
      }
      {
        name: 'OUTPUT_PATH'
        value: outputPath
      }
      {
        name: 'DATA_PATH'
        value: '/data'
      }
      {
        name: 'TENANT_IDS'
        value: tenantIds
      }
      {
        name: 'DATE_RANGE_START'
        value: dateRangeStart
      }
      {
        name: 'DATE_RANGE_END'
        value: dateRangeEnd
      }
      {
        name: 'LOG_LEVEL'
        value: 'INFO'
      }
      {
        name: 'AZURE_STORAGE_ACCOUNT'
        value: storageAccountName
      }
    ]
  }
}

// Outputs
output jobName string = jobName
output containerGroupId string = processingJob.outputs.containerGroupId
output principalId string = processingJob.outputs.principalId

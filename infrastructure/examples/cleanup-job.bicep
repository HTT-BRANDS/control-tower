// =============================================================================
// Example: Resource Cleanup Job using Azure Container Instances
// This example demonstrates running scheduled cleanup operations
// =============================================================================

@description('Name for the cleanup job')
param jobName string = 'resource-cleanup-${utcNow('yyyyMMdd')}'

@description('Location for the resources')
param location string = resourceGroup().location

@description('Container image with cleanup tools')
param containerImage string = 'mcr.microsoft.com/azure-cli:latest'

@description('Log Analytics workspace for logging')
param logAnalyticsWorkspaceId string

@description('Log Analytics workspace key')
@secure()
param logAnalyticsWorkspaceKey string

@description('Resource groups to clean up')
param resourceGroups array = []

@description('Resource age threshold in days')
param ageThresholdDays int = 30

@description('Dry run mode (no actual deletion)')
param dryRun bool = true

@description('Resource types to clean up')
param resourceTypesToClean array = [
  'Microsoft.Compute/disks'
  'Microsoft.Network/publicIPAddresses'
  'Microsoft.Network/networkInterfaces'
  'Microsoft.Sql/servers/databases'
]

@description('Tags to apply')
param tags object = {
  Application: 'Resource Cleanup'
  Environment: 'Production'
  JobType: 'cleanup'
}

// Build cleanup script
var cleanupScript = '''
#!/bin/bash
set -euo pipefail

echo "Starting resource cleanup job..."
echo "Dry run mode: ${DRY_RUN}"
echo "Age threshold: ${AGE_THRESHOLD_DAYS} days"

# Login using managed identity
az login --identity

# Set subscription
az account set --subscription "${SUBSCRIPTION_ID}"

# Process each resource group
for rg in ${RESOURCE_GROUPS}; do
    echo "Processing resource group: $rg"
    
    # Get resources older than threshold
    CUTOFF_DATE=$(date -d "-${AGE_THRESHOLD_DAYS} days" +%Y-%m-%d)
    
    for resource_type in ${RESOURCE_TYPES}; do
        echo "Checking resources of type: $resource_type"
        
        RESOURCES=$(az resource list \
            --resource-group "$rg" \
            --resource-type "$resource_type" \
            --query "[?createdTime <= '${CUTOFF_DATE}'].id" \
            -o tsv)
        
        if [ -n "$RESOURCES" ]; then
            for resource_id in $RESOURCES; do
                echo "Found resource: $resource_id"
                
                if [ "${DRY_RUN}" = "false" ]; then
                    echo "Deleting resource: $resource_id"
                    az resource delete --ids "$resource_id" --yes
                    echo "Deleted: $resource_id"
                else
                    echo "[DRY RUN] Would delete: $resource_id"
                fi
            done
        else
            echo "No resources of type $resource_type older than ${AGE_THRESHOLD_DAYS} days found"
        fi
    done
done

echo "Cleanup job completed"
'''

// Container instance for cleanup job
module cleanupJob '../modules/container-instances.bicep' = {
  name: 'cleanup-job'
  params: {
    name: jobName
    location: location
    containerImage: containerImage
    jobType: 'cleanup'
    cpuCores: 1
    memoryGB: 2
    osType: 'Linux'
    restartPolicy: 'Never'
    enableManagedIdentity: true
    logAnalyticsWorkspaceId: logAnalyticsWorkspaceId
    logAnalyticsWorkspaceKey: logAnalyticsWorkspaceKey
    tags: tags
    command: [
      '/bin/bash'
      '-c'
      cleanupScript
    ]
    environmentVariables: [
      {
        name: 'DRY_RUN'
        value: string(dryRun)
      }
      {
        name: 'AGE_THRESHOLD_DAYS'
        value: string(ageThresholdDays)
      }
      {
        name: 'SUBSCRIPTION_ID'
        value: subscription().subscriptionId
      }
      {
        name: 'RESOURCE_GROUPS'
        value: join(resourceGroups, ' ')
      }
      {
        name: 'RESOURCE_TYPES'
        value: join(resourceTypesToClean, ' ')
      }
    ]
  }
}

// Outputs
output jobName string = jobName
output containerGroupId string = cleanupJob.outputs.containerGroupId
output principalId string = cleanupJob.outputs.principalId
output dryRunMode string = string(dryRun)

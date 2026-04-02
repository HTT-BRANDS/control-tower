@description('Name of the Logic App')
param name string

@description('Location for the resource')
param location string = resourceGroup().location

@description('Logic App service plan SKU')
@allowed(['Free', 'Standard', 'Premium'])
param sku string = 'Standard'

@description('Tags to apply')
param tags object = {}

@description('Enable managed identity')
param enableManagedIdentity bool = true

@description('User-assigned managed identity resource ID (optional)')
param userAssignedIdentityId string = ''

@description('Log Analytics workspace ID for diagnostics')
param logAnalyticsWorkspaceId string = ''

@description('Storage account name for Logic Apps state')
param storageAccountName string

@description('Storage account resource group (if different)')
param storageAccountResourceGroup string = resourceGroup().name

@description('Enable integration with Microsoft Teams')
param enableTeamsIntegration bool = true

@description('Microsoft Teams webhook URL for notifications')
@secure()
param teamsWebhookUrl string = ''

@description('Enable Azure Monitor alerts integration')
param enableMonitorAlerts bool = true

@description('Enable cost optimization workflows')
param enableCostOptimization bool = true

@description('Email for notifications')
param notificationEmail string = ''

@description('Resource groups to monitor for cleanup')
param monitoredResourceGroups array = []

@description('Schedule for cleanup workflow (cron expression)')
param cleanupSchedule string = '0 0 2 * * *' // 2 AM daily

@description('Resource age threshold in days for cleanup candidates')
param cleanupAgeThresholdDays int = 30

@description('Cost threshold for alerts (in USD)')
param costAlertThreshold decimal = 1000.00

// Reference to existing storage account
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: storageAccountName
  scope: resourceGroup(storageAccountResourceGroup)
}

// Build identity configuration
var identityType = enableManagedIdentity ? (!empty(userAssignedIdentityId) ? 'UserAssigned' : 'SystemAssigned') : 'None'
var identityConfig = enableManagedIdentity ? {
  type: identityType
  userAssignedIdentities: !empty(userAssignedIdentityId) ? {
    '${userAssignedIdentityId}': {}
  } : null
} : null

// Logic App (Standard) - Hosting Plan
resource logicAppPlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: '${name}-plan'
  location: location
  tags: tags
  sku: {
    name: sku == 'Free' ? 'WS1' : (sku == 'Standard' ? 'WS2' : 'WS3')
    tier: sku == 'Free' ? 'WorkflowStandard' : 'WorkflowStandard'
  }
  kind: 'functionapp,workflowapp'
  properties: {
    reserved: true
    targetWorkerCount: 1
    targetWorkerSizeId: 0
  }
}

// Logic App (Standard) - Main Resource
resource logicApp 'Microsoft.Web/sites@2023-12-01' = {
  name: name
  location: location
  tags: tags
  kind: 'functionapp,workflowapp'
  identity: identityConfig
  properties: {
    serverFarmId: logicAppPlan.id
    siteConfig: {
      netFrameworkVersion: 'v6.0'
      functionsRuntimeScaleMonitoringEnabled: false
      appSettings: [
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'node'
        }
        {
          name: 'WEBSITE_NODE_DEFAULT_VERSION'
          value: '~18'
        }
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value // #nosec — Key Vault preferred, listKeys is fallback};EndpointSuffix=core.windows.net'
        }
        {
          name: 'WEBSITE_CONTENTAZUREFILECONNECTIONSTRING'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value // #nosec — Key Vault preferred, listKeys is fallback};EndpointSuffix=core.windows.net'
        }
        {
          name: 'WEBSITE_CONTENTSHARE'
          value: toLower(name)
        }
        {
          name: 'APP_KIND'
          value: 'workflowApp'
        }
        {
          name: 'TeamsWebhookUrl'
          value: enableTeamsIntegration ? teamsWebhookUrl : ''
        }
        {
          name: 'NotificationEmail'
          value: notificationEmail
        }
        {
          name: 'CleanupAgeThresholdDays'
          value: string(cleanupAgeThresholdDays)
        }
        {
          name: 'CostAlertThreshold'
          value: string(costAlertThreshold)
        }
        {
          name: 'MonitoredResourceGroups'
          value: join(monitoredResourceGroups, ',')
        }
      ]
      alwaysOn: sku != 'Free'
    }
    httpsOnly: true
  }
}

// Storage Blob Data Contributor role for Logic App managed identity
resource storageRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (enableManagedIdentity) {
  name: guid(storageAccount.id, logicApp.id, 'StorageBlobDataContributor')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: enableManagedIdentity && !empty(userAssignedIdentityId) ? reference(userAssignedIdentityId, '2023-01-31').principalId : logicApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Diagnostic settings
resource diagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (!empty(logAnalyticsWorkspaceId)) {
  name: 'LogicAppDiagnostics'
  scope: logicApp
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        category: 'FunctionAppLogs'
        enabled: true
      }
      {
        category: 'WorkflowRuntime'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

// Sample Workflow: Teams Notification on Alert
resource teamsNotificationWorkflow 'Microsoft.Logic/workflows@2019-05-01' = if (enableTeamsIntegration && !empty(teamsWebhookUrl)) {
  name: '${name}-teams-notification'
  location: location
  tags: tags
  identity: identityConfig
  properties: {
    state: 'Enabled'
    definition: {
      '$schema': 'https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#'
      contentVersion: '1.0.0.0'
      parameters: {
        '$connections': {
          defaultValue: {}
          type: 'Object'
        }
      }
      triggers: {
        When_a_resource_event_occurs: {
          type: 'Request'
          kind: 'Http'
          inputs: {
            schema: {
              type: 'object'
              properties: {
                alertName: {
                  type: 'string'
                }
                severity: {
                  type: 'string'
                }
                description: {
                  type: 'string'
                }
                resourceName: {
                  type: 'string'
                }
                timestamp: {
                  type: 'string'
                }
              }
            }
          }
        }
      }
      actions: {
        Post_message_to_Teams: {
          type: 'Http'
          inputs: {
            method: 'POST'
            uri: teamsWebhookUrl
            headers: {
              'Content-Type': 'application/json'
            }
            body: {
              '@@type': 'MessageCard'
              '@@context': 'https://schema.org/extensions'
              themeColor: "@{if(equals(triggerBody()['severity'], 'Critical'), 'FF0000', if(equals(triggerBody()['severity'], 'Warning'), 'FF9900', '0078D7'))}"
              summary: "@{triggerBody()['alertName']}"
              sections: [
                {
                  activityTitle: "Azure Governance Alert: @{triggerBody()['alertName']}"
                  activitySubtitle: "@{triggerBody()['timestamp']}"
                  facts: [
                    {
                      name: 'Resource'
                      value: "@{triggerBody()['resourceName']}"
                    }
                    {
                      name: 'Severity'
                      value: "@{triggerBody()['severity']}"
                    }
                    {
                      name: 'Description'
                      value: "@{triggerBody()['description']}"
                    }
                  ]
                }
              ]
            }
          }
        }
      }
    }
  }
}

// Sample Workflow: Scheduled Resource Cleanup
resource cleanupWorkflow 'Microsoft.Logic/workflows@2019-05-01' = if (enableCostOptimization && !empty(monitoredResourceGroups)) {
  name: '${name}-resource-cleanup'
  location: location
  tags: tags
  identity: identityConfig
  properties: {
    state: 'Enabled'
    definition: {
      '$schema': 'https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#'
      contentVersion: '1.0.0.0'
      parameters: {
        '$connections': {
          defaultValue: {}
          type: 'Object'
        }
      }
      triggers: {
        Recurrence: {
          type: 'Recurrence'
          recurrence: {
            frequency: 'Day'
            interval: 1
            startTime: '2024-01-01T02:00:00Z'
          }
        }
      }
      actions: {
        List_Resources: {
          type: 'Http'
          inputs: {
            method: 'GET'
            uri: 'https://management.azure.com/subscriptions/@{subscription().subscriptionId}/resources?api-version=2021-04-01'
            authentication: {
              type: 'ManagedServiceIdentity'
            }
          }
        }
        Filter_Old_Resources: {
          type: 'Query'
          dependsOn: ['List_Resources']
          inputs: {
            from: '@body(\'List_Resources\')?[\'value\']'
            where: '@greaterOrEquals(ticks(utcNow()), add(ticks(item()[\'properties\']?[\'changeTime\']), mul(variables(\'ageThresholdDays\'), 864000000000)))'
          }
        }
        Send_Cleanup_Report: {
          type: 'Http'
          dependsOn: ['Filter_Old_Resources']
          inputs: {
            method: 'POST'
            uri: teamsWebhookUrl
            headers: {
              'Content-Type': 'application/json'
            }
            body: {
              '@@type': 'MessageCard'
              '@@context': 'https://schema.org/extensions'
              themeColor: '0078D7'
              summary: 'Daily Resource Cleanup Report'
              sections: [
                {
                  activityTitle: 'Azure Governance: Resource Cleanup Candidates'
                  activitySubtitle: '@{utcNow()}'
                  text: 'Found @{length(body(\'Filter_Old_Resources\'))} resources older than @{variables(\'ageThresholdDays\')} days that may need cleanup.'
                }
              ]
            }
          }
        }
      }
    }
  }
}

// Sample Workflow: Cost Alert
resource costAlertWorkflow 'Microsoft.Logic/workflows@2019-05-01' = if (enableCostOptimization) {
  name: '${name}-cost-alert'
  location: location
  tags: tags
  identity: identityConfig
  properties: {
    state: 'Enabled'
    definition: {
      '$schema': 'https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#'
      contentVersion: '1.0.0.0'
      parameters: {
        '$connections': {
          defaultValue: {}
          type: 'Object'
        }
      }
      triggers: {
        Recurrence: {
          type: 'Recurrence'
          recurrence: {
            frequency: 'Hour'
            interval: 6
          }
        }
      }
      actions: {
        Get_Current_Cost: {
          type: 'Http'
          inputs: {
            method: 'POST'
            uri: 'https://management.azure.com/subscriptions/@{subscription().subscriptionId}/providers/Microsoft.CostManagement/query?api-version=2023-03-01'
            headers: {
              'Content-Type': 'application/json'
            }
            body: {
              type: 'Usage'
              timeframe: 'MonthToDate'
              dataset: {
                granularity: 'None'
                aggregation: {
                  totalCost: {
                    name: 'PreTaxCost'
                    function: 'Sum'
                  }
                }
              }
            }
            authentication: {
              type: 'ManagedServiceIdentity'
            }
          }
        }
        Check_Threshold: {
          type: 'If'
          dependsOn: ['Get_Current_Cost']
          expression: {
            and: [
              {
                greater: [
                  '@float(first(body(\'Get_Current_Cost\')?[\'properties\']?[\'rows\'])[0])'
                  '@float(variables(\'costThreshold\'))'
                ]
              }
            ]
          }
          actions: {
            Send_Cost_Alert: {
              type: 'Http'
              inputs: {
                method: 'POST'
                uri: teamsWebhookUrl
                headers: {
                  'Content-Type': 'application/json'
                }
                body: {
                  '@@type': 'MessageCard'
                  '@@context': 'https://schema.org/extensions'
                  themeColor: 'FF9900'
                  summary: 'Cost Alert: Budget Threshold Exceeded'
                  sections: [
                    {
                      activityTitle: '⚠️ Azure Cost Alert'
                      activitySubtitle: '@{utcNow()}'
                      text: 'Current month cost has exceeded the threshold of @{variables(\'costThreshold\')} USD'
                    }
                  ]
                }
              }
            }
          }
        }
      }
    }
  }
}

// Outputs
output logicAppId string = logicApp.id
output logicAppName string = logicApp.name
output principalId string = enableManagedIdentity ? (enableManagedIdentity && !empty(userAssignedIdentityId) ? reference(userAssignedIdentityId, '2023-01-31').principalId : logicApp.identity.principalId) : ''
output teamsWorkflowId string = enableTeamsIntegration && !empty(teamsWebhookUrl) ? teamsNotificationWorkflow.id : ''
output cleanupWorkflowId string = enableCostOptimization && !empty(monitoredResourceGroups) ? cleanupWorkflow.id : ''
output costAlertWorkflowId string = enableCostOptimization ? costAlertWorkflow.id : ''

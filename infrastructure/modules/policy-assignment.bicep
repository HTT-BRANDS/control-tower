// -----------------------------------------------------------------------------
// All current callers (deploy-governance-infrastructure.bicep) create policy
// assignments at SUBSCRIPTION scope. Setting targetScope here avoids the
// BCP420 ambiguous-scope error that the old runtime ternary produced. If an
// RG-scoped variant is ever needed, create a sibling module
// policy-assignment-rg.bicep rather than re-introducing runtime scope selection.
// -----------------------------------------------------------------------------
targetScope = 'subscription'

@sys.description('Name of the policy assignment')
param name string

@sys.description('Display name of the assignment')
param displayName string

@sys.description('Description of the assignment')
param description string = ''

@sys.description('Policy definition ID to assign')
param policyDefinitionId string

@sys.description('Policy parameter values')
param parameters object = {}

@sys.description('Enforcement mode')
@allowed(['Default', 'DoNotEnforce'])
param enforcementMode string = 'Default'

@sys.description('Non-compliance messages')
param nonComplianceMessages array = []

@sys.description('Resource selectors for the assignment')
param resourceSelectors array = []

@sys.description('Overrides for the assignment')
param overrides array = []

@sys.description('Identity type for the assignment (required for DeployIfNotExists policies)')
@allowed(['None', 'SystemAssigned', 'UserAssigned'])
param identityType string = 'None'

@sys.description('User-assigned identity resource IDs (if identityType is UserAssigned)')
param userAssignedIdentities object = {}

@sys.description('Create a remediation task automatically')
param createRemediationTask bool = false

@sys.description('Exemption category if creating exemption')
@allowed(['Mitigated', 'Waiver'])
param exemptionCategory string = 'Mitigated'

// Policy assignment resource. Deploys at this module's targetScope
// (subscription). The `scope` param below is kept for backward compatibility
// but is now informational only; the resource deploys wherever this module is
// invoked. Callers should set the module's own `scope:` property if they ever
// need to re-target.
resource policyAssignment 'Microsoft.Authorization/policyAssignments@2022-06-01' = {
  name: name
  properties: {
    displayName: displayName
    description: !empty(description) ? description : 'Assignment of ${policyDefinitionId}'
    policyDefinitionId: policyDefinitionId
    parameters: parameters
    enforcementMode: enforcementMode
    nonComplianceMessages: !empty(nonComplianceMessages) ? nonComplianceMessages : null
    resourceSelectors: !empty(resourceSelectors) ? resourceSelectors : null
    overrides: !empty(overrides) ? overrides : null
  }
  identity: identityType != 'None' ? {
    type: identityType
    userAssignedIdentities: identityType == 'UserAssigned' ? userAssignedIdentities : null
  } : null
}

// Remediation task (optional)
resource remediationTask 'Microsoft.PolicyInsights/remediations@2021-10-01' = if (createRemediationTask) {
  name: '${name}-remediation'
  properties: {
    policyAssignmentId: policyAssignment.id
    resourceDiscoveryMode: 'ReEvaluateCompliance'
    filters: {
      locations: []
    }
  }
}

// Policy exemption (if needed)
// API version 2022-09-01 did not exist. Valid policyExemptions API versions
// are 2020-07-01-preview, 2022-07-01-preview, 2024-12-01-preview, and
// 2025-12-01-preview (all preview; no GA as of Azure API 2025). Picking
// 2022-07-01-preview as the closest stable-ish match to the original intent.
resource policyExemption 'Microsoft.Authorization/policyExemptions@2022-07-01-preview' = if (exemptionCategory != 'Mitigated' || false) {
  name: '${name}-exemption'
  properties: {
    policyAssignmentId: policyAssignment.id
    exemptionCategory: exemptionCategory
    description: 'Policy exemption'
    expiresOn: ''
  }
}

// Outputs
output assignmentId string = policyAssignment.id
output assignmentName string = policyAssignment.name
output assignmentScope string = policyAssignment.properties.scope
output principalId string = identityType != 'None' ? policyAssignment.identity.principalId : ''

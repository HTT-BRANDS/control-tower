# Azure Policy API Field Length Analysis

**Source**: Microsoft REST API Documentation (Tier 1)  
**API Version**: 2024-10-01  
**URL**: https://learn.microsoft.com/en-us/rest/api/policyinsights/policy-states/list-query-results-for-subscription

## PolicyState Response Schema (Definitions Section)

All fields from the formal API schema definition:

| Field Name | Type | Description | Max Length |
|-----------|------|-------------|-----------|
| `@odata.context` | string | OData context string | Not specified |
| `@odata.id` | string | OData entity ID (always null) | Not specified |
| `complianceState` | string | Compliance state of the resource | Not specified |
| `components` | ComponentStateDetails[] | Component compliance records | N/A |
| `effectiveParameters` | string | Effective parameters | Not specified |
| `isCompliant` | boolean | DEPRECATED — use complianceState | N/A |
| `managementGroupIds` | string | Comma-separated management group IDs | Not specified |
| `policyAssignmentId` | string | Policy assignment ID | Not specified |
| `policyAssignmentName` | string | Policy assignment name | Not specified |
| `policyAssignmentOwner` | string | Policy assignment owner | Not specified |
| `policyAssignmentParameters` | string | Policy assignment parameters | Not specified |
| `policyAssignmentScope` | string | Policy assignment scope | Not specified |
| `policyAssignmentVersion` | string | Evaluated policy assignment version | Not specified |
| `policyDefinitionAction` | string | Policy definition action (effect) | Not specified |
| `policyDefinitionCategory` | string | Policy definition category | Not specified |
| **`policyDefinitionGroupNames`** | **string[]** | **Policy definition group names** | **Not specified** |
| **`policyDefinitionId`** | **string** | **Policy definition ID** | **Not specified** |
| `policyDefinitionName` | string | Policy definition name | Not specified |
| **`policyDefinitionReferenceId`** | **string** | **Reference ID for policy def in policy set** | **Not specified** |
| `policyDefinitionVersion` | string | Evaluated policy definition version | Not specified |
| `policyEvaluationDetails` | PolicyEvaluationDetails | Policy evaluation details | N/A |
| `policySetDefinitionCategory` | string | Policy set definition category | Not specified |
| `policySetDefinitionId` | string | Policy set definition ID | Not specified |
| `policySetDefinitionName` | string | Policy set definition name | Not specified |
| `policySetDefinitionOwner` | string | Policy set definition owner | Not specified |
| `policySetDefinitionParameters` | string | Policy set definition parameters | Not specified |
| `policySetDefinitionVersion` | string | Evaluated policy set definition version | Not specified |
| `resourceGroup` | string | Resource group name | Not specified |
| `resourceId` | string | Resource ID | Not specified |
| `resourceLocation` | string | Resource location | Not specified |
| `resourceTags` | string | List of resource tags | Not specified |
| `resourceType` | string | Resource type | Not specified |
| `subscriptionId` | string | Subscription ID | Not specified |
| `timestamp` | string (date-time) | Timestamp | N/A |

## Key Observation

**None of the string fields in the PolicyState schema have a documented maxLength constraint.**

The REST API specification uses bare `string` types throughout. This means:
1. Microsoft does not guarantee any maximum length
2. The values are bounded only by practical ARM resource path conventions
3. Any hardcoded column width in our database is an assumption, not a contract

## Sample Values from Official Documentation

### policyDefinitionId
```
"/providers/microsoft.authorization/policydefinitions/44452482-524f-4bf4-b852-0bff7cc4a3ed"
→ 89 characters (built-in)

"/subscriptions/fffedd8f-ffff-fffd-fffd-fffed2f84852/providers/microsoft.authorization/policydefinitions/24813039-7534-408a-9842-eb99f45721b1"
→ 139 characters (subscription-scoped)
```

### policyDefinitionReferenceId
```
"14799174781370023846" → 20 characters (auto-generated numeric hash)
"16797080356382393273" → 20 characters (auto-generated numeric hash)
null → nullable (not part of a policy set)
"allowedLocationsSQL" → 19 characters (user-defined in initiative)
"allowedLocationsVMs" → 19 characters (user-defined in initiative)
```

### policyDefinitionGroupNames
```
["myGroup"] → array with single short entry
```

## policyDefinitionReferenceId Source Analysis

From Azure Policy Initiative Definition Structure docs:
- This field is **user-defined** within initiative (policy set) definitions
- It's the `policyDefinitionReferenceId` property in the `policyDefinitions` array
- When not explicitly set by the user, Azure auto-generates a numeric hash (~20 chars)
- When user-defined, it can be **any arbitrary string** with no documented length limit
- Examples in Microsoft docs show short descriptive names

## ARM Resource ID Length Conventions

While not formally documented as a max, ARM resource IDs follow this pattern:
```
/subscriptions/{36-char-guid}/resourceGroups/{1-90 chars}/providers/{namespace}/{type}/{name}
```

Typical lengths:
- Simple resource: 100-200 chars
- Nested resource: 200-400 chars  
- Policy definition (subscription): ~130-140 chars
- Policy definition (management group): ~140-160 chars
- Policy assignment with long names: could exceed 200 chars

**Conclusion**: `String(500)` for `policy_definition_id` is likely sufficient for 99%+ of cases, but `String(1000)` provides better safety margin. The real risk is `policyDefinitionGroupNames` joined as a comma-separated string, which has no practical upper bound.

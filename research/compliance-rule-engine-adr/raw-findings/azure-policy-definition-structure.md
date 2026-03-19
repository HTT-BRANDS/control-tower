# Raw Finding: Azure Policy Definition Structure

## Source
- **Primary**: Microsoft Learn — Azure Policy Documentation
- **URL**: https://learn.microsoft.com/en-us/azure/governance/policy/concepts/definition-structure-basics
- **URL (Effects)**: https://learn.microsoft.com/en-us/azure/governance/policy/concepts/effect-basics
- **Last Updated**: March 4, 2025
- **Source Tier**: Tier 1 — Official Microsoft documentation

## Policy Definition JSON Structure
```json
{
  "properties": {
    "displayName": "string (max 128 chars)",
    "description": "string (max 512 chars)",
    "mode": "Indexed | all | <ResourceProvider>",
    "version": "{Major}.{Minor}.{Patch}",
    "metadata": {
      "version": "string",
      "category": "string",
      "preview": "boolean",
      "deprecated": "boolean"
    },
    "parameters": {
      "<paramName>": {
        "type": "array | string | boolean | integer | object | float",
        "metadata": { "description": "", "displayName": "", "strongType": "" },
        "defaultValue": "<value>",
        "allowedValues": ["<value1>", "<value2>"]
      }
    },
    "policyRule": {
      "if": { "<condition>" },
      "then": { "effect": "<effect>" }
    }
  }
}
```

## Supported Effects (11 total)
From the effects documentation left navigation:

| Effect | Description |
|--------|-------------|
| `addToNetworkGroup` | Add resource to a network group |
| `append` | Append fields to resource |
| `audit` | Log non-compliant resources (no enforcement) |
| `auditIfNotExists` | Audit if related/child resource doesn't exist |
| `deny` | Block non-compliant resource creation/update |
| `denyAction` | Block specific action operations |
| `deployIfNotExists` | Deploy a template if condition met and resource not exists |
| `disabled` | Policy disabled (no evaluation) |
| `manual` | Requires manual compliance assessment |
| `modify` | Add/replace/remove tags or properties |
| `mutate` | Mutate resources at admission time (Kubernetes) |

## Effect Interchangeability Rules
- `audit`, `deny`, and `modify`/`append` are often interchangeable
- `auditIfNotExists` and `deployIfNotExists` are often interchangeable
- `manual` is NOT interchangeable
- `disabled` is interchangeable with any effect

## Effect Evaluation Order
Azure Policy evaluates requests to create/update resources by:
1. Creating a list of all applicable assignments
2. Evaluating each definition
3. Processing effects in order before passing to Resource Provider

## Modes
### Resource Manager Modes
- `all`: Evaluate resource groups, subscriptions, and all resource types
- `indexed`: Only evaluate resource types that support tags and location

### Resource Provider Modes (Fully Supported)
- `Microsoft.Kubernetes.Data` — Kubernetes cluster policies
- `Microsoft.KeyVault.Data` — Key Vault vault and certificate policies
- `Microsoft.Network.Data` — VNet Manager custom membership

### Resource Provider Modes (Preview)
- `Microsoft.ManagedHSM.Data`
- `Microsoft.DataFactory.Data`
- `Microsoft.MachineLearningServices.v2.Data`
- `Microsoft.LoadTestService.Data`

## Policy Types
- `Builtin` — Microsoft-provided and maintained
- `Custom` — Customer-created
- `Static` — Regulatory Compliance (Microsoft Ownership)

## Condition Language Elements (policyRule.if)
- `field` — Access resource property via alias
- `value` — Access literal values
- `count` — Count array members meeting condition
- `not` — Logical negation
- `allOf` — Logical AND
- `anyOf` — Logical OR
- Operators: `equals`, `notEquals`, `like`, `notLike`, `match`, `matchInsensitively`,
  `notMatch`, `notMatchInsensitively`, `contains`, `notContains`, `in`, `notIn`,
  `containsKey`, `notContainsKey`, `less`, `lessOrEquals`, `greater`, `greaterOrEquals`,
  `exists`

## Parameter Functions in policyRule
- `[parameters('paramName')]` — Reference policy parameters
- `[field('fieldName')]` — Reference resource field
- `[resourceGroup().location]` — ARM template functions

## ADR Relevance — Cost of Reimplementation
Reimplementing Azure Policy would require:

1. **11 distinct effect behaviors** with different semantics and prerequisites
2. **Full alias system** for accessing nested Azure resource properties
3. **Array alias support** for array conditions (e.g., tags, allowed locations)
4. **Parameter system** with type validation, allowed values, and strong typing
5. **Condition operators** (20+ operators)
6. **ARM template functions** support in conditions
7. **Initiative definition structure** (grouping policies)
8. **Assignment structure** with scope, exemptions
9. **Exemption structure** for individual resource exemptions
10. **Versioning** with breaking-change semantics
11. **Compliance state engine** (Compliant, NonCompliant, Exempt, Unknown)
12. **Mode-based evaluation** (Indexed vs All)

**Estimated engineering effort**: 6-18 months for a production-quality implementation.
**Maintenance burden**: Ongoing — Azure Policy evolves frequently (mode additions, new effects).

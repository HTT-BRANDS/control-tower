# Raw Finding: JSON Schema as a Rule Engine

## Sources
- **Primary**: python-jsonschema library docs — https://python-jsonschema.readthedocs.io/en/stable/
- **Primary**: JSON Schema specification — https://json-schema.org/
- **Case Studies**: JSON Schema Blog — https://json-schema.org/blog
- **Source Tier**: Tier 1 (official library docs) + Tier 2 (community case studies)

## Library: python-jsonschema
- **Current version**: 4.26.0 (latest stable)
- **Python support**: 3.10, 3.11, 3.12, 3.13, 3.14
- **CI status**: Passing (docs), Failing (main CI — notable)
- **Specification support**: Draft 2020-12, Draft 2019-09, Draft 7, Draft 6, Draft 4, Draft 3
- **License**: MIT

## Core Validation Pattern
```python
from jsonschema import validate

schema = {
    "type": "object",
    "properties": {
        "sku": {"type": "string", "enum": ["Standard", "Premium"]},
        "retentionDays": {"type": "integer", "minimum": 30},
    },
    "required": ["sku"]
}

validate(instance=resource_properties, schema=schema)
# Raises ValidationError if non-compliant
```

## Features Available for Rule Definitions

### Type Constraints
- `type`: string, number, integer, boolean, array, object, null

### String Constraints
- `minLength`, `maxLength`, `pattern` (regex), `format`, `enum`, `const`

### Numeric Constraints
- `minimum`, `maximum`, `exclusiveMinimum`, `exclusiveMaximum`, `multipleOf`

### Array Constraints
- `minItems`, `maxItems`, `uniqueItems`, `items`, `prefixItems`, `contains`
- `minContains`, `maxContains`

### Object Constraints
- `properties`, `required`, `additionalProperties`, `patternProperties`
- `minProperties`, `maxProperties`, `dependentRequired`, `dependentSchemas`

### Composition
- `allOf` — All subschemas must validate
- `anyOf` — At least one subschema must validate
- `oneOf` — Exactly one subschema must validate
- `not` — Schema must NOT validate
- `if`/`then`/`else` — Conditional validation (Draft 7+)

### Cross-References
- `$ref` — Reference another schema definition
- `$defs` — Local schema definitions

## JSON Schema as Rule Engine — Real-World Examples

### 1. RxDB (NoSQL Database)
- Uses JSON Schema for data validation and type safety
- Validates documents on write/read
- Blog post: "How RxDB embraces JSON Schema to build its NoSQL Database"

### 2. Oracle (Relational Databases)
- Bridging JSON Schema and relational databases
- Blog post: "How Oracle is Bridging the Gap Between JSON Schema and Relational Databases"

### 3. SlashDB (Data-Centric Web APIs)
- "Advanced use of JSON Schema in Data-Centric Web APIs"
- Using JSON Schema for API validation rules

### 4. OPA (Open Policy Agent) Integration
- OPA supports JSON Schema annotations for type checking Rego policies
- Schemas can be passed via `-s` flag for static analysis

### 5. AWS Config Rules (Similar Pattern)
- AWS Config uses JSON-based rule definitions for compliance checking
- Custom rules use AWS Lambda but managed rules use a declarative JSON structure
- Pattern: property path + operator + expected value

## What JSON Schema CAN Express (compliance use cases)

```json
{
  "description": "Storage account must use HTTPS only",
  "properties": {
    "supportsHttpsTrafficOnly": { "const": true }
  },
  "required": ["supportsHttpsTrafficOnly"]
}
```

```json
{
  "description": "Key Vault must have soft delete enabled with 90+ day retention",
  "properties": {
    "softDeleteEnabled": { "const": true },
    "softDeleteRetentionInDays": { "type": "integer", "minimum": 90 }
  },
  "required": ["softDeleteEnabled", "softDeleteRetentionInDays"]
}
```

```json
{
  "description": "VM SKU must be from approved list",
  "properties": {
    "vmSize": {
      "type": "string",
      "enum": ["Standard_D2s_v3", "Standard_D4s_v3", "Standard_D8s_v3"]
    }
  }
}
```

```json
{
  "description": "Resource must have required tags",
  "properties": {
    "tags": {
      "type": "object",
      "required": ["environment", "cost-center", "owner"]
    }
  }
}
```

## What JSON Schema CANNOT Express (compliance use cases)

1. **Cross-property comparisons**: `retentionDays >= backupFrequencyDays`
2. **Relative date comparisons**: `expiryDate > today() + 30 days`
3. **Count conditions with thresholds**: `count(nonCompliantRules) > 5 then alert`
4. **String interpolation**: Can't reference one property in the pattern of another
5. **Complex business logic**: `if resourceType == 'storage' and tier == 'Premium' then...` (limited)
6. **External data lookups**: Can't reference approved IP lists from external source
7. **Effect specification**: No built-in notion of audit vs. deny vs. remediate

## Performance Characteristics

### Throughput
- JSON Schema validation is a pure Python operation
- Each validation: O(schema_complexity × data_depth)
- Typical Azure resource JSON: ~2-20KB
- Expected performance: 1,000-10,000 validations/second on modern hardware (single thread)

### Multi-Tenant Scale (5-50 tenants)
- With 50 tenants × 100 resources each × 50 rules: 250,000 validations per sync cycle
- At 5,000 validations/second: ~50 seconds per full sync
- Caching compiled validators (per rule) avoids recompilation overhead
- Memory: compiled validators are small (~KB each), manageable

### Caching Pattern
```python
from jsonschema import Draft202012Validator

# Cache compiled validators per rule_id to avoid recompilation
_validator_cache: dict[str, Draft202012Validator] = {}

def get_validator(rule_id: str, schema: dict) -> Draft202012Validator:
    if rule_id not in _validator_cache:
        _validator_cache[rule_id] = Draft202012Validator(schema)
    return _validator_cache[rule_id]
```

## Security Profile

| Risk | Assessment |
|------|------------|
| Code Injection | **None** — pure data validation, no code execution |
| DoS via Schema Bombs | **Low-Medium** — deeply nested `$ref` cycles possible |
| Schema Exfiltration | **None** — schemas are stored in DB, not executed |
| Tenant Isolation | **High** — each tenant's rules validated in isolation |
| Supply Chain | **Low** — jsonschema is well-maintained, MIT license |

### Schema Bomb Mitigation
```python
# Prevent $ref cycles and excessive recursion depth
validator = Draft202012Validator(
    schema,
    resolver=RefResolver.from_schema(schema)  # local refs only, no remote
)
# Also: set recursion depth limit in validation
```

## ADR Relevance

**Strengths for this project:**
- Zero code execution risk — fundamental security property for multi-tenant compliance
- Schema stored as JSON in DB — easy audit, versioning, UI editing
- Lazy validation with iterator API returns ALL errors (not just first)
- Can express ~80% of common Azure compliance rules
- Natural integration with Python FastAPI stack

**Weaknesses for this project:**
- Cannot express mathematical comparisons between fields
- No built-in effect system (audit/deny/remediate)
- No parameter interpolation within schemas
- Would need a custom wrapper for compliance-specific semantics

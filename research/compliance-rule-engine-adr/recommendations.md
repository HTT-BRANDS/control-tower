# Project-Specific Recommendations — Compliance Rule Engine ADR

## Executive Decision

**Recommended Option: JSON Schema Rule Definitions (Option 1)**
with a defined extension strategy to OPA/Rego for future richness.

**Eliminate from consideration: Python Expression Evaluator (Option 2)**
due to CVE-2026-32640 (CVSS 8.7/10, network-exploitable, no-auth, no-user-interaction).

---

## Rationale Summary

### Why JSON Schema Wins

1. **Security is the paramount concern** — This is a compliance rule engine. It must be trustworthy. An injection vulnerability in a compliance product is an existential threat to the product's credibility. JSON Schema is provably injection-safe.

2. **Covers ~80% of compliance use cases** — Analysis of common Azure governance rules (encryption, tags, SKU allowlists, retention periods, HTTPS enforcement, network restrictions) shows that the vast majority are expressible in JSON Schema.

3. **Fits the existing stack perfectly** — Python-native library (jsonschema 4.26.0), JSON stored in PostgreSQL, FastAPI integration is trivial, SQLAlchemy models extend naturally.

4. **Low implementation cost** — 1-2 weeks to implement the wrapper, validation engine, and DB schema. Option 3 would take 6-18 months.

5. **Auditable and UI-friendly** — JSON rules can be displayed in a JSON editor, version-controlled in the DB, and reviewed by non-developers.

### Why Option 2 Must Be Eliminated

**CVE-2026-32640 (simpleeval), published March 13, 2026, CVSS 8.7:**
- Attack Vector: **Network** — no physical access needed
- Attack Complexity: **Low** — no specialized knowledge
- Privileges Required: **None** — any tenant can trigger it
- User Interaction: **None** — fully automated exploitation

In a multi-tenant compliance SaaS, tenants submit rule expressions. If the evaluation context
includes any Python objects (which it must — the Azure resource properties), a malicious tenant
can traverse module attributes to reach `os.system()`. **This is weaponizable remote code execution.**

Even with simpleeval 1.0.5 (patched), the library has shown a pattern of recurring security
issues (see GitHub issues #81, #154, #166, #171). The GHSA advisory from February 2026 was
resolved by #171 which added module access restriction — but the library's fundamental design
(dynamic attribute access on arbitrary Python objects) creates an ongoing attack surface.

`ast.literal_eval` is equally unsuitable: too limited to evaluate comparison operators, and
explicitly documented by Python as unsafe on untrusted input (memory exhaustion, DoS).

### Why Option 3 Is Deferred, Not Eliminated

Azure Policy's definition language is sophisticated and well-designed, but:
- Reimplementing it faithfully is a 6-18 month project
- You already **use** Azure Policy natively via your sync infrastructure — this is complementary, not a replacement
- For the **custom** rules use case (tenant-specific rules beyond what Azure Policy provides), a simpler declarative approach is better
- If full Azure Policy cloning becomes necessary in the future, OPA/Rego (Option 4) is a better foundation than building from scratch

---

## Prioritized Action Items

### Immediate (Sprint 1-2)

#### 1. Create `CustomComplianceRule` model
```python
class CustomComplianceRule(Base):
    __tablename__ = "custom_compliance_rules"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = Column(String(36), ForeignKey("tenants.id"), nullable=False)
    rule_name: Mapped[str] = Column(String(255), nullable=False)
    rule_description: Mapped[str] = Column(Text, nullable=True)
    rule_category: Mapped[str] = Column(String(100), nullable=False, default="Custom")
    resource_type: Mapped[str] = Column(String(255), nullable=False)  # e.g., "Microsoft.Storage/storageAccounts"
    severity: Mapped[str] = Column(String(20), nullable=False, default="Medium")  # High/Medium/Low
    effect: Mapped[str] = Column(String(20), nullable=False, default="audit")  # audit/deny
    schema: Mapped[dict] = Column(JSONB, nullable=False)  # The JSON Schema rule
    is_active: Mapped[bool] = Column(Boolean, default=True)
    created_by: Mapped[str] = Column(String(255), nullable=True)
    created_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    schema_version: Mapped[int] = Column(Integer, default=1)
```

#### 2. Implement `JsonSchemaRuleEngine`
```python
from jsonschema import Draft202012Validator, ValidationError, SchemaError
from jsonschema.exceptions import best_match
import re

class JsonSchemaRuleEngine:
    MAX_SCHEMA_SIZE_BYTES = 65_536  # 64KB
    MAX_PATTERN_LENGTH = 500

    def __init__(self):
        self._validator_cache: dict[str, Draft202012Validator] = {}
    
    def validate_rule_schema(self, schema: dict) -> list[str]:
        """Validate a rule schema before storing it. Returns error messages."""
        errors = []
        
        # Size limit
        import json
        schema_str = json.dumps(schema)
        if len(schema_str.encode()) > self.MAX_SCHEMA_SIZE_BYTES:
            errors.append(f"Schema exceeds maximum size of {self.MAX_SCHEMA_SIZE_BYTES} bytes")
        
        # No remote $ref (security: prevent SSRF via schema loading)
        if self._has_remote_refs(schema):
            errors.append("Remote $ref URLs are not permitted in rule schemas")
        
        # Validate pattern lengths (ReDoS mitigation)
        if pattern_errors := self._check_patterns(schema):
            errors.extend(pattern_errors)
        
        # Validate it's a valid JSON Schema
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as e:
            errors.append(f"Invalid JSON Schema: {e.message}")
        
        return errors
    
    def evaluate(
        self, 
        rule_id: str,
        schema: dict, 
        resource_properties: dict
    ) -> list[dict]:
        """
        Evaluate a resource against a rule schema.
        Returns list of violation dicts with message and path.
        """
        validator = self._get_cached_validator(rule_id, schema)
        violations = []
        for error in validator.iter_errors(resource_properties):
            violations.append({
                "message": error.message,
                "path": list(error.absolute_path),
                "schema_path": list(error.absolute_schema_path),
            })
        return violations
    
    def _get_cached_validator(self, rule_id: str, schema: dict) -> Draft202012Validator:
        if rule_id not in self._validator_cache:
            self._validator_cache[rule_id] = Draft202012Validator(
                schema,
                format_checker=None  # Disable format checking (performance + security)
            )
        return self._validator_cache[rule_id]
    
    def _has_remote_refs(self, schema: dict) -> bool:
        """Check for any remote $ref URLs recursively."""
        if isinstance(schema, dict):
            if "$ref" in schema:
                ref = schema["$ref"]
                if ref.startswith("http://") or ref.startswith("https://"):
                    return True
            return any(self._has_remote_refs(v) for v in schema.values())
        if isinstance(schema, list):
            return any(self._has_remote_refs(item) for item in schema)
        return False
    
    def _check_patterns(self, schema: dict, path: str = "") -> list[str]:
        """Check regex patterns for excessive length (ReDoS mitigation)."""
        errors = []
        if isinstance(schema, dict):
            if "pattern" in schema and isinstance(schema["pattern"], str):
                if len(schema["pattern"]) > self.MAX_PATTERN_LENGTH:
                    errors.append(f"Pattern at {path or 'root'} exceeds max length of {self.MAX_PATTERN_LENGTH}")
            for key, value in schema.items():
                errors.extend(self._check_patterns(value, f"{path}.{key}"))
        elif isinstance(schema, list):
            for i, item in enumerate(schema):
                errors.extend(self._check_patterns(item, f"{path}[{i}]"))
        return errors
```

#### 3. Add API routes for rule management
- `POST /api/v1/compliance/custom-rules` — Create rule (validates schema first)
- `GET /api/v1/compliance/custom-rules` — List tenant rules
- `PUT /api/v1/compliance/custom-rules/{id}` — Update rule
- `DELETE /api/v1/compliance/custom-rules/{id}` — Delete rule
- `POST /api/v1/compliance/custom-rules/{id}/test` — Test rule against a sample resource

#### 4. Integrate with compliance sync
Extend `app/core/sync/compliance.py` to evaluate custom rules during sync:
```python
async def evaluate_custom_rules(
    tenant_id: str, 
    resources: list[dict],
    rule_engine: JsonSchemaRuleEngine
) -> list[CustomRuleViolation]:
    """Run all active custom rules for tenant against their resources."""
    ...
```

---

### Short-Term (Sprint 3-4)

#### 5. Rule versioning and history
- Track schema changes with `schema_history` JSONB column or separate history table
- Allow rollback to previous versions

#### 6. Rule testing UI
- Provide a "dry run" mode where admins can test rules against existing resources before activation
- Return a preview of violations without creating PolicyState records

#### 7. Rule import from Azure Policy format
- Allow importing existing Azure Policy definitions and mapping condition language to JSON Schema
- Cover the most common built-in Azure Policy patterns automatically

---

### Medium-Term (Sprint 5+)

#### 8. Identify expressiveness gaps
Monitor which use cases tenants request that JSON Schema can't handle.
Common candidates:
- Cross-property comparisons (e.g., `minTLSVersion >= 1.2`)
- Date-relative rules (e.g., `certificateExpiry > now + 30days`)
- Count thresholds (e.g., `allowedIPCount < 10`)

#### 9. Evaluate OPA/Rego for advanced rules
If expressiveness gaps become significant, evaluate OPA as a **complementary** engine for
advanced rules that JSON Schema cannot express. OPA has no code execution model, is CNCF
Graduated, and is explicitly designed for this use case.

Integration pattern:
```python
# OPA sidecar or subprocess for advanced rules
import subprocess
result = subprocess.run(
    ["opa", "eval", "-d", "policy.rego", "-i", "input.json", "data.compliance.deny"],
    capture_output=True, text=True
)
```

#### 10. Consider cel-python (Common Expression Language)
Google's CEL (Common Expression Language) is used by Firebase, Google Cloud, and is increasingly
adopted for safe expression evaluation. `cel-python` provides a Python implementation with:
- No code execution
- Mathematical operations
- String functions
- Safe sandbox by design
- CNCF specification

This could cover the gap between JSON Schema (too limited) and simpleeval (too dangerous) for
cross-property comparisons without the injection risks of simpleeval.

---

## JSON Schema Rule Examples for Azure Governance

These examples demonstrate the rules that CAN be expressed in JSON Schema:

```json
{
  "rule_name": "storage-https-only",
  "description": "Storage accounts must require HTTPS-only traffic",
  "resource_type": "Microsoft.Storage/storageAccounts",
  "severity": "High",
  "schema": {
    "type": "object",
    "properties": {
      "supportsHttpsTrafficOnly": { "const": true }
    },
    "required": ["supportsHttpsTrafficOnly"]
  }
}
```

```json
{
  "rule_name": "keyvault-soft-delete",
  "description": "Key Vaults must have soft delete enabled with ≥90 day retention",
  "resource_type": "Microsoft.KeyVault/vaults",
  "severity": "High",
  "schema": {
    "type": "object",
    "properties": {
      "enableSoftDelete": { "const": true },
      "softDeleteRetentionInDays": { "type": "integer", "minimum": 90 }
    },
    "required": ["enableSoftDelete", "softDeleteRetentionInDays"]
  }
}
```

```json
{
  "rule_name": "vm-approved-sizes",
  "description": "Virtual machines must use approved SKUs",
  "resource_type": "Microsoft.Compute/virtualMachines",
  "severity": "Medium",
  "schema": {
    "type": "object",
    "properties": {
      "hardwareProfile": {
        "properties": {
          "vmSize": {
            "type": "string",
            "enum": ["Standard_D2s_v3", "Standard_D4s_v3", "Standard_D8s_v3", "Standard_D16s_v3"]
          }
        },
        "required": ["vmSize"]
      }
    },
    "required": ["hardwareProfile"]
  }
}
```

```json
{
  "rule_name": "required-tags",
  "description": "All resources must have required governance tags",
  "resource_type": "*",
  "severity": "Low",
  "schema": {
    "type": "object",
    "properties": {
      "tags": {
        "type": "object",
        "required": ["environment", "cost-center", "owner", "team"]
      }
    },
    "required": ["tags"]
  }
}
```

```json
{
  "rule_name": "sql-tls-minimum",
  "description": "SQL servers must use TLS 1.2 or higher",
  "resource_type": "Microsoft.Sql/servers",
  "severity": "High",
  "schema": {
    "type": "object",
    "properties": {
      "minimalTlsVersion": {
        "type": "string",
        "enum": ["1.2", "1.3"]
      }
    },
    "required": ["minimalTlsVersion"]
  }
}
```

---

## Risk Mitigation Checklist for Option 1

- [ ] Disable remote `$ref` resolution (prevent SSRF)
- [ ] Enforce schema size limit (max 64KB recommended)
- [ ] Validate regex pattern length (prevent ReDoS)
- [ ] Sanitize rule names and descriptions (prevent XSS in UI)
- [ ] Enforce tenant_id FK on all custom rules (prevent cross-tenant access)
- [ ] Add rate limiting on rule evaluation endpoint (prevent compute DoS)
- [ ] Cache compiled validators per rule_id (prevent recompilation DoS)
- [ ] Log all rule evaluations with tenant context for audit
- [ ] Add RBAC: only admins can create/modify rules (not all tenant users)
- [ ] Set max schema nesting depth (prevent deep recursion)
- [ ] Add integration tests confirming tenant isolation

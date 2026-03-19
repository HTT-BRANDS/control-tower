# Multi-Dimensional Analysis — Compliance Rule Engine Approaches

## Approach Comparison Matrix

| Dimension | Option 1: JSON Schema | Option 2: Python Expr Eval | Option 3: Azure Policy Clone |
|-----------|----------------------|---------------------------|------------------------------|
| **Security** | 🟢 Excellent | 🔴 Critical Risk | 🟡 Medium |
| **Implementation Complexity** | 🟢 Low | 🟡 Medium | 🔴 Very High |
| **Expressiveness** | 🟡 Medium | 🟢 High | 🟢 Very High |
| **Maintenance** | 🟢 Low | 🟡 Medium | 🔴 High |
| **Stability** | 🟢 High | 🔴 Low (CVE) | 🟡 Medium |
| **Cost** | 🟢 Low | 🟡 Medium | 🔴 Very High |
| **Compatibility** | 🟢 Native Python | 🟢 Native Python | 🟡 Custom |
| **Tenant Safety** | 🟢 Complete isolation | 🔴 Injection risk | 🟡 Depends on impl |

---

## 🔴 SECURITY ANALYSIS (Primary Decision Factor)

### Option 1: JSON Schema
**Risk Level: MINIMAL**

JSON Schema is a data-validation specification. Rule evaluation involves:
1. Loading a JSON schema document from the database
2. Running `jsonschema.validate(resource_properties, schema)`
3. Collecting `ValidationError` objects

There is **no code execution**. The schema is pure data. A malicious tenant cannot:
- Execute OS commands
- Import Python modules
- Access file system or network
- Escape the validation context
- Affect other tenants

**Residual risks:**
- **ReDoS**: Regex patterns in `pattern` keyword could be expensive. Mitigate with `re` timeout wrapper or pattern size limit.
- **Schema bombs**: Deeply nested `$ref` cycles could cause recursion. Mitigate by disabling remote `$ref` resolution (local schemas only) and setting max recursion depth.
- **DoS via large schemas**: Mitigate with schema size limits (e.g., max 64KB per rule).

**STRIDE for Option 1:**
| Threat | Risk | Mitigation |
|--------|------|-----------|
| Spoofing | Low | Rule stored with tenant_id FK; auth enforced at API layer |
| Tampering | Low | DB integrity; schema versioning with audit log |
| Repudiation | Low | Audit log records who created/modified each rule |
| Information Disclosure | Low | Tenant isolation via DB row-level security |
| Denial of Service | Low | Schema size limits, regex timeout, recursion limit |
| Elevation of Privilege | **None** | No code execution path |

---

### Option 2: Python Expression Evaluator (simpleeval / ast.literal_eval)

**Risk Level: CRITICAL 🔴**

#### CVE-2026-32640 (GHSA-44vg-5wv2-h2hg) — Published March 13, 2026
- **CVSS v4**: 8.7/10 (HIGH)
- **Attack Vector**: Network (no physical access required)
- **Attack Complexity**: Low
- **Privileges Required**: None
- **User Interaction**: None
- **Impact**: High Integrity on vulnerable system
- **CWE**: CWE-94 (Code Injection), CWE-915 (Improperly Controlled Object Attribute Modification)

**What the CVE means for a compliance rule engine:**

In a multi-tenant compliance SaaS, tenants submit rule expressions that are evaluated by the
engine. If the evaluation context includes any Python objects with module attributes (e.g., a
`resource` object that includes helper methods from modules like `pathlib`, `os.path`, `statistics`,
or `numpy`), a malicious tenant can:

1. Traverse the attribute chain: `resource.helper.sys.modules['os']`
2. Access `os.system()`, `subprocess.call()`, etc.
3. Execute arbitrary shell commands **in the context of the compliance worker process**
4. Potentially access: other tenant data, database credentials, Azure service principal tokens,
   Key Vault secrets, network sidecar metadata, and more.

**This is a weaponizable remote code execution vulnerability in multi-tenant SaaS context.**

#### ast.literal_eval — Separate Concerns
Even without simpleeval, `ast.literal_eval` is:
- **Too limited**: Cannot evaluate operators (`==`, `>=`, `and`, `or`) — useless for compliance rules
- **Still unsafe on untrusted input** (Python docs explicitly): memory exhaustion, interpreter crash

**STRIDE for Option 2:**
| Threat | Risk | Mitigation (if any) |
|--------|------|---------------------|
| Spoofing | Medium | Standard auth |
| Tampering | **Critical** | CVE-2026-32640 — no reliable mitigation at rule authoring time |
| Repudiation | Medium | Audit log |
| Information Disclosure | **Critical** | Sandbox escape exposes all process memory, env vars, secrets |
| Denial of Service | **High** | Memory exhaustion via crafted expressions (Python docs warning) |
| Elevation of Privilege | **Critical** | OS module access → full host access |

**No amount of input validation reliably prevents all exploitation paths when the underlying library has an actively exploited sandbox escape CVE.**

---

### Option 3: Azure Policy Clone
**Risk Level: MEDIUM (but complexity creates its own risks)**

A custom reimplementation of Azure Policy's JSON-based condition language would:
- Be declarative (no code execution if done correctly)
- Require implementing all 20+ condition operators correctly
- Require implementing all 11 effects with their distinct evaluation semantics
- Be a high-complexity system with many edge cases

**Security risks of reimplementation:**
- Logic bugs in condition evaluation → bypass of compliance rules (false negatives)
- Off-by-one errors in `less`/`lessOrEquals` → policy bypass
- Alias resolution errors → wrong resource property evaluated
- Array alias edge cases → rules apply to wrong array elements
- Effect ordering bugs → expected `deny` becomes `audit`

**STRIDE for Option 3:**
| Threat | Risk | Mitigation |
|--------|------|-----------|
| Spoofing | Low | Standard auth |
| Tampering | Medium | Custom parser bugs could allow policy bypass |
| Repudiation | Low | Audit log |
| Information Disclosure | Low | No code execution if implemented correctly |
| Denial of Service | Medium | Complex condition evaluation could be slow |
| Elevation of Privilege | Medium | Parser bugs could allow privilege escalation via policy bypass |

---

## 💰 COST ANALYSIS

### Option 1: JSON Schema
- **Implementation**: 1-2 weeks (library + wrapper for compliance semantics)
- **Ongoing**: Minimal — jsonschema library is stable, MIT licensed, well-maintained
- **Storage**: JSON rules in existing PostgreSQL DB (already have this)
- **Compute**: Low — pure Python, no extra services
- **Total estimated cost**: Low

### Option 2: Python Expression Evaluator
- **Implementation**: 2-4 weeks (evaluator + security hardening)
- **Security hardening**: Ongoing — CVEs require version management, regression testing
- **Security incident risk**: HIGH — a breach from CVE-2026-32640 could cost millions
- **Compliance risk**: Running with a CVSS 8.7 CVE in a compliance product is an existential risk
- **Total estimated cost**: Medium initially, **Very High when breach risk is factored in**

### Option 3: Azure Policy Clone
- **Implementation**: 6-18 months of senior engineering time
- **Testing**: Extensive property-based testing to match Azure behavior exactly
- **Ongoing**: Must track Azure Policy changes (new effects, new operators)
- **Risk of not being Azure-compatible**: High — tenants may expect Azure Policy behavior
- **Total estimated cost**: Very High

---

## 🔧 IMPLEMENTATION COMPLEXITY

### Option 1: JSON Schema
```python
# Core implementation sketch
from jsonschema import Draft202012Validator, ValidationError
from typing import Iterator

class JsonSchemaRuleEngine:
    def __init__(self):
        self._validator_cache: dict[str, Draft202012Validator] = {}
    
    def evaluate(self, rule_schema: dict, resource_properties: dict) -> list[str]:
        """Returns list of violation messages."""
        validator = self._get_validator(rule_schema)
        return [
            error.message 
            for error in validator.iter_errors(resource_properties)
        ]
    
    def _get_validator(self, schema: dict) -> Draft202012Validator:
        schema_key = str(schema.get("$id", id(schema)))
        if schema_key not in self._validator_cache:
            self._validator_cache[schema_key] = Draft202012Validator(schema)
        return self._validator_cache[schema_key]
```

**Complexity**: Low. The library does the heavy lifting.

### Option 2: Python Expression Evaluator
```python
# Would require (simplified)
from simpleeval import EvalWithCompoundTypes  # CVE-2026-32640 affected

class ExpressionRuleEngine:
    SAFE_FUNCTIONS = {"len": len, "str": str, "int": int}
    
    def evaluate(self, expression: str, context: dict) -> bool:
        # DANGER: simpleeval has CVE-2026-32640
        # Even with allowlist, object attribute chains can escape sandbox
        evaluator = EvalWithCompoundTypes(
            functions=self.SAFE_FUNCTIONS,
            names=context  # <-- if context contains any objects with module attrs, EXPLOITABLE
        )
        return evaluator.eval(expression)
```

**Complexity**: Medium to implement, Very High to secure reliably.

### Option 3: Azure Policy Clone
Requires implementing from scratch:
1. Policy definition parser and validator
2. Resource alias resolver (100+ Azure-specific aliases)
3. 20+ condition operators with exact Azure semantics
4. 11 effect handlers with their distinct pre-conditions and behaviors
5. Parameter interpolation engine
6. Array alias evaluation with `count`, `where`, `all`, `any`
7. Initiative aggregation
8. Assignment scope resolution
9. Exemption handling
10. Compliance state aggregation

**Complexity**: Very High. Estimated 6-18 months.

---

## 📈 EXPRESSIVENESS ANALYSIS

### What compliance rules need to express:

| Rule Type | Option 1 | Option 2 | Option 3 |
|-----------|----------|----------|----------|
| Equality check (value == constant) | ✅ `const` | ✅ | ✅ |
| Required field present | ✅ `required` | ✅ | ✅ |
| Value in allowed list | ✅ `enum` | ✅ | ✅ |
| String pattern match | ✅ `pattern` | ✅ | ✅ `like`, `match` |
| Numeric range check | ✅ `minimum`/`maximum` | ✅ | ✅ `less`/`greater` |
| Required tags | ✅ `required` on `tags` | ✅ | ✅ |
| Cross-property comparison | ❌ | ✅ | ✅ |
| Relative date check | ❌ | ✅ | ✅ (limited) |
| Count conditions | ❌ (basic) | ✅ | ✅ `count` |
| Effect system (audit/deny/remediate) | ❌ (must wrap) | ❌ (must wrap) | ✅ native |
| Parameterized rules | ❌ (manual) | ✅ | ✅ native |
| Conditional logic | ✅ `if`/`then`/`else` | ✅ | ✅ |

**Coverage for typical Azure governance rules**: Option 1 covers ~75-85%, Option 2 ~95%, Option 3 ~100%.

---

## 🏭 STABILITY & MATURITY

| Metric | Option 1 (JSON Schema) | Option 2 (simpleeval) | Option 3 (Custom) |
|--------|------------------------|----------------------|-------------------|
| **Library version** | 4.26.0 (stable) | Pre-1.0 history → 1.0.5 | N/A |
| **CVE history** | None | CVE-2026-32640 (CVSS 8.7) | N/A (new code) |
| **Spec maturity** | Draft 2020-12 (final) | N/A | N/A |
| **Breaking changes** | Low (stable spec) | High (v2.0 redesign) | High (your changes) |
| **Long-term support** | High (JSON Schema is ISO standard path) | Low (small maintainer) | Depends on team |
| **Community** | Large (JSON Schema everywhere) | Small (579 stars) | None |

---

## 🔄 COMPATIBILITY WITH PROJECT

This project:
- **Stack**: Python/FastAPI, PostgreSQL (SQLAlchemy), Azure
- **Multi-tenant**: 5-50 tenants (current), potentially more
- **Compliance data**: Azure Policy state synced from Azure (policy_states table)
- **Existing pattern**: Rules currently come from Azure Policy directly

| Compatibility Factor | Option 1 | Option 2 | Option 3 |
|---------------------|----------|----------|----------|
| Python native | ✅ | ✅ | Custom |
| DB-storable rules | ✅ JSON in PostgreSQL | ✅ strings in PostgreSQL | ✅ JSON |
| FastAPI integration | ✅ Trivial | ✅ | Custom |
| Existing SQLAlchemy models | ✅ Add `custom_rules` table | ✅ | ✅ |
| UI editability | ✅ JSON editor | ⚠️ Expression editor | ⚠️ Complex |
| Azure Policy parallel | ✅ Complement | ✅ Complement | 🔴 Competes |
| Audit trail | ✅ Standard | ✅ Standard | ✅ Standard |

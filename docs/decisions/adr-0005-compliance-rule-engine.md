---
status: proposed
date: 2026-03-19
decision-makers: Solutions Architect 🏛️, Security Auditor 🛡️, Pack Leader 🐺
consulted: web-puppy-e25e65 (research agent), Compliance Domain Expert
informed: All agents, Platform Engineering
---

# Use JSON Schema for Custom Compliance Rule Definitions

## Context and Problem Statement

The Azure Governance Platform currently evaluates compliance via synced Azure Policy state
(`ComplianceSnapshot`, `PolicyState` models). Tenants have requested the ability to define
**custom compliance rules** — rules that go beyond native Azure Policy, such as organisation-specific
naming conventions, approved SKU lists, required tag sets, and minimum retention periods. These
user-defined rules must be evaluated against Azure resource properties in a **multi-tenant SaaS
environment** (5–50 tenants) where any tenant could be adversarial. How should the rule definition
and evaluation system be implemented?

## Decision Drivers

- **Security (K.O. criterion)**: Multi-tenant SaaS — rules authored by tenant admins must not create injection vectors; a single compromised rule must not affect other tenants or the host process
- **Auditability**: Rule definitions must be stored, versioned, and auditable (who created what rule when)
- **Expressiveness**: Rules must cover ~80%+ of common Azure governance scenarios (encryption, tags, SKUs, retention, network configuration)
- **Implementation velocity**: The compliance module already exists; the extension should be deliverable in 1–2 sprints
- **Maintainability**: The approach must be sustainable without deep security expertise in the maintenance path
- **Compatibility**: Must integrate naturally with the existing Python/FastAPI/PostgreSQL stack

## Considered Options

1. **JSON Schema rule definitions stored in DB** — declarative JSON Schema describing what Azure resource properties must match; evaluated via `jsonschema` library (no code execution)
2. **Python expression evaluator** (`simpleeval` / `ast.literal_eval`) — tenant-authored expressions evaluated at runtime; richer conditions but with code execution
3. **Azure Policy definition language clone** — full reimplementation of Azure Policy's condition language with effects, aliases, parameter system
4. **OPA/Rego** (considered and noted for future) — CNCF Graduated declarative policy engine; deferred due to Python integration complexity at current scale

## Decision Outcome

**Chosen option: Option 1 — JSON Schema rule definitions**, because it is the only option that
satisfies the **security K.O. criterion** while meeting expressiveness requirements for ~80% of
real-world Azure governance rules, at low implementation cost within the existing stack.

**Option 2 (Python expression evaluator) is eliminated** due to CVE-2026-32640 (CVSS 8.7/10,
network-exploitable, zero-auth, zero-user-interaction) — a live, active sandbox escape
vulnerability in `simpleeval` published March 13, 2026 (6 days before this ADR).

**Option 3 (Azure Policy clone) is deferred** — full reimplementation is estimated at 6–18 months
and creates a competing system to the native Azure Policy already integrated into this platform.

### Consequences

**Good:**
- No code execution path in the compliance rule evaluation pipeline → eliminates injection attack surface
- Rule definitions are pure JSON data — storable in PostgreSQL, version-tracked, renderable in UI
- `jsonschema` 4.26.0 is a mature, MIT-licensed library with zero CVEs and Python 3.10–3.14 support
- Covers ~80% of common Azure governance rules (see examples in recommendations.md)
- 1–2 sprint implementation timeline
- Natural integration: JSON rules stored alongside existing `compliance_snapshots`/`policy_states` tables
- Multi-tenant isolation is trivially enforced via `tenant_id` FK

**Bad:**
- Cannot express cross-property comparisons (`fieldA >= fieldB`)
- Cannot express date arithmetic (`expiryDate > now() + 30d`)
- No built-in effect system — must wrap with custom audit/deny semantics
- No parameter interpolation within schemas (must use static values)
- ~20% of conceivable governance rules may require a future upgrade to OPA

### Confirmation

Implementation is confirmed when:
1. `custom_compliance_rules` table exists with `tenant_id`, `schema` (JSONB), `severity`, `effect`, `resource_type` columns
2. `JsonSchemaRuleEngine.evaluate()` passes all unit tests including tenant isolation tests
3. Security review confirms no code execution path in the validation pipeline
4. Remote `$ref` resolution is disabled (SSRF prevention confirmed by test)
5. Schema size and pattern length limits enforced (ReDoS mitigation confirmed by test)

## STRIDE Security Analysis

| Threat Category | Risk Level | Mitigation |
|-----------------|-----------|------------|
| **Spoofing** | Low | Rules stored with `tenant_id` FK; RBAC limits rule creation to tenant admins; Azure AD auth required on all API endpoints |
| **Tampering** | Low | DB integrity constraints; rule versioning with audit log; schema validation on write prevents storing invalid schemas |
| **Repudiation** | Low | All rule create/update/delete operations logged to `audit_log` with `created_by`; evaluation results timestamped |
| **Information Disclosure** | Low | Tenant isolation enforced at DB level via `tenant_id` FK and row-level filtering in all queries; no cross-tenant rule access |
| **Denial of Service** | Low–Medium | Schema size limit (64KB), regex pattern length limit (500 chars), validator caching (prevents recompilation), rate limiting on evaluation endpoint |
| **Elevation of Privilege** | **None** | **JSON Schema evaluation has no code execution model.** There is no execution environment to escape. The schema is pure data processed by the jsonschema library. |

**Overall Security Posture**: Option 1 introduces **no new attack surfaces** beyond standard JSON data storage and retrieval. The fundamental security property is that JSON Schema validation cannot execute code — this eliminates the entire class of injection/sandbox-escape vulnerabilities that disqualify Option 2.

**CVE Evidence for Option 2 Elimination** (Tier 1 sources):
- `CVE-2026-32640` / `GHSA-44vg-5wv2-h2hg` (NVD + GitHub Advisory Database, Mar 13–16, 2026):
  CVSS v4 **8.7/10 (HIGH)**, AV:N/AC:L/AT:N/PR:N/UI:N — simpleeval sandbox escape via object attribute chains reaching `os`/`sys`. Affected: simpleeval < 1.0.5. CWE-94 (Code Injection).
- `ast.literal_eval` — Python 3.14.3 official documentation explicitly states: *"calling it on
  untrusted data is thus not recommended"* — confirmed DoS via memory exhaustion / interpreter crash.

## Pros and Cons of the Options

### Option 1 — JSON Schema Rule Definitions

Declarative JSON Schema stored as JSONB in PostgreSQL, evaluated via `jsonschema` 4.26.0.

```json
{
  "rule_name": "storage-https-only",
  "resource_type": "Microsoft.Storage/storageAccounts",
  "severity": "High",
  "effect": "audit",
  "schema": {
    "type": "object",
    "properties": {
      "supportsHttpsTrafficOnly": { "const": true }
    },
    "required": ["supportsHttpsTrafficOnly"]
  }
}
```

- Good, because **no code execution** — zero injection attack surface
- Good, because **DB-native** — JSON rules stored in existing PostgreSQL, versionable, auditable
- Good, because **low implementation cost** — 1–2 sprints with existing Python/FastAPI stack
- Good, because **multi-tenant safe by design** — `tenant_id` FK, no shared evaluation state
- Good, because **lazy validation** — `iter_errors()` returns all violations (not just first)
- Good, because **JSON Schema is a stable, widely-understood standard** — easy for users to author
- Good, because **~80% expressiveness** covers most real Azure governance scenarios
- Neutral, because **security guards needed** — must disable remote `$ref`, enforce size/pattern limits
- Bad, because **cannot express cross-property comparisons** (e.g., `retentionDays >= backupFrequencyDays`)
- Bad, because **no native effect system** — must build audit/deny wrapper
- Bad, because **~20% of advanced rules** require a future engine upgrade (OPA path exists)

---

### Option 2 — Python Expression Evaluator (simpleeval / ast.literal_eval)

Tenant-authored Python expressions evaluated by `simpleeval` or `ast.literal_eval` at compliance check time.

- Good, because **high expressiveness** — arbitrary Python expressions cover all rule scenarios
- Bad, because **CVE-2026-32640 (CVSS 8.7 HIGH)** — active sandbox escape in simpleeval (March 13, 2026). Network-exploitable, zero authentication, zero user interaction. In multi-tenant context, any tenant can escape the sandbox and execute arbitrary OS commands.
- Bad, because **ast.literal_eval is too limited** — cannot evaluate operators; Python docs explicitly say unsafe on untrusted input
- Bad, because **recurring security issue pattern** — simpleeval GitHub issues #81 (2023), #154 (2024), #166 (2025), #171 (2026) show an ongoing fight against sandbox escapes
- Bad, because **no reliable mitigation** — allow-listing cannot prevent all exploitation paths when the underlying object model allows attribute chain traversal
- Bad, because **compliance SaaS context amplifies risk** — this platform holds Azure credentials, tenant data, and Key Vault references; a sandbox escape exposes everything

**This option is eliminated (K.O. criterion: security).**

---

### Option 3 — Azure Policy Definition Language Clone

Full reimplementation of Azure Policy's JSON condition language: 11 effects, 20+ operators, resource alias system, parameter interpolation, array alias support, initiative grouping.

- Good, because **full expressiveness** — covers 100% of Azure Policy scenarios
- Good, because **familiar to Azure users** — existing Azure Policy knowledge transfers
- Good, because **declarative** — no code execution if implemented correctly
- Bad, because **6–18 months engineering effort** to implement production-quality
- Bad, because **11 complex effects** with distinct pre-conditions and evaluation semantics
- Bad, because **100+ Azure resource aliases** require a maintained alias registry
- Bad, because **reimplementation bugs** could silently produce wrong compliance results (false negatives)
- Bad, because **competing with native Azure Policy** — this platform already syncs Azure Policy state; a clone creates confusion about which system is authoritative
- Bad, because **ongoing maintenance** — Azure Policy adds new effects and operators; the clone must track these

**This option is deferred pending clearer requirements for 100% Azure Policy compatibility.**

---

### Option 4 (Bonus) — OPA/Rego

CNCF Graduated declarative policy engine with Rego language. Noted for future roadmap.

- Good, because **no code execution** — Rego is Datalog-inspired assertions, Turing-incomplete
- Good, because **full expressiveness** — mathematical comparisons, aggregations, string ops
- Good, because **CNCF Graduated** — production-proven at scale (Kubernetes, Envoy, Terraform)
- Good, because **used by Azure Policy itself** for Kubernetes via Gatekeeper
- Good, because **JSON-native** — designed for structured document evaluation
- Neutral, because **Python integration via sidecar** — requires OPA process or subprocess
- Neutral, because **new language** — Rego has a learning curve for rule authors
- Bad, because **adds operational complexity** — OPA sidecar/subprocess vs. pure Python library

**Recommended as the natural evolution path if JSON Schema expressiveness proves insufficient.**

## More Information

**Research Package**: `research/compliance-rule-engine-adr/` — full evidence including CVE details, raw findings, multi-dimensional analysis, source credibility assessments, and prioritized implementation recommendations.

**Key Sources (Tier 1)**:
- CVE-2026-32640: https://nvd.nist.gov/vuln/detail/CVE-2026-32640
- GHSA-44vg-5wv2-h2hg: https://github.com/advisories/GHSA-44vg-5wv2-h2hg
- ast.literal_eval (Python 3 docs): https://docs.python.org/3/library/ast.html#ast.literal_eval
- Azure Policy effect basics: https://learn.microsoft.com/en-us/azure/governance/policy/concepts/effect-basics
- Azure Policy definition structure: https://learn.microsoft.com/en-us/azure/governance/policy/concepts/definition-structure-basics
- jsonschema docs: https://python-jsonschema.readthedocs.io/en/stable/
- OPA Policy Language: https://www.openpolicyagent.org/docs/policy-language

**Review Trigger**: Revisit this decision if more than 20% of rule requests require expressions not expressible in JSON Schema (cross-property comparisons, date arithmetic, aggregation). At that point, evaluate OPA/Rego as a complementary engine.

**Implementation Reference**: See `research/compliance-rule-engine-adr/recommendations.md` for:
- `CustomComplianceRule` SQLAlchemy model
- `JsonSchemaRuleEngine` implementation with security guards
- Example rules covering common Azure governance scenarios
- Risk mitigation checklist

---

**Template Version:** MADR 4.0 (September 2024) with STRIDE Security Analysis  
**Last Updated:** 2026-03-19  
**Maintained By:** Solutions Architect 🏛️  
**Research By:** web-puppy-e25e65

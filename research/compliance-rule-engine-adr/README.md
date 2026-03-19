# Research: Custom Compliance Rule Engine — ADR Evidence Package

**Research Agent**: web-puppy-e25e65  
**Research Date**: March 19, 2026  
**Project Context**: azure-governance-platform (Python/FastAPI, multi-tenant, 5-50 tenants)  
**Purpose**: Evidence base for ADR comparing three approaches to user-defined compliance rules

---

## 🔴 CRITICAL FINDING — Act Immediately

**CVE-2026-32640 (GHSA-44vg-5wv2-h2hg)** was published **March 13, 2026** (6 days ago):

> **"SimpleEval: Objects (including modules) can leak dangerous modules through to direct access inside the sandbox"**
>
> - **CVSS v4**: 8.7/10 **(HIGH)**
> - **Attack Vector**: Network | **Attack Complexity**: Low | **Privileges Required**: None | **User Interaction**: None
> - **Affected**: simpleeval < 1.0.5 | **Patched**: 1.0.5
> - **CWE**: CWE-94 Code Injection + CWE-915 Object Attribute Modification

**In a multi-tenant compliance SaaS context, this CVE means any tenant can submit a crafted rule expression that escapes the simpleeval sandbox and executes arbitrary OS commands in the compliance worker process.**

Source: https://github.com/advisories/GHSA-44vg-5wv2-h2hg | https://nvd.nist.gov/vuln/detail/CVE-2026-32640

---

## ADR Option Summary

### Option 1: JSON Schema Rule Definitions ✅ RECOMMENDED

JSON Schema definitions stored in DB. Rules describe what Azure resource properties must match.
No code execution. Pure data validation via `jsonschema` 4.26.0 library.

| | |
|--|--|
| **Security** | 🟢 Minimal — no code execution model, no injection surface |
| **Expressiveness** | 🟡 ~80% of common Azure governance rules |
| **Implementation** | 🟢 1-2 weeks |
| **Maintenance** | 🟢 Low — stable library, stable JSON Schema spec |
| **CVEs** | None |

**What it CAN express:**
- Value equality: `properties.httpsOnly == true`
- Numeric ranges: `retentionDays >= 90`
- Allowed value lists: `sku in ["Standard", "Premium"]`
- Required fields/tags: `required: ["environment", "cost-center"]`
- String patterns: `name matches /^prod-[a-z]+$/`
- Conditional rules: `if sku == "Premium" then minCapacity >= 2`
- Object structure validation: nested property requirements

**What it CANNOT express:**
- Cross-property comparisons: `fieldA >= fieldB`
- Date arithmetic: `expiryDate > now() + 30d`
- Aggregation: `count(denied_rules) > 5`
- Effect system: no native audit/deny/remediate semantics (requires wrapper)

---

### Option 2: Python Expression Evaluator ❌ ELIMINATED

Using `simpleeval` or `ast.literal_eval` to evaluate tenant-authored rule expressions.

| | |
|--|--|
| **Security** | 🔴 **Critical** — CVE-2026-32640 (CVSS 8.7 HIGH), network-exploitable |
| **Expressiveness** | 🟢 High — arbitrary Python expressions |
| **Implementation** | 🟡 2-4 weeks |
| **Maintenance** | 🔴 Recurring security issues (2023, 2024, 2025, 2026) |
| **CVEs** | **CVE-2026-32640 (2026)** — active as of research date |

**Why it's eliminated:**

1. **Active CVE with CVSS 8.7**: Published 6 days ago. Network-accessible, zero-auth, zero-user-interaction exploitation. Patched in 1.0.5, but the library's architecture (dynamic attribute access on Python objects) creates a recurring attack surface.

2. **Multi-tenant amplification**: In a single-tenant context, this might be manageable. In a multi-tenant compliance SaaS, any of 5-50 tenants can trigger RCE by crafting a rule expression that traverses object attributes to reach `os.system()`. One malicious tenant = full process compromise = all tenant data exposed.

3. **Recurring pattern**: simpleeval security issues in GitHub issues #81 (2023), #154 (2024), #166 (2025), #171 (2026). The library has been fighting this problem for 3+ years.

4. **ast.literal_eval is too limited AND still unsafe**: Cannot evaluate operators (no `==`, `>=`, `and`, `or`). Python 3 docs explicitly state: *"calling it on untrusted data is thus not recommended"* — confirmed DoS via memory exhaustion.

**No remediation can make Option 2 safe in a multi-tenant context.** Even with allow-listing and sandboxing, the fundamental design of evaluating user-authored code expressions is incompatible with multi-tenant security requirements.

---

### Option 3: Azure Policy Clone ⚠️ DEFERRED

Full reimplementation of Azure Policy's definition language: effects (audit/deny/deployIfNotExists/etc.), condition operators, resource aliases, parameter system.

| | |
|--|--|
| **Security** | 🟡 Medium — declarative if done correctly, but complex impl creates bypass risks |
| **Expressiveness** | 🟢 Very High — full Azure Policy capability |
| **Implementation** | 🔴 6-18 months |
| **Maintenance** | 🔴 High — must track Azure Policy evolution |
| **CVEs** | None (new code, but untested implementation risks) |

**Azure Policy has 11 distinct effects** (addToNetworkGroup, append, audit, auditIfNotExists, deny, denyAction, deployIfNotExists, disabled, manual, modify, mutate), 20+ condition operators, resource alias system, parameter interpolation, array alias support, initiative grouping, assignment scope, and exemption handling.

**This is a 6-18 month engineering project** for a production-quality implementation.

**Key insight**: This project already uses Azure Policy natively (via `ComplianceSnapshot` and `PolicyState` models synced from Azure). Custom rules should complement Azure Policy, not replace it.

---

### Option 4 (Bonus): OPA/Rego — Recommended Future Path

Not one of the three proposed options, but highly relevant:

| | |
|--|--|
| **Security** | 🟢 Excellent — declarative, no execution model, Turing-incomplete |
| **Expressiveness** | 🟢 Very High — full boolean logic, comparisons, aggregations |
| **Implementation** | 🟡 1-4 weeks (sidecar integration) |
| **Maintenance** | 🟢 Low — CNCF Graduated, OPA community |
| **CVEs** | None of note |

OPA/Rego is the **industry standard** for declarative policy evaluation in cloud-native systems. It:
- Is **CNCF Graduated** (same as Kubernetes, Prometheus)
- Is used by **Azure Policy itself** for Kubernetes via Gatekeeper
- Has **no code execution model** — policies are Datalog-inspired assertions
- Is **Turing-incomplete** — guaranteed termination, no infinite loops
- Supports all comparisons, string operations, aggregations
- Is JSON-native (input/output as JSON)

**Recommendation**: Use JSON Schema (Option 1) now. Evaluate OPA as a complementary engine when expressiveness gaps emerge.

---

## Recommended Decision: Option 1 (JSON Schema) + OPA Roadmap

### Immediate Implementation
1. Add `custom_compliance_rules` table to PostgreSQL
2. Implement `JsonSchemaRuleEngine` wrapper class with security guards
3. Add API routes for rule CRUD (admin-only)
4. Integrate with compliance sync pipeline
5. Implement security mitigations (no remote `$ref`, schema size limits, pattern length limits)

### Future Expansion
6. Monitor for expressiveness gaps (cross-property comparisons, date arithmetic)
7. Evaluate CEL (Common Expression Language) or OPA for advanced rules
8. Consider OPA sidecar for rules that JSON Schema cannot express

---

## Evidence Files

| File | Contents |
|------|----------|
| [raw-findings/simpleeval-cve-2026-32640.md](raw-findings/simpleeval-cve-2026-32640.md) | Full CVE details, CVSS metrics, exploitation context |
| [raw-findings/ast-literal-eval-security.md](raw-findings/ast-literal-eval-security.md) | Python official docs findings on ast.literal_eval |
| [raw-findings/azure-policy-definition-structure.md](raw-findings/azure-policy-definition-structure.md) | Full Azure Policy structure, 11 effects, reimplementation cost |
| [raw-findings/json-schema-as-rule-engine.md](raw-findings/json-schema-as-rule-engine.md) | JSON Schema capabilities, performance, real-world examples |
| [raw-findings/opa-rego-alternative.md](raw-findings/opa-rego-alternative.md) | OPA/Rego as Option 4, comparison matrices |
| [sources.md](sources.md) | All sources with credibility assessments and source tiers |
| [analysis.md](analysis.md) | Multi-dimensional analysis across all 7 dimensions |
| [recommendations.md](recommendations.md) | Prioritized action items with code examples |

---

## Key Sources (Tier 1 Only)

| Finding | Source | URL |
|---------|--------|-----|
| CVE-2026-32640 (CVSS 8.7) | NVD / GitHub Advisory Database | https://nvd.nist.gov/vuln/detail/CVE-2026-32640 |
| GHSA-44vg-5wv2-h2hg | GitHub Security Advisory | https://github.com/advisories/GHSA-44vg-5wv2-h2hg |
| ast.literal_eval unsafe on untrusted data | Python 3.14.3 official docs | https://docs.python.org/3/library/ast.html#ast.literal_eval |
| Azure Policy effects (11 types) | Microsoft Learn | https://learn.microsoft.com/en-us/azure/governance/policy/concepts/effect-basics |
| Azure Policy definition structure | Microsoft Learn | https://learn.microsoft.com/en-us/azure/governance/policy/concepts/definition-structure-basics |
| jsonschema 4.26.0 | python-jsonschema official docs | https://python-jsonschema.readthedocs.io/en/stable/ |
| OPA Rego policy language | OPA official docs v1.14.1 | https://www.openpolicyagent.org/docs/policy-language |

---

## ADR Writing Guidance

When writing the ADR (docs/decisions/adr-0005-compliance-rule-engine.md), ensure:

1. **STRIDE Security Analysis is complete** — required by project ADR template. The CVE evidence is the cornerstone of the security analysis.

2. **Cross-reference the CVE in the decision outcome** — this is a K.O. criterion (knockout criterion) against Option 2.

3. **Document Option 4 (OPA) as "considered but deferred"** — it's the industry standard and should be acknowledged.

4. **Set a confirmation criteria** — e.g., "Security review confirms no code execution path in JSON Schema validation pipeline" and "Integration test confirms tenant_id isolation on custom rules".

5. **Set a review trigger** — "Revisit if >20% of rule requests require cross-property comparisons not expressible in JSON Schema."

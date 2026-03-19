# Raw Finding: OPA/Rego as an Alternative Approach

## Source
- **Primary**: Open Policy Agent Documentation v1.14.1
- **URL**: https://www.openpolicyagent.org/docs/policy-language
- **CNCF Status**: Graduated Project
- **License**: Apache 2.0
- **Source Tier**: Tier 1 — Official OPA documentation

## What is OPA/Rego?
OPA (Open Policy Agent) is a **CNCF Graduated** general-purpose policy engine.
Rego is OPA's declarative policy language, inspired by Datalog, designed for
evaluating structured data (JSON, YAML, etc.).

> "Rego queries are assertions on data that can be used to define policies and
> make decisions about whether data violates the expected state of your system."

## Language Characteristics
- **Declarative** — express WHAT, not HOW
- **No code execution** — pure assertion logic over data
- **JSON-native** — designed for structured documents
- **Turing-incomplete** — guaranteed to terminate (no infinite loops)
- **Safety by design** — variables must be grounded (bound to concrete values)

## Example Rego Policy (Compliance Rule)
```rego
package azure.compliance

# Storage account must use HTTPS only
deny contains msg if {
    input.properties.supportsHttpsTrafficOnly != true
    msg := "Storage account must enable HTTPS-only traffic"
}

# Retention must be at least 30 days
deny contains msg if {
    input.properties.retentionDays < 30
    msg := sprintf("Retention days %v is less than minimum 30", [input.properties.retentionDays])
}

# Required tags must be present
deny contains msg if {
    required_tags := ["environment", "cost-center", "owner"]
    some tag in required_tags
    not input.properties.tags[tag]
    msg := sprintf("Required tag '%v' is missing", [tag])
}
```

## Security Properties
| Property | Assessment |
|----------|-----------|
| Code execution | **None** — Rego is purely declarative data assertions |
| Sandbox escape | **Not applicable** — no execution model to escape |
| DoS risk | **Low** — policies are bounded (no infinite loops) |
| Injection | **Not possible** — no string eval, no dynamic code |
| Tenant isolation | **By design** — policies are namespaced by package |

## Integration Options with Python
1. **OPA as a sidecar service** — REST API, policies evaluated via HTTP
2. **rego-python** (community library) — embedded evaluation
3. **Subprocess** — `opa eval` CLI integration
4. **OPA WASM** — compile policies to WebAssembly for embedding

## Comparison with Option 1 (JSON Schema)
| Feature | JSON Schema | OPA Rego |
|---------|-------------|----------|
| Code execution | None | None |
| Mathematical comparisons | ❌ Not supported | ✅ Supported |
| Cross-field conditions | ❌ Limited | ✅ Full support |
| Pattern matching | ✅ Regex | ✅ Regex + glob |
| Required fields | ✅ `required` | ✅ Explicit |
| Effect system | ❌ None built-in | ✅ Custom (deny/allow/warn) |
| Learning curve | Low | Medium |
| Performance | ~5,000/s | ~10,000/s (compiled) |
| DB-storable rules | ✅ JSON | ✅ Text (Rego modules) |
| User authoring | ✅ Easy (JSON) | Medium (new language) |
| Multi-tenant | ✅ trivial | ✅ namespaced packages |
| Python integration | ✅ Native library | ⚠️ HTTP sidecar or subprocess |

## Comparison with Option 2 (simpleeval)
| Feature | simpleeval | OPA Rego |
|---------|-----------|----------|
| Code execution | ✅ Yes (sandbox) | ❌ No |
| CVE history | CVE-2026-32640 (CVSS 8.7) | None |
| Sandbox escape | Possible via module attr chains | Not applicable |
| DoS risk | Yes (confirmed by CVE) | Minimal |
| Python native | ✅ Library | ⚠️ Sidecar |

## Comparison with Option 3 (Azure Policy Clone)
| Feature | Azure Policy Clone | OPA Rego |
|---------|-------------------|----------|
| Implementation effort | 6-18 months | 1-4 weeks integration |
| Maintained by | You | CNCF/OPA community |
| Effects | 11 complex effects | Custom (simpler) |
| Azure-specific | Yes | General-purpose |
| Kubernetes support | Native | Native |

## ADR Relevance

OPA/Rego is not one of the three proposed options but is highly relevant as:
1. **The industry-standard** for declarative policy evaluation in cloud-native systems
2. **CNCF Graduated** — production-proven at scale (Kubernetes admission, API gateways)
3. **Security-first** — designed from the ground up to prevent injection
4. **Used by Azure Policy itself** — Azure Kubernetes Policy uses OPA/Gatekeeper

The ADR should acknowledge OPA as a considered-and-rejected alternative (if JSON Schema
is chosen) or as a future migration path.

## Production Deployments
- Kubernetes (via Gatekeeper) — used by Azure Policy for AKS
- Envoy/Istio service mesh authorization
- Terraform plan validation
- AWS CloudFormation hooks
- GitHub Actions policy enforcement
- Thousands of enterprises in production

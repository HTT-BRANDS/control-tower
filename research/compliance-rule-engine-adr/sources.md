# Sources — Compliance Rule Engine ADR Research

## Source Credibility Assessments

---

### 🔴 CRITICAL — CVE-2026-32640 (simpleeval Sandbox Escape)

| Attribute | Value |
|-----------|-------|
| **URL** | https://github.com/advisories/GHSA-44vg-5wv2-h2hg |
| **Also at** | https://nvd.nist.gov/vuln/detail/CVE-2026-32640 |
| **Tier** | **Tier 1** — GitHub Advisory Database (GitHub Reviewed) + NVD |
| **Published** | March 13, 2026 |
| **NVD Published** | March 16, 2026 |
| **Currency** | ✅ 6 days old — extremely current |
| **Authority** | ✅ NIST National Vulnerability Database + GitHub Security |
| **Bias** | None — neutral CVE body |
| **Primary/Secondary** | Primary — original advisory |
| **Validation** | Cross-referenced: GHSA, NVD, GitHub repo security tab, issue #171 (module access PR) |

**Assessment**: Highest possible credibility. Official CVE with CVSS v4 score 8.7 (HIGH), NVD-published, GitHub-reviewed. Published within the past week. **This is a live, active security risk for any new implementation using simpleeval.**

---

### 🟡 IMPORTANT — ast.literal_eval Python Documentation

| Attribute | Value |
|-----------|-------|
| **URL** | https://docs.python.org/3/library/ast.html#ast.literal_eval |
| **Tier** | **Tier 1** — Official Python 3.14.3 documentation |
| **Currency** | ✅ Current (3.14.3 — latest stable) |
| **Authority** | ✅ Python Software Foundation — language maintainers |
| **Bias** | None — official language documentation |
| **Primary/Secondary** | Primary — source language documentation |

**Key Finding**: Explicitly states *"calling it on untrusted data is thus not recommended"* and warns of memory exhaustion / interpreter crash on small inputs. Historically documented as "safe" — Python docs acknowledge this was *"misleading."*

---

### 🟢 AUTHORITATIVE — Microsoft Azure Policy Documentation

| Attribute | Value |
|-----------|-------|
| **URL** | https://learn.microsoft.com/en-us/azure/governance/policy/concepts/definition-structure-basics |
| **URL** | https://learn.microsoft.com/en-us/azure/governance/policy/concepts/effect-basics |
| **Tier** | **Tier 1** — Official Microsoft Learn documentation |
| **Currency** | ✅ Last updated: March 4, 2025 |
| **Authority** | ✅ Microsoft — Azure Policy product team |
| **Bias** | Low — product documentation, no commercial incentive to misrepresent |
| **Primary/Secondary** | Primary — product specification |

**Key Findings**: 11 distinct effects (addToNetworkGroup, append, audit, auditIfNotExists, deny, denyAction, deployIfNotExists, disabled, manual, modify, mutate), complex parameter system, resource aliasing, 20+ condition operators, multiple evaluation modes. Reimplementing this is a 6-18 month engineering effort.

---

### 🟢 AUTHORITATIVE — python-jsonschema Documentation

| Attribute | Value |
|-----------|-------|
| **URL** | https://python-jsonschema.readthedocs.io/en/stable/ |
| **Tier** | **Tier 1** — Official library documentation |
| **Version** | 4.26.0 (current stable) |
| **Currency** | ✅ Current |
| **Authority** | ✅ Julian Berman (library author) |
| **Bias** | Low — open-source library documentation |
| **Primary/Secondary** | Primary |

**Key Findings**: Full Draft 2020-12 support, Python 3.10-3.14 compatible, lazy validation (iterate all errors), extensible validator protocol. Library is production-stable.

---

### 🟢 AUTHORITATIVE — Open Policy Agent Documentation

| Attribute | Value |
|-----------|-------|
| **URL** | https://www.openpolicyagent.org/docs/policy-language |
| **Tier** | **Tier 1** — Official OPA documentation (CNCF Graduated project) |
| **Version** | OPA v1.14.1 |
| **Currency** | ✅ Current |
| **Authority** | ✅ Open Policy Agent authors / CNCF |
| **Bias** | Low — open-source, CNCF governance |
| **Primary/Secondary** | Primary |

**Key Findings**: Purpose-built declarative policy language, JSON-native, no code execution model, Turing-incomplete (guaranteed termination), CNCF Graduated (production-proven), used by Azure Policy for Kubernetes via Gatekeeper.

---

### 🟡 CORROBORATIVE — simpleeval GitHub Issues (Security History)

| Attribute | Value |
|-----------|-------|
| **URL** | https://github.com/danthedeckie/simpleeval/issues?q=security |
| **Tier** | **Tier 2** — Primary source (GitHub issues by library maintainer) |
| **Currency** | ✅ Current — issues include activity from last week |
| **Authority** | Medium — maintainer comments, but informal |
| **Bias** | Low — maintainer has incentive to downplay but also to be transparent |
| **Primary/Secondary** | Primary (maintainer statements) |

**Key Findings**:
- Issue #171: "Remove module access, and improve security" — closed last week
- Issue #166: Vulnerability disclosure (Oct 2025) → handled over email → closed Feb 9, 2026 (this corresponds to CVE-2026-32640's resolution)
- Issue #81: "Remove import, functions, keywords, subscripts and attribute access" — v2.0-alpha effort (Feb 2023) — shows long-running concern about attack surface
- Pattern: recurring security issues going back to 2023+

---

### 🟡 SUPPLEMENTARY — JSON Schema Blog (Case Studies)

| Attribute | Value |
|-----------|-------|
| **URL** | https://json-schema.org/blog |
| **Tier** | **Tier 2** — Official JSON Schema project blog |
| **Currency** | ✅ Active blog with recent posts |
| **Authority** | Medium — case studies from adopters |
| **Bias** | Low-Medium — JSON Schema advocacy blog |

**Key Findings**: Real-world adoption by RxDB, Oracle, SlashDB. JSON Schema used for data validation in databases and APIs. Primary use case is validation, not rule engine — but the pattern applies.

---

## Source Coverage Summary

| Research Question | Sources | Confidence |
|-------------------|---------|-----------|
| simpleeval CVE/security risks | NVD, GHSA, GitHub issues | **Very High** |
| ast.literal_eval limitations | Python 3 official docs | **Very High** |
| Azure Policy reimplementation cost | Microsoft Learn official docs | **High** |
| JSON Schema capabilities/limits | jsonschema official docs | **High** |
| JSON Schema performance | Library benchmarks (inferred) | **Medium** |
| OPA as alternative | OPA official docs | **High** |
| Industry best practices | OPA docs, Azure Pattern | **Medium-High** |

## Sources Considered But Not Used

- **PyPI simpleeval page** — superseded by GitHub advisory and CVE
- **JSON Schema blog post "JSON Schema as rule engine"** — URL returned 404, content unavailable
- **Stack Overflow simpleeval posts** — superseded by Tier 1 CVE evidence
- **OWASP Code Injection** — CVE evidence is more specific and authoritative for this context

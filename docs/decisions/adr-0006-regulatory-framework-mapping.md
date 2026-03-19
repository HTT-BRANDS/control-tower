---
status: proposed
date: 2026-03-20
decision-makers: Solutions Architect 🏛️, Security Auditor 🛡️, Pack Leader 🐺
consulted: Web Puppy 🕵️ (SOC2/NIST research), Experience Architect 🎨 (API contracts)
informed: All Code Puppy agents, MSP administrators
relates-to: CM-003
---

# Map compliance findings to SOC2 Trust Service Criteria and NIST CSF 2.0 controls

## Context and Problem Statement

The Azure Governance Platform syncs Azure Policy compliance states into `ComplianceSnapshot` and `PolicyState` models, tracks Riverside-specific compliance via `RiversideCompliance` and `RiversideMFA` models, and supports custom compliance rules via `CustomComplianceRule` (ADR-0005). However, **customers cannot view their compliance posture through the lens of regulatory frameworks** — they see raw policy violations but have no way to answer questions like:

- "Which SOC2 Trust Service Criteria are we failing?"
- "What is our NIST CSF coverage across the Protect function?"
- "Which CC6 (Logical Access) controls have gaps?"

MSP administrators managing 5+ tenants need regulatory framework mapping to prepare for SOC2 Type II audits and demonstrate NIST CSF alignment. The compliance sync pipeline already receives `policy_definition_group_names` from Azure (which include SOC2 and NIST control references), but this data is currently flattened into a CSV string in `policy_category` — losing the framework-specific semantic structure.

How should the platform map existing compliance findings to SOC2 Trust Service Criteria and NIST CSF 2.0 controls?

## Decision Drivers

- **No new database tables**: Framework definitions are static reference data that changes on AICPA/NIST publication cycles (years), not at runtime — storing them in PostgreSQL adds migration burden without benefit
- **Computation at read time**: Compliance coverage percentages must reflect the *current* state of `PolicyState` and `ComplianceSnapshot` data, not a stale cache
- **Extensibility**: Must support adding ISO 27001, CIS Benchmarks, or PCI-DSS in future without schema changes
- **Auditability**: Framework definitions must be version-controlled in source code, not editable at runtime
- **Implementation velocity**: Must integrate with existing FastAPI + SQLAlchemy stack in 1 sprint
- **SOC2 TSC IP constraint**: SOC2 Trust Service Criteria are AICPA proprietary — reference control IDs and brief descriptions only, do not reproduce full criterion text
- **Azure alignment**: Azure built-in policy initiatives already tag policies with `SOC_2_CC6.1` and `NIST_CSF_v2.0_PR.AA_01` style group names — leverage these rather than building a parallel mapping

## Considered Options

1. **Code-embedded framework definitions with keyword-based policy mapping** — Python dataclasses define frameworks; existing `PolicyState.policy_name` and `policy_category` keywords map to controls at query time
2. **New database tables for frameworks and mappings** — `compliance_frameworks`, `framework_controls`, and `policy_control_mappings` tables with foreign keys
3. **External mapping file (YAML/JSON) loaded at startup** — Framework definitions in `config/frameworks/*.yaml`, loaded into memory on app start

## Decision Outcome

**Chosen option: "Code-embedded framework definitions with keyword-based policy mapping"**, because it satisfies the no-new-tables constraint, keeps framework definitions version-controlled alongside the code that uses them, enables immediate computation of coverage percentages by joining in-memory framework data with existing `PolicyState` queries, and aligns with the existing pattern established by `ComplianceService._map_severity()` which already classifies policies by keyword matching.

### Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│  GET /api/v1/compliance/frameworks                  │
│  GET /api/v1/compliance/frameworks/{framework_id}   │
└──────────────────────┬──────────────────────────────┘
                       │
           ┌───────────▼───────────────┐
           │  FrameworkMappingService   │
           │  (app/api/services/)      │
           └───────────┬───────────────┘
                       │
          ┌────────────┼────────────────┐
          │            │                │
    ┌─────▼─────┐  ┌──▼──────────┐  ┌──▼──────────────┐
    │ Framework  │  │ PolicyState │  │ ComplianceSnapshot│
    │ Registry   │  │ (DB query)  │  │ (DB query)        │
    │ (in-memory)│  └─────────────┘  └──────────────────┘
    └────────────┘
         │
    Python dataclasses
    with keyword→control
    mapping tables
```

### Framework Definition Structure

Each framework is defined as a Python dataclass with:
- **Framework metadata**: ID, name, version, description
- **Control categories**: Hierarchical grouping (e.g., CC6 → CC6.1, CC6.2, ...)
- **Control definitions**: ID, name, brief description
- **Keyword mappings**: Which `PolicyState.policy_name` / `policy_category` keywords indicate coverage of which control

```python
@dataclass(frozen=True)
class FrameworkControl:
    """A single control within a regulatory framework."""
    id: str                    # e.g., "CC6.1"
    name: str                  # e.g., "Logical Access Security"
    description: str           # Brief description (not full AICPA text)
    category_id: str           # e.g., "CC6"

@dataclass(frozen=True)
class ControlCategory:
    """A category grouping related controls."""
    id: str                    # e.g., "CC6"
    name: str                  # e.g., "Logical and Physical Access Controls"
    controls: tuple[FrameworkControl, ...]

@dataclass(frozen=True)
class RegulatoryFramework:
    """A complete regulatory framework definition."""
    id: str                    # e.g., "soc2"
    name: str                  # e.g., "SOC 2 Type II"
    version: str               # e.g., "2017 with 2022 revisions"
    description: str
    categories: tuple[ControlCategory, ...]
```

### Keyword-to-Control Mapping Approach

The mapping uses a **two-tier strategy**:

**Tier 1 — Azure group name matching** (highest confidence): When `PolicyState.policy_category` contains Azure initiative group names like `SOC_2_CC6.1` or `NIST_CSF_v2.0_PR.AA_01`, these map directly to framework controls. This leverages Azure's own SOC2 and NIST CSF built-in initiatives.

**Tier 2 — Keyword matching** (supplementary): When Azure group names aren't present, fall back to matching `PolicyState.policy_name` keywords to controls. This extends the existing `ComplianceService._map_severity()` pattern. Example: a policy containing "encryption" AND "transit" maps to CC6.7 (transmission protection) and PR.DS-02 (data in transit).

```python
# Tier 1: Direct Azure initiative group name → control mapping
AZURE_GROUP_TO_CONTROL: dict[str, list[tuple[str, str]]] = {
    "SOC_2_CC6.1": [("soc2", "CC6.1")],
    "SOC_2_CC6.3": [("soc2", "CC6.3")],
    "NIST_CSF_v2.0_PR.AA_01": [("nist_csf", "PR.AA-01")],
    # ... full mapping in implementation spec
}

# Tier 2: Keyword sets → control mapping (fallback)
KEYWORD_CONTROL_MAP: list[tuple[frozenset[str], list[tuple[str, str]]]] = [
    (frozenset({"encryption", "transit"}), [("soc2", "CC6.7"), ("nist_csf", "PR.DS-02")]),
    (frozenset({"mfa"}), [("soc2", "CC6.1"), ("nist_csf", "PR.AA-01")]),
    (frozenset({"firewall"}), [("soc2", "CC6.6"), ("nist_csf", "PR.AA-05")]),
    # ... full mapping in implementation spec
]
```

### API Design

#### `GET /api/v1/compliance/frameworks`

Returns all available regulatory frameworks with summary coverage data.

```json
{
  "frameworks": [
    {
      "id": "soc2",
      "name": "SOC 2 Type II",
      "version": "2017 with 2022 revisions",
      "description": "Trust Service Criteria for Security, Availability, Processing Integrity, Confidentiality, Privacy",
      "total_controls": 35,
      "categories_count": 12,
      "coverage_summary": {
        "controls_with_coverage": 22,
        "controls_without_coverage": 13,
        "overall_coverage_percent": 62.9
      }
    },
    {
      "id": "nist_csf",
      "name": "NIST Cybersecurity Framework",
      "version": "2.0 (February 2024)",
      "description": "Framework for improving critical infrastructure cybersecurity",
      "total_controls": 22,
      "categories_count": 6,
      "coverage_summary": {
        "controls_with_coverage": 15,
        "controls_without_coverage": 7,
        "overall_coverage_percent": 68.2
      }
    }
  ]
}
```

#### `GET /api/v1/compliance/frameworks/{framework_id}`

Returns full framework mapping with per-control compliance status.

Query parameters:
- `tenant_ids: list[str] | None` — filter to specific tenants
- `include_policies: bool = false` — include matched policy details per control

```json
{
  "framework": {
    "id": "soc2",
    "name": "SOC 2 Type II",
    "version": "2017 with 2022 revisions"
  },
  "overall_coverage_percent": 62.9,
  "categories": [
    {
      "id": "CC6",
      "name": "Logical and Physical Access Controls",
      "coverage_percent": 75.0,
      "controls": [
        {
          "id": "CC6.1",
          "name": "Logical Access Security",
          "description": "Logical access security software, infrastructure, and architectures",
          "status": "covered",
          "matched_policies_count": 5,
          "compliant_count": 3,
          "non_compliant_count": 2,
          "compliance_percent": 60.0,
          "matched_policies": [
            {
              "policy_name": "MFA should be enabled on accounts with owner permissions",
              "compliance_state": "NonCompliant",
              "non_compliant_count": 2,
              "mapping_confidence": "high"
            }
          ]
        }
      ]
    }
  ]
}
```

### Consequences

**Good:**
- **Zero database migration** — framework definitions are pure Python code; no Alembic migration needed
- **Version-controlled** — framework definitions change with git commits, enabling full audit trail
- **Instant extensibility** — adding ISO 27001 requires only a new Python module, no schema changes
- **Leverages existing data** — computes coverage from `PolicyState` records already synced by the compliance pipeline
- **Azure-native alignment** — uses Azure's own initiative group names for high-confidence mapping
- **Read-time freshness** — coverage percentages always reflect current compliance state
- **Low implementation cost** — ~3 new files, ~500 lines of code, 1 sprint

**Bad:**
- **Keyword mapping is heuristic** — not all policies will map cleanly; some controls may show as "no coverage" when partial coverage exists via unmapped policies
- **No runtime customization** — MSP administrators cannot add custom framework-to-policy mappings without code changes
- **Coverage ≠ certification** — SOC2 compliance requires auditor judgment beyond policy state; must clearly label as "automated coverage assessment, not audit opinion"

**Neutral:**
- Framework definitions will need periodic updates when AICPA revises TSC or NIST publishes CSF updates — but this happens on multi-year cycles

### Confirmation

This decision is confirmed when:
1. `GET /api/v1/compliance/frameworks` returns both SOC2 and NIST CSF with coverage percentages
2. `GET /api/v1/compliance/frameworks/soc2` returns all control categories with per-control compliance data
3. Framework definitions are Python dataclasses in `app/api/services/framework_definitions.py`
4. No new Alembic migration is required
5. Keyword mapping covers ≥20 SOC2 controls and ≥15 NIST CSF controls
6. All fitness functions pass

## STRIDE Security Analysis

| Threat Category | Risk Level | Mitigation |
|-----------------|-----------|------------|
| **Spoofing** | Low | Framework endpoints require authentication via existing `get_current_user` dependency; tenant filtering uses existing `TenantAuthorization` middleware — same pattern as `/api/v1/compliance/summary` |
| **Tampering** | **None** | Framework definitions are frozen dataclasses in source code — no runtime mutation path. Coverage percentages are computed from existing `PolicyState` records which have their own integrity controls |
| **Repudiation** | Low | Framework definition changes tracked via git history; API access logged via existing audit middleware; coverage percentages are deterministic (same DB state → same result) |
| **Information Disclosure** | Low | Framework definitions are public knowledge (SOC2 control IDs, NIST CSF categories); compliance coverage data is tenant-scoped via existing `TenantAuthorization`; no new sensitive data introduced |
| **Denial of Service** | Low | Coverage computation queries `PolicyState` table (already indexed by `tenant_id`); framework registries are tiny in-memory structures (~5KB); no expensive joins or aggregations beyond existing compliance queries |
| **Elevation of Privilege** | **None** | No new authorization model introduced; reuses existing `get_current_user` + `TenantAuthorization`; framework data is read-only reference material with no write endpoints |

**Overall Security Posture**: This decision introduces **no new attack surfaces**. The framework definitions are static, read-only reference data. The only computation is joining in-memory framework definitions with existing `PolicyState` queries that already enforce tenant isolation. The API endpoints reuse the same authentication and authorization stack as all other compliance endpoints.

**Key Security Design Principle**: Framework definitions are `frozen=True` dataclasses — immutable at the Python level. There is no API endpoint to modify them, no database table to inject into, and no configuration file to tamper with at runtime.

## Pros and Cons of the Options

### Option A — Code-Embedded Framework Definitions with Keyword Mapping (selected)

*Python frozen dataclasses define frameworks and controls; `PolicyState` fields are matched to controls via Azure group names and keyword heuristics; coverage computed at query time.*

- Good, because **zero database migration** — no new tables, no Alembic version, no schema coupling
- Good, because **version-controlled** — framework definitions are reviewed, committed, and auditable via git history
- Good, because **frozen dataclasses** provide immutability guarantees — no runtime mutation possible
- Good, because **Azure group name matching** (Tier 1) provides high-confidence mapping aligned with Microsoft's own SOC2/NIST initiatives
- Good, because **keyword fallback** (Tier 2) extends the existing `_map_severity()` pattern in `ComplianceService`
- Good, because **read-time computation** always reflects current compliance state
- Good, because **extensibility** — adding ISO 27001 is just a new Python module with dataclass definitions
- Neutral, because framework updates require code changes — but AICPA/NIST publish on multi-year cycles
- Bad, because **keyword mapping is heuristic** — edge cases will exist where policies don't map cleanly
- Bad, because **no runtime customization** — MSP admins can't override mappings without deploying code
- Bad, because **coverage ≠ certification** — must clearly disclaim this is automated assessment, not audit opinion

### Option B — New Database Tables for Frameworks and Mappings

*`compliance_frameworks`, `framework_controls`, `policy_control_mappings` tables with CRUD endpoints for custom mappings.*

- Good, because MSP administrators can customize mappings at runtime
- Good, because mapping changes don't require code deployment
- Good, because standard relational modeling with foreign keys and constraints
- Bad, because **requires Alembic migration** — adds schema complexity for data that changes on multi-year cycles
- Bad, because **framework definitions become mutable** — risk of accidental or malicious modification
- Bad, because **mapping CRUD requires new authorization model** — who can change which framework definitions?
- Bad, because **6 new tables minimum** — `frameworks`, `categories`, `controls`, `keyword_maps`, `group_maps`, `coverage_snapshots`
- Bad, because **stale data risk** — coverage snapshots may not reflect current `PolicyState` data

### Option C — External YAML/JSON Files Loaded at Startup

*Framework definitions in `config/frameworks/soc2.yaml` and `config/frameworks/nist_csf.yaml`, loaded into memory on application start.*

- Good, because YAML is human-readable and easy to edit
- Good, because no database migration needed
- Good, because configuration-as-code pattern is well understood
- Neutral, because still requires restart to pick up changes (same as Option A)
- Bad, because **no type safety** — YAML parsing errors only caught at runtime, not at import time
- Bad, because **no IDE support** — no autocomplete, no type checking on framework definitions
- Bad, because **deserialization overhead** — must validate YAML structure on every startup
- Bad, because **file path dependency** — adds deployment concern about config file presence
- Bad, because **YAML is a superset of JSON** with known parsing pitfalls (Norway problem, implicit type coercion)

## Fitness Functions

The following automated tests enforce this ADR. They are located in `tests/architecture/test_fitness_functions.py`:

### FF-1: Framework definitions are immutable (frozen dataclasses)

```python
def test_framework_definitions_are_frozen():
    """ADR-0006 FF-1: Framework definitions must be frozen dataclasses.

    Ensures no runtime mutation of framework registry data.
    """
    framework_file = Path("app/api/services/framework_definitions.py")
    if not framework_file.exists():
        pytest.skip("framework_definitions.py not yet implemented")

    content = framework_file.read_text()
    assert "frozen=True" in content, (
        "ADR-0006 violation: Framework dataclasses must use frozen=True "
        "to prevent runtime mutation of regulatory framework definitions."
    )
    assert "@dataclass(frozen=True)" in content or "frozen=True" in content, (
        "ADR-0006 violation: All framework definition dataclasses must be frozen."
    )
```

### FF-2: Framework endpoints require authentication

```python
def test_framework_endpoints_require_auth():
    """ADR-0006 FF-2: /api/v1/compliance/frameworks endpoints must require authentication.

    The frameworks router must be nested under the compliance router which
    requires get_current_user, or have its own auth dependency.
    """
    route_files = [
        Path("app/api/routes/compliance.py"),
        Path("app/api/routes/compliance_frameworks.py"),
    ]

    for route_file in route_files:
        if not route_file.exists():
            continue
        content = route_file.read_text()
        if "frameworks" in content:
            assert "get_current_user" in content, (
                f"ADR-0006 violation: {route_file.name} contains framework endpoints "
                f"but does not require authentication via Depends(get_current_user)."
            )
```

### FF-3: No new Alembic migration for frameworks

```python
def test_no_framework_alembic_migration():
    """ADR-0006 FF-3: No new database tables for framework definitions.

    Framework data is code-embedded (frozen dataclasses), not DB-stored.
    """
    migrations_dir = Path("alembic/versions")
    if not migrations_dir.exists():
        pytest.skip("alembic/versions not found")

    for migration_file in migrations_dir.glob("*.py"):
        content = migration_file.read_text()
        assert "compliance_frameworks" not in content, (
            f"ADR-0006 violation: {migration_file.name} creates a compliance_frameworks "
            f"table. Framework definitions must be code-embedded, not DB-stored."
        )
        assert "framework_controls" not in content, (
            f"ADR-0006 violation: {migration_file.name} creates a framework_controls "
            f"table. Framework definitions must be code-embedded, not DB-stored."
        )
```

### FF-4: Minimum control coverage in mappings

```python
def test_minimum_framework_control_coverage():
    """ADR-0006 FF-4: Framework definitions must have minimum control counts.

    SOC2: ≥20 controls defined with keyword mappings
    NIST CSF: ≥15 controls defined with keyword mappings
    """
    try:
        from app.api.services.framework_definitions import FRAMEWORK_REGISTRY
    except ImportError:
        pytest.skip("framework_definitions not yet implemented")

    soc2 = FRAMEWORK_REGISTRY.get("soc2")
    nist = FRAMEWORK_REGISTRY.get("nist_csf")

    assert soc2 is not None, "ADR-0006 violation: SOC2 framework not in registry"
    assert nist is not None, "ADR-0006 violation: NIST CSF framework not in registry"

    soc2_controls = sum(len(cat.controls) for cat in soc2.categories)
    nist_controls = sum(len(cat.controls) for cat in nist.categories)

    assert soc2_controls >= 20, (
        f"ADR-0006 violation: SOC2 has only {soc2_controls} controls, need ≥20"
    )
    assert nist_controls >= 15, (
        f"ADR-0006 violation: NIST CSF has only {nist_controls} controls, need ≥15"
    )
```

## More Information

**Relates to:** CM-003 (Regulatory Framework Mapping)

**Research Package:** [`research/compliance-frameworks-soc2-nist/`](../../research/compliance-frameworks-soc2-nist/) — full evidence including:
- SOC2 Trust Service Criteria complete control listing (CC1–CC9, A1, C1, PI1)
- NIST CSF 2.0 complete category/subcategory structure (6 functions, 22 categories)
- Azure built-in initiative group name conventions for SOC2 and NIST CSF
- Cross-framework equivalence mapping (SOC2 ↔ NIST CSF)

**Key References:**
- AICPA SOC 2 Trust Service Criteria: https://us.aicpa.org/interestareas/frc/assuranceadvisoryservices/trustservicescriteria
- NIST CSF 2.0: https://www.nist.gov/cyberframework (published February 26, 2024)
- Azure Policy SOC 2 Initiative: https://github.com/Azure/azure-policy (SOC_2.json)
- Azure Policy NIST CSF v2.0 Initiative: https://github.com/Azure/azure-policy (NIST_CSF_v2.0.json)

**Related ADRs:**
- [ADR-0005: Custom compliance rule engine](adr-0005-custom-compliance-rules.md) — custom rules that can also be mapped to frameworks
- [ADR-0004: Research-first protocol](adr-0004-research-first-protocol.md) — research methodology used

**Related Code:**
- `app/models/compliance.py` — `ComplianceSnapshot`, `PolicyState` models
- `app/api/services/compliance_service.py` — existing compliance service with `_map_severity()` keyword pattern
- `app/api/routes/compliance.py` — existing `/api/v1/compliance/*` routes
- `app/core/sync/compliance.py` — sync pipeline receiving `policy_definition_group_names`

**Disclaimer Requirement:**
All framework coverage endpoints MUST include a disclaimer:
> "Automated compliance coverage assessment based on Azure Policy state. This is not an audit opinion. SOC 2 Type II certification requires independent auditor evaluation of the full Trust Service Criteria including controls not assessable via automated policy checks."

**Future Evolution:**
- If MSP administrators require custom framework-to-policy mappings, consider a hybrid approach: code-embedded defaults with DB-stored overrides
- When Azure adds new built-in initiatives (e.g., PCI-DSS, ISO 27001), add corresponding framework definitions
- Consider caching coverage computations with TTL matching the compliance sync interval

**Review History:**
- 2026-03-20: Initial ADR proposed by Solutions Architect 🏛️ (`solutions-architect-43aef9`)
- Research conducted by: Web Puppy 🕵️
- Pending review: Security Auditor 🛡️ (STRIDE co-sign), Pack Leader 🐺 (sign-off)

---

**ADR Status:** Proposed
**Implementation Status:** ⏳ Pending (CM-003)
**Last Updated:** March 20, 2026
**Maintained By:** Solutions Architect 🏛️

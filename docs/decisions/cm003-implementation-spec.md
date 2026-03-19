# CM-003 Implementation Specification: Regulatory Framework Mapping

**ADR:** [ADR-0006](adr-0006-regulatory-framework-mapping.md)
**Status:** Ready for Implementation
**Target Implementer:** Python Programmer 🐍
**Estimated Effort:** 1 sprint (~3 days)

---

## File Structure

Create the following files:

```
app/api/services/framework_definitions.py   # Framework dataclasses + registries
app/api/services/framework_mapping_service.py # Service computing coverage
app/api/routes/compliance_frameworks.py       # API route handlers
app/schemas/framework.py                      # Pydantic response schemas
tests/unit/test_framework_definitions.py      # Unit tests for definitions
tests/unit/test_framework_mapping_service.py  # Unit tests for service
```

Modify the following existing files:

```
app/api/routes/__init__.py                    # Register new router
app/main.py                                   # Include new router
```

---

## 1. Framework Definitions (`app/api/services/framework_definitions.py`)

### Dataclass Definitions

```python
"""Regulatory framework definitions for SOC2 TSC and NIST CSF 2.0.

Code-embedded, frozen dataclasses per ADR-0006. These are static reference
data — framework definitions change on AICPA/NIST publication cycles (years).

SOC2 Trust Service Criteria: © AICPA. Control IDs and brief descriptions
referenced under fair use for compliance mapping. Not a reproduction of
the full criteria text.

NIST CSF 2.0: Public domain (US Government work). Published Feb 26, 2024.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FrameworkControl:
    """A single control within a regulatory framework."""

    id: str
    name: str
    description: str
    category_id: str


@dataclass(frozen=True)
class ControlCategory:
    """A category grouping related controls."""

    id: str
    name: str
    controls: tuple[FrameworkControl, ...]


@dataclass(frozen=True)
class RegulatoryFramework:
    """A complete regulatory framework definition."""

    id: str
    name: str
    version: str
    description: str
    categories: tuple[ControlCategory, ...]

    @property
    def total_controls(self) -> int:
        return sum(len(cat.controls) for cat in self.categories)

    @property
    def categories_count(self) -> int:
        return len(self.categories)

    def get_control(self, control_id: str) -> FrameworkControl | None:
        for cat in self.categories:
            for ctrl in cat.controls:
                if ctrl.id == control_id:
                    return ctrl
        return None

    def get_category(self, category_id: str) -> ControlCategory | None:
        for cat in self.categories:
            if cat.id == category_id:
                return cat
        return None
```

### SOC2 Framework Definition (≥20 controls)

```python
SOC2_FRAMEWORK = RegulatoryFramework(
    id="soc2",
    name="SOC 2 Type II",
    version="2017 with 2022 revisions",
    description="AICPA Trust Service Criteria for Security, Availability, Processing Integrity, Confidentiality, and Privacy",
    categories=(
        ControlCategory(
            id="CC1",
            name="Control Environment",
            controls=(
                FrameworkControl(id="CC1.1", name="COSO Principle 1", description="Commitment to integrity and ethical values", category_id="CC1"),
                FrameworkControl(id="CC1.2", name="COSO Principle 2", description="Board independence and oversight of internal controls", category_id="CC1"),
                FrameworkControl(id="CC1.3", name="COSO Principle 3", description="Management establishes structures, reporting lines, authorities", category_id="CC1"),
                FrameworkControl(id="CC1.4", name="COSO Principle 4", description="Commitment to attract, develop, and retain competent individuals", category_id="CC1"),
                FrameworkControl(id="CC1.5", name="COSO Principle 5", description="Accountability for internal control responsibilities", category_id="CC1"),
            ),
        ),
        ControlCategory(
            id="CC2",
            name="Communication and Information",
            controls=(
                FrameworkControl(id="CC2.1", name="COSO Principle 13", description="Obtains or generates quality information for internal control", category_id="CC2"),
                FrameworkControl(id="CC2.2", name="COSO Principle 14", description="Internally communicates information for internal control", category_id="CC2"),
                FrameworkControl(id="CC2.3", name="COSO Principle 15", description="Communicates with external parties regarding internal control", category_id="CC2"),
            ),
        ),
        ControlCategory(
            id="CC3",
            name="Risk Assessment",
            controls=(
                FrameworkControl(id="CC3.1", name="COSO Principle 6", description="Specifies objectives to identify and assess risks", category_id="CC3"),
                FrameworkControl(id="CC3.2", name="COSO Principle 7", description="Identifies and analyzes risks to achievement of objectives", category_id="CC3"),
                FrameworkControl(id="CC3.3", name="COSO Principle 8", description="Considers potential for fraud in assessing risks", category_id="CC3"),
                FrameworkControl(id="CC3.4", name="COSO Principle 9", description="Identifies and assesses changes that could impact internal controls", category_id="CC3"),
            ),
        ),
        ControlCategory(
            id="CC4",
            name="Monitoring Activities",
            controls=(
                FrameworkControl(id="CC4.1", name="COSO Principle 16", description="Selects, develops, and performs ongoing or separate evaluations", category_id="CC4"),
                FrameworkControl(id="CC4.2", name="COSO Principle 17", description="Evaluates and communicates internal control deficiencies timely", category_id="CC4"),
            ),
        ),
        ControlCategory(
            id="CC5",
            name="Control Activities",
            controls=(
                FrameworkControl(id="CC5.1", name="COSO Principle 10", description="Selects and develops control activities to mitigate risks", category_id="CC5"),
                FrameworkControl(id="CC5.2", name="COSO Principle 11", description="Selects and develops general controls over technology", category_id="CC5"),
                FrameworkControl(id="CC5.3", name="COSO Principle 12", description="Deploys control activities through policies and procedures", category_id="CC5"),
            ),
        ),
        ControlCategory(
            id="CC6",
            name="Logical and Physical Access Controls",
            controls=(
                FrameworkControl(id="CC6.1", name="Logical Access Security", description="Logical access security software, infrastructure, and architectures", category_id="CC6"),
                FrameworkControl(id="CC6.2", name="User Registration and Authorization", description="New users registered and authorized before credential issuance", category_id="CC6"),
                FrameworkControl(id="CC6.3", name="Access Modification and Removal", description="Access authorized, modified, and removed per documented rules", category_id="CC6"),
                FrameworkControl(id="CC6.4", name="Physical Access Restriction", description="Physical access restricted to authorized personnel only", category_id="CC6"),
                FrameworkControl(id="CC6.5", name="Data Disposal Protection", description="Data protection maintained until recovery capability diminished", category_id="CC6"),
                FrameworkControl(id="CC6.6", name="External Threat Protection", description="Protection against threats from outside system boundaries", category_id="CC6"),
                FrameworkControl(id="CC6.7", name="Transmission Protection", description="Restriction and protection of information transmission and movement", category_id="CC6"),
                FrameworkControl(id="CC6.8", name="Malicious Software Prevention", description="Prevention and detection of unauthorized or malicious software", category_id="CC6"),
            ),
        ),
        ControlCategory(
            id="CC7",
            name="System Operations",
            controls=(
                FrameworkControl(id="CC7.1", name="Vulnerability Detection", description="Detect configuration changes that introduce vulnerabilities", category_id="CC7"),
                FrameworkControl(id="CC7.2", name="Anomaly Monitoring", description="Monitor system components for anomalies indicative of malicious acts", category_id="CC7"),
                FrameworkControl(id="CC7.3", name="Event Evaluation", description="Evaluate events to determine if security objectives are impacted", category_id="CC7"),
                FrameworkControl(id="CC7.4", name="Incident Response", description="Execute incident response procedures to contain and remediate", category_id="CC7"),
                FrameworkControl(id="CC7.5", name="Incident Recovery", description="Identify and implement recovery activities from security incidents", category_id="CC7"),
            ),
        ),
        ControlCategory(
            id="CC8",
            name="Change Management",
            controls=(
                FrameworkControl(id="CC8.1", name="Change Authorization and Implementation", description="Authorize, design, develop, test, approve, and implement changes", category_id="CC8"),
            ),
        ),
        ControlCategory(
            id="CC9",
            name="Risk Mitigation",
            controls=(
                FrameworkControl(id="CC9.1", name="Risk Identification and Assessment", description="Identify and assess risk from business partners and vendors", category_id="CC9"),
                FrameworkControl(id="CC9.2", name="Vendor Risk Management", description="Assess and manage risks associated with vendors and partners", category_id="CC9"),
            ),
        ),
        ControlCategory(
            id="A1",
            name="Availability",
            controls=(
                FrameworkControl(id="A1.1", name="Capacity Management", description="Maintain, monitor, and evaluate processing capacity and usage", category_id="A1"),
                FrameworkControl(id="A1.2", name="Backup and Recovery", description="Backup processes and recovery infrastructure for RTO/RPO", category_id="A1"),
                FrameworkControl(id="A1.3", name="Recovery Testing", description="Test recovery plan procedures for effectiveness", category_id="A1"),
            ),
        ),
        ControlCategory(
            id="C1",
            name="Confidentiality",
            controls=(
                FrameworkControl(id="C1.1", name="Confidential Information Identification", description="Identify and classify confidential information", category_id="C1"),
                FrameworkControl(id="C1.2", name="Confidential Information Disposal", description="Dispose of confidential information per retention policies", category_id="C1"),
            ),
        ),
        ControlCategory(
            id="PI1",
            name="Processing Integrity",
            controls=(
                FrameworkControl(id="PI1.1", name="Processing Accuracy", description="System processing is complete, valid, accurate, and timely", category_id="PI1"),
                FrameworkControl(id="PI1.2", name="Input Validation", description="System inputs are validated for completeness and accuracy", category_id="PI1"),
            ),
        ),
    ),
)
```

### NIST CSF 2.0 Framework Definition (≥15 controls)

```python
NIST_CSF_FRAMEWORK = RegulatoryFramework(
    id="nist_csf",
    name="NIST Cybersecurity Framework",
    version="2.0 (February 2024)",
    description="Framework for improving critical infrastructure cybersecurity — Govern, Identify, Protect, Detect, Respond, Recover",
    categories=(
        ControlCategory(
            id="GV",
            name="Govern",
            controls=(
                FrameworkControl(id="GV.OC-01", name="Organizational Context", description="Organizational mission is understood and informs cybersecurity risk management", category_id="GV"),
                FrameworkControl(id="GV.RM-01", name="Risk Management Strategy", description="Risk management objectives are established and agreed upon", category_id="GV"),
                FrameworkControl(id="GV.RR-01", name="Roles and Responsibilities", description="Cybersecurity roles and responsibilities are established", category_id="GV"),
                FrameworkControl(id="GV.PO-01", name="Policy", description="Cybersecurity policy is established based on organizational context", category_id="GV"),
                FrameworkControl(id="GV.SC-07", name="Supply Chain Risk", description="Supply chain risk management strategy includes priorities and tolerances", category_id="GV"),
            ),
        ),
        ControlCategory(
            id="ID",
            name="Identify",
            controls=(
                FrameworkControl(id="ID.AM-01", name="Hardware Asset Inventory", description="Inventories of hardware managed by the organization are maintained", category_id="ID"),
                FrameworkControl(id="ID.AM-02", name="Software Asset Inventory", description="Inventories of software, services, and systems are maintained", category_id="ID"),
                FrameworkControl(id="ID.AM-05", name="Asset Prioritization", description="Assets are prioritized based on classification, criticality, and mission impact", category_id="ID"),
                FrameworkControl(id="ID.RA-01", name="Vulnerability Identification", description="Vulnerabilities in assets are identified, validated, and recorded", category_id="ID"),
                FrameworkControl(id="ID.RA-07", name="Change Risk Assessment", description="Changes and exceptions are managed, assessed for risk impact", category_id="ID"),
            ),
        ),
        ControlCategory(
            id="PR",
            name="Protect",
            controls=(
                FrameworkControl(id="PR.AA-01", name="Identity and Credential Management", description="Identities and credentials for authorized users, services, hardware are managed", category_id="PR"),
                FrameworkControl(id="PR.AA-03", name="Authentication", description="Users, services, and hardware are authenticated", category_id="PR"),
                FrameworkControl(id="PR.AA-05", name="Access Permissions", description="Access permissions defined incorporating least privilege and separation of duties", category_id="PR"),
                FrameworkControl(id="PR.DS-01", name="Data at Rest Protection", description="Data-at-rest is protected with encryption and integrity measures", category_id="PR"),
                FrameworkControl(id="PR.DS-02", name="Data in Transit Protection", description="Data-in-transit is protected with encryption", category_id="PR"),
                FrameworkControl(id="PR.PS-02", name="Software Maintenance", description="Software is maintained, replaced, and removed in alignment with risk", category_id="PR"),
                FrameworkControl(id="PR.PS-04", name="Log Management", description="Adequate log management capacity is maintained", category_id="PR"),
                FrameworkControl(id="PR.PS-05", name="Unauthorized Software Prevention", description="Installation and execution of unauthorized software is prevented", category_id="PR"),
                FrameworkControl(id="PR.IR-01", name="Network Protection", description="Networks and environments are protected from unauthorized access", category_id="PR"),
            ),
        ),
        ControlCategory(
            id="DE",
            name="Detect",
            controls=(
                FrameworkControl(id="DE.CM-03", name="Personnel Activity Monitoring", description="Personnel activity and technology usage monitored for adverse events", category_id="DE"),
                FrameworkControl(id="DE.CM-09", name="Hardware and Software Monitoring", description="Computing hardware, software, runtime environments, and data are monitored", category_id="DE"),
                FrameworkControl(id="DE.AE-03", name="Event Correlation", description="Events are correlated from multiple sources", category_id="DE"),
                FrameworkControl(id="DE.AE-06", name="Incident Declaration", description="Information on adverse events is provided to authorized staff", category_id="DE"),
            ),
        ),
        ControlCategory(
            id="RS",
            name="Respond",
            controls=(
                FrameworkControl(id="RS.MA-01", name="Incident Management", description="Incident response plan is executed once an incident is declared", category_id="RS"),
                FrameworkControl(id="RS.AN-03", name="Incident Analysis", description="Analysis is performed to determine what has taken place during an incident", category_id="RS"),
                FrameworkControl(id="RS.CO-02", name="Stakeholder Notification", description="Internal and external stakeholders are notified of incidents", category_id="RS"),
                FrameworkControl(id="RS.CO-03", name="Information Sharing", description="Information is shared with designated stakeholders per response plan", category_id="RS"),
                FrameworkControl(id="RS.MI-01", name="Incident Containment", description="Incidents are contained and mitigated", category_id="RS"),
            ),
        ),
        ControlCategory(
            id="RC",
            name="Recover",
            controls=(
                FrameworkControl(id="RC.RP-01", name="Recovery Execution", description="Restoration activities are performed to ensure operational availability", category_id="RC"),
                FrameworkControl(id="RC.RP-04", name="Integrity Verification", description="Integrity of backups and assets is verified before restoration", category_id="RC"),
                FrameworkControl(id="RC.CO-03", name="Recovery Communication", description="Recovery activities and progress are communicated to stakeholders", category_id="RC"),
            ),
        ),
    ),
)
```

### Keyword-to-Control Mapping Tables

```python
# ============================================================================
# Tier 1: Azure initiative group name → framework control mapping
# These come from policy_definition_group_names in the Azure Policy SDK
# and are stored in PolicyState.policy_category as CSV
# ============================================================================

AZURE_GROUP_TO_CONTROLS: dict[str, list[tuple[str, str]]] = {
    # SOC 2 initiative group names
    "SOC_2_CC6.1": [("soc2", "CC6.1")],
    "SOC_2_CC6.2": [("soc2", "CC6.2")],
    "SOC_2_CC6.3": [("soc2", "CC6.3")],
    "SOC_2_CC6.4": [("soc2", "CC6.4")],
    "SOC_2_CC6.5": [("soc2", "CC6.5")],
    "SOC_2_CC6.6": [("soc2", "CC6.6")],
    "SOC_2_CC6.7": [("soc2", "CC6.7")],
    "SOC_2_CC6.8": [("soc2", "CC6.8")],
    "SOC_2_CC7.1": [("soc2", "CC7.1")],
    "SOC_2_CC7.2": [("soc2", "CC7.2")],
    "SOC_2_CC7.3": [("soc2", "CC7.3")],
    "SOC_2_CC7.4": [("soc2", "CC7.4")],
    "SOC_2_CC7.5": [("soc2", "CC7.5")],
    "SOC_2_CC8.1": [("soc2", "CC8.1")],
    "SOC_2_CC9.1": [("soc2", "CC9.1")],
    "SOC_2_CC9.2": [("soc2", "CC9.2")],
    "SOC_2_A1.1": [("soc2", "A1.1")],
    "SOC_2_A1.2": [("soc2", "A1.2")],
    "SOC_2_A1.3": [("soc2", "A1.3")],
    "SOC_2_C1.1": [("soc2", "C1.1")],
    "SOC_2_C1.2": [("soc2", "C1.2")],
    "SOC_2_PI1.1": [("soc2", "PI1.1")],
    "SOC_2_PI1.2": [("soc2", "PI1.2")],
    # NIST CSF 2.0 initiative group names
    "NIST_CSF_v2.0_GV.OC_01": [("nist_csf", "GV.OC-01")],
    "NIST_CSF_v2.0_GV.SC_07": [("nist_csf", "GV.SC-07")],
    "NIST_CSF_v2.0_ID.AM_01": [("nist_csf", "ID.AM-01")],
    "NIST_CSF_v2.0_ID.AM_02": [("nist_csf", "ID.AM-02")],
    "NIST_CSF_v2.0_ID.RA_01": [("nist_csf", "ID.RA-01")],
    "NIST_CSF_v2.0_ID.RA_07": [("nist_csf", "ID.RA-07")],
    "NIST_CSF_v2.0_PR.AA": [("nist_csf", "PR.AA-01")],
    "NIST_CSF_v2.0_PR.AA_01": [("nist_csf", "PR.AA-01")],
    "NIST_CSF_v2.0_PR.AA_03": [("nist_csf", "PR.AA-03")],
    "NIST_CSF_v2.0_PR.AA_05": [("nist_csf", "PR.AA-05")],
    "NIST_CSF_v2.0_PR.DS": [("nist_csf", "PR.DS-01")],
    "NIST_CSF_v2.0_PR.DS_01": [("nist_csf", "PR.DS-01")],
    "NIST_CSF_v2.0_PR.DS_02": [("nist_csf", "PR.DS-02")],
    "NIST_CSF_v2.0_PR.PS_02": [("nist_csf", "PR.PS-02")],
    "NIST_CSF_v2.0_PR.PS_04": [("nist_csf", "PR.PS-04")],
    "NIST_CSF_v2.0_PR.PS_05": [("nist_csf", "PR.PS-05")],
    "NIST_CSF_v2.0_PR.IR_01": [("nist_csf", "PR.IR-01")],
    "NIST_CSF_v2.0_DE.CM": [("nist_csf", "DE.CM-03")],
    "NIST_CSF_v2.0_DE.CM_03": [("nist_csf", "DE.CM-03")],
    "NIST_CSF_v2.0_DE.CM_09": [("nist_csf", "DE.CM-09")],
    "NIST_CSF_v2.0_DE.AE": [("nist_csf", "DE.AE-03")],
    "NIST_CSF_v2.0_DE.AE_03": [("nist_csf", "DE.AE-03")],
    "NIST_CSF_v2.0_DE.AE_06": [("nist_csf", "DE.AE-06")],
    "NIST_CSF_v2.0_RS.CO_02": [("nist_csf", "RS.CO-02")],
    "NIST_CSF_v2.0_RS.CO_03": [("nist_csf", "RS.CO-03")],
    "NIST_CSF_v2.0_RC.RP": [("nist_csf", "RC.RP-01")],
    "NIST_CSF_v2.0_RC.RP_04": [("nist_csf", "RC.RP-04")],
}


# ============================================================================
# Tier 2: Keyword set → framework control mapping (fallback)
# When Azure group names aren't available, match on policy_name keywords.
# Each entry: (required_keywords, mapped_controls)
# A policy matches if ALL keywords in the frozenset appear in its
# policy_name.lower() or policy_category.lower()
# ============================================================================

KEYWORD_CONTROL_MAP: list[tuple[frozenset[str], list[tuple[str, str]]]] = [
    # Identity and Access
    (frozenset({"mfa"}), [("soc2", "CC6.1"), ("nist_csf", "PR.AA-01"), ("nist_csf", "PR.AA-03")]),
    (frozenset({"multi-factor"}), [("soc2", "CC6.1"), ("nist_csf", "PR.AA-01"), ("nist_csf", "PR.AA-03")]),
    (frozenset({"authentication"}), [("soc2", "CC6.1"), ("nist_csf", "PR.AA-03")]),
    (frozenset({"password"}), [("soc2", "CC6.1"), ("nist_csf", "PR.AA-01")]),
    (frozenset({"identity"}), [("soc2", "CC6.1"), ("soc2", "CC6.2"), ("nist_csf", "PR.AA-01")]),
    (frozenset({"access", "control"}), [("soc2", "CC6.3"), ("nist_csf", "PR.AA-05")]),
    (frozenset({"role", "assignment"}), [("soc2", "CC6.3"), ("nist_csf", "PR.AA-05")]),
    (frozenset({"permission"}), [("soc2", "CC6.3"), ("nist_csf", "PR.AA-05")]),
    (frozenset({"rbac"}), [("soc2", "CC6.3"), ("nist_csf", "PR.AA-05")]),
    (frozenset({"privileged"}), [("soc2", "CC6.3"), ("nist_csf", "PR.AA-05")]),

    # Network and Infrastructure
    (frozenset({"firewall"}), [("soc2", "CC6.6"), ("nist_csf", "PR.IR-01")]),
    (frozenset({"network", "security"}), [("soc2", "CC6.6"), ("nist_csf", "PR.IR-01")]),
    (frozenset({"nsg"}), [("soc2", "CC6.6"), ("nist_csf", "PR.IR-01")]),
    (frozenset({"private", "endpoint"}), [("soc2", "CC6.6"), ("nist_csf", "PR.IR-01")]),
    (frozenset({"public", "access"}), [("soc2", "CC6.6"), ("nist_csf", "PR.IR-01")]),
    (frozenset({"ddos"}), [("soc2", "CC6.6"), ("nist_csf", "PR.IR-01")]),
    (frozenset({"waf"}), [("soc2", "CC6.6"), ("nist_csf", "PR.IR-01")]),

    # Encryption and Data Protection
    (frozenset({"encryption"}), [("soc2", "CC6.7"), ("nist_csf", "PR.DS-01")]),
    (frozenset({"tls"}), [("soc2", "CC6.7"), ("nist_csf", "PR.DS-02")]),
    (frozenset({"ssl"}), [("soc2", "CC6.7"), ("nist_csf", "PR.DS-02")]),
    (frozenset({"https"}), [("soc2", "CC6.7"), ("nist_csf", "PR.DS-02")]),
    (frozenset({"encryption", "transit"}), [("soc2", "CC6.7"), ("nist_csf", "PR.DS-02")]),
    (frozenset({"encryption", "rest"}), [("soc2", "CC6.7"), ("nist_csf", "PR.DS-01")]),
    (frozenset({"key", "vault"}), [("soc2", "CC6.7"), ("nist_csf", "PR.DS-01")]),
    (frozenset({"secret"}), [("soc2", "CC6.7"), ("nist_csf", "PR.DS-01")]),
    (frozenset({"cmk"}), [("soc2", "CC6.7"), ("nist_csf", "PR.DS-01")]),

    # Malware and Software Security
    (frozenset({"antimalware"}), [("soc2", "CC6.8"), ("nist_csf", "PR.PS-05")]),
    (frozenset({"defender"}), [("soc2", "CC6.8"), ("soc2", "CC7.1"), ("nist_csf", "DE.CM-09")]),
    (frozenset({"vulnerability"}), [("soc2", "CC7.1"), ("nist_csf", "ID.RA-01"), ("nist_csf", "DE.CM-09")]),
    (frozenset({"secure", "score"}), [("soc2", "CC7.1"), ("nist_csf", "DE.CM-09")]),
    (frozenset({"security", "center"}), [("soc2", "CC7.1"), ("nist_csf", "DE.CM-09")]),

    # Monitoring and Detection
    (frozenset({"monitor"}), [("soc2", "CC7.2"), ("nist_csf", "DE.CM-09")]),
    (frozenset({"diagnostic"}), [("soc2", "CC7.2"), ("nist_csf", "PR.PS-04"), ("nist_csf", "DE.CM-03")]),
    (frozenset({"log"}), [("soc2", "CC7.2"), ("nist_csf", "PR.PS-04"), ("nist_csf", "DE.CM-03")]),
    (frozenset({"audit"}), [("soc2", "CC7.2"), ("nist_csf", "DE.CM-03")]),
    (frozenset({"alert"}), [("soc2", "CC7.3"), ("nist_csf", "DE.AE-06")]),
    (frozenset({"sentinel"}), [("soc2", "CC7.2"), ("nist_csf", "DE.AE-03")]),

    # Resource and Asset Management
    (frozenset({"tag"}), [("soc2", "CC3.1"), ("nist_csf", "ID.AM-01")]),
    (frozenset({"inventory"}), [("nist_csf", "ID.AM-01"), ("nist_csf", "ID.AM-02")]),
    (frozenset({"naming"}), [("nist_csf", "ID.AM-01")]),

    # Backup and Recovery
    (frozenset({"backup"}), [("soc2", "A1.2"), ("nist_csf", "RC.RP-01"), ("nist_csf", "RC.RP-04")]),
    (frozenset({"disaster", "recovery"}), [("soc2", "A1.2"), ("soc2", "A1.3"), ("nist_csf", "RC.RP-01")]),
    (frozenset({"geo-redundant"}), [("soc2", "A1.2"), ("nist_csf", "RC.RP-01")]),
    (frozenset({"availability"}), [("soc2", "A1.1")]),
    (frozenset({"scaling"}), [("soc2", "A1.1")]),

    # Cost and Billing (low severity — maps to governance/oversight)
    (frozenset({"cost"}), [("nist_csf", "GV.OC-01")]),
    (frozenset({"billing"}), [("nist_csf", "GV.OC-01")]),
]


# ============================================================================
# Framework Registry — the single lookup point
# ============================================================================

FRAMEWORK_REGISTRY: dict[str, RegulatoryFramework] = {
    "soc2": SOC2_FRAMEWORK,
    "nist_csf": NIST_CSF_FRAMEWORK,
}
```

---

## 2. Framework Mapping Service (`app/api/services/framework_mapping_service.py`)

### Method Signatures with Type Hints

```python
"""Service for computing regulatory framework compliance coverage.

Maps PolicyState records to framework controls using the two-tier
strategy defined in ADR-0006: Azure group names (Tier 1) and keyword
matching (Tier 2).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.api.services.framework_definitions import (
    AZURE_GROUP_TO_CONTROLS,
    FRAMEWORK_REGISTRY,
    KEYWORD_CONTROL_MAP,
    ControlCategory,
    FrameworkControl,
    RegulatoryFramework,
)
from app.core.auth import User
from app.models.compliance import PolicyState

logger = logging.getLogger(__name__)

# Disclaimer required by ADR-0006
COVERAGE_DISCLAIMER = (
    "Automated compliance coverage assessment based on Azure Policy state. "
    "This is not an audit opinion. SOC 2 Type II certification requires "
    "independent auditor evaluation of the full Trust Service Criteria "
    "including controls not assessable via automated policy checks."
)


@dataclass
class ControlCoverage:
    """Coverage data for a single framework control."""

    control: FrameworkControl
    status: str  # "covered" | "not_covered" | "partial"
    matched_policies_count: int
    compliant_count: int
    non_compliant_count: int
    compliance_percent: float
    matched_policies: list[dict[str, Any]]  # policy details when requested


@dataclass
class CategoryCoverage:
    """Coverage data for a control category."""

    category: ControlCategory
    coverage_percent: float
    controls: list[ControlCoverage]


@dataclass
class FrameworkCoverageResult:
    """Complete coverage result for a framework."""

    framework: RegulatoryFramework
    overall_coverage_percent: float
    categories: list[CategoryCoverage]
    disclaimer: str = COVERAGE_DISCLAIMER


class FrameworkMappingService:
    """Computes regulatory framework compliance coverage from PolicyState data."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_frameworks(
        self,
        tenant_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return all available frameworks with summary coverage.

        Args:
            tenant_ids: Optional tenant filter for coverage computation.

        Returns:
            List of framework summary dicts for the API response.
        """
        ...

    def get_framework_coverage(
        self,
        framework_id: str,
        tenant_ids: list[str] | None = None,
        include_policies: bool = False,
    ) -> FrameworkCoverageResult | None:
        """Compute full coverage for a specific framework.

        Args:
            framework_id: Framework ID ("soc2" or "nist_csf").
            tenant_ids: Optional tenant filter.
            include_policies: Whether to include matched policy details.

        Returns:
            FrameworkCoverageResult with per-control coverage, or None
            if framework_id is not found.
        """
        ...

    def _get_policy_states(
        self,
        tenant_ids: list[str] | None = None,
    ) -> list[PolicyState]:
        """Query PolicyState records with optional tenant filtering.

        Args:
            tenant_ids: Optional tenant filter.

        Returns:
            List of PolicyState records.
        """
        ...

    def _map_policy_to_controls(
        self,
        policy: PolicyState,
    ) -> list[tuple[str, str]]:
        """Map a single PolicyState to framework controls.

        Uses two-tier strategy:
        1. Azure group name matching from policy_category
        2. Keyword matching from policy_name

        Args:
            policy: A PolicyState record.

        Returns:
            List of (framework_id, control_id) tuples.
        """
        ...

    def _compute_control_coverage(
        self,
        control: FrameworkControl,
        matched_policies: list[PolicyState],
        include_details: bool = False,
    ) -> ControlCoverage:
        """Compute coverage for a single control based on matched policies.

        Args:
            control: The framework control definition.
            matched_policies: Policies mapped to this control.
            include_details: Whether to include full policy details.

        Returns:
            ControlCoverage with compliance stats.
        """
        ...

    def _compute_category_coverage(
        self,
        category: ControlCategory,
        control_coverages: list[ControlCoverage],
    ) -> CategoryCoverage:
        """Compute coverage for a category from its control coverages.

        Coverage percent = (controls with ≥1 matched policy) / total controls × 100

        Args:
            category: The control category definition.
            control_coverages: Coverage data for each control in the category.

        Returns:
            CategoryCoverage with aggregated stats.
        """
        ...
```

### Implementation Logic (for Python Programmer)

**`_map_policy_to_controls` algorithm:**
1. Split `policy.policy_category` by comma (it's stored as CSV)
2. For each group name, look up in `AZURE_GROUP_TO_CONTROLS` → add matched (framework_id, control_id)
3. If no Tier 1 matches found, build `text = (policy.policy_name or "").lower() + " " + (policy.policy_category or "").lower()`
4. For each `(keyword_set, controls)` in `KEYWORD_CONTROL_MAP`: if ALL keywords in `keyword_set` appear in `text`, add the controls
5. Deduplicate the result list

**`get_framework_coverage` algorithm:**
1. Get framework from `FRAMEWORK_REGISTRY[framework_id]`
2. Query all `PolicyState` records (filtered by tenant_ids)
3. Build `control_to_policies: dict[str, list[PolicyState]]` by mapping each policy via `_map_policy_to_controls`, filtering to the requested framework_id
4. For each category → for each control → compute `ControlCoverage`
5. For each category → compute `CategoryCoverage`
6. Overall coverage = mean of category coverage percentages
7. Return `FrameworkCoverageResult`

**Coverage percentage definition:**
- **Control level**: `compliant_count / (compliant_count + non_compliant_count) * 100` — among policies mapped to this control, what fraction are compliant
- **Category level**: `controls_with_any_policy / total_controls_in_category * 100` — what fraction of controls have at least one mapped policy
- **Framework level**: mean of all category coverage percentages

---

## 3. API Routes (`app/api/routes/compliance_frameworks.py`)

```python
"""Regulatory framework compliance mapping routes — CM-003."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.api.services.framework_mapping_service import FrameworkMappingService
from app.core.auth import User, get_current_user
from app.core.authorization import TenantAuthorization, get_tenant_authorization
from app.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/compliance/frameworks",
    tags=["compliance-frameworks"],
    dependencies=[Depends(get_current_user)],
)


@router.get("")
async def list_frameworks(
    tenant_ids: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
) -> dict:
    """List all available regulatory frameworks with coverage summaries.

    Returns SOC2 Trust Service Criteria and NIST CSF 2.0 with
    overall compliance coverage percentages computed from current
    PolicyState data.
    """
    authz.ensure_at_least_one_tenant()
    filtered_tenant_ids = authz.filter_tenant_ids(tenant_ids)

    service = FrameworkMappingService(db)
    frameworks = service.list_frameworks(tenant_ids=filtered_tenant_ids)
    return {"frameworks": frameworks}


@router.get("/{framework_id}")
async def get_framework_coverage(
    framework_id: str = Path(..., pattern="^(soc2|nist_csf)$"),
    tenant_ids: list[str] | None = Query(default=None),
    include_policies: bool = Query(default=False),
    db: Session = Depends(get_db),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
) -> dict:
    """Get full framework mapping with per-control compliance coverage.

    Args:
        framework_id: "soc2" or "nist_csf"
        tenant_ids: Optional tenant filter
        include_policies: Include matched policy details per control
    """
    authz.ensure_at_least_one_tenant()
    filtered_tenant_ids = authz.filter_tenant_ids(tenant_ids)

    service = FrameworkMappingService(db)
    result = service.get_framework_coverage(
        framework_id=framework_id,
        tenant_ids=filtered_tenant_ids,
        include_policies=include_policies,
    )

    if result is None:
        raise HTTPException(status_code=404, detail=f"Framework '{framework_id}' not found")

    # Serialize the result
    return {
        "framework": {
            "id": result.framework.id,
            "name": result.framework.name,
            "version": result.framework.version,
            "description": result.framework.description,
        },
        "overall_coverage_percent": round(result.overall_coverage_percent, 1),
        "disclaimer": result.disclaimer,
        "categories": [
            {
                "id": cat_cov.category.id,
                "name": cat_cov.category.name,
                "coverage_percent": round(cat_cov.coverage_percent, 1),
                "controls": [
                    {
                        "id": ctrl_cov.control.id,
                        "name": ctrl_cov.control.name,
                        "description": ctrl_cov.control.description,
                        "status": ctrl_cov.status,
                        "matched_policies_count": ctrl_cov.matched_policies_count,
                        "compliant_count": ctrl_cov.compliant_count,
                        "non_compliant_count": ctrl_cov.non_compliant_count,
                        "compliance_percent": round(ctrl_cov.compliance_percent, 1),
                        **({"matched_policies": ctrl_cov.matched_policies} if include_policies else {}),
                    }
                    for ctrl_cov in cat_cov.controls
                ],
            }
            for cat_cov in result.categories
        ],
    }
```

---

## 4. Pydantic Response Schemas (`app/schemas/framework.py`)

```python
"""Pydantic schemas for regulatory framework compliance responses."""

from pydantic import BaseModel, Field


class FrameworkSummary(BaseModel):
    """Summary of a single regulatory framework."""

    id: str
    name: str
    version: str
    description: str
    total_controls: int
    categories_count: int
    coverage_summary: "CoverageSummary"


class CoverageSummary(BaseModel):
    """High-level coverage numbers for a framework."""

    controls_with_coverage: int
    controls_without_coverage: int
    overall_coverage_percent: float = Field(ge=0, le=100)


class FrameworkListResponse(BaseModel):
    """Response for GET /api/v1/compliance/frameworks."""

    frameworks: list[FrameworkSummary]


class MatchedPolicy(BaseModel):
    """A policy matched to a framework control."""

    policy_name: str
    compliance_state: str
    non_compliant_count: int
    mapping_confidence: str = "high"  # "high" for Tier 1, "medium" for Tier 2


class ControlDetail(BaseModel):
    """Detailed compliance status for a single framework control."""

    id: str
    name: str
    description: str
    status: str  # "covered" | "not_covered" | "partial"
    matched_policies_count: int
    compliant_count: int
    non_compliant_count: int
    compliance_percent: float = Field(ge=0, le=100)
    matched_policies: list[MatchedPolicy] | None = None


class CategoryDetail(BaseModel):
    """Compliance coverage for a control category."""

    id: str
    name: str
    coverage_percent: float = Field(ge=0, le=100)
    controls: list[ControlDetail]


class FrameworkCoverageResponse(BaseModel):
    """Response for GET /api/v1/compliance/frameworks/{framework_id}."""

    framework: FrameworkSummary
    overall_coverage_percent: float = Field(ge=0, le=100)
    disclaimer: str
    categories: list[CategoryDetail]


# Rebuild forward refs
FrameworkSummary.model_rebuild()
```

---

## 5. Registration in Existing Code

### `app/api/routes/__init__.py` — add import

```python
from app.api.routes.compliance_frameworks import router as compliance_frameworks_router
# Add to __all__:
"compliance_frameworks_router",
```

### `app/main.py` — include router

```python
from app.api.routes.compliance_frameworks import router as compliance_frameworks_router
app.include_router(compliance_frameworks_router)
```

---

## 6. Cross-Framework Control Equivalence

For reference, these SOC2 ↔ NIST CSF controls are equivalent and share keyword mappings:

| SOC 2 | NIST CSF 2.0 | Topic |
|-------|-------------|-------|
| CC6.1 | PR.AA-01, PR.AA-03 | Identity & credential management, MFA |
| CC6.3 | PR.AA-05 | Access authorization, RBAC, least privilege |
| CC6.6 | PR.IR-01 | Network protection, firewall, NSG |
| CC6.7 | PR.DS-01, PR.DS-02 | Encryption at rest and in transit |
| CC6.8 | PR.PS-05, DE.CM-09 | Malware prevention, Defender |
| CC7.1 | ID.RA-01, DE.CM-09 | Vulnerability detection, Secure Score |
| CC7.2 | DE.CM-03, DE.AE-03 | Monitoring, logging, SIEM |
| CC7.4 | RS.MA-01 | Incident response |
| CC7.5 | RC.RP-01 | Incident recovery |
| CC8.1 | ID.RA-07, PR.PS-02 | Change management |
| CC9.2 | GV.SC-07 | Vendor/supply chain risk |
| A1.2 | RC.RP-01, RC.RP-04 | Backup and recovery |

---

## 7. Test Plan Summary

### Unit tests to write:

1. **`test_framework_definitions.py`** (~10 tests):
   - All framework dataclasses are frozen
   - SOC2 has ≥20 controls
   - NIST CSF has ≥15 controls
   - All controls have valid category_id references
   - `get_control()` and `get_category()` work correctly
   - `FRAMEWORK_REGISTRY` contains both frameworks

2. **`test_framework_mapping_service.py`** (~15 tests):
   - Tier 1 Azure group name mapping works
   - Tier 2 keyword matching works
   - Policies with no keywords return empty mapping
   - Coverage percentages compute correctly (0%, 50%, 100%)
   - Tenant filtering works
   - `list_frameworks()` returns all frameworks
   - `get_framework_coverage()` returns None for unknown framework
   - Disclaimer is included in all responses
   - `include_policies=True` includes policy details
   - `include_policies=False` omits policy details

3. **`test_compliance_frameworks_routes.py`** (~8 tests):
   - `GET /api/v1/compliance/frameworks` returns 200
   - `GET /api/v1/compliance/frameworks/soc2` returns 200
   - `GET /api/v1/compliance/frameworks/nist_csf` returns 200
   - `GET /api/v1/compliance/frameworks/unknown` returns 404 or 422
   - Authentication required (401 without token)
   - Tenant isolation enforced

---

**Spec Version:** 1.0
**Last Updated:** March 20, 2026
**Author:** Solutions Architect 🏛️ (`solutions-architect-43aef9`)

# Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records (ADRs) for the Azure Governance Platform, documenting significant architectural and design decisions using the MADR 4.0 format.

## What is an ADR?

An Architecture Decision Record (ADR) captures an important architectural decision made along with its context and consequences. ADRs help teams:

- **Understand the rationale** behind past decisions
- **Avoid revisiting settled debates** repeatedly
- **Onboard new team members** faster by providing historical context
- **Track the evolution** of the system architecture over time

## When to Write an ADR

Write an ADR when you make a decision that:

- Has **significant impact** on the system architecture
- Affects **multiple components** or teams
- Involves **trade-offs** between competing concerns
- Requires **justification** to stakeholders
- May need to be **revisited** in the future

### Examples of ADR-worthy decisions:

✅ **Write an ADR for:**
- Choosing a web framework (FastAPI vs Flask vs Django)
- Selecting a database technology (PostgreSQL vs SQLite vs MongoDB)
- Deciding on authentication strategy (OAuth vs SAML vs JWT)
- Adopting a new architectural pattern (multi-agent vs monolithic)
- Changing deployment strategy (VMs vs containers vs serverless)

❌ **Don't write an ADR for:**
- Variable naming conventions
- Code formatting choices (use linters)
- Minor refactoring within a single module
- Routine bug fixes
- Implementation details that don't affect architecture

## How to Create an ADR

### 1. Copy the Template

```bash
cp docs/decisions/adr-template.md docs/decisions/adr-NNNN-your-decision-title.md
```

### 2. Choose a Number

ADRs are numbered sequentially starting from 0001. Check the directory for the highest number and use the next one:

```bash
ls docs/decisions/adr-*.md | sort -V | tail -1
# If last is adr-0003-*, your new ADR is adr-0004-*
```

### 3. Write Your ADR

Follow the template structure:

1. **Metadata** - Status, date, decision-makers, consulted parties
2. **Title** - Short, present tense imperative ("Use FastAPI for Backend")
3. **Context** - What problem are you solving? Why now?
4. **Decision Drivers** - What factors influenced the decision?
5. **Considered Options** - What alternatives did you evaluate?
6. **Decision Outcome** - What did you choose and why?
7. **Consequences** - What are the positive and negative outcomes?
8. **STRIDE Security Analysis** - Security implications (REQUIRED)
9. **Pros and Cons** - Detailed analysis of each option
10. **More Information** - Links, references, validation criteria

### 4. Get Review

ADRs should be reviewed by:
- **Solutions Architect** 🏛️ (architecture concerns)
- **Security Auditor** 🛡️ (STRIDE analysis verification)
- **Relevant domain experts** (depending on the decision)
- **Pack Leader** 🐺 (final sign-off)

### 5. Update Status

ADR lifecycle:

```
proposed → accepted → {deprecated | superseded by ADR-NNNN}
                  ↘
                   rejected
```

- **proposed** - Under discussion
- **accepted** - Implemented and in use
- **rejected** - Decided not to implement
- **deprecated** - No longer recommended
- **superseded by ADR-NNNN** - Replaced by a newer decision

## STRIDE Security Analysis

**Every ADR must include a STRIDE security analysis section.** This is a project requirement to ensure security is considered in all architectural decisions.

### STRIDE Categories:

| Category | What to Consider |
|----------|------------------|
| **S**poofing | Can someone impersonate a user or system component? |
| **T**ampering | Can data or code be maliciously modified? |
| **R**epudiation | Can someone deny performing an action? |
| **I**nformation Disclosure | Can sensitive data be exposed? |
| **D**enial of Service | Can the system be made unavailable? |
| **E**levation of Privilege | Can someone gain unauthorized access? |

### Example:

```markdown
## STRIDE Security Analysis

| Threat Category | Risk Level | Mitigation |
|-----------------|-----------|------------|
| **Spoofing** | Low | Azure AD authentication required for all API endpoints |
| **Tampering** | Medium | API requests validated; database has audit logs |
| **Repudiation** | Low | All actions logged with user ID and timestamp |
| **Information Disclosure** | Medium | Tenant isolation enforced; role-based access control |
| **Denial of Service** | Low | Rate limiting and circuit breakers implemented |
| **Elevation of Privilege** | Low | Least-privilege principle; per-agent tool filtering |

**Overall Security Posture:** This decision maintains the current security posture with no new attack surfaces introduced.
```

## File Naming Convention

```
adr-NNNN-short-title-with-dashes.md
```

- **NNNN** - Sequential number with leading zeros (0001, 0002, ...)
- **short-title** - Present tense, imperative, lowercase with dashes
- **.md** - Markdown file extension

### Good Examples:
- `adr-0001-multi-agent-architecture.md`
- `adr-0002-per-agent-tool-filtering.md`
- `adr-0003-local-first-issue-tracking.md`
- `adr-0004-use-fastapi-for-backend.md`

### Bad Examples:
- ❌ `adr-1-multi-agent.md` (number not zero-padded)
- ❌ `adr-0001-Multi_Agent_Architecture.md` (wrong case, underscores)
- ❌ `adr-0001-why-we-chose-multi-agent.md` (not imperative)
- ❌ `multi-agent-decision.md` (missing adr- prefix and number)

## ADR Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [0001](adr-0001-multi-agent-architecture.md) | Use multi-agent architecture for Code Puppy | accepted | 2026-03-06 |
| [0002](adr-0002-per-agent-tool-filtering.md) | Implement per-agent tool filtering | accepted | 2026-03-06 |
| [0003](adr-0003-local-first-issue-tracking.md) | Use bd for local-first issue tracking | accepted | 2026-03-06 |
| [0004](adr-0004-research-first-protocol.md) | Mandate research-first protocol for all ADRs | accepted | 2026-03-06 |
| [0005](adr-0005-compliance-rule-engine.md) | Use JSON Schema for custom compliance rule definitions | proposed | 2026-03-19 |
| [0006](adr-0006-regulatory-framework-mapping.md) | Map compliance findings to SOC2 and NIST CSF controls | proposed | 2026-03-20 |
| [0007](adr-0007-auth-evolution.md) | Authentication Architecture Evolution: Phase A→B→C | accepted | 2025-02-15 |
| [0008](adr-0008-container-registry.md) | Container Registry Migration: ACR → GHCR | accepted | 2025-01-28 |
| [0009](adr-0009-database-tier.md) | Database Tier Selection: Standard → Free Tier | accepted | 2025-02-10 |
| [0010](adr-0010-sync-reliability.md) | Sync Reliability: Prevent cascading multi-tenant failures | accepted | 2025-04-15 |
| [0011](adr-0011-granular-rbac.md) | Granular RBAC with permission-based access control | accepted | 2025-05-20 |

## References

- **MADR Official**: https://adr.github.io/madr/
- **MADR GitHub**: https://github.com/adr/madr
- **STRIDE Threat Model**: https://learn.microsoft.com/en-us/azure/security/develop/threat-modeling-tool-threats
- **Research**: [research/solutions-architect-patterns/analysis/adr-formats.md](../../research/solutions-architect-patterns/analysis/adr-formats.md)

---

**Maintained By:** Solutions Architect 🏛️  
**Last Updated:** March 2025  
**Template Version:** MADR 4.0 with STRIDE Security Analysis

---
status: accepted
date: 2026-03-06
decision-makers: Solutions Architect, Planning Agent, Pack Leader
consulted: Experience Architect, Security Auditor, Web Puppy (research)
informed: All Code Puppy agents, development team
---

# Mandate research-first protocol for all ADRs

## Context and Problem Statement

Architecture decisions have long-term consequences on system design, security, performance, and maintainability. Decisions made without proper research can lead to:

- **Technical debt** from choosing outdated or inappropriate technologies
- **Rework** when better alternatives are discovered after implementation
- **Missed best practices** that the industry has already established
- **Security vulnerabilities** from uninformed design choices
- **Incompatibility** with existing systems or future requirements

How can we ensure that every architecture decision is grounded in current, evidence-based research rather than assumptions, preferences, or outdated knowledge?

## Decision Drivers

- **Accuracy**: Decisions must be based on facts, not opinions or assumptions
- **Currency**: Technology landscape changes rapidly; research must reflect current state (2024-2026)
- **Evidence trail**: Need documented reasoning that can be reviewed and verified
- **Reproducibility**: Others should be able to validate the research that informed decisions
- **Best practices**: Industry has solved many problems; we should learn from established patterns
- **Security**: Many architectural decisions have security implications that require research
- **Compliance**: Azure governance requires justified, traceable decisions
- **Efficiency**: Better to research once thoroughly than to rework later
- **Knowledge transfer**: Research artifacts benefit future team members

## Considered Options

1. **No formal research requirement (ad-hoc)** - Agents make decisions based on their training data and general knowledge
2. **Manual research via browsing (human-dependent)** - Require human to research before writing ADRs
3. **Mandatory web-puppy research before every ADR (research-first protocol)** - Web Puppy 🕵️‍♂️ agent MUST be invoked to research topic before any ADR is drafted
4. **Research only for major decisions** - Require research for "big" decisions, allow ad-hoc for smaller ones

## Decision Outcome

Chosen option: **"Mandatory web-puppy research before every ADR (research-first protocol)"**, because it ensures all architecture decisions are evidence-based, traceable, and current, while creating a knowledge repository that benefits the entire team.

### Research-First Protocol

**Core Principle:** No Architecture Decision Record (ADR) may be created without first invoking Web Puppy 🕵️‍♂️ to conduct research on the topic.

**Process Flow:**

```
┌─────────────────────────────────────────────────────────────┐
│ 1. IDENTIFY DECISION                                        │
│    Solutions Architect or Experience Architect identifies   │
│    an architectural decision that requires an ADR           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. INVOKE WEB-PUPPY                                         │
│    Architect agent invokes Web Puppy with research prompt   │
│    Example: "Research MADR vs LADR vs C4 for ADR formats"  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. WEB-PUPPY RESEARCHES                                     │
│    Web Puppy searches web, analyzes sources, synthesizes    │
│    Saves research to research/{topic}/ directory:           │
│    - README.md (overview)                                   │
│    - analysis.md (detailed findings)                        │
│    - sources.md (bibliography with links)                   │
│    - recommendations.md (what to do)                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. REVIEW RESEARCH                                          │
│    Architect reads research artifacts, verifies quality     │
│    If insufficient: Request additional research             │
│    If adequate: Proceed to draft ADR                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. DRAFT ADR                                                │
│    Architect creates ADR referencing research directory     │
│    Example: "See research/solutions-architect-patterns/"    │
│    ADR must cite specific findings from research            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. REVIEW & VERIFICATION                                    │
│    Security Auditor / Reviewers check:                      │
│    ✓ Research directory exists for topic                    │
│    ✓ ADR references research findings                       │
│    ✓ Recommendations from research are addressed            │
│    ✓ STRIDE analysis informed by security research          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. ACCEPTANCE                                               │
│    Pack Leader signs off, ADR status → accepted             │
└─────────────────────────────────────────────────────────────┘
```

### Agent Workflow Integration

**Solutions Architect 🏛️ Instructions (Excerpt):**
```markdown
## Creating Architecture Decision Records (ADRs)

1. **RESEARCH FIRST** 🔍  
   BEFORE drafting any ADR, you MUST invoke Web Puppy to research the topic:
   
   - Identify key technologies/patterns to evaluate
   - Invoke Web Puppy: "Research [technology A] vs [technology B] for [use case]"
   - Wait for research to be saved to research/{topic}/ directory
   - Review README.md, analysis.md, sources.md, recommendations.md
   
2. **DRAFT ADR** 📝  
   Use research findings to inform your decision:
   - Reference research directory in ADR
   - Cite specific findings that influenced decision
   - Address alternatives mentioned in research
```

**Experience Architect 🎨 Instructions (Excerpt):**
```markdown
## Research-First UX Decisions

1. **RESEARCH REQUIREMENTS** 🔍  
   Before recommending any UX pattern, framework, or approach:
   
   - Invoke Web Puppy to research current best practices
   - Example: "Research accessible form validation patterns 2024"
   - Example: "Research WCAG 2.2 AA requirements for data tables"
   - Review research artifacts before making recommendations
```

### Research Directory Structure

All research is stored in `research/{topic}/` with standard structure:

```
research/
├── solutions-architect-patterns/
│   ├── README.md              # Research overview
│   ├── analysis.md            # Detailed findings
│   ├── sources.md             # Bibliography (all links)
│   ├── recommendations.md     # What to do
│   └── artifacts/             # Screenshots, PDFs, etc.
├── ux-accessibility-patterns/
│   ├── README.md
│   ├── analysis.md
│   ├── sources.md
│   └── recommendations.md
└── security-oauth-flows/
    ├── README.md
    ├── analysis.md
    ├── sources.md
    └── recommendations.md
```

### Consequences

- **Good**, because decisions are grounded in current evidence rather than assumptions
- **Good**, because research artifacts create a knowledge repository for the team
- **Good**, because evidence trail makes decisions auditable and defensible
- **Good**, because best practices from industry are systematically incorporated
- **Good**, because security implications are researched proactively
- **Good**, because research is reproducible (sources.md provides all links)
- **Good**, because onboarding new team members is easier (research explains the "why")
- **Good**, because reduces rework from uninformed decisions
- **Bad**, because adds time to decision-making process (research takes time)
- **Bad**, because creates dependency on Web Puppy agent availability
- **Bad**, because may slow down "urgent" decisions (though urgency shouldn't bypass research)
- **Neutral**, because requires discipline to follow protocol (but so does any good process)

### Confirmation

This protocol is validated by:

1. **Research directory exists**: `research/` at repo root with multiple topics
2. **ADRs reference research**: Each ADR includes "More Information" section linking to research/{topic}/
3. **Agent instructions updated**: Solutions Architect and Experience Architect prompts mandate research-first
4. **Review checklist includes verification**: Security Auditor and reviewers check for research artifacts
5. **Web Puppy agent operational**: Agent can be invoked and produces standard research structure

## STRIDE Security Analysis

| Threat Category | Risk Level | Mitigation |
|-----------------|-----------|------------|
| **Spoofing** | Low | Research sources are documented with URLs; can verify authenticity of information |
| **Tampering** | Medium | Research files are version-controlled in git; all changes tracked with audit trail |
| **Repudiation** | Low | Git commits show who created research; ADRs cite research explicitly |
| **Information Disclosure** | Low | Research may reference public security vulnerabilities, but stored in private repo |
| **Denial of Service** | Medium | If Web Puppy unavailable, ADR creation blocked; mitigation: cache research, allow manual research as fallback |
| **Elevation of Privilege** | Low | Research informs security decisions; better than uninformed decisions that might create vulnerabilities |

**Overall Security Posture:** This protocol **improves** security posture by ensuring security-relevant decisions are researched:

1. **Proactive threat analysis** - Security patterns researched before implementation
2. **Known vulnerability avoidance** - Research identifies CVEs and security issues with technologies
3. **Best practice adoption** - Industry security standards incorporated systematically
4. **Informed STRIDE analysis** - Security Auditor can reference research when evaluating ADRs

The "Denial of Service" risk (Web Puppy dependency) is mitigated by:
- Allowing manual research if Web Puppy is down (human can research and create research/ artifacts)
- Caching research for common topics (reusable across decisions)
- Web Puppy is a high-priority agent (Pack Leader ensures availability)

## Pros and Cons of the Options

### No formal research requirement (ad-hoc) (rejected)

*Agents make decisions based on their training data and general knowledge*

- Good, because fastest approach (no research time required)
- Good, because no dependency on Web Puppy agent
- Good, because simple process (just write the ADR)
- Bad, because **decisions may be based on outdated information** (LLM training data is stale)
- Bad, because **no evidence trail** - can't verify reasoning
- Bad, because **misses current best practices** (e.g., new security patterns from 2024-2026)
- Bad, because **high risk of rework** when better alternatives are discovered
- Bad, because **no knowledge transfer** - decisions are opaque to others
- Bad, because **LLM hallucinations** may go undetected (no fact-checking)

### Manual research via browsing (human-dependent) (rejected)

*Require human to research before writing ADRs*

- Good, because ensures research is conducted
- Good, because human can apply judgment and critical thinking
- Neutral, because research quality depends on human skill
- Bad, because **not scalable** - requires human in the loop for every ADR
- Bad, because **inconsistent methodology** - different people research differently
- Bad, because **no standard structure** - research artifacts vary in quality/format
- Bad, because **time-consuming for humans** - humans have other responsibilities
- Bad, because **knowledge not systematically captured** - may live in email/chat instead of repo

### Mandatory web-puppy research before every ADR (research-first protocol) (accepted)

*Current decision - see above for full analysis*

- Good, because evidence-based decisions
- Good, because creates knowledge repository
- Good, because reproducible and auditable
- Good, because incorporates current best practices
- Good, because systematic and scalable
- Bad, because adds time to decision process
- Bad, because dependency on Web Puppy agent

### Research only for major decisions (rejected)

*Require research for "big" decisions, allow ad-hoc for smaller ones*

- Good, because faster for "small" decisions
- Neutral, because some research is better than none
- Bad, because **"major vs minor" is subjective** - what's small to one person is major to another
- Bad, because **small decisions accumulate** - many small uninformed decisions = technical debt
- Bad, because **no clear threshold** - when does a decision cross from minor to major?
- Bad, because **inconsistent quality** - some ADRs researched, others not
- Bad, because **misses opportunities** - even "small" decisions benefit from research

## More Information

**Related Requirements:**
- REQ-101: Create Solutions Architect JSON agent
- REQ-102: Create Experience Architect JSON agent
- REQ-704: Implement research-first protocol (this ADR)

**Related ADRs:**
- [ADR-0001: Use multi-agent architecture](adr-0001-multi-agent-architecture.md) - Defines Web Puppy's role
- [ADR-0003: Use bd for local-first issue tracking](adr-0003-local-first-issue-tracking.md) - Research informed tool selection

**Related Documents:**
- [Agent Instructions](../../AGENTS.md) - Solutions Architect and Experience Architect
- [Research Directory](../../research/) - All research artifacts
- [Web Puppy Agent](~/.code_puppy/agents/web-puppy.json) - Research agent definition

**Research Examples:**
- [Solutions Architect Patterns Research](../../research/solutions-architect-patterns/) - Informed ADR format decision (MADR 4.0)
- [UX Accessibility Patterns Research](../../research/ux-accessibility-patterns/) - Informed WCAG requirements

**Validation Checklist:**

- ✅ Web Puppy agent created and operational
- ✅ Research directory structure established (`research/` at repo root)
- ✅ Solutions Architect instructions updated to mandate research-first
- ✅ Experience Architect instructions updated to mandate research-first
- ✅ ADR template includes "More Information" section for research links
- ✅ Review process includes verification of research artifacts
- ✅ At least 3 research topics documented (solutions-architect-patterns, etc.)

**Review History:**
- 2026-03-06: Initial decision documented
- Reviewed by: Security Auditor 🛡️ (STRIDE analysis), Solutions Architect 🏛️ (methodology)
- Consulted: Web Puppy 🕵️‍♂️ (research capability validation)
- Signed off by: Pack Leader 🐺, Planning Agent 📋

---

**ADR Status:** Accepted  
**Implementation Status:** ✅ Complete  
**Last Updated:** March 6, 2026

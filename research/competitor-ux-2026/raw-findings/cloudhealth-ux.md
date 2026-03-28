# CloudHealth (VMware Tanzu / Broadcom) — Raw UX Findings (March 2026)

**Sources:** news.broadcom.com press release (Jun 2025), techdocs.broadcom.com, vmware.com solution overview PDF
**Date Accessed:** March 27, 2026
**Tier:** 1-2 (official docs + press release)

---

## Product Identity
- **Full name:** VMware Tanzu CloudHealth (under Broadcom)
- **Category:** Cloud financial management / FinOps
- **Distribution:** Exclusively through Arrow Electronics (since 2024)
- **Recognition:** Named industry leader by 7 independent analyst firms in 2024

## New CloudHealth User Experience (June 2025 GA)

### Announcement Details
- **Date:** June 2, 2025
- **Venue:** FinOps X conference
- **Source:** GLOBE NEWSWIRE press release
- **Speaker:** Purnima Padmanabhan, General Manager, Tanzu Division, Broadcom

### Intelligent Assist (AI Co-Pilot)
- Generative AI FinOps co-pilot embedded in platform
- Large language model-enabled chatbot
- **Capabilities:**
  - Natural-language queries about clouds and services
  - Granular custom report generation via conversation
  - Cost usage recommendations
  - Insights exploration for non-technical users
- **Design goal:** "Break down barriers to entry for business-oriented personas"
- **Collaboration focus:** Makes data accessible to all decision-makers
- **Key quote:** "Enabling technical and non-technical users alike"

### Smart Summary
- AI-generated summaries of cloud cost changes
- Automated pattern recognition for cost shifts
- Industry-leading approach to understanding cost changes
- Reduces manual analysis effort

### Design Philosophy
- "Tool for the entire team" — not just FinOps practitioners
- "All personas of all backgrounds" — democratize access
- "Culture of accountability and collaboration"
- Reduce barriers to entry for FinOps tools

## Documentation Structure (techdocs.broadcom.com)
**Last Updated:** March 24, 2026

### Topic Areas
1. **Getting Started with CloudHealth**
2. **Using and Managing CloudHealth**
3. **Working with Reports and Recommendations**
4. **Working with Partner Platform**
5. **Exploring New CloudHealth Experience** — dedicated section for new UX
6. **CloudHealth Release Naming Convention**

### Feature Cross-Reference Table (from docs index)
| Use Case | Feature |
|----------|---------|
| Configure cost thresholds | Policies |
| Multiple organizational units, access management | FlexOrgs |
| View anomalies and cost impact | Anomaly Dashboard |
| Make upfront monetary commitment (AWS) | AWS Reservation Management |
| Analyze bill data on-demand across any variable | FlexReports |

## Solution Overview (VMware PDF)

### Target Personas
1. FinOps practitioners
2. Cloud architects
3. Platform operators
4. Engineering/app developers
5. Executives

### Key Benefits
1. **Make sense of cloud data** — Visibility for multi-cloud, dynamic business groups (Perspectives), fully custom reporting
2. **Optimize and control cloud spend** — Tailored recommendations, governance policies, automated actions

### Key Concepts
- **FlexOrgs:** Hierarchical organization → OUs with access, sharing, and delegation control
- **Perspectives:** Dynamic business grouping — allocate assets to business groups without changing underlying data structure
- **FlexReports:** Ad-hoc analysis across any dimension

## Multi-Tenant Governance UX
- Parent org → child OUs with inheritance model
- Users scoped to their OU assignment
- Admin/parent roles get cross-OU reporting
- Delegation of access and responsibility per OU level

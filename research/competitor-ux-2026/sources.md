# Sources — Competitor UX Analysis (March 2026)

---

## Tier 1 Sources (Official Documentation)

### Microsoft Learn — Azure Cost Management
- **URL:** https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/quick-acm-cost-analysis
- **Date Accessed:** March 27, 2026
- **Authority:** ★★★★★ Official Microsoft documentation
- **Currency:** Continuously updated, version-controlled
- **Content Used:** Smart views vs. customizable views UX patterns, KPI row layout, insights panel, tab system, scope selector, inline budget creation
- **Reliability:** Highest — primary source, matches live Azure Portal UX

### Microsoft Learn — Azure Policy Overview
- **URL:** https://learn.microsoft.com/en-us/azure/governance/policy/overview
- **Date Accessed:** March 27, 2026
- **Authority:** ★★★★★ Official Microsoft documentation
- **Currency:** Continuously updated
- **Content Used:** Policy evaluation model, compliance states, scope hierarchy
- **Reliability:** Highest — primary source

### Microsoft Learn — Defender for Cloud Overview Dashboard
- **URL:** https://learn.microsoft.com/en-us/azure/defender-for-cloud/overview-page
- **Date Accessed:** March 27, 2026
- **Authority:** ★★★★★ Official Microsoft documentation
- **Currency:** Continuously updated (redirected to cloud-infrastructure-dashboard)
- **Content Used:** Dashboard sections, top actions bar, trends over time, security at a glance KPIs, paired chart pattern
- **Reliability:** Highest — primary source with screenshots

### Microsoft Learn — Azure Lighthouse
- **URL:** https://learn.microsoft.com/en-us/azure/lighthouse/how-to/view-manage-customers
- **Date Accessed:** March 27, 2026
- **Authority:** ★★★★★ Official Microsoft documentation
- **Currency:** Continuously updated
- **Content Used:** My Customers table view, delegation management, scope switching UX
- **Reliability:** Highest — primary source

### Broadcom TechDocs — CloudHealth
- **URL:** https://techdocs.broadcom.com/us/en/ca-enterprise-software/it-operations-management/cloudhealth/saas/index.html
- **Date Accessed:** March 27, 2026 (Last Updated: March 24, 2026)
- **Authority:** ★★★★★ Official product documentation
- **Currency:** Very current (updated 3 days prior)
- **Content Used:** FlexOrgs introduction, Perspectives, Anomaly Dashboard, FlexReports, New CloudHealth Experience section
- **Reliability:** Highest — primary source

---

## Tier 2 Sources (Vendor Product Marketing + Press Releases)

### Vantage.sh — Product Pages
- **URLs:**
  - https://www.vantage.sh (homepage)
  - https://www.vantage.sh/features (features overview)
  - https://www.vantage.sh/features/cost-reports (cost reports detail)
- **Date Accessed:** March 27, 2026
- **Authority:** ★★★★☆ Official vendor website with live UI screenshots
- **Currency:** Current (live product marketing)
- **Content Used:** Cost Reports UI layout, KPI cards, filter bar, workspace selector, virtual tagging rule builder, waste detection UI, Kubernetes rightsizing tooltip
- **Reliability:** High — product marketing with embedded UI screenshots, but may show best-case scenarios
- **Bias:** Vendor marketing; UX screenshots likely cherry-picked

### Broadcom Press Release — New CloudHealth UX
- **URL:** https://lite.aol.com/tech/story/0022/20250602/9461084.htm (mirror of news.broadcom.com release)
- **Date:** June 2, 2025 (GLOBE NEWSWIRE)
- **Authority:** ★★★★☆ Official press release via news wire
- **Currency:** 10 months old but describes current product version
- **Content Used:** Intelligent Assist (AI co-pilot), Smart Summary features, Arrow Electronics partnership, FinOps X conference launch
- **Reliability:** High — official press release with quotes from Broadcom GM
- **Bias:** Promotional language, but facts are verifiable

### VMware — CloudHealth Solution Overview PDF
- **URL:** https://www.vmware.com/docs/solution-overview-vmware-tanzu-cloudhealth-simplify-cloud-financial-management
- **Date Accessed:** March 27, 2026
- **Authority:** ★★★★☆ Official vendor documentation (PDF)
- **Currency:** Undated but current product positioning
- **Content Used:** Target personas, key benefits, Perspectives and FlexOrgs description
- **Reliability:** High — official vendor document

### Flexera One — Product Pages
- **URLs:**
  - https://www.flexera.com/products/flexera-one (platform overview)
  - https://www.flexera.com/products/flexera-one/finops (FinOps features)
- **Date Accessed:** March 27, 2026
- **Authority:** ★★★★☆ Official vendor website with UI screenshots
- **Currency:** Current (live product marketing)
- **Content Used:** Sidebar navigation structure, Automation Catalog card layout, policy card actions (Unpublish/Apply), FinOps phases (Inform, Optimize, Operate)
- **Reliability:** High — product marketing with embedded UI screenshots
- **Bias:** Vendor marketing; screenshots may show ideal scenarios

### CoreStack — Product Pages
- **URLs:**
  - https://www.corestack.io (homepage)
  - https://go.corestack.io/platform-tour (interactive demo)
- **Date Accessed:** March 27, 2026
- **Authority:** ★★★★☆ Official vendor website
- **Currency:** Current (©2025 in footer)
- **Content Used:** "Accounts Governance Dashboard" as central hub, Agentic AI positioning, customer logos, FOCUS™ compliance
- **Reliability:** High for product positioning; limited UI detail (demo requires interaction)
- **Bias:** Vendor marketing; interactive demo limited without account

### Turbot — Product Pages
- **URL:** https://turbot.com
- **Date Accessed:** March 27, 2026
- **Authority:** ★★★★☆ Official vendor website
- **Currency:** Current (Launch Week 12 banner, PSPM announcement)
- **Content Used:** PSPM pivot, prevention-first architecture, integration with Wiz/Cortex/Pipes, 6-feature "Power of Prevention" framework, dark theme design
- **Reliability:** High — official vendor with clear product positioning
- **Bias:** Vendor marketing; represents strategic pivot, may downplay traditional governance features

---

## Tier 3 Sources (Image Search / Secondary)

### DuckDuckGo Image Search — CloudHealth Dashboard
- **Search:** "CloudHealth dashboard UI screenshots cost management multi-tenant FlexOrgs"
- **Date Accessed:** March 27, 2026
- **Authority:** ★★½☆☆ Mixed results from various sources
- **Content Used:** Visual reference for CloudHealth dashboard layout
- **Reliability:** Medium — images may be outdated; source attribution varies

### DuckDuckGo Image Search — CoreStack Dashboard
- **Search:** "CoreStack governance dashboard compliance multi-cloud UI screenshots"
- **Date Accessed:** March 27, 2026
- **Authority:** ★★½☆☆ Mixed results from various sources
- **Content Used:** Visual reference for CoreStack dashboard layout, FOCUS dashboard mention
- **Reliability:** Medium — images may be outdated

---

## Cross-Reference Validation

| Claim | Primary Source | Cross-Reference | Validated? |
|-------|---------------|-----------------|-----------|
| CloudHealth has AI co-pilot (Intelligent Assist) | Broadcom press release (Jun 2025) | Broadcom TechDocs (Mar 2026) | ✅ Yes |
| Vantage has workspace selector + cost KPI badges | vantage.sh product page | Previous research (Mar 2026) | ✅ Yes |
| Azure Cost Analysis has smart views + insights | Microsoft Learn docs | Live Azure Portal (verifiable) | ✅ Yes |
| Turbot pivoted to PSPM | turbot.com homepage | "Introducing PSPM" banner on site | ✅ Yes |
| CoreStack uses "Accounts Governance Dashboard" | Interactive demo modal | corestack.io product copy | ✅ Yes |
| Flexera has Automation Catalog with cards | flexera.com/products/flexera-one/finops | UI screenshot on page | ✅ Yes |
| CloudHealth FlexOrgs for multi-tenant | Broadcom TechDocs | VMware solution overview PDF | ✅ Yes |

---

## Sources Not Used (Evaluated and Rejected)

| Source | Reason for Rejection |
|--------|---------------------|
| G2/Capterra reviews of competitors | Reviews focus on features/satisfaction, not UX patterns |
| YouTube competitor demos | Most are 12+ months old, UX may have changed |
| Third-party comparison sites (SelectHub, etc.) | Feature checklists, not UX analysis |
| Reddit/HN discussions | Anecdotal, not verifiable, often outdated |

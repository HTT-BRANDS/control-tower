# Flexera One — Raw UX Findings (March 2026)

**Sources:** flexera.com/products/flexera-one, flexera.com/products/flexera-one/finops
**Date Accessed:** March 27, 2026
**Tier:** 2 (vendor product marketing with UI screenshots)

---

## Product Identity
- **Full name:** Flexera One
- **Tagline:** "Optimize your IT with full visibility, cost control & compliance"
- **Category:** SaaS suite for hybrid IT spend and risk management
- **Note:** Absorbed RightScale (acquired 2018) and Spot.io is NOT part of Flexera (Spot.io → NetApp → discontinued/redirected)

## Product Modules
- **IT Visibility** — Discovery and inventory across all IT
- **IT Asset Management** — Hardware, software license management
- **SaaS Management** — SaaS application governance
- **FinOps** — Cloud cost optimization
- **Data Collection** — Connectors and data ingestion

## FinOps Page

### Headline
- "Expand FinOps savings to software licenses and SaaS"
- Three FinOps phases: Inform, Optimize, Operate

### Recommended Products (right sidebar)
- Cloud Cost Optimization
- Cloud Governance
- Data Center & Cloud
- MSPs

### Key Messaging
- "Unified platform for FinOps, ITAM, and SaaS"
- "Break down silos and facilitate cross-team collaboration"
- "Calculate total cost of ownership (TCO) for the cloud"
- "40% average savings with cloud cost optimization" (stat)

## UI Screenshot: Automation Catalog

### Left Sidebar Navigation
```
🔍 Search
🏠 Home
⭐ Favorites
📁 Workspaces
📊 Dashboards
🏢 Business Services
👁 IT Visibility
☁ SaaS
☁ Cloud
⚡ Automation (active)
📥 Data Collection
🏛 Organization
⚙ Administration
```

### Main Content Area
- **Breadcrumb:** Automation / Catalog
- **Filter bar:** Categories (0 selected) | Clear all | Show: Published | Search: "AWS, Instances, Resources"
- **View toggle:** Grid (tile) / List (rows) icons

### Policy Cards (Grid View)
**Card 1: "Untagged Resources"**
- Published on Jul 26, 2023 by support@flexera.com
- Deprecated notice + link to README
- Buttons: [Unpublish] [Apply]

**Card 2: "Azure AHUB Utilization with..."**
- Published on Feb 13, 2023 by support@flexera.com
- Description about Azure Hybrid Benefit
- Buttons: [Unpublish] [Apply]

**Card 3: "Azure Regulatory Compliance"**
- Published on Feb 13, 2023 by support@flexera.com
- Policy overview for Regulatory Compliance controls
- Link to README and docs.flexera.com
- Buttons: [Unpublish] [Apply]

**Card 4: "Azure Tag Resources with N..."**
- Published on Feb 13, 2023 by support@flexera.com
- Scan resources in Azure Subscription, tag with Name/Resource Group
- Buttons: [Unpublish] [Apply]

### Card Layout Pattern
```
┌──────────────────────────────────┐
│ [Icon] Title                     │
│ Published on [date] by [email]   │
│                                  │
│ [Description text, truncated]    │
│ [Link to docs if applicable]     │
│                                  │
│ [Unpublish]  [Apply]            │
└──────────────────────────────────┘
```

## "Operate" Section Screenshot
- **Header:** "Operate FinOps at scale"
- **Description:** Leverage automation for hybrid multi-cloud, extensible cost-savings policies, software licensing impacts
- **Companion screenshot:** Shows the Automation Catalog in context
- **CTA:** "Learn More →"

## Design Language
- **Primary color:** Blue (#0078D4-ish)
- **Background:** Dark navy for hero, white for content areas
- **Typography:** Clean sans-serif
- **Chat widget:** Intercom-style "Welcome to Flexera!" — can overlap content
- **Density:** Medium — professional enterprise look

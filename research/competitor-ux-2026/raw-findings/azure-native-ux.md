# Azure Portal Native Governance Tools — Raw UX Findings (March 2026)

**Sources:** learn.microsoft.com (Azure Cost Management, Azure Policy, Defender for Cloud, Azure Lighthouse)
**Date Accessed:** March 27, 2026
**Tier:** 1 (official Microsoft documentation)

---

## Azure Cost Management + Billing — Cost Analysis

### Two View Types
1. **Smart Views** (pre-built, intelligent)
   - Open in tabs within Cost Analysis
   - Include: KPIs, intelligent insights (anomaly detection), expandable details, hierarchical breakdown
   - Up to 5 tabs open simultaneously
   - Examples: Services view, Subscriptions view, Reservations view

2. **Customizable Views** (user-editable)
   - Open in custom view editor
   - Can be saved and shared
   - Full chart customization

### View Navigation
- **Recent section:** Recently used views
- **All views section:** All saved + Microsoft-provided views
- **Pin to recent:** Quick access shortcut from All views
- **Recommended:** System-suggested views based on common usage

### Cost Analysis UI Layout

#### Header
- **Scope:** Management group or subscription with "(change)" link
- **Tabs:** Named view tabs + "+" button (up to 5 tabs)
- **Toolbar:** Customize | Download | ••• (3-dot menu)

#### Filter Bar
- **Filter rows:** Button to add/remove column filters
- **Date pill:** "Jan 2023" with ← → arrows for period navigation
  - Click date text for menu with calendar, presets, etc.

#### KPI Row (3 KPIs)
- **Total (USD):** $3,318 ↑0% — large value with change indicator
- **Average:** $370.33/day — per-day average
- **Budget:** None → "[create]" — inline action link
  - Clicking "[create]" opens inline dialog:
    ```
    ┌─────────────────────────┐
    │ Create budget            │
    │ Amount: [________]       │
    │ Configure advanced       │
    │ settings ⓘ              │
    │ [Create] [Cancel]        │
    └─────────────────────────┘
    ```

#### Metadata
- "Showing 9 subscriptions" — result count below KPIs

#### Data View
- **Table:** Sortable columns (Name, ID, Total)
- **Area chart:** Cumulative cost over time (in customizable views)

### Cost Insights Panel
- **Trigger:** "See insights" link below KPIs
- **Panel content:** Overlay/slide-in from right
- **Header:** "Insights — Cost insights provide a highlight of your cost and usage patterns along with recommendations to increase your savings. Learn more"
- **Insight items:**
  ```
  Daily run rate: X% on [Date]
  Estimated cost [increased/decreased] X% on [Date] compared
  to the average daily usage during the last 60 days. ⓘ
  Updated X days ago
  Is this helpful? 👍 👎
  ```
- Multiple insights listed vertically
- Each has "Is this helpful?" feedback mechanism

### Left Sidebar (Cost Management Blade)
```
├── Overview
├── Change scope
├── Access control
├── Diagnose and solve problems
├── Give feedback about this menu
│
├── Cost analysis ← (current)
├── Exports
├── Monitoring
├── Optimization
├── Advisor
├── Reservations + Hybrid Benefit
│
├── Configurations
├── Preview Features
│
├── Usage + charges
└── Invoices
```

---

## Azure Policy

### Compliance Model
- **Rule format:** JSON policy definitions
- **Grouping:** Policy initiatives (policySets) for business rule groups
- **Scope hierarchy:** Management groups → Subscriptions → Resource groups → Individual resources
- **Compliance states:** Compliant, Non-compliant, Exempt, Unknown
- **Effects:** Append, Audit, AuditIfNotExist, DeployIfNotExists, Modify, Deny, Deploy

### Evaluation Timing
- New assignment: ~5 minutes to start
- Resource change: ~15 minutes for individual resource
- Subscription-level: ~30 minutes
- Standard cycle: Every 24 hours
- On-demand scan: Asynchronous, REST-triggered

### Key UX Notes
- Compliance dashboard is point-in-time (no built-in trend visualization)
- Must use Azure Resource Graph or Power BI for trend analysis
- Export to CSV available
- Remediation tasks for non-compliant resources

---

## Microsoft Defender for Cloud — Cloud Overview Dashboard

### Top Controls (Filter Bar)
```
📅 Last 7 days ▼  |  🔍 Environment Filter: Off  |  🎯 Scope filter: Off ⓘ
```
- **Time range presets:** Last 7 days, 30 days, 3 months, 6 months
- Applies to all historical graphs and trend indicators

### Dashboard Section 1: "Security at a glance"
- **Cloud Secure Score** (preview): Overall cloud security risk score with trend indicator
- **Threat Protection:** Number of alerts by severity
- **Assets Coverage:** Protected assets count with coverage status
  - **Full:** Assets covered by posture AND protection plans
  - **Partial:** Assets protected by posture OR protection plans
  - **None:** Unprotected assets
- Connected cloud and code environments list

### Dashboard Section 2: "Top Actions" Bar
Three prioritized action items in a horizontal bar:
1. **Critical Recommendations** — "Review critical recommendations to strengthen security posture"
2. **High-Severity Incidents** — "Resolve high severity to mitigate immediate threats"
3. **Attack Paths** — "Explore and investigate critical attack paths"

### Dashboard Section 3: "Trends over time"
Two paired charts side by side:

**Left: Security Posture**
- Line chart showing Cloud Secure Score over time
- Blue series: Secure Score
- Time axis: Monthly (Jan through Jul)
- Link: "View cloud initiative"

**Right: Security Recommendations**
- Stacked bar chart by severity level
- Colors: Red (Critical), Orange (High), Yellow (Medium), Gray (Low)
- Count labels on bars (175, 1005, 8743, 6675...)
- Link: "View recommendations"

**Below:** Threat Detection section
- "View security alert trends by severity"
- Separate chart for alert volume trends

### Target Users (from docs)
- **Cloud Security Admins & Architects:** Monitor posture, threats, and trends across environments
- **Workload Owners (DevOps, Developers):** Track scoped issues and act on them

---

## Azure Lighthouse — Multi-Tenant Management

### "My Customers" View

#### Access Path
- Navigate to "Customers" from service menu → "My customers" section

#### Customer List Table
- **Columns:** Name | Customer ID (tenant ID) | Offer ID | Offer version | Delegations
- **Delegations column:** Count of delegated subscriptions and resource groups

#### Top Controls
- Sort by any column
- Filter by specific customers, offers, or keywords
- Group by criteria

#### Detail Navigation
- Click customer → customer detail view
- **Available sections:**
  - View and manage customer details
  - View and manage delegations
  - View delegation change activity
  - Work in the context of a delegated subscription
  - Cloud Solution Provider (Preview)

#### Context Switching Pattern
- "Work in the context of a delegated subscription" — key UX pattern
- Service provider can switch context to act within a customer's subscription
- Provides cross-tenant management without leaving the portal

### Key Limitation for Our Platform
- Azure Lighthouse provides **per-customer** views but does NOT aggregate data across customers
- Our platform's value is specifically in this cross-tenant aggregation
- No unified dashboard across all delegated subscriptions in native Azure

---

## Cross-Tool UX Patterns in Azure Portal

### Common UI Elements Across All Azure Governance Blades
1. **Breadcrumb navigation** with scope context
2. **Left sidebar** organized by function group
3. **"Change scope"** link in header for tenant/subscription switching
4. **"Diagnose and solve problems"** link in every blade
5. **Filter bar** with time range, resource type, and custom filters
6. **Export** options (CSV, Power BI, Azure Resource Graph)
7. **"Was this page helpful?"** feedback in documentation

### Azure Portal's Key UX Weakness (Our Opportunity)
Each governance tool is a **separate blade** with no unified dashboard:
- Cost Management blade
- Azure Policy blade
- Defender for Cloud blade
- Lighthouse blade
- Entra ID (Identity) blade

Our platform provides a **single pane of glass** across all these, which is the #1 UX differentiator.

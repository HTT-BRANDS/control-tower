# Cross-Competitor UX Patterns — Synthesis

**Research Date:** March 27, 2026

---

## 1. Summary → Drill-Down Navigation Pattern

### Universal 3-Level Hierarchy
Every governance dashboard follows this pattern:

```
┌─────────────────────────────────────────────────────────────────┐
│ LEVEL 1: KPI Summary Bar (3-5 key metrics, always above fold)  │
│ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐              │
│ │ Metric 1│ │ Metric 2│ │ Metric 3│ │ Metric 4│              │
│ │ $12.3K  │ │ 87%     │ │ 3 🔴    │ │ 1,234   │              │
│ │ ▲ 8.2%  │ │ ▼ 2.1%  │ │         │ │         │              │
│ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘              │
│      │           │           │           │                     │
│ ─────▼───────────▼───────────▼───────────▼──────────────────── │
│ LEVEL 2: Category Breakdown (2x2 or 3-col grid, expandable)   │
│ ┌──────────────────┐ ┌──────────────────┐                     │
│ │ Cost Breakdown   │ │ Compliance       │                     │
│ │ • Top services   │ │ • Score trend    │                     │
│ │ • Anomalies      │ │ • Non-compliant  │                     │
│ │ [View Details →] │ │ [View Details →] │                     │
│ └──────────────────┘ └──────────────────┘                     │
│ ┌──────────────────┐ ┌──────────────────┐                     │
│ │ Identity         │ │ Resources        │                     │
│ │ • MFA status     │ │ • Orphaned       │                     │
│ │ • Guest users    │ │ • Untagged       │                     │
│ │ [View Details →] │ │ [View Details →] │                     │
│ └──────────────────┘ └──────────────────┘                     │
│                                                                │
│ ─────────────────────────────────────────────────────────────── │
│ LEVEL 3: Detail View (full tables, charts, inline actions)     │
│ Reached via "View Details" link or clicking a KPI card         │
│ Full-page or slide-in panel, with back navigation              │
└─────────────────────────────────────────────────────────────────┘
```

### Per-Platform Variations

| Platform | L1 (Summary) | L2 (Categories) | L3 (Detail) |
|----------|-------------|-----------------|-------------|
| Vantage | 2 KPI cards (Accrued + Forecasted) | Cost table below KPIs | Not shown in marketing |
| CloudHealth | FlexOrgs overview | Perspectives groupings | FlexReports drill-down |
| Flexera | Not prominent | Card catalog | Card detail + Apply |
| Azure Cost | 3 KPIs (Total, Avg, Budget) | Area chart + table | Insights panel overlay |
| Azure Defender | 3 "at a glance" metrics | Paired trend charts | Top Actions bar |
| CoreStack | Accounts Dashboard | Per-account governance | Agentic AI suggestions |

---

## 2. Multi-Tenant / Multi-Account Switching

### Pattern Taxonomy

**A. Dropdown Selector (Most Common)**
- Used by: Vantage (workspace), Azure Cost Analysis (scope)
- Position: Top-left or top-center
- Behavior: Changes context for entire page
- UX: Quick, familiar, one click

**B. Hierarchical Tree (Enterprise)**
- Used by: CloudHealth (FlexOrgs), Azure (Management Groups)
- Position: Scope selection modal/panel
- Behavior: Navigate org tree to select scope level
- UX: Powerful but complex, requires understanding of hierarchy

**C. Table List (Management View)**
- Used by: Azure Lighthouse (My Customers), CoreStack (Accounts Dashboard)
- Position: Main content area
- Behavior: Table with sort/filter/group, click row for context switch
- UX: Good for overview across all tenants, weak for quick switching

**D. Sidebar Navigation Item**
- Used by: Flexera (Workspaces)
- Position: Left sidebar
- Behavior: Opens workspace management page
- UX: Persistent but requires extra click

### Recommendation for Our Platform
**Use Pattern A (Dropdown Selector)** for 4-5 tenants:
```html
<select id="tenant-scope" class="...">
  <option value="all">All Tenants (5)</option>
  <optgroup label="Riverside">
    <option value="htt">HTT</option>
    <option value="bcc">BCC</option>
    <option value="fn">FN</option>
    <option value="tll">TLL</option>
  </optgroup>
  <optgroup label="Standalone">
    <option value="dce">DCE</option>
  </optgroup>
</select>
```

For >10 tenants, upgrade to Pattern B (hierarchical tree).

---

## 3. Compliance Trend Visualization

### Current Industry Approaches

**A. Paired Side-by-Side Charts (Best)**
- Used by: Azure Defender for Cloud
- Layout: Score trend line chart || Recommendations stacked bar chart
- Why it works: Visual correlation between posture improvement and gap closure

**B. Single Score Trend (Common)**
- Used by: Azure Defender (Secure Score), CoreStack
- Layout: Line chart of compliance score over time
- Why it works: Simple, clear trend. Misses "why" behind changes.

**C. Point-in-Time Snapshot (Basic)**
- Used by: Azure Policy (native), most tools
- Layout: Current state only, no history
- Why it works: Simple. Fails to show progress or regression.

**D. Anomaly-Based (Cost-Focused)**
- Used by: Vantage, CloudHealth
- Layout: Tab or panel showing anomalies with cost impact
- Why it works: Actionable alerts. Not suitable for compliance trends.

### Recommendation for Our Platform
**Use Pattern A (Paired Charts)** for Riverside dashboard:
```
┌──────────────────────────┐ ┌──────────────────────────┐
│ Maturity Score Trend     │ │ Requirement Status Trend │
│                          │ │                          │
│ ──── Overall (2.4→?)     │ │ ███ Compliant            │
│ ─ ─ Target (3.0)         │ │ ███ In Progress          │
│ ──── IAM domain          │ │ ███ Not Started           │
│ ──── GS domain           │ │                          │
│                          │ │                          │
│ [View maturity →]        │ │ [View requirements →]    │
└──────────────────────────┘ └──────────────────────────┘
```

---

## 4. Inline Actions vs. Navigation Required

### Inline Actions (Things Users Can Do Without Leaving the Page)

| Action | Platform | Implementation |
|--------|----------|---------------|
| Create budget | Azure Cost Analysis | Inline dialog with Amount field + Create/Cancel |
| Apply policy | Flexera | Button on policy card (no modal) |
| Save view | Vantage | Split button with dropdown (Save / Save As / ...) |
| Acknowledge anomaly | Azure Defender | Checkbox + bulk action toolbar |
| Change time range | All platforms | Dropdown or pill selector in filter bar |
| Filter by category | All platforms | Filter chips or dropdown |
| Export data | Azure | Download button in toolbar |

### Navigation Required (Things That Force Page Change)

| Action | Platform | Current Implementation |
|--------|----------|----------------------|
| View resource detail | All platforms | Full page navigation |
| Configure alert rules | Most platforms | Settings/admin page |
| Create compliance rule | Most platforms | Separate form page |
| View audit history | Most platforms | Dedicated audit page |

### Key Insight
The best UX puts **read + acknowledge + triage** actions inline, and reserves full-page navigation for **creation, configuration, and deep analysis**.

---

## 5. Alert/Notification Management

### Pattern Taxonomy

**A. Top Actions Bar (Best for Prioritization)**
- Used by: Azure Defender for Cloud
- Shows: Max 3 prioritized actions (Critical Recommendations, High-Severity Incidents, Attack Paths)
- UX: Always visible, forces focus on most important items

**B. Insights Panel (Best for Discovery)**
- Used by: Azure Cost Analysis
- Shows: AI-generated insights with daily rate changes, cost anomalies
- UX: Slide-in overlay, doesn't replace current view, has per-item feedback

**C. Sidebar Navigation Item (Adequate)**
- Used by: Vantage (Issues), most platforms
- Shows: Alert/issue list on dedicated page
- UX: Out of sight, easy to ignore

**D. Tab-Based (Adequate for Cost Anomalies)**
- Used by: Vantage (Anomalies tab within Cost Reports)
- Shows: Anomalies as a parallel view to cost data
- UX: Good for cost anomalies specifically, one click away

**E. Prevention-First (Radical)**
- Used by: Turbot
- Shows: Minimize alerts by preventing issues
- UX: Reduces noise. "Reduce alerts by 60%."

### Recommendation for Our Platform
**Combine A + B:**
1. **Top Actions Bar** on dashboard with 3 most critical items (from Riverside gaps, cost anomalies, identity risks)
2. **Insights Panel** accessible via button, showing detailed anomaly callouts with acknowledge/dismiss actions

---

## 6. Design System Patterns Across Competitors

### Color Usage for Status/Severity

| Status | Vantage | Azure | Flexera | Defender |
|--------|---------|-------|---------|----------|
| Critical | — | Red (#FF0000 area) | — | Red |
| High | — | Orange | — | Orange |
| Warning/Medium | — | Yellow | — | Yellow |
| Good/Low | Green badge | Green | Green | Gray |
| Bad/Increase | Red badge | Red indicator | — | Red |
| Neutral | Gray | Gray | Blue | Gray |

### Information Density Spectrum

```
Low Density ←────────────────────────────────→ High Density
    Turbot    Vantage    Flexera    Azure    CloudHealth    CoreStack
```

### Navigation Patterns

| Pattern | Platforms |
|---------|-----------|
| Left sidebar (persistent) | ALL platforms |
| Top horizontal nav | Vantage, Turbot (marketing only) |
| Breadcrumb | Azure, Flexera |
| Tabs within content | Azure, Vantage |
| Scope selector in header | Azure, Vantage |

### Our Platform's Optimal Position
- Information density: Between Vantage and Azure (power users but small team)
- Navigation: Left sidebar (already have) + scope selector in header (need to add)
- Color system: Follow our existing wm-* token system (already well-defined)
- Status colors: Follow Azure's severity model (Critical/High/Medium/Low)

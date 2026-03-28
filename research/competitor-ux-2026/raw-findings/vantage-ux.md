# Vantage.sh — Raw UX Findings (March 2026)

**Sources:** vantage.sh, vantage.sh/features, vantage.sh/features/cost-reports
**Date Accessed:** March 27, 2026
**Tier:** 2 (vendor product marketing with live UI screenshots)

---

## Homepage
- **Headline:** "Cloud Cost Management for Modern Engineering Teams"
- **New feature badge:** "New! Introducing Vantage in ChatGPT →" (AI/ChatGPT integration)
- **CTAs:** "Book a demo" (purple filled) + "Sign up for free" (white outlined)
- **Nav:** Features ▼, Solutions ▼, Integrations ▼, Docs, Pricing, Company ▼ | Sign In, Get started, Book a demo
- **Color:** Purple primary (#6C5CE7-ish)

## Cost Reports UI (Product Screenshot)

### Layout
- **Left sidebar:** Workspace selector ("Management" ▼) at top → Search → Overview, Cost Reports (active, highlighted), Issues
- **Main area header:** Breadcrumb "Cost Reports / All Resources" with ••• and Save (split button with ▼)
- **Tabs:** Overview | Anomalies
- **Filter bar:** 🔧 Filter | 📅 August 1 - August 31 | ⚙ Settings

### KPI Cards (2, side by side)
- **Accrued Costs:** $34,567,883.65 with green badge "+12.78%"
- **Forecasted Costs:** $25,324,463.12 with red badge "-15.89%"
- Badge colors: green = favorable for context, red = unfavorable

### Cost Breakdown Table
- **Columns:** Service (with provider icon) | Accrued Costs | Previous Period Costs | Change %
- **Sortable:** Sort icons visible on columns
- **Service icons:** AWS logo next to service names
- **Sample rows:**
  - Log Management: $4,516.86 | $2,573.97 | +75.48%
  - Amazon Redshift: $1,577.40 | $520.00 | +203.35%

## Features Page

### Feature Organization (Goal-Based IA)
**VISIBILITY:**
- Kubernetes — "Group By: Cluster" dropdown, stacked bar chart, rightsizing tooltip
- Virtual Tagging — 3-step rule builder wizard

**OPTIMIZATION:**
- Automated Waste Detection — Multi-cloud scan (AWS/Azure/GCP icons), progress bar, checklist findings

### Kubernetes Rightsizing Tooltip
```
Rightsizing Suggestion
Current vCPU:       16
Suggested vCPU:      2
Potential Savings: $143/mo
```

### Virtual Tagging Rule Builder (3-step wizard)
1. **Select Input Cost Filters**
   - Query builder: "All Costs ... from [GCP icon] GCP where [Category icon] Category is [GCP Support (Business) ×] [+] [🗑]"
   - "+ New Rule" button
2. **Select a Tag Key** (dropdown: "Sports Event")
3. **Select Output Cost Filters**

### Waste Detection Scanning UI
- Multi-cloud icons: AWS, Azure, GCP
- Progress bar: "Scanning Azure usage 76%" with spinner animation
- Checklist findings:
  - 🟡 No issues found in virtual machine usage
  - 🔵 Storage volumes optimized and healthy
  - 🟢 Network configuration within best practices

## Customer Logos
- CircleCI, Vercel, Boom, Rippling, HelloFresh, Joybird, Starburst, Metronome, Square, PBS

## Customer Quote
- PlanetScale CTO: "Doing all our cost reporting manually was taking too much time..."

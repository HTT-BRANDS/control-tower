# QA Audit Round 3: Visual Verification Checklist

**Instructions**: Log into the app at https://app-governance-prod.azurewebsites.net and check each item below.

---

## Global Checks

- [ ] Dark mode toggle works (top right moon icon)
- [ ] All nav links work: Dashboard, Sync, Costs, Compliance, Resources, Identity, Topology, Riverside
- [ ] No 500 errors or blank pages
- [ ] Footer shows "Last sync: Xm ago" (not "19 days ago")

## Compliance Page (/compliance)

- [ ] Overall Score card shows a real percentage (not "0.0%")
- [ ] Total Policies card shows a real number (not "0")
- [ ] Compliant card shows a real number
- [ ] Non-Compliant card shows a real number
- [ ] "Compliance Scores by Tenant" table shows all 5 brands with percentages
- [ ] "Non-Compliant Policies" table shows UNIQUE policies (not duplicated rows)
- [ ] Each row in non-compliant table shows: Policy name, Category, Affected Resources count, Severity

## Costs Page (/costs)

- [ ] Total Cost card shows real dollar amount (not "$0.00")
- [ ] Change indicator shows up/down arrow with percentage
- [ ] Top Services section shows bar charts with service names and costs
- [ ] "Cost by Tenant" table shows all 5 brands with costs
- [ ] "Anomalies" table shows any detected anomalies

## Resources Page (/resources)

- [ ] Total Resources card shows real count
- [ ] Idle Resources card shows real count
- [ ] Orphaned Resources card shows real count
- [ ] Tagging Compliance card shows real percentage (not "0%")
- [ ] Resource Inventory table shows resources with names
- [ ] Idle Resources table shows resource IDs and savings estimates
- [ ] Orphaned Resources table shows resource names and reasons

## Identity Page (/identity)

- [ ] Total Users card shows real count
- [ ] Guest Users card shows real count
- [ ] Stale Accounts card shows real count
- [ ] Privileged Users card shows real count
- [ ] "Privileged Users" table shows names, emails, and ROLE names (not "--")
- [ ] "Guest Users" table shows names and emails
- [ ] "Stale Accounts" table shows names and last sign-in dates

## Dashboard (/dashboard)

- [ ] KPI cards show real numbers (not all zeros)
- [ ] Cost trend chart shows data
- [ ] Compliance gauge shows real percentage
- [ ] No "stale sync" warning banner (or if present, it's accurate)

---

## If Data Shows Zeros or "--"

This means the sync hasn't run recently. Go to **Sync Dashboard** and:
1. Check sync status for each domain (Costs, Compliance, Resources, Identity)
2. Trigger a sync if needed
3. Wait 2-3 minutes for data to populate
4. Refresh the page

## Sign-Off

Once all checked boxes above are confirmed working, this round is complete.

Auditor: _________________ Date: _________________

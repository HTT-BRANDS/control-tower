# Riverside Compliance Platform - User Guide

A comprehensive guide for using the Riverside Compliance Platform to monitor and manage Azure governance across HTT Brands tenants.

---

## Table of Contents

1. [Executive Overview](#executive-overview)
2. [Dashboard Walkthrough](#dashboard-walkthrough)
3. [Interpreting Compliance Scores](#interpreting-compliance-scores)
4. [Using MFA Reports](#using-mfa-reports)
5. [Troubleshooting Guide](#troubleshooting-guide)
6. [FAQ Section](#faq-section)

---

## Executive Overview

### What is Riverside Compliance?

The Riverside Compliance Platform is a centralized governance solution that monitors security posture, compliance status, and operational metrics across all HTT Brands Azure tenants. It provides executive visibility into:

- **Security Posture**: MFA enrollment, device compliance, threat intelligence
- **Compliance Status**: Progress toward July 8, 2026 deadline
- **Operational Metrics**: Resource utilization, cost optimization, security scores

### Key Capabilities

| Capability | Description | Frequency |
|------------|-------------|-----------|
| **MFA Monitoring** | Track multi-factor authentication enrollment | Hourly |
| **Requirement Tracking** | Monitor compliance requirement completion | Real-time |
| **Maturity Scoring** | Assess tenant security maturity levels | Weekly |
| **Threat Intelligence** | Monitor security threats and vulnerabilities | Daily |
| **Device Compliance** | Track compliant vs non-compliant devices | Daily |
| **Alert Notifications** | Teams and email alerts for critical issues | Immediate |

### Supported Tenants

| Tenant | Environment | Priority |
|--------|-------------|----------|
| HTT | Production | P0 |
| BCC | Production | P0 |
| FN | Production | P0 |
| TLL | Production | P0 |
| DCE | Production | P0 |

---

## Dashboard Walkthrough

### Main Dashboard

The executive dashboard provides a single-pane view of compliance status across all tenants.

#### Key Metrics (Top Panel)

```
┌─────────────────────────────────────────────────────────────┐
│  Overall Maturity: 2.8/5.0    Target: 3.0    ⚠️ Below Target  │
│  Days Until Deadline: 120 days (July 8, 2026)               │
│  Total Requirements: 145    Completed: 87 (60%)             │
│  Critical Gaps: 12    Financial Risk: $20M                │
└─────────────────────────────────────────────────────────────┘
```

#### Tenant Summary Table

| Tenant | Maturity | MFA Users | MFA Admins | Req Complete | Critical Gaps |
|--------|----------|-----------|------------|--------------|---------------|
| HTT | 3.2 ✅ | 98% | 100% | 85% | 2 |
| BCC | 2.9 ⚠️ | 94% | 100% | 72% | 4 |
| FN | 2.7 ⚠️ | 96% | 100% | 68% | 3 |
| TLL | 2.8 ⚠️ | 91% | 100% | 55% | 2 |
| DCE | 2.5 ⚠️ | 89% | 97% | 45% | 1 |

#### Status Indicators

- **Green (✅)**: Meeting or exceeding targets
- **Yellow (⚠️)**: Below target but within acceptable range
- **Red (⛔)**: Critical issue requiring immediate attention

### Navigation

#### Header Menu

- **Dashboard**: Executive summary view
- **Requirements**: Detailed requirement tracking
- **MFA Report**: Multi-factor authentication status
- **Compliance**: Maturity score details
- **Device Status**: Device compliance overview
- **Threat Intel**: Security threat monitoring

#### Filters

Use the filter bar to narrow dashboard data:

- **Tenant**: Select specific tenant(s)
- **Status**: Filter by requirement status
- **Priority**: Filter by P0, P1, P2
- **Category**: Filter by compliance domain
- **Date Range**: Custom date filtering

### Detail Views

Click any row in the tenant summary table to view:

1. **Tenant Detail Page**
   - Breakdown by compliance category
   - Recent activity log
   - Alert history
   - Quick action buttons

2. **Requirement Detail**
   - Full requirement description
   - Evidence upload interface
   - Status history
   - Related requirements

---

## Interpreting Compliance Scores

### Maturity Score Calculation

The overall maturity score is a weighted average across five categories:

| Category | Weight | Description |
|----------|--------|-------------|
| **Identity** | 25% | MFA, conditional access, admin protection |
| **Devices** | 20% | Device compliance, Intune policies |
| **Data** | 20% | DLP, encryption, classification |
| **Apps** | 15% | App governance, permission reviews |
| **Infrastructure** | 20% | Network security, logging, monitoring |

### Score Ranges

```
Score    | Rating     | Action Required
---------|------------|------------------
4.0-5.0  | ✅ Leading | Maintain current practices
3.0-3.9  | ✅ Good    | Monitor and optimize
2.0-2.9  | ⚠️ Fair    | Address gaps identified
1.0-1.9  | ⛔ Poor    | Immediate remediation needed
0.0-0.9  | 🚨 Critical| Escalate to leadership
```

### Reading Your Score

**Example: HTT Tenant (Score: 3.2)**

```
Category        Score    Weight    Contribution
────────────────────────────────────────────────
Identity        4.1      × 0.25    = 1.025
Devices         3.5      × 0.20    = 0.700
Data            2.8      × 0.20    = 0.560
Apps            2.9      × 0.15    = 0.435
Infrastructure  2.5      × 0.20    = 0.500
────────────────────────────────────────────────
Total                      3.2      ✅ Good
```

**Recommendations for HTT:**
- **Strength**: Identity management (4.1) - Maintain MFA enforcement
- **Opportunity**: Data protection (2.8) - Implement additional DLP policies
- **Action**: Infrastructure security (2.5) - Enable advanced threat protection

### Trend Analysis

The platform tracks score changes over time:

- **↗️ Improving**: Score increased >0.1 from last assessment
- **➡️ Stable**: Score change within ±0.1
- **↘️ Declining**: Score decreased >0.1 (triggers alert)

---

## Using MFA Reports

### MFA Dashboard Overview

The MFA report provides comprehensive visibility into authentication security.

#### Key Metrics

```
┌────────────────────────────────────────────────────────────┐
│  Overall MFA Coverage: 93.6%    Target: 95%    ⚠️ Below    │
│  Admin MFA Coverage: 99.4%       Target: 100%   ⚠️ Below    │
│  Unprotected Admins: 3           Critical: Immediate        │
│  Total Users: 2,847    MFA Enrolled: 2,665                  │
└────────────────────────────────────────────────────────────┘
```

### MFA Report Sections

#### 1. Coverage Summary

Shows MFA enrollment by tenant:

| Tenant | User MFA | Admin MFA | Unprotected Admins | Status |
|--------|----------|-----------|-------------------|---------|
| HTT | 98% ✅ | 100% ✅ | 0 | Compliant |
| BCC | 94% ⚠️ | 100% ✅ | 0 | Monitor |
| FN | 96% ✅ | 100% ✅ | 0 | Compliant |
| TLL | 91% ⚠️ | 100% ✅ | 0 | Monitor |
| DCE | 89% ⛔ | 97% ⚠️ | 3 | Action Required |

#### 2. Admin MFA Details

Critical security view showing admin account protection:

```
⚠️ DCE Tenant: 3 Unprotected Admins Detected

Account          | Role           | Last Sign-in | Action
─────────────────────────────────────────────────────────────
admin1@dce.com   | Global Admin   | 2 days ago   | 🔴 Immediate
backup@dce.com   | Security Admin | 5 days ago   | 🔴 Immediate
svc@dce.com      | Service Admin  | 1 day ago    | 🔴 Immediate

Recommended Actions:
1. Enforce MFA via Conditional Access policy
2. Verify admin legitimacy
3. Review admin privileges
```

#### 3. User MFA Breakdown

Non-admin user MFA enrollment:

- **Total Users**: 2,847
- **MFA Enabled**: 2,665 (93.6%)
- **MFA Not Enabled**: 182 (6.4%)
- **Target**: 95% (2,705 users)
- **Gap**: 40 users need MFA

### Understanding MFA Alerts

#### Alert Triggers

| Alert Type | Threshold | Severity | Channel |
|------------|-----------|----------|---------|
| **Admin MFA Gap** | Any unprotected admin | 🔴 Critical | Teams + Email |
| **User MFA Gap** | Below 95% coverage | 🟡 Warning | Teams |
| **Enrollment Drop** | Decrease >5% | 🟡 Warning | Teams |
| **Compliance Achieved** | Target reached | 🟢 Info | Teams |

#### Sample Alert

```
🚨 MFA Compliance Alert: DCE

Severity: CRITICAL
Time: 2026-03-02 09:15 UTC

MFA enrollment gaps detected for tenant DCE:
  • Admin MFA: 97% (target: 100%) - 3 admins without MFA

Affected Accounts:
  • admin1@dce.com (Global Admin)
  • backup@dce.com (Security Admin)
  • svc@dce.com (Service Admin)

Required Actions:
1. Enforce MFA for all admin accounts
2. Review Conditional Access policies
3. Verify emergency access account MFA

[View Dashboard]  [Remediate Now]
```

### Best Practices

1. **Weekly Review**: Check MFA dashboard weekly for gaps
2. **Admin Priority**: Never allow unprotected admin accounts
3. **Onboarding**: Require MFA before account activation
4. **Monitoring**: Enable alerts for MFA coverage <95%
5. **Documentation**: Keep evidence of MFA enforcement

---

## Troubleshooting Guide

### Common Issues

#### Issue: Dashboard Not Loading

**Symptoms**: Blank page or loading spinner

**Resolution Steps**:

1. Check browser console (F12 → Console)
2. Verify network connectivity to API
3. Clear browser cache (Ctrl+Shift+R)
4. Try alternate browser

**Error Codes**:

| Code | Meaning | Action |
|------|---------|--------|
| 401 | Unauthorized | Re-authenticate |
| 403 | Forbidden | Check permissions |
| 500 | Server Error | Contact support |
| 503 | Maintenance | Check status page |

#### Issue: Data Not Syncing

**Symptoms**: Stale data, missing tenants

**Resolution Steps**:

1. Check sync status in footer
2. View last sync timestamp
3. Manual sync: Click "🔄 Refresh Data" button
4. Check sync logs: View → Logs → Sync

**Expected Sync Schedule**:

- **Hourly**: MFA data
- **Daily**: Device compliance, threat intelligence
- **Weekly**: Maturity assessments
- **On-demand**: Requirements updates

#### Issue: MFA Report Shows Old Data

**Symptoms**: Known MFA changes not reflected

**Resolution**:

```bash
# Trigger manual MFA sync
POST /api/sync/riverside-mfa

# Or via dashboard:
Settings → Sync → Run MFA Sync
```

**Data Freshness**:

| Data Type | Source | Update Frequency |
|-----------|--------|------------------|
| MFA Status | Microsoft Graph | ~1 hour delay |
| Device Compliance | Intune API | ~2 hour delay |
| Threat Intel | Defender API | ~4 hour delay |
| Requirements | Manual entry | Real-time |

#### Issue: Alert Notifications Not Received

**Symptoms**: Alerts in dashboard but no Teams/email

**Checklist**:

1. **Verify Configuration**
   ```
   Settings → Notifications → Webhook URL
   ```

2. **Test Webhook**
   ```
   Settings → Notifications → Send Test
   ```

3. **Check Teams Channel**
   - Verify webhook connector is active
   - Check channel permissions
   - Look in Teams connector history

4. **Email Settings**
   - Verify SMTP configuration
   - Check spam folders
   - Verify recipient list

**Notification Channels**:

| Severity | Teams | Email | Dashboard |
|----------|-------|-------|-----------|
| Critical | ✅ | ✅ | ✅ |
| Error | ✅ | ✅ | ✅ |
| Warning | ✅ | - | ✅ |
| Info | - | - | ✅ |

#### Issue: Cannot Update Requirement Status

**Symptoms**: Update fails or reverts

**Common Causes**:

1. **Permission Denied**
   - Verify user has "Requirement Manager" role
   - Check tenant-specific permissions

2. **Validation Error**
   - Ensure all required fields are filled
   - Check date format (YYYY-MM-DD)
   - Verify status transition is valid

3. **Concurrent Edit**
   - Another user edited the requirement
   - Refresh and retry

**Status Transitions**:

```
┌──────────┐    ┌──────────┐    ┌──────────┐
│  NOT     │───▶│   IN     │───▶│COMPLETED │
│ STARTED  │    │ PROGRESS │    │          │
└──────────┘    └──────────┘    └──────────┘
     │                               ▲
     │         ┌──────────┐          │
     └────────▶│ BLOCKED  │──────────┘
               └──────────┘
```

### Performance Issues

#### Slow Dashboard Loading

**Causes & Solutions**:

| Cause | Solution | Priority |
|-------|----------|----------|
| Large dataset | Enable pagination | Medium |
| Slow queries | Check database indexes | High |
| Network latency | Enable CDN | Low |
| Browser issues | Use latest Chrome/Edge | Medium |

**Optimization Tips**:

1. **Filter First**: Apply date/tenant filters before loading
2. **Pagination**: Use table pagination for large datasets
3. **Cache**: Dashboard caches for 5 minutes
4. **Export**: Use CSV export for offline analysis

### Getting Help

#### Support Channels

| Issue Type | Contact | Response |
|------------|---------|----------|
| Technical | support@httbrands.com | 4 hours |
| Security | security@httbrands.com | 1 hour |
| Feature Request | roadmap@httbrands.com | 24 hours |
| Emergency | +1-555-HTT-SUPPORT | Immediate |

#### Required Information

When reporting issues, include:

1. **Timestamp**: When did the issue occur?
2. **URL**: Which page/dashboard?
3. **User**: Who experienced the issue?
4. **Screenshot**: Visual evidence
5. **Steps**: How to reproduce
6. **Browser**: Version and OS

---

## FAQ Section

### General Questions

**Q: What is the Riverside Compliance deadline?**

A: The compliance deadline is **July 8, 2026**. This is when all P0 requirements must be completed.

**Q: Which tenants are included in Riverside compliance?**

A: All five HTT Brands tenants: HTT, BCC, FN, TLL, and DCE.

**Q: How often is data refreshed?**

A: See the [Data Freshness](#data-freshness) table in the troubleshooting guide.

### Dashboard Questions

**Q: Why does my maturity score show as "Below Target"?**

A: The target maturity score is 3.0/5.0. If your score is below this, you're not meeting the compliance target. Review the [Interpreting Compliance Scores](#interpreting-compliance-scores) section for improvement strategies.

**Q: What does "Financial Risk Exposure" mean?**

A: This is an estimated financial impact of non-compliance, calculated based on:
- Number of critical gaps
- Time until deadline
- Historical penalty data
- Industry benchmarks

**Q: Can I export dashboard data?**

A: Yes! Use the export button (📥) on any dashboard table to download CSV or Excel files.

### MFA Questions

**Q: Why is admin MFA at 100% but still showing warnings?**

A: Even one unprotected admin account triggers a critical alert. Check the [Admin MFA Details](#2-admin-mfa-details) section for the specific accounts.

**Q: How are service accounts handled in MFA reporting?**

A: Service accounts are excluded from user MFA calculations but included in admin MFA if they have admin privileges.

**Q: What if a user can't enroll in MFA?**

A: Contact IT Support for alternative authentication methods. Document any exceptions as requirement evidence.

### Requirements Questions

**Q: What do the priority levels (P0/P1/P2) mean?**

A:
- **P0**: Critical - Must be completed by deadline
- **P1**: Important - Should be completed by deadline
- **P2**: Nice-to-have - Best effort

**Q: Can I bulk update requirements?**

A: Yes! Use the bulk update feature:
1. Select multiple requirements (checkbox)
2. Click "Bulk Actions"
3. Choose action: Update Status, Assign Owner, Set Due Date
4. Confirm changes

**Q: Where do I upload evidence?**

A: Navigate to the requirement detail page and use the "📎 Upload Evidence" button. Supported formats: PDF, DOC, DOCX, PNG, JPG.

### Alert Questions

**Q: How do I configure alert notifications?**

A: Go to **Settings → Notifications** and configure:
1. Teams webhook URL
2. Email recipients
3. Severity thresholds
4. Cooldown periods

**Q: Why didn't I receive an alert?**

A: Check the [Alert Notifications](#issue-alert-notifications-not-received) troubleshooting section.

**Q: Can I customize alert messages?**

A: Alert templates are standardized for consistency. Contact support if you need custom alert formatting.

### Technical Questions

**Q: What browsers are supported?**

A: We recommend:
- Chrome 90+ ✅
- Edge 90+ ✅
- Firefox 90+ ✅
- Safari 14+ ⚠️ (limited testing)

**Q: Is there a mobile app?**

A: The dashboard is responsive and works on mobile browsers. No dedicated app is available yet.

**Q: How do I access the API?**

A: API documentation is available at `/docs` endpoint. Authentication requires a valid JWT token.

**Q: What are the system requirements?**

A: Minimum requirements:
- Modern web browser
- 1280x720 screen resolution
- Internet connection
- HTT Brands network access

### Security Questions

**Q: Who can see my tenant's data?**

A: Access is role-based:
- **Global Admin**: All tenants
- **Tenant Admin**: Assigned tenant only
- **Compliance Manager**: Read-only all tenants
- **Auditor**: Read-only, no sensitive data

**Q: Is data encrypted?**

A: Yes:
- Data in transit: TLS 1.3
- Data at rest: AES-256
- Database: Encrypted volumes
- Backups: Encrypted storage

**Q: How long is data retained?**

A:
- Compliance data: 7 years
- Audit logs: 3 years
- System logs: 90 days

### Getting Started

**Q: I'm new - where should I start?**

A: Recommended onboarding path:
1. Review this user guide
2. Watch the [Dashboard Tour](#dashboard-walkthrough) video
3. Explore the demo environment
4. Attend weekly office hours (Wednesdays 2pm)
5. Complete the compliance checklist

**Q: Is there training available?**

A: Yes! Available resources:
- Self-paced online course (1 hour)
- Monthly live training sessions
- Recorded demos on SharePoint
- Office hours: Wednesdays 2-3pm CT

---

## Quick Reference

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl + /` | Open search |
| `Ctrl + R` | Refresh data |
| `Esc` | Close modals |
| `?` | Show help |

### Emergency Contacts

| Situation | Contact | Phone |
|-----------|---------|-------|
| Security Incident | security@httbrands.com | +1-555-HTT-SEC |
| Platform Outage | oncall@httbrands.com | +1-555-HTT-OPS |
| Compliance Question | compliance@httbrands.com | +1-555-HTT-COMP |

### Links

- **Dashboard**: https://governance.httbrands.com/riverside
- **API Docs**: https://governance.httbrands.com/docs
- **Status Page**: https://status.httbrands.com
- **Support Portal**: https://support.httbrands.com

---

## Document Information

- **Version**: 1.0
- **Last Updated**: March 2, 2026
- **Author**: HTT Brands Compliance Team
- **Review Cycle**: Quarterly
- **Next Review**: June 2, 2026

For questions about this guide, contact: documentation@httbrands.com

# Azure Multi-Tenant Governance Platform - Requirements

## Executive Summary

A lightweight, cost-effective governance platform to manage 4 Azure/M365 tenants with centralized visibility into costs, compliance, resources, and identity governance.

---

## 1. Functional Requirements

### 1.1 Cost Optimization Module

| ID | Requirement | Priority |
|----|-------------|----------|
| CO-001 | Aggregate cost data across all 4 tenants | P0 |
| CO-002 | Daily/weekly/monthly cost trending | P0 |
| CO-003 | Cost anomaly detection & alerting | P0 |
| CO-004 | Resource cost attribution by tags | P1 |
| CO-005 | Idle resource identification | P0 |
| CO-006 | Right-sizing recommendations | P1 |
| CO-007 | Reserved instance utilization | P1 |
| CO-008 | Budget tracking per tenant/sub | P0 |
| CO-009 | Savings opportunities dashboard | P0 |
| CO-010 | Chargeback/showback reporting | P2 |

### 1.2 Compliance Monitoring Module

| ID | Requirement | Priority |
|----|-------------|----------|
| CM-001 | Azure Policy compliance across tenants | P0 |
| CM-002 | Custom compliance rule definitions | P1 |
| CM-003 | Regulatory framework mapping (SOC2, etc) | P2 |
| CM-004 | Compliance drift detection | P0 |
| CM-005 | Automated remediation suggestions | P1 |
| CM-006 | Secure Score aggregation | P0 |
| CM-007 | Non-compliant resource inventory | P0 |
| CM-008 | Compliance trend reporting | P1 |
| CM-009 | Policy exemption management | P2 |
| CM-010 | Audit log aggregation | P1 |

### 1.3 Resource Management Module

| ID | Requirement | Priority |
|----|-------------|----------|
| RM-001 | Cross-tenant resource inventory | P0 |
| RM-002 | Resource tagging compliance | P0 |
| RM-003 | Orphaned resource detection | P0 |
| RM-004 | Resource lifecycle tracking | P1 |
| RM-005 | Subscription/RG organization view | P0 |
| RM-006 | Resource health aggregation | P1 |
| RM-007 | Quota utilization monitoring | P1 |
| RM-008 | Resource provisioning standards | P2 |
| RM-009 | Tag enforcement reporting | P0 |
| RM-010 | Resource change history | P2 |

### 1.4 Identity Governance Module

| ID | Requirement | Priority |
|----|-------------|----------|
| IG-001 | Cross-tenant user inventory | P0 |
| IG-002 | Privileged access reporting | P0 |
| IG-003 | Guest user management | P0 |
| IG-004 | Stale account detection | P0 |
| IG-005 | MFA compliance reporting | P0 |
| IG-006 | Conditional Access policy audit | P1 |
| IG-007 | Role assignment analysis | P0 |
| IG-008 | Service principal inventory | P1 |
| IG-009 | License utilization tracking | P1 |
| IG-010 | Access review facilitation | P2 |

---

## 2. Non-Functional Requirements

### 2.1 Performance

| ID | Requirement |
|----|-------------|
| NF-P01 | Dashboard load time < 3 seconds |
| NF-P02 | API response time < 500ms (cached) |
| NF-P03 | Support 50+ concurrent users |
| NF-P04 | Data refresh intervals: 15min-24hr |

### 2.2 Security

| ID | Requirement |
|----|-------------|
| NF-S01 | SSO via Azure AD / Entra ID |
| NF-S02 | Role-based access control (RBAC) |
| NF-S03 | Audit logging of all actions |
| NF-S04 | Secrets in Azure Key Vault |
| NF-S05 | Encrypted data at rest |
| NF-S06 | HTTPS/TLS 1.2+ only |

### 2.3 Scalability & Availability

| ID | Requirement |
|----|-------------|
| NF-A01 | 99.5% uptime target |
| NF-A02 | Graceful degradation on API limits |
| NF-A03 | Support expansion to 10+ tenants |

### 2.4 Cost Constraints

| ID | Requirement |
|----|-------------|
| NF-C01 | Monthly infra cost < $200/month |
| NF-C02 | Leverage free-tier services |
| NF-C03 | Minimize premium API calls |
| NF-C04 | SQLite for MVP, migrate later |

---

## 3. Technical Requirements

### 3.1 Azure API Access

```
Required APIs per Tenant:
├── Azure Resource Manager API
├── Azure Cost Management API
├── Azure Policy API
├── Microsoft Graph API
├── Azure Advisor API
├── Azure Security Center API
└── Azure Monitor API
```

### 3.2 Authentication Setup (Per Tenant)

| Component | Details |
|-----------|----------|
| App Registration | 1 per tenant |
| Service Principal | Reader + specific roles |
| API Permissions | See Section 5 |
| Cross-tenant | Azure Lighthouse preferred |

### 3.3 Minimum Role Assignments

```
Per Tenant Service Principal:
├── Reader (subscription scope)
├── Cost Management Reader
├── Security Reader
├── Directory.Read.All (Graph)
├── Policy.Read.All (Graph)
└── Reports.Read.All (Graph)
```

---

## 4. Data Requirements

### 4.1 Data Retention

| Data Type | Retention |
|-----------|----------|
| Cost data | 24 months |
| Compliance snapshots | 12 months |
| Resource inventory | 6 months |
| Identity snapshots | 6 months |
| Audit logs | 12 months |
| Riverside compliance | 5 years |

### 4.2 Data Refresh Frequencies

| Data Type | Frequency |
|-----------|----------|
| Cost actuals | Daily |
| Cost forecasts | Weekly |
| Compliance state | 4 hours |
| Resource inventory | 1 hour |
| Identity data | Daily |
| Recommendations | Daily |
| Riverside MFA status | 4 hours |
| Riverside device compliance | 4 hours |

---

## 5. API Permissions Matrix

### Azure Resource Manager (ARM)

```
Microsoft.Resources/subscriptions/read
Microsoft.Resources/subscriptions/resourceGroups/read
Microsoft.Resources/resources/read
Microsoft.CostManagement/query/read
Microsoft.Advisor/recommendations/read
Microsoft.PolicyInsights/policyStates/read
Microsoft.Security/secureScores/read
```

### Microsoft Graph

```
User.Read.All
Group.Read.All
Directory.Read.All
RoleManagement.Read.All
Policy.Read.All
AuditLog.Read.All
Reports.Read.All
```

---

## 6. Integration Requirements

| Integration | Purpose | Priority |
|-------------|---------|----------|
| Azure Lighthouse | Multi-tenant access | P0 |
| Azure Cost Mgmt API | Cost data | P0 |
| Microsoft Graph | Identity data | P0 |
| Azure Policy | Compliance | P0 |
| Azure Advisor | Recommendations | P1 |
| Teams Webhook | Alerting | P1 |
| Power BI (optional) | Advanced viz | P2 |

---

## 7. User Stories

### Cost Optimization

- As a **Cloud Admin**, I want to see total spend across all tenants
- As a **FinOps Lead**, I want to identify cost anomalies quickly
- As a **Manager**, I want monthly cost reports by department

### Compliance

- As a **Security Admin**, I want compliance scores per tenant
- As an **Auditor**, I want historical compliance trending
- As a **DevOps Lead**, I want to see non-compliant resources

### Resource Management

- As a **Cloud Admin**, I want to find orphaned resources
- As a **Platform Engineer**, I want tagging compliance reports
- As a **Manager**, I want resource counts by tenant/subscription

### Identity Governance

- As a **Security Admin**, I want to audit privileged access
- As an **IT Admin**, I want to find stale guest accounts
- As a **Compliance Officer**, I want MFA coverage reports

---

## 8. Riverside Compliance Requirements

This section defines requirements specific to Riverside Company compliance tracking. These requirements support the July 8, 2026 compliance deadline with target maturity score of 3.0/5.0.

### 8.1 Executive Tracking Requirements

| ID | Requirement | Priority | Purpose |
|----|-------------|----------|--------|
| RC-001 | Executive compliance dashboard | P0 | Stakeholder visibility |
| RC-002 | Days to deadline countdown | P0 | Timeline awareness |
| RC-003 | Maturity score tracking | P0 | Progress measurement |
| RC-004 | Financial risk quantification | P0 | Business justification |
| RC-005 | Requirement completion percentage | P0 | Overall progress |
| RC-006 | Trend analysis and forecasting | P1 | Predict completion |

### 8.2 MFA Monitoring Requirements

| ID | Requirement | Priority | Current Status |
|----|-------------|----------|----------------|
| RC-010 | Real-time MFA enrollment tracking | P0 | 30% (current) |
| RC-011 | Per-tenant MFA breakdown | P0 | 4 tenants tracked |
| RC-012 | Admin account MFA tracking | P0 | 39 admin accounts |
| RC-013 | MFA trend reporting | P1 | Historical trending |
| RC-014 | Non-MFA user alerting | P0 | Manual process |
| RC-015 | MFA gap identification | P0 | 1,358 unprotected |

### 8.3 Requirement Tracking Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| RC-020 | Requirement status tracking | P0 |
| RC-021 | Evidence upload/link storage | P0 |
| RC-022 | Requirement categorization | P0 |
| RC-023 | Owner assignment | P0 |
| RC-024 | Due date tracking | P0 |
| RC-025 | Priority classification (P0/P1/P2) | P0 |
| RC-026 | Completion date recording | P0 |
| RC-027 | Notes and comments | P1 |

### 8.4 Device Compliance Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| RC-030 | MDM enrollment tracking | P0 |
| RC-031 | EDR coverage monitoring | P0 |
| RC-032 | Device encryption status | P1 |
| RC-033 | Asset inventory | P1 |
| RC-034 | Device compliance scoring | P0 |
| RC-035 | Non-compliant device alerting | P1 |

### 8.5 Maturity Scoring Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| RC-040 | Domain maturity tracking | P0 |
| RC-041 | Historical trending | P1 |
| RC-042 | Score calculation | P0 |
| RC-043 | Domain breakdown (IAM, GS, DS) | P0 |
| RC-044 | Target gap analysis | P0 |
| RC-045 | Improvement recommendations | P1 |

### 8.6 External Threat Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| RC-050 | Threat Beta score display | P1 |
| RC-051 | Vulnerability count | P1 |
| RC-052 | Malicious domain alerts | P1 |
| RC-053 | Peer comparison | P2 |
| RC-054 | Threat trend reporting | P2 |

### 8.7 Riverside Data Sources

| Source | Integration | Frequency |
|--------|-------------|-----------|
| Microsoft Graph | MFA, user data | Daily |
| Intune | MDM status | Daily |
| Azure AD | Admin roles | Daily |
| Azure Policy | Compliance state | 4 hours |
| Azure Security Center | Secure score | Daily |
| Cybeta API | Threat data | Weekly (if available) |
| Manual entry | Evidence, requirements | On-demand |

### 8.8 Success Metrics

| Metric | Current | Target | Deadline | Financial Impact |
|--------|---------|--------|----------|------------------|
| Overall Maturity | 2.4 | 3.0+ | July 8, 2026 | $4M risk |
| MFA Coverage | 30% (634/1992) | 100% | 30 days | $4M risk |
| Critical Gaps | 8 | 0 | July 8, 2026 | Compliance failure |
| Admin MFA | 39 accounts tracked | 100% | 30 days | $4M risk |
| Device Compliance | Phase 2 (Sui Generis) | 90%+ | 60 days | Audit failure |
| Domain Maturity (IAM) | 2.2 | 3.0 | July 8, 2026 | - |
| Domain Maturity (GS) | 2.5 | 3.0 | July 8, 2026 | - |
| Domain Maturity (DS) | 2.6 | 3.0 | July 8, 2026 | - |

### 8.9 Critical Gap Priorities

The following gaps require immediate attention to meet the July 8, 2026 deadline:

| Rank | Gap | Current | Target | Deadline | Risk |
|------|-----|---------|--------|----------|------|
| 1 | MFA Universal Enforcement | 30% | 100% | Immediate | $4M |
| 2 | Dedicated Security Team | None | 1+ FTE | 30 days | Audit |
| 3 | Privileged Access Management | 0% | 100% | 60 days | $4M |
| 4 | Conditional Access Policies | 40% | 100% | 60 days | $2M |
| 5 | Data Classification | 0% | Complete | 90 days | Compliance |
| 6 | Security Awareness Training | 25% | 100% | 90 days | Human error |
| 7 | Service Account Management | 0% | 100% | 120 days | Credential theft |
| 8 | Encryption at Rest | 0% | 100% | 120 days | Data breach |

---

## 9. MVP Scope (Phase 1)

### In Scope

- [x] Cross-tenant cost aggregation dashboard
- [x] Basic compliance score visualization
- [x] Resource inventory with tagging status
- [x] Identity overview (users, guests, admins)
- [x] Single lightweight deployment
- [x] Manual data refresh triggers
- [x] Riverside compliance dashboard (MVP)

### Out of Scope (Phase 2+)

- [ ] Automated remediation
- [ ] Custom compliance frameworks
- [ ] Advanced anomaly ML
- [ ] Chargeback workflows
- [ ] Access review automation
- [ ] Power BI embedding
- [ ] Riverside automated Azure sync
- [ ] Riverside external threat integration

---

## 10. Success Metrics

| Metric | Target |
|--------|--------|
| Cost visibility | 100% of resources |
| Idle resource savings | 10-15% reduction |
| Compliance visibility | All 4 tenants |
| Stale account cleanup | < 50 accounts |
| Admin time saved | 5+ hrs/week |
| Riverside compliance | 3.0+ maturity by July 8, 2026 |

---

## 11. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| API rate limits | Data gaps | Caching, staggered refresh |
| Cross-tenant auth | Access denied | Azure Lighthouse setup |
| Data staleness | Bad decisions | Clear refresh timestamps |
| Scope creep | Delays | Strict MVP boundaries |
| Cost overrun | Budget breach | SQLite, minimal infra |
| Riverside deadline miss | $4M loss | Priority tracking, early start |
| MFA adoption resistance | Compliance failure | Executive sponsorship, incentives |

---

## 12. Acceptance Criteria

### MVP Release Criteria

| # | Acceptance Criterion | Code Complete | Staging Verified | Notes |
|---|---------------------|:------------:|:----------------:|-------|
| 1 | All 4 tenants connected and data flowing | ✅ | ⏳ Pending | Requires ACR image rebuild + container startup |
| 2 | Cost dashboard shows aggregated spend | ✅ | ⏳ Pending | Needs live tenant data sync |
| 3 | Compliance scores visible per tenant | ✅ | ⏳ Pending | Needs live tenant data sync |
| 4 | Resource inventory complete | ✅ | ⏳ Pending | Needs live tenant data sync |
| 5 | Identity overview functional | ✅ | ⏳ Pending | Needs live tenant data sync |
| 6 | < $200/month infrastructure cost | ✅ | ⚠️ To Verify | B1 tier deployed, need Azure Cost Mgmt check |
| 7 | Documentation complete | ✅ | ✅ | All docs updated and current |
| 8 | Basic alerting operational | ✅ | ⏳ Pending | Requires running scheduler |
| 9 | Riverside dashboard operational | ✅ | ⏳ Pending | Requires data sync post-startup |

### Riverside Compliance Criteria

1. ✅ Executive summary visible at /riverside
2. ✅ MFA tracking shows 30% coverage
3. ✅ Requirement tracking shows 72+ requirements
4. ✅ Maturity scores display 2.4/5.0 overall
5. ✅ Days to deadline countdown visible
6. ✅ Financial risk ($4M) displayed
7. ✅ Critical gaps identified
8. ✅ Evidence upload capability

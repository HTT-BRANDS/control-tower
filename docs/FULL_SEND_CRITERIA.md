# Full Send Criteria - Go/No-Go Decision Matrix

**Purpose:** Define the exact criteria for approving production operations  
**Status:** Operational/Team readiness criteria are now traceable to staged artifacts + bd issues (see checklists below); awaiting Tyler's execution + sign-off (`ct-71r`)  
**Date:** March 31, 2026

---

## The "Full Send" Philosophy

> "Test, analyze, validate, then full send. No shortcuts. No surprises."

**Definition:** Full Send = Confident, sustainable production operations with monitoring, documentation, and team readiness.

---

## Go/No-Go Decision Matrix

### Test Results Weighting

| Category | Weight | Minimum | Target | Excellent |
|----------|--------|---------|--------|-----------|
| **Smoke Tests** | 20% | 100% | 100% | 100% |
| **Unit Tests** | 25% | 85% | 90% | 95% |
| **Integration Tests** | 15% | 75% | 80% | 90% |
| **Architecture Tests** | 15% | 100% | 100% | 100% |
| **Code Coverage** | 15% | 75% | 80% | 85% |
| **Mutation Score** | 10% | 85% | 90% | 95% |

### Scoring Calculation

```
Total Score = (Smoke × 0.20) + 
              (Unit × 0.25) + 
              (Integration × 0.15) + 
              (Architecture × 0.15) + 
              (Coverage × 0.15) + 
              (Mutation × 0.10)
```

---

## Decision Thresholds

### 🟢 FULL SEND APPROVED (Score >= 85%)

**Criteria:**
- All smoke tests pass (100%)
- Unit tests >= 90%
- Overall weighted score >= 85%

**Actions:**
- ✅ Enter operations mode
- ✅ Begin daily monitoring
- ✅ Schedule quarterly reviews
- ✅ Archive as "certified release"

**Rationale:** System is solid, documented, and ready for sustained operations.

---

### 🟡 CONDITIONAL FULL SEND (Score 70-85%)

**Criteria:**
- Smoke tests pass (100%)
- Unit tests >= 85%
- Overall weighted score 70-85%

**Actions:**
- ⚠️ Document known issues
- ⚠️ Create mitigation plan
- ⚠️ Set enhanced monitoring
- ⚠️ Schedule 30-day review
- ⚠️ Fix critical issues in next sprint

**Rationale:** System is functional but has gaps. Can proceed with guardrails.

---

### 🔴 NO-GO (Score < 70%)

**Criteria:**
- Smoke tests fail, OR
- Unit tests < 85%, OR
- Overall weighted score < 70%

**Actions:**
- ❌ Do not enter full operations
- ❌ Fix critical failures first
- ❌ Add missing test coverage
- ❌ Re-test after fixes
- ❌ Re-evaluate architecture

**Rationale:** System has significant gaps. Full send would be risky.

---

## Risk Assessment Matrix

### Low Risk (Proceed with Confidence)

| Indicator | Status |
|-----------|--------|
| Test score >= 85% | ✅ |
| All smoke tests pass | ✅ |
| No critical security issues | ✅ |
| Documentation complete | ✅ |
| Team trained on runbook | ✅ |

**Decision:** 🟢 FULL SEND

---

### Medium Risk (Proceed with Caution)

| Indicator | Status |
|-----------|--------|
| Test score 70-85% | ⚠️ |
| Minor test failures | ⚠️ |
| Known workarounds documented | ⚠️ |
| Enhanced monitoring required | ⚠️ |

**Decision:** 🟡 CONDITIONAL FULL SEND

---

### High Risk (Do Not Proceed)

| Indicator | Status |
|-----------|--------|
| Test score < 70% | ❌ |
| Critical smoke test failures | ❌ |
| Security vulnerabilities | ❌ |
| Incomplete documentation | ❌ |

**Decision:** 🔴 NO-GO

---

## Pre-Full Send Checklist

### Technical Validation

- [ ] All smoke tests pass
- [ ] Unit test coverage >= 90%
- [ ] Integration tests pass
- [ ] Architecture constraints met
- [ ] Code coverage >= 80%
- [ ] Mutation score >= 90% (optional but recommended)
- [ ] Security scan clean
- [ ] Performance baseline established

### Operational Readiness

_Each item is wired to the artifact that satisfies it + the bd issue + who executes. "Staged" = artifact merged to main; the checkbox is Tyler's to tick once executed._

- [ ] **Data freshness fixed + monitored** — `--always-on true` on prod+staging + restart, then `/healthz/data` `any_stale:false` (`ct-cne`/`ct-ar3`; observability staged: `/healthz/scheduler`). _Tyler (Azure)._
- [ ] **Operational runbook reviewed by team** — `OPERATIONAL_RUNBOOK.md` incl. sync-recovery (`ct-6su`, staged). _Tyler review._
- [ ] **Monitoring dashboards accessible** — App Insights/Log Analytics access grant (`ct-8by`). _Tyler (RBAC)._
- [ ] **Alert thresholds configured** — `scripts/setup-freshness-alert.sh` (`ct-vuv`) + `scripts/setup-ops-alerts.sh` (`ct-8jt`); both staged. _Tyler runs + test-fires._
- [ ] **Escalation contacts confirmed** — fill `_TODO_` slots in `INCIDENT_RESPONSE.md` (`ct-o1w`, staged). _Tyler._
- [ ] **Incident response plan documented** — `docs/INCIDENT_RESPONSE.md` (`ct-o1w`, staged). ✅ drafted.
- [ ] **Rollback procedure tested** — run `docs/runbooks/staging-rollback-drill.md` (`ct-c60`, staged). _Tyler (staging)._

### Documentation Completeness

- [ ] PROJECT_COMPLETION_CERTIFICATE.md signed
- [ ] FINAL_SYSTEM_VALIDATION.md current
- [ ] OPERATIONAL_RUNBOOK.md reviewed
- [ ] All 16 documents accessible
- [ ] Architecture Decision Records current

### Team Readiness

- [ ] **Ops users provisioned** at correct tiers — `scripts/setup_admin.py` per `docs/runbooks/provision-ops-users.md` (`ct-hvv`, staged; Manager now provisionable). _Tyler (DB/identity)._
- [ ] **DevOps team trained** — onboarding guide `OPS_ONBOARDING.md` (`ct-bmq`, staged) + session (`ct-dxb`). _Tyler delivers._
- [ ] **On-call rotation defined** — fill rotation in `INCIDENT_RESPONSE.md` (`ct-o1w`). _Tyler._
- [ ] **Monitoring tools access granted** — `ct-8by`. _Tyler (RBAC)._
- [ ] **Emergency contacts confirmed** — `INCIDENT_RESPONSE.md` contacts table. _Tyler._

---

## Full Send Declaration Template

```markdown
# FULL SEND DECLARATION

**Project:** Azure Governance Platform  
**Version:** 1.8.1  
**Date:** [DATE]  
**Decision:** [🟢 APPROVED / 🟡 CONDITIONAL / 🔴 NO-GO]

## Test Results Summary

| Test Category | Score | Weight | Weighted |
|---------------|-------|--------|----------|
| Smoke Tests | [X%] | 20% | [Y%] |
| Unit Tests | [X%] | 25% | [Y%] |
| Integration | [X%] | 15% | [Y%] |
| Architecture | [X%] | 15% | [Y%] |
| Coverage | [X%] | 15% | [Y%] |
| Mutation | [X%] | 10% | [Y%] |
| **TOTAL** | - | 100% | **[Z%]** |

## Risk Assessment

- Technical Risk: [Low/Medium/High]
- Operational Risk: [Low/Medium/High]
- Security Risk: [Low/Medium/High]

## Mitigations (if applicable)

- [List any conditions or workarounds]

## Approved By

- 🐺 Husky (Infrastructure): ___________
- 🐶 Code-puppy (Code Quality): ___________
- 🐱 QA-kitten (Testing): ___________
- 🐕‍🦺 Bloodhound (Security): ___________
- Stakeholder: ___________

## Next Actions

- [ ] Begin operations mode
- [ ] Set up monitoring cadence
- [ ] Schedule first quarterly review
- [ ] [Any other actions]

**DECLARED FULL SEND ON:** [DATE]
```

---

## Post-Full Send Monitoring

### First 30 Days (Intensive)

| Activity | Frequency | Responsible |
|----------|-----------|-------------|
| Health checks | Daily | Automated |
| Alert review | Daily | DevOps |
| Metrics review | Weekly | Team |
| Issue triage | As needed | On-call |

### Ongoing (Sustained)

| Activity | Frequency | Responsible |
|----------|-----------|-------------|
| Health checks | Daily | Automated |
| Alert review | Weekly | DevOps |
| Metrics review | Monthly | Team |
| Full review | Quarterly | All |

---

## Emergency Stop Criteria

**Immediately halt operations if:**

1. 🔴 Production downtime > 15 minutes
2. 🔴 Data loss or corruption detected
3. 🔴 Security breach confirmed
4. 🔴 Error rate > 10% for > 10 minutes
5. 🔴 Critical business function unavailable

**Emergency Response:**
1. Page on-call engineer immediately
2. Execute rollback procedure
3. Communicate to stakeholders
4. Post-mortem within 24 hours

---

## Summary

**The Rule:** Test → Analyze → Validate → Full Send

**The Standard:** 85% or higher for full approval

**The Philosophy:** Better to catch issues in testing than in production

**The Goal:** Confident, sustainable, monitored operations

---

**Ready to execute tests and apply these criteria?** Run the test execution plan and use this matrix for your go/no-go decision.

🐕‍🦺 Bloodhound has sniffed the criteria. The trail is clear. Execute tests and decide. 🎯

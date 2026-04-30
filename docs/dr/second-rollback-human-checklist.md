# Second Rollback Human Checklist

> **Status:** Ready for Tyler to assign a human
> **Owner:** Tyler Granlund
> **Tracked by:** bd `azure-governance-platform-213e`
> **Waiver expires:** 2026-06-22

This checklist defines what “second rollback human” means. Naming someone in
chat is not enough; they must be able to execute a rollback without Tyler typing
the commands for them.

---

## 1. Candidate

| Field | Value |
|---|---|
| Name | **Dustin Boyd** |
| Role / org | 🔴 TODO Tyler (HTT IT / role title) |
| Backup contact method | 🔴 TODO Tyler (Teams handle + cell + email) |
| Date nominated | 2026-04-30 |
| Date accepted | 🔴 TODO Tyler (after Dustin confirms) |

---

## 2. Required access

The candidate is not operationally ready until each row is checked.

| Access | Required capability | Status | Evidence pointer |
|---|---|---|---|
| GitHub repo | Read repo, inspect Actions, dispatch `deploy-production.yml` | 🔴 TODO | 🔴 TODO |
| GitHub environments | See/run production deployment workflow as allowed by policy | 🔴 TODO | 🔴 TODO |
| Azure HTT-CORE | Run `az` against prod resource group for rollback/DR | 🔴 TODO | 🔴 TODO |
| Azure Key Vault | Read/recover relevant operational secrets, if policy permits | 🔴 TODO | 🔴 TODO |
| Azure SQL | Execute PITR restore drill to a non-prod target | 🔴 TODO | 🔴 TODO |
| GHCR | Validate/pull previous-good container digest or use deploy workflow | 🔴 TODO | 🔴 TODO |
| Teams ops channel | Receive and post incident updates | 🔴 TODO | 🔴 TODO |
| `SECRETS_OF_RECORD.md` | Read secret pointers / recovery map | 🔴 TODO | 🔴 TODO |

---

## 3. Required reading

| Document | Why | Status |
|---|---|---|
| `RUNBOOK.md` | Emergency operating entry point | 🔴 TODO |
| `docs/runbooks/disaster-recovery.md` | Scenario procedures | 🔴 TODO |
| `docs/dr/rto-rpo.md` | Targets and test cadence | 🔴 TODO |
| `docs/release-gate/rollback-current-state.yaml` | Current rollback digest/source of truth | 🔴 TODO |
| `INFRASTRUCTURE_END_TO_END.md` | Current topology | 🔴 TODO |
| `SECRETS_OF_RECORD.md` | Secret pointer inventory | 🔴 TODO |

---

## 4. Tabletop exercise

Acceptance for bd `213e` requires a tabletop exercise on one DR scenario.
Recommended first scenario: **Scenario A.3 — rollback to previous known-good
container digest** from `docs/runbooks/disaster-recovery.md`.

### Exercise script

1. Candidate explains the severity classification for a broken production deploy.
2. Candidate locates the current production workflow history:
   ```bash
   gh run list --workflow=deploy-production.yml --status=success --limit 5
   ```
3. Candidate identifies where previous known-good image digest evidence lives.
4. Candidate walks through the rollback command sequence without executing it.
5. Candidate identifies validation commands:
   ```bash
   curl -sS https://app-governance-prod.azurewebsites.net/health | jq .
   curl -sS https://app-governance-prod.azurewebsites.net/api/v1/health/data | jq .
   ```
6. Candidate states when to stop and escalate.
7. Tyler records actual gaps and follow-up actions below.

### Tabletop record

| Field | Value |
|---|---|
| Date | 🔴 TODO Tyler |
| Scenario | Scenario A.3 rollback to previous known-good digest |
| Candidate | 🔴 TODO Tyler |
| Facilitator | Tyler Granlund |
| Result | 🔴 TODO pass/fail |
| Gaps found | 🔴 TODO |
| Follow-up issues filed | 🔴 TODO |

---

## 5. Closure criteria for bd `213e`

Do not close `213e` until all are true:

- [ ] Candidate is named in §1.
- [ ] Candidate has required access or documented break-glass substitute.
- [ ] Candidate completed required reading.
- [ ] Candidate completed at least one tabletop exercise.
- [ ] `RUNBOOK.md` points to this checklist.
- [ ] Any gaps discovered during tabletop have bd follow-up issues.

---

*Authored by Richard (code-puppy-661ed0), 2026-04-30. No human was named on
Tyler's behalf.*

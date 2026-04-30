# Second Rollback Human Checklist

> **Status:** Ready for Tyler to provision Dustin Boyd's access + schedule tabletop
> **Owner:** Tyler Granlund
> **Tracked by:** bd `azure-governance-platform-213e`
> **Waiver expires:** 2026-06-22

This checklist defines what "second rollback human" means at HTT-Brands today.

---

## 0. Why this role exists (post-auto-rollback)

As of commit `d9d9d88`, `deploy-production.yml` automatically rolls back to the
previous-good container digest when post-deploy health checks fail. The
**predictable** failure modes — bad image, bad migration, TLS misconfig,
unreachable dependency, OOM at startup — are now handled without any human
involvement. Workflow run summaries record every rollback decision.

The second human is **not** there to type rollback CLI commands at 3 AM. They
are there for the failure classes auto-rollback **cannot** detect or recover:

| Auto-rollback handles | Second human handles |
|---|---|
| `/health` returning non-200 | App is "healthy" but doing the wrong thing (silent corruption, unintended data exfil, runaway cost) |
| Image pull failures, container crashes, startup loops | Database outage, Key Vault outage, managed identity broken, regional Azure outage |
| Bad migration that crashes the app | Bad migration that *succeeds* but corrupts data |
| TLS / cert misconfig | GitHub / GHCR outage blocking the deploy workflow itself |
| Single-deploy regressions | "The auto-rollback itself failed" — both digests bad, Azure CLI errored, etc. |

In disaster-recovery.md terms: auto-rollback covers **§A.3**. The second human
covers **§A.4** (runtime failure not caught by health), **§B** (database),
**§C** (Key Vault / identity), **§D** (region), **§E** (GitHub/GHCR),
**§F** (smoking crater), and any novel SEV1 not yet codified.

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

The candidate is not operationally ready until each row is checked. Auto-rollback
shrinks this list slightly — direct GHCR digest manipulation is no longer required —
but the rest still applies because non-deploy SEV1s (DB / KV / identity / region)
need the same access.

| Access | Why it's still needed | Status | Evidence pointer |
|---|---|---|---|
| GitHub repo | Read repo, inspect Actions runs (incl. auto-rollback decision summaries), dispatch `deploy-production.yml` | 🔴 TODO | 🔴 TODO |
| GitHub `production` environment | Approve / re-run prod deploys, including emergency forward-fixes | 🔴 TODO | 🔴 TODO |
| Azure HTT-CORE subscription | Run `az` against `rg-governance-production` for §A.4, §B, §C, §F | 🔴 TODO | 🔴 TODO |
| Azure Key Vault `kv-governance-prod-*` | Recover soft-deleted secrets per §C.3 | 🔴 TODO | 🔴 TODO |
| Azure SQL `sqldb-governance-prod` | Trigger PITR restore per §B.3 | 🔴 TODO | 🔴 TODO |
| GHCR (`ghcr.io/htt-brands/control-tower`) | List/inspect digests; **only needed for §A.4 manual rollback when auto-rollback failed** | 🔴 TODO | 🔴 TODO |
| Teams ops channel | Receive incident notifications (auto-rollback posts here too); coordinate with Tyler | 🔴 TODO | 🔴 TODO |
| `SECRETS_OF_RECORD.md` | Pointer inventory for KV/storage account secrets — required for §B/§C/§F (blocked on bd `9lfn`) | 🔴 TODO | 🔴 TODO |

---

## 3. Required reading

Narrower than pre-auto-rollback. Drop deep CLI procedures for routine rollback
(automation handles §A.3); keep judgment + escalation + non-deploy scenarios.

| Document | Why | Status |
|---|---|---|
| `RUNBOOK.md` | Emergency operating entry point — start here for any page | 🔴 TODO |
| `docs/runbooks/disaster-recovery.md` | **Read §1 (golden rules), §2 (severity), §A.4, §B, §C in full.** §A.3 can be skimmed — automation handles it. §D/§E/§F only when you are paged for one. | 🔴 TODO |
| `docs/dr/rto-rpo.md` | Targets and test cadence — what "good" looks like | 🔴 TODO |
| `docs/release-gate/rollback-current-state.yaml` | Source of truth for current waiver state + authorized humans | 🔴 TODO |
| `INFRASTRUCTURE_END_TO_END.md` | Current topology — needed to make sense of "what failed where" | 🔴 TODO |
| `SECRETS_OF_RECORD.md` | Secret recovery map (blocked on bd `9lfn`) | 🔴 TODO when 9lfn lands |
| `.github/workflows/deploy-production.yml` (skim) | Understand what auto-rollback does and what its run summary looks like | 🔴 TODO |

Total reading time estimate: **~75 min** (was ~3 hr pre-auto-rollback).

---

## 4. Tabletop exercise

Acceptance for bd `213e` requires a tabletop on one DR scenario. The recommended
scenario is **no longer §A.3** — that's automated. Walk through **Scenario A.4
"auto-rollback failed, what now?"** instead, since that's the actual gap auto-rollback
leaves.

### 4.1 Recommended scenario: A.4 — auto-rollback failed

Setup: a deploy ran, health checks failed, auto-rollback fired, but rollback
*also* failed. Workflow summary shows the 🔴🔴 CRITICAL block. Production is on
an unknown digest in a degraded state.

### 4.2 Exercise script

1. Candidate explains the severity classification (§2 in disaster-recovery.md)
   given the workflow summary they would see.
2. Candidate locates the failed workflow run and explains how to read the run
   summary block:
   ```bash
   gh run list --workflow=deploy-production.yml --limit 3
   gh run view <run-id> --log
   ```
3. Candidate identifies the *current* container image actually deployed
   (independent of what the workflow attempted):
   ```bash
   az webapp config container show \
     -g rg-governance-production -n app-governance-prod \
     --query linuxFxVersion -o tsv
   ```
4. Candidate identifies the **previous known-good digest** from release evidence
   in this order:
   a. last successful `deploy-production` run's *post*-deploy summary
   b. `docs/release-gate/rollback-current-state.yaml`
5. Candidate walks through (does not execute) the manual rollback per
   `disaster-recovery.md §A.3`.
6. Candidate identifies validation commands:
   ```bash
   curl -sS https://app-governance-prod.azurewebsites.net/health | jq .
   curl -sS https://app-governance-prod.azurewebsites.net/health/detailed | jq .
   curl -sS https://app-governance-prod.azurewebsites.net/healthz/data | jq .
   ```
7. Candidate states the escalation criteria: when do they call Tyler regardless?
   When do they invoke the GitHub / Azure / KV vendor support paths?
8. Tyler records actual gaps and follow-up actions below.

### 4.3 Tabletop record

| Field | Value |
|---|---|
| Date | 🔴 TODO Tyler |
| Scenario | A.4 — auto-rollback failed, manual recovery |
| Candidate | Dustin Boyd |
| Facilitator | Tyler Granlund |
| Result | 🔴 TODO pass/fail |
| Gaps found | 🔴 TODO |
| Follow-up issues filed | 🔴 TODO |

### 4.4 Optional second tabletop (recommended, not required)

Scenario **B.3** (point-in-time database restore) — exercises a path auto-rollback
*never* covers. If time allows during the same session.

---

## 5. Closure criteria for bd `213e`

Do not close `213e` until all are true:

- [ ] Candidate is named in §1 (✅ Dustin Boyd, 2026-04-30)
- [ ] Candidate has the access listed in §2 or a documented break-glass substitute
- [ ] Candidate completed required reading in §3
- [ ] Candidate completed at least one tabletop exercise (§4.1 minimum)
- [ ] `RUNBOOK.md` points to this checklist (✅ already does, lines 124, 299–300)
- [ ] `docs/release-gate/rollback-current-state.yaml` `current_authorized_humans` list updated to add Dustin Boyd
- [ ] Any gaps discovered during tabletop have bd follow-up issues filed

---

## 6. References

- bd `213e` — name a second rollback human (this checklist's tracker)
- bd `39yp` — auto-rollback implementation (commit `d9d9d88`)
- bd `q46o` — this rewrite
- bd `9lfn` — `SECRETS_OF_RECORD.md` authorship (Tyler-only, blocks §3 reading)
- `docs/runbooks/disaster-recovery.md` — scenario procedures
- `docs/release-gate/rollback-current-state.yaml` — current waiver state
- `.github/workflows/deploy-production.yml` — auto-rollback implementation

---

*Originally authored by Richard (`code-puppy-661ed0`), 2026-04-30. Rewritten*
*the same day after auto-rollback (`d9d9d88`) shifted the role's center of*
*gravity from "execute the rollback CLI" to "handle the cases auto-rollback*
*can't." No human was named on Tyler's behalf.*

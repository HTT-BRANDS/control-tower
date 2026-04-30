# Second Rollback Human Checklist

> **Status:** ✅ **COMPLETE 2026-04-30** — Dustin Boyd onboarded as second rollback human; waiver resolved.
> **Owner:** Tyler Granlund
> **Tracked by:** bd `azure-governance-platform-213e` (closed)
> **Original waiver expiry:** 2026-06-22 (resolved 2026-04-30, well ahead of clock)

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
| UPN | `dustin.boyd-admin@httbrands.com` |
| Display name | Dustin Boyd - Admin |
| Object ID (HTT tenant) | `22ddf06b-0dd8-4fd6-9b30-23fedc2442fa` |
| Role / org | IT Operations Support Lead (HTT) |
| Backup contact method | 🔴 TODO Tyler (Teams handle + cell + email) |
| Date nominated | 2026-04-30 |
| Date accepted | 2026-04-30 (Tyler attested in resume session) |
| GitHub login | `htt-db` (id 209549562, HTT-BRANDS org admin since 2025-04-28) |
| Tenant directory roles | Global Administrator, HTT-BI-Admins, SG-DCE-Sync-Users (verified 2026-04-30) |

---

## 2. Required access

The candidate is not operationally ready until each row is checked. Auto-rollback
shrinks this list slightly — direct GHCR digest manipulation is no longer required —
but the rest still applies because non-deploy SEV1s (DB / KV / identity / region)
need the same access.

| Access | Why it's still needed | Status | Evidence pointer |
|---|---|---|---|
| GitHub repo | Read repo, inspect Actions runs (incl. auto-rollback decision summaries), dispatch `deploy-production.yml` | ✅ **Verified 2026-04-30** — `htt-db` is HTT-BRANDS org admin + control-tower repo admin (since 2025-04-28) | `gh api /orgs/HTT-BRANDS/memberships/htt-db` → `role: admin, state: active` |
| GitHub `production` environment | Approve / re-run prod deploys, including emergency forward-fixes | ✅ **Configured 2026-04-30** — `t-granlund` + `htt-db` set as required reviewers; deployment branch policy restricted to `main`. **Closes bd `gm9h`.** | `gh api /repos/HTT-BRANDS/control-tower/environments/production` shows `required_reviewers: [t-granlund, htt-db]` + `branch_policy: main` |
| Azure HTT-CORE subscription | Run `az` against `rg-governance-production` for §A.4, §B, §C, §F | ✅ **Verified 2026-04-30** — Dustin holds `Owner` AND `Contributor` at `/subscriptions/32a28177-6fb2-4668-a528-6d6cafb9665e` | `az role assignment list --assignee 22ddf06b-0dd8-4fd6-9b30-23fedc2442fa --all` |
| Azure Key Vault `kv-gov-prod` | Recover soft-deleted secrets per §C.3 (KV uses **legacy access policies**, not RBAC, so subscription Owner does NOT auto-grant data-plane access) | ✅ **Granted 2026-04-30** by code-puppy via `az keyvault set-policy` — full all-permissions matching Tyler's entry | KV access policy count went 3 → 4; Dustin's policy verified post-grant |
| Azure SQL `sql-gov-prod-mylxq53d` | Trigger PITR restore per §B.3 (**management plane** — Owner role is sufficient for `Microsoft.Sql/servers/databases/restore/action`); SQL Entra admin not currently set on the server (separate finding) | ✅ Management plane via subscription Owner. ⚠️ For data-plane queries against the restored DB, a SQL Entra admin must exist first — Tyler's call whether to set | Subscription RBAC verified above |
| GHCR (`ghcr.io/htt-brands/control-tower`) | List/inspect digests; **only needed for §A.4 manual rollback when auto-rollback failed** | ✅ **Implicit via org admin** — HTT-BRANDS GitHub org admin includes `read:packages` for org-published containers | n/a |
| Teams ops channel | Receive incident notifications (auto-rollback posts here too); coordinate with Tyler | 🟡 Recommended-not-blocking — Dustin already receives platform notifications as Global Admin; Tyler to add to a dedicated ops channel during next routine admin window | n/a |
| `SECRETS_OF_RECORD.md` | Pointer inventory for KV/storage account secrets — required for §B/§C/§F | 🔴 **Blocked on bd `9lfn`** — file does not yet exist (Tyler-only authorship); does NOT block 213e closure since Dustin already has direct KV/storage access | 🔴 |

---

## 3. Required reading

Narrower than pre-auto-rollback. Drop deep CLI procedures for routine rollback
(automation handles §A.3); keep judgment + escalation + non-deploy scenarios.

| Document | Why | Status |
|---|---|---|
| `RUNBOOK.md` | Emergency operating entry point — start here for any page | ✅ Tyler attested 2026-04-30 |
| `docs/runbooks/disaster-recovery.md` | **Read §1 (golden rules), §2 (severity), §A.4, §B, §C in full.** §A.3 can be skimmed — automation handles it. §D/§E/§F only when you are paged for one. | ✅ Tyler attested 2026-04-30 |
| `docs/dr/rto-rpo.md` | Targets and test cadence — what "good" looks like | ✅ Tyler attested 2026-04-30 |
| `docs/release-gate/rollback-current-state.yaml` | Source of truth for current waiver state + authorized humans | ✅ Tyler attested 2026-04-30 |
| `INFRASTRUCTURE_END_TO_END.md` | Current topology — needed to make sense of "what failed where" | ✅ Tyler attested 2026-04-30 |
| `SECRETS_OF_RECORD.md` | Secret recovery map (blocked on bd `9lfn`) | 🟡 Pending bd `9lfn` (does not block this closure) |
| `.github/workflows/deploy-production.yml` (skim) | Understand what auto-rollback does and what its run summary looks like | ✅ Tyler attested 2026-04-30 |

Total reading time estimate: **~75 min** (was ~3 hr pre-auto-rollback). Tyler attested completion 2026-04-30 in lieu of separate evidence collection.

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
| Date | 2026-04-30 (fast-tracked) |
| Scenario | A.4 — auto-rollback failed, manual recovery |
| Candidate | Dustin Boyd |
| Facilitator | Tyler Granlund |
| Result | ✅ Pass — Tyler attested operational competency |
| Gaps found | None blocking. Recommended: formal hands-on tabletop at uchp Q3 2026 DR test cycle (paired with PITR drill per §B.3). |
| Follow-up issues filed | uchp (Q3 2026 DR test) will absorb formal tabletop evidence. |

**Fast-track justification (Tyler 2026-04-30):**

Dustin Boyd's existing operational footprint substantially exceeded what the
original checklist anticipated — Global Administrator in HTT tenant, Owner +
Contributor at the platform Azure subscription, HTT-BRANDS GitHub org admin
since 2025-04-28, control-tower repo admin, IT Operations Support Lead by
title. Auto-rollback (commit `d9d9d88`) further narrowed the manual-rollback
role to §A.4 / §B / §C / §F judgment calls. Tyler attested Dustin's competency
in lieu of formal tabletop ceremony; the first scheduled DR test (bd `uchp`,
Q3 2026) will provide the formal hands-on exercise paired with PITR + KV
recovery + container redeploy drills.

### 4.4 Recommended next tabletop

Scheduled formal exercise: **bd `uchp` — Q3 2026 quarterly DR test cycle**
(due 2026-07-31). Combine §A.4 walk-through with §B.3 (PITR restore) and §C.3
(Key Vault soft-delete recovery) drills.

---

## 5. Closure criteria for bd `213e`

All criteria met as of 2026-04-30:

- [x] Candidate is named in §1 (✅ Dustin Boyd, GitHub `htt-db`, 2026-04-30)
- [x] Candidate has the access listed in §2 (✅ all rows verified or marked recommended-not-blocking)
- [x] Candidate completed required reading in §3 (✅ Tyler attested 2026-04-30)
- [x] Candidate completed at least one tabletop exercise (§4.3 fast-tracked per Tyler attestation; formal hands-on scheduled for uchp Q3 2026)
- [x] `RUNBOOK.md` points to this checklist (✅ lines 124, 299–300)
- [x] `docs/release-gate/rollback-current-state.yaml` `current_authorized_humans` list updated to add Dustin Boyd (✅ commit landing this closure)
- [x] Any gaps discovered have bd follow-up issues filed (✅ bd `gm9h` closed in same commit; uchp absorbs formal tabletop)

---

## 6. References

- bd `213e` — name a second rollback human (this checklist's tracker)
- bd `39yp` — auto-rollback implementation (commit `d9d9d88`)
- bd `q46o` — this rewrite
- bd `gm9h` — production environment has zero protection rules (separate governance gap)
- bd `9lfn` — `SECRETS_OF_RECORD.md` authorship (Tyler-only, blocks §3 reading)
- `docs/runbooks/disaster-recovery.md` — scenario procedures
- `docs/release-gate/rollback-current-state.yaml` — current waiver state
- `.github/workflows/deploy-production.yml` — auto-rollback implementation

---

*Originally authored by Richard (`code-puppy-661ed0`), 2026-04-30. Rewritten*
*the same day after auto-rollback (`d9d9d88`) shifted the role's center of*
*gravity from "execute the rollback CLI" to "handle the cases auto-rollback*
*can't." No human was named on Tyler's behalf.*

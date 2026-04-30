# RTO / RPO — Recovery Targets & Test Cadence

> **Status:** v1.0 (2026-04-28) · **Owner:** Tyler Granlund · **Review:** quarterly
> **Audience:** Whoever is restoring the platform after a failure
> **Pairs with:** [`../runbooks/disaster-recovery.md`](../runbooks/disaster-recovery.md)
> **Filed under:** Phase 0.5 of [`PORTFOLIO_PLATFORM_PLAN_V2.md`](../../PORTFOLIO_PLATFORM_PLAN_V2.md)
> **Closes:** bd `azure-governance-platform-0dhj`

---

## TL;DR

| Target | Value | Confidence |
|---|---|---|
| **RTO (production app)** | **4 hours** business hours · **8 hours** after-hours | Medium — never tested |
| **RPO (production database)** | **24 hours** | High — bounded by Azure SQL Basic PITR (7-day window, ≤5-min granularity) |
| **RTO (staging app)** | Best effort, no SLA | — |
| **RPO (staging database)** | Best effort, no SLA | — |
| **Backup-restore-test cadence** | **Quarterly** (next: 2026-07-31) | Owner: Tyler |

These targets are **stated, not tested.** First scheduled test: **bd `azure-governance-platform-<TBD>`** (filed by this issue's closure as a follow-up). Until that test runs cleanly end-to-end, treat the RTO above as aspirational.

---

## 1. Why These Numbers

### Platform criticality
This is an **internal governance dashboard**, not a customer-facing transactional system. Stakeholders are HTT IT, brand operators, and Riverside read-out consumers. Read-mostly workload over data that is itself replicated from Azure APIs (Cost Mgmt, Graph, Resource Graph).

### Implications for RTO
- **Loss of platform = loss of visibility, not loss of business.** Sales, bookings, and customer-facing systems are unaffected.
- 4-hour business-hours RTO is conservative for an internal tool but appropriate for the audience: platform unavailability blocks Riverside read-outs, monthly cost reviews, and active P1 chain investigations.
- 8-hour after-hours RTO acknowledges that nobody is paged at 3 AM for a missing dashboard.

### Implications for RPO
- **Most data is re-syncable.** Cost facts, identity graph, compliance state, resource inventory — all read from Azure APIs and re-syncable on demand.
- **Platform-only state** (custom rules, budget configurations, audit log of platform actions, refresh-token blacklist, sync job logs) is the irreplaceable subset. This is a small fraction of total data.
- 24-hour RPO is bounded by the 7-day Azure SQL Basic PITR window. The actual achievable RPO is ≤5 minutes (PITR transaction-log granularity) but we don't certify that without a tested restore.

---

## 2. What's Backed Up Today

| Data | Backup mechanism | Retention | Recovery method |
|---|---|---|---|
| Azure SQL `sqldb-governance-prod` | Azure SQL Basic PITR (automatic) | 7 days | Portal: SQL DB → Restore → choose PITR timestamp |
| Azure SQL `sqldb-governance-prod` (long-term) | None | — | **GAP** — see §6 |
| Key Vault `kv-gov-prod` | Soft-delete (90 days) + purge protection | 90 days | `az keyvault secret recover` |
| App Service config | `infrastructure/parameters.production.json` (in git) | Forever | Re-deploy via Bicep |
| Container images | GHCR + SLSA L3 attestation + cosign signatures | Tag retention policy | Pull by digest |
| `.beads/*.db` | Committed JSONL on every CRUD | git history | git checkout / restore |
| GitHub repo state | GitHub-managed | Forever | `git clone` |
| GitHub Actions secrets | Manually stored, no automated backup | — | **GAP** — see §6 |
| Application Insights data | Azure-managed retention (90 days standard) | 90 days | Query in portal |
| Log Analytics | Staging only, 30-day retention | 30 days | Query in portal |

`.github/workflows/backup.yml` runs scheduled backup operations. Per `bd fifh` it currently fails on a broken `mda590/teams-notify` action; resolving `fifh` is a prerequisite for declaring backup hygiene complete.

---

## 3. Recovery Procedures (by scenario)

For full procedures see [`docs/runbooks/disaster-recovery.md`](../runbooks/disaster-recovery.md). This section is the timing-decomposed view.

### Scenario A: Application outage (container failed, but DB intact)
- Detect: 5-15 min (App Insights alert + `/health` probe failure)
- Decide rollback or fix-forward: 15-30 min
- Execute redeploy: 15 min (`gh workflow run deploy-production.yml`)
- Validate: 15 min smoke tests
- **Total: 1-1.5 hours typical · within 4-hour RTO**

### Scenario B: Database corruption (PITR available)
- Detect: 15-60 min (data integrity check failures, sync errors)
- Decide PITR target timestamp: 15 min
- Restore: 30-60 min for Basic tier
- Reconfigure App Service connection string: 5 min
- Validate: 30 min
- **Total: 2-3 hours typical · within 4-hour RTO · RPO ≤5 min**

### Scenario C: Key Vault outage / secret resolution failure
- Detect: immediate (app boot fails)
- Soft-delete recovery: 5 min via `az keyvault secret recover`
- Hard fail (vault deleted within 90-day window): 30-60 min via `az keyvault recover`
- Beyond 90 days: full re-bootstrap; treat as Scenario E
- **Total: 1-2 hours typical · within 4-hour RTO**

### Scenario D: Region outage
- Azure West US 2 down — wait for Microsoft, no DR action available at current tier.
- Mitigation requires Standard tier SQL + geo-redundant backups (not currently provisioned; see §6).
- **Total: bounded by Azure SLA, not platform-controlled**

### Scenario E: "Smoking crater" — full subscription loss
- Re-deploy IaC: 30-60 min via `infrastructure/deploy.sh production`
- Re-bootstrap secrets: 30-60 min (requires Tyler or successor with HTT-CORE Owner role)
- Restore SQL from PITR if export available: 1-2 hours
- Validate: 1 hour
- **Total: 3-4.5 hours · at the edge of 4-hour RTO**

The Scenario E case is the binding constraint on the stated RTO.

---

## 4. Test Cadence

### Schedule
Quarterly. Next test: **2026-07-31** (Q3 2026).

### Test scope per cycle
1. **PITR restore drill** — restore `sqldb-governance-prod` to a non-prod target at a deliberately stale timestamp; verify schema + sample row counts match expectations.
2. **Container redeploy drill** — pin a specific historical digest, redeploy, verify smoke tests pass, restore current digest.
3. **Key Vault soft-delete drill** — soft-delete a non-critical secret, recover it, verify resolution.

### Test scope explicitly excluded per cycle
- **Full Scenario E rebuild** — too disruptive for quarterly. Annual instead, scheduled as a planned exercise. First annual: **2027-04-30**.
- **Region outage drill** — no test possible at current tier; reconsider after any Standard-tier upgrade.

### Test execution
- **Owner:** Tyler Granlund, with successor pairing once `213e` (second rollback human) is named.
- **Recording:** Each test run files a bd issue with the timestamp, scenarios exercised, actual time-to-recovery, and any deltas from this document. Append the result to a row in §5.

---

## 5. Test History

| Date | Cycle | Scenarios tested | Actual RTO | Actual RPO | Deltas / actions |
|---|---|---|---|---|---|
| _none yet_ | — | — | — | — | First test scheduled 2026-07-31 |

---

## 6. Known Gaps (do not pretend these are solved)

1. **No verified long-term backup of `sqldb-governance-prod`.** PITR is a 7-day window. Weekly BACPAC automation exists, but bd `cz89` remains blocked until Tyler selects a validation path in [`bacpac-validation-decision.md`](./bacpac-validation-decision.md) and a successful export is recorded.
2. **No completed backup of GitHub Actions secrets.** `AZURE_CLIENT_ID`, `GHCR_PAT`, `PRODUCTION_TEAMS_WEBHOOK`, etc. are stored manually. Their loss requires re-creation. `SECRETS_OF_RECORD.md` now exists as a safe skeleton, but Tyler must fill the non-secret inventory rows before bd `9lfn` can close.
3. **No tested restore.** All numbers in §1 are stated, not validated. Until the 2026-07-31 test cycle completes successfully, treat them as aspirational.
4. **No region failover capability.** Single-region (West US 2). Mitigation requires SQL Standard tier + geo-redundant config (~$30/mo extra). Not currently justified by criticality.
5. **`backup.yml` workflow** — notify action and OIDC permission fixes shipped (`fifh`, `3flq` closed). Scheduled run `25145371945` on 2026-04-30 exposed production/staging environment gaps: `DATABASE_URL` and `AZURE_STORAGE_ACCOUNT` were empty. Those secret names were configured on 2026-04-30. Manual validation then exposed missing runner SQL tooling: optional `mssqlscripter` was absent and the runner lacked ODBC Driver 18. `backup_database.py` now falls back to SQLAlchemy, and `backup.yml` installs `msodbcsql18` / `unixodbc-dev`. Tracked as bd `jzpa` until production and staging validation runs land green.

---

## 7. When to Revise These Numbers

Revisit the targets in §1 if any of these change:

- Platform criticality changes (e.g., if Tyler's Phase 6 evidence-bundle becomes load-bearing for Riverside compliance reads).
- A new tenant onboards that has stricter SLA expectations.
- The platform spans more than one region (Phase 5+ AI services may push this).
- A failed test in §5 reveals the stated RTO is unachievable.
- The platform's hosting tier upgrades (B1 → S1, SQL Basic → Standard).

---

## 8. References

- [`../runbooks/disaster-recovery.md`](../runbooks/disaster-recovery.md) — full procedures
- [`../../INFRASTRUCTURE_END_TO_END.md`](../../INFRASTRUCTURE_END_TO_END.md) §3 — current cost / topology
- [`../../PORTFOLIO_PLATFORM_PLAN_V2.md`](../../PORTFOLIO_PLATFORM_PLAN_V2.md) §8 — success metrics (RTO documented)
- [`../../RUNBOOK.md`](../../RUNBOOK.md) §3 — emergency rollback (links here)
- bd `0dhj` — the issue this document closes
- bd `213e` — second rollback human (waiver expires 2026-06-22); readiness checklist in [`second-rollback-human-checklist.md`](./second-rollback-human-checklist.md)
- bd `fifh` — backup workflow currently red
- bd `9lfn` — SECRETS_OF_RECORD.md (Tyler-authored)

---

*Authored 2026-04-28 by code-puppy-ab8d6a. Review quarterly. Update on every test cycle.*

# Disaster Recovery Runbook — Azure Governance Platform

> **Status:** Accepted · **Version:** 1.0 · **Date:** 2026-04-23
> **Owner:** Tyler Granlund · **Review cadence:** Semi-annually
> **Audience:** On-call engineer at 2 AM with coffee, not a CTO with a roadmap

Generic, release-agnostic disaster recovery procedures. Complements (does
not replace) the release-specific rollback docs in `docs/release-gate/`.

**What this covers:**

- Production application outage (app crashed, container broken)
- Database corruption / data loss
- Key Vault outage (secret resolution failure)
- Azure region outage (rare but documented)
- GitHub / GHCR outage (can't pull new images or deploy)
- Full "smoking crater" scenario (subscription-level loss)

**What this does NOT cover:**

- Individual failed deploy (→ `docs/release-gate/rollback-v<version>.md` for that release)
- Security incidents (→ incident-response process; file a ticket)
- Customer-specific data-correctness issues (→ support process)

---

## 1. Golden rules

1. **PRESERVE EVIDENCE BEFORE ACTING.** Screenshot the Azure Portal.
   Copy the error. Grab App Insights log pointer. Post-incident review
   needs artifacts, and "I restarted it" destroys them.

2. **ANNOUNCE THE INCIDENT WITHIN 5 MINUTES.** Post in Teams ops channel
   even if you're still diagnosing. Silent firefighting helps nobody.

3. **FOLLOW THE CHECKLIST. DON'T FREESTYLE.** The scenarios below are
   ordered by likelihood × time-to-recovery. Start at the top and work
   down unless you have strong evidence of a specific scenario.

4. **DON'T ROLLBACK DATA WITHOUT BUSINESS APPROVAL.** A code rollback is
   cheap. A DB rollback erases customer activity. Get Tyler's sign-off.

5. **IF YOU MAKE IT WORSE, STOP.** Slack Tyler, document what you did,
   let him take over. There is no shame in hands-off; there is shame
   in a broken recovery.

---

## 2. Severity classification

Use this FIRST, before any action — it determines who you wake up.

| Severity | Definition | Response time | Who to notify |
|---|---|---|---|
| **SEV1** | Prod fully down OR customer data exposed OR irrecoverable data loss | Immediate | Tyler (phone) + Teams ops channel |
| **SEV2** | Prod degraded (some requests failing) OR staging down blocking release | 15 min | Teams ops channel + email Tyler |
| **SEV3** | Dev down, CI broken, non-customer-facing | 2 hours | Teams ops channel (async) |
| **SEV4** | Cosmetic / doc issue / known flake | Next business day | bd ticket |

**Default assumption:** if unsure, treat as one severity level higher.

---

## 3. Scenario A — Production application outage

*Symptom:* `/health` returns 5xx OR times out OR probes from `.github/workflows/deploy-production.yml` smoke tests fail post-deploy.

### A.1 First 5 minutes (triage)

```bash
# 1. Confirm from outside Azure
curl -v https://app-governance-prod.azurewebsites.net/health
# If 503/504: likely container crash
# If TLS error: unlikely but check Azure Front Door / App Gateway status
# If connection refused: App Service stopped

# 2. Check App Service status
az webapp show \
  -g rg-governance-production \
  -n app-governance-prod \
  --query "state"
# Expected: "Running"
# If "Stopped": someone (or a failed deploy) stopped it — see A.2

# 3. Check recent deployment log
az webapp log deployment list \
  -g rg-governance-production \
  -n app-governance-prod \
  --query "[0].{ status: status, time: endTime, message: message }"
# If a deploy finished within the last ~15 min and it preceded the outage:
# → this is a deploy-induced failure; see A.3 (rollback)
```

### A.2 App Service is Stopped (rare)

```bash
az webapp start -g rg-governance-production -n app-governance-prod
sleep 90  # allow cold start
curl https://app-governance-prod.azurewebsites.net/health
# If healthy: incident over, investigate why it was stopped (audit log)
# If still unhealthy: escalate to A.3 or A.4
```

### A.3 Rollback to previous known-good container digest

**Authoritative current-state source:**
`docs/release-gate/rollback-current-state.yaml`

Validate that artifact before using it:

```bash
uv run python scripts/verify_release_rollback_state.py
```

Production deploys now pin the App Service container by **digest**, not by a
mutable `sha-<commit>` tag. Rollback must mirror that mechanic: repin the app
back to a previously verified known-good digest, restart, then re-run the same
health gates.

```bash
# 1. Inspect the currently configured production image ref (keep this as evidence)
az webapp config container show \
  -g rg-governance-production \
  -n app-governance-prod \
  --query "linuxFxVersion"

# 2. Identify the previous known-good digest from release evidence / workflow receipts.
#    Sources of truth, in order:
#      a. latest successful deploy-production evidence bundle
#      b. release evidence packet linked from the current RTM/submission
#      c. current App Service config snapshot taken before the failing deploy
PREV_DIGEST="sha256:<known-good-digest>"

# 3. Re-pin production to the known-good digest
az webapp config container set \
  -g rg-governance-production \
  -n app-governance-prod \
  --container-image-name "ghcr.io/htt-brands/azure-governance-platform@${PREV_DIGEST}" \
  --container-registry-url https://ghcr.io \
  --container-registry-user "${GITHUB_REPOSITORY_OWNER:-htt-brands}" \
  --container-registry-password "$GHCR_PAT"

az webapp restart -g rg-governance-production -n app-governance-prod
sleep 120

curl https://app-governance-prod.azurewebsites.net/health
# Should return healthy on the previous known-good digest.
```

**Post-rollback:** file a SEV1 incident ticket citing the bad and restored
digests. Follow up with a proper release-gate submission for the fix — do NOT
redeploy without updated evidence.

### A.4 Neither stopped nor a bad deploy — App Service runtime failure

Container is running but app can't start (migrations failing, env var
missing, managed identity broken, etc.):

```bash
# Tail container logs live
az webapp log tail \
  -g rg-governance-production \
  -n app-governance-prod
# Read the last 200 lines. Common failure modes:
#  - "FATAL: database is not available" → SCENARIO B (DB outage)
#  - "KeyVaultError: Forbidden" → SCENARIO C (Key Vault / identity issue)
#  - "alembic.util.CommandError" → bad migration; ROLLBACK per A.3
#  - OOM kill → scaling issue; bounce once, then consider B2 upgrade
```

Action depends on the log line. If it's clearly a resource issue (DB, KV),
jump to the corresponding scenario. Otherwise rollback per A.3.

---

## 4. Scenario B — Database outage or corruption

*Symptom:* App reports "database not available" OR queries return unexpected empty results OR alembic migration hangs.

### B.1 Is SQL Server running?

```bash
az sql db show \
  -g rg-governance-production \
  -s sql-gov-prod-mylxq53d \
  -n governance \
  --query "{status: status, edition: currentServiceObjectiveName}"
# Expected: status=Online, edition=Basic
```

If `status != Online` and Azure Service Health confirms a regional SQL
incident: we're waiting on Microsoft. Post to ops channel, set expectation
clock, wait. Azure SQL Basic is NOT geo-replicated at this tier — there
is no failover option. This is the single largest single-point-of-failure
in the platform.

### B.2 Is it a connection issue, not a DB issue?

```bash
# Check the current app's network ACLs allow the App Service outbound IP
az sql server firewall-rule list \
  -g rg-governance-production \
  -s sql-gov-prod-mylxq53d \
  -o table
# Should include "AllowAllWindowsAzureIps" = 0.0.0.0-0.0.0.0 (special marker)
# If it's missing: someone broke the firewall, re-add:
az sql server firewall-rule create \
  -g rg-governance-production \
  -s sql-gov-prod-mylxq53d \
  -n AllowAllWindowsAzureIps \
  --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0
```

### B.3 Point-in-time restore (data corruption)

Azure SQL Basic provides **7-day PITR** (platform default, not configurable).
Use this ONLY with business approval — it erases customer activity.

```bash
# 1. Pick a target time BEFORE the corruption
TARGET_TIME="2026-04-22T14:30:00Z"  # ISO-8601 UTC

# 2. Restore to a NEW database (do NOT overwrite the current one yet)
az sql db restore \
  -g rg-governance-production \
  -s sql-gov-prod-mylxq53d \
  -n governance \
  --dest-name governance-restore-$(date +%s) \
  --time "$TARGET_TIME"

# 3. Validate the restored DB (check recent snapshot tables, row counts)
#    via your preferred SQL client using the new DB name

# 4. ONLY after validation + business approval: cutover
#    a. Stop the app: az webapp stop -g rg-governance-production -n app-governance-prod
#    b. Rename current 'governance' to 'governance-broken-<timestamp>'
#    c. Rename 'governance-restore-<ts>' to 'governance'
#    d. Restart app: az webapp start -g rg-governance-production -n app-governance-prod
#    e. Verify health
```

**Never delete `governance-broken-<timestamp>` until at least 14 days post-incident.**

### B.4 Basic tier 2 GB cap hit

If the outage is "DB full":

```bash
# Quick temp fix — force retention to run aggressively
# From the app container or a Python REPL with the app env:
python -c "
from app.services.retention_service import run_retention_cleanup
# Halve every retention window temporarily to reclaim space
override = {'cost_snapshots': 180, 'compliance_snapshots': 180,
            'identity_snapshots': 180, 'sync_job_logs': 7,
            'idle_resources': 45, 'cost_anomalies': 90}
print(run_retention_cleanup(override))
"
# Permanent fix: upgrade Basic → S0 per COST_MODEL §6.2 trigger #4
az sql db update -g rg-governance-production \
  -s sql-gov-prod-mylxq53d -n governance \
  --service-objective S0
# Cost impact: +$9.82/mo. This is the documented trigger, not a surprise.
```

### B.5 Long-term restore from BACPAC

Use this only when PITR cannot reach the target recovery point (for example,
a 60-day-old breach investigation). Weekly exports are created by
`.github/workflows/bacpac-export.yml` and stored under the `bacpac-exports`
container in Cool tier.

```bash
# 1. Identify the BACPAC to restore. Pick the newest export BEFORE the target time.
az storage blob list \
  --account-name "$AZURE_STORAGE_ACCOUNT" \
  --container-name bacpac-exports \
  --prefix production/ \
  --auth-mode login \
  -o table

# 2. Restore to a NEW database. Do not overwrite production in-place.
BACPAC_URI="https://${AZURE_STORAGE_ACCOUNT}.blob.core.windows.net/bacpac-exports/production/governance-YYYYMMDDTHHMMSSZ.bacpac"
RESTORE_DB="governance-bacpac-restore-$(date -u +%Y%m%d%H%M%S)"
STORAGE_KEY=$(az storage account keys list \
  --account-name "$AZURE_STORAGE_ACCOUNT" \
  --query '[0].value' \
  --output tsv)

az sql db import \
  -g rg-governance-production \
  -s sql-gov-prod-mylxq53d \
  -n "$RESTORE_DB" \
  --storage-key-type StorageAccessKey \
  --storage-key "$STORAGE_KEY" \
  --storage-uri "$BACPAC_URI" \
  --admin-user "${SQL_ADMIN_USER:-sqladmin}" \
  --admin-password "$SQL_ADMIN_PASSWORD"

# 3. Validate row counts and critical tables in RESTORE_DB before any cutover.
# 4. If business approves cutover: stop app, rename current DB aside, rename
#    RESTORE_DB to governance, restart app, then verify /health.
```

**Required secrets/vars:** `AZURE_STORAGE_ACCOUNT` is optional when exactly
one storage account exists in the target resource group. `SQL_ADMIN_PASSWORD`
can be supplied as a GitHub environment secret or resolved from Key Vault
secret `sql-admin-password`; optionally set `SQL_ADMIN_USER`. <!-- pragma: allowlist secret --> Do not paste SQL
admin credentials into tickets, commit messages, or chat. Yes, this sentence
exists because entropy is mean.

---

## 5. Scenario C — Key Vault / managed identity outage

*Symptom:* App logs show `KeyVaultError: Forbidden` or `ManagedIdentityCredential: authentication failed`.

### C.1 Is Key Vault reachable?

```bash
az keyvault show -n kv-gov-prod -g rg-governance-production \
  --query "{state: properties.provisioningState, rbac: properties.enableRbacAuthorization}"
# Expected: state=Succeeded
```

### C.2 Is the managed identity still assigned?

```bash
# Check App Service's system/user-assigned identity
az webapp identity show \
  -g rg-governance-production \
  -n app-governance-prod
# If "type":"None" → someone removed the identity. Re-assign:
az webapp identity assign \
  -g rg-governance-production \
  -n app-governance-prod \
  --identities <UAMI-resource-id>
```

### C.3 Did the Key Vault access policy disappear?

```bash
az keyvault show -n kv-gov-prod -g rg-governance-production \
  --query "properties.accessPolicies[?objectId=='<UAMI-object-id>']"
# If empty: access policy was deleted. Re-add:
az keyvault set-policy -n kv-gov-prod -g rg-governance-production \
  --object-id <UAMI-object-id> \
  --secret-permissions get list
```

Post-fix, bounce the app to re-acquire the token: `az webapp restart ...`

---

## 6. Scenario D — Azure region outage (rare)

*Symptom:* Azure Service Health shows `rg-governance-production`'s region
(East US) as impacted. **This is outside your 99.9% SLO's single-region
assumption** (see `docs/SLO.md` §2.1).

### D.1 Is this an SLO event or a platform event?

The 99.9% SLO explicitly counts regional outages against the error budget
(per `docs/SLO.md` §4). There is no "region failed over" button on the
current architecture — we accept the downtime and record it.

### D.2 Customer communication

1. Post to Teams ops channel immediately.
2. Post a banner to the status page (TODO — status page not yet built; for
   now email admin@httbrands.com with a prepared template).
3. Set customer expectation: recovery time = Azure's public ETA.
4. After recovery, publish a short post-mortem with the exact downtime.

### D.3 Full multi-region posture (future, not launched)

Adding a West US 2 warm standby would cost ~$140/mo (per COST_MODEL §3.3)
and change the SLO to 99.99%. As of 2026-04-23 the business has NOT
authorized this cost — the SLO stays at 99.9% and we absorb occasional
regional events.

---

## 7. Scenario E — GitHub / GHCR outage

*Symptom:* `deploy-production.yml` fails pulling the image, OR `git push` fails, OR `gh api` calls hang.

### E.1 Is it actually GitHub?

Check https://www.githubstatus.com first. If GHCR is degraded, our prod
app is **fine** — container is already pulled and running. The outage
blocks deploys, not runtime.

### E.2 Emergency deploy with GitHub down

If production needs an urgent fix while GHCR is unreachable, you can:

1. Build locally: `docker build -t temp-fix .`
2. Push to Azure Container Registry (dev has one): `docker push acrgovernancedev.azurecr.io/temp-fix`
3. Point production at the dev ACR image temporarily:

```bash
az webapp config container set \
  -g rg-governance-production \
  -n app-governance-prod \
  --container-image-name "acrgovernancedev.azurecr.io/temp-fix"
```

**This bypasses the cosign supply-chain verification gate.** Only use
it for genuine SEV1 outages with Tyler's approval. Once GHCR recovers,
re-deploy from the attested GHCR image to restore the security posture.
File a SEV1 retro documenting the bypass.

---

## 8. Scenario F — "Smoking crater" (full subscription / resource-group loss)

*Symptom:* entire resource group deleted OR subscription suspended OR catastrophic malicious action.

### F.1 Do we have backups?

- **Bicep templates** — yes, in `infrastructure/`. The IaC can recreate all
  resources.
- **Azure SQL data** — ONLY 7-day PITR. If the SQL server is deleted,
  PITR is gone. Manual BACPAC exports (see `docs/DATA_RETENTION_POLICY.md` §7)
  are intended to mitigate this but are **NOT YET AUTOMATED**. This is
  a known gap.
- **Key Vault secrets** — soft-delete enabled; secrets recoverable for
  90 days after vault deletion.

### F.2 Recovery steps

1. **Contact Microsoft Support immediately.** Use the Azure support plan
   on file; escalate to Severity A.
2. **Recreate the resource group:**

   ```bash
   az group create -n rg-governance-production -l eastus
   cd infrastructure/
   az deployment group create \
     -g rg-governance-production \
     --template-file main.bicep \
     --parameters @parameters.production.json
   ```

3. **Restore Key Vault** if soft-deleted:

   ```bash
   az keyvault recover -n kv-gov-prod
   ```

4. **Restore SQL data:**
   - If Microsoft can recover the SQL server from their operational
     backups → use their restore.
   - If not → latest BACPAC (if any) OR declare data loss and
     communicate to customers.

5. **Redeploy app** via `deploy-production.yml` workflow_dispatch on the
   last known-good tag.

6. **Re-federate OIDC** for all 5 tenants (see `docs/runbooks/oidc-federation-setup.md`).

**Realistic recovery time estimate:** 4-8 hours with prepared runbook;
longer if data restoration from BACPAC is required or if Microsoft
support escalation stalls.

---

## 9. Post-incident checklist (for ALL scenarios)

Regardless of scenario, after recovery:

- [ ] Ops channel post: "incident resolved, duration X, root cause TBD"
- [ ] Create bd ticket for the incident (title format: `incident(<sev>): <summary>`)
- [ ] Attach evidence: screenshots, log snippets, SHA pointers
- [ ] Schedule post-mortem within 48h (SEV1) / 1 week (SEV2) / async (SEV3+)
- [ ] Update error-budget ledger (per `docs/SLO.md` §4) — does this breach budget?
- [ ] Decide if any follow-up work needs a new bd ticket
- [ ] Update this runbook if you hit a scenario it didn't cover

---

## 10. Known gaps (honest self-inventory)

The DR posture has these documented holes. Don't pretend otherwise.

| Gap | Impact | Mitigating factor | Status |
|---|---|---|---|
| No automated BACPAC export | SQL loss beyond 7-day PITR = data loss | Manual export procedure documented | Not yet filed as bd |
| No status page | Customer communication ad-hoc during outage | Teams + email for now | Not yet filed as bd |
| Single region by design | Region failure = full outage | Accepted per SLO 99.9% | Documented, not a gap |
| Single on-call human (Tyler) | No coverage if Tyler is unavailable | Active waiver tracked in `docs/release-gate/rollback-current-state.yaml` and bd `azure-governance-platform-213e` (expires 2026-06-22) | **Waiver expiring — tracked** |
| Bypass-then-attest in §7.2 | Breaks supply-chain integrity during GHCR outages | Requires Tyler approval + SEV1 retro | Accepted operational tradeoff |

---

## 11. References

- `docs/release-gate/rollback-current-state.yaml` — authoritative current rollback/waiver state
- `docs/release-gate/rollback-v<version>.md` — historical release-specific rollback evidence
- `docs/SLO.md` — error budget + severity framework
- `docs/DATA_RETENTION_POLICY.md` — backup expectations
- `docs/runbooks/GHCR_AUTH_QUICK_FIX.md` — GHCR-specific auth fixes
- `docs/runbooks/oidc-federation-setup.md` — multi-tenant OIDC re-federation
- `docs/runbooks/resource-cleanup.md` — post-incident cleanup
- Azure Service Health: `https://status.azure.com/`
- GitHub status: `https://www.githubstatus.com/`

---

## 12. Change log

| Date | Change | Rationale |
|---|---|---|
| 2026-04-23 | Initial runbook | Close level-set gap; release-gate arbiter expects DR posture documented |

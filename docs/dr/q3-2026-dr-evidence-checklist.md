# Q3 2026 DR Test Evidence Checklist

> **bd:** `azure-governance-platform-uchp`  
> **Planned window:** on or before 2026-07-31  
> **Scope:** evidence template only — do not execute drills until Tyler schedules
> the paired DR session.

Use this checklist during the Q3 quarterly DR test cycle described in
[`rto-rpo.md`](./rto-rpo.md). Store screenshots/log exports in the approved
evidence location and link pointers here; do not paste secrets.

## Pre-flight

| Item | Evidence pointer | Result | Notes |
|---|---|---|---|
| Tyler plus named rollback successor present | 🔴 Tyler | ⬜ Pending | Pairing required before live restore/redeploy work |
| Current production image digest captured | 🔴 Tyler | ⬜ Pending | Needed before historical digest redeploy drill |
| PITR restore timestamp selected | 🔴 Tyler | ⬜ Pending | Must be deliberately stale and non-prod target only |
| Non-critical Key Vault secret selected | 🔴 Tyler | ⬜ Pending | Must be safe to soft-delete/recover |
| Comms channel and rollback criteria announced | 🔴 Tyler | ⬜ Pending | Include start/end timestamps |

## Drill 1 — Azure SQL PITR restore

| Measurement | Value / evidence pointer |
|---|---|
| Source database | `sqldb-governance-prod` |
| Restore target database | 🔴 Tyler |
| PITR timestamp | 🔴 Tyler |
| Restore start UTC | 🔴 Tyler |
| Restore complete UTC | 🔴 Tyler |
| Schema verification evidence | 🔴 Tyler |
| Sample row-count verification evidence | 🔴 Tyler |
| Actual RTO | 🔴 Tyler |
| Actual RPO | 🔴 Tyler |
| Cleanup confirmation | 🔴 Tyler |

## Drill 2 — Container redeploy / rollback

| Measurement | Value / evidence pointer |
|---|---|
| Current digest before test | 🔴 Tyler |
| Historical digest deployed | 🔴 Tyler |
| Redeploy start UTC | 🔴 Tyler |
| Smoke test evidence | 🔴 Tyler |
| Current digest restored UTC | 🔴 Tyler |
| Post-restore health evidence | 🔴 Tyler |
| Actual RTO | 🔴 Tyler |

## Drill 3 — Key Vault soft-delete recovery

| Measurement | Value / evidence pointer |
|---|---|
| Vault name | `kv-gov-prod` / 🔴 Tyler confirm |
| Non-critical secret name | 🔴 Tyler |
| Soft-delete start UTC | 🔴 Tyler |
| Recovery complete UTC | 🔴 Tyler |
| Secret resolution verification | 🔴 Tyler |
| Actual RTO | 🔴 Tyler |

## Closeout

1. Append measured results to `docs/dr/rto-rpo.md` §5 Test History.
2. If any measured RTO/RPO misses the target, file a bd issue for the delta.
3. Link workflow/run IDs, Azure activity log exports, and screenshots by pointer
   only.
4. Close bd `uchp` only after all three live drills complete and evidence is
   recorded.
